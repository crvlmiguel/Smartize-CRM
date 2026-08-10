"""Iteration 15 — plain-text signature (signature_text) generation, persistence and preview usage."""
import os
import re

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")

EMAIL = "carlos.miguel@smartize.pt"
PASSWORD = "100%Smartize"

SIG_HTML = (
    '<table><tr><td><img src="https://x/logo.png" width="80"/></td>'
    '<td><div style="font-weight:bold">Carlos Santo</div>'
    '<div>Growth Manager- Smartize Portugal</div>'
    '<div>Phone: (+351) 968 537 603</div>'
    '<div>Email: <a href="mailto:carlos.santo@smartize.pt">carlos.santo@smartize.pt</a></div>'
    '<div><a href="https://www.smartize.pt">www.smartize.pt</a></div>'
    '</td></tr></table>'
)


@pytest.fixture(scope="session")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    if r.status_code != 200:
        pytest.fail(f"login failed {r.status_code}: {r.text[:300]}")
    token = r.json().get("token")
    assert token
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


# --- Requirement 1/5/6: improved converter, one info per line, no glued elements ---
class TestConverterPreview:
    def test_preview_plain_text_signature_lines(self, client):
        r = client.post(f"{BASE_URL}/api/templates/preview", json={
            "subject": "Ola {first_name}",
            "content_html": "",
            "content_text": "Ola {first_name},",
            "signature_html": SIG_HTML,
        })
        assert r.status_code == 200, r.text
        data = r.json()
        text = data["content_text"]
        print("PREVIEW TEXT:\n" + text)
        assert "<" not in text and ">" not in text, "HTML tags leaked into plain text"
        assert data["email_html"] == "", "plain-text template should not produce email_html"
        assert text.startswith("Ola João,")
        lines = [l for l in text.split("\n") if l.strip()]
        assert "Carlos Santo" in lines
        assert "Growth Manager- Smartize Portugal" in lines
        assert any(l.startswith("Phone:") for l in lines)
        assert any(l.startswith("Email:") for l in lines)
        assert any("www.smartize.pt" == l for l in lines)
        # no gluing
        assert "SantoGrowth" not in text
        assert "PortugalPhone" not in text
        assert "603Email" not in text
        assert "smartize.ptwww" not in text

    def test_preview_html_template_uses_html_signature(self, client):
        r = client.post(f"{BASE_URL}/api/templates/preview", json={
            "subject": "Oi",
            "content_html": "<p>Ola {first_name}, tudo bem?</p>",
            "content_text": "Ola {first_name},",
            "signature_html": SIG_HTML,
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["email_html"], "HTML template must produce email_html"
        assert "logo.png" in d["email_html"]
        assert "www.smartize.pt" in d["email_html"]
        assert "<a" in d["email_html"]


# --- Requirement: per-account signature_text persistence + preview fallback usage ---
class TestSignatureTextPersistence:
    def test_signature_text_crud_and_preview(self, client):
        r = client.get(f"{BASE_URL}/api/smtp")
        assert r.status_code == 200, r.text
        accounts = r.json()
        assert isinstance(accounts, list) and accounts, "no SMTP accounts seeded"
        acc = next((a for a in accounts if a.get("is_default")), accounts[0])
        assert "_id" not in acc, "raw mongo _id exposed"
        assert "id" in acc
        original_text = acc.get("signature_text", "")
        original_html = acc.get("signature_html", "")

        new_text = ("Carlos Santo\nGrowth Manager- Smartize Portugal\n"
                    "Phone: (+351) 968 537 603\nEmail: carlos.santo@smartize.pt\nwww.smartize.pt")
        up = client.put(f"{BASE_URL}/api/smtp/{acc['id']}",
                        json={"signature_text": new_text, "signature_html": SIG_HTML})
        assert up.status_code == 200, up.text

        # GET to verify persistence
        got = next(a for a in client.get(f"{BASE_URL}/api/smtp").json() if a["id"] == acc["id"])
        assert got["signature_text"] == new_text
        assert got["signature_html"] == SIG_HTML

        # Preview without signature_html in body -> uses account signature_text
        pr = client.post(f"{BASE_URL}/api/templates/preview", json={
            "subject": "S", "content_html": "", "content_text": "Ola {first_name},"})
        assert pr.status_code == 200, pr.text
        text = pr.json()["content_text"]
        print("PREVIEW (account sig_text):\n" + text)
        for line in new_text.split("\n"):
            assert line in text.split("\n"), f"missing line: {line}"

        # Clear signature_text -> preview falls back to converted HTML signature
        up2 = client.put(f"{BASE_URL}/api/smtp/{acc['id']}", json={"signature_text": ""})
        assert up2.status_code == 200, up2.text
        pr2 = client.post(f"{BASE_URL}/api/templates/preview", json={
            "subject": "S", "content_html": "", "content_text": "Ola {first_name},"})
        t2 = pr2.json()["content_text"]
        print("PREVIEW (fallback html_to_text):\n" + t2)
        lines2 = [l for l in t2.split("\n") if l.strip()]
        assert "Carlos Santo" in lines2
        assert any(l.startswith("Phone:") for l in lines2)
        assert "<" not in t2

        # restore
        rest = client.put(f"{BASE_URL}/api/smtp/{acc['id']}",
                          json={"signature_text": original_text, "signature_html": original_html})
        assert rest.status_code == 200


# --- Edge cases of the converter ---
class TestConverterEdgeCases:
    @pytest.mark.parametrize("sig,expected_lines", [
        ("<div>A</div><div>B</div>", ["A", "B"]),
        ("<p>A</p><p>B</p>", ["A", "B"]),
        ("<table><tr><td>A</td><td>B</td></tr></table>", ["A", "B"]),
        ("<span>A</span><br><span>B</span>", ["A", "B"]),
        ("<ul><li>A</li><li>B</li></ul>", ["A", "B"]),
        ("<style>.x{color:red}</style><div>A</div>", ["A"]),
        ("<div>A&nbsp;&amp;&nbsp;B</div>", ["A & B"]),
    ])
    def test_edge(self, client, sig, expected_lines):
        r = client.post(f"{BASE_URL}/api/templates/preview", json={
            "subject": "s", "content_html": "", "content_text": "X", "signature_html": sig})
        assert r.status_code == 200, r.text
        text = r.json()["content_text"]
        lines = [l for l in text.split("\n") if l.strip()]
        assert lines[0] == "X"
        assert lines[1:] == expected_lines, f"got {lines!r}"
        assert not re.search(r"<[^>]+>", text)

    def test_empty_signature_no_trailing_junk(self, client):
        r = client.post(f"{BASE_URL}/api/templates/preview", json={
            "subject": "s", "content_html": "", "content_text": "X", "signature_html": ""})
        assert r.status_code == 200
        assert r.json()["content_text"].strip() == "X"
