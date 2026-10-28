"""Beneficiary check: before a bank customer pays a NEW beneficiary, the bank asks Ubufakazi whether that account is
named in scam reports, and warns the customer. It stops the next victim instead of only recording the last one.

Security design (OWASP Top 10:2025 A01/A04/A06/A07/A09, OWASP API security):
- Only subscribed banks can ask. Each bank has its own key (derived from the server secret, never shared between
  banks); every request is HMAC-signed over a timestamp, the bank id and the exact body.
- Replay protection: requests older than 5 minutes are refused, and each signature is accepted once.
- Anti-framing: one report can never produce "do not pay". "High" needs several victims in at least two station
  jurisdictions, or the account's own bank having frozen it. A single report only gives "caution".
- Anti-enumeration and minimisation: the answer is a risk level and counts only (no victims, references, stations,
  amounts or report text). Each bank has an hourly quota, and unusual lookup volumes raise a security alert.
- Every lookup is written to the hash-chained audit log, without the account number.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import threading
import time

from sqlalchemy import func

from .config import get_settings

WINDOW_SECONDS = 300
SUBSCRIBERS = {     # bank id -> (name, plan, lookups per hour). A real deployment keeps this in the database.
    "utb": ("Ubuntu Trust Bank", "Bank plan (demo)", 300),
}
UNUSUAL_DISTINCT_PER_10_MIN = 40
_seen: dict[str, float] = {}
_seen_lock = threading.Lock()


class CheckRefused(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


# ------------------------------------------------------------------------------------------------ keys & signing
def bank_key(bank_id: str) -> bytes:
    return hmac.new(get_settings().secret_key.encode(), f"beneficiary-check-key:{bank_id}".encode(),
                    hashlib.sha256).hexdigest().encode()


def sign(bank_id: str, raw: bytes, ts: int | None = None) -> str:
    ts = int(ts if ts is not None else time.time())
    mac = hmac.new(bank_key(bank_id), f"{ts}.{bank_id}.".encode() + raw, hashlib.sha256).hexdigest()
    return f"t={ts},v1={mac}"


def _verify(bank_id: str, raw: bytes, header: str | None) -> bool:
    try:
        parts = dict(p.split("=", 1) for p in (header or "").split(","))
        ts = int(parts["t"])
    except (ValueError, KeyError):
        return False
    if abs(time.time() - ts) > WINDOW_SECONDS:
        return False
    expected = hmac.new(bank_key(bank_id), f"{ts}.{bank_id}.".encode() + raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, parts.get("v1", "")):
        return False
    with _seen_lock:                                     # each signature is accepted once (replay protection)
        now = time.time()
        for k in [k for k, t in _seen.items() if now - t > WINDOW_SECONDS * 2]:
            _seen.pop(k, None)
        if expected in _seen:
            return False
        _seen[expected] = now
    return True


# ------------------------------------------------------------------------------------------------ assessment
def assess(db, account_number: str) -> dict:
    from .models import BankAlert, BankDelivery, Identifier, Report
    from .security import identifier_hmac
    digits = "".join(ch for ch in account_number if ch.isdigit())
    hm = identifier_hmac("account", digits)
    from .aiguard import untrusted
    rows = (db.query(Report, Identifier.source).join(Identifier, Identifier.report_id == Report.id)
            .filter(Identifier.kind == "account", Identifier.hmac == hm).all())
    trusted = {r.id: r for r, src in rows if not untrusted(src)}
    # AI-only / injection-flagged readings count only once a trusted reading of the same account exists
    reps = list({r.id: r for r, src in rows}.values()) if trusted else []
    n = len(reps)
    stations = {r.station_id for r in reps}
    provinces = {r.province for r in reps if r.province}
    al = db.query(BankAlert).filter_by(account_hmac=hm).first()
    dl = db.query(BankDelivery).filter_by(alert_id=al.id).first() if al else None
    frozen = bool(dl and dl.bank_status == "frozen")
    last = max((r.created_at for r in reps), default=None)
    pv = f"{len(provinces)} province{'s' if len(provinces) != 1 else ''}"
    if n == 0:
        risk, headline = "clear", "No scam reports name this account."
        advice = "No reports is not a guarantee. Only pay people and businesses you have verified yourself."
    elif frozen or (n >= 3 and len(stations) >= 2):
        risk, headline = "high", f"Named in {n} scam reports by different victims in {pv}."
        advice = ("Do not pay. This account matches a pattern used by scam syndicates"
                  + (" and its bank has frozen it." if frozen else ".") + " If someone is pressuring you to pay, stop and call your bank.")
    elif n >= 2:
        risk, headline = "warning", f"Named in {n} scam reports."
        advice = "Be very careful. Confirm who owns this account before paying, using contact details you found yourself."
    else:
        risk, headline = "caution", "Named in 1 unverified scam report."
        advice = "Check carefully before paying. One report alone does not prove this account is used for fraud."
    return {"risk": risk, "headline": headline, "advice": advice, "reports": n, "provinces": len(provinces),
            "jurisdictions": len(stations), "frozen_by_its_bank": frozen,
            "last_report_month": last.strftime("%B %Y") if last else None, "account_hmac": hm,
            "rule": "'High' needs several victims in at least two station jurisdictions, or the account frozen by its "
                    "own bank, so one false report can never block an innocent account."}


# ------------------------------------------------------------------------------------------------ the API
def handle(raw: bytes, headers) -> dict:
    """Ubufakazi's beneficiary-check API. `headers` is any mapping. Raises CheckRefused."""
    from . import audit
    from .db import session_scope, write_lock
    from .models import BeneficiaryCheck, utcnow
    h = {str(k).lower(): v for k, v in dict(headers).items()}
    bank_id = (h.get("x-ubf-bank") or "").strip().lower()
    if bank_id not in SUBSCRIBERS or len(raw) > 4000 or not _verify(bank_id, raw, h.get("x-ubf-signature")):
        with write_lock, session_scope() as db:
            audit.record(db, "beneficiary.refused", actor=f"bank:{bank_id[:20] or 'unknown'}",
                         detail={"reason": "unknown bank or bad signature"})
        raise CheckRefused(401, "Not a subscribed bank, or the request signature is invalid or reused.")
    try:
        body = json.loads(raw)
        number = "".join(ch for ch in str(body.get("account_number", "")) if ch.isdigit())
        amount = float(body["amount"]) if body.get("amount") not in (None, "") else None
    except (ValueError, TypeError, AttributeError):
        raise CheckRefused(400, "Bad request.")
    if not 6 <= len(number) <= 16:
        raise CheckRefused(400, "account_number must be 6 to 16 digits.")
    name, plan, quota = SUBSCRIBERS[bank_id]
    since = utcnow() - dt.timedelta(hours=1)
    with write_lock, session_scope() as db:
        used = db.query(func.count(BeneficiaryCheck.id)).filter(BeneficiaryCheck.bank_id == bank_id,
                                                                BeneficiaryCheck.at >= since).scalar() or 0
        if used >= quota:
            audit.record(db, "beneficiary.quota_exceeded", actor=f"bank:{bank_id}", detail={"quota_per_hour": quota})
    if used >= quota:
        raise CheckRefused(429, "Hourly lookup quota reached for this bank.")
    with write_lock, session_scope() as db:
        res = assess(db, number)
        chk = BeneficiaryCheck(bank_id=bank_id, account_hmac=res["account_hmac"], risk=res["risk"],
                               reports=res["reports"], amount=amount)
        db.add(chk)
        db.flush()
        audit.record(db, "beneficiary.checked", actor=f"bank:{bank_id}", target_type="beneficiary_check",
                     target_id=chk.id, detail={"risk": res["risk"], "reports": res["reports"]}, commit=False)
        recent = db.query(func.count(func.distinct(BeneficiaryCheck.account_hmac))).filter(
            BeneficiaryCheck.bank_id == bank_id,
            BeneficiaryCheck.at >= utcnow() - dt.timedelta(minutes=10)).scalar() or 0
        if recent > UNUSUAL_DISTINCT_PER_10_MIN:
            audit.record(db, "security.alert", actor="system", detail={"type": "beneficiary_lookup_volume",
                         "bank": bank_id, "distinct_accounts_10_min": recent}, commit=False)
        out = {k: v for k, v in res.items() if k != "account_hmac"}
        out.update({"check_id": f"BC-{chk.id:06d}", "bank": name, "plan": plan, "quota_left_this_hour": quota - used - 1})
    return out


def warned_counts(db) -> dict[str, int]:
    """account hmac -> how many payment attempts were warned (risk warning/high)."""
    from .models import BeneficiaryCheck
    rows = (db.query(BeneficiaryCheck.account_hmac, func.count(BeneficiaryCheck.id))
            .filter(BeneficiaryCheck.risk.in_(("warning", "high"))).group_by(BeneficiaryCheck.account_hmac).all())
    return dict(rows)


# ------------------------------------------------------------------------------------------------ the bank's client
def client_check(bank_id: str, account_number: str, amount: float | None) -> tuple[int, dict]:
    """How a subscribed bank calls the API (used by the fictional Ubuntu Trust Bank)."""
    from . import banklink
    import secrets
    raw = json.dumps({"account_number": account_number, "amount": amount, "sent_at": int(time.time()),
                      "nonce": secrets.token_hex(8)},          # identical checks in the same second stay distinct
                     separators=(",", ":"), sort_keys=True).encode()
    return banklink._post(f"{banklink._local_base()}/api/v1/beneficiary-check", raw,
                          {"Content-Type": "application/json", "X-UBF-Bank": bank_id,
                           "X-UBF-Signature": sign(bank_id, raw)})
