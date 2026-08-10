"""Iteration 16 — HTML signature must arrive as real HTML in the text/html MIME part.

Covers:
- MIME composition (multipart/alternative with text/plain + text/html)
- compose_email_html preserves table/img/anchor/inline colors (no text conversion, no box)
- /api/templates/preview returns email_html mirroring the sent HTML
- text/plain fallback keeps one info per line
- regression: plain-text templates + variable substitution
"""
import asyncio
import os
import re
import sys

import pytest
import requests
from dotenv import dotenv_values

sys.path.insert(0, "/app/backend")

frontend_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")).rstrip("/")
CREDS = {"email": "carlos.miguel@smartize.pt", "password": "100%Smartize"}

SIG_HTML = (
    '<table cellpadding="0" cellspacing="0" style="font-family:Arial;font-size:13px"><tr>'
    '<td style="padding-right:12px"><img src="https://smartize.pt/logo.png" width="120" alt="Smartize"></td>'
    '<td><div style="color:#111827;font-weight:bold">Carlos Santo</div>'
    '<div style="color:#7c3aed">Growth Manager – Smartize Portugal</div>'
    '<div style="color:#374151">Phone: (+351) 968 537 603</div>'
    '<div><a href="mailto:carlos.santo@smartize.pt" style="color:#2563eb">carlos.santo@smartize.pt</a></div>'
    '<div><a href="https://www.smartize.pt" style="color:#2563eb">www.smartize.pt</a></div>'
    '</td></tr></table>'
)
SIG_TEXT = ("Carlos Santo\nGrowth Manager – Smartize Portugal\nPhone: (+351) 968 537 603\n"
            "Email: carlos.santo@smartize.pt\nwww.smartize.pt")


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=CREDS, timeout=30)
    if r.status_code != 200:
        pytest.fail(f"login failed {r.status_code}: {r.text[:300]}")
    token = r.json().get("token")
    assert token
    s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return s


# --- email_service: compose_email_html / MIME ---------------------------------
class TestCompose:
    def test_compose_preserves_html_signature(self):
        from email_service import compose_email_html, text_to_html
        html = compose_email_html(text_to_html("Ola Joao,\n\nTexto simples."), SIG_HTML)
        assert "<table" in html
        assert 'src="https://smartize.pt/logo.png"' in html
        assert 'href="mailto:carlos.santo@smartize.pt"' in html
        assert 'href="https://www.smartize.pt"' in html
        assert "#7c3aed" in html and "#2563eb" in html
        assert "Ola Joao,<br>" in html
        # natural body: no card/box background
        assert "#f4f4f5" not in html
        # signature must not be flattened into text
        assert "SantoGrowth" not in html and "PortugalPhone" not in html

    def test_img_made_email_safe_without_losing_src(self):
        from email_service import compose_email_html
        html = compose_email_html("<p>Ola</p>", SIG_HTML)
        img = re.search(r"<img\b[^>]*>", html, re.I).group(0)
        assert "max-width:100%" in img and "height:auto" in img
        assert 'src="https://smartize.pt/logo.png"' in img
        assert 'width="120"' in img

    def test_mime_has_two_parts_html_signature_intact(self):
        """Build the real MIMEMultipart through send_email (SMTP transport patched out)."""
        import email_service
        from email_service import compose_email_html, text_to_html

        captured = {}

        async def fake_send(msg, **kwargs):
            captured["msg"] = msg
            return None

        original = email_service.aiosmtplib.send
        email_service.aiosmtplib.send = fake_send
        try:
            full_html = compose_email_html(text_to_html("Ola Joao,\n\nTexto."), SIG_HTML)
            text_body = "Ola Joao,\n\nTexto.\n\n" + SIG_TEXT
            asyncio.get_event_loop().run_until_complete(email_service.send_email(
                {"from_name": "Carlos", "from_email": "carlos@smartize.pt", "password_enc": "",
                 "host": "smtp.invalid", "port": 587},
                "dest@example.invalid", "Assunto", full_html, text_body,
            ))
        finally:
            email_service.aiosmtplib.send = original

        msg = captured["msg"]
        assert msg.get_content_type() == "multipart/alternative"
        parts = {p.get_content_type(): p.get_payload(decode=True).decode("utf-8") for p in msg.get_payload()}
        assert set(parts) == {"text/plain", "text/html"}, parts.keys()

        html_part = parts["text/html"]
        assert "<table" in html_part and "<img" in html_part
        assert "https://smartize.pt/logo.png" in html_part
        assert 'href="mailto:carlos.santo@smartize.pt"' in html_part
        assert "#7c3aed" in html_part

        text_part = parts["text/plain"]
        lines = [l for l in text_part.split("\n") if l.strip()]
        for expected in SIG_TEXT.split("\n"):
            assert expected in lines, (expected, lines)
        assert "<" not in text_part


# --- worker: always composes an HTML part with the HTML signature -------------
@pytest.fixture(scope="module")
def wenv():
    import worker
    from core import db
    from bson import ObjectId
    # Reuse the loop the Motor client is already bound to (a new loop breaks the driver).
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    async def setup():
        c = await db.contacts.insert_one({"first_name": "TEST_Joao", "last_name": "Silva",
                                          "email": "test_iter16@example.invalid", "status": "novo"})
        t = await db.templates.insert_one({"name": "TEST_iter16 plain", "subject": "Ola {first_name}",
                                          "content_text": "Ola {first_name},\n\nMensagem simples.",
                                          "content_html": ""})
        return str(c.inserted_id), str(t.inserted_id)

    contact_id, tpl_id = loop.run_until_complete(setup())
    yield {"worker": worker, "db": db, "ObjectId": ObjectId, "contact_id": contact_id, "tpl_id": tpl_id, "loop": loop}

    async def teardown():
        await db.contacts.delete_one({"_id": ObjectId(contact_id)})
        await db.templates.delete_one({"_id": ObjectId(tpl_id)})
        await db.email_jobs.delete_many({"contact_id": contact_id})
    loop.run_until_complete(teardown())


def _invoke(wenv, template_id, smtp):
    worker, db, ObjectId = wenv["worker"], wenv["db"], wenv["ObjectId"]
    captured = {}

    async def fake_send_email(smtp_account, to_email, subject, html_body, text_body, in_reply_to=None):
        captured.update(subject=subject, html=html_body, text=text_body, to=to_email)
        return "<fake@id>"

    original = worker.send_email
    worker.send_email = fake_send_email
    try:
        async def go():
            res = await db.email_jobs.insert_one({
                "campaign_id": "x", "contact_id": wenv["contact_id"], "to_email": "test_iter16@example.invalid",
                "status": "pending", "tracking_id": str(ObjectId()), "attempts": 0,
            })
            job = await db.email_jobs.find_one({"_id": res.inserted_id})
            await worker._send_job({"template_id": template_id}, job, smtp)
            return await db.email_jobs.find_one({"_id": res.inserted_id})
        job_after = wenv["loop"].run_until_complete(go())
    finally:
        worker.send_email = original
    return captured, job_after


class TestWorker:
    def test_plain_text_template_still_sends_html_signature(self, wenv):
        smtp = {"_id": "s1", "from_name": "Carlos", "from_email": "c@smartize.pt",
                "signature_html": SIG_HTML, "signature_text": SIG_TEXT}
        cap, job = _invoke(wenv, wenv["tpl_id"], smtp)
        assert job["status"] == "sent"
        # HTML part present with real HTML signature
        assert cap["html"], "worker must always send an HTML alternative"
        assert "<table" in cap["html"] and "<img" in cap["html"]
        assert "https://smartize.pt/logo.png" in cap["html"]
        assert "#7c3aed" in cap["html"]
        # body natural (<br>) and variables substituted
        assert "Ola TEST_Joao,<br>" in cap["html"]
        assert cap["subject"] == "Ola TEST_Joao"
        # links rewritten for tracking but mailto untouched
        assert 'href="mailto:carlos.santo@smartize.pt"' in cap["html"]
        assert "/api/track/click/" in cap["html"]
        assert "/api/track/open/" in cap["html"]
        # text fallback intact, one info per line
        lines = [l for l in cap["text"].split("\n") if l.strip()]
        for expected in SIG_TEXT.split("\n"):
            assert expected in lines
        assert "<" not in cap["text"]

    def test_derived_text_signature_when_signature_text_empty(self, wenv):
        smtp = {"_id": "s1", "from_name": "Carlos", "from_email": "c@smartize.pt",
                "signature_html": SIG_HTML, "signature_text": ""}
        cap, _ = _invoke(wenv, wenv["tpl_id"], smtp)
        lines = [l for l in cap["text"].split("\n") if l.strip()]
        assert "Carlos Santo" in lines
        assert "Growth Manager – Smartize Portugal" in lines
        assert "www.smartize.pt" in lines
        assert "<" not in cap["text"]
        # HTML part still has the untouched HTML signature
        assert "<table" in cap["html"]


# --- /api/templates/preview ---------------------------------------------------
class TestPreview:
    def test_preview_email_html_keeps_signature(self, client):
        r = client.post(f"{BASE_URL}/api/templates/preview", json={
            "subject": "Ola {first_name}",
            "content_html": "",
            "content_text": "Ola {first_name},\n\nSegunda linha.",
            "signature_html": SIG_HTML,
        }, timeout=30)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert "email_html" in data
        html = data["email_html"]
        assert "<table" in html and "<img" in html
        assert "https://smartize.pt/logo.png" in html
        assert 'href="mailto:carlos.santo@smartize.pt"' in html
        assert 'href="https://www.smartize.pt"' in html
        assert "#7c3aed" in html and "#2563eb" in html
        assert "Ola João,<br>" in html  # variable substituted + natural <br> body
        assert "#f4f4f5" not in html    # no card/box
        assert data["subject"] == "Ola João"

    def test_preview_text_fallback_has_signature_lines(self, client):
        r = client.post(f"{BASE_URL}/api/templates/preview", json={
            "subject": "s", "content_html": "", "content_text": "Ola {first_name},",
        }, timeout=30)
        assert r.status_code == 200
        data = r.json()
        text = data["content_text"]
        lines = [l for l in text.split("\n") if l.strip()]
        assert lines[0] == "Ola João,"
        assert "<" not in text
        assert len(lines) > 1, "account signature_text missing from plain-text fallback"
        assert "Carlos Santo" in lines
        # HTML alternative for the same preview keeps the account HTML signature
        assert "<" in data["email_html"] and "Carlos Santo" in data["email_html"]

    def test_preview_html_template_body_preserved(self, client):
        r = client.post(f"{BASE_URL}/api/templates/preview", json={
            "subject": "s",
            "content_html": "<p>Ola <b>{first_name}</b>, conteudo <i>HTML</i>.</p>",
            "content_text": "ignorado",
            "signature_html": SIG_HTML,
        }, timeout=30)
        assert r.status_code == 200
        html = r.json()["email_html"]
        assert "<b>João</b>" in html
        assert "<table" in html and "Growth Manager – Smartize Portugal" in html

    def test_preview_without_signature(self, client):
        r = client.post(f"{BASE_URL}/api/templates/preview", json={
            "subject": "s", "content_html": "", "content_text": "Ola {saudacao} {first_name},",
            "signature_html": "",
        }, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "Ola Caro João," in data["email_html"]
        assert "<img" not in data["email_html"]
        assert data["content_text"].strip() == "Ola Caro João,"
