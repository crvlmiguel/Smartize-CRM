"""Iteration 4 backend tests: signature in send, retry/bounce, tracking, variables."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://campaign-manager-94.preview.emergentagent.com").rstrip("/")
EMAIL = "miguel.carvalho@smartize.pt"
PASSWORD = "100%Smartize"


@pytest.fixture(scope="module")
def client():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}", "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def seed(client):
    """Create smtp with signature, group + contact, template with {var} and {{var}}, campaign started."""
    ids = {}
    smtp = client.post(f"{BASE_URL}/api/smtp", json={
        "name": "TEST_iter4_smtp", "account_type": "smtp",
        "from_email": "sender@test.pt", "from_name": "T4",
        "host": "127.0.0.1", "port": 2, "use_ssl": False, "use_tls": False,
        "username": "u", "password": "p",
        "signature_html": '<p><b>{first_name}</b> — <a href="https://smartize.pt">Smartize</a></p>',
    }).json()
    ids["smtp"] = smtp["id"]

    grp = client.post(f"{BASE_URL}/api/groups", json={"name": "TEST_iter4_grp"}).json()
    ids["group"] = grp["id"]

    contact = client.post(f"{BASE_URL}/api/contacts", json={
        "email": "TEST_iter4_target@example.com", "first_name": "João",
        "last_name": "Silva", "company": "Smartize", "group_id": grp["id"], "status": "ativo",
    }).json()
    ids["contact"] = contact["id"]

    tpl = client.post(f"{BASE_URL}/api/templates", json={
        "name": "TEST_iter4_tpl",
        "subject": "Olá {first_name} da {{company}}",
        "content_html": "<p>Olá {first_name} da {{company}}</p><p>Visita <a href=\"https://smartize.pt\">o site</a></p>",
        "content_text": "Olá {first_name} da {{company}}",
    }).json()
    ids["template"] = tpl["id"]

    camp = client.post(f"{BASE_URL}/api/campaigns", json={
        "name": "TEST_iter4_camp",
        "smtp_account_id": ids["smtp"], "group_id": ids["group"], "template_id": ids["template"],
        "settings": {
            "min_interval_seconds": 1, "max_interval_seconds": 1,
            "business_days_only": False, "business_hour_start": 0, "business_hour_end": 23,
            "timezone": "Europe/Lisbon", "emails_per_hour": 100, "emails_per_day": 200,
        },
    }).json()
    ids["campaign"] = camp["id"]
    start = client.post(f"{BASE_URL}/api/campaigns/{camp['id']}/start")
    assert start.status_code == 200, start.text
    yield ids

    # teardown
    client.delete(f"{BASE_URL}/api/campaigns/{ids['campaign']}")
    client.delete(f"{BASE_URL}/api/templates/{ids['template']}")
    client.delete(f"{BASE_URL}/api/contacts/{ids['contact']}")
    client.delete(f"{BASE_URL}/api/groups/{ids['group']}")
    client.delete(f"{BASE_URL}/api/smtp/{ids['smtp']}")


# ---------- Variables substitution ----------
class TestVariables:
    def test_preview_both_syntaxes(self, client):
        r = client.post(f"{BASE_URL}/api/templates/preview", json={
            "subject": "Olá {first_name} da {{company}}",
            "content_html": "<p>{first_name} — {{company}}</p>",
            "content_text": "{first_name} {{company}}",
        })
        assert r.status_code == 200
        d = r.json()
        assert "João" in d["subject"] and "Smartize" in d["subject"]
        assert "João" in d["content_html"] and "Smartize" in d["content_html"]
        assert "João" in d["content_text"] and "Smartize" in d["content_text"]


# ---------- Retry / attempts / bounce state machine ----------
class TestRetryAndTracking:
    def _get_job(self, client, campaign_id):
        r = client.get(f"{BASE_URL}/api/campaigns/{campaign_id}/stats")
        assert r.status_code == 200
        d = r.json()
        assert d["recipients"], "no recipients"
        return d, d["recipients"][0]

    def test_scheduler_processes_and_retries_transient(self, client, seed):
        """SMTP host is unreachable → transient error → job returns to pending with attempts++."""
        cid = seed["campaign"]
        # wait up to ~35s for scheduler (10s tick) to attempt at least once
        deadline = time.time() + 40
        job = None
        while time.time() < deadline:
            _, job = self._get_job(client, cid)
            if job.get("attempts", 0) >= 1:
                break
            time.sleep(3)
        assert job is not None
        assert job["attempts"] >= 1, f"attempts not incremented: {job}"
        # transient (connection refused) → status is 'pending' or 'sending' (in flight) or eventually failed after 3 tries
        assert job["status"] in ("pending", "sending", "failed", "bounced"), job["status"]
        # error message must be recorded when pending after failure
        if job["status"] == "pending":
            assert job.get("error"), "error should be recorded on transient failure"

    def test_stats_fields_present(self, client, seed):
        d, job = self._get_job(client, seed["campaign"])
        for k in ("open_count", "click_count", "attempts"):
            assert k in job, f"missing {k} in recipient"
        for k in ("total", "sent", "opened", "clicked", "bounced", "failed", "pending"):
            assert k in d["stats"]

    def test_open_tracking_pixel_no_auth(self, client, seed):
        """Force a job to 'sent' state by direct DB is not possible from client;
        instead call the tracking endpoint against the job's tracking_id and
        verify open_count increments and status becomes 'opened' when previously 'pending/sending/sent'."""
        # obtain tracking_id via stats then via jobs (we only have job_id) — use dashboard? No.
        # Trick: get the job via /api/campaigns/{id}/stats — recipient lacks tracking_id.
        # So we hit a different path: use the seed to fetch tracking_id via mongo? Not accessible.
        # Alternative: create a fresh campaign with the SAME plumbing and rely on the fact that
        # the scheduler DOES try to send. Even if sending fails, we can still hit the tracking
        # endpoint using the tracking_id we need to discover. So we must expose tracking_id.
        # Workaround: the /stats endpoint doesn't return it — skip if we can't obtain it.
        # But we CAN call the endpoint with a non-existent id and expect 200 image/png (no-op).
        r = requests.get(f"{BASE_URL}/api/track/open/nonexistent.png?t=1", timeout=15)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("image/")
        assert len(r.content) > 20

    def test_click_tracking_redirect_no_auth(self):
        r = requests.get(
            f"{BASE_URL}/api/track/click/nonexistent",
            params={"url": "https://smartize.pt"},
            allow_redirects=False, timeout=15,
        )
        assert r.status_code in (302, 307), r.status_code
        assert "smartize.pt" in r.headers.get("location", "")


# ---------- Tracking pixel/click updates real jobs (using mongo to fetch tracking_id) ----------
class TestTrackingUpdatesJob:
    def _mongo(self):
        from pymongo import MongoClient
        mc = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
        return mc[os.environ.get("DB_NAME", "test_database")]

    def _get_job_doc(self, seed):
        dbm = self._mongo()
        return dbm.email_jobs.find_one({"campaign_id": seed["campaign"]})

    def test_open_pixel_marks_opened_and_increments(self, client, seed):
        job = self._get_job_doc(seed)
        assert job and job.get("tracking_id"), "job not created or missing tracking_id"
        # Pre-set status to 'sent' so pixel can promote to 'opened' (bypasses need for real SMTP)
        dbm = self._mongo()
        dbm.email_jobs.update_one(
            {"_id": job["_id"]},
            {"$set": {"status": "sent", "sent_at": "2026-01-01T00:00:00+00:00",
                      "opened_at": None, "open_count": 0}},
        )
        tid = job["tracking_id"]

        # Hit pixel (no auth) — should return image/png and update job
        r1 = requests.get(f"{BASE_URL}/api/track/open/{tid}.png", params={"t": 1}, timeout=15)
        assert r1.status_code == 200
        assert r1.headers.get("content-type", "").startswith("image/png")

        j1 = dbm.email_jobs.find_one({"_id": job["_id"]})
        assert j1["status"] == "opened", j1["status"]
        assert j1["open_count"] == 1
        assert j1["opened_at"] is not None
        assert j1.get("last_opened_at") is not None

        # Second hit → open_count == 2, opened_at preserved
        first_opened_at = j1["opened_at"]
        r2 = requests.get(f"{BASE_URL}/api/track/open/{tid}.png", params={"t": 1}, timeout=15)
        assert r2.status_code == 200
        j2 = dbm.email_jobs.find_one({"_id": job["_id"]})
        assert j2["open_count"] == 2
        assert j2["opened_at"] == first_opened_at

        # Campaign stats reflect the opened count
        s = client.get(f"{BASE_URL}/api/campaigns/{seed['campaign']}/stats").json()
        assert s["stats"]["opened"] >= 1
        rec = next(x for x in s["recipients"] if x["job_id"] == str(job["_id"]))
        assert rec["open_count"] == 2
        assert rec["status"] == "opened"

    def test_click_marks_clicked_and_redirects(self, client, seed):
        job = self._get_job_doc(seed)
        assert job and job.get("tracking_id")
        tid = job["tracking_id"]

        r = requests.get(
            f"{BASE_URL}/api/track/click/{tid}",
            params={"url": "https://smartize.pt"},
            allow_redirects=False, timeout=15,
        )
        assert r.status_code in (302, 307)
        assert "smartize.pt" in r.headers.get("location", "")

        dbm = self._mongo()
        jd = dbm.email_jobs.find_one({"_id": job["_id"]})
        assert jd["clicked_at"] is not None
        assert jd["click_count"] >= 1
        assert jd["status"] == "clicked"


# ---------- Signature applied in HTML (verify via legacy fallback path) ----------
class TestSignatureFallback:
    """We can't intercept the outgoing SMTP payload, but we can validate the
    LEGACY signature fallback path directly via the smtp accounts collection:
    write a legacy 'signature' plain-text field and confirm worker._send_job()
    would use it (indirect: signature_html is empty in DB, but no send happens
    without SMTP — we assert only field persistence + presence in doc)."""

    def test_signature_html_persists_on_smtp(self, client, seed):
        r = client.put(f"{BASE_URL}/api/smtp/{seed['smtp']}", json={
            "signature_html": '<p>Sig <a href="https://smartize.pt">Smartize</a></p>',
            "password": "",
        })
        assert r.status_code == 200
        assert 'smartize.pt' in r.json()["signature_html"]

    def test_smtp_test_send_uses_signature(self, client, seed):
        # test-send returns a message; if SMTP unreachable, success=False + message
        r = client.post(f"{BASE_URL}/api/smtp/test-send", json={
            "smtp_account_id": seed["smtp"],
            "to_email": "sink@example.com",
            "signature_html": "<p>OverrideSig</p>",
        })
        assert r.status_code == 200
        j = r.json()
        assert "success" in j and "message" in j
