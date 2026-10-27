"""Ubufakazi's link to a bank's fraud team, over a signed HTTP API.

The only bank connected is Ubuntu Trust Bank, a FICTIONAL bank that runs inside this demo (see utb.py) so the
integration can be shown end to end. No real bank is contacted.

What the bank receives for a reported receiving account: the account number (it is the bank's own account, and the
bank needs it to act), how many separate reports name it, amounts and dates, provinces and scam types.
Never: victims' names, phone numbers, statements, report references or evidence.

Both directions are signed:  X-UBF-Signature: t=<unix time>,v1=<HMAC-SHA256(shared secret, "<t>." + body)>
and rejected when older than 5 minutes (replay protection).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import logging
import os
import threading
import time

import httpx
from sqlalchemy import func

from .config import get_settings

log = logging.getLogger("ubufakazi.banklink")
BANK_NAME = "Ubuntu Trust Bank"
ROUTED_BANKS = {BANK_NAME}             # stated banks whose accounts are sent to the connected bank
WINDOW_SECONDS = 300
SYNC = False                           # tests: deliver in the calling thread
STATE = {"delivered": 0, "responses": 0, "last_ok_at": None, "last_error": None}
STATUS_LABELS = {"received": "Received by the bank", "investigating": "Under investigation by the bank",
                 "frozen": "Account frozen by the bank", "released": "Freeze lifted by the bank",
                 "no_match": "Not an account at this bank", "closed": "Closed by the bank"}


# ------------------------------------------------------------------------------------------------- signing
def shared_secret() -> bytes:
    s = get_settings()
    if s.utb_shared_secret:
        return s.utb_shared_secret.encode()
    return hmac.new(s.secret_key.encode(), b"ubuntu-trust-bank-link", hashlib.sha256).hexdigest().encode()


def sign(raw: bytes, ts: int | None = None) -> str:
    ts = int(ts if ts is not None else time.time())
    mac = hmac.new(shared_secret(), f"{ts}.".encode() + raw, hashlib.sha256).hexdigest()
    return f"t={ts},v1={mac}"


def verify(raw: bytes, header: str | None) -> bool:
    try:
        parts = dict(p.split("=", 1) for p in (header or "").split(","))
        ts = int(parts["t"])
    except (ValueError, KeyError):
        return False
    if abs(time.time() - ts) > WINDOW_SECONDS:
        return False
    expected = hmac.new(shared_secret(), f"{ts}.".encode() + raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, parts.get("v1", ""))


def _local_base() -> str:
    """The built-in fictional bank runs in this server: reach it over HTTP on the server's own port, so delivery
    does not depend on the public address (which, during a deploy, may still point at the previous instance)."""
    port = os.environ.get("PORT")
    return f"http://127.0.0.1:{port}" if port else get_settings().public_base_url


def api_url() -> str:
    s = get_settings()
    return s.utb_api_url or f"{_local_base()}/utb/api/v1"


def callback_url() -> str:
    s = get_settings()
    return f"{s.public_base_url if s.utb_api_url else _local_base()}/api/bank-link/callback"


def _post(url: str, raw: bytes, headers: dict) -> tuple[int, dict]:
    """The HTTP call (tests replace this to route to the bank in-process)."""
    r = httpx.post(url, content=raw, headers=headers, timeout=20)
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, {}


def post_signed(url: str, payload: dict) -> tuple[int, dict]:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return _post(url, raw, {"Content-Type": "application/json", "X-UBF-Signature": sign(raw)})


# ------------------------------------------------------------------------------------------------- outgoing alerts
def build_payload(db, alert) -> dict | None:
    from .extract import TYPE_LABEL
    from .models import Identifier, IntelMatch, Report
    ident = db.query(Identifier).filter_by(kind="account", hmac=alert.account_hmac).first()
    if ident is None:
        return None
    reps = (db.query(Report).join(Identifier, Identifier.report_id == Report.id)
            .filter(Identifier.kind == "account", Identifier.hmac == alert.account_hmac)
            .order_by(Report.created_at).distinct().all())
    ids = [r.id for r in reps]
    corroborated = db.query(func.count(IntelMatch.id)).filter(
        IntelMatch.report_a.in_(ids or [-1]), IntelMatch.report_b.in_(ids or [-1]),
        IntelMatch.strength == "corroborated").scalar() or 0
    # Deliberately no names, references, phone numbers, statements or evidence.
    return {"alert_id": alert.id, "account_number": ident.value, "bank_stated": alert.bank_stated or "",
            "reports": len(reps), "total_reported": round(sum(r.amount_paid or 0 for r in reps), 2),
            "provinces": sorted({r.province for r in reps if r.province}),
            "scam_types": sorted({TYPE_LABEL.get(r.scam_type or "", "Other") for r in reps if r.scam_type}),
            "first_report": reps[0].created_at.date().isoformat() if reps else None,
            "last_report": reps[-1].created_at.date().isoformat() if reps else None,
            "timeline": [{"date": r.created_at.date().isoformat(), "amount": r.amount_paid} for r in reps],
            "corroborated_links": corroborated, "callback_url": callback_url()}


def deliver(alert_id: int) -> bool:
    """Sends (or re-sends, if the picture changed) one alert. Never raises."""
    from .db import session_scope, write_lock
    from .models import BankAlert, BankDelivery
    from . import audit
    with write_lock, session_scope() as db:
        a = db.get(BankAlert, alert_id)
        if a is None or (a.bank_stated or "") not in ROUTED_BANKS:
            return False
        payload = build_payload(db, a)
        if payload is None:
            return False
        digest = hashlib.sha256(json.dumps({k: v for k, v in payload.items() if k != "callback_url"},
                                           sort_keys=True).encode()).hexdigest()
        d = db.query(BankDelivery).filter_by(alert_id=a.id).first()
        if d and d.payload_hash == digest and d.delivered_at:
            return True                                   # nothing new to tell the bank
    try:
        status, body = post_signed(f"{api_url()}/fraud-alerts", {**payload, "sent_at": _now()})
        error = None if status in (200, 201, 202) else f"the bank answered HTTP {status}"
    except httpx.HTTPError as e:
        status, body, error = 0, {}, f"could not reach the bank ({type(e).__name__})"
    with write_lock, session_scope() as db:
        d = db.query(BankDelivery).filter_by(alert_id=alert_id).first()
        if d is None:
            d = BankDelivery(alert_id=alert_id, bank=BANK_NAME)
            db.add(d)
        d.attempts = (d.attempts or 0) + 1
        if error:
            d.last_error = error[:300]
            STATE["last_error"] = error
            log.warning("bank delivery failed for alert %s: %s", alert_id, error)
            return False
        d.payload_hash, d.delivered_at, d.last_error = digest, _utcnow(), None
        d.bank_case_ref = body.get("case_ref") or d.bank_case_ref
        if body.get("status"):
            d.bank_status, d.bank_updated_at = body["status"], _utcnow()
            d.bank_note = (body.get("note") or "")[:300]
        audit.record(db, "bank.alert_sent", actor="system", target_type="bank_alert", target_id=alert_id,
                     detail={"bank": BANK_NAME, "case_ref": d.bank_case_ref, "reports": payload["reports"]}, commit=False)
    STATE["delivered"] += 1
    STATE["last_ok_at"], STATE["last_error"] = _now(), None
    return True


def deliver_for_report(report_id: int) -> None:
    """Never raises: a bank problem must not affect the report itself."""
    from .db import session_scope
    from .models import BankAlert, Identifier
    try:
        with session_scope() as db:
            hmacs = [h for (h,) in db.query(Identifier.hmac).filter_by(report_id=report_id, kind="account")]
            ids = [a.id for a in db.query(BankAlert).filter(BankAlert.account_hmac.in_(hmacs or ["-"]))]
        for i in ids:
            deliver(i)
    except Exception as e:                                  # noqa: BLE001
        STATE["last_error"] = f"delivery failed ({type(e).__name__})"
        log.exception("bank delivery failed for report %s", report_id)


def keep_delivering(first_delay: float = 5, every: float = 600) -> None:
    """Background loop: deliver anything the bank has not received yet (after a deploy, after a network hiccup)."""
    time.sleep(first_delay)
    while True:
        try:
            deliver_pending()
        except Exception as e:                              # noqa: BLE001
            STATE["last_error"] = f"retry loop: {type(e).__name__}"
            log.exception("bank delivery retry failed")
        time.sleep(every)


def deliver_pending() -> int:
    """Backfill: send every routed alert the bank has not seen yet, or whose picture changed (deliver() skips the
    rest), e.g. after new reports or a demo-data refresh."""
    from .db import session_scope
    from .models import BankAlert
    with session_scope() as db:
        todo = [a.id for a in db.query(BankAlert).filter(BankAlert.bank_stated.in_(ROUTED_BANKS))]
    return sum(1 for i in todo if deliver(i))


_backfill_lock = threading.Lock()


def backfill_soon() -> None:
    """Start one background backfill unless one is already running (used when the bank console looks empty)."""
    if not _backfill_lock.acquire(blocking=False):
        return

    def _run():
        try:
            deliver_pending()
        finally:
            _backfill_lock.release()
    run_later(_run)


def run_later(fn, *args) -> None:
    if SYNC:
        fn(*args)
    else:
        threading.Thread(target=fn, args=args, daemon=True).start()


# ------------------------------------------------------------------------------------------------- bank responses
def receive_callback(raw: bytes, header: str | None) -> dict:
    """The bank tells Ubufakazi what it did. Raises PermissionError / ValueError."""
    from .db import session_scope, write_lock
    from .models import BankDelivery
    from . import audit
    if not verify(raw, header):
        raise PermissionError("bad signature")
    body = json.loads(raw)
    status = body.get("status")
    if status not in STATUS_LABELS:
        raise ValueError("unknown status")
    with write_lock, session_scope() as db:
        d = db.query(BankDelivery).filter_by(alert_id=int(body.get("alert_id", 0))).first()
        if d is None:
            raise ValueError("unknown alert")
        d.bank_status, d.bank_note = status, str(body.get("note") or "")[:300]
        d.bank_case_ref = str(body.get("case_ref") or d.bank_case_ref or "")[:40]
        d.bank_updated_at = _utcnow()
        audit.record(db, "bank.response_received", actor=f"bank:{BANK_NAME}", target_type="bank_alert",
                     target_id=d.alert_id, detail={"status": status, "case_ref": d.bank_case_ref}, commit=False)
    STATE["responses"] += 1
    return {"ok": True}


def responses_for_report(db, report) -> list[dict]:
    from .extract import mask_acc
    from .models import BankAlert, BankDelivery
    out = []
    for i in report.identifiers:
        if i.kind != "account":
            continue
        a = db.query(BankAlert).filter_by(account_hmac=i.hmac).first()
        d = db.query(BankDelivery).filter_by(alert_id=a.id).first() if a else None
        if d is None or not d.delivered_at:
            continue
        out.append({"account": mask_acc(i.value), "bank": d.bank, "case_ref": d.bank_case_ref,
                    "status": d.bank_status or "received",
                    "status_label": STATUS_LABELS.get(d.bank_status or "received", d.bank_status),
                    "note": d.bank_note or "", "at": (d.bank_updated_at or d.delivered_at).isoformat() + "Z"})
    return out


def status(db) -> dict:
    from .models import BankDelivery
    n = db.query(func.count(BankDelivery.id)).filter(BankDelivery.delivered_at.isnot(None)).scalar() or 0
    answered = db.query(func.count(BankDelivery.id)).filter(
        BankDelivery.bank_status.isnot(None), BankDelivery.bank_status != "received").scalar() or 0
    if not n:
        note = (f"Link to {BANK_NAME} (a fictional bank) is set up but no alert has been delivered yet."
                + (f" Last problem: {STATE['last_error']}" if STATE["last_error"] else ""))
        return {"connected": False, "note": note}
    note = (f"Connected to {BANK_NAME}, a fictional bank, over a signed API (HMAC-SHA256, 5-minute replay window). "
            f"{n} account alert(s) delivered and acknowledged; the bank has decided on {answered}. The bank receives account "
            "numbers, counts, amounts and dates only: never victims' names, statements or references.")
    if STATE["last_error"]:
        note += f" Last problem: {STATE['last_error']}"
    return {"connected": True, "note": note}


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)      # naive UTC, like the rest of the database


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
