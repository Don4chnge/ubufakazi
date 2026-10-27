"""Relational data model for Ubufakazi 2.0.

Sensitive report data (reports, evidence, identifiers, notes) is separated from
accounts and stations. Every report belongs to exactly one station; the API
enforces station membership on every query (see police.py: scope_reports).
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy import (JSON, Boolean, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text,
                        UniqueConstraint, Index, DDL, event)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


# ------------------------------------------------------------------ accounts and stations
ROLES = ("admin", "officer", "bank_reviewer")


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20))
    password_hash: Mapped[str] = mapped_column(String(255))
    totp_secret: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[Optional[dt.datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    stations: Mapped[list["Station"]] = relationship(secondary="station_memberships", lazy="selectin")


class Station(Base):
    """Fictional demonstration stations. Never presented as real SAPS stations."""
    __tablename__ = "stations"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(12), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    province: Mapped[str] = mapped_column(String(60))
    towns: Mapped[list] = mapped_column(JSON, default=list)


class StationMembership(Base):
    __tablename__ = "station_memberships"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id", ondelete="CASCADE"), primary_key=True)


class LoginSession(Base):
    __tablename__ = "login_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    mfa_pending: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime)
    ip: Mapped[str] = mapped_column(String(64), default="")
    user: Mapped[User] = relationship(lazy="joined")


# ------------------------------------------------------------------ reports
STATUSES = (
    "submitted",              # Submitted to Ubufakazi
    "awaiting_review",        # Awaiting review
    "under_review",           # Under review
    "more_info_required",     # More information required
    "prepared_for_visit",     # Prepared for complainant's visit
    "registered_at_station",  # Registered at a police station (CAS number recorded by an officer)
    "closed",                 # Closed in Ubufakazi's workflow
)
STATUS_LABELS = {
    "submitted": "Submitted to Ubufakazi",
    "awaiting_review": "Awaiting review",
    "under_review": "Under review",
    "more_info_required": "More information required",
    "prepared_for_visit": "Prepared for complainant's visit",
    "registered_at_station": "Registered at a police station",
    "closed": "Closed in Ubufakazi's workflow",
}
CATEGORIES = {
    "scam": "Online scam / fraudulent job offer",
    "banking_fraud": "Digital banking fraud / suspicious payment",
    "theft": "Theft or property incident",
    "abuse": "Physical abuse / domestic violence",
    "threats": "Threats or harassment",
    "misconduct": "Suspected evidence tampering or misconduct",
    "other": "Other reportable incident",
}
FINANCIAL_CATEGORIES = ("scam", "banking_fraud")


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    source: Mapped[str] = mapped_column(String(16))           # telegram | web | seed | test
    category: Mapped[str] = mapped_column(String(20), index=True)
    scam_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    language: Mapped[str] = mapped_column(String(4), default="en")
    province: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    town: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), index=True)
    location_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)   # rounded, optional
    location_lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    incident_when: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    incident_date: Mapped[Optional[dt.date]] = mapped_column(nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    complainant_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    contact_channel: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    contact_ref: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)   # e.g. Telegram chat id
    answers: Mapped[dict] = mapped_column(JSON, default=dict)                       # follow-up answers
    safety: Mapped[dict] = mapped_column(JSON, default=dict)                        # sensitive-handling flags
    status: Mapped[str] = mapped_column(String(24), default="submitted", index=True)
    processing_status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|processing|ready|error
    processing_note: Mapped[str] = mapped_column(Text, default="")
    facts: Mapped[dict] = mapped_column(JSON, default=dict)                         # extracted facts (unverified)
    statement: Mapped[str] = mapped_column(Text, default="")
    statements: Mapped[dict] = mapped_column(JSON, default=dict)                    # lang -> text
    bank_report: Mapped[str] = mapped_column(Text, default="")
    amount_paid: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    script_text: Mapped[str] = mapped_column(Text, default="")                      # suspect's messages, for template matching
    is_seed: Mapped[bool] = mapped_column(Boolean, default=False)
    receipt_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # victim's private receipt key (hashed)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    station: Mapped[Station] = relationship(lazy="joined")
    evidence: Mapped[list["EvidenceFile"]] = relationship(back_populates="report", order_by="EvidenceFile.id",
                                                          cascade="all, delete-orphan")
    timeline: Mapped[list["TimelineEvent"]] = relationship(order_by="TimelineEvent.order", cascade="all, delete-orphan")
    identifiers: Mapped[list["Identifier"]] = relationship(cascade="all, delete-orphan")


class Consent(Base):
    __tablename__ = "consents"
    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String(16))
    version: Mapped[str] = mapped_column(String(16))
    text: Mapped[str] = mapped_column(Text)
    given_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class EvidenceFile(Base):
    """An ORIGINAL file exactly as received. Never modified after storage."""
    __tablename__ = "evidence_files"
    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    uid: Mapped[str] = mapped_column(String(40), unique=True)          # random storage name, never user-controlled
    original_name: Mapped[str] = mapped_column(String(200))
    declared_mime: Mapped[str] = mapped_column(String(100), default="")
    detected_type: Mapped[str] = mapped_column(String(20))             # txt|pdf|jpeg|png|webp|mp3|m4a|ogg|wav|mp4|...
    size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    received_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)   # server receipt time (not a trusted timestamp)
    channel: Mapped[str] = mapped_column(String(16))                   # telegram | web | chat-text | seed
    trusted_timestamp: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # RFC 3161 token, only if configured
    report: Mapped[Report] = relationship(back_populates="evidence")
    derivatives: Mapped[list["EvidenceDerivative"]] = relationship(cascade="all, delete-orphan")


class EvidenceDerivative(Base):
    """Anything produced FROM an original: extracted text, OCR, transcript, AI summary."""
    __tablename__ = "evidence_derivatives"
    id: Mapped[int] = mapped_column(primary_key=True)
    evidence_id: Mapped[int] = mapped_column(ForeignKey("evidence_files.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(24))        # text | pdf-text | ocr | transcript | ai-extract
    method: Mapped[str] = mapped_column(String(40))      # rules | pymupdf | gemini:<model> | none
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    content: Mapped[str] = mapped_column(Text, default="")
    content_sha256: Mapped[str] = mapped_column(String(64), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="queued")   # queued|running|done|error
    started_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime, nullable=True)
    error: Mapped[str] = mapped_column(Text, default="")


class TimelineEvent(Base):
    __tablename__ = "timeline_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    order: Mapped[int] = mapped_column(Integer, default=0)
    at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime, nullable=True)
    when_text: Mapped[str] = mapped_column(String(80), default="")
    kind: Mapped[str] = mapped_column(String(20))
    what: Mapped[str] = mapped_column(Text)
    quote: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(20))      # chat | complainant | system | evidence


IDENTIFIER_KINDS = ("account", "phone", "email", "domain", "url", "social", "username", "payment_ref")


class Identifier(Base):
    """An identifier extracted from evidence. `value` is restricted like the report; `hmac` is used for matching."""
    __tablename__ = "identifiers"
    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16), index=True)
    value: Mapped[str] = mapped_column(String(300))
    display: Mapped[str] = mapped_column(String(300))
    hmac: Mapped[str] = mapped_column(String(64), index=True)
    bank: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    source: Mapped[str] = mapped_column(String(40), default="chat")   # chat | description | evidence:<id> | seed
    first_seen: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (Index("ix_ident_kind_hmac", "kind", "hmac"),)


class IntelMatch(Base):
    """A possible connection between two reports, with the evidence for it. Never a finding of guilt."""
    __tablename__ = "intel_matches"
    id: Mapped[int] = mapped_column(primary_key=True)
    report_a: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    report_b: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    signals: Mapped[list] = mapped_column(JSON, default=list)         # [{kind, display, hmac, reason}]
    strength: Mapped[str] = mapped_column(String(12))                 # "single" | "corroborated" (documented rule, not a probability)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (UniqueConstraint("report_a", "report_b"),)


class StatusChange(Base):
    __tablename__ = "status_changes"
    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    from_status: Mapped[str] = mapped_column(String(24))
    to_status: Mapped[str] = mapped_column(String(24))
    by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


class Note(Base):
    __tablename__ = "notes"
    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    author: Mapped[User] = relationship(lazy="joined")


class AuditEvent(Base):
    """Append-only, hash-chained audit log: each row's hash covers the previous row's hash."""
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, index=True)
    actor_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    actor: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(48), index=True)
    target_type: Mapped[str] = mapped_column(String(24), default="")
    target_id: Mapped[str] = mapped_column(String(40), default="")
    station_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    ip: Mapped[str] = mapped_column(String(64), default="")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))


class StationHandover(Base):
    """The complainant presented their case pack at a police station and an officer accepted the case there.
    The CAS number is typed in by that officer from the station's own system; Ubufakazi never creates or verifies it."""
    __tablename__ = "station_handovers"
    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), unique=True, index=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"))
    from_station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"))
    accepted_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    accepted_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    cas_number: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    cas_recorded_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    cas_recorded_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime, nullable=True)


class BankAlert(Base):
    """Fictional demo alert about a receiving account named in several reports. No real bank is contacted."""
    __tablename__ = "bank_alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    account_hmac: Mapped[str] = mapped_column(String(64), unique=True)
    account_display: Mapped[str] = mapped_column(String(40))
    bank_stated: Mapped[str] = mapped_column(String(60), default="")
    status: Mapped[str] = mapped_column(String(20), default="new")    # new | under_review | reviewed | escalated
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class EvidenceBlob(Base):
    """Original file bytes, when evidence is kept in the database (hosted mode, UBF_STORAGE=db).
    Insert-only: database triggers reject UPDATE, so an original cannot be silently replaced through SQL."""
    __tablename__ = "evidence_blobs"
    uid: Mapped[str] = mapped_column(String(40), primary_key=True)
    data: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=utcnow)


event.listen(EvidenceBlob.__table__, "after_create", DDL(
    "CREATE TRIGGER evidence_blobs_no_update BEFORE UPDATE ON evidence_blobs "
    "BEGIN SELECT RAISE(ABORT, 'evidence originals are read-only'); END").execute_if(dialect="sqlite"))
event.listen(EvidenceBlob.__table__, "after_create", DDL(
    "CREATE OR REPLACE FUNCTION ubf_evidence_read_only() RETURNS trigger AS $$ BEGIN "
    "RAISE EXCEPTION 'evidence originals are read-only'; END; $$ LANGUAGE plpgsql; "
    "CREATE TRIGGER evidence_blobs_no_update BEFORE UPDATE ON evidence_blobs "
    "FOR EACH ROW EXECUTE FUNCTION ubf_evidence_read_only()").execute_if(dialect="postgresql"))
