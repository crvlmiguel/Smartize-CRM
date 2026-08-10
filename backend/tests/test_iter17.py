"""Iteration 17 — Signature fix: clean the pasted-editor bloat, prevent Gmail's
"show trimmed content" (...) collapse, and keep the HTML signature once at the end.

Covers:
- sanitize_signature_html strips unused Tailwind `--tw-*` custom properties but
  keeps the visible styling (color/font/width) and structure (img/links).
- compose_email_html sanitizes the signature (no --tw- junk) and includes it once.
- inject_anti_trim / inject_open_pixel add a UNIQUE invisible marker per email so
  Gmail does not trim the repeated signature.
- worker path: real _send_job output carries the clean signature + the unique token.
"""
import asyncio
import os
import re
import sys

import pytest
from dotenv import dotenv_values

sys.path.insert(0, "/app/backend")

# A realistic pasted signature bloated with the editor's unused --tw-* variables.
_TW = ("--tw-border-spacing-y: 0; --tw-translate-x: 0; --tw-ring-color: #3b82f680; "
       "--tw-shadow: 0 0 #0000; --tw-blur: ; ")
SIG_HTML = (
    f'<div style="{_TW}border-color: rgb(228, 228, 231); font-size: small; '
    f'font-family: Arial, Helvetica, sans-serif; color: rgb(136, 136, 136);">'
    f'<img src="https://smartize.pt/api/public/image/abc123" width="120" alt="" '
    f'style="{_TW}border-style: none; width: 120px;"></div>'
    f'<div style="{_TW}color: rgb(66, 135, 227);">Carlos Santo</div>'
    f'<div style="{_TW}color: rgb(136, 136, 136);">'
    f'<a href="https://www.smartize.pt" style="{_TW}color: rgb(66, 135, 227);">www.smartize.pt</a></div>'
)


# --- sanitize_signature_html --------------------------------------------------
class TestSanitize:
    def test_removes_tw_junk_keeps_visible_styles(self):
        from email_service import sanitize_signature_html
        out = sanitize_signature_html(SIG_HTML)
        assert "--tw-" not in out
        # Visible styling preserved.
        assert "rgb(66, 135, 227)" in out
        assert "font-family: Arial, Helvetica, sans-serif" in out
        assert "width: 120px" in out
        # Structure preserved.
        assert 'src="https://smartize.pt/api/public/image/abc123"' in out
        assert 'href="https://www.smartize.pt"' in out
        assert "Carlos Santo" in out
        # Substantially smaller than the bloated input.
        assert len(out) < len(SIG_HTML)

    def test_empty_signature(self):
        from email_service import sanitize_signature_html
        assert sanitize_signature_html("") == ""


# --- compose_email_html -------------------------------------------------------
class TestCompose:
    def test_signature_sanitized_and_present_once(self):
        from email_service import compose_email_html, text_to_html
        html = compose_email_html(text_to_html("Ola,\n\nCom os melhores cumprimentos,"), SIG_HTML)
        assert "--tw-" not in html
        assert html.count("/api/public/image/abc123") == 1
        assert "Carlos Santo" in html
        assert "Ola,<br>" in html


# --- anti-trim marker (Gmail "..." fix) --------------------------------------
class TestAntiTrim:
    def test_inject_anti_trim_adds_unique_marker(self):
        from email_service import inject_anti_trim
        html = "<html><body><p>Ola</p></body></html>"
        out = inject_anti_trim(html, "TOKEN-XYZ")
        assert "TOKEN-XYZ" in out
        # placed before </body>
        assert out.index("TOKEN-XYZ") < out.lower().index("</body>")
        # faintly-visible (NOT opacity:0/display:none — those are unreliable in Gmail)
        assert "opacity:0" not in out and "display:none" not in out
        assert "font-size:8px" in out

    def test_open_pixel_bundles_unique_token_and_pixel(self):
        from email_service import inject_open_pixel
        base = "https://x.test"
        a = inject_open_pixel("<html><body>hi</body></html>", base, "TID-A")
        b = inject_open_pixel("<html><body>hi</body></html>", base, "TID-B")
        assert "TID-A" in a and "/api/track/open/TID-A.png" in a
        assert "TID-B" in b
        # unique per email -> Gmail cannot match a "repeated" signature
        assert "TID-A" not in b


# --- worker path --------------------------------------------------------------
@pytest.fixture(scope="module")
def wenv():
    import worker
    from core import db
    from bson import ObjectId
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    async def setup():
        c = await db.contacts.insert_one({"first_name": "TEST_Ana", "last_name": "S",
                                          "email": "test_iter17@example.invalid", "status": "novo"})
        t = await db.templates.insert_one({"name": "TEST_iter17", "subject": "Ola {first_name}",
                                          "content_text": "Ola {first_name},\n\nMensagem.",
                                          "content_html": ""})
        return str(c.inserted_id), str(t.inserted_id)

    contact_id, tpl_id = loop.run_until_complete(setup())
    yield {"worker": worker, "db": db, "ObjectId": ObjectId,
           "contact_id": contact_id, "tpl_id": tpl_id, "loop": loop}

    async def teardown():
        await db.contacts.delete_one({"_id": ObjectId(contact_id)})
        await db.templates.delete_one({"_id": ObjectId(tpl_id)})
        await db.email_jobs.delete_many({"contact_id": contact_id})
    loop.run_until_complete(teardown())


class TestWorker:
    def test_send_job_clean_signature_and_unique_token(self, wenv):
        worker, db, ObjectId = wenv["worker"], wenv["db"], wenv["ObjectId"]
        captured = {}

        async def fake_send_email(smtp_account, to_email, subject, html_body, text_body, in_reply_to=None):
            captured.update(html=html_body, text=text_body)
            return "<fake@id>"

        smtp = {"_id": "s1", "from_name": "Carlos", "from_email": "c@smartize.pt",
                "signature_html": SIG_HTML, "signature_text": "Carlos Santo\nwww.smartize.pt"}
        original = worker.send_email
        worker.send_email = fake_send_email
        try:
            async def go():
                res = await db.email_jobs.insert_one({
                    "campaign_id": "x", "contact_id": wenv["contact_id"],
                    "to_email": "test_iter17@example.invalid", "status": "pending",
                    "tracking_id": str(ObjectId()), "attempts": 0,
                })
                job = await db.email_jobs.find_one({"_id": res.inserted_id})
                await worker._send_job({"template_id": wenv["tpl_id"]}, job, smtp)
                return job
            job = wenv["loop"].run_until_complete(go())
        finally:
            worker.send_email = original

        assert "--tw-" not in captured["html"]
        assert captured["html"].count("/api/public/image/abc123") == 1
        assert job["tracking_id"] in captured["html"]
        assert "Ola TEST_Ana,<br>" in captured["html"]
        # plain-text fallback stays clean
        assert "<" not in captured["text"]
