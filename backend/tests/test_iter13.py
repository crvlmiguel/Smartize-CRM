"""Iteration 13 tests: Templates are Plain Text ONLY.

Modules / features covered:
- email_service.html_has_visible_content (unit): empty editor markup => plain text
- email_service.send_email (unit, SMTP patched): empty html_body => single text/plain part
- POST/PUT/GET /api/templates: content_html is always persisted empty for plain-text templates,
  legacy HTML templates are cleaned on update
- POST /api/templates/preview: email_html == "" and variables substituted in subject + body
- Campaign pipeline with plain-text template: jobs created, campaign 'sending'
- worker._send_job / _send_sequence_step branching (source-level assertion on html_has_visible_content)
"""
import asyncio
import os
import re
import sys
import uuid

import pytest
import requests
from dotenv import dotenv_values

sys.path.insert(0, "/app/backend")

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/") + "/api"

EMAIL = "carlos.miguel@smartize.pt"
PASSWORD = "100%Smartize"
TAG = uuid.uuid4().hex[:6]

TEXT_CONTENT = (
    "Caro {saudacao} {first_name},\n\nEspero que esteja bem. Trabalha na {company}?\n\n"
    "Com os melhores cumprimentos,\nMiguel\nSmartize"
)


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    if r.status_code != 200:
        pytest.fail(f"Login failed {r.status_code}: {r.text[:300]}")
    token = r.json().get("token")
    assert token, "no token in login response"
    s.headers.update({"Authorization": f"Bearer {token}"})
    yield s


@pytest.fixture(scope="module")
def created(client):
    store = {"templates": [], "groups": [], "contacts": [], "campaigns": []}
    yield store
    for cid in store["campaigns"]:
        client.delete(f"{BASE_URL}/campaigns/{cid}", timeout=30)
    for cid in store["contacts"]:
        client.delete(f"{BASE_URL}/contacts/{cid}", timeout=30)
    for gid in store["groups"]:
        client.delete(f"{BASE_URL}/groups/{gid}", timeout=30)
    for tid in store["templates"]:
        client.delete(f"{BASE_URL}/templates/{tid}", timeout=30)


# ---------- Unit: html_has_visible_content ----------
class TestVisibleContentUnit:
    @pytest.mark.parametrize("html", ["", "   ", "<br>", "<p><br></p>", "<div><br></div>", "<p>&nbsp;</p>", "<p></p>"])
    def test_empty_editor_markup_is_not_visible(self, html):
        from email_service import html_has_visible_content
        assert html_has_visible_content(html) is False, html

    @pytest.mark.parametrize("html", ["<p>Olá</p>", "texto", '<img src="a.png">'])
    def test_real_content_is_visible(self, html):
        from email_service import html_has_visible_content
        assert html_has_visible_content(html) is True, html


# ---------- Unit: send_email builds a real text/plain message when html is empty ----------
class TestSendEmailMime:
    def _send(self, html_body, text_body):
        import email_service
        captured = {}

        async def fake_send(msg, **kwargs):
            captured["msg"] = msg
            return {}, "ok"

        orig = email_service.aiosmtplib.send
        email_service.aiosmtplib.send = fake_send
        try:
            asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
                email_service.send_email(
                    {"host": "smtp.example.com", "port": 587, "from_email": "a@b.pt",
                     "from_name": "QA", "username": "", "password_enc": ""},
                    "to@example.com", "Assunto", html_body, text_body,
                )
            )
        finally:
            email_service.aiosmtplib.send = orig
        return captured["msg"]

    def test_plain_text_only_message(self):
        msg = self._send("", "Olá João,\n\nAbraço")
        parts = [p.get_content_type() for p in msg.walk() if not p.get_content_type().startswith("multipart")]
        assert parts == ["text/plain"], parts
        raw = msg.as_string()
        assert "text/html" not in raw
        assert "<div" not in raw and "<html" not in raw.lower()

    def test_html_present_when_html_body_given(self):
        msg = self._send("<html><body><div>Olá</div></body></html>", "Olá")
        parts = [p.get_content_type() for p in msg.walk() if not p.get_content_type().startswith("multipart")]
        assert parts == ["text/plain", "text/html"], parts


# ---------- API: preview is plain text ----------
class TestPreviewPlainText:
    def test_preview_empty_email_html_and_substitution(self, client):
        r = client.post(f"{BASE_URL}/templates/preview", json={
            "subject": "Ola {first_name} da {company}",
            "content_html": "",
            "content_text": TEXT_CONTENT,
        }, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["email_html"] == "", d["email_html"][:200]
        assert d["subject"] == "Ola João da Smartize", d["subject"]
        body = d["content_text"]
        assert body.startswith("Caro Caro João,"), body
        assert "{first_name}" not in body and "{saudacao}" not in body and "{company}" not in body
        assert "Smartize" in body
        # no HTML markup leaked into the plain-text preview body
        assert not re.search(r"<[a-zA-Z/]", body), body

    def test_preview_double_brace_variables(self, client):
        r = client.post(f"{BASE_URL}/templates/preview", json={
            "subject": "Ola {{first_name}}",
            "content_html": "",
            "content_text": "Caro {{saudacao}} {{first_name}} da {{company}}",
        }, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["subject"] == "Ola João", d["subject"]
        assert d["content_text"].startswith("Caro Caro João da Smartize"), d["content_text"]
        assert d["email_html"] == ""

    def test_preview_includes_signature_as_text(self, client):
        r = client.post(f"{BASE_URL}/templates/preview", json={
            "subject": "x", "content_html": "", "content_text": "Corpo",
            "signature_html": "<p>Carlos Miguel<br>Smartize</p>",
        }, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["email_html"] == ""
        assert "Carlos Miguel" in d["content_text"]
        assert "<" not in d["content_text"], d["content_text"]


# ---------- API: persistence, content_html always empty ----------
class TestTemplatePersistence:
    def test_create_plain_text_template_persists_empty_html(self, client, created):
        payload = {"name": f"TEST_iter13_plain_{TAG}", "subject": "Ola {first_name}",
                   "content_text": TEXT_CONTENT, "content_html": ""}
        r = client.post(f"{BASE_URL}/templates", json=payload, timeout=30)
        assert r.status_code in (200, 201), r.text
        t = r.json()
        tid = t["id"]
        created["templates"].append(tid)
        assert t["name"] == payload["name"]
        assert t["content_text"] == TEXT_CONTENT
        assert (t.get("content_html") or "") == "", t.get("content_html")
        assert "_id" not in t

        listed = client.get(f"{BASE_URL}/templates", timeout=30)
        assert listed.status_code == 200, listed.text
        match = [x for x in listed.json() if x["id"] == tid]
        assert match, "created template missing from GET /templates"
        got = match[0]
        assert got["content_text"] == TEXT_CONTENT
        assert (got.get("content_html") or "") == ""
        assert got["subject"] == "Ola {first_name}"
        assert "_id" not in got

    def test_update_legacy_html_template_clears_html(self, client, created):
        legacy = {"name": f"TEST_iter13_legacy_{TAG}", "subject": "Assunto legado",
                  "content_html": "<p>HTML <b>antigo</b></p><img src='x.png'>", "content_text": "texto antigo"}
        r = client.post(f"{BASE_URL}/templates", json=legacy, timeout=30)
        assert r.status_code in (200, 201), r.text
        tid = r.json()["id"]
        created["templates"].append(tid)
        assert "HTML" in r.json()["content_html"]

        upd = client.put(f"{BASE_URL}/templates/{tid}", json={
            "name": legacy["name"], "subject": "Assunto novo",
            "content_text": "Novo corpo em texto simples", "content_html": "",
        }, timeout=30)
        assert upd.status_code == 200, upd.text

        listed = client.get(f"{BASE_URL}/templates", timeout=30)
        got = [x for x in listed.json() if x["id"] == tid][0]
        assert (got.get("content_html") or "") == "", got.get("content_html")
        assert got["content_text"] == "Novo corpo em texto simples"
        assert got["subject"] == "Assunto novo"

    def test_delete_template_removed(self, client):
        r = client.post(f"{BASE_URL}/templates", json={
            "name": f"TEST_iter13_del_{TAG}", "subject": "s", "content_text": "t", "content_html": ""}, timeout=30)
        assert r.status_code in (200, 201), r.text
        tid = r.json()["id"]
        d = client.delete(f"{BASE_URL}/templates/{tid}", timeout=30)
        assert d.status_code in (200, 204), d.text
        listed = client.get(f"{BASE_URL}/templates", timeout=30)
        assert not [x for x in listed.json() if x["id"] == tid]


# ---------- Pipeline: plain-text campaign ----------
class TestPlainTextCampaign:
    def test_campaign_with_plain_text_template(self, client, created):
        t = client.post(f"{BASE_URL}/templates", json={
            "name": f"TEST_iter13_camp_{TAG}", "subject": "Ola {first_name}",
            "content_text": TEXT_CONTENT, "content_html": ""}, timeout=30)
        assert t.status_code in (200, 201), t.text
        tid = t.json()["id"]
        created["templates"].append(tid)

        g = client.post(f"{BASE_URL}/groups", json={"name": f"TEST_iter13_grp_{TAG}"}, timeout=30)
        assert g.status_code in (200, 201), g.text
        gid = g.json()["id"]
        created["groups"].append(gid)
        c = client.post(f"{BASE_URL}/contacts", json={
            "first_name": "Ana", "last_name": "Costa", "saudacao": "Cara",
            "email": f"qa_iter13_{TAG}@example.com", "company": "ACME", "group_id": gid}, timeout=30)
        assert c.status_code in (200, 201), c.text
        created["contacts"].append(c.json()["id"])

        camp = client.post(f"{BASE_URL}/campaigns", json={
            "name": f"TEST_iter13_camp_{TAG}", "group_id": gid, "template_id": tid}, timeout=30)
        assert camp.status_code in (200, 201), camp.text
        cid = camp.json()["id"]
        created["campaigns"].append(cid)

        st = client.post(f"{BASE_URL}/campaigns/{cid}/start", timeout=60)
        assert st.status_code == 200, st.text
        assert st.json()["recipients"] == 1, st.json()

        got = client.get(f"{BASE_URL}/campaigns/{cid}", timeout=30)
        assert got.status_code == 200, got.text
        assert got.json()["status"] in ("sending", "completed"), got.json()["status"]


# ---------- Worker source-level branching ----------
class TestWorkerBranching:
    def test_worker_uses_visible_content_check(self):
        src = open("/app/backend/worker.py", encoding="utf-8").read()
        assert src.count("html_has_visible_content(") >= 2, "both send paths must use html_has_visible_content"
        assert "content_html" in src
        # plain-text branch must produce an empty html body
        assert re.search(r"else:\s*\n\s*#[^\n]*\n\s*full_html = \"\"", src), "plain-text branch missing"

    def test_worker_plain_text_produces_empty_full_html(self):
        from email_service import html_has_visible_content, compose_email_html
        html_body = ""
        full_html = compose_email_html(html_body, "<p>sig</p>") if html_has_visible_content(html_body) else ""
        assert full_html == ""
        html_body = "<p><br></p>"
        full_html = compose_email_html(html_body, "<p>sig</p>") if html_has_visible_content(html_body) else ""
        assert full_html == ""


# ---------- Frontend source guard: no rich text / HTML editor left ----------
class TestTemplatesUISource:
    def test_no_rich_text_editor_in_templates_page(self):
        src = open("/app/frontend/src/pages/Templates.jsx", encoding="utf-8").read()
        for banned in ["RichTextEditor", "contentEditable", "execCommand", "dangerouslySetInnerHTML",
                       "iframe", "Tabs", "content-html-input"]:
            assert banned not in src, f"{banned} still present in Templates.jsx"
        assert "template-text-input" in src
        assert 'content_html: ""' in src
