"""Ubuntu Trust Bank: a FICTIONAL bank, built so the bank integration can be demonstrated end to end.

It has its own (fictional) account register and fraud-case inbox, and it only talks to Ubufakazi over the
signed API in banklink.py: alerts come in at /utb/api/v1/fraud-alerts, and every decision its fraud team takes
is reported back to Ubufakazi's callback. Customers are identified by a customer reference only; there are no
names, and nothing here is a real bank, account or person.
"""
from __future__ import annotations

import datetime as dt
import json
import random

from . import banklink
from .db import session_scope, write_lock
from .extract import mask_acc

NAME = banklink.BANK_NAME
STATUS = {"received": "New alert", "investigating": "Under investigation", "frozen": "Account frozen",
          "released": "Freeze lifted", "no_match": "Not our account", "closed": "Closed"}
ACTIONS = {   # action -> (new case status, new account status or None, message sent back to Ubufakazi)
    "investigate": ("investigating", None, "The bank's fraud team is investigating the receiving account."),
    "freeze": ("frozen", "frozen", "The receiving account has been frozen pending investigation."),
    "release": ("released", "active", "The bank lifted the freeze after its investigation."),
    "close": ("closed", None, "The bank closed its fraud case for this account."),
}

# Accounts named in the synthetic demo data and in the demo evidence kit, plus filler accounts.
KNOWN = ["1047228359", "5530187264", "5530199012", "7718203345", "2290118476"]


def seed_registry(db) -> int:
    """Creates the bank's fictional account register once (idempotent)."""
    from .models import UtbAccount
    if db.query(UtbAccount).first():
        return 0
    from .seed import _rows
    rng = random.Random(4242)
    # The fictional world is shared: accounts that the synthetic reports say are at this bank exist here too.
    synthetic = [a for row in _rows() if row["bank"] == NAME for a in row["acc"]]
    numbers = list(dict.fromkeys(KNOWN + synthetic + ["".join(str(rng.randint(0, 9)) for _ in range(10))
                                                      for _ in range(20)]))
    for n, num in enumerate(numbers):
        db.add(UtbAccount(number=num, customer_ref=f"UTB-C-{10421 + n * 7}",
                          product=rng.choice(["Everyday account", "Savings account", "Business account"]),
                          balance=round(rng.uniform(1500, 95000), 2),
                          opened_at=dt.datetime(2024, 1, 1) + dt.timedelta(days=rng.randint(0, 600))))
    db.flush()
    return len(numbers)


def _event(db, case, action, by, note=""):
    from .models import UtbEvent
    db.add(UtbEvent(case_id=case.id, action=action, by=by, note=note[:300]))


def receive_alert(raw: bytes, header: str | None) -> dict:
    """The bank's public API. Raises PermissionError (bad signature) or ValueError (bad body)."""
    from .models import UtbAccount, UtbCase
    if not banklink.verify(raw, header):
        raise PermissionError("bad signature")
    body = json.loads(raw)
    num = "".join(ch for ch in str(body.get("account_number", "")) if ch.isdigit())
    alert_id = int(body.get("alert_id", 0))
    if not (6 <= len(num) <= 16) or alert_id <= 0:
        raise ValueError("account_number and alert_id are required")
    summary = {k: body.get(k) for k in ("reports", "total_reported", "provinces", "scam_types", "first_report",
                                         "last_report", "timeline", "corroborated_links", "bank_stated")}
    with write_lock, session_scope() as db:
        seed_registry(db)
        acct = db.query(UtbAccount).filter_by(number=num).first()
        case = db.query(UtbCase).filter_by(source_alert_id=alert_id).first()
        if case is None:
            case = UtbCase(case_ref="", source_alert_id=alert_id, account_number=num,
                           account_id=acct.id if acct else None, summary=summary,
                           status="received" if acct else "no_match",
                           callback_url=str(body.get("callback_url") or "")[:300])
            db.add(case)
            db.flush()
            case.case_ref = f"UTB-FC-{100200 + case.id}"
            _event(db, case, "alert.received", "Ubufakazi API", f"{summary.get('reports')} report(s)")
            if acct is None:
                _event(db, case, "no_match", "system", "No Ubuntu Trust Bank account with this number.")
        else:
            case.summary = summary
            if case.status in ("closed", "released") and acct is not None:
                case.status = "received"          # new reports re-open a closed case
            _event(db, case, "alert.updated", "Ubufakazi API", f"{summary.get('reports')} report(s)")
        ref, st = case.case_ref, case.status
    note = "" if st != "no_match" else "No account with this number is held at Ubuntu Trust Bank."
    return {"case_ref": ref, "status": st, "note": note}


def _priority(n: int) -> str:
    return "high" if n >= 5 else "medium" if n >= 2 else "low"


def case_row(db, c) -> dict:
    from .models import UtbAccount
    acct = db.get(UtbAccount, c.account_id) if c.account_id else None
    s = c.summary or {}
    return {"id": c.id, "case_ref": c.case_ref, "account": mask_acc(c.account_number),
            "account_status": acct.status if acct else None, "matched": acct is not None,
            "reports": s.get("reports") or 0, "total_reported": s.get("total_reported") or 0,
            "first_report": s.get("first_report"), "last_report": s.get("last_report"),
            "priority": _priority(s.get("reports") or 0), "status": c.status,
            "status_label": STATUS.get(c.status, c.status), "updated_at": c.updated_at.isoformat() + "Z"}


def case_detail(db, c) -> dict:
    from .models import UtbAccount, UtbEvent
    acct = db.get(UtbAccount, c.account_id) if c.account_id else None
    s = c.summary or {}
    return {**case_row(db, c), "provinces": s.get("provinces") or [], "scam_types": s.get("scam_types") or [],
            "timeline": s.get("timeline") or [], "corroborated_links": s.get("corroborated_links") or 0,
            "account_detail": {"customer_ref": acct.customer_ref, "product": acct.product, "balance": acct.balance,
                               "status": acct.status, "opened": acct.opened_at.date().isoformat()} if acct else None,
            "events": [{"at": e.at.isoformat() + "Z", "action": e.action, "by": e.by, "note": e.note}
                       for e in db.query(UtbEvent).filter_by(case_id=c.id).order_by(UtbEvent.id)],
            "actions": [a for a, (st, _, _) in ACTIONS.items() if acct is not None and st != c.status]}


def act(case_id: int, action: str, by: str) -> dict:
    """A decision by the bank's fraud team, then reported back to Ubufakazi (signed)."""
    from .models import UtbAccount, UtbCase
    if action not in ACTIONS:
        raise ValueError("Unknown action.")
    new_status, acct_status, message = ACTIONS[action]
    with write_lock, session_scope() as db:
        c = db.get(UtbCase, case_id)
        if c is None:
            raise LookupError("Not found.")
        if c.account_id is None:
            raise ValueError("This number is not an Ubuntu Trust Bank account.")
        c.status = new_status
        if acct_status:
            db.get(UtbAccount, c.account_id).status = acct_status
        _event(db, c, action, by, message)
        callback = {"alert_id": c.source_alert_id, "case_ref": c.case_ref, "status": new_status, "note": message,
                    "at": banklink._now()}
        url = c.callback_url
    banklink.run_later(_send_callback, url, callback, case_id)
    return {"status": new_status, "status_label": STATUS[new_status]}


def _send_callback(url: str, payload: dict, case_id: int) -> None:
    from .models import UtbCase
    if not url:
        return
    try:
        status, _ = banklink.post_signed(url, payload)
        note = "Ubufakazi acknowledged" if status == 200 else f"Ubufakazi answered HTTP {status}"
    except Exception as e:                                # network problems are recorded, not raised
        note = f"could not reach Ubufakazi ({type(e).__name__})"
    with write_lock, session_scope() as db:
        c = db.get(UtbCase, case_id)
        if c is not None:
            _event(db, c, "callback.sent", "system", f"{payload['status']}: {note}")
