"""Automatic bounce detection & management.

Two detection sources feed the same handling (`mark_bounce`):
  1. Immediate SMTP rejection at send time (worker) — e.g. 550 user unknown.
  2. Asynchronous DSN / MAILER-DAEMON emails detected via IMAP sync.

A bounced email is recorded in the `bounces` history collection, the contact is
flagged (bounce_type / bounce_reason / bounced_at) and — for hard bounces (or soft
bounces that repeat) — the contact is blocked (status "bounce") so it is never
selected for future campaigns. Contacts stay in the database.
"""
import re
import email
from email.parser import Parser
from email.utils import parseaddr

from core import db, now_utc

# After this many soft bounces the address is blocked like a hard bounce.
SOFT_BLOCK_THRESHOLD = 3

HARD_PATTERNS = [
    "user unknown", "no such user", "no such recipient", "does not exist", "doesn't exist",
    "mailbox unavailable", "mailbox not found", "no such mailbox", "invalid recipient",
    "recipient rejected", "address rejected", "recipient address rejected", "account disabled",
    "account has been disabled", "unrouteable address", "unknown user", "user not found",
    "recipient not found", "not a valid mailbox", "no mailbox", "address does not exist",
    "domain not found", "host or domain name not found", "nxdomain", "relay access denied",
    "5.1.1", "5.1.0", "5.1.2", "5.1.3", "5.4.4",
]
SOFT_PATTERNS = [
    "quota", "mailbox full", "over quota", "temporarily", "temporary failure", "try again",
    "try later", "greylist", "grey-list", "rate limit", "too many", "timed out", "timeout",
    "connection", "deferred", "service unavailable", "resources temporarily", "throttl",
    "4.2.2", "4.2.0", "4.7.",
]


def classify_bounce(text: str):
    """Return (bounce_type, reason) where bounce_type is 'hard' | 'soft' | None."""
    if not text:
        return None, ""
    reason = " ".join(str(text).split())[:300]
    low = reason.lower()
    m = re.search(r"\b([45])\.\d{1,3}\.\d{1,3}\b", reason)  # enhanced status code
    if m:
        return ("hard" if m.group(1) == "5" else "soft"), reason
    if any(p in low for p in HARD_PATTERNS):
        return "hard", reason
    if any(p in low for p in SOFT_PATTERNS):
        return "soft", reason
    m2 = re.search(r"\b([45])\d\d\b", reason)  # raw smtp code
    if m2:
        return ("hard" if m2.group(1) == "5" else "soft"), reason
    return None, reason


def is_bounce_candidate(from_email: str, subject: str) -> bool:
    fe = (from_email or "").lower()
    if "mailer-daemon" in fe or "postmaster@" in fe or fe.startswith("postmaster"):
        return True
    subj = (subject or "").lower()
    keywords = [
        "undelivered", "undeliverable", "delivery status notification", "returned mail",
        "mail delivery failed", "delivery failure", "delivery has failed", "failure notice",
        "mail delivery subsystem", "delivery incomplete",
    ]
    return any(k in subj for k in keywords)


def _classify_from_status(status: str, diagnostic: str, action: str):
    s = (status or "").strip()
    if s.startswith("5"):
        return "hard", (diagnostic or status)
    if s.startswith("4"):
        return "soft", (diagnostic or status)
    t, reason = classify_bounce(diagnostic or "")
    if t:
        return t, reason
    if (action or "").lower() == "failed":
        return "hard", (diagnostic or "Entrega falhou")
    return "soft", (diagnostic or status or "Bounce")


def _parse_delivery_status(text: str):
    recips = []
    for block in re.split(r"\n\s*\n", (text or "").strip()):
        hdr = Parser().parsestr(block)
        fr = hdr.get("Final-Recipient") or hdr.get("Original-Recipient")
        if not fr:
            continue
        raw = fr.split(";")[-1].strip().strip("<>")
        em = (parseaddr(raw)[1] or raw).strip().lower()
        if "@" not in em:
            continue
        btype, reason = _classify_from_status(
            hdr.get("Status", ""), hdr.get("Diagnostic-Code", ""), hdr.get("Action", "")
        )
        recips.append({"email": em, "type": btype, "reason": reason})
    return recips


def parse_dsn(raw: bytes):
    """Parse a bounce/DSN email; return list of {email, type, reason} for failed recipients."""
    try:
        msg = email.message_from_bytes(raw)
    except Exception:
        return []
    recips = []
    for part in msg.walk():
        if part.get_content_type() == "message/delivery-status":
            payload = part.get_payload()
            if isinstance(payload, list):
                text = "\n\n".join(p.as_string() for p in payload)
            else:
                text = payload if isinstance(payload, str) else ""
            recips.extend(_parse_delivery_status(text))
    if not recips:
        xfr = msg.get("X-Failed-Recipients")
        if xfr:
            for em in re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", xfr):
                recips.append({"email": em.lower(), "type": "hard", "reason": "Entrega falhou"})
    # de-dup by email
    seen, out = set(), []
    for r in recips:
        if r["email"] and r["email"] not in seen:
            seen.add(r["email"])
            out.append(r)
    return out


async def mark_bounce(email_addr: str, bounce_type: str, reason: str, source: str,
                      campaign_id=None, job_id=None):
    """Record a bounce and, when warranted, block the contact for future campaigns.
    Returns True if the contact ended up blocked."""
    email_addr = (email_addr or "").strip().lower()
    if not email_addr or "@" not in email_addr:
        return False
    now = now_utc().isoformat()
    contact = await db.contacts.find_one({"email": email_addr})
    await db.bounces.insert_one({
        "email": email_addr,
        "contact_id": str(contact["_id"]) if contact else None,
        "campaign_id": str(campaign_id) if campaign_id else None,
        "job_id": str(job_id) if job_id else None,
        "type": bounce_type,
        "reason": (reason or "")[:500],
        "source": source,
        "created_at": now,
    })
    if not contact:
        return False

    soft_count = int(contact.get("soft_bounce_count", 0))
    block = bounce_type == "hard"
    if bounce_type == "soft":
        soft_count += 1
        block = soft_count >= SOFT_BLOCK_THRESHOLD

    upd = {
        "bounce_type": bounce_type,
        "bounce_reason": (reason or "")[:500],
        "bounced_at": now,
        "soft_bounce_count": soft_count,
        "last_activity": now,
    }
    if block:
        upd["status"] = "bounce"
        upd["blocked"] = True
    await db.contacts.update_one({"_id": contact["_id"]}, {"$set": upd})

    if block:
        await db.email_jobs.update_many(
            {"contact_id": str(contact["_id"]), "status": "pending"},
            {"$set": {"status": "cancelled", "error": "Cancelado — email em bounce"}},
        )
        await db.campaign_contacts.update_many(
            {"contact_id": str(contact["_id"]), "status": "active"},
            {"$set": {"status": "stopped", "stop_reason": "Bounce"}},
        )
    return block
