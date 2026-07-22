import io
import re
from datetime import datetime, timezone, timedelta

import pandas as pd
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import Response, RedirectResponse

from core import db, now_utc, encrypt_secret
from auth import get_current_user
from email_service import build_variable_map, substitute, test_smtp_connection, send_email
from worker import build_campaign_jobs
from models import (
    ContactCreate, ContactUpdate, GroupCreate, GroupUpdate,
    TemplateCreate, TemplateUpdate, SmtpCreate, SmtpUpdate, SmtpTestRequest,
    CampaignCreate, CampaignUpdate, SettingsUpdate, SmtpTestSendRequest,
)

api = APIRouter(prefix="/api")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SENT_STATUSES = ["sent", "delivered", "opened", "clicked"]

PIXEL = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000d49444154789c6360000002000001e221bc330000000049454e44ae426082"
)


def _oid(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")


def serialize(doc: dict) -> dict:
    if not doc:
        return doc
    out = dict(doc)
    out["id"] = str(out.pop("_id"))
    out.pop("password_enc", None)
    out.pop("imap_password_enc", None)
    return out


def valid_email(e: str) -> bool:
    return bool(e and EMAIL_RE.match(e.strip()))


# ==================== CONTACTS ====================
@api.get("/contacts")
async def list_contacts(
    search: str = "", group_id: str = "", status: str = "",
    user=Depends(get_current_user),
):
    q = {}
    if group_id:
        q["group_id"] = group_id
    if status:
        q["status"] = status
    if search:
        q["$or"] = [
            {"first_name": {"$regex": search, "$options": "i"}},
            {"last_name": {"$regex": search, "$options": "i"}},
            {"email": {"$regex": search, "$options": "i"}},
            {"company": {"$regex": search, "$options": "i"}},
        ]
    docs = await db.contacts.find(q).sort("created_at", -1).to_list(5000)
    return [serialize(d) for d in docs]


@api.post("/contacts")
async def create_contact(payload: ContactCreate, user=Depends(get_current_user)):
    if not valid_email(payload.email):
        raise HTTPException(status_code=400, detail="Email inválido")
    email = payload.email.strip().lower()
    if await db.contacts.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Contacto com este email já existe")
    doc = payload.model_dump()
    doc["email"] = email
    doc["created_at"] = now_utc().isoformat()
    doc["last_activity"] = None
    res = await db.contacts.insert_one(doc)
    doc["_id"] = res.inserted_id
    return serialize(doc)


@api.get("/contacts/{contact_id}")
async def get_contact(contact_id: str, user=Depends(get_current_user)):
    doc = await db.contacts.find_one({"_id": _oid(contact_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Contacto não encontrado")
    return serialize(doc)


@api.put("/contacts/{contact_id}")
async def update_contact(contact_id: str, payload: ContactUpdate, user=Depends(get_current_user)):
    updates = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
    if "email" in updates:
        if not valid_email(updates["email"]):
            raise HTTPException(status_code=400, detail="Email inválido")
        updates["email"] = updates["email"].strip().lower()
    if not updates:
        raise HTTPException(status_code=400, detail="Nada para atualizar")
    res = await db.contacts.update_one({"_id": _oid(contact_id)}, {"$set": updates})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Contacto não encontrado")
    doc = await db.contacts.find_one({"_id": _oid(contact_id)})
    return serialize(doc)


@api.delete("/contacts/{contact_id}")
async def delete_contact(contact_id: str, user=Depends(get_current_user)):
    await db.contacts.delete_one({"_id": _oid(contact_id)})
    return {"ok": True}


HEADER_MAP = {
    "first_name": ["first_name", "primeiro nome", "nome", "first name", "firstname"],
    "last_name": ["last_name", "apelido", "sobrenome", "last name", "lastname"],
    "company": ["company", "empresa"],
    "position": ["position", "cargo", "titulo", "título"],
    "email": ["email", "e-mail", "mail"],
    "phone": ["phone", "telefone", "telemovel", "telemóvel", "tel"],
    "city": ["city", "cidade"],
    "country": ["country", "pais", "país"],
    "website": ["website", "site", "web", "url"],
}


@api.post("/contacts/import")
async def import_contacts(
    file: UploadFile = File(...),
    group_id: str = Form(""),
    user=Depends(get_current_user),
):
    content = await file.read()
    name = (file.filename or "").lower()
    try:
        if name.endswith(".csv") or "csv" in (file.content_type or ""):
            dfr = pd.read_csv(io.BytesIO(content))
        else:
            dfr = pd.read_excel(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Não foi possível ler o ficheiro: {e}")

    dfr.columns = [str(c).strip().lower() for c in dfr.columns]
    col_index = {}
    for field, aliases in HEADER_MAP.items():
        for alias in aliases:
            if alias in dfr.columns:
                col_index[field] = alias
                break

    if "email" not in col_index:
        raise HTTPException(status_code=400, detail="Ficheiro sem coluna de email reconhecível")

    imported, skipped, duplicates = 0, 0, 0
    existing_emails = set(
        d["email"] for d in await db.contacts.find({}, {"email": 1}).to_list(100000)
    )
    seen = set()
    for _, row in dfr.iterrows():
        raw_email = str(row.get(col_index["email"], "")).strip().lower()
        if not valid_email(raw_email):
            skipped += 1
            continue
        if raw_email in existing_emails or raw_email in seen:
            duplicates += 1
            continue
        seen.add(raw_email)
        doc = {"email": raw_email, "status": "ativo", "group_id": group_id or None,
               "custom_fields": {}, "notes": "", "created_at": now_utc().isoformat(),
               "last_activity": None}
        for field, col in col_index.items():
            if field == "email":
                continue
            val = row.get(col, "")
            doc[field] = "" if pd.isna(val) else str(val).strip()
        for f in ["first_name", "last_name", "company", "position", "phone", "city", "country", "website"]:
            doc.setdefault(f, "")
        await db.contacts.insert_one(doc)
        imported += 1

    return {"imported": imported, "skipped": skipped, "duplicates": duplicates}


# ==================== GROUPS ====================
@api.get("/groups")
async def list_groups(user=Depends(get_current_user)):
    groups = await db.groups.find().sort("created_at", -1).to_list(1000)
    result = []
    for g in groups:
        count = await db.contacts.count_documents({"group_id": str(g["_id"])})
        d = serialize(g)
        d["contact_count"] = count
        result.append(d)
    return result


@api.post("/groups")
async def create_group(payload: GroupCreate, user=Depends(get_current_user)):
    doc = payload.model_dump()
    doc["created_at"] = now_utc().isoformat()
    res = await db.groups.insert_one(doc)
    doc["_id"] = res.inserted_id
    d = serialize(doc)
    d["contact_count"] = 0
    return d


@api.put("/groups/{group_id}")
async def update_group(group_id: str, payload: GroupUpdate, user=Depends(get_current_user)):
    updates = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
    await db.groups.update_one({"_id": _oid(group_id)}, {"$set": updates})
    doc = await db.groups.find_one({"_id": _oid(group_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Grupo não encontrado")
    return serialize(doc)


@api.delete("/groups/{group_id}")
async def delete_group(group_id: str, user=Depends(get_current_user)):
    await db.groups.delete_one({"_id": _oid(group_id)})
    await db.contacts.update_many({"group_id": group_id}, {"$set": {"group_id": None}})
    return {"ok": True}


@api.get("/groups/{group_id}/contacts")
async def group_contacts(group_id: str, user=Depends(get_current_user)):
    docs = await db.contacts.find({"group_id": group_id}).to_list(5000)
    return [serialize(d) for d in docs]


# ==================== TEMPLATES ====================
@api.get("/templates")
async def list_templates(user=Depends(get_current_user)):
    docs = await db.templates.find().sort("created_at", -1).to_list(1000)
    return [serialize(d) for d in docs]


@api.post("/templates")
async def create_template(payload: TemplateCreate, user=Depends(get_current_user)):
    doc = payload.model_dump()
    doc["created_at"] = now_utc().isoformat()
    res = await db.templates.insert_one(doc)
    doc["_id"] = res.inserted_id
    return serialize(doc)


@api.get("/templates/{template_id}")
async def get_template(template_id: str, user=Depends(get_current_user)):
    doc = await db.templates.find_one({"_id": _oid(template_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Template não encontrado")
    return serialize(doc)


@api.put("/templates/{template_id}")
async def update_template(template_id: str, payload: TemplateUpdate, user=Depends(get_current_user)):
    updates = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
    await db.templates.update_one({"_id": _oid(template_id)}, {"$set": updates})
    doc = await db.templates.find_one({"_id": _oid(template_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Template não encontrado")
    return serialize(doc)


@api.delete("/templates/{template_id}")
async def delete_template(template_id: str, user=Depends(get_current_user)):
    await db.templates.delete_one({"_id": _oid(template_id)})
    return {"ok": True}


@api.post("/templates/{template_id}/duplicate")
async def duplicate_template(template_id: str, user=Depends(get_current_user)):
    doc = await db.templates.find_one({"_id": _oid(template_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Template não encontrado")
    doc.pop("_id")
    doc["name"] = doc.get("name", "Template") + " (cópia)"
    doc["created_at"] = now_utc().isoformat()
    res = await db.templates.insert_one(doc)
    doc["_id"] = res.inserted_id
    return serialize(doc)


@api.post("/templates/preview")
async def preview_template(body: dict, user=Depends(get_current_user)):
    contact = None
    if body.get("contact_id"):
        contact = await db.contacts.find_one({"_id": _oid(body["contact_id"])})
    if not contact:
        contact = {"first_name": "João", "last_name": "Silva", "company": "Smartize",
                   "position": "CEO", "email": "joao@exemplo.pt", "phone": "+351 900 000 000",
                   "city": "Lisboa", "country": "Portugal", "website": "smartize.pt",
                   "custom_fields": {}}
    variables = build_variable_map(contact)
    return {
        "subject": substitute(body.get("subject", ""), variables),
        "content_html": substitute(body.get("content_html", ""), variables),
        "content_text": substitute(body.get("content_text", ""), variables),
    }


# ==================== SMTP ====================
@api.get("/smtp")
async def list_smtp(user=Depends(get_current_user)):
    docs = await db.smtp_accounts.find().sort("created_at", -1).to_list(1000)
    return [serialize(d) for d in docs]


@api.post("/smtp")
async def create_smtp(payload: SmtpCreate, user=Depends(get_current_user)):
    doc = payload.model_dump()
    doc["password_enc"] = encrypt_secret(doc.pop("password", "") or "")
    doc["imap_password_enc"] = encrypt_secret(doc.pop("imap_password", "") or "")
    doc["created_at"] = now_utc().isoformat()
    doc["connection_status"] = "unknown"
    doc["last_sync"] = None
    make_default = doc.get("is_default") or await db.smtp_accounts.count_documents({}) == 0
    doc["is_default"] = make_default
    if make_default:
        await db.smtp_accounts.update_many({}, {"$set": {"is_default": False}})
    res = await db.smtp_accounts.insert_one(doc)
    doc["_id"] = res.inserted_id
    return serialize(doc)


@api.put("/smtp/{smtp_id}")
async def update_smtp(smtp_id: str, payload: SmtpUpdate, user=Depends(get_current_user)):
    updates = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
    if "password" in updates:
        pw = updates.pop("password")
        if pw:
            updates["password_enc"] = encrypt_secret(pw)
    if "imap_password" in updates:
        ipw = updates.pop("imap_password")
        if ipw:
            updates["imap_password_enc"] = encrypt_secret(ipw)
    if updates.get("is_default"):
        await db.smtp_accounts.update_many({}, {"$set": {"is_default": False}})
    await db.smtp_accounts.update_one({"_id": _oid(smtp_id)}, {"$set": updates})
    doc = await db.smtp_accounts.find_one({"_id": _oid(smtp_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Conta de email não encontrada")
    return serialize(doc)


@api.delete("/smtp/{smtp_id}")
async def delete_smtp(smtp_id: str, user=Depends(get_current_user)):
    acc = await db.smtp_accounts.find_one({"_id": _oid(smtp_id)})
    await db.smtp_accounts.delete_one({"_id": _oid(smtp_id)})
    if acc and acc.get("is_default"):
        other = await db.smtp_accounts.find_one({})
        if other:
            await db.smtp_accounts.update_one({"_id": other["_id"]}, {"$set": {"is_default": True}})
    return {"ok": True}


@api.post("/smtp/{smtp_id}/set-default")
async def set_default_smtp(smtp_id: str, user=Depends(get_current_user)):
    acc = await db.smtp_accounts.find_one({"_id": _oid(smtp_id)})
    if not acc:
        raise HTTPException(status_code=404, detail="Conta de email não encontrada")
    await db.smtp_accounts.update_many({}, {"$set": {"is_default": False}})
    await db.smtp_accounts.update_one({"_id": _oid(smtp_id)}, {"$set": {"is_default": True}})
    return {"ok": True}


@api.post("/smtp/{smtp_id}/disconnect")
async def disconnect_smtp(smtp_id: str, user=Depends(get_current_user)):
    res = await db.smtp_accounts.update_one({"_id": _oid(smtp_id)}, {"$set": {"connection_status": "disconnected", "status": "inativo"}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Conta de email não encontrada")
    return {"ok": True}


@api.post("/smtp/test")
async def test_smtp(payload: SmtpTestRequest, user=Depends(get_current_user)):
    from core import decrypt_secret
    password = payload.password
    if payload.smtp_account_id and not password:
        acc = await db.smtp_accounts.find_one({"_id": _oid(payload.smtp_account_id)})
        if acc:
            password = decrypt_secret(acc.get("password_enc", ""))
    ok, message = await test_smtp_connection(
        payload.host, payload.port, payload.username, password, payload.use_ssl, payload.use_tls
    )
    if payload.smtp_account_id:
        await db.smtp_accounts.update_one(
            {"_id": _oid(payload.smtp_account_id)},
            {"$set": {"connection_status": "connected" if ok else "disconnected",
                      "last_sync": now_utc().isoformat() if ok else None,
                      "status": "ativo" if ok else "inativo"}},
        )
    return {"success": ok, "message": message}


# ==================== CAMPAIGNS ====================
async def _campaign_stats(campaign_id: str) -> dict:
    total = await db.email_jobs.count_documents({"campaign_id": campaign_id})
    sent = await db.email_jobs.count_documents({"campaign_id": campaign_id, "status": {"$in": SENT_STATUSES}})
    bounced = await db.email_jobs.count_documents({"campaign_id": campaign_id, "status": "bounced"})
    failed = await db.email_jobs.count_documents({"campaign_id": campaign_id, "status": "failed"})
    opened = await db.email_jobs.count_documents({"campaign_id": campaign_id, "opened_at": {"$ne": None}})
    clicked = await db.email_jobs.count_documents({"campaign_id": campaign_id, "clicked_at": {"$ne": None}})
    replied = await db.email_jobs.count_documents({"campaign_id": campaign_id, "replied": True})
    pending = await db.email_jobs.count_documents({"campaign_id": campaign_id, "status": "pending"})
    delivered = sent
    return {
        "total": total, "sent": sent, "delivered": delivered, "bounced": bounced,
        "failed": failed, "opened": opened, "clicked": clicked, "replied": replied,
        "pending": pending,
        "open_rate": round(opened / sent * 100, 1) if sent else 0,
        "click_rate": round(clicked / sent * 100, 1) if sent else 0,
        "reply_rate": round(replied / sent * 100, 1) if sent else 0,
        "delivery_rate": round(delivered / total * 100, 1) if total else 0,
        "bounce_rate": round(bounced / total * 100, 1) if total else 0,
    }


@api.get("/campaigns")
async def list_campaigns(user=Depends(get_current_user)):
    docs = await db.campaigns.find().sort("created_at", -1).to_list(1000)
    result = []
    for c in docs:
        d = serialize(c)
        d["stats"] = await _campaign_stats(str(c["_id"]))
        result.append(d)
    return result


@api.post("/campaigns")
async def create_campaign(payload: CampaignCreate, user=Depends(get_current_user)):
    doc = payload.model_dump()
    if not doc.get("smtp_account_id"):
        default = await db.smtp_accounts.find_one({"is_default": True}) or await db.smtp_accounts.find_one({})
        if not default:
            raise HTTPException(status_code=400, detail="Nenhuma conta de email configurada")
        doc["smtp_account_id"] = str(default["_id"])
    doc["status"] = "rascunho"  # draft
    doc["created_at"] = now_utc().isoformat()
    doc["started_at"] = None
    res = await db.campaigns.insert_one(doc)
    doc["_id"] = res.inserted_id
    d = serialize(doc)
    d["stats"] = await _campaign_stats(str(res.inserted_id))
    return d


@api.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: str, user=Depends(get_current_user)):
    doc = await db.campaigns.find_one({"_id": _oid(campaign_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Campanha não encontrada")
    d = serialize(doc)
    d["stats"] = await _campaign_stats(campaign_id)
    return d


@api.put("/campaigns/{campaign_id}")
async def update_campaign(campaign_id: str, payload: CampaignUpdate, user=Depends(get_current_user)):
    updates = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
    await db.campaigns.update_one({"_id": _oid(campaign_id)}, {"$set": updates})
    doc = await db.campaigns.find_one({"_id": _oid(campaign_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Campanha não encontrada")
    return serialize(doc)


@api.delete("/campaigns/{campaign_id}")
async def delete_campaign(campaign_id: str, user=Depends(get_current_user)):
    await db.campaigns.delete_one({"_id": _oid(campaign_id)})
    await db.email_jobs.delete_many({"campaign_id": campaign_id})
    return {"ok": True}


@api.post("/campaigns/{campaign_id}/start")
async def start_campaign(campaign_id: str, user=Depends(get_current_user)):
    campaign = await db.campaigns.find_one({"_id": _oid(campaign_id)})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campanha não encontrada")
    if campaign.get("status") in ("sending", "completed"):
        raise HTTPException(status_code=400, detail="Campanha já iniciada")

    smtp = await db.smtp_accounts.find_one({"_id": _oid(campaign["smtp_account_id"])})
    if not smtp:
        raise HTTPException(status_code=400, detail="Conta SMTP inválida")

    contacts = await db.contacts.find({
        "group_id": campaign["group_id"],
        "status": {"$nin": ["bounce", "descadastrado"]},
    }).to_list(100000)
    valid, seen = [], set()
    for c in contacts:
        e = (c.get("email") or "").strip().lower()
        if not valid_email(e) or e in seen:
            continue
        seen.add(e)
        valid.append(c)
    if not valid:
        raise HTTPException(status_code=400, detail="Nenhum contacto válido no grupo selecionado")

    await db.email_jobs.delete_many({"campaign_id": campaign_id})
    count = await build_campaign_jobs(campaign, valid)
    await db.campaigns.update_one({"_id": campaign["_id"]}, {"$set": {
        "status": "sending", "started_at": now_utc().isoformat(), "total_recipients": count,
    }})
    return {"ok": True, "recipients": count}


@api.post("/campaigns/{campaign_id}/cancel")
async def cancel_campaign(campaign_id: str, user=Depends(get_current_user)):
    await db.campaigns.update_one({"_id": _oid(campaign_id)}, {"$set": {"status": "cancelada"}})
    await db.email_jobs.update_many({"campaign_id": campaign_id, "status": "pending"}, {"$set": {"status": "cancelled"}})
    return {"ok": True}


@api.post("/campaigns/{campaign_id}/archive")
async def archive_campaign(campaign_id: str, user=Depends(get_current_user)):
    await db.campaigns.update_one({"_id": _oid(campaign_id)}, {"$set": {"status": "arquivada"}})
    return {"ok": True}


@api.post("/campaigns/{campaign_id}/duplicate")
async def duplicate_campaign(campaign_id: str, user=Depends(get_current_user)):
    doc = await db.campaigns.find_one({"_id": _oid(campaign_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Campanha não encontrada")
    doc.pop("_id")
    doc["name"] = doc.get("name", "Campanha") + " (cópia)"
    doc["status"] = "rascunho"
    doc["created_at"] = now_utc().isoformat()
    doc["started_at"] = None
    res = await db.campaigns.insert_one(doc)
    doc["_id"] = res.inserted_id
    d = serialize(doc)
    d["stats"] = await _campaign_stats(str(res.inserted_id))
    return d


@api.get("/campaigns/{campaign_id}/stats")
async def campaign_stats(campaign_id: str, user=Depends(get_current_user)):
    campaign = await db.campaigns.find_one({"_id": _oid(campaign_id)})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campanha não encontrada")
    stats = await _campaign_stats(campaign_id)
    jobs = await db.email_jobs.find({"campaign_id": campaign_id}).to_list(100000)
    recipients = []
    for j in jobs:
        contact = await db.contacts.find_one({"_id": _oid(j["contact_id"])}) if j.get("contact_id") else None
        recipients.append({
            "job_id": str(j["_id"]),
            "contact_id": j.get("contact_id"),
            "email": j.get("to_email"),
            "name": ((contact.get("first_name", "") + " " + contact.get("last_name", "")).strip() if contact else ""),
            "status": j.get("status"),
            "sent_at": j.get("sent_at"),
            "opened_at": j.get("opened_at"),
            "last_opened_at": j.get("last_opened_at"),
            "open_count": j.get("open_count", 0),
            "clicked_at": j.get("clicked_at"),
            "click_count": j.get("click_count", 0),
            "attempts": j.get("attempts", 0),
            "replied": j.get("replied", False),
            "error": j.get("error"),
        })
    return {"campaign": serialize(campaign), "stats": stats, "recipients": recipients}


@api.post("/campaigns/{campaign_id}/contacts/{contact_id}/reply")
async def mark_replied(campaign_id: str, contact_id: str, user=Depends(get_current_user)):
    await db.email_jobs.update_one(
        {"campaign_id": campaign_id, "contact_id": contact_id},
        {"$set": {"replied": True, "replied_at": now_utc().isoformat()}},
    )
    await db.contacts.update_one({"_id": _oid(contact_id)}, {"$set": {"status": "respondido", "last_activity": now_utc().isoformat()}})
    return {"ok": True}


# ==================== DASHBOARD ====================
@api.get("/dashboard")
async def dashboard(user=Depends(get_current_user)):
    total_contacts = await db.contacts.count_documents({})
    total_groups = await db.groups.count_documents({})
    total_campaigns = await db.campaigns.count_documents({})
    sent = await db.email_jobs.count_documents({"status": {"$in": SENT_STATUSES}})
    bounced = await db.email_jobs.count_documents({"status": "bounced"})
    opened = await db.email_jobs.count_documents({"opened_at": {"$ne": None}})
    clicked = await db.email_jobs.count_documents({"clicked_at": {"$ne": None}})
    replied = await db.email_jobs.count_documents({"replied": True})
    delivered = sent

    campaigns = await db.campaigns.find().sort("created_at", -1).limit(5).to_list(5)
    recent = []
    for c in campaigns:
        d = serialize(c)
        d["stats"] = await _campaign_stats(str(c["_id"]))
        recent.append(d)

    # daily evolution last 14 days
    days = []
    tz = timezone.utc
    for i in range(13, -1, -1):
        day = (datetime.now(tz) - timedelta(days=i)).strftime("%Y-%m-%d")
        day_sent = await db.email_jobs.count_documents({
            "status": {"$in": SENT_STATUSES},
            "sent_at": {"$regex": f"^{day}"},
        })
        day_opened = await db.email_jobs.count_documents({
            "opened_at": {"$regex": f"^{day}"},
        })
        days.append({"date": day, "enviados": day_sent, "abertos": day_opened})

    return {
        "totals": {
            "contacts": total_contacts, "groups": total_groups, "campaigns": total_campaigns,
            "sent": sent, "delivered": delivered, "opened": opened, "clicked": clicked,
            "replied": replied, "bounced": bounced,
        },
        "recent_campaigns": recent,
        "daily": days,
    }


# ==================== SETTINGS ====================
@api.get("/settings")
async def get_settings(user=Depends(get_current_user)):
    doc = await db.settings.find_one({"key": "global"})
    if not doc:
        doc = {"key": "global", "company_name": "Smartize", "logo_url": "",
               "language": "pt", "timezone": "Europe/Lisbon", "footer": ""}
        await db.settings.insert_one(dict(doc))
    doc.pop("_id", None)
    return doc


@api.put("/settings")
async def update_settings(payload: SettingsUpdate, user=Depends(get_current_user)):
    updates = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
    if updates.get("logo_url") and len(updates["logo_url"]) > 2_800_000:
        raise HTTPException(status_code=400, detail="Logótipo demasiado grande (máx. ~2MB)")
    await db.settings.update_one({"key": "global"}, {"$set": updates}, upsert=True)
    doc = await db.settings.find_one({"key": "global"})
    doc.pop("_id", None)
    return doc


# ==================== SIGNATURES (per SMTP account) ====================
@api.post("/smtp/test-send")
async def smtp_test_send(payload: SmtpTestSendRequest, user=Depends(get_current_user)):
    smtp = await db.smtp_accounts.find_one({"_id": _oid(payload.smtp_account_id)})
    if not smtp:
        raise HTTPException(status_code=400, detail="Conta SMTP inválida")
    if not valid_email(payload.to_email):
        raise HTTPException(status_code=400, detail="Email de destino inválido")
    settings = await db.settings.find_one({"key": "global"}) or {}
    company = settings.get("company_name") or "Smartize"
    logo = settings.get("logo_url") or ""
    header = (
        f'<img src="{logo}" alt="{company}" style="height:28px;margin-bottom:16px" />'
        if logo.startswith("data:")
        else f'<div style="font-weight:bold;font-size:18px;color:#0055FF;margin-bottom:16px">{company}</div>'
    )
    sample = {"first_name": "João", "last_name": "Silva", "company": "Smartize",
              "position": "CEO", "email": payload.to_email, "phone": "+351 900 000 000",
              "city": "Lisboa", "country": "Portugal", "website": "smartize.pt", "custom_fields": {}}
    variables = build_variable_map(sample)
    sig = payload.signature_html if payload.signature_html is not None else smtp.get("signature_html", "")
    sig = substitute(sig or "", variables)
    body = (
        f'<div style="font-family:Arial,sans-serif">'
        f'{header}'
        f'<p>Esta é uma mensagem de teste enviada pela plataforma {company} Outreach.</p>'
        f'<p>Confirma que a sua conta de email e assinatura estão a funcionar corretamente.</p>'
        f'<br/><div class="email-signature">{sig}</div></div>'
    )
    try:
        await send_email(smtp, payload.to_email, f"Teste de envio — {company} Outreach", body, "Mensagem de teste")
        return {"success": True, "message": f"Email de teste enviado para {payload.to_email}"}
    except Exception as e:
        return {"success": False, "message": f"Falha no envio: {str(e)}"}


DEFAULT_LOGO = "/smartize-logo.webp"


@api.get("/public/branding")
async def public_branding():
    doc = await db.settings.find_one({"key": "global"})
    logo = (doc or {}).get("logo_url") or DEFAULT_LOGO
    company = (doc or {}).get("company_name") or "Smartize"
    return {"logo_url": logo, "company_name": company}


# ==================== TRACKING (no auth) ====================
OPEN_TRACKED_STATUSES = ["sent", "delivered", "sending", "pending"]


@api.get("/track/open/{tracking_id}.png")
async def track_open(tracking_id: str):
    job = await db.email_jobs.find_one({"tracking_id": tracking_id})
    if job:
        now = now_utc().isoformat()
        set_fields = {"last_opened_at": now}
        if not job.get("opened_at"):
            set_fields["opened_at"] = now
        # Advance status to "opened" but never downgrade clicked/replied/bounced.
        if job.get("status") in OPEN_TRACKED_STATUSES:
            set_fields["status"] = "opened"
        await db.email_jobs.update_one(
            {"_id": job["_id"]},
            {"$set": set_fields, "$inc": {"open_count": 1}},
        )
        if job.get("contact_id"):
            await db.contacts.update_one({"_id": _oid(job["contact_id"])}, {"$set": {"last_activity": now}})
    return Response(content=PIXEL, media_type="image/png", headers={
        "Cache-Control": "no-store, no-cache, must-revalidate, private",
        "Pragma": "no-cache", "Expires": "0",
    })


@api.get("/track/click/{tracking_id}")
async def track_click(tracking_id: str, url: str = Query(...)):
    job = await db.email_jobs.find_one({"tracking_id": tracking_id})
    if job:
        now = now_utc().isoformat()
        set_fields = {"clicked_at": now, "last_opened_at": now}
        inc = {"click_count": 1}
        if not job.get("opened_at"):
            set_fields["opened_at"] = now
            inc["open_count"] = 1
        if job.get("status") in OPEN_TRACKED_STATUSES + ["opened"]:
            set_fields["status"] = "clicked"
        await db.email_jobs.update_one({"_id": job["_id"]}, {"$set": set_fields, "$inc": inc})
        if job.get("contact_id"):
            await db.contacts.update_one({"_id": _oid(job["contact_id"])}, {"$set": {"last_activity": now}})
    return RedirectResponse(url=url)
