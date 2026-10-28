"""Security alert centre (OWASP A09:2025 security logging and alerting).

Alerts are derived from the hash-chained audit log, so they cannot be quietly removed: brute-force logins, locked
accounts, rejected bank-API signatures, beneficiary-check abuse, prompt-injection attempts in evidence, bulk access to
evidence, and the integrity of the audit chain itself.
"""
from __future__ import annotations

import datetime as dt
from collections import Counter, defaultdict

from sqlalchemy.orm import Session

from .models import AuditEvent, utcnow

RULES = {
    "login.locked": ("medium", "Account locked after repeated failed sign-ins"),
    "login.mfa_failed": ("low", "Wrong two-factor code"),
    "beneficiary.refused": ("high", "Rejected beneficiary-check call (unknown bank or bad / reused signature)"),
    "beneficiary.quota_exceeded": ("medium", "A bank reached its hourly beneficiary-check quota"),
    "bank.signature_rejected": ("high", "Rejected bank API message (bad signature)"),
    "security.prompt_injection_suspected": ("high", "Possible prompt injection in submitted evidence"),
    "security.alert": ("high", "Unusual beneficiary-check volume from a bank"),
}
SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _window(evs, minutes, threshold, key):
    """Groups events by key; returns groups with >= threshold events inside any `minutes` window."""
    out = []
    groups = defaultdict(list)
    for e in evs:
        groups[key(e)].append(e.at)
    for k, times in groups.items():
        times.sort()
        lo = 0
        for hi in range(len(times)):
            while times[hi] - times[lo] > dt.timedelta(minutes=minutes):
                lo += 1
            if hi - lo + 1 >= threshold:
                out.append((k, hi - lo + 1, times[hi]))
                break
    return out


def alerts(db: Session, days: int = 7) -> dict:
    from . import audit, ai
    since = utcnow() - dt.timedelta(days=days)
    evs = db.query(AuditEvent).filter(AuditEvent.at >= since).order_by(AuditEvent.id).all()
    out = []
    for e in evs:
        if e.action in RULES:
            sev, title = RULES[e.action]
            out.append({"severity": sev, "title": title, "at": e.at.isoformat() + "Z", "actor": e.actor,
                        "target": f"{e.target_type}:{e.target_id}" if e.target_type else "", "detail": e.detail or {},
                        "rule": e.action})
    fails = [e for e in evs if e.action in ("login.failed", "login.mfa_failed")]
    for (actor, ip), n, last in _window(fails, 10, 5, lambda e: (e.actor, e.ip or "")):
        out.append({"severity": "high", "title": f"Possible password guessing: {n} failed sign-ins in 10 minutes",
                    "at": last.isoformat() + "Z", "actor": actor, "target": f"ip:{ip}" if ip else "", "detail": {},
                    "rule": "brute_force"})
    reads = [e for e in evs if e.action in ("evidence.previewed", "pack.police", "evidence.timestamp_downloaded")]
    for actor, n, last in _window(reads, 10, 25, lambda e: e.actor):
        out.append({"severity": "medium", "title": f"Bulk access to evidence: {n} files or packs in 10 minutes",
                    "at": last.isoformat() + "Z", "actor": actor, "target": "", "detail": {}, "rule": "bulk_access"})
    chain = audit.verify_chain(db)
    if not chain["intact"]:
        out.append({"severity": "critical", "title": f"Audit log chain BROKEN at event {chain['broken_at']}: history was changed",
                    "at": utcnow().isoformat() + "Z", "actor": "system", "target": "", "detail": chain, "rule": "audit_chain"})
    out.sort(key=lambda a: (SEV_ORDER[a["severity"]], a["at"]), reverse=False)
    out.sort(key=lambda a: a["at"], reverse=True)
    out.sort(key=lambda a: SEV_ORDER[a["severity"]])
    counts = Counter(a["severity"] for a in out)
    return {"since": since.isoformat() + "Z", "alerts": out[:200], "counts": dict(counts), "audit_chain": chain,
            "ai_usage": ai.usage(), "events_checked": len(evs)}
