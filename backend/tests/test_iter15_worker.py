"""Iteration 15 — worker-level unit test: plain-text body gets the account's signature_text (one info per line)."""
import asyncio
import sys

import pytest

sys.path.insert(0, "/app/backend")


SIG_HTML = (
    '<table><tr><td><div>Carlos Santo</div><div>Growth Manager- Smartize Portugal</div>'
    '<div>Phone: (+351) 968 537 603</div><div>Email: carlos.santo@smartize.pt</div>'
    '<div>www.smartize.pt</div></td></tr></table>'
)
SIG_TEXT = ("Carlos Santo\nGrowth Manager- Smartize Portugal\nPhone: (+351) 968 537 603\n"
            "Email: carlos.santo@smartize.pt\nwww.smartize.pt")


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture(scope="module")
def env():
    import worker
    from core import db
    from bson import ObjectId
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def setup():
        c = await db.contacts.insert_one({"first_name": "TEST_Joao", "last_name": "Silva",
                                         "email": "test_iter15@example.invalid", "status": "novo"})
        t = await db.templates.insert_one({"name": "TEST_iter15 plain", "subject": "Ola {first_name}",
                                          "content_text": "Ola {first_name},\n\nMensagem simples.",
                                          "content_html": ""})
        th = await db.templates.insert_one({"name": "TEST_iter15 html", "subject": "Ola {first_name}",
                                           "content_text": "Ola {first_name},",
                                           "content_html": "<p>Ola <b>{first_name}</b>, conteudo HTML.</p>"})
        return str(c.inserted_id), str(t.inserted_id), str(th.inserted_id)

    contact_id, tpl_text_id, tpl_html_id = loop.run_until_complete(setup())
    yield {"worker": worker, "db": db, "ObjectId": ObjectId, "contact_id": contact_id,
           "tpl_text_id": tpl_text_id, "tpl_html_id": tpl_html_id, "loop": loop}

    async def teardown():
        await db.contacts.delete_one({"_id": ObjectId(contact_id)})
        await db.templates.delete_many({"_id": {"$in": [ObjectId(tpl_text_id), ObjectId(tpl_html_id)]}})
        await db.email_jobs.delete_many({"contact_id": contact_id})
    loop.run_until_complete(teardown())


def _invoke(env, template_id, smtp):
    worker, db, ObjectId = env["worker"], env["db"], env["ObjectId"]
    captured = {}

    async def fake_send_email(smtp_account, to_email, subject, html_body, text_body, in_reply_to=None):
        captured.update(subject=subject, html=html_body, text=text_body, to=to_email)
        return "<fake@id>"

    original = worker.send_email
    worker.send_email = fake_send_email
    try:
        async def go():
            res = await db.email_jobs.insert_one({
                "campaign_id": "x", "contact_id": env["contact_id"], "to_email": "test_iter15@example.invalid",
                "status": "pending", "tracking_id": str(ObjectId()), "attempts": 0,
            })
            job = await db.email_jobs.find_one({"_id": res.inserted_id})
            await worker._send_job({"template_id": template_id}, job, smtp)
            return await db.email_jobs.find_one({"_id": res.inserted_id})
        job_after = env["loop"].run_until_complete(go())
    finally:
        worker.send_email = original
    return captured, job_after


# Plain-text template -> text part contains account signature_text, one info per line, no HTML part
def test_plain_text_uses_signature_text(env):
    smtp = {"_id": "s1", "from_name": "Carlos", "from_email": "c@smartize.pt",
            "signature_html": SIG_HTML, "signature_text": SIG_TEXT}
    cap, job = _invoke(env, env["tpl_text_id"], smtp)
    print("TEXT BODY:\n" + cap["text"])
    assert job["status"] == "sent"
    assert cap["html"] == "", "plain-text template must not send HTML part"
    lines = [l for l in cap["text"].split("\n") if l.strip()]
    for expected in SIG_TEXT.split("\n"):
        assert expected in lines
    assert "SantoGrowth" not in cap["text"] and "PortugalPhone" not in cap["text"]
    assert "<" not in cap["text"]


# Empty signature_text -> derived from HTML via improved converter (still one info per line)
def test_plain_text_fallback_conversion(env):
    smtp = {"_id": "s1", "from_name": "Carlos", "from_email": "c@smartize.pt",
            "signature_html": SIG_HTML, "signature_text": ""}
    cap, job = _invoke(env, env["tpl_text_id"], smtp)
    print("FALLBACK TEXT BODY:\n" + cap["text"])
    lines = [l for l in cap["text"].split("\n") if l.strip()]
    assert "Carlos Santo" in lines
    assert "Growth Manager- Smartize Portugal" in lines
    assert any(l.startswith("Phone:") for l in lines)
    assert "www.smartize.pt" in lines
    assert "<" not in cap["text"]


# HTML template -> HTML part keeps the HTML signature, text part still has clean text signature
def test_html_template_keeps_html_signature(env):
    smtp = {"_id": "s1", "from_name": "Carlos", "from_email": "c@smartize.pt",
            "signature_html": SIG_HTML, "signature_text": SIG_TEXT}
    cap, job = _invoke(env, env["tpl_html_id"], smtp)
    assert job["status"] == "sent"
    assert "conteudo HTML" in cap["html"]
    assert "Growth Manager- Smartize Portugal" in cap["html"]
    assert "<div>" in cap["html"] or "<table" in cap["html"]
    # text alternative still carries clean text signature
    assert "Carlos Santo" in cap["text"].split("\n")
