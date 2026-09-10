"""Iteration 19 — automatic bounce detection & management."""
import asyncio
import sys

import pytest

sys.path.insert(0, "/app/backend")


class TestClassify:
    def test_hard_codes_and_keywords(self):
        from bounces import classify_bounce
        assert classify_bounce("(550, b'5.1.1 <x@y.pt> User unknown')")[0] == "hard"
        assert classify_bounce("550 No such user here")[0] == "hard"
        assert classify_bounce("Recipient address rejected: User unknown")[0] == "hard"

    def test_soft_codes_and_keywords(self):
        from bounces import classify_bounce
        assert classify_bounce("452 4.2.2 Mailbox full")[0] == "soft"
        assert classify_bounce("Connection timed out")[0] == "soft"
        assert classify_bounce("421 Service temporarily unavailable, try again later")[0] == "soft"

    def test_unknown(self):
        from bounces import classify_bounce
        assert classify_bounce("")[0] is None


class TestDSN:
    def test_parse_delivery_status(self):
        from bounces import parse_dsn
        raw = (
            b"From: MAILER-DAEMON@mail.pt\r\n"
            b"Subject: Undelivered Mail Returned to Sender\r\n"
            b"Content-Type: multipart/report; report-type=delivery-status; boundary=\"B\"\r\n\r\n"
            b"--B\r\nContent-Type: text/plain\r\n\r\nDelivery failed.\r\n"
            b"--B\r\nContent-Type: message/delivery-status\r\n\r\n"
            b"Reporting-MTA: dns; mail.pt\r\n\r\n"
            b"Final-Recipient: rfc822; joao@empresa.pt\r\n"
            b"Action: failed\r\n"
            b"Status: 5.1.1\r\n"
            b"Diagnostic-Code: smtp; 550 5.1.1 User unknown\r\n\r\n"
            b"--B--\r\n"
        )
        recips = parse_dsn(raw)
        assert len(recips) == 1
        assert recips[0]["email"] == "joao@empresa.pt"
        assert recips[0]["type"] == "hard"

    def test_is_candidate(self):
        from bounces import is_bounce_candidate
        assert is_bounce_candidate("MAILER-DAEMON@x.pt", "anything")
        assert is_bounce_candidate("no@x.pt", "Undeliverable: your message")
        assert not is_bounce_candidate("joao@empresa.pt", "Re: proposta")


@pytest.fixture()
def loop():
    try:
        l = asyncio.get_event_loop()
        if l.is_closed():
            raise RuntimeError
    except RuntimeError:
        l = asyncio.new_event_loop()
        asyncio.set_event_loop(l)
    return l


class TestMarkBounce:
    def test_hard_blocks_and_cancels_jobs(self, loop):
        from bounces import mark_bounce
        from core import db

        async def go():
            email = "test_iter19_hard@example.invalid"
            await db.contacts.delete_many({"email": email})
            await db.bounces.delete_many({"email": email})
            res = await db.contacts.insert_one({"email": email, "status": "ativo", "first_name": "T"})
            cid = str(res.inserted_id)
            jid = (await db.email_jobs.insert_one({"contact_id": cid, "to_email": email, "status": "pending", "tracking_id": "t"})).inserted_id
            blocked = await mark_bounce(email, "hard", "550 User unknown", "smtp")
            c = await db.contacts.find_one({"_id": res.inserted_id})
            j = await db.email_jobs.find_one({"_id": jid})
            b = await db.bounces.find_one({"email": email})
            # cleanup
            await db.contacts.delete_many({"email": email})
            await db.bounces.delete_many({"email": email})
            await db.email_jobs.delete_many({"_id": jid})
            return blocked, c, j, b

        blocked, c, j, b = loop.run_until_complete(go())
        assert blocked is True
        assert c["status"] == "bounce" and c["blocked"] is True and c["bounce_type"] == "hard"
        assert c["bounce_reason"]
        assert j["status"] == "cancelled"
        assert b is not None and b["type"] == "hard" and b["source"] == "smtp"

    def test_soft_blocks_after_threshold(self, loop):
        from bounces import mark_bounce
        from core import db

        async def go():
            email = "test_iter19_soft@example.invalid"
            await db.contacts.delete_many({"email": email})
            await db.bounces.delete_many({"email": email})
            res = await db.contacts.insert_one({"email": email, "status": "ativo"})
            r1 = await mark_bounce(email, "soft", "452 Mailbox full", "imap")
            r2 = await mark_bounce(email, "soft", "452 Mailbox full", "imap")
            c_before = await db.contacts.find_one({"_id": res.inserted_id})
            r3 = await mark_bounce(email, "soft", "452 Mailbox full", "imap")
            c_after = await db.contacts.find_one({"_id": res.inserted_id})
            await db.contacts.delete_many({"email": email})
            await db.bounces.delete_many({"email": email})
            return r1, r2, r3, c_before, c_after

        r1, r2, r3, c_before, c_after = loop.run_until_complete(go())
        assert r1 is False and r2 is False and c_before["status"] == "ativo"
        assert r3 is True and c_after["status"] == "bounce" and c_after["soft_bounce_count"] == 3
