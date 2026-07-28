"""Iteration 5 — IMAP sync endpoint + IMAP fields persistence + secret hiding."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://campaign-manager-94.preview.emergentagent.com").rstrip("/")
EMAIL = "miguel.carvalho@smartize.pt"
PASSWORD = "100%Smartize"


@pytest.fixture(scope="module")
def client():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200, r.text
    tok = r.json()["token"]
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    yield s
    # cleanup TEST_iter5_ accounts
    for a in s.get(f"{BASE_URL}/api/smtp").json():
        if a["name"].startswith("TEST_iter5_"):
            s.delete(f"{BASE_URL}/api/smtp/{a['id']}")


class TestIter5ImapSync:
    _ids = {}

    def test_create_smtp_without_imap(self, client):
        r = client.post(f"{BASE_URL}/api/smtp", json={
            "name": "TEST_iter5_noimap", "account_type": "smtp",
            "from_email": "noimap@test.pt", "from_name": "N",
            "host": "smtp.example.com", "port": 587, "use_tls": True, "use_ssl": False,
            "username": "n@test.pt", "password": "pw",
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert not d.get("imap_host")
        # secrets never returned
        for k in ("password", "password_enc", "imap_password", "imap_password_enc"):
            assert k not in d
        TestIter5ImapSync._ids["noimap"] = d["id"]

    def test_create_smtp_with_imap_fields_persisted(self, client):
        r = client.post(f"{BASE_URL}/api/smtp", json={
            "name": "TEST_iter5_withimap", "account_type": "smtp",
            "from_email": "wi@test.pt", "from_name": "W",
            "host": "smtp.example.com", "port": 465, "use_ssl": True, "use_tls": False,
            "username": "wi@test.pt", "password": "smtppw",
            "imap_host": "imap.unreachable.invalid", "imap_port": 993,
            "imap_username": "wi@test.pt", "imap_password": "imappw",
        })
        assert r.status_code == 200, r.text
        d = r.json()
        # Persistence
        assert d["imap_host"] == "imap.unreachable.invalid"
        assert d["imap_port"] == 993
        assert d["imap_username"] == "wi@test.pt"
        # NEVER expose secrets
        for k in ("password", "password_enc", "imap_password", "imap_password_enc"):
            assert k not in d, f"leaked {k}"
        TestIter5ImapSync._ids["withimap"] = d["id"]

    def test_list_smtp_hides_secrets(self, client):
        r = client.get(f"{BASE_URL}/api/smtp")
        assert r.status_code == 200
        for s in r.json():
            for k in ("password", "password_enc", "imap_password", "imap_password_enc"):
                assert k not in s, f"leaked {k} on {s.get('name')}"

    def test_sync_imap_no_imap_configured_returns_400(self, client):
        sid = TestIter5ImapSync._ids["noimap"]
        r = client.post(f"{BASE_URL}/api/smtp/{sid}/sync-imap")
        assert r.status_code == 400
        j = r.json()
        # Portuguese message
        assert "IMAP" in (j.get("detail") or "")

    def test_sync_imap_unreachable_host_returns_400(self, client):
        sid = TestIter5ImapSync._ids["withimap"]
        r = client.post(f"{BASE_URL}/api/smtp/{sid}/sync-imap", timeout=60)
        assert r.status_code == 400, r.text
        j = r.json()
        assert "IMAP" in (j.get("detail") or "") or "Falha" in (j.get("detail") or "")
        # Verify imap_status persisted as 'error' but still no password leak
        acc = next(s for s in client.get(f"{BASE_URL}/api/smtp").json() if s["id"] == sid)
        assert acc.get("imap_status") == "error"
        for k in ("password", "password_enc", "imap_password", "imap_password_enc"):
            assert k not in acc

    def test_sync_imap_unknown_account_404(self, client):
        r = client.post(f"{BASE_URL}/api/smtp/507f1f77bcf86cd799439011/sync-imap")
        assert r.status_code == 404

    def test_sync_imap_bad_id_400(self, client):
        r = client.post(f"{BASE_URL}/api/smtp/notanid/sync-imap")
        assert r.status_code == 400

    def test_sync_imap_requires_auth(self):
        # Use one existing account id
        r = requests.post(f"{BASE_URL}/api/smtp/507f1f77bcf86cd799439011/sync-imap", timeout=30)
        assert r.status_code in (401, 403)

    def test_update_smtp_imap_password_empty_kept(self, client):
        sid = TestIter5ImapSync._ids["withimap"]
        r = client.put(f"{BASE_URL}/api/smtp/{sid}", json={"imap_host": "imap.other.invalid", "imap_password": ""})
        assert r.status_code == 200
        d = r.json()
        assert d["imap_host"] == "imap.other.invalid"
        for k in ("password", "password_enc", "imap_password", "imap_password_enc"):
            assert k not in d
