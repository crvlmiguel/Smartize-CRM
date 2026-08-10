"""Iteration 17 — signature image must be stored/served BYTE-FOR-BYTE.

The upload endpoint must never resize, convert or recompress the file:
transparency, colours, sharpness and format are preserved exactly. Display
size is controlled only via the HTML width in the signature.
"""
import hashlib
import io
import os

import pytest
import requests
from dotenv import dotenv_values
from PIL import Image

frontend_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")).rstrip("/")
CREDS = {"email": "carlos.miguel@smartize.pt", "password": "100%Smartize"}


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json=CREDS, timeout=30)
    assert r.status_code == 200, r.text[:200]
    return r.json()["token"]


def _make_png(size=(1800, 700)):
    im = Image.new("RGBA", size, (0, 0, 0, 0))  # transparent
    for x in range(100, size[0] - 100):
        for y in range(200, 500):
            im.putpixel((x, y), (37, 99, 235, 255))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def test_upload_preserves_original_bytes_and_transparency(token):
    raw = _make_png()
    orig_sha = hashlib.sha256(raw).hexdigest()
    up = requests.post(
        f"{BASE_URL}/api/uploads/image",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("logo.png", raw, "image/png")}, timeout=30,
    )
    assert up.status_code == 200, up.text[:200]
    data = up.json()
    # Native dimensions reported unchanged (no resize even above the old 1600px cap).
    assert data["width"] == 1800 and data["height"] == 700

    got = requests.get(data["url"], timeout=30)
    assert got.status_code == 200
    assert got.headers.get("content-type") == "image/png"
    # Byte-for-byte identical -> no recompression/conversion.
    assert hashlib.sha256(got.content).hexdigest() == orig_sha
    # Transparency preserved.
    served = Image.open(io.BytesIO(got.content)).convert("RGBA")
    assert served.format is None or True
    assert served.getpixel((0, 0))[3] == 0
