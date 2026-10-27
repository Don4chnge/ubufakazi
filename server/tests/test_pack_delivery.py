"""Telegram/WhatsApp case pack delivery: answers typed early, /pack, and failed AI reads being retried."""
from __future__ import annotations


def _submit(conv, category):
    conv.data = {"category": category, "language": "en", "province": "Gauteng", "town": "Johannesburg",
                 "station": "x", "description": "Someone keeps sending me threatening messages."}
    conv.step = "consent"
    return conv.handle("I agree, submit")


def test_sensitive_report_pdf_answers(app):
    from ubufakazi_server.conversation import Conversation
    c = Conversation(channel="telegram", contact_ref="tg:1")
    outs = _submit(c, "threats")
    assert c.step == "pack_choice" and "/pack" in outs[0].text and "/track" in outs[0].text
    assert c.handle("hmm")[0].options == ["Yes, send it", "No"]          # unclear: ask again, never assume "no"
    out = c.handle("PDF")[0]                                             # typed before/after the question
    assert out.action == {"type": "send_pack", "reference": c.submitted[-1]}


def test_no_then_pack_later(app):
    from ubufakazi_server.conversation import Conversation
    c = Conversation(channel="telegram", contact_ref="tg:2")
    _submit(c, "threats")
    assert "/pack" in c.handle("No")[0].text and c.step == "submitted"
    assert c.handle("/pack")[0].action["type"] == "send_pack"


def test_failed_ai_read_is_retried_on_reprocess(app, monkeypatch):
    from ubufakazi_server import ai, services
    from ubufakazi_server.db import SessionLocal
    from ubufakazi_server.models import Report
    png = bytes.fromhex("89504e470d0a1a0a") + bytes(64)
    res = services.submit_report(files=[(png, "shot.png", "image/png")], source="web", category="scam", language="en",
                                 province="Gauteng", town="Johannesburg", description="A test of retrying AI reading.",
                                 consent_given=True)
    monkeypatch.setattr(ai, "read_media", lambda d, t: {"ok": False, "text": "", "method": "gemini:x", "note": "busy"})
    services.process_report(res["id"])
    monkeypatch.setattr(ai, "read_media", lambda d, t: {"ok": True, "text": "FOUND: 1047228359", "method": "gemini:x",
                                                        "note": "AI-generated"})
    services.process_report(res["id"])
    db = SessionLocal()
    try:
        ders = db.get(Report, res["id"]).evidence[0].derivatives
        assert [d.kind for d in ders] == ["ai-extract"] and ders[0].ai_generated
    finally:
        db.close()
