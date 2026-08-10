"""Iteration 9 tests: 'saudacao' field (import, contact CRUD, template variable),
import 'incomplete' counter fix, and email-safe <img> normalisation."""
import io
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
    # cleanup: remove every contact created by this run
    lst = s.get(f"{BASE_URL}/contacts", params={"search": f"qa_saud_iter9_{TAG}"}, timeout=30)
    if lst.status_code == 200:
        for c in lst.json():
            if f"qa_saud_iter9_{TAG}" in (c.get("email") or ""):
                s.delete(f"{BASE_URL}/contacts/{c['id']}", timeout=30)


def _csv(rows_csv: str, name="contacts.csv"):
    return {"file": (name, io.BytesIO(rows_csv.encode("utf-8")), "text/csv")}


# ---------- SAUDACAO: import ----------
class TestImportSaudacao:
    def test_preview_detects_saudacao_and_incomplete(self, client):
        csv = (
            "first_name,last_name,Saudação,email,company,job_title\n"
            f"Ana,Lopes,Cara,qa_saud_iter9_{TAG}_a@example.com,ACME,CEO\n"
            f",,Exmo.,qa_saud_iter9_{TAG}_b@example.com,Beta,Dev\n"
            "bad,row,Caro,not-an-email,Gamma,QA\n"
        )
        r = client.post(f"{BASE_URL}/contacts/import/preview", files=_csv(csv), timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        # 'Saudação' header (accented, capitalised) must auto-map to the saudacao field
        assert d["mapping"].get("saudacao") == "saudação", d["mapping"]
        assert d["counts"]["total"] == 3
        assert d["counts"]["valid"] == 2
        assert d["counts"]["invalid"] == 1
        # fixed counter: row without first/last name must be counted as incomplete
        assert d["counts"]["incomplete"] >= 1, d["counts"]
        # sample rows carry the saudacao value verbatim
        assert d["sample"][0]["saudacao"] == "Cara"
        assert d["sample"][1]["saudacao"] == "Exmo."

    def test_import_stores_saudacao_verbatim(self, client):
        email = f"qa_saud_iter9_{TAG}_imp@example.com"
        csv = f"first_name,last_name,saudacao,email\nRui,Nunes,Exmo.,{email}\n"
        r = client.post(f"{BASE_URL}/contacts/import", files=_csv(csv), data={"mapping": ""}, timeout=60)
        assert r.status_code == 200, r.text
        assert r.json()["imported"] == 1, r.json()

        lst = client.get(f"{BASE_URL}/contacts", params={"search": email}, timeout=30)
        assert lst.status_code == 200
        found = [c for c in lst.json() if c["email"] == email]
        assert found, "imported contact not returned by GET /contacts"
        c = found[0]
        assert c["saudacao"] == "Exmo.", c
        assert "_id" not in c

    def test_import_without_saudacao_still_works(self, client):
        email = f"qa_saud_iter9_{TAG}_nosaud@example.com"
        csv = f"first_name,last_name,email,company\nZita,Reis,{email},Delta\n"
        r = client.post(f"{BASE_URL}/contacts/import", files=_csv(csv), timeout=60)
        assert r.status_code == 200, r.text
        assert r.json()["imported"] == 1
        lst = client.get(f"{BASE_URL}/contacts", params={"search": email}, timeout=30)
        c = [x for x in lst.json() if x["email"] == email][0]
        assert c.get("saudacao") == ""


# ---------- SAUDACAO: contact CRUD ----------
class TestContactSaudacao:
    def test_create_update_persists_saudacao(self, client):
        email = f"qa_saud_iter9_{TAG}_crud@example.com"
        r = client.post(f"{BASE_URL}/contacts", json={
            "first_name": "Marta", "last_name": "Sousa", "saudacao": "Exma. Sra.", "email": email,
        }, timeout=30)
        assert r.status_code in (200, 201), r.text
        cid = r.json()["id"]
        assert r.json()["saudacao"] == "Exma. Sra."

        g = client.get(f"{BASE_URL}/contacts/{cid}", timeout=30)
        assert g.status_code == 200
        assert g.json()["saudacao"] == "Exma. Sra."

        u = client.put(f"{BASE_URL}/contacts/{cid}", json={"saudacao": "Cara"}, timeout=30)
        assert u.status_code == 200, u.text
        g2 = client.get(f"{BASE_URL}/contacts/{cid}", timeout=30)
        assert g2.json()["saudacao"] == "Cara"
        assert g2.json()["first_name"] == "Marta"

    def test_preview_uses_contact_saudacao(self, client):
        email = f"qa_saud_iter9_{TAG}_prev@example.com"
        r = client.post(f"{BASE_URL}/contacts", json={
            "first_name": "Pedro", "last_name": "Alves", "saudacao": "Exmo. Sr.", "email": email,
        }, timeout=30)
        cid = r.json()["id"]
        p = client.post(f"{BASE_URL}/templates/preview", json={
            "subject": "{saudacao} {first_name}",
            "content_html": "<p>{saudacao} {first_name},</p>",
            "contact_id": cid,
        }, timeout=60)
        assert p.status_code == 200, p.text
        d = p.json()
        assert d["subject"] == "Exmo. Sr. Pedro", d["subject"]
        assert "Exmo. Sr. Pedro," in d["content_html"]


# ---------- SAUDACAO: template variable ----------
class TestTemplatePreviewVariable:
    def test_single_and_double_brace_saudacao(self, client):
        p = client.post(f"{BASE_URL}/templates/preview", json={
            "subject": "{{saudacao}} {{first_name}}",
            "content_html": "<p>{saudacao} {first_name}</p>",
            "signature_html": "",
        }, timeout=60)
        assert p.status_code == 200, p.text
        d = p.json()
        assert d["subject"] == "Caro João", d["subject"]
        assert "Caro João" in d["content_html"]
        assert "Caro João" in d["email_html"]

    def test_content_text_variable_and_plain_text_intact(self, client):
        p = client.post(f"{BASE_URL}/templates/preview", json={
            "subject": "x",
            "content_html": "",
            "content_text": "{saudacao} {first_name},\nObrigado.",
        }, timeout=60)
        d = p.json()
        assert d["content_text"].startswith("Caro João,")
        assert "Caro João,<br/>Obrigado." in d["email_html"]


# ---------- EMAIL-SAFE IMG ----------
class TestEmailSafeImg:
    def test_border_style_initial_removed(self, client):
        html = "<p><img src=\"https://x.test/a.png\" style=\"line-height:1.4;border-style:initial;width:120px\"></p>"
        p = client.post(f"{BASE_URL}/templates/preview", json={
            "subject": "s", "content_html": html, "signature_html": "",
        }, timeout=60)
        assert p.status_code == 200, p.text
        eh = p.json()["email_html"]
        m = re.search(r"<img[^>]*a\.png[^>]*>", eh)
        assert m, eh
        tag = m.group(0)
        assert "border-style" not in tag, tag
        assert "border:0" in tag, tag
        assert "max-width:100%" in tag, tag
        assert "height:auto" in tag, tag
        assert "width:120px" in tag, tag
        assert "line-height:1.4" in tag, tag
        assert ";;" not in tag, tag

    def test_img_without_style_gets_defaults(self, client):
        p = client.post(f"{BASE_URL}/templates/preview", json={
            "subject": "s", "content_html": '<img src="https://x.test/b.png" width="150">',
            "signature_html": "",
        }, timeout=60)
        tag = re.search(r"<img[^>]*b\.png[^>]*>", p.json()["email_html"]).group(0)
        assert "max-width:100%" in tag and "height:auto" in tag and "border:0" in tag

    def test_explicit_border_preserved_is_removed_but_border0_added(self, client):
        # A user-set border is dropped in favour of border:0 (documented behaviour check)
        p = client.post(f"{BASE_URL}/templates/preview", json={
            "subject": "s",
            "content_html": '<img src="https://x.test/c.png" style="border:2px solid red;height:40px">',
            "signature_html": "",
        }, timeout=60)
        tag = re.search(r"<img[^>]*c\.png[^>]*>", p.json()["email_html"]).group(0)
        assert "border:0" in tag
        assert "height:40px" in tag
        assert "height:auto" not in tag


# ---------- unit level ----------
class TestUnits:
    def test_build_variable_map_and_img_unit(self):
        from email_service import build_variable_map, _ensure_img_email_safe, substitute
        v = build_variable_map({"first_name": "A", "saudacao": "Exmo."})
        assert v["saudacao"] == "Exmo."
        assert substitute("{saudacao} {first_name}", v) == "Exmo. A"
        out = _ensure_img_email_safe('<img style="line-height:1.4;border-style:initial;width:120px">')
        assert "border-style" not in out and "border:0" in out and ";;" not in out
        # missing saudacao -> empty string, not KeyError
        assert build_variable_map({})["saudacao"] == ""


# ---------- regression ----------
class TestRegression:
    @pytest.mark.parametrize("path", [
        "/contacts", "/groups", "/templates", "/campaigns", "/dashboard",
        "/pipelines", "/deals", "/tasks", "/automations", "/settings", "/smtp",
    ])
    def test_core_endpoints_ok(self, client, path):
        r = client.get(f"{BASE_URL}{path}", timeout=30)
        assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:200]}"
        assert "_id" not in str(r.text)[:5000] or '"_id"' not in r.text
