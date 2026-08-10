import os
import requests
from dotenv import dotenv_values

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"]).rstrip("/") + "/api"
s = requests.Session()
r = s.post(f"{BASE}/auth/login", json={"email": "carlos.miguel@smartize.pt", "password": "100%Smartize"}, timeout=30)
s.headers.update({"Authorization": f"Bearer {r.json()['token']}"})

data = s.get(f"{BASE}/contacts?limit=1000", timeout=30).json()
items = data if isinstance(data, list) else data.get("items", [])
for c in items:
    if str(c.get("email", "")).startswith("qa_imp_iter8_"):
        print("del contact", c["email"], s.delete(f"{BASE}/contacts/{c['id']}", timeout=30).status_code)
for t in s.get(f"{BASE}/templates", timeout=30).json():
    if str(t.get("name", "")).startswith("TEST_"):
        print("del template", t["name"], s.delete(f"{BASE}/templates/{t['id']}", timeout=30).status_code)
for c in s.get(f"{BASE}/campaigns", timeout=30).json():
    if str(c.get("name", "")).startswith("TEST_"):
        print("del campaign", c["name"], s.delete(f"{BASE}/campaigns/{c['id']}", timeout=30).status_code)
for g in s.get(f"{BASE}/groups", timeout=30).json():
    if str(g.get("name", "")).startswith("TEST_"):
        print("del group", g["name"], s.delete(f"{BASE}/groups/{g['id']}", timeout=30).status_code)
print("remaining contacts:", len((lambda d: d if isinstance(d, list) else d.get("items", []))(s.get(f"{BASE}/contacts?limit=1000", timeout=30).json())))
print("templates:", [t["name"] for t in s.get(f"{BASE}/templates", timeout=30).json()])
