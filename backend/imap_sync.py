import asyncio
import imaplib
import email
import logging
from email.utils import parseaddr, getaddresses
from datetime import datetime, timedelta, timezone

from bson import ObjectId

from core import db, now_utc, decrypt_secret
from bounces import is_bounce_candidate, parse_dsn, mark_bounce

logger = logging.getLogger("imap_sync")


def _fetch_recent_headers(host, port, username, password, since_days=3):
    """Blocking IMAP fetch of recent messages. Returns list of dicts. Bounce/DSN
    messages are parsed in full and carry a `bounce_recipients` list."""
    results = []
    imap = imaplib.IMAP4_SSL(host, int(port or 993))
    try:
        imap.login(username, password)
        imap.select("INBOX", readonly=True)
        since = (datetime.now(timezone.utc) - timedelta(days=since_days)).strftime("%d-%b-%Y")
        status, data = imap.search(None, f'(SINCE {since})')
        if status != "OK":
            return results
        ids = data[0].split()
        for msg_id in ids[-200:]:  # cap to last 200
            status, msg_data = imap.fetch(
                msg_id, "(BODY.PEEK[HEADER.FIELDS (FROM IN-REPLY-TO REFERENCES MESSAGE-ID SUBJECT DATE)])"
            )
            if status != "OK" or not msg_data or not msg_data[0]:
                continue
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)
            from_email = parseaddr(msg.get("From", ""))[1].strip().lower()
            subject = msg.get("Subject", "")

            # Bounce / DSN — fetch full body and extract failed recipients.
            if is_bounce_candidate(from_email, subject):
                bstatus, bdata = imap.fetch(msg_id, "(BODY.PEEK[])")
                bounce_recipients = []
                if bstatus == "OK" and bdata and bdata[0]:
                    bounce_recipients = parse_dsn(bdata[0][1])
                results.append({
                    "from_email": from_email, "subject": subject,
                    "bounce_recipients": bounce_recipients,
                })
                continue

            in_reply_to = msg.get("In-Reply-To", "") or ""
            references = msg.get("References", "") or ""
            results.append({
                "from_email": from_email,
                "in_reply_to": in_reply_to.strip(),
                "references": references,
                "subject": subject,
                "date": msg.get("Date", ""),
            })
    finally:
        try:
            imap.logout()
        except Exception:
            pass
    return results


def _extract_message_ids(reply):
    ids = set()
    for token in (reply.get("in_reply_to", "") + " " + reply.get("references", "")).split():
        token = token.strip().strip("<>").strip()
        if token:
            ids.add(token)
            ids.add(f"<{token}>")
    return ids


async def _mark_reply(contact_id: str, matched_job_id=None):
    now = now_utc().isoformat()
    await db.contacts.update_one(
        {"_id": ObjectId(contact_id)},
        {"$set": {"status": "respondido", "last_activity": now}},
    )
    if matched_job_id:
        await db.email_jobs.update_one(
            {"_id": matched_job_id},
            {"$set": {"replied": True, "replied_at": now, "status": "replied"}},
        )
    else:
        # mark the most recent sent job of this contact as replied
        job = await db.email_jobs.find_one(
            {"contact_id": contact_id, "status": {"$in": ["sent", "delivered", "opened", "clicked"]}},
            sort=[("sent_at", -1)],
        )
        if job:
            await db.email_jobs.update_one(
                {"_id": job["_id"]},
                {"$set": {"replied": True, "replied_at": now, "status": "replied"}},
            )
    # stop future sends for this contact
    await db.email_jobs.update_many(
        {"contact_id": contact_id, "status": "pending"},
        {"$set": {"status": "cancelled", "error": "Cancelado — contacto respondeu"}},
    )


async def sync_account(account: dict) -> int:
    host = account.get("imap_host")
    if not host:
        return 0
    username = account.get("imap_username") or account.get("username") or account.get("from_email")
    password = decrypt_secret(account.get("imap_password_enc", "")) or decrypt_secret(account.get("password_enc", ""))
    if not username or not password:
        return 0

    try:
        replies = await asyncio.to_thread(
            _fetch_recent_headers, host, account.get("imap_port", 993), username, password
        )
    except Exception as e:
        logger.warning("IMAP sync falhou para %s: %s", account.get("name"), e)
        await db.smtp_accounts.update_one(
            {"_id": account["_id"]}, {"$set": {"imap_status": "error", "imap_error": str(e)}}
        )
        return 0

    found = 0
    for reply in replies:
        # Bounce / DSN messages: mark each failed recipient and skip reply handling.
        if reply.get("bounce_recipients") is not None:
            for r in reply["bounce_recipients"]:
                await mark_bounce(r["email"], r.get("type") or "hard",
                                  r.get("reason") or "Bounce", "imap")
                found += 1
            continue

        contact_id = None
        matched_job_id = None

        # 1) Match by threading headers against our sent Message-IDs
        candidate_ids = _extract_message_ids(reply)
        if candidate_ids:
            job = await db.email_jobs.find_one({"message_id": {"$in": list(candidate_ids)}})
            if job:
                contact_id = job.get("contact_id")
                matched_job_id = job["_id"]

        # 2) Fallback: match sender email to a known contact that we emailed
        if not contact_id and reply.get("from_email"):
            contact = await db.contacts.find_one({"email": reply["from_email"]})
            if contact:
                has_job = await db.email_jobs.find_one({"contact_id": str(contact["_id"])})
                if has_job:
                    contact_id = str(contact["_id"])

        if not contact_id:
            continue

        contact = await db.contacts.find_one({"_id": ObjectId(contact_id)})
        if contact and contact.get("status") == "respondido":
            continue  # already handled

        await _mark_reply(contact_id, matched_job_id)
        found += 1

    await db.smtp_accounts.update_one(
        {"_id": account["_id"]},
        {"$set": {"last_sync": now_utc().isoformat(), "imap_status": "ok", "imap_error": None}},
    )
    if found:
        logger.info("IMAP sync %s: %s respostas detetadas", account.get("name"), found)
    return found


async def sync_all_accounts():
    accounts = await db.smtp_accounts.find({
        "imap_host": {"$nin": [None, ""]},
        "status": {"$ne": "inativo"},
    }).to_list(100)
    total = 0
    for acc in accounts:
        total += await sync_account(acc)
    return total
