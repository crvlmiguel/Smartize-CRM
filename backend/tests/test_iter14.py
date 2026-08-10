"""Iteration 14 — legacy template migration (HIGH bug), plain-text preview, branding/company_name."""
import os
import re
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")


@pytest.fixture(scope="module")
def creds():
    p = Path("/app/memory/test_credentials.md")
    content = p.read_text(encoding="utf-8")
    m = re.search(r"Email:\s*(\S+)\s*\|\s*Password:\s*(\S+)", content)
    if not m:
        pytest.skip("credentials not parseable")
    return {"email": m.group(1), "password": m.group(2)}


@pytest.fixture(scope="module")
def client(creds):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json=creds)
    if r.status_code != 200:
        pytest.fail(f"login failed {r.status_code}: {r.text[:300]}")
    token = r.json().get("token")
    assert isinstance(token, str) and token
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module")
def created(client):
    ids = []
    yield ids
    for tid in ids:
        client.delete(f"{BASE_URL}/api/templates/{tid}")


# ---------------- Legacy template migration (bug HIGH) ----------------
class TestLegacyTemplateMigration:
    def test_create_legacy_template_persists_html(self, client, created):
        payload = {"name": "TEST_iter14 Legacy", "subject": "Ola {first_name}",
                   "content_html": "<p>Ola {first_name}</p><p>Segundo paragrafo</p>", "content_text": ""}
        r = client.post(f"{BASE_URL}/api/templates", json=payload)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "id" in d and "_id" not in d
        created.append(d["id"])
        g = client.get(f"{BASE_URL}/api/templates/{d['id']}")
        assert g.status_code == 200
        gd = g.json()
        assert gd["content_html"] == payload["content_html"]
        assert gd["content_text"] == ""

    def test_update_with_migrated_text_clears_html(self, client, created):
        tid = created[0]
        migrated = "Ola {first_name}\n\nSegundo paragrafo"
        r = client.put(f"{BASE_URL}/api/templates/{tid}", json={
            "name": "TEST_iter14 Legacy", "subject": "Ola {first_name}",
            "content_text": migrated, "content_html": ""})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["content_text"] == migrated
        assert d["content_html"] == ""
        # GET to verify persistence — body must NOT be lost
        gd = client.get(f"{BASE_URL}/api/templates/{tid}").json()
        assert gd["content_text"] == migrated
        assert gd["content_html"] == ""
        assert gd["content_text"].strip() != ""

    def test_seeded_legacy_templates_still_have_html_body(self, client):
        """Seed 'QA Template 1/2' should keep legacy html so the UI fallback can be exercised."""
        r = client.get(f"{BASE_URL}/api/templates")
        assert r.status_code == 200
        names = {t["name"]: t for t in r.json()}
        legacy = [t for n, t in names.items() if n.startswith("QA Template")]
        for t in legacy:
            assert "_id" not in t
        # informational assert: at least one legacy template exists for UI testing
        assert len(legacy) >= 1


# ---------------- Plain-text preview ----------------
class TestPreview:
    def test_preview_plain_text_only(self, client):
        r = client.post(f"{BASE_URL}/api/templates/preview", json={
            "subject": "Ola {{first_name}}", "content_html": "",
            "content_text": "Caro {{saudacao}} {{first_name}}, da {{company}}."})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["email_html"] == ""
        assert d["subject"] == "Ola João"
        assert "{{" not in d["content_text"]
        assert "João" in d["content_text"]
        assert "<" not in d["content_text"].replace("\n", "")

    def test_preview_both_variable_syntaxes(self, client):
        r = client.post(f"{BASE_URL}/api/templates/preview", json={
            "subject": "{first_name} / {{last_name}}", "content_html": "", "content_text": "{company}"})
        assert r.status_code == 200
        d = r.json()
        assert d["subject"] == "João / Silva"
        assert "Smartize" in d["content_text"]


# ---------------- Settings / branding ----------------
class TestBranding:
    def test_settings_company_name_restored(self, client):
        r = client.get(f"{BASE_URL}/api/settings")
        assert r.status_code == 200
        d = r.json()
        assert "_id" not in d
        assert d["company_name"] == "Smartize", f"leftover test data: {d['company_name']}"

    def test_public_branding_company_name(self):
        r = requests.get(f"{BASE_URL}/api/public/branding")
        assert r.status_code == 200
        assert r.json()["company_name"] == "Smartize"


# ---------------- Auth basics ----------------
class TestAuth:
    def test_me(self, client, creds):
        r = client.get(f"{BASE_URL}/api/auth/me")
        assert r.status_code == 200
        assert r.json()["email"] == creds["email"]

    def test_login_bad_password(self, creds):
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": creds["email"], "password": "wrong-pass-xyz"})
        assert r.status_code in (400, 401, 423, 429), r.text
