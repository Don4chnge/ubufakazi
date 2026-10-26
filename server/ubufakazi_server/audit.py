"""Hash-chained audit log.

Each event stores prev_hash and hash = SHA-256(prev_hash || canonical JSON of the event).
Editing or deleting any past row breaks every later hash, which verify_chain() reports.
There is no API to edit or delete audit events.
"""
from __future__ import annotations

import hashlib
import json
from sqlalchemy.orm import Session

from .db import write_lock
from .models import AuditEvent, utcnow

GENESIS = "0" * 64


def _canonical(ev: AuditEvent) -> str:
    return json.dumps({
        "at": ev.at.isoformat(timespec="microseconds"), "actor_user_id": ev.actor_user_id, "actor": ev.actor,
        "action": ev.action, "target_type": ev.target_type, "target_id": ev.target_id,
        "station_id": ev.station_id, "ip": ev.ip, "detail": ev.detail,
    }, sort_keys=True, separators=(",", ":"), default=str)


def _compute(prev_hash: str, ev: AuditEvent) -> str:
    return hashlib.sha256((prev_hash + _canonical(ev)).encode()).hexdigest()


def record(db: Session, action: str, *, actor: str, actor_user_id: int | None = None, target_type: str = "",
           target_id: str | int = "", station_id: int | None = None, ip: str = "", detail: dict | None = None,
           commit: bool = True) -> AuditEvent:
    with write_lock:
        last = db.query(AuditEvent).order_by(AuditEvent.id.desc()).first()
        prev = last.hash if last else GENESIS
        ev = AuditEvent(at=utcnow(), actor_user_id=actor_user_id, actor=actor, action=action,
                        target_type=target_type, target_id=str(target_id), station_id=station_id, ip=ip,
                        detail=detail or {}, prev_hash=prev, hash="")
        ev.hash = _compute(prev, ev)
        db.add(ev)
        if commit:
            db.commit()
        else:
            db.flush()
        return ev


def verify_chain(db: Session) -> dict:
    prev = GENESIS
    count = 0
    for ev in db.query(AuditEvent).order_by(AuditEvent.id).yield_per(500):
        if ev.prev_hash != prev or _compute(prev, ev) != ev.hash:
            return {"intact": False, "checked": count, "broken_at": ev.id}
        prev = ev.hash
        count += 1
    return {"intact": True, "checked": count, "head": prev}
