"""Iteration 7 backend tests: editable pipelines (CRUD + stages), deals creation/move, contact conversion."""
import os
import uuid

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
base_url = os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")
if not base_url:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")
BASE_URL = base_url.rstrip("/")
API = f"{BASE_URL}/api"

EMAIL = "carlos.miguel@smartize.pt"
PASSWORD = "100%Smartize."  # from review request; fallback below


@pytest.fixture(scope="session")
def client():
    ses = requests.Session()
    ses.headers.update({"Content-Type": "application/json"})
    token = None
    for pwd in ["100%Smartize", "100%Smartize."]:
        r = ses.post(f"{API}/auth/login", json={"email": EMAIL, "password": pwd})
        if r.status_code == 200 and r.json().get("token"):
            token = r.json()["token"]
            break
    if not token:
        pytest.fail(f"Login failed for {EMAIL}")
    ses.headers.update({"Authorization": f"Bearer {token}"})
    return ses


@pytest.fixture(scope="module")
def created(client):
    ids = {"pipelines": [], "deals": [], "contacts": []}
    yield ids
    for d in ids["deals"]:
        client.delete(f"{API}/deals/{d}")
    for p in ids["pipelines"]:
        client.delete(f"{API}/pipelines/{p}")
    for c in ids["contacts"]:
        client.delete(f"{API}/contacts/{c}")


# ---------- Pipelines CRUD ----------
class TestPipelines:
    def test_list_pipelines_shape(self, client):
        r = client.get(f"{API}/pipelines")
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list) and len(data) >= 1
        for p in data:
            assert "id" in p and "_id" not in p
            assert isinstance(p["stages"], list) and p["stages"]
            for st in p["stages"]:
                assert "color" in st and st["color"].startswith("#")
                assert isinstance(st["probability"], int)
                assert st["type"] in ("open", "won", "lost")
        assert sum(1 for p in data if p.get("is_default")) == 1, "exactly one default pipeline expected"

    def test_create_rename_and_persist(self, client, created):
        name = f"TEST_pipe_{uuid.uuid4().hex[:6]}"
        r = client.post(f"{API}/pipelines", json={"name": name})
        assert r.status_code == 200, r.text
        p = r.json()
        created["pipelines"].append(p["id"])
        assert p["name"] == name
        assert len(p["stages"]) == 7

        new_name = name + "_ren"
        stages = [
            {"id": "a", "name": "Aberta A", "type": "open", "color": "#123456", "probability": 25},
            {"id": "b", "name": "Ganha B", "type": "won", "color": "#10b981", "probability": 100},
            {"id": "c", "name": "Perdida C", "type": "lost", "color": "#ef4444", "probability": 0},
        ]
        r = client.put(f"{API}/pipelines/{p['id']}", json={"name": new_name, "stages": stages})
        assert r.status_code == 200, r.text
        # GET verify persistence + order
        got = next(x for x in client.get(f"{API}/pipelines").json() if x["id"] == p["id"])
        assert got["name"] == new_name
        assert [s["id"] for s in got["stages"]] == ["a", "b", "c"]
        assert got["stages"][0]["color"] == "#123456"
        assert got["stages"][0]["probability"] == 25
        assert got["stages"][1]["type"] == "won"

        # reorder
        reordered = [stages[2], stages[0], stages[1]]
        r = client.put(f"{API}/pipelines/{p['id']}", json={"stages": reordered})
        assert r.status_code == 200, r.text
        got = next(x for x in client.get(f"{API}/pipelines").json() if x["id"] == p["id"])
        assert [s["id"] for s in got["stages"]] == ["c", "a", "b"]
        assert got["name"] == new_name

    def test_put_empty_body(self, client, created):
        pid = created["pipelines"][0]
        r = client.put(f"{API}/pipelines/{pid}", json={})
        assert r.status_code in (200, 400, 422), r.text

    def test_set_default_and_restore(self, client, created):
        original = next(p for p in client.get(f"{API}/pipelines").json() if p.get("is_default"))
        target = created["pipelines"][0]
        r = client.post(f"{API}/pipelines/{target}/set-default")
        assert r.status_code == 200, r.text
        data = client.get(f"{API}/pipelines").json()
        assert next(p for p in data if p["id"] == target)["is_default"] is True
        assert sum(1 for p in data if p.get("is_default")) == 1
        # restore
        assert client.post(f"{API}/pipelines/{original['id']}/set-default").status_code == 200
        data = client.get(f"{API}/pipelines").json()
        assert next(p for p in data if p["id"] == original["id"])["is_default"] is True

    def test_put_nonexistent_pipeline_should_404(self, client):
        r = client.put(f"{API}/pipelines/{'0'*24}", json={"name": "TEST_ghost"})
        assert r.status_code == 404, f"expected 404, got {r.status_code} body={r.text[:200]}"

    def test_stage_probability_bounds(self, client, created):
        pid = created["pipelines"][0]
        r = client.put(f"{API}/pipelines/{pid}", json={"stages": [
            {"id": "x", "name": "Bad", "type": "open", "color": "#000000", "probability": 500}]})
        assert r.status_code in (400, 422), f"probability 500 accepted (status {r.status_code})"

    def test_set_default_invalid_id(self, client):
        assert client.post(f"{API}/pipelines/{'0'*24}/set-default").status_code == 404
        assert client.post(f"{API}/pipelines/abc/set-default").status_code == 400

    def test_delete_pipeline_cascades(self, client, created):
        p = client.post(f"{API}/pipelines", json={"name": "TEST_del_pipe"}).json()
        pid = p["id"]
        deal = client.post(f"{API}/deals", json={"name": "TEST_deal_cascade", "pipeline_id": pid}).json()
        assert deal["pipeline_id"] == pid
        r = client.delete(f"{API}/pipelines/{pid}")
        assert r.status_code == 200, r.text
        assert all(x["id"] != pid for x in client.get(f"{API}/pipelines").json())
        assert client.get(f"{API}/deals/{deal['id']}").status_code == 404

    def test_cannot_delete_only_pipeline(self, client):
        pipes = client.get(f"{API}/pipelines").json()
        if len(pipes) > 1:
            pytest.skip("more than one pipeline exists; 400 branch verified by code path only")
        r = client.delete(f"{API}/pipelines/{pipes[0]['id']}")
        assert r.status_code == 400

    def test_delete_nonexistent_pipeline(self, client):
        r = client.delete(f"{API}/pipelines/{'0'*24}")
        assert r.status_code in (400, 404)


# ---------- Deals ----------
class TestDeals:
    @pytest.fixture(scope="class")
    def pipe(self, client, created):
        stages = [
            {"id": "s1", "name": "Novo", "type": "open", "color": "#3b82f6", "probability": 10},
            {"id": "s2", "name": "Reunião marcada", "type": "open", "color": "#8b5cf6", "probability": 30},
            {"id": "s3", "name": "Ganho", "type": "won", "color": "#10b981", "probability": 100},
            {"id": "s4", "name": "Perdido", "type": "lost", "color": "#ef4444", "probability": 0},
        ]
        p = client.post(f"{API}/pipelines", json={"name": f"TEST_deals_{uuid.uuid4().hex[:5]}", "stages": stages}).json()
        created["pipelines"].append(p["id"])
        return p

    def test_create_deal_inherits_stage_probability(self, client, created, pipe):
        payload = {"name": "TEST_deal_prob", "contact_name": "Ana Silva", "company": "ACME",
                   "email": "test_deal@example.com", "phone": "911", "value": 1500,
                   "pipeline_id": pipe["id"], "stage_id": "s2", "owner": "Carlos", "notes": "n"}
        r = client.post(f"{API}/deals", json=payload)
        assert r.status_code == 200, r.text
        d = r.json()
        created["deals"].append(d["id"])
        assert d["probability"] == 30, "should inherit stage probability"
        assert d["contact_name"] == "Ana Silva"
        assert d["stage_id"] == "s2"
        assert d["status"] == "open"
        assert "_id" not in d
        got = client.get(f"{API}/deals/{d['id']}").json()
        assert got["value"] == 1500 and got["company"] == "ACME"

    def test_manual_probability_respected(self, client, created, pipe):
        d = client.post(f"{API}/deals", json={"name": "TEST_deal_manual", "pipeline_id": pipe["id"],
                                             "stage_id": "s2", "probability": 77}).json()
        created["deals"].append(d["id"])
        assert d["probability"] == 77

    def test_deal_defaults_to_default_pipeline_and_first_stage(self, client, created):
        default_pipe = next(p for p in client.get(f"{API}/pipelines").json() if p.get("is_default"))
        d = client.post(f"{API}/deals", json={"name": "TEST_deal_default"}).json()
        created["deals"].append(d["id"])
        assert d["pipeline_id"] == default_pipe["id"]
        assert d["stage_id"] == default_pipe["stages"][0]["id"]

    def test_move_deal_won_lost_open(self, client, created, pipe):
        d = client.post(f"{API}/deals", json={"name": "TEST_deal_move", "pipeline_id": pipe["id"], "stage_id": "s1"}).json()
        created["deals"].append(d["id"])
        did = d["id"]

        r = client.post(f"{API}/deals/{did}/move", json={"stage_id": "s3"})
        assert r.status_code == 200, r.text
        m = r.json()
        assert m["status"] == "won" and m["probability"] == 100 and m["lost_reason"] is None

        r = client.post(f"{API}/deals/{did}/move", json={"stage_id": "s4", "lost_reason": "Preço"})
        m = r.json()
        assert r.status_code == 200
        assert m["status"] == "lost" and m["lost_reason"] == "Preço" and m["probability"] == 0

        r = client.post(f"{API}/deals/{did}/move", json={"stage_id": "s2"})
        m = r.json()
        assert m["status"] == "open" and m["probability"] == 30 and m["lost_reason"] is None
        # persisted
        got = client.get(f"{API}/deals/{did}").json()
        assert got["stage_id"] == "s2" and got["status"] == "open"
        assert any("Movido para" in h["text"] for h in got.get("history", []))

    def test_move_invalid_stage(self, client, created, pipe):
        d = client.post(f"{API}/deals", json={"name": "TEST_deal_badmove", "pipeline_id": pipe["id"]}).json()
        created["deals"].append(d["id"])
        r = client.post(f"{API}/deals/{d['id']}/move", json={"stage_id": "nope"})
        assert r.status_code == 400

    def test_update_and_delete_deal(self, client, pipe):
        d = client.post(f"{API}/deals", json={"name": "TEST_deal_upd", "pipeline_id": pipe["id"]}).json()
        r = client.put(f"{API}/deals/{d['id']}", json={"name": "TEST_deal_upd2", "value": 999, "contact_name": "Bruno"})
        assert r.status_code == 200
        got = client.get(f"{API}/deals/{d['id']}").json()
        assert got["name"] == "TEST_deal_upd2" and got["value"] == 999 and got["contact_name"] == "Bruno"
        assert client.delete(f"{API}/deals/{d['id']}").status_code == 200
        assert client.get(f"{API}/deals/{d['id']}").status_code == 404

    def test_list_deals_filtered_by_pipeline(self, client, pipe):
        r = client.get(f"{API}/deals", params={"pipeline_id": pipe["id"]})
        assert r.status_code == 200
        assert all(d["pipeline_id"] == pipe["id"] for d in r.json())


# ---------- Contact conversion ----------
class TestConvertContact:
    def test_convert_contact_copies_fields(self, client, created):
        email = f"qa_iter7_{uuid.uuid4().hex[:6]}@example.com"
        c = client.post(f"{API}/contacts", json={"first_name": "Rita", "last_name": "Costa", "email": email,
                                                 "company": "Costa Lda", "phone": "912345678",
                                                 "position": "CEO", "website": "https://costa.pt"})
        assert c.status_code in (200, 201), c.text
        contact = c.json()
        created["contacts"].append(contact["id"])
        r = client.post(f"{API}/contacts/{contact['id']}/convert")
        assert r.status_code == 200, r.text
        d = r.json()
        created["deals"].append(d["id"])
        assert d["email"] == email and d["company"] == "Costa Lda"
        assert d["phone"] == "912345678" and d["position"] == "CEO" and d["website"] == "https://costa.pt"
        assert "Rita Costa" in d["name"]
        assert d["contact_id"] == contact["id"]
        assert any(h["text"] == "Negócio criado" for h in d["history"])

    def test_convert_missing_contact(self, client):
        assert client.post(f"{API}/contacts/{'0'*24}/convert").status_code == 404


# ---------- Regression: automations ----------
class TestAutomationsRegression:
    def test_automation_crud_and_add_tag_on_create(self, client, created):
        p = client.post(f"{API}/pipelines", json={"name": f"TEST_auto_{uuid.uuid4().hex[:5]}"}).json()
        created["pipelines"].append(p["id"])
        a = client.post(f"{API}/automations", json={"pipeline_id": p["id"], "name": "TEST_auto_tag",
                                                    "event": "deal_created", "action": "add_tag",
                                                    "config": {"tag": "TEST_tag"}, "enabled": True})
        assert a.status_code == 200, a.text
        aid = a.json()["id"]
        d = client.post(f"{API}/deals", json={"name": "TEST_auto_deal", "pipeline_id": p["id"]}).json()
        created["deals"].append(d["id"])
        got = client.get(f"{API}/deals/{d['id']}").json()
        assert "TEST_tag" in got.get("tags", []), "add_tag automation should run on deal_created"
        r = client.put(f"{API}/automations/{aid}", json={"enabled": False, "name": "TEST_auto_tag2"})
        assert r.status_code == 200 and r.json()["name"] == "TEST_auto_tag2"
        assert client.delete(f"{API}/automations/{aid}").status_code == 200
        assert all(x["id"] != aid for x in client.get(f"{API}/automations", params={"pipeline_id": p["id"]}).json())

    def test_automation_update_404(self, client):
        assert client.put(f"{API}/automations/{'0'*24}", json={"name": "x"}).status_code == 404


# ---------- Auth ----------
class TestAuth:
    def test_unauthenticated_pipelines(self):
        r = requests.get(f"{API}/pipelines")
        assert r.status_code in (401, 403)

    def test_bad_credentials(self):
        r = requests.post(f"{API}/auth/login", json={"email": EMAIL, "password": "wrong-pass-xyz"})
        assert r.status_code in (401, 429)
