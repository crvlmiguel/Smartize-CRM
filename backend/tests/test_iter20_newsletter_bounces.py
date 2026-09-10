"""Iteration 20: Newsletter HTML templates + Bounces page endpoint."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback: read from frontend/.env
    try:
        with open("/app/frontend/.env") as fh:
            for line in fh:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                    break
    except Exception:
        pass

LOGIN_EMAIL = "carlos.miguel@smartize.pt"
LOGIN_PASSWORD = "100%Smartize"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": LOGIN_EMAIL, "password": LOGIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    tok = r.json().get("token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ---------- Templates: HTML type ----------
class TestTemplateHtml:
    created_id = None

    def test_create_html_template_persists_type(self, headers):
        payload = {
            "name": "TEST_newsletter_iter20",
            "subject": "Olá {{first_name}}",
            "content_html": "<div><h1>Hi {{first_name}}</h1><p>Body</p></div>",
            "content_text": "",
            "type": "html",
        }
        r = requests.post(f"{BASE_URL}/api/templates", json=payload, headers=headers, timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["type"] == "html"
        assert data["name"] == payload["name"]
        assert "id" in data
        TestTemplateHtml.created_id = data["id"]

        # GET back to verify persistence
        r2 = requests.get(f"{BASE_URL}/api/templates/{data['id']}", headers=headers, timeout=10)
        assert r2.status_code == 200
        assert r2.json()["type"] == "html"
        assert r2.json()["content_html"] == payload["content_html"]

    def test_preview_html_returns_exact_html_no_wrapper(self, headers):
        html = "<div style='color:red'>Olá {{first_name}}</div>"
        r = requests.post(f"{BASE_URL}/api/templates/preview",
                          json={"subject": "S", "content_html": html, "type": "html"},
                          headers=headers, timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()
        # email_html should equal content_html after variable substitution (no wrapper/signature)
        expected = "<div style='color:red'>Olá João</div>"
        assert data["email_html"] == expected, f"Got: {data['email_html']!r}"
        assert data["content_html"] == expected
        # No signature or wrapper added
        assert "signature" not in data["email_html"].lower()
        assert "<html" not in data["email_html"].lower()
        assert "<body" not in data["email_html"].lower()

    def test_preview_plain_wraps_with_signature(self, headers):
        # plain type: email_html should be wrapped (compose_email_html adds <html>/<body>)
        r = requests.post(f"{BASE_URL}/api/templates/preview",
                          json={"subject": "S", "content_text": "Olá {{first_name}}", "type": "plain"},
                          headers=headers, timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()
        html = data["email_html"]
        # For plain, the composed html is a full document (contains DOCTYPE or html tag)
        assert "<html" in html.lower() or "<body" in html.lower() or "<!doctype" in html.lower(), \
            f"Plain preview should have wrapper: {html[:200]}"

    def test_test_send_endpoint_reachable(self, headers):
        # SMTP is fictional in preview; endpoint should respond 200 with success:false OR 400 if no SMTP
        payload = {
            "to_email": "someone@example.com",
            "subject": "Teste",
            "content_html": "<p>Olá {{first_name}}</p>",
            "type": "html",
        }
        r = requests.post(f"{BASE_URL}/api/templates/test-send", json=payload, headers=headers, timeout=30)
        # accept 200 (with success flag) or 400 if no SMTP configured
        assert r.status_code in (200, 400), r.text
        if r.status_code == 200:
            body = r.json()
            assert "success" in body
            assert "message" in body

    def test_test_send_invalid_email(self, headers):
        r = requests.post(f"{BASE_URL}/api/templates/test-send",
                          json={"to_email": "not-an-email", "subject": "x",
                                "content_html": "<p>x</p>", "type": "html"},
                          headers=headers, timeout=10)
        assert r.status_code == 400

    def test_cleanup_html_template(self, headers):
        if TestTemplateHtml.created_id:
            r = requests.delete(f"{BASE_URL}/api/templates/{TestTemplateHtml.created_id}",
                                headers=headers, timeout=10)
            assert r.status_code == 200


# ---------- Templates: plain (no regression) ----------
class TestTemplatePlainNoRegression:
    def test_create_plain_template_default_type(self, headers):
        payload = {"name": "TEST_plain_iter20", "subject": "Ola", "content_text": "Ola {{first_name}}"}
        r = requests.post(f"{BASE_URL}/api/templates", json=payload, headers=headers, timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data.get("type") == "plain"  # default
        tid = data["id"]
        # cleanup
        requests.delete(f"{BASE_URL}/api/templates/{tid}", headers=headers, timeout=10)


# ---------- Bounces endpoint ----------
class TestBouncesEndpoint:
    def test_get_bounces_returns_list(self, headers):
        r = requests.get(f"{BASE_URL}/api/bounces", headers=headers, timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        # If any bounces exist, they should have enriched fields
        for b in data[:3]:
            assert "campaign_name" in b
            assert "contact_name" in b
            assert "_id" not in b  # ObjectId excluded
            assert "id" in b

    def test_get_bounces_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/bounces", timeout=10)
        assert r.status_code in (401, 403)
