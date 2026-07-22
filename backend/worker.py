import os
import random
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from bson import ObjectId
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from core import db, now_utc
from email_service import (
    build_variable_map, substitute, rewrite_links, inject_open_pixel, send_email,
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

    signature_html = smtp.get("signature_html", "")
    if signature_html:
        signature_html = substitute(signature_html, variables)
        if not html_body:
            html_body = substitute(template.get("content_text", ""), variables).replace("\n", "<br/>")
        html_body = html_body + f'<br/><br/><div class="email-signature">{signature_html}</div>'

    tracking_id = job["tracking_id"]
    if html_body:
        html_body = rewrite_links(html_body, BASE_URL, tracking_id)
        html_body = inject_open_pixel(html_body, BASE_URL, tracking_id)

    try:
        message_id = await send_email(smtp, job["to_email"], subject, html_body, text_body)
        await db.email_jobs.update_one({"_id": job["_id"]}, {"$set": {
            "status": "sent",
            "sent_at": now_utc().isoformat(),
            "message_id": message_id,
        }})
        await db.contacts.update_one({"_id": contact["_id"]}, {"$set": {"last_activity": now_utc().isoformat()}})
    except Exception as e:
        err = str(e)
        await db.email_jobs.update_one({"_id": job["_id"]}, {"$set": {
            "status": "failed", "error": err, "sent_at": now_utc().isoformat(),
        }})
        low = err.lower()
        if any(k in low for k in ["mailbox", "does not exist", "user unknown", "550", "recipient", "no such"]):
            await db.email_jobs.update_one({"_id": job["_id"]}, {"$set": {"status": "bounced"}})
            await db.contacts.update_one({"_id": contact["_id"]}, {"$set": {"status": "bounce"}})


def start_scheduler():
    if not scheduler.running:
        scheduler.add_job(process_due_jobs, "interval", seconds=10, id="sender", max_instances=1, coalesce=True)
        scheduler.start()
