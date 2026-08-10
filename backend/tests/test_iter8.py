"""Iteration 8 backend tests: image uploads, email-safe HTML preview, plain text, contact import (preview + mapping)."""
import io
import json
import os
import re

import pytest
import requests
from dotenv import dotenv_values
from PIL import Image

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE = base_url.rstrip("/") + "/api"

EMAIL_PREFIX = "qa_imp_iter8_"


def _png_bytes(w=400, h=120, color=(20, 120, 220)):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(scope="module")
def creds():
    content = open("/app/memory/test_credentials.md", encoding="utf-8").read()
    assert "carlos.miguel@smartize.pt" in content
    return {"email": "carlos.miguel@smartize.pt", "password": "100%Smartize"}


@pytest.fixture(scope="module")
def client(creds):
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json=creds, timeout=30)
    if r.status_code != 200:
        pytest.fail(f"Login failed {r.status_code}: {r.text[:300]}")
    token = r.json().get("token")
    assert token
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module", autouse=True)
def cleanup(client):
    yield
    # remove any contacts created by the import tests
    r = client.get(f"{BASE}/contacts?limit=1000", timeout=30)
    if r.status_code == 200:
        data = r.json()
        items = data if isinstance(data, list) else data.get("items", [])
        for c in items:
            if str(c.get("email", "")).startswith(EMAIL_PREFIX):
                client.delete(f"{BASE}/contacts/{c['id']}", timeout=30)
    # remove test templates
    r = client.get(f"{BASE}/templates", timeout=30)
    if r.status_code == 200:
        for t in r.json():
            if str(t.get("name", "")).startswith("TEST_"):
                client.delete(f"{BASE}/templates/{t['id']}", timeout=30)
    # remove test campaigns/groups
    r = client.get(f"{BASE}/campaigns", timeout=30)
    if r.status_code == 200:
        for c in r.json():
            if str(c.get("name", "")).startswith("TEST_"):
                client.delete(f"{BASE}/campaigns/{c['id']}", timeout=30)
    r = client.get(f"{BASE}/groups", timeout=30)
    if r.status_code == 200:
        for g in r.json():
            if str(g.get("name", "")).startswith("TEST_"):
                client.delete(f"{BASE}/groups/{g['id']}", timeout=30)


# ==================== Auth basics ====================
class TestAuth:
    def test_login_and_me(self, client, creds):
        r = client.get(f"{BASE}/auth/me", timeout=30)
        assert r.status_code == 200
        assert r.json()["email"] == creds["email"]

    def test_bcrypt_hash_format(self):
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient
        env = dotenv_values("/app/backend/.env")

        async def run():
            cl = AsyncIOMotorClient(env["MONGO_URL"])
            u = await cl[env["DB_NAME"]].users.find_one({"email": "carlos.miguel@smartize.pt"})
            cl.close()
            return u
        u = asyncio.run(run())
        assert u is not None
        h = u.get("password_hash") or u.get("password") or ""
        assert h.startswith("$2b$") or h.startswith("$2a$"), f"unexpected hash prefix: {h[:6]}"


# ==================== Uploads ====================
class TestUploads:
    def test_upload_image_returns_url_and_size(self, client):
        files = {"file": ("logo.png", _png_bytes(400, 120), "image/png")}
        r = client.post(f"{BASE}/uploads/image", files=files, timeout=60)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        assert "url" in data and data["width"] == 400 and data["height"] == 120
        assert "/api/public/image/" in data["url"]
        assert data["url"].startswith("http"), f"url not absolute: {data['url']}"

    def test_public_image_served_without_auth(self, client):
        files = {"file": ("logo.png", _png_bytes(300, 100), "image/png")}
        url = client.post(f"{BASE}/uploads/image", files=files, timeout=60).json()["url"]
        r = requests.get(url, timeout=30)  # no auth header
        assert r.status_code == 200, r.text[:200]
        assert r.headers.get("content-type", "").startswith("image/")
        assert len(r.content) > 100
        assert Image.open(io.BytesIO(r.content)).size == (300, 100)

    def test_upload_downscales_wide_image(self, client):
        files = {"file": ("wide.png", _png_bytes(2400, 600), "image/png")}
        r = client.post(f"{BASE}/uploads/image", files=files, timeout=90)
        assert r.status_code == 200
        d = r.json()
        assert d["width"] == 1600 and d["height"] == 400

    def test_upload_rejects_non_image(self, client):
        files = {"file": ("a.txt", b"not an image", "text/plain")}
        r = client.post(f"{BASE}/uploads/image", files=files, timeout=30)
        assert r.status_code == 400, r.status_code

    def test_public_image_bad_id(self):
        r = requests.get(f"{BASE}/public/image/000000000000000000000000", timeout=30)
        assert r.status_code == 404, r.status_code

    def test_uploads_image_requires_auth(self):
        files = {"file": ("logo.png", _png_bytes(50, 50), "image/png")}
        r = requests.post(f"{BASE}/uploads/image", files=files, timeout=30)
        assert r.status_code in (401, 403), r.status_code


# ==================== Templates preview (email-safe HTML) ====================
class TestTemplatePreview:
    def test_preview_returns_email_safe_html(self, client):
        body = {
            "subject": "Olá {{first_name}}",
            "content_html": "<p>Olá {{first_name}} da {{company}}</p>",
            "content_text": "Olá {{first_name}}",
            "signature_html": '<p>Cumprimentos<br/><img src="https://x/y.png" width="180"></p>',
        }
        r = client.post(f"{BASE}/templates/preview", json=body, timeout=30)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["subject"] == "Olá João"
        assert "João" in d["content_html"] and "Smartize" in d["content_html"]
        html = d["email_html"]
        assert html.lower().startswith("<!doctype html>")
        # iter12: natural email — no container table/card
        assert "<table" not in html.lower() and 'width="600"' not in html
        assert "max-width:600px" not in html
        assert "background-color" not in html.lower()
        # signature integrated + img made email safe
        assert "Cumprimentos" in html
        img = re.search(r"<img[^>]*y\.png[^>]*>", html)
        assert img, "signature image missing in email_html"
        assert "max-width:100%" in img.group(0) and "height:auto" in img.group(0)

    def test_preview_falls_back_to_default_account_signature(self, client):
        accounts = client.get(f"{BASE}/smtp", timeout=30).json()
        sig = ""
        for a in accounts:
            if a.get("is_default"):
                sig = a.get("signature_html") or ""
        r = client.post(f"{BASE}/templates/preview",
                        json={"subject": "s", "content_html": "<p>corpo</p>"}, timeout=30)
        assert r.status_code == 200
        html = r.json()["email_html"]
        if sig:
            snippet = re.sub(r"<[^>]+>", "", sig).strip()[:12]
            if snippet:
                assert snippet in re.sub(r"<[^>]+>", "", html), "default account signature not injected"

    def test_preview_uses_text_when_no_html(self, client):
        r = client.post(f"{BASE}/templates/preview",
                        json={"subject": "s", "content_text": "linha1\nlinha2"}, timeout=30)
        assert r.status_code == 200
        # iter16: text-only template also gets an HTML alternative (natural <br> body)
        assert "linha1<br>" in r.json()["email_html"]
        assert r.json()["content_text"].startswith("linha1\nlinha2")

    def test_preview_requires_auth(self):
        r = requests.post(f"{BASE}/templates/preview", json={"subject": "x"}, timeout=30)
        assert r.status_code in (401, 403)


# ==================== Plain text persistence ====================
class TestTemplatePlainText:
    def test_create_template_with_text_persists(self, client):
        payload = {"name": "TEST_iter8_tpl", "subject": "Assunto {{first_name}}",
                   "content_html": "<p>Olá <img src='https://x/z.png' width='120'></p>",
                   "content_text": "Olá\nPlain text preservado"}
        r = client.post(f"{BASE}/templates", json=payload, timeout=30)
        assert r.status_code == 200, r.text[:300]
        tid = r.json()["id"]
        assert r.json()["content_text"] == payload["content_text"]
        lst = client.get(f"{BASE}/templates", timeout=30).json()
        found = [t for t in lst if t["id"] == tid]
        assert found, "template not listed"
        assert found[0]["content_text"] == payload["content_text"]
        assert "_id" not in found[0]


# ==================== Contact import ====================
CSV_HEADER = "first_name,last_name,email,company,job_title,phone\n"


def _csv(rows):
    return (CSV_HEADER + "".join(rows)).encode()


class TestImport:
    def test_preview_counts_and_mapping(self, client):
        rows = [
            f"Ana,Silva,{EMAIL_PREFIX}a@example.com,ACME,Diretora,912345678\n",
            f"Bruno,Costa,{EMAIL_PREFIX}b@example.com,Beta,CTO,912345679\n",
            f"Ana,Silva,{EMAIL_PREFIX}a@example.com,ACME,Diretora,912345678\n",  # duplicate in file
            ",,semmail,Gamma,CEO,\n",                                              # invalid email
            f",,{EMAIL_PREFIX}c@example.com,Delta,Dev,\n",                        # incomplete name
        ]
        files = {"file": ("c.csv", _csv(rows), "text/csv")}
        r = client.post(f"{BASE}/contacts/import/preview", files=files, timeout=60)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d["counts"] == {"total": 5, "valid": 3, "invalid": 1, "duplicates": 1, "incomplete": 1}, d["counts"]
        assert d["mapping"]["email"] == "email"
        assert d["mapping"]["position"] == "job_title"
        assert d["mapping"]["first_name"] == "first_name"
        assert d["has_email_column"] is True
        assert d["unknown_columns"] == []
        assert len(d["sample"]) == 3

    def test_preview_unknown_columns(self, client):
        content = b"email,notas_extra,foo\n" + f"{EMAIL_PREFIX}u@example.com,abc,1\n".encode()
        r = client.post(f"{BASE}/contacts/import/preview",
                        files={"file": ("u.csv", content, "text/csv")}, timeout=60)
        assert r.status_code == 200
        d = r.json()
        assert set(d["unknown_columns"]) == {"notas_extra", "foo"}

    def test_preview_no_email_column(self, client):
        content = b"nome,empresa\nAna,ACME\n"
        r = client.post(f"{BASE}/contacts/import/preview",
                        files={"file": ("n.csv", content, "text/csv")}, timeout=60)
        assert r.status_code == 200
        d = r.json()
        assert d["has_email_column"] is False
        assert d["counts"]["valid"] == 0 and d["counts"]["invalid"] == 1

    def test_import_with_mapping_creates_contacts(self, client):
        rows = [
            f"Carla,Dias,{EMAIL_PREFIX}map1@example.com,ACME,Gestora,912000001\n",
            f"Duarte,Reis,{EMAIL_PREFIX}map2@example.com,Beta,Analista,912000002\n",
            ",,bademail,Gamma,X,\n",
            f"Carla,Dias,{EMAIL_PREFIX}map1@example.com,ACME,Gestora,912000001\n",
        ]
        mapping = {"first_name": "first_name", "last_name": "last_name", "email": "email",
                   "company": "company", "position": "job_title", "phone": "phone"}
        r = client.post(f"{BASE}/contacts/import",
                        files={"file": ("m.csv", _csv(rows), "text/csv")},
                        data={"mapping": json.dumps(mapping), "group_id": ""}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        assert d == {"imported": 2, "skipped": 1, "duplicates": 1}, d
        lst = client.get(f"{BASE}/contacts?search={EMAIL_PREFIX}map1", timeout=30).json()
        items = lst if isinstance(lst, list) else lst.get("items", [])
        c = [x for x in items if x["email"] == f"{EMAIL_PREFIX}map1@example.com"]
        assert c, "imported contact not persisted"
        assert c[0]["first_name"] == "Carla"
        assert c[0]["position"] == "Gestora", c[0]
        assert c[0]["company"] == "ACME"

    def test_import_respects_manual_mapping(self, client):
        # deliberately map company -> job_title column
        rows = [f"Elsa,Nunes,{EMAIL_PREFIX}manual@example.com,IgnoredCo,ManualValue,912000003\n"]
        mapping = {"first_name": "first_name", "email": "email", "company": "job_title"}
        r = client.post(f"{BASE}/contacts/import",
                        files={"file": ("mm.csv", _csv(rows), "text/csv")},
                        data={"mapping": json.dumps(mapping)}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        assert r.json()["imported"] == 1
        lst = client.get(f"{BASE}/contacts?search={EMAIL_PREFIX}manual", timeout=30).json()
        items = lst if isinstance(lst, list) else lst.get("items", [])
        c = [x for x in items if x["email"] == f"{EMAIL_PREFIX}manual@example.com"][0]
        assert c["company"] == "ManualValue", c
        assert c["position"] == ""
        assert c["last_name"] == ""

    def test_import_without_email_mapping_rejected(self, client):
        rows = [f"Fabio,Lima,{EMAIL_PREFIX}noemail@example.com,ACME,X,\n"]
        r = client.post(f"{BASE}/contacts/import",
                        files={"file": ("ne.csv", _csv(rows), "text/csv")},
                        data={"mapping": json.dumps({"first_name": "first_name"})}, timeout=60)
        # mapping without email should not silently fall back and import
        assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text[:200]}"


# ==================== Email-safe sending pipeline ====================
class TestSendPipeline:
    def test_campaign_start_creates_jobs(self, client):
        g = client.post(f"{BASE}/groups", json={"name": "TEST_iter8_grp"}, timeout=30)
        assert g.status_code == 200, g.text[:200]
        gid = g.json()["id"]
        c = client.post(f"{BASE}/contacts", json={
            "first_name": "Ivo", "last_name": "Q", "email": f"{EMAIL_PREFIX}camp@example.com",
            "group_id": gid}, timeout=30)
        assert c.status_code == 200, c.text[:200]
        t = client.post(f"{BASE}/templates", json={
            "name": "TEST_iter8_camp_tpl", "subject": "Olá {{first_name}}",
            "content_html": "<p>Corpo</p>", "content_text": "Corpo"}, timeout=30)
        tid = t.json()["id"]
        camp = client.post(f"{BASE}/campaigns", json={
            "name": "TEST_iter8_camp", "group_id": gid, "template_id": tid}, timeout=30)
        assert camp.status_code == 200, camp.text[:300]
        cid = camp.json()["id"]
        r = client.post(f"{BASE}/campaigns/{cid}/start", timeout=60)
        assert r.status_code == 200, r.text[:300]
        assert r.json()["recipients"] == 1
        got = client.get(f"{BASE}/campaigns/{cid}", timeout=30).json()
        assert got["status"] == "sending"
        stats = client.get(f"{BASE}/campaigns/{cid}/stats", timeout=30)
        assert stats.status_code == 200
        client.post(f"{BASE}/campaigns/{cid}/cancel", timeout=30)

    def test_compose_email_html_unit(self):
        import sys
        sys.path.insert(0, "/app/backend")
        from email_service import compose_email_html
        html = compose_email_html('<p>x</p><img src="a.png" width="200">', "<p>sig</p>")
        # iter12: no 600px container wrapper anymore
        assert 'width="600"' not in html and "<!DOCTYPE html>" in html
        assert "max-width:100%" in html and "sig" in html
        assert html.count("<!DOCTYPE html>") == 1
