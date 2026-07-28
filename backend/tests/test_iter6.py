"""Iteration 6 backend tests: CRM (pipelines, deals, move, convert, automations) + Campaign sequences."""
import os
import re
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")


@pytest.fixture(scope="session")
def creds():
    p = Path("/app/memory/test_credentials.md")
    if not p.exists():
        pytest.skip("missing test_credentials.md")
    content = p.read_text(encoding="utf-8")
    m = re.search(r"Email:\s*(carlos\.miguel@\S+)\s*\|\s*Password:\s*(\S+)", content)
    if not m:
        pytest.skip("carlos.miguel credentials not found")
    return {"email": m.group(1), "password": m.group(2)}


@pytest.fixture(scope="session")
def client(creds):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=30)
    if r.status_code != 200:
        pytest.fail(f"login failed {r.status_code}: {r.text[:300]}")
    token = r.json().get("token")
    assert token
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="session")
def pipeline(client):
    r = client.get(f"{BASE_URL}/api/pipelines", timeout=30)
    assert r.status_code == 200, r.text
    pls = r.json()
    assert len(pls) >= 1
    p = pls[0]
    assert "_id" not in p and "id" in p
    return p


created_deals = []
created_automations = []
created_campaigns = []
created_contacts = []
created_templates = []
created_smtp = []
created_groups = []


@pytest.fixture(scope="session")
def seed(client):
    """Seed SMTP account, 2 templates, a group with 2 contacts (preview DB is empty)."""
    smtp = client.post(f"{BASE_URL}/api/smtp", json={
        "name": "TEST_iter6 SMTP", "from_name": "QA", "from_email": "qa@example.com",
        "host": "smtp.example.com", "port": 587, "username": "qa@example.com",
        "password": "secret", "is_default": True,
    }, timeout=30)
    assert smtp.status_code in (200, 201), smtp.text
    smtp_id = smtp.json()["id"]
    created_smtp.append(smtp_id)

    tpl_ids = []
    for i in (1, 2):
        t = client.post(f"{BASE_URL}/api/templates", json={
            "name": f"TEST_iter6 Template {i}", "subject": f"Assunto {i} {{first_name}}",
            "content_html": f"<p>Ola {{first_name}} passo {i}</p>", "content_text": f"Ola {{first_name}} passo {i}",
        }, timeout=30)
        assert t.status_code in (200, 201), t.text
        tpl_ids.append(t.json()["id"])
        created_templates.append(t.json()["id"])

    g = client.post(f"{BASE_URL}/api/groups", json={"name": "TEST_iter6 SeqGroup"}, timeout=30)
    gid = g.json()["id"]
    created_groups.append(gid)
    for i in (1, 2):
        c = client.post(f"{BASE_URL}/api/contacts", json={
            "group_id": gid, "email": f"test_iter6_seq{i}@example.com",
            "first_name": f"Seq{i}", "last_name": "Teste",
        }, timeout=30)
        assert c.status_code in (200, 201), c.text
        created_contacts.append(c.json()["id"])
    return {"smtp_id": smtp_id, "templates": tpl_ids, "group_id": gid}


@pytest.fixture(scope="session", autouse=True)
def cleanup(client):
    yield
    for d in created_deals:
        client.delete(f"{BASE_URL}/api/deals/{d}", timeout=30)
    for a in created_automations:
        client.delete(f"{BASE_URL}/api/automations/{a}", timeout=30)
    for c in created_campaigns:
        client.delete(f"{BASE_URL}/api/campaigns/{c}", timeout=30)
    for c in created_contacts:
        client.delete(f"{BASE_URL}/api/contacts/{c}", timeout=30)
    for t in created_templates:
        client.delete(f"{BASE_URL}/api/templates/{t}", timeout=30)
    for sid in created_smtp:
        client.delete(f"{BASE_URL}/api/smtp/{sid}", timeout=30)
    for gid in created_groups:
        client.delete(f"{BASE_URL}/api/groups/{gid}", timeout=30)


# ---------------- Pipelines ----------------
class TestPipelines:
    def test_default_stages(self, pipeline):
        names = [st["name"] for st in pipeline["stages"]]
        assert "Novo contacto" in names
        assert "Reunião marcada" in names
        types = {st["type"] for st in pipeline["stages"]}
        assert "won" in types and "lost" in types

    def test_pipelines_unauth(self):
        r = requests.get(f"{BASE_URL}/api/pipelines", timeout=30)
        assert r.status_code in (401, 403)


# ---------------- Deals CRUD ----------------
class TestDeals:
    def test_create_deal_defaults_first_stage(self, client, pipeline):
        r = client.post(f"{BASE_URL}/api/deals", json={"name": "TEST_iter6 Deal A", "value": 1500.5}, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        created_deals.append(d["id"])
        assert d["name"] == "TEST_iter6 Deal A"
        assert d["value"] == 1500.5
        assert d["status"] == "open"
        assert d["stage_id"] == pipeline["stages"][0]["id"]
        assert d["pipeline_id"] == pipeline["id"]
        assert "_id" not in d
        assert any("criado" in h["text"].lower() for h in d["history"])

        g = client.get(f"{BASE_URL}/api/deals/{d['id']}", timeout=30)
        assert g.status_code == 200
        assert g.json()["name"] == "TEST_iter6 Deal A"

    def test_update_deal_persists(self, client):
        r = client.post(f"{BASE_URL}/api/deals", json={"name": "TEST_iter6 Deal B"}, timeout=30)
        did = r.json()["id"]
        created_deals.append(did)
        u = client.put(f"{BASE_URL}/api/deals/{did}", json={"name": "TEST_iter6 Deal B2", "value": 999, "probability": 40}, timeout=30)
        assert u.status_code == 200, u.text
        assert u.json()["name"] == "TEST_iter6 Deal B2"
        g = client.get(f"{BASE_URL}/api/deals/{did}", timeout=30).json()
        assert g["name"] == "TEST_iter6 Deal B2"
        assert g["value"] == 999
        assert g["probability"] == 40

    def test_delete_deal(self, client):
        r = client.post(f"{BASE_URL}/api/deals", json={"name": "TEST_iter6 Deal C"}, timeout=30)
        did = r.json()["id"]
        assert client.delete(f"{BASE_URL}/api/deals/{did}", timeout=30).status_code == 200
        assert client.get(f"{BASE_URL}/api/deals/{did}", timeout=30).status_code == 404

    def test_get_deal_404_and_400(self, client):
        assert client.get(f"{BASE_URL}/api/deals/507f1f77bcf86cd799439011", timeout=30).status_code == 404
        assert client.get(f"{BASE_URL}/api/deals/notanid", timeout=30).status_code == 400

    def test_list_deals_filter(self, client, pipeline):
        r = client.get(f"{BASE_URL}/api/deals", params={"pipeline_id": pipeline["id"]}, timeout=30)
        assert r.status_code == 200
        for d in r.json():
            assert d["pipeline_id"] == pipeline["id"]


# ---------------- Move ----------------
class TestMoveDeal:
    def test_move_open_won_lost(self, client, pipeline):
        stages = pipeline["stages"]
        open_stage = next(st for st in stages if st["type"] == "open" and st != stages[0])
        won = next(st for st in stages if st["type"] == "won")
        lost = next(st for st in stages if st["type"] == "lost")

        did = client.post(f"{BASE_URL}/api/deals", json={"name": "TEST_iter6 Move"}, timeout=30).json()["id"]
        created_deals.append(did)

        r = client.post(f"{BASE_URL}/api/deals/{did}/move", json={"stage_id": open_stage["id"]}, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["stage_id"] == open_stage["id"]
        assert r.json()["status"] == "open"

        r = client.post(f"{BASE_URL}/api/deals/{did}/move", json={"stage_id": won["id"]}, timeout=30)
        assert r.json()["status"] == "won"

        r = client.post(f"{BASE_URL}/api/deals/{did}/move", json={"stage_id": lost["id"], "lost_reason": "TEST_sem orçamento"}, timeout=30)
        body = r.json()
        assert body["status"] == "lost"
        assert body["lost_reason"] == "TEST_sem orçamento"

        g = client.get(f"{BASE_URL}/api/deals/{did}", timeout=30).json()
        assert g["status"] == "lost" and g["stage_id"] == lost["id"]
        assert any("Movido" in h["text"] for h in g["history"])

    def test_move_invalid_stage(self, client):
        did = client.post(f"{BASE_URL}/api/deals", json={"name": "TEST_iter6 MoveBad"}, timeout=30).json()["id"]
        created_deals.append(did)
        r = client.post(f"{BASE_URL}/api/deals/{did}/move", json={"stage_id": "nope"}, timeout=30)
        assert r.status_code == 400
        assert "Etapa" in r.json().get("detail", "")

    def test_move_unknown_deal(self, client):
        r = client.post(f"{BASE_URL}/api/deals/507f1f77bcf86cd799439011/move", json={"stage_id": "novo"}, timeout=30)
        assert r.status_code == 404


# ---------------- Convert contact ----------------
class TestConvertContact:
    def test_convert_contact_creates_deal(self, client):
        groups = client.get(f"{BASE_URL}/api/groups", timeout=30).json()
        gid = groups[0]["id"] if groups else client.post(f"{BASE_URL}/api/groups", json={"name": "TEST_iter6 Group"}, timeout=30).json()["id"]
        c = client.post(f"{BASE_URL}/api/contacts", json={
            "group_id": gid, "email": "test_iter6_convert@example.com",
            "first_name": "Ana", "last_name": "Silva", "company": "TEST Corp", "position": "CEO",
        }, timeout=30)
        assert c.status_code in (200, 201), c.text
        cid = c.json()["id"]
        created_contacts.append(cid)

        r = client.post(f"{BASE_URL}/api/contacts/{cid}/convert", timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        created_deals.append(d["id"])
        assert "Ana Silva" in d["name"]
        assert d["contact_id"] == cid
        assert d["email"] == "test_iter6_convert@example.com"
        assert d["company"] == "TEST Corp"
        assert d["status"] == "open"

        listed = client.get(f"{BASE_URL}/api/deals", timeout=30).json()
        assert any(x["id"] == d["id"] for x in listed)

    def test_convert_unknown_contact(self, client):
        r = client.post(f"{BASE_URL}/api/contacts/507f1f77bcf86cd799439011/convert", timeout=30)
        assert r.status_code == 404


# ---------------- Automations ----------------
class TestAutomations:
    def test_create_list_update_delete(self, client, pipeline, seed):
        tid = seed["templates"][0]
        payload = {
            "pipeline_id": pipeline["id"], "name": "TEST_iter6 Auto",
            "event": "deal_created", "action": "send_email",
            "config": {"template_id": tid} if tid else {}, "delay_days": 0, "enabled": True,
        }
        r = client.post(f"{BASE_URL}/api/automations", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        a = r.json()
        created_automations.append(a["id"])
        assert a["name"] == "TEST_iter6 Auto"
        assert a["event"] == "deal_created"
        assert a["action"] == "send_email"
        assert "_id" not in a

        lst = client.get(f"{BASE_URL}/api/automations", params={"pipeline_id": pipeline["id"]}, timeout=30).json()
        assert any(x["id"] == a["id"] for x in lst)

        u = client.put(f"{BASE_URL}/api/automations/{a['id']}", json={"enabled": False, "name": "TEST_iter6 Auto2"}, timeout=30)
        assert u.status_code == 200
        assert u.json()["enabled"] is False
        assert u.json()["name"] == "TEST_iter6 Auto2"

        assert client.delete(f"{BASE_URL}/api/automations/{a['id']}", timeout=30).status_code == 200
        lst = client.get(f"{BASE_URL}/api/automations", timeout=30).json()
        assert not any(x["id"] == a["id"] for x in lst)

    def test_add_tag_automation_fires_on_deal_created(self, client, pipeline):
        r = client.post(f"{BASE_URL}/api/automations", json={
            "pipeline_id": pipeline["id"], "name": "TEST_iter6 TagAuto",
            "event": "deal_created", "action": "add_tag", "config": {"tag": "TEST_auto_tag"},
        }, timeout=30)
        assert r.status_code == 200, r.text
        aid = r.json()["id"]
        created_automations.append(aid)

        d = client.post(f"{BASE_URL}/api/deals", json={"name": "TEST_iter6 AutoDeal"}, timeout=30).json()
        created_deals.append(d["id"])
        g = client.get(f"{BASE_URL}/api/deals/{d['id']}", timeout=30).json()
        assert "TEST_auto_tag" in g.get("tags", []), f"automation add_tag did not fire: {g.get('tags')}"

    def test_create_task_automation_on_stage_change(self, client, pipeline):
        won = next(st for st in pipeline["stages"] if st["type"] == "won")
        r = client.post(f"{BASE_URL}/api/automations", json={
            "pipeline_id": pipeline["id"], "name": "TEST_iter6 TaskAuto",
            "event": "deal_won", "action": "create_task", "config": {"title": "TEST_auto_task"},
        }, timeout=30)
        aid = r.json()["id"]
        created_automations.append(aid)
        did = client.post(f"{BASE_URL}/api/deals", json={"name": "TEST_iter6 TaskDeal"}, timeout=30).json()["id"]
        created_deals.append(did)
        mv = client.post(f"{BASE_URL}/api/deals/{did}/move", json={"stage_id": won["id"]}, timeout=30)
        assert mv.status_code == 200
        tasks = client.get(f"{BASE_URL}/api/tasks", params={"deal_id": did}, timeout=30).json()
        assert any(t["title"] == "TEST_auto_task" for t in tasks), tasks


# ---------------- Campaign sequences ----------------
class TestSequenceCampaign:
    def test_create_sequence_campaign_and_start(self, client, seed):
        t0, t1 = seed["templates"]
        payload = {
            "name": "TEST_iter6 Sequencia", "group_id": seed["group_id"], "is_sequence": True,
            "smtp_account_id": seed["smtp_id"],
            "steps": [
                {"template_id": t0, "send_type": "new", "delay_days": 0, "delay_hours": 0},
                {"template_id": t1, "send_type": "reply", "delay_days": 3, "delay_hours": 2},
            ],
            "schedule_at": "2030-01-01T09:00:00",
        }
        r = client.post(f"{BASE_URL}/api/campaigns", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        c = r.json()
        created_campaigns.append(c["id"])
        assert c["is_sequence"] is True
        assert len(c["steps"]) == 2
        assert c["steps"][1]["send_type"] == "reply"
        assert c["steps"][1]["delay_days"] == 3
        assert c["steps"][1]["delay_hours"] == 2
        assert c["status"] == "rascunho"

        g = client.get(f"{BASE_URL}/api/campaigns/{c['id']}", timeout=30).json()
        assert g["is_sequence"] is True and len(g["steps"]) == 2

        st = client.post(f"{BASE_URL}/api/campaigns/{c['id']}/start", timeout=30)
        assert st.status_code == 200, st.text
        body = st.json()
        assert body["recipients"] == 2, body

        after = client.get(f"{BASE_URL}/api/campaigns/{c['id']}", timeout=30).json()
        assert after["status"] == "sending"
        assert after["total_recipients"] == 2

        # enrollments created (verify in mongo)
        n, enr = _mongo_enrollments("TEST_iter6 Sequencia")
        assert n == 2, f"expected 2 enrollments, got {n}"
        assert enr["current_step"] == 0
        assert enr["status"] == "active"
        assert enr["next_send_at"]
        assert enr["smtp_account_id"] == seed["smtp_id"]

        # cancel so worker stops
        assert client.post(f"{BASE_URL}/api/campaigns/{c['id']}/cancel", timeout=30).status_code == 200
        n2, enr2 = _mongo_enrollments("TEST_iter6 Sequencia")
        assert enr2["status"] == "stopped"

    def test_start_twice_rejected(self, client, seed):
        t0 = seed["templates"][0]
        r = client.post(f"{BASE_URL}/api/campaigns", json={
            "name": "TEST_iter6 SeqTwice", "group_id": seed["group_id"], "is_sequence": True,
            "steps": [{"template_id": t0, "send_type": "new", "delay_days": 0, "delay_hours": 0}],
        }, timeout=30)
        cid = r.json()["id"]
        created_campaigns.append(cid)
        assert client.post(f"{BASE_URL}/api/campaigns/{cid}/start", timeout=30).status_code == 200
        second = client.post(f"{BASE_URL}/api/campaigns/{cid}/start", timeout=30)
        assert second.status_code == 400
        client.post(f"{BASE_URL}/api/campaigns/{cid}/cancel", timeout=30)

    def test_simple_campaign_still_works(self, client, seed):
        r = client.post(f"{BASE_URL}/api/campaigns", json={
            "name": "TEST_iter6 Simples", "group_id": seed["group_id"], "template_id": seed["templates"][0],
        }, timeout=30)
        assert r.status_code == 200, r.text
        c = r.json()
        created_campaigns.append(c["id"])
        assert c["is_sequence"] is False
        assert c["template_id"] == seed["templates"][0]
        assert c["status"] == "rascunho"
        st = client.post(f"{BASE_URL}/api/campaigns/{c['id']}/start", timeout=30)
        assert st.status_code == 200, st.text
        assert st.json()["recipients"] == 2
        client.post(f"{BASE_URL}/api/campaigns/{c['id']}/cancel", timeout=30)

    def test_start_sequence_without_steps_fails(self, client, seed):
        r = client.post(f"{BASE_URL}/api/campaigns", json={
            "name": "TEST_iter6 SemPassos", "group_id": seed["group_id"], "is_sequence": True, "steps": [],
        }, timeout=30)
        assert r.status_code == 200, r.text
        cid = r.json()["id"]
        created_campaigns.append(cid)
        st = client.post(f"{BASE_URL}/api/campaigns/{cid}/start", timeout=30)
        assert st.status_code == 400
        assert "template" in st.json().get("detail", "").lower()


class TestEnrollmentCleanup:
    """Known defect: DELETE /api/campaigns/{id} does not remove campaign_contacts enrollments."""

    def test_delete_campaign_removes_enrollments(self, client, seed):
        t0 = seed["templates"][0]
        r = client.post(f"{BASE_URL}/api/campaigns", json={
            "name": "TEST_iter6 OrphanSeq", "group_id": seed["group_id"], "is_sequence": True,
            "steps": [{"template_id": t0, "send_type": "new", "delay_days": 0, "delay_hours": 0}],
        }, timeout=30)
        cid = r.json()["id"]
        assert client.post(f"{BASE_URL}/api/campaigns/{cid}/start", timeout=30).status_code == 200
        client.post(f"{BASE_URL}/api/campaigns/{cid}/cancel", timeout=30)
        assert client.delete(f"{BASE_URL}/api/campaigns/{cid}", timeout=30).status_code == 200
        n = _count_enrollments(cid)
        assert n == 0, f"{n} orphan campaign_contacts left after deleting campaign {cid}"


def _count_enrollments(campaign_id):
    import asyncio
    from motor.motor_asyncio import AsyncIOMotorClient
    from dotenv import dotenv_values as dv
    env = dv("/app/backend/.env")

    async def run():
        cli = AsyncIOMotorClient(env["MONGO_URL"])
        n = await cli[env["DB_NAME"]].campaign_contacts.count_documents({"campaign_id": campaign_id})
        cli.close()
        return n

    return asyncio.run(run())


def _mongo_enrollments(campaign_name):
    import asyncio
    from motor.motor_asyncio import AsyncIOMotorClient
    from dotenv import dotenv_values as dv
    env = dv("/app/backend/.env")

    async def check():
        cli = AsyncIOMotorClient(env["MONGO_URL"])
        dbx = cli[env["DB_NAME"]]
        camp = await dbx.campaigns.find_one({"name": campaign_name})
        assert camp, "campaign not found in db"
        n = await dbx.campaign_contacts.count_documents({"campaign_id": str(camp["_id"])})
        enr = await dbx.campaign_contacts.find_one({"campaign_id": str(camp["_id"])})
        cli.close()
        return n, enr

    return asyncio.run(check())
