"""WhatsApp adapter: webhook verification, signature checks and a full report through the Cloud API webhook.

Meta's servers are never contacted: sending, media download and upload are replaced by fakes.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re

import pytest

from conftest import KIT

PHONE_ID = "1234567890"
APP_SECRET = "test-app-secret-" + "x" * 16
VERIFY = "verify-me-123"
USER = "27710000001"


@pytest.fixture
def wa(app, monkeypatch):
    from ubufakazi_server import whatsapp
    from ubufakazi_server.config import get_settings
    s = get_settings()
    for k, v in {"whatsapp_token": "test-token", "whatsapp_phone_id": PHONE_ID,
                 "whatsapp_verify_token": VERIFY, "whatsapp_app_secret": APP_SECRET}.items():
        monkeypatch.setattr(s, k, v)
    sent: list[dict] = []
    uploads: list[tuple[str, int]] = []

    async def fake_send(to, body):
        sent.append({"to": to, **body})
        return {"messages": [{"id": "wamid.out"}]}

    async def fake_download(media_id):
        return (KIT / "case1-scam-website-screenshot.png").read_bytes(), ""

    async def fake_upload(data, filename, mime):
        uploads.append((filename, len(data)))
        return "MEDIA-1"

    monkeypatch.setattr(whatsapp, "send", fake_send)
    monkeypatch.setattr(whatsapp, "_download_media", fake_download)
    monkeypatch.setattr(whatsapp, "_upload", fake_upload)
    monkeypatch.setattr(whatsapp, "SYNC", True)
    whatsapp._chats.clear()
    whatsapp._seen_ids.clear()
    return {"mod": whatsapp, "sent": sent, "uploads": uploads}


_n = [0]


def _post(client, msg: dict, secret: str = APP_SECRET):
    _n[0] += 1
    msg = {"from": USER, "id": f"wamid.in.{_n[0]}", "timestamp": "1761500000", **msg}
    payload = {"object": "whatsapp_business_account", "entry": [{"id": "WABA", "changes": [{"field": "messages", "value": {
        "messaging_product": "whatsapp", "metadata": {"display_phone_number": "15550000000", "phone_number_id": PHONE_ID},
        "contacts": [{"wa_id": USER, "profile": {"name": "Test"}}], "messages": [msg]}}]}]}
    raw = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return client.post("/api/whatsapp/webhook", content=raw,
                       headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig})


def _text(client, t):
    r = _post(client, {"type": "text", "text": {"body": t}})
    assert r.status_code == 200, r.text


def _tap(client, wa, title):
    """Taps the option with this title in the last interactive message (button or list row)."""
    chat = wa["mod"]._chats[USER]
    i = chat.options.index(title)
    last = [m for m in wa["sent"] if m["type"] == "interactive"][-1]["interactive"]
    kind = "button_reply" if last["type"] == "button" else "list_reply"
    r = _post(client, {"type": "interactive", "interactive": {"type": kind, kind: {"id": f"opt:{i}", "title": title[:24]}}})
    assert r.status_code == 200, r.text


def test_not_configured_is_honest(client):
    assert client.get("/api/whatsapp/webhook").status_code == 404
    assert client.post("/api/whatsapp/webhook", content=b"{}").status_code == 404
    w = client.get("/api/integrations").json()["whatsapp"]
    assert w["running"] is False and "WHATSAPP_TOKEN" in w["note"]


def test_webhook_verification(client, wa):
    base = "/api/whatsapp/webhook?hub.mode=subscribe&hub.challenge=987654"
    assert client.get(base + "&hub.verify_token=wrong").status_code == 403
    r = client.get(base + f"&hub.verify_token={VERIFY}")
    assert r.status_code == 200 and r.text == "987654"
    bad = f"/api/whatsapp/webhook?hub.mode=subscribe&hub.challenge=<script>&hub.verify_token={VERIFY}"
    assert client.get(bad).status_code == 403


def test_unsigned_or_forged_posts_rejected(client, wa):
    assert client.post("/api/whatsapp/webhook", content=b"{}").status_code == 403
    assert _post(client, {"type": "text", "text": {"body": "hi"}}, secret="not-the-secret").status_code == 403
    assert wa["sent"] == []


def test_full_report_over_whatsapp(client, wa):
    from ubufakazi_server.db import SessionLocal
    from ubufakazi_server.models import Report
    sent = wa["sent"]
    _text(client, "hi")
    assert any(m["type"] == "interactive" for m in sent), "language choice should be an interactive list"
    _tap(client, wa, "English")
    _tap(client, wa, "Online scam / fraudulent job offer")
    _tap(client, wa, "Eastern Cape")
    _tap(client, wa, "Mthatha")
    _tap(client, wa, "Skip")                     # location
    _text(client, "yesterday")
    _text(client, "A recruiter on WhatsApp offered me a job and asked me to pay a training fee of R3 500.")
    r = _post(client, {"type": "image", "image": {"id": "MEDIA-IN-1", "mime_type": "image/png", "caption": ""}})
    assert r.status_code == 200
    assert "SHA-256 fingerprint" in sent[-1]["interactive"]["body"]["text"]
    _tap(client, wa, "Done")
    _text(client, "R3 500")
    _tap(client, wa, "Skip")                     # name
    _tap(client, wa, "Looks right, continue")
    _tap(client, wa, "I agree, submit")
    texts = [m["text"]["body"] for m in sent if m["type"] == "text"]
    done = next(t for t in texts if t.startswith("Report submitted."))
    ref = re.search(r"Reference: (\S+)", done).group(1)
    docs = [m for m in sent if m["type"] == "document"]
    assert docs and docs[-1]["document"]["id"] == "MEDIA-1" and wa["uploads"][-1][0] == f"Ubufakazi-{ref}.pdf"
    assert all(m["to"] == USER for m in sent)
    db = SessionLocal()
    try:
        rep = db.query(Report).filter_by(reference=ref).one()
        assert rep.source == "whatsapp" and rep.contact_channel == "whatsapp"
        assert rep.contact_ref.startswith("wa:") and USER not in rep.contact_ref     # number stored only as a keyed hash
        assert rep.station.code == "MTH"
        assert len(rep.evidence) == 1 and rep.evidence[0].channel == "whatsapp"
    finally:
        db.close()


def test_long_lists_are_numbered_and_numbers_resolve(client, wa):
    _text(client, "/new")
    _tap(client, wa, "English")
    _tap(client, wa, "Online scam / fraudulent job offer")
    _tap(client, wa, "Gauteng")
    last = wa["sent"][-1]
    assert last["type"] == "text" and "Reply with a number" in last["text"]["body"]
    chat = wa["mod"]._chats[USER]
    first_town = chat.options[0]
    _text(client, "1")
    assert chat.conv.data["town"] == first_town


def test_duplicate_deliveries_handled_once(client, wa):
    msg = {"from": USER, "id": "wamid.dup", "type": "text", "text": {"body": "hi"}}
    body = {"entry": [{"changes": [{"value": {"metadata": {"phone_number_id": PHONE_ID}, "messages": [msg]}}]}]}
    raw = json.dumps(body).encode()
    sig = "sha256=" + hmac.new(APP_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    for _ in range(2):
        assert client.post("/api/whatsapp/webhook", content=raw, headers={"X-Hub-Signature-256": sig}).status_code == 200
    assert sum(1 for m in wa["sent"] if m["type"] == "interactive") == 1


def test_stop_explains_chat_cannot_be_deleted(client, wa):
    _text(client, "/new")
    _text(client, "stop")
    assert "delete the chat yourself" in wa["sent"][-1]["text"]["body"]
