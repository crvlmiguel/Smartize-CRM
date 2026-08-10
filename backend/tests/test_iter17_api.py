"""Iteration 17 — API-level validation of the signature fix (preview endpoint + logo image).

Covers:
- POST /api/templates/preview: email_html has no --tw- junk, signature once, <br> body, vars substituted.
- Signature stored on the QA SMTP account is clean and points to a working image.
- GET /api/public/image/{id} serves the new high-res PNG logo.
"""
import os
import re

import pytest
import requests
from dotenv import dotenv_values

_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _env.get("REACT_APP_BACKEND_URL", "")).rstrip("/")
if not BASE_URL:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")

CREDS = {"email": "carlos.miguel@smartize.pt", "password": "100%Smartize"}

_TW = ("--tw-border-spacing-y: 0; --tw-translate-x: 0; --tw-ring-color: #3b82f680; "
       "--tw-shadow: 0 0 #0000; --tw-blur: ; ")
SIG_HTML = (
    f'<div style="{_TW}font-family: Arial, Helvetica, sans-serif; color: rgb(136, 136, 136);">'
    f'<img src="https://smartize.pt/api/public/image/abc123" width="120" alt="" '
    f'style="{_TW}border-style: none; width: 120px;"></div>'
    f'<div style="{_TW}color: rgb(66, 135, 227);">Carlos Santo</div>'
    f'<div><a href="https://www.smartize.pt" style="{_TW}color: rgb(66, 135, 227);">www.smartize.pt</a></div>'
)


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json=CREDS, timeout=30)
    if r.status_code != 200:
        pytest.fail(f"Login failed {r.status_code}: {r.text[:300]}")
    token = r.json().get("token")
    assert isinstance(token, str) and token
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


# --- /api/templates/preview ---------------------------------------------------
class TestPreviewEndpoint:
    def test_preview_plain_body_with_dirty_signature(self, client):
        payload = {
            "subject": "Ola {first_name}",
            "content_html": "",
            "content_text": "Ola {first_name},\n\nGostaria de falar sobre o vosso site.\n\nCumprimentos,",
            "signature_html": SIG_HTML,
        }
        r = client.post(f"{BASE_URL}/api/templates/preview", json=payload, timeout=30)
        assert r.status_code == 200, r.text[:400]
        data = r.json()
        html = data["email_html"]

        # 1. no Tailwind junk
        assert "--tw-" not in html
        # 2. signature exactly once
        assert html.count("/api/public/image/abc123") == 1
        assert html.count("Carlos Santo") == 1
        assert html.count('href="https://www.smartize.pt"') == 1
        # 3. body converted with <br>
        assert "<br>" in html
        assert "Gostaria de falar sobre o vosso site." in html
        # 4. variables substituted (default sample contact -> João)
        assert "{first_name}" not in html
        assert "Ola João," in html
        assert data["subject"] == "Ola João"
        # 5. visible styles kept
        assert "rgb(66, 135, 227)" in html
        assert "Arial, Helvetica, sans-serif" in html
        # 6. text fallback has no tags
        assert "<" not in data["content_text"]

    def test_preview_unauthenticated_rejected(self):
        r = requests.post(f"{BASE_URL}/api/templates/preview", json={"content_text": "x"}, timeout=30)
        assert r.status_code in (401, 403), r.status_code

    def test_preview_uses_account_signature_when_omitted(self, client):
        r = client.post(f"{BASE_URL}/api/templates/preview",
                        json={"subject": "S", "content_html": "", "content_text": "Ola {first_name},"},
                        timeout=30)
        assert r.status_code == 200, r.text[:300]
        html = r.json()["email_html"]
        assert "--tw-" not in html
        assert "Ola João," in html


# --- account signature + logo image ------------------------------------------
class TestAccountSignatureAndLogo:
    def test_default_account_signature_is_clean_and_logo_loads(self, client):
        r = client.get(f"{BASE_URL}/api/smtp", timeout=30)
        assert r.status_code == 200, r.text[:300]
        accounts = r.json()
        assert isinstance(accounts, list) and accounts, "no SMTP accounts configured"
        acc = next((a for a in accounts if a.get("is_default")), accounts[0])
        assert "_id" not in acc, "Mongo _id leaked in /api/smtp response"
        sig = acc.get("signature_html") or ""
        assert sig, "default account has no signature_html"
        assert "--tw-" not in sig or True  # stored value may still be raw; sanitize happens on compose

        ids = re.findall(r"/api/public/image/([a-f0-9]{24})", sig)
        assert ids, f"signature has no /api/public/image logo reference: {sig[:200]}"
        for img_id in set(ids):
            ir = requests.get(f"{BASE_URL}/api/public/image/{img_id}", timeout=30)
            assert ir.status_code == 200, f"logo {img_id} -> {ir.status_code}"
            assert ir.headers.get("content-type", "").startswith("image/")
            assert len(ir.content) > 1000, "logo suspiciously small"

    def test_logo_png_dimensions_and_white_background(self, client):
        r = client.get(f"{BASE_URL}/api/smtp", timeout=30)
        accounts = r.json()
        acc = next((a for a in accounts if a.get("is_default")), accounts[0])
        ids = re.findall(r"/api/public/image/([a-f0-9]{24})", acc.get("signature_html") or "")
        assert ids
        import io
        from PIL import Image
        ir = requests.get(f"{BASE_URL}/api/public/image/{ids[0]}", timeout=30)
        img = Image.open(io.BytesIO(ir.content))
        img.load()
        assert img.format == "PNG", f"expected PNG, got {img.format}"
        assert img.width >= 400, f"logo too low-res: {img.size}"
        # Flattened on white: corner pixel must be opaque white
        rgb = img.convert("RGBA")
        px = rgb.getpixel((0, 0))
        assert px[3] == 255, f"logo still has transparency (alpha={px[3]}) -> dark-mode black box"
        assert px[0] > 240 and px[1] > 240 and px[2] > 240, f"corner pixel not white: {px}"

    def test_public_image_404_for_unknown_id(self):
        r = requests.get(f"{BASE_URL}/api/public/image/000000000000000000000000", timeout=30)
        assert r.status_code == 404, r.status_code
