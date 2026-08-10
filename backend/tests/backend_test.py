"""Smartize Outreach backend regression tests."""
import io
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://campaign-manager-94.preview.emergentagent.com").rstrip("/")
EMAIL = "miguel.carvalho@smartize.pt"
PASSWORD = "100%Smartize"


@pytest.fixture(scope="session")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def client(token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return s


# ---------- Auth ----------
class TestAuth:
    def test_login_success(self):
        r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "token" in data and data["user"]["email"] == EMAIL

    def test_login_bad_credentials(self):
        r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": "wrong"}, timeout=30)
        assert r.status_code == 401

    def test_me_no_token(self):
        r = requests.get(f"{BASE_URL}/api/auth/me", timeout=30)
        assert r.status_code == 401

    def test_me_ok(self, client):
        r = client.get(f"{BASE_URL}/api/auth/me")
        assert r.status_code == 200
        assert r.json()["email"] == EMAIL


# ---------- Dashboard ----------
class TestDashboard:
    def test_dashboard_shape(self, client):
        r = client.get(f"{BASE_URL}/api/dashboard")
        assert r.status_code == 200
        d = r.json()
        assert "totals" in d and "recent_campaigns" in d and "daily" in d
        for k in ["contacts", "groups", "campaigns", "sent", "delivered", "opened", "clicked", "replied", "bounced"]:
            assert k in d["totals"]
        assert len(d["daily"]) == 14


# ---------- Groups ----------
class TestGroups:
    _created = {}

    def test_create_group(self, client):
        r = client.post(f"{BASE_URL}/api/groups", json={"name": "TEST_grupo_a", "description": "desc"})
        assert r.status_code == 200
        d = r.json()
        assert d["name"] == "TEST_grupo_a" and d["contact_count"] == 0
        TestGroups._created["id"] = d["id"]

    def test_list_groups(self, client):
        r = client.get(f"{BASE_URL}/api/groups")
        assert r.status_code == 200
        assert any(g["id"] == TestGroups._created["id"] for g in r.json())

    def test_update_group(self, client):
        gid = TestGroups._created["id"]
        r = client.put(f"{BASE_URL}/api/groups/{gid}", json={"name": "TEST_grupo_a2"})
        assert r.status_code == 200
        assert r.json()["name"] == "TEST_grupo_a2"


# ---------- Contacts ----------
class TestContacts:
    _created = {}

    def test_create_contact(self, client):
        gid = TestGroups._created["id"]
        r = client.post(f"{BASE_URL}/api/contacts", json={
            "email": "TEST_alice@example.com", "first_name": "Alice", "last_name": "Silva",
            "company": "AcmePT", "status": "ativo", "group_id": gid,
        })
        assert r.status_code == 200
        d = r.json()
        assert d["email"] == "test_alice@example.com"
        assert "password_enc" not in d
        TestContacts._created["id"] = d["id"]

    def test_create_contact_invalid_email(self, client):
        r = client.post(f"{BASE_URL}/api/contacts", json={"email": "notanemail"})
        assert r.status_code == 400

    def test_create_contact_duplicate(self, client):
        r = client.post(f"{BASE_URL}/api/contacts", json={"email": "TEST_alice@example.com"})
        assert r.status_code == 400

    def test_get_contact(self, client):
        r = client.get(f"{BASE_URL}/api/contacts/{TestContacts._created['id']}")
        assert r.status_code == 200

    def test_update_contact(self, client):
        r = client.put(f"{BASE_URL}/api/contacts/{TestContacts._created['id']}", json={"first_name": "Alicia"})
        assert r.status_code == 200
        assert r.json()["first_name"] == "Alicia"

    def test_search_and_filter(self, client):
        r = client.get(f"{BASE_URL}/api/contacts", params={"search": "Alicia", "group_id": TestGroups._created["id"]})
        assert r.status_code == 200
        assert len(r.json()) >= 1

    def test_import_csv(self, client, token):
        csv = "first_name,last_name,email,company\nBob,Costa,TEST_bob@example.com,AcmePT\nBad,Row,notemail,X\nDup,Ent,TEST_alice@example.com,AcmePT\nCarol,Dias,TEST_carol@example.com,AcmePT\n"
        files = {"file": ("contacts.csv", csv.encode(), "text/csv")}
        data = {"group_id": TestGroups._created["id"]}
        r = requests.post(f"{BASE_URL}/api/contacts/import", files=files, data=data,
                          headers={"Authorization": f"Bearer {token}"}, timeout=60)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["imported"] == 2 and j["duplicates"] == 1 and j["skipped"] == 1


# ---------- Templates ----------
class TestTemplates:
    _created = {}

    def test_create_template(self, client):
        r = client.post(f"{BASE_URL}/api/templates", json={
            "name": "TEST_tpl", "subject": "Olá {first_name}",
            "content_html": "<p>Olá {first_name} da {company}</p>", "content_text": "Olá {first_name}",
        })
        assert r.status_code == 200
        TestTemplates._created["id"] = r.json()["id"]

    def test_preview(self, client):
        r = client.post(f"{BASE_URL}/api/templates/preview", json={
            "subject": "Olá {first_name}", "content_html": "<p>{company}</p>", "content_text": "{first_name}",
        })
        assert r.status_code == 200
        d = r.json()
        assert "João" in d["subject"] and "Smartize" in d["content_html"]

    def test_duplicate(self, client):
        r = client.post(f"{BASE_URL}/api/templates/{TestTemplates._created['id']}/duplicate")
        assert r.status_code == 200
        assert "cópia" in r.json()["name"]


# ---------- SMTP ----------
class TestSmtp:
    _created = {}

    def test_create_smtp(self, client):
        r = client.post(f"{BASE_URL}/api/smtp", json={
            "name": "TEST_smtp", "from_email": "sender@test.pt", "from_name": "TEST",
            "host": "localhost", "port": 2525, "use_tls": False, "use_ssl": False,
            "username": "u", "password": "supersecret", "daily_limit": 100,
        })
        assert r.status_code == 200
        d = r.json()
        # password never returned
        assert "password" not in d and "password_enc" not in d
        TestSmtp._created["id"] = d["id"]

    def test_list_no_password(self, client):
        r = client.get(f"{BASE_URL}/api/smtp")
        assert r.status_code == 200
        for s in r.json():
            assert "password" not in s and "password_enc" not in s

    def test_update_smtp_keeps_password(self, client):
        sid = TestSmtp._created["id"]
        r = client.put(f"{BASE_URL}/api/smtp/{sid}", json={"name": "TEST_smtp2", "password": ""})
        assert r.status_code == 200
        assert r.json()["name"] == "TEST_smtp2"

    def test_create_smtp_with_signature_and_reply_to(self, client):
        r = client.post(f"{BASE_URL}/api/smtp", json={
            "name": "TEST_smtp_sig", "from_email": "sender2@test.pt", "from_name": "TEST2",
            "host": "smtp.hostinger.com", "port": 465, "use_ssl": True, "use_tls": False,
            "username": "u2", "password": "sekret2",
            "reply_to": "reply@test.pt",
            "signature_html": "<p><b>Test</b> Sig</p>",
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["reply_to"] == "reply@test.pt"
        assert d["signature_html"] == "<p><b>Test</b> Sig</p>"
        assert "password" not in d and "password_enc" not in d
        TestSmtp._created["sig_id"] = d["id"]

    def test_update_smtp_signature_persists(self, client):
        sid = TestSmtp._created["sig_id"]
        r = client.put(f"{BASE_URL}/api/smtp/{sid}", json={"signature_html": "<p>Updated</p>", "password": ""})
        assert r.status_code == 200
        assert r.json()["signature_html"] == "<p>Updated</p>"
        # verify persistence via list
        r2 = client.get(f"{BASE_URL}/api/smtp")
        found = next(s for s in r2.json() if s["id"] == sid)
        assert found["signature_html"] == "<p>Updated</p>"
        assert "password_enc" not in found

    def test_smtp_test_send_endpoint(self, client):
        sid = TestSmtp._created["sig_id"]
        r = client.post(f"{BASE_URL}/api/smtp/test-send", json={
            "smtp_account_id": sid, "to_email": "recv@test.pt",
            "signature_html": "<p>OverSig</p>",
        })
        assert r.status_code == 200
        j = r.json()
        assert "success" in j and "message" in j

    def test_smtp_test_send_invalid_email(self, client):
        sid = TestSmtp._created["sig_id"]
        r = client.post(f"{BASE_URL}/api/smtp/test-send", json={
            "smtp_account_id": sid, "to_email": "notanemail",
        })
        assert r.status_code == 400

    def test_smtp_test_endpoint(self, client):
        r = client.post(f"{BASE_URL}/api/smtp/test", json={
            "host": "127.0.0.1", "port": 1, "username": "u", "password": "p",
            "use_ssl": False, "use_tls": False,
        })
        # We expect the endpoint to respond (success or failure), not crash
        assert r.status_code == 200
        assert "success" in r.json() and "message" in r.json()


# ---------- Campaigns ----------
class TestCampaigns:
    _created = {}

    def test_create_campaign(self, client):
        payload = {
            "name": "TEST_camp", "smtp_account_id": TestSmtp._created["id"],
            "group_id": TestGroups._created["id"], "template_id": TestTemplates._created["id"],
            "min_interval_seconds": 1, "max_interval_seconds": 2,
            "business_days_only": False, "business_hour_start": 0, "business_hour_end": 23,
            "daily_send_limit": 50, "track_opens": True, "track_clicks": True,
        }
        r = client.post(f"{BASE_URL}/api/campaigns", json=payload)
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "rascunho"
        TestCampaigns._created["id"] = d["id"]

    def test_start_campaign(self, client):
        cid = TestCampaigns._created["id"]
        r = client.post(f"{BASE_URL}/api/campaigns/{cid}/start")
        assert r.status_code == 200, r.text
        assert r.json()["recipients"] >= 1

    def test_stats(self, client):
        cid = TestCampaigns._created["id"]
        r = client.get(f"{BASE_URL}/api/campaigns/{cid}/stats")
        assert r.status_code == 200
        d = r.json()
        assert "recipients" in d and "stats" in d
        assert len(d["recipients"]) >= 1

    def test_duplicate(self, client):
        cid = TestCampaigns._created["id"]
        r = client.post(f"{BASE_URL}/api/campaigns/{cid}/duplicate")
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "rascunho"
        TestCampaigns._created["dup_id"] = d["id"]

    def test_cancel(self, client):
        cid = TestCampaigns._created["id"]
        r = client.post(f"{BASE_URL}/api/campaigns/{cid}/cancel")
        assert r.status_code == 200

    def test_archive(self, client):
        cid = TestCampaigns._created["id"]
        r = client.post(f"{BASE_URL}/api/campaigns/{cid}/archive")
        assert r.status_code == 200

    def test_start_no_contacts_error(self, client):
        # Create empty group and campaign
        gr = client.post(f"{BASE_URL}/api/groups", json={"name": "TEST_empty", "description": ""})
        gid = gr.json()["id"]
        payload = {
            "name": "TEST_camp_empty", "smtp_account_id": TestSmtp._created["id"],
            "group_id": gid, "template_id": TestTemplates._created["id"],
            "min_interval_seconds": 1, "max_interval_seconds": 2,
            "business_days_only": False, "business_hour_start": 0, "business_hour_end": 23,
            "daily_send_limit": 50, "track_opens": True, "track_clicks": True,
        }
        r = client.post(f"{BASE_URL}/api/campaigns", json=payload)
        cid = r.json()["id"]
        r2 = client.post(f"{BASE_URL}/api/campaigns/{cid}/start")
        assert r2.status_code == 400
        client.delete(f"{BASE_URL}/api/campaigns/{cid}")
        client.delete(f"{BASE_URL}/api/groups/{gid}")


# ---------- Settings ----------
class TestSettings:
    def test_get_set_settings(self, client):
        r = client.get(f"{BASE_URL}/api/settings")
        assert r.status_code == 200
        data = r.json()
        # default_signature must not exist in settings anymore
        assert "default_signature" not in data
        try:
            r2 = client.put(f"{BASE_URL}/api/settings", json={"company_name": "TEST_Smartize", "timezone": "Europe/Lisbon"})
            assert r2.status_code == 200
            assert r2.json()["company_name"] == "TEST_Smartize"
            assert "default_signature" not in r2.json()
        finally:
            # restore so the test run does not leave TEST_ branding behind
            client.put(f"{BASE_URL}/api/settings", json={
                "company_name": data.get("company_name", "Smartize"),
                "timezone": data.get("timezone", "Europe/Lisbon"),
            })

    def test_settings_reject_default_signature(self, client):
        # SettingsUpdate should silently ignore unknown fields OR reject. Either way, must not persist default_signature.
        r = client.put(f"{BASE_URL}/api/settings", json={"default_signature": "<p>Nope</p>"})
        # should still succeed but not save default_signature
        assert r.status_code in (200, 422)
        if r.status_code == 200:
            assert "default_signature" not in r.json()


# ---------- Iteration 3: Branding + account_type + is_default/disconnect ----------
class TestIter3:
    _ids = {}

    def test_public_branding_no_auth(self):
        r = requests.get(f"{BASE_URL}/api/public/branding", timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "logo_url" in d and "company_name" in d
        assert isinstance(d["logo_url"], str) and isinstance(d["company_name"], str)

    def test_settings_save_logo_base64_and_branding_reflects(self, client):
        # snapshot original settings so this test does not pollute the environment
        original = client.get(f"{BASE_URL}/api/settings").json()
        tiny = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABAQMAAAAl21bKAAAAA1BMVEUAAACnej3aAAAAAXRSTlMAQObYZgAAAApJREFUCNdjYAAAAAIAAeIhvDMAAAAASUVORK5CYII="
        try:
            r = client.put(f"{BASE_URL}/api/settings", json={"logo_url": tiny, "company_name": "TEST_Smartize3"})
            assert r.status_code == 200
            assert r.json().get("logo_url") == tiny
            # public branding must expose it without auth
            pb = requests.get(f"{BASE_URL}/api/public/branding", timeout=30).json()
            assert pb["logo_url"] == tiny
            assert pb["company_name"] == "TEST_Smartize3"
        finally:
            client.put(f"{BASE_URL}/api/settings", json={
                "logo_url": original.get("logo_url", ""),
                "company_name": original.get("company_name", "Smartize"),
            })

    def test_create_google_account_defaults(self, client):
        # first, delete any TEST_ smtp so is_default assignment tests reliably
        r = client.post(f"{BASE_URL}/api/smtp", json={
            "name": "TEST_iter3_google", "account_type": "google",
            "from_email": "g@test.pt", "from_name": "G",
            "host": "smtp.gmail.com", "port": 465, "use_ssl": True, "use_tls": False,
            "username": "g@test.pt", "password": "app-pass-xyz",
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["account_type"] == "google"
        assert d.get("host") == "smtp.gmail.com" and d.get("port") == 465
        assert "password" not in d and "password_enc" not in d
        assert "imap_password" not in d and "imap_password_enc" not in d
        assert "is_default" in d and "connection_status" in d
        TestIter3._ids["google"] = d["id"]

    def test_create_smtp_custom_account(self, client):
        r = client.post(f"{BASE_URL}/api/smtp", json={
            "name": "TEST_iter3_custom", "account_type": "smtp",
            "from_email": "c@test.pt", "from_name": "C",
            "host": "smtp.hostinger.com", "port": 465, "use_ssl": True, "use_tls": False,
            "username": "c@test.pt", "password": "sekret",
            "imap_host": "imap.hostinger.com", "imap_port": 993,
            "imap_username": "c@test.pt", "imap_password": "imapsekret",
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["account_type"] == "smtp"
        assert "password_enc" not in d and "imap_password_enc" not in d
        assert d.get("imap_host") == "imap.hostinger.com"
        TestIter3._ids["custom"] = d["id"]

    def test_set_default_switches(self, client):
        gid = TestIter3._ids["google"]
        cid = TestIter3._ids["custom"]
        # set custom as default
        r = client.post(f"{BASE_URL}/api/smtp/{cid}/set-default")
        assert r.status_code == 200
        lst = client.get(f"{BASE_URL}/api/smtp").json()
        defaults = [s for s in lst if s.get("is_default")]
        assert len(defaults) == 1 and defaults[0]["id"] == cid
        # now switch to google
        r = client.post(f"{BASE_URL}/api/smtp/{gid}/set-default")
        assert r.status_code == 200
        lst = client.get(f"{BASE_URL}/api/smtp").json()
        defaults = [s for s in lst if s.get("is_default")]
        assert len(defaults) == 1 and defaults[0]["id"] == gid

    def test_disconnect_marks_status(self, client):
        cid = TestIter3._ids["custom"]
        r = client.post(f"{BASE_URL}/api/smtp/{cid}/disconnect")
        assert r.status_code == 200
        lst = client.get(f"{BASE_URL}/api/smtp").json()
        acc = next(s for s in lst if s["id"] == cid)
        assert acc.get("connection_status") == "disconnected"

    def test_campaign_uses_default_when_no_smtp_id(self, client):
        # ensure default is google
        gid = TestIter3._ids["google"]
        client.post(f"{BASE_URL}/api/smtp/{gid}/set-default")
        # need a group + template
        gr = client.post(f"{BASE_URL}/api/groups", json={"name": "TEST_iter3_grp"})
        group_id = gr.json()["id"]
        tp = client.post(f"{BASE_URL}/api/templates", json={
            "name": "TEST_iter3_tpl", "subject": "s", "content_html": "<p>h</p>", "content_text": "t"
        })
        tid = tp.json()["id"]
        r = client.post(f"{BASE_URL}/api/campaigns", json={
            "name": "TEST_iter3_camp_nosmtp",
            "group_id": group_id, "template_id": tid,
            "min_interval_seconds": 1, "max_interval_seconds": 2,
            "business_days_only": False, "business_hour_start": 0, "business_hour_end": 23,
            "daily_send_limit": 10, "track_opens": True, "track_clicks": True,
        })
        assert r.status_code == 200, r.text
        assert r.json()["smtp_account_id"] == gid
        # cleanup
        client.delete(f"{BASE_URL}/api/campaigns/{r.json()['id']}")
        client.delete(f"{BASE_URL}/api/templates/{tid}")
        client.delete(f"{BASE_URL}/api/groups/{group_id}")

    def test_smtp_list_hides_all_secrets(self, client):
        lst = client.get(f"{BASE_URL}/api/smtp").json()
        for s in lst:
            for k in ("password", "password_enc", "imap_password", "imap_password_enc"):
                assert k not in s, f"leak {k}"


# ---------- Signatures endpoint must be removed ----------
class TestSignaturesRemoved:
    def test_get_signatures_404(self, client):
        r = client.get(f"{BASE_URL}/api/signatures")
        assert r.status_code == 404

    def test_post_signatures_404(self, client):
        r = client.post(f"{BASE_URL}/api/signatures", json={"name": "x", "html": "<p/>"})
        assert r.status_code in (404, 405)


# ---------- Cleanup ----------
def test_zzz_cleanup(client):
    for c in client.get(f"{BASE_URL}/api/campaigns").json():
        if c["name"].startswith("TEST_") or "cópia" in c["name"]:
            client.delete(f"{BASE_URL}/api/campaigns/{c['id']}")
    for t in client.get(f"{BASE_URL}/api/templates").json():
        if t["name"].startswith("TEST_") or "cópia" in t["name"]:
            client.delete(f"{BASE_URL}/api/templates/{t['id']}")
    for s in client.get(f"{BASE_URL}/api/smtp").json():
        if s["name"].startswith("TEST_"):
            client.delete(f"{BASE_URL}/api/smtp/{s['id']}")
    for cont in client.get(f"{BASE_URL}/api/contacts").json():
        if cont["email"].startswith("test_"):
            client.delete(f"{BASE_URL}/api/contacts/{cont['id']}")
    for g in client.get(f"{BASE_URL}/api/groups").json():
        if g["name"].startswith("TEST_"):
            client.delete(f"{BASE_URL}/api/groups/{g['id']}")
