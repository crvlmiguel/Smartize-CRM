import logging
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from core import db, now_utc
from auth import get_current_user
from email_service import build_variable_map, substitute, send_email

logger = logging.getLogger("crm")
crm = APIRouter(prefix="/api")


def _oid(v):
    try:
        return ObjectId(v)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")


def s(doc):
    if not doc:
        return doc
    d = dict(doc)
    d["id"] = str(d.pop("_id"))
    return d


# ==================== MODELS ====================
class Stage(BaseModel):
    id: str
    name: str
    type: str = "open"  # open | won | lost


class PipelineCreate(BaseModel):
    name: str
    stages: Optional[List[Stage]] = None


class PipelineUpdate(BaseModel):
    name: Optional[str] = None
    stages: Optional[List[Stage]] = None


class DealCreate(BaseModel):
    name: str
    contact_id: Optional[str] = None
    pipeline_id: Optional[str] = None
    stage_id: Optional[str] = None
    company: str = ""
    email: str = ""
    phone: str = ""
    position: str = ""
    website: str = ""
    value: float = 0
    probability: int = 0
    owner: str = ""
    expected_close: Optional[str] = None
    notes: str = ""
    tags: List[str] = []
    source_group_id: Optional[str] = None
    source_campaign_id: Optional[str] = None


class DealUpdate(BaseModel):
    name: Optional[str] = None
    company: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    position: Optional[str] = None
    website: Optional[str] = None
    value: Optional[float] = None
    probability: Optional[int] = None
    owner: Optional[str] = None
    expected_close: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None
    stage_id: Optional[str] = None
    status: Optional[str] = None
    lost_reason: Optional[str] = None


class MoveDeal(BaseModel):
    stage_id: str
    lost_reason: Optional[str] = None


class AutomationCreate(BaseModel):
    pipeline_id: str
    name: str
    event: str            # deal_created | stage_changed | deal_won | deal_lost | contact_replied | email_opened
    stage_id: Optional[str] = None
    action: str           # send_email | create_task | change_stage | add_tag | create_project
    config: Dict[str, Any] = {}
    delay_days: int = 0
    enabled: bool = True


class AutomationUpdate(BaseModel):
    name: Optional[str] = None
    event: Optional[str] = None
    stage_id: Optional[str] = None
    action: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    delay_days: Optional[int] = None
    enabled: Optional[bool] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    done: Optional[bool] = None
    due_at: Optional[str] = None


DEFAULT_STAGES = [
    {"id": "novo", "name": "Novo contacto", "type": "open"},
    {"id": "reuniao", "name": "Reunião marcada", "type": "open"},
    {"id": "proposta", "name": "Proposta enviada", "type": "open"},
    {"id": "negociacao", "name": "Negociação", "type": "open"},
    {"id": "contrato", "name": "Contrato", "type": "open"},
    {"id": "ganho", "name": "Ganho", "type": "won"},
    {"id": "perdido", "name": "Perdido", "type": "lost"},
]


async def ensure_default_pipeline():
    existing = await db.pipelines.find_one({})
    if not existing:
        await db.pipelines.insert_one({
            "name": "Pipeline Comercial", "stages": DEFAULT_STAGES,
            "created_at": now_utc().isoformat(),
        })


# ==================== PIPELINES ====================
@crm.get("/pipelines")
async def list_pipelines(user=Depends(get_current_user)):
    await ensure_default_pipeline()
    docs = await db.pipelines.find().sort("created_at", 1).to_list(100)
    return [s(d) for d in docs]


@crm.post("/pipelines")
async def create_pipeline(payload: PipelineCreate, user=Depends(get_current_user)):
    stages = [st.model_dump() for st in payload.stages] if payload.stages else DEFAULT_STAGES
    doc = {"name": payload.name, "stages": stages, "created_at": now_utc().isoformat()}
    res = await db.pipelines.insert_one(doc)
    doc["_id"] = res.inserted_id
    return s(doc)


@crm.put("/pipelines/{pid}")
async def update_pipeline(pid: str, payload: PipelineUpdate, user=Depends(get_current_user)):
    updates = {}
    if payload.name is not None:
        updates["name"] = payload.name
    if payload.stages is not None:
        updates["stages"] = [st.model_dump() for st in payload.stages]
    await db.pipelines.update_one({"_id": _oid(pid)}, {"$set": updates})
    return s(await db.pipelines.find_one({"_id": _oid(pid)}))


@crm.delete("/pipelines/{pid}")
async def delete_pipeline(pid: str, user=Depends(get_current_user)):
    count = await db.pipelines.count_documents({})
    if count <= 1:
        raise HTTPException(status_code=400, detail="Não pode eliminar o único pipeline")
    await db.pipelines.delete_one({"_id": _oid(pid)})
    await db.deals.delete_many({"pipeline_id": pid})
    await db.automations.delete_many({"pipeline_id": pid})
    return {"ok": True}


# ==================== DEALS ====================
async def _add_history(deal_id, text):
    await db.deals.update_one({"_id": _oid(deal_id)}, {"$push": {"history": {
        "text": text, "at": now_utc().isoformat(),
    }}})


@crm.get("/deals")
async def list_deals(pipeline_id: Optional[str] = None, user=Depends(get_current_user)):
    await ensure_default_pipeline()
    q = {}
    if pipeline_id:
        q["pipeline_id"] = pipeline_id
    docs = await db.deals.find(q).sort("created_at", -1).to_list(5000)
    return [s(d) for d in docs]


@crm.post("/deals")
async def create_deal(payload: DealCreate, user=Depends(get_current_user)):
    await ensure_default_pipeline()
    pipeline = None
    if payload.pipeline_id:
        pipeline = await db.pipelines.find_one({"_id": _oid(payload.pipeline_id)})
    if not pipeline:
        pipeline = await db.pipelines.find_one({})
    stage_id = payload.stage_id or pipeline["stages"][0]["id"]

    history = []
    # copy contact email history summary
    if payload.contact_id:
        jobs = await db.email_jobs.find({"contact_id": payload.contact_id}).to_list(500)
        for j in jobs:
            history.append({"text": f"Email '{j.get('status')}' para {j.get('to_email')}", "at": j.get("sent_at") or j.get("created_at")})
    history.append({"text": "Negócio criado", "at": now_utc().isoformat()})

    doc = payload.model_dump()
    doc["pipeline_id"] = str(pipeline["_id"])
    doc["stage_id"] = stage_id
    doc["status"] = "open"
    doc["lost_reason"] = None
    doc["history"] = history
    doc["created_at"] = now_utc().isoformat()
    res = await db.deals.insert_one(doc)
    doc["_id"] = res.inserted_id
    await run_automations("deal_created", doc)
    return s(await db.deals.find_one({"_id": res.inserted_id}))


@crm.get("/deals/{did}")
async def get_deal(did: str, user=Depends(get_current_user)):
    doc = await db.deals.find_one({"_id": _oid(did)})
    if not doc:
        raise HTTPException(status_code=404, detail="Negócio não encontrado")
    return s(doc)


@crm.put("/deals/{did}")
async def update_deal(did: str, payload: DealUpdate, user=Depends(get_current_user)):
    existing = await db.deals.find_one({"_id": _oid(did)})
    if not existing:
        raise HTTPException(status_code=404, detail="Negócio não encontrado")
    updates = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
    await db.deals.update_one({"_id": _oid(did)}, {"$set": updates})
    return s(await db.deals.find_one({"_id": _oid(did)}))


@crm.delete("/deals/{did}")
async def delete_deal(did: str, user=Depends(get_current_user)):
    await db.deals.delete_one({"_id": _oid(did)})
    await db.tasks.delete_many({"deal_id": did})
    return {"ok": True}


@crm.post("/deals/{did}/move")
async def move_deal(did: str, payload: MoveDeal, user=Depends(get_current_user)):
    deal = await db.deals.find_one({"_id": _oid(did)})
    if not deal:
        raise HTTPException(status_code=404, detail="Negócio não encontrado")
    pipeline = await db.pipelines.find_one({"_id": _oid(deal["pipeline_id"])})
    stage = next((st for st in pipeline["stages"] if st["id"] == payload.stage_id), None)
    if not stage:
        raise HTTPException(status_code=400, detail="Etapa inválida")
    updates = {"stage_id": payload.stage_id}
    status = "open"
    if stage["type"] == "won":
        status = "won"
        updates["lost_reason"] = None
    elif stage["type"] == "lost":
        status = "lost"
        updates["lost_reason"] = payload.lost_reason or ""
    else:
        updates["lost_reason"] = None
    updates["status"] = status
    await db.deals.update_one({"_id": _oid(did)}, {"$set": updates})
    await _add_history(did, f"Movido para '{stage['name']}'")
    deal.update(updates)
    await run_automations("stage_changed", deal)
    if status == "won":
        await run_automations("deal_won", deal)
    elif status == "lost":
        await run_automations("deal_lost", deal)
    return s(await db.deals.find_one({"_id": _oid(did)}))


@crm.post("/contacts/{contact_id}/convert")
async def convert_contact(contact_id: str, user=Depends(get_current_user)):
    contact = await db.contacts.find_one({"_id": _oid(contact_id)})
    if not contact:
        raise HTTPException(status_code=404, detail="Contacto não encontrado")
    # find a source campaign (last job)
    last_job = await db.email_jobs.find_one({"contact_id": contact_id}, sort=[("created_at", -1)])
    full = f"{contact.get('first_name','')} {contact.get('last_name','')}".strip()
    payload = DealCreate(
        name=f"Negócio — {full or contact.get('email')}",
        contact_id=contact_id,
        company=contact.get("company", ""),
        email=contact.get("email", ""),
        phone=contact.get("phone", ""),
        position=contact.get("position", ""),
        website=contact.get("website", ""),
        source_group_id=contact.get("group_id"),
        source_campaign_id=(last_job or {}).get("campaign_id"),
    )
    return await create_deal(payload, user)


# ==================== TASKS ====================
@crm.get("/tasks")
async def list_tasks(deal_id: Optional[str] = None, user=Depends(get_current_user)):
    q = {}
    if deal_id:
        q["deal_id"] = deal_id
    docs = await db.tasks.find(q).sort("created_at", -1).to_list(2000)
    return [s(d) for d in docs]


@crm.post("/tasks")
async def create_task(body: dict, user=Depends(get_current_user)):
    doc = {"title": body.get("title", "Tarefa"), "deal_id": body.get("deal_id"),
           "done": False, "due_at": body.get("due_at"), "created_at": now_utc().isoformat()}
    res = await db.tasks.insert_one(doc)
    doc["_id"] = res.inserted_id
    return s(doc)


@crm.put("/tasks/{tid}")
async def update_task(tid: str, payload: TaskUpdate, user=Depends(get_current_user)):
    updates = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
    await db.tasks.update_one({"_id": _oid(tid)}, {"$set": updates})
    return s(await db.tasks.find_one({"_id": _oid(tid)}))


@crm.delete("/tasks/{tid}")
async def delete_task(tid: str, user=Depends(get_current_user)):
    await db.tasks.delete_one({"_id": _oid(tid)})
    return {"ok": True}


# ==================== AUTOMATIONS ====================
@crm.get("/automations")
async def list_automations(pipeline_id: Optional[str] = None, user=Depends(get_current_user)):
    q = {}
    if pipeline_id:
        q["pipeline_id"] = pipeline_id
    docs = await db.automations.find(q).sort("created_at", -1).to_list(500)
    return [s(d) for d in docs]


@crm.post("/automations")
async def create_automation(payload: AutomationCreate, user=Depends(get_current_user)):
    doc = payload.model_dump()
    doc["created_at"] = now_utc().isoformat()
    res = await db.automations.insert_one(doc)
    doc["_id"] = res.inserted_id
    return s(doc)


@crm.put("/automations/{aid}")
async def update_automation(aid: str, payload: AutomationUpdate, user=Depends(get_current_user)):
    existing = await db.automations.find_one({"_id": _oid(aid)})
    if not existing:
        raise HTTPException(status_code=404, detail="Automação não encontrada")
    updates = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
    await db.automations.update_one({"_id": _oid(aid)}, {"$set": updates})
    return s(await db.automations.find_one({"_id": _oid(aid)}))


@crm.delete("/automations/{aid}")
async def delete_automation(aid: str, user=Depends(get_current_user)):
    await db.automations.delete_one({"_id": _oid(aid)})
    return {"ok": True}


# ==================== AUTOMATION ENGINE ====================
def _deal_variables(deal):
    name = (deal.get("name") or "")
    contact_name = name.split("—")[-1].strip() if "—" in name else name
    return {
        "first_name": contact_name.split(" ")[0] if contact_name else "",
        "full_name": contact_name, "company": deal.get("company", ""),
        "position": deal.get("position", ""), "email": deal.get("email", ""),
        "phone": deal.get("phone", ""), "website": deal.get("website", ""),
        "today": datetime.now().strftime("%d/%m/%Y"),
        "deal_name": deal.get("name", ""), "deal_value": str(deal.get("value", 0)),
    }


async def _execute_action(automation, deal):
    action = automation["action"]
    config = automation.get("config", {})
    did = str(deal["_id"])
    try:
        if action == "add_tag":
            tag = config.get("tag", "")
            if tag:
                await db.deals.update_one({"_id": _oid(did)}, {"$addToSet": {"tags": tag}})
                await _add_history(did, f"Etiqueta adicionada: {tag}")
        elif action == "create_task":
            await db.tasks.insert_one({"title": config.get("title", "Tarefa automática"),
                "deal_id": did, "done": False, "due_at": None, "created_at": now_utc().isoformat()})
            await _add_history(did, "Tarefa criada por automação")
        elif action == "create_project":
            await db.projects.insert_one({"name": config.get("name") or deal.get("name"),
                "deal_id": did, "created_at": now_utc().isoformat()})
            await _add_history(did, "Projeto criado por automação")
        elif action == "change_stage":
            new_stage = config.get("stage_id")
            if new_stage and new_stage != deal.get("stage_id"):
                await db.deals.update_one({"_id": _oid(did)}, {"$set": {"stage_id": new_stage}})
                await _add_history(did, f"Etapa alterada por automação")
        elif action == "send_email":
            await _automation_send_email(config, deal)
            await _add_history(did, "Email automático enviado")
    except Exception as e:
        logger.warning("Automação falhou (%s): %s", action, e)


async def _automation_send_email(config, deal):
    if not deal.get("email"):
        return
    template = None
    if config.get("template_id"):
        template = await db.templates.find_one({"_id": ObjectId(config["template_id"])})
    smtp = await db.smtp_accounts.find_one({"is_default": True}) or await db.smtp_accounts.find_one({})
    if not smtp:
        return
    variables = _deal_variables(deal)
    subject = substitute(config.get("subject") or (template or {}).get("subject", "") or "Mensagem", variables)
    html = substitute((template or {}).get("content_html", "") or config.get("body", ""), variables)
    text = substitute((template or {}).get("content_text", ""), variables)
    sig = smtp.get("signature_html") or ""
    if sig:
        html = html + f'<br/><br/>{substitute(sig, variables)}'
    await send_email(smtp, deal["email"], subject, html, text)


async def run_automations(event, deal):
    q = {"pipeline_id": deal.get("pipeline_id"), "event": event, "enabled": True}
    autos = await db.automations.find(q).to_list(100)
    for a in autos:
        if event == "stage_changed" and a.get("stage_id") and a["stage_id"] != deal.get("stage_id"):
            continue
        if a.get("delay_days", 0) and a["action"] == "send_email":
            run_at = now_utc() + timedelta(days=a["delay_days"])
            await db.automation_jobs.insert_one({
                "automation_id": str(a["_id"]), "deal_id": str(deal["_id"]),
                "run_at": run_at.isoformat(), "status": "pending", "created_at": now_utc().isoformat(),
            })
        else:
            await _execute_action(a, deal)


async def process_automation_jobs():
    try:
        jobs = await db.automation_jobs.find({
            "status": "pending", "run_at": {"$lte": now_utc().isoformat()},
        }).to_list(100)
        for job in jobs:
            deal = await db.deals.find_one({"_id": ObjectId(job["deal_id"])})
            auto = await db.automations.find_one({"_id": ObjectId(job["automation_id"])})
            if deal and auto and deal.get("status") == "open":
                # skip follow-up if contact already replied
                contact = None
                if deal.get("contact_id"):
                    contact = await db.contacts.find_one({"_id": ObjectId(deal["contact_id"])})
                if not (contact and contact.get("status") == "respondido"):
                    await _execute_action(auto, deal)
            await db.automation_jobs.update_one({"_id": job["_id"]}, {"$set": {"status": "done"}})
    except Exception as e:
        logger.warning("process_automation_jobs error: %s", e)
