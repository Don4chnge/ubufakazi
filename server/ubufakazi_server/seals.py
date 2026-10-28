"""Sealed documents (OWASP A08:2025 integrity; ISO/IEC 27037 preservation; NIST SP 800-86 reporting).

Every case pack Ubufakazi issues gets a seal: a random, unguessable seal id printed on the PDF with a QR code, the
SHA-256 of the exact PDF bytes, and (when configured) an RFC 3161 timestamp from an independent authority. Anyone
holding the PDF can check it on /verify: the browser computes the PDF's fingerprint and compares it with the seal.
Changing a single character of the file breaks the match, so edited or forged police paperwork is caught.
"""
from __future__ import annotations

import hashlib
import secrets
import threading

from .db import session_scope, write_lock

SYNC = False


def new_seal(doc_type: str, reference: str, issued_to: str, station_id: int | None) -> str:
    from .models import DocumentSeal
    sid = "SEAL-" + secrets.token_hex(8).upper()
    with write_lock, session_scope() as db:
        db.add(DocumentSeal(seal_id=sid, doc_type=doc_type, reference=reference, issued_to=issued_to[:60],
                            station_id=station_id))
    return sid


def finish(seal_id: str, pdf: bytes) -> str:
    from . import audit
    from .models import DocumentSeal
    digest = hashlib.sha256(pdf).hexdigest()
    with write_lock, session_scope() as db:
        s = db.query(DocumentSeal).filter_by(seal_id=seal_id).one()
        s.sha256, s.size = digest, len(pdf)
        audit.record(db, "document.sealed", actor="system", target_type="report", target_id=s.reference,
                     station_id=s.station_id, detail={"seal": seal_id, "sha256": digest, "type": s.doc_type}, commit=False)
    (threading.Thread(target=_timestamp, args=(seal_id, digest), daemon=True).start() if not SYNC else _timestamp(seal_id, digest))
    return digest


def _timestamp(seal_id: str, digest: str) -> None:
    from . import timestamps
    from .models import DocumentSeal
    token = timestamps.stamp_quietly(digest)
    if token:
        with write_lock, session_scope() as db:
            db.query(DocumentSeal).filter_by(seal_id=seal_id).update({"trusted_timestamp": token})


LABEL = {"case_pack_police": "Case pack · bank fraud desk copy", "case_pack_complainant": "Case pack · complainant copy"}


def public(s) -> dict:
    from . import timestamps
    return {"seal_id": s.seal_id, "document": LABEL.get(s.doc_type, s.doc_type), "reference": s.reference,
            "issued_at": s.issued_at.isoformat() + "Z", "issued_to": "a bank fraud investigator" if s.issued_to.startswith("officer")
            or s.issued_to.startswith("admin") else "the complainant", "sha256": s.sha256, "size": s.size,
            "timestamp": timestamps.public_info(s.trusted_timestamp)}
