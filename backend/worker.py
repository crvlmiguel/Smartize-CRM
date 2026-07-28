import os
import random
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from bson import ObjectId
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from core import db, now_utc
from email_service import (
    build_variable_map, substitute, rewrite_links, inject_open_pixel, send_email, html_to_text,
)

logger = logging.getLogger("worker")
scheduler = AsyncIOScheduler()

BASE_URL = os.environ.get("FRONTEND_URL", "").rstrip("/")


def _next_business_slot(dt: datetime, settings: dict) -> datetime:
    tz = ZoneInfo(settings.get("timezone", "Europe/Lisbon"))
    local = dt.astimezone(tz)
    start_h = settings.get("business_hour_start", 9)
    end_h = settings.get("business_hour_end", 18)
    business_only = settings.get("business_days_only", True)

    for _ in range(14):
        is_weekday = local.weekday() < 5
        if (not business_only or is_weekday):
            if local.hour < start_h:
                local = local.replace(hour=start_h, minute=0, second=0, microsecond=0)
                return local.astimezone(timezone.utc)
            if start_h <= local.hour < end_h:
                return local.astimezone(timezone.utc)
        # move to next day start
        local = (local + timedelta(days=1)).replace(hour=start_h, minute=0, second=0, microsecond=0)
    return local.astimezone(timezone.utc)


async def build_campaign_jobs(campaign: dict, contacts: list) -> int:
    settings = campaign.get("settings", {})
    min_i = settings.get("min_interval_seconds", 30)
    max_i = settings.get("max_interval_seconds", 90)
    if max_i < min_i:
        max_i = min_i

    start_iso = campaign.get("schedule_at")
    cursor = now_utc()
    if start_iso:
        try:
            cursor = datetime.fromisoformat(start_iso)
            if cursor.tzinfo is None:
                cursor = cursor.replace(tzinfo=timezone.utc)
        except Exception:
            cursor = now_utc()
    if cursor < now_utc():
        cursor = now_utc()

    count = 0
    for contact in contacts:
        cursor = _next_business_slot(cursor, settings)
        job = {
            "campaign_id": str(campaign["_id"]),
            "contact_id": str(contact["_id"]),
            "smtp_account_id": campaign["smtp_account_id"],
            "to_email": contact.get("email", ""),
            "status": "pending",
            "scheduled_at": cursor.isoformat(),
            "tracking_id": str(ObjectId()),
            "created_at": now_utc().isoformat(),
            "sent_at": None,
            "opened_at": None,
            "clicked_at": None,
            "last_opened_at": None,
            "open_count": 0,
            "click_count": 0,
            "attempts": 0,
            "max_attempts": 3,
            "error": None,
        }
        await db.email_jobs.insert_one(job)
        count += 1
        cursor = cursor + timedelta(seconds=random.randint(min_i, max_i))
    return count


async def _count_sent_today(smtp_account_id: str) -> int:
    tz = ZoneInfo("Europe/Lisbon")
    today = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    return await db.email_jobs.count_documents({
        "smtp_account_id": smtp_account_id,
        "status": {"$in": ["sent", "delivered", "opened", "clicked"]},
        "sent_at": {"$gte": today.astimezone(timezone.utc).isoformat()},
    })


async def process_due_jobs():
    try:
        campaigns = await db.campaigns.find({"status": "sending"}).to_list(100)
        for campaign in campaigns:
            cid = str(campaign["_id"])
            remaining = await db.email_jobs.count_documents({"campaign_id": cid, "status": "pending"})
            if remaining == 0:
                await db.campaigns.update_one({"_id": campaign["_id"]}, {"$set": {"status": "completed", "completed_at": now_utc().isoformat()}})
                continue

            job = await db.email_jobs.find_one({
                "campaign_id": cid,
                "status": "pending",
                "scheduled_at": {"$lte": now_utc().isoformat()},
            }, sort=[("scheduled_at", 1)])
            if not job:
                continue

            smtp = await db.smtp_accounts.find_one({"_id": ObjectId(job["smtp_account_id"])})
            if not smtp:
                await db.email_jobs.update_one({"_id": job["_id"]}, {"$set": {"status": "failed", "error": "Conta SMTP não encontrada"}})
                continue

            # daily limit
            limit = smtp.get("daily_limit", 200)
            if await _count_sent_today(job["smtp_account_id"]) >= limit:
                # push to next business day
                settings = campaign.get("settings", {})
                next_slot = _next_business_slot(now_utc() + timedelta(hours=12), settings)
                await db.email_jobs.update_one({"_id": job["_id"]}, {"$set": {"scheduled_at": next_slot.isoformat()}})
                continue

            await _send_job(campaign, job, smtp)
    except Exception as e:
        logger.exception("process_due_jobs error: %s", e)


async def _send_job(campaign: dict, job: dict, smtp: dict):
    contact = await db.contacts.find_one({"_id": ObjectId(job["contact_id"])})
    template = await db.templates.find_one({"_id": ObjectId(campaign["template_id"])})
    if not contact or not template:
        await db.email_jobs.update_one({"_id": job["_id"]}, {"$set": {"status": "failed", "error": "Contacto ou template em falta"}})
        return
    if contact.get("status") in ("bounce", "descadastrado"):
        await db.email_jobs.update_one({"_id": job["_id"]}, {"$set": {"status": "skipped", "error": "Contacto bloqueado"}})
        return

    variables = build_variable_map(contact)
    subject = substitute(template.get("subject", ""), variables)
    text_body = substitute(template.get("content_text", ""), variables)
    html_body = substitute(template.get("content_html", ""), variables)

    # Signature from account (with legacy fallback for pre-refactor plain-text field).
    signature_html = smtp.get("signature_html") or ""
    if not signature_html and smtp.get("signature"):
        signature_html = smtp.get("signature").replace("\n", "<br/>")
    if signature_html:
        signature_html = substitute(signature_html, variables)
        if not html_body:
            html_body = substitute(template.get("content_text", ""), variables).replace("\n", "<br/>")
        html_body = html_body + f'<br/><br/><div class="email-signature">{signature_html}</div>'
        text_body = (text_body or "") + "\n\n" + html_to_text(signature_html)

    tracking_id = job["tracking_id"]
    if html_body:
        html_body = rewrite_links(html_body, BASE_URL, tracking_id)
        html_body = inject_open_pixel(html_body, BASE_URL, tracking_id)

    await db.email_jobs.update_one({"_id": job["_id"]}, {"$set": {"status": "sending"}})
    try:
        message_id = await send_email(smtp, job["to_email"], subject, html_body, text_body)
        await db.email_jobs.update_one({"_id": job["_id"]}, {"$set": {
            "status": "sent",
            "sent_at": now_utc().isoformat(),
            "message_id": message_id,
            "error": None,
        }})
        await db.contacts.update_one({"_id": contact["_id"]}, {"$set": {"last_activity": now_utc().isoformat()}})
        logger.info("Email enviado: job=%s to=%s", str(job["_id"]), job["to_email"])
    except Exception as e:
        err = str(e)
        low = err.lower()
        attempts = job.get("attempts", 0) + 1
        max_attempts = job.get("max_attempts", 3)
        permanent = any(k in low for k in [
            "mailbox", "does not exist", "user unknown", "no such", "recipient address rejected",
            "550", "551", "553", "5.1.1", "5.1.0", "invalid recipient",
        ])
        if permanent:
            await db.email_jobs.update_one({"_id": job["_id"]}, {"$set": {
                "status": "bounced", "error": err, "attempts": attempts,
                "sent_at": now_utc().isoformat(),
            }})
            await db.contacts.update_one({"_id": contact["_id"]}, {"$set": {"status": "bounce"}})
            logger.warning("Bounce: job=%s to=%s err=%s", str(job["_id"]), job["to_email"], err)
        elif attempts < max_attempts:
            backoff = timedelta(seconds=60 * attempts)
            await db.email_jobs.update_one({"_id": job["_id"]}, {"$set": {
                "status": "pending", "error": f"Tentativa {attempts}/{max_attempts}: {err}",
                "attempts": attempts, "scheduled_at": (now_utc() + backoff).isoformat(),
            }})
            logger.warning("Retry agendado: job=%s attempt=%s err=%s", str(job["_id"]), attempts, err)
        else:
            await db.email_jobs.update_one({"_id": job["_id"]}, {"$set": {
                "status": "failed", "error": err, "attempts": attempts,
                "sent_at": now_utc().isoformat(),
            }})
            logger.error("Falha definitiva: job=%s to=%s err=%s", str(job["_id"]), job["to_email"], err)


async def build_enrollments(campaign: dict, contacts: list) -> int:
    start_iso = campaign.get("schedule_at")
    cursor = now_utc()
    if start_iso:
        try:
            cursor = datetime.fromisoformat(start_iso)
            if cursor.tzinfo is None:
                cursor = cursor.replace(tzinfo=timezone.utc)
        except Exception:
            cursor = now_utc()
    if cursor < now_utc():
        cursor = now_utc()
    count = 0
    for c in contacts:
        await db.campaign_contacts.insert_one({
            "campaign_id": str(campaign["_id"]),
            "contact_id": str(c["_id"]),
            "to_email": c.get("email", ""),
            "smtp_account_id": campaign["smtp_account_id"],
            "current_step": 0,
            "status": "active",
            "next_send_at": cursor.isoformat(),
            "last_message_id": None,
            "last_subject": None,
            "attempts": 0,
            "created_at": now_utc().isoformat(),
        })
        count += 1
    return count


async def process_sequences():
    try:
        enrollments = await db.campaign_contacts.find({
            "status": "active",
            "next_send_at": {"$lte": now_utc().isoformat()},
        }).sort("next_send_at", 1).to_list(50)
        for enr in enrollments:
            campaign = await db.campaigns.find_one({"_id": ObjectId(enr["campaign_id"])})
            if not campaign or campaign.get("status") != "sending":
                continue
            contact = await db.contacts.find_one({"_id": ObjectId(enr["contact_id"])})
            if not contact:
                await db.campaign_contacts.update_one({"_id": enr["_id"]}, {"$set": {"status": "stopped", "stop_reason": "Contacto removido"}})
                continue
            if contact.get("status") in ("respondido", "bounce", "descadastrado"):
                reason = {"respondido": "Contacto respondeu", "bounce": "Bounce", "descadastrado": "Descadastrado"}[contact["status"]]
                await db.campaign_contacts.update_one({"_id": enr["_id"]}, {"$set": {"status": "stopped", "stop_reason": reason}})
                continue

            steps = campaign.get("steps", [])
            idx = enr["current_step"]
            if idx >= len(steps):
                await db.campaign_contacts.update_one({"_id": enr["_id"]}, {"$set": {"status": "completed"}})
                continue

            smtp = await db.smtp_accounts.find_one({"_id": ObjectId(enr["smtp_account_id"])})
            if not smtp:
                await db.campaign_contacts.update_one({"_id": enr["_id"]}, {"$set": {"status": "stopped", "stop_reason": "Conta SMTP inválida"}})
                continue

            await _send_sequence_step(campaign, enr, contact, smtp, steps, idx)
    except Exception as e:
        logger.exception("process_sequences error: %s", e)


async def _send_sequence_step(campaign, enr, contact, smtp, steps, idx):
    step = steps[idx]
    template = await db.templates.find_one({"_id": ObjectId(step["template_id"])}) if step.get("template_id") else None
    if not template:
        await db.campaign_contacts.update_one({"_id": enr["_id"]}, {"$set": {"status": "stopped", "stop_reason": "Template em falta"}})
        return
    variables = build_variable_map(contact)
    subject = substitute(step.get("subject") or template.get("subject", ""), variables)
    is_reply = step.get("send_type") == "reply" and enr.get("last_message_id")
    if is_reply and enr.get("last_subject"):
        subject = enr["last_subject"] if enr["last_subject"].lower().startswith("re:") else f"Re: {enr['last_subject']}"
    text_body = substitute(template.get("content_text", ""), variables)
    html_body = substitute(template.get("content_html", ""), variables)
    sig = smtp.get("signature_html") or (smtp.get("signature") or "").replace("\n", "<br/>")
    if sig:
        sig = substitute(sig, variables)
        if not html_body:
            html_body = text_body.replace("\n", "<br/>")
        html_body += f'<br/><br/><div class="email-signature">{sig}</div>'
        text_body = (text_body or "") + "\n\n" + html_to_text(sig)

    tracking_id = str(ObjectId())
    if html_body:
        html_body = rewrite_links(html_body, BASE_URL, tracking_id)
        html_body = inject_open_pixel(html_body, BASE_URL, tracking_id)

    job_doc = {
        "campaign_id": str(campaign["_id"]), "contact_id": str(contact["_id"]),
        "smtp_account_id": str(smtp["_id"]), "to_email": contact.get("email", ""),
        "status": "sending", "step": idx, "tracking_id": tracking_id,
        "scheduled_at": now_utc().isoformat(), "created_at": now_utc().isoformat(),
        "sent_at": None, "opened_at": None, "clicked_at": None,
        "open_count": 0, "click_count": 0, "attempts": 0, "error": None,
    }
    jres = await db.email_jobs.insert_one(job_doc)
    try:
        message_id = await send_email(smtp, contact["email"], subject, html_body, text_body,
                                      in_reply_to=enr.get("last_message_id") if is_reply else None)
        await db.email_jobs.update_one({"_id": jres.inserted_id}, {"$set": {"status": "sent", "sent_at": now_utc().isoformat(), "message_id": message_id}})
        await db.contacts.update_one({"_id": contact["_id"]}, {"$set": {"last_activity": now_utc().isoformat()}})
        # advance
        next_idx = idx + 1
        upd = {"current_step": next_idx, "last_message_id": message_id, "last_subject": subject, "attempts": 0}
        if next_idx >= len(steps):
            upd["status"] = "completed"
        else:
            nxt = steps[next_idx]
            delay = timedelta(days=nxt.get("delay_days", 0), hours=nxt.get("delay_hours", 0))
            slot = _next_business_slot(now_utc() + delay, campaign.get("settings", {}))
            upd["next_send_at"] = slot.isoformat()
        await db.campaign_contacts.update_one({"_id": enr["_id"]}, {"$set": upd})
    except Exception as e:
        err = str(e)
        low = err.lower()
        attempts = enr.get("attempts", 0) + 1
        permanent = any(k in low for k in ["mailbox", "does not exist", "user unknown", "no such", "550", "5.1.1"])
        await db.email_jobs.update_one({"_id": jres.inserted_id}, {"$set": {"status": "bounced" if permanent else "failed", "error": err, "sent_at": now_utc().isoformat(), "attempts": attempts}})
        if permanent:
            await db.contacts.update_one({"_id": contact["_id"]}, {"$set": {"status": "bounce"}})
            await db.campaign_contacts.update_one({"_id": enr["_id"]}, {"$set": {"status": "stopped", "stop_reason": "Bounce"}})
        elif attempts >= 3:
            await db.campaign_contacts.update_one({"_id": enr["_id"]}, {"$set": {"status": "stopped", "stop_reason": err, "attempts": attempts}})
        else:
            await db.campaign_contacts.update_one({"_id": enr["_id"]}, {"$set": {"attempts": attempts, "next_send_at": (now_utc() + timedelta(minutes=5)).isoformat()}})


def start_scheduler():
    if not scheduler.running:
        from imap_sync import sync_all_accounts
        from crm import process_automation_jobs
        scheduler.add_job(process_due_jobs, "interval", seconds=10, id="sender", max_instances=1, coalesce=True)
        scheduler.add_job(process_sequences, "interval", seconds=12, id="sequences", max_instances=1, coalesce=True)
        scheduler.add_job(sync_all_accounts, "interval", seconds=180, id="imap_sync", max_instances=1, coalesce=True)
        scheduler.add_job(process_automation_jobs, "interval", seconds=30, id="automations", max_instances=1, coalesce=True)
        scheduler.start()
