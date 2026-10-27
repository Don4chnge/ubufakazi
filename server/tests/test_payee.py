"""Beneficiary check: subscribed banks only, signed and single-use requests, anti-framing, minimal answers."""
from __future__ import annotations

import json
import time

SYN = "1047228359"          # fake-job syndicate mule account (9 victims, several jurisdictions)


def _call(client, payload, bank="utb", sig=None, ts=None):
    from ubufakazi_server import payee
    raw = json.dumps(payload).encode()
    return client.post("/api/v1/beneficiary-check", content=raw, headers={
        "Content-Type": "application/json", "X-UBF-Bank": bank, "X-UBF-Signature": sig or payee.sign(bank, raw, ts)})


def test_syndicate_account_is_high_risk_and_answer_is_minimal(client):
    r = _call(client, {"account_number": SYN, "amount": 1850, "n": 1})
    assert r.status_code == 200
    d = r.json()
    assert d["risk"] == "high" and d["reports"] >= 9 and d["provinces"] >= 6
    assert "account_hmac" not in d and "references" not in json.dumps(d) and SYN not in json.dumps(d)


def test_unknown_account_is_clear_and_single_report_is_only_caution(client, app):
    assert _call(client, {"account_number": "9999000011", "n": 2}).json()["risk"] == "clear"
    from ubufakazi_server.db import SessionLocal
    from ubufakazi_server.models import Identifier
    from sqlalchemy import func
    db = SessionLocal()
    try:   # an account named in exactly one report
        hm = db.query(Identifier.hmac).filter_by(kind="account").group_by(Identifier.hmac).having(func.count() == 1).first()[0]
        value = db.query(Identifier.value).filter_by(kind="account", hmac=hm).first()[0]
    finally:
        db.close()
    d = _call(client, {"account_number": value, "n": 3}).json()
    assert d["risk"] == "caution" and d["reports"] == 1          # one report can never say "do not pay"


def test_only_subscribed_banks_with_valid_fresh_single_use_signatures(client):
    from ubufakazi_server import payee
    assert _call(client, {"account_number": SYN}, bank="scammer").status_code == 401
    assert _call(client, {"account_number": SYN}, sig="t=1,v1=00").status_code == 401
    assert _call(client, {"account_number": SYN, "n": 4}, ts=int(time.time()) - 3600).status_code == 401   # stale
    raw = json.dumps({"account_number": SYN, "n": 5}).encode()
    sig = payee.sign("utb", raw)
    h = {"Content-Type": "application/json", "X-UBF-Bank": "utb", "X-UBF-Signature": sig}
    assert client.post("/api/v1/beneficiary-check", content=raw, headers=h).status_code == 200
    assert client.post("/api/v1/beneficiary-check", content=raw, headers=h).status_code == 401              # replay


def test_bank_app_checks_before_paying_and_board_counts_warnings(login):
    c, me = login("bank.reviewer")
    r = c.post("/api/utb/payment-check", json={"account_number": SYN, "amount": 1650}, headers={"X-CSRF-Token": me["csrf"]})
    assert r.status_code == 200 and r.json()["risk"] == "high"
    a, ame = login("admin")
    b = a.get("/api/police/intel/board").json()
    job = next(s for s in b["syndicates"] if s["scam_type"] == "job")
    assert any(m["warned"] >= 1 for m in job["mules"])
