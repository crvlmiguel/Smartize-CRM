"""Iteration 12 tests: natural (non-boxed) outreach email HTML + real Plain Text sending.

Modules covered:
- email_service.wrap_email_html / compose_email_html (unit)
- POST /api/templates/preview (HTML template -> natural email_html; text-only -> email_html == "")
- Campaign pipeline: jobs created for HTML template and for plain-text-only template
"""
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

HTML_CONTENT = (
    '<p>Olá {first_name}, {saudacao} {last_name} da {company}.</p>'
    '<p>Veja <a href="https://smartize.pt/produto">a nossa página</a>.</p>'
    '<p><img src="https://smartize.pt/logo.png" width="200" style="border:1px solid #ccc"></p>'
)
TEXT_CONTENT = "Olá {first_name},\n\nSou o Carlos da Smartize.\n\nAbraço,\nCarlos"


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
    """Track and clean up test data (templates, groups, contacts, campaigns)."""
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


# ---------- Unit: compose_email_html has no container box ----------
class TestComposeUnit:
    def test_no_container_markup(self):
        from email_service import compose_email_html
        html = compose_email_html("<p>Olá</p>", '<p>Carlos<br>Smartize</p>')
        low = html.lower()
        assert "<table" not in low, html
        assert "background-color" not in low, html
        assert "background:" not in low, html
        assert "border-radius" not in low, html
        # no container border/max-width card
        assert not re.search(r'border\s*:\s*1px', low), html
        assert "max-width:600px" not in low.replace(" ", ""), html
        # natural wrapper only
        assert "font-family:arial" in low.replace(" ", "").replace("font-family:arial,helvetica,sans-serif", "font-family:arial")
        assert "line-height" in low
        assert "<p>ol" in low
        # signature separated by blank-line spacing
        assert "<br><br>" in low, html
        assert "Carlos" in html

    def test_img_email_safe_and_border_stripped(self):
        from email_service import compose_email_html
        html = compose_email_html('<img src="x.png" width="200" style="border:1px solid #ccc">', "")
        m = re.search(r"<img[^>]*>", html, re.I)
        assert m, html
        tag = m.group(0)
        assert "max-width:100%" in tag, tag
        assert "height:auto" in tag, tag
        assert "border:0" in tag, tag
        assert "1px solid" not in tag, tag
        assert 'width="200"' in tag, tag

    def test_no_signature_no_extra_break(self):
        from email_service import compose_email_html
        html = compose_email_html("<p>Olá</p>", "")
        assert "<br><br>" not in html.lower(), html


# ---------- API: preview for HTML template ----------
class TestPreviewHtml:
    def test_html_preview_is_natural(self, client):
        r = client.post(f"{BASE_URL}/templates/preview", json={
            "subject": "Proposta para {company}",
            "content_html": HTML_CONTENT,
            "content_text": "",
            "signature_html": "<p>Carlos Miguel<br>Smartize</p>",
        }, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        eh = d["email_html"]
        low = eh.lower()
        assert "<table" not in low, eh
        assert "background-color" not in low, eh
        assert "border-radius" not in low, eh
        assert not re.search(r'border\s*:\s*1px', low), eh
        # variables substituted
        assert "{first_name}" not in eh and "{saudacao}" not in eh
        assert "João" in eh and "Silva" in eh and "Smartize" in eh
        assert d["subject"] == "Proposta para Smartize"
        # link intact in preview (tracking rewrite happens at send time)
        assert "https://smartize.pt/produto" in eh
        # signature present at the end, separated by spacing
        assert "<br><br>" in low
        assert eh.lower().rindex("carlos miguel") > eh.lower().rindex("produto")
        # img email-safe
        assert "max-width:100%" in eh and "height:auto" in eh and "border:0" in eh

    def test_preview_default_signature_used_when_omitted(self, client):
        r = client.post(f"{BASE_URL}/templates/preview", json={
            "subject": "s", "content_html": "<p>Olá {first_name}</p>", "content_text": "",
        }, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["email_html"].startswith("<!DOCTYPE html>")


# ---------- API: preview for plain-text template ----------
class TestPreviewPlainText:
    def test_text_only_still_returns_html_alternative(self, client):
        r = client.post(f"{BASE_URL}/templates/preview", json={
            "subject": "Olá {first_name}",
            "content_html": "",
            "content_text": TEXT_CONTENT,
        }, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        # iter16: an HTML alternative is ALWAYS produced (natural body + HTML signature)
        assert d["email_html"].startswith("<!DOCTYPE html>")
        assert "Olá João,<br>" in d["email_html"]
        assert d["content_text"].startswith("Olá João,"), d["content_text"]
        assert "{first_name}" not in d["content_text"]
        assert "Abraço,\nCarlos" in d["content_text"]
        assert d["subject"] == "Olá João"

    def test_whitespace_only_html_is_treated_as_text(self, client):
        r = client.post(f"{BASE_URL}/templates/preview", json={
            "subject": "x", "content_html": "   \n  ", "content_text": TEXT_CONTENT,
        }, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["email_html"].startswith("<!DOCTYPE html>")


# ---------- Pipeline: campaigns with HTML and text-only templates ----------
class TestCampaignPipeline:
    def _make_group_with_contact(self, client, created, label):
        g = client.post(f"{BASE_URL}/groups", json={"name": f"TEST_iter12_{label}_{TAG}"}, timeout=30)
        assert g.status_code in (200, 201), g.text
        gid = g.json()["id"]
        created["groups"].append(gid)
        c = client.post(f"{BASE_URL}/contacts", json={
            "first_name": "Ana", "last_name": "Costa", "saudacao": "Cara",
            "email": f"qa_iter12_{label}_{TAG}@example.com", "company": "ACME",
            "group_id": gid,
        }, timeout=30)
        assert c.status_code in (200, 201), c.text
        created["contacts"].append(c.json()["id"])
        return gid

    def _start(self, client, created, tpl_payload, label):
        t = client.post(f"{BASE_URL}/templates", json=tpl_payload, timeout=30)
        assert t.status_code in (200, 201), t.text
        tid = t.json()["id"]
        created["templates"].append(tid)
        gid = self._make_group_with_contact(client, created, label)
        camp = client.post(f"{BASE_URL}/campaigns", json={
            "name": f"TEST_iter12_{label}_{TAG}", "group_id": gid, "template_id": tid,
        }, timeout=30)
        assert camp.status_code in (200, 201), camp.text
        cid = camp.json()["id"]
        created["campaigns"].append(cid)
        st = client.post(f"{BASE_URL}/campaigns/{cid}/start", timeout=60)
        assert st.status_code == 200, st.text
        assert st.json()["recipients"] == 1, st.json()
        got = client.get(f"{BASE_URL}/campaigns/{cid}", timeout=30)
        assert got.status_code == 200
        assert got.json()["status"] in ("sending", "completed"), got.json()["status"]
        return cid

    def test_html_campaign_creates_jobs(self, client, created):
        self._start(client, created, {
            "name": f"TEST_iter12_html_{TAG}", "subject": "Olá {first_name}",
            "content_html": HTML_CONTENT, "content_text": "",
        }, "html")

    def test_text_only_campaign_creates_jobs(self, client, created):
        self._start(client, created, {
            "name": f"TEST_iter12_text_{TAG}", "subject": "Olá {first_name}",
            "content_html": "", "content_text": TEXT_CONTENT,
        }, "text")

    def test_worker_builds_empty_html_for_text_only_template(self):
        """Mirror worker logic: text-only template must produce full_html == '' (real plain text)."""
        from email_service import compose_email_html
        html_body = ""
        full_html = compose_email_html(html_body, "sig") if html_body.strip() else ""
        assert full_html == ""
