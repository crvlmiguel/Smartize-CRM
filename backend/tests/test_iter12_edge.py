"""Iteration 12 edge cases: 'visually empty' HTML from the rich text editor must be
treated as no-HTML so that plain-text templates are actually sent as plain text."""
import os
import sys

import pytest
import requests
from dotenv import dotenv_values

sys.path.insert(0, "/app/backend")

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
BASE_URL = base_url.rstrip("/") + "/api"

EMAIL = "carlos.miguel@smartize.pt"
PASSWORD = "100%Smartize"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    if r.status_code != 200:
        pytest.fail(f"Login failed {r.status_code}: {r.text[:300]}")
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
    return s


@pytest.mark.parametrize("empty_html", ["<br>", "<p><br></p>", "<div><br></div>", "<p>&nbsp;</p>", "<br><br>"])
def test_visually_empty_html_should_fall_back_to_plain_text(client, empty_html):
    r = client.post(f"{BASE_URL}/templates/preview", json={
        "subject": "s", "content_html": empty_html,
        "content_text": "Olá {first_name},\n\nAbraço",
    }, timeout=30)
    assert r.status_code == 200, r.text
    eh = r.json()["email_html"]
    # iter16: visually-empty HTML falls back to the plain-text body converted to natural HTML
    assert "Olá João,<br>" in eh, (
        f"content_html={empty_html!r} should fall back to the plain-text body: {eh[:300]}"
    )
