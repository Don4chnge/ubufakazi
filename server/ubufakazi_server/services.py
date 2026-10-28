"""Report lifecycle: create -> store evidence -> process -> review.

All reporting channels (Telegram, the web form, tests) go through these functions, so the
rules are the same everywhere. Originals are stored before anything reads them; everything
produced from an original is saved as a separate, labelled derivative.
"""
from __future__ import annotations

import datetime as dt
import logging
import threading
import re
import secrets
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.orm import Session

from . import ai, aiguard, audit, banklink, intel, slipcheck, storage, timestamps
from .db import session_scope, write_lock
from .extract import TYPE_LABEL, analyse_text, extract, parse_chat, show_phone
from .models import (CATEGORIES, FINANCIAL_CATEGORIES, STATUSES, Consent, EvidenceDerivative, EvidenceFile,
                     ProcessingJob, Report, Station, StatusChange, TimelineEvent, utcnow)
from .security import sha256_hex
from .stations import route
from .writing import LANG_NAMES, bank_report, general_statement, scam_statement

log = logging.getLogger("ubufakazi.services")

CONSENT_VERSION = "2026-10-demo-1"
CONSENT_TEXT = (
    "Ubufakazi is a DEMONSTRATION prototype by Team CyberThreat. It is not SAPS and is not connected to SAPS or any bank. "
    "Your report and files will be stored by Ubufakazi and shown only to the fictional demo station for the area you chose, "
    "so that a draft statement and case pack can be prepared for you. No case number is issued. "
    "Please use the demo evidence kit or your own test data. For a real crime, go to your nearest police station "
    "or call 10111."
)
REF_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
LANGS = tuple(LANG_NAMES)
_ai_retried: set[int] = set()
SYNC_PROCESSING = False          # tests set this to True
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ubf-process")


class ReportError(ValueError):
    pass


# ------------------------------------------------------------------ helpers
def new_reference(db: Session) -> str:
    while True:
        ref = "UBF-26-" + "".join(secrets.choice(REF_ALPHABET) for _ in range(6))
        if not db.query(Report.id).filter_by(reference=ref).first():
            return ref


def new_receipt_key() -> str:
    raw = "".join(secrets.choice(REF_ALPHABET) for _ in range(12))
    return "-".join(raw[i:i + 4] for i in range(0, 12, 4))


def check_receipt(report: Report | None, key: str) -> bool:
    if not report or not report.receipt_hash or not key:
        return False
    return secrets.compare_digest(report.receipt_hash, sha256_hex(key.strip().upper()))


_MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def parse_when(text: str | None, today: dt.date | None = None) -> dt.date | None:
    """Best-effort date from what the complainant typed. Returns None when unsure (never guesses)."""
    t = (text or "").strip().lower()
    today = today or dt.date.today()
    if not t:
        return None
    if t in ("today", "namhlanje", "vandag", "kajeno", "namhlanje"):
        return today
    if t in ("yesterday", "izolo", "gister", "maobane"):
        return today - dt.timedelta(days=1)
    m = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", t)
    try:
        if m:
            return dt.date(int(m[1]), int(m[2]), int(m[3]))
        m = re.search(r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{2,4})\b", t)
        if m:
            y = int(m[3]) + (2000 if len(m[3]) == 2 else 0)
            return dt.date(y, int(m[2]), int(m[1]))
        m = re.search(r"\b(\d{1,2})\s+([a-z]{3})[a-z]*\.?(?:\s+(\d{4}))?\b", t)
        if m and m[2] in _MONTHS:
            return dt.date(int(m[3] or today.year), _MONTHS[m[2]], int(m[1]))
    except ValueError:
        return None
    return None


def station_for(db: Session, province: str | None, town: str | None) -> Station:
    code = route(province, town)
    st = db.query(Station).filter_by(code=code).first()
    if not st:
        raise ReportError("Stations are not set up. Run: python -m ubufakazi_server.setup")
    return st


# ------------------------------------------------------------------ create
def create_report(db: Session, *, source: str, category: str, language: str = "en", province: str | None = None,
                  town: str | None = None, description: str = "", incident_when: str | None = None,
                  complainant_name: str | None = None, contact_channel: str | None = None, contact_ref: str | None = None,
                  answers: dict | None = None, safety: dict | None = None, location: tuple[float, float] | None = None,
                  consent_given: bool = False, ip: str = "") -> tuple[Report, str]:
    """Create a report. Returns (report, receipt_key). The receipt key is shown to the complainant once."""
    if not consent_given:
        raise ReportError("Consent is required before a report can be submitted.")
    if category not in CATEGORIES:
        raise ReportError("Unknown category.")
    language = language if language in LANGS else "en"
    description = (description or "").strip()[:8000]
    if len(description) < 10:
        raise ReportError("Please describe what happened (at least a sentence).")
    st = station_for(db, province, town)
    key = new_receipt_key()
    lat = lon = None
    if location:
        lat, lon = round(float(location[0]), 2), round(float(location[1]), 2)   # ~1 km: never exact GPS
    r = Report(reference=new_reference(db), source=source, category=category, language=language, province=province,
               town=(town or "").strip()[:80] or None, station_id=st.id, location_lat=lat, location_lon=lon,
               incident_when=(incident_when or "").strip()[:80] or None, incident_date=parse_when(incident_when),
               description=description, complainant_name=(complainant_name or "").strip()[:120] or None,
               contact_channel=contact_channel, contact_ref=contact_ref, answers=answers or {}, safety=safety or {},
               receipt_hash=sha256_hex(key))
    db.add(r)
    db.flush()
    db.add(Consent(report_id=r.id, channel=source, version=CONSENT_VERSION, text=CONSENT_TEXT))
    db.add(StatusChange(report_id=r.id, from_status="", to_status="submitted", note="Report received"))
    audit.record(db, "report.created", actor=f"complainant:{source}", target_type="report", target_id=r.reference,
                 station_id=st.id, ip=ip, detail={"category": category, "station": st.code, "consent": CONSENT_VERSION})
    return r, key


def add_evidence(db: Session, report: Report, data: bytes, name: str, *, declared_mime: str = "", channel: str,
                 ip: str = "", actor: str = "complainant") -> EvidenceFile:
    if len(report.evidence) >= storage_limit():
        raise storage.RejectedFile(f"A report can hold at most {storage_limit()} files.")
    info = storage.store_original(data, name, db=db)
    ev = EvidenceFile(uid=info["uid"], original_name=info["original_name"],
                      declared_mime=(declared_mime or "")[:100], detected_type=info["detected_type"], size=info["size"],
                      sha256=info["sha256"], channel=channel)
    report.evidence.append(ev)
    db.flush()
    audit.record(db, "evidence.received", actor=actor, target_type="evidence", target_id=ev.id,
                 station_id=report.station_id, ip=ip,
                 detail={"report": report.reference, "sha256": ev.sha256, "size": ev.size, "type": ev.detected_type,
                         "name": ev.original_name})
    return ev


def storage_limit() -> int:
    from .config import get_settings
    return get_settings().max_files_per_report


# ------------------------------------------------------------------ processing
def _decode_text(data: bytes) -> str:
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16", errors="replace")
    return data.decode("utf-8-sig", errors="replace")


def _pdf_text(data: bytes) -> str:
    import pymupdf
    out = []
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        for i, page in enumerate(doc):
            if i >= 50:
                out.append("[stopped after 50 pages]")
                break
            out.append(page.get_text())
    return "\n".join(out).strip()


def _derive_rows(uid: str, sha256: str, detected_type: str) -> list[dict]:
    """Read one original and produce derivative rows. Pure computation (no database), so slow
    steps such as AI reading never hold the database write lock."""
    data = storage.read_original(uid)
    if sha256_hex(data) != sha256:
        return [{"kind": "integrity", "method": "sha256", "content": "", "ai_generated": False,
                 "note": "STOP: the stored file no longer matches the hash recorded at receipt. Not processed."}]
    rows = []
    if detected_type == "txt":
        rows.append({"kind": "text", "method": "utf-decode", "content": _decode_text(data)[:200_000], "ai_generated": False,
                     "note": "Text of the original file (decoded, unchanged)."})
    elif detected_type == "pdf":
        try:
            text = _pdf_text(data)
            note = "Text layer extracted from the PDF." if text else "No text layer (probably a scan)."
        except Exception as e:   # malformed PDFs are expected from untrusted uploads
            text, note = "", f"PDF could not be read ({type(e).__name__})."
        rows.append({"kind": "pdf-text", "method": "pymupdf", "content": text[:200_000], "ai_generated": False, "note": note})
        if not text:
            r = ai.read_media(data, "pdf")
            rows.append({"kind": "ai-extract" if r["ok"] else "not-processed", "method": r["method"], "ai_generated": r["ok"],
                         "content": r["text"], "note": r["note"]})
    else:
        r = ai.read_media(data, detected_type)
        rows.append({"kind": "ai-extract" if r["ok"] else "not-processed", "method": r["method"], "ai_generated": r["ok"],
                     "content": r["text"], "note": r["note"]})
    sig = slipcheck.as_derivative(data, detected_type)          # forensic warning signs of editing (never a verdict)
    if sig:
        rows.append(sig)
    for d in rows:
        d["content_sha256"] = sha256_hex(d["content"]) if d["content"] else ""
    return rows


def _facts(analysis: dict, scam_type: str, extra_sources: dict) -> dict:
    ex = analysis["ex"]
    return {
        "suspect_alias": analysis["scammer"],
        "scam_type": scam_type, "scam_type_label": TYPE_LABEL.get(scam_type, "Other"),
        "accounts": [{"value": a["value"], "bank": a.get("bank")} for a in ex["accounts"]],
        "phones": [show_phone(p["value"]) for p in ex["phones"]],
        "emails": [e["value"] for e in ex["emails"]],
        "domains": ex["domains"],
        "links": [l["url"] for l in ex["links"]][:20],
        "social": [{"platform": s["platform"], "url": s["url"]} for s in ex["social"]],
        "usernames": [u["value"] for u in ex["usernames"]],
        "payment_refs": [r["value"] for r in ex["payment_refs"]],
        "total_paid": ex["total_paid"], "total_requested": ex["total_requested"],
        "payments": [p["amounts"][0] for p in ex["paid"]],
        "messages_parsed": len(analysis["msgs"]),
        "extra_identifier_sources": extra_sources,
        "method": "Documented rules (regular expressions and keyword lists). Unverified until checked by an officer.",
    }


def track_url() -> str:
    from .config import get_settings
    return get_settings().public_base_url + "/track"


_proc_locks: dict[int, threading.Lock] = {}
_proc_guard = threading.Lock()


def process_report(report_id: int) -> None:
    """Run the processing pipeline for one report. Safe to re-run: originals are never touched.
    Two runs for the same report (e.g. background processing and a Telegram /pack) never overlap."""
    with _proc_guard:
        lock = _proc_locks.setdefault(report_id, threading.Lock())
    with lock:
        _process_report(report_id)


def _process_report(report_id: int) -> None:
    with write_lock, session_scope() as db:
        r = db.get(Report, report_id)
        if r is None:
            return
        r.processing_status = "processing"
        job = ProcessingJob(report_id=r.id, status="running", started_at=utcnow())
        db.add(job)
        db.flush()
        job_id = job.id
        # New files, plus files whose AI reading failed earlier (a re-run retries them).
        todo = [(ev.id, ev.uid, ev.sha256, ev.detected_type) for ev in r.evidence
                if not ev.derivatives or all(d.kind == "not-processed" for d in ev.derivatives)]
        to_stamp = [(ev.id, ev.sha256) for ev in r.evidence if not ev.trusted_timestamp]
    try:
        derived = {ev_id: _derive_rows(uid, sha, typ) for ev_id, uid, sha, typ in todo}   # slow part, no lock held
        stamps = {ev_id: timestamps.stamp_quietly(sha) for ev_id, sha in to_stamp} if timestamps.configured() else {}
        with write_lock, session_scope() as db:
            r = db.get(Report, report_id)
            for ev in r.evidence:
                if ev.id in derived:
                    for old_d in [d for d in ev.derivatives if d.kind == "not-processed"]:
                        ev.derivatives.remove(old_d)      # derived material only; the original is never touched
                for d in derived.get(ev.id, []):
                    ev.derivatives.append(EvidenceDerivative(**d))
                if stamps.get(ev.id) and not ev.trusted_timestamp:
                    ev.trusted_timestamp = stamps[ev.id]
                    info = timestamps.public_info(ev.trusted_timestamp)
                    audit.record(db, "evidence.timestamped", actor="system", target_type="evidence", target_id=ev.id,
                                 station_id=r.station_id, detail={"report": r.reference, "sha256": ev.sha256, **(info or {})})
            db.flush()
            _process(db, r)
            job = db.get(ProcessingJob, job_id)
            job.status, job.finished_at = "done", utcnow()
            r.processing_status = "ready"
            if r.status == "submitted":
                db.add(StatusChange(report_id=r.id, from_status="submitted", to_status="awaiting_review",
                                    note="Processing finished"))
                r.status = "awaiting_review"
            audit.record(db, "report.processed", actor="system", target_type="report", target_id=r.reference,
                         station_id=r.station_id, detail={"identifiers": len(r.identifiers), "evidence": len(r.evidence)})
        banklink.run_later(banklink.deliver_for_report, report_id)     # tell the connected bank (fictional)
        failed = any(d["kind"] == "not-processed" and d["method"].startswith("gemini") for rows in derived.values() for d in rows)
        if failed and report_id not in _ai_retried and not SYNC_PROCESSING:
            _ai_retried.add(report_id)                                  # one automatic retry, two minutes later
            threading.Timer(120, enqueue, args=(report_id,)).start()
    except Exception as e:
        log.exception("processing failed for report %s", report_id)
        with write_lock, session_scope() as db:
            r = db.get(Report, report_id)
            r.processing_status = "error"
            r.processing_note = f"Processing failed ({type(e).__name__}). Originals are safe; an officer can retry."
            job = db.get(ProcessingJob, job_id)
            job.status, job.finished_at, job.error = "error", utcnow(), f"{type(e).__name__}: {e}"[:2000]
            audit.record(db, "report.processing_error", actor="system", target_type="report", target_id=r.reference,
                         station_id=r.station_id, detail={"error": type(e).__name__})


def _process(db: Session, r: Report) -> None:
    chat_parts, other_parts = [], []
    findings, chat_flagged = [], False                     # AI safety: prompt-injection attempts in evidence
    for n, ev in enumerate(r.evidence, 1):
        for d in ev.derivatives:
            if not d.content:
                continue
            hits = aiguard.scan(d.content, is_ai_output=(d.kind == "ai-extract"))
            for h in hits:
                findings.append({**h, "file": f"file #{n}: {ev.original_name}"[:120],
                                 "read_by": "AI" if d.kind == "ai-extract" else "rules"})
            if d.kind == "text" and parse_chat(d.content) and any(m["sender"] for m in parse_chat(d.content)[:50]):
                chat_parts.append(d.content)
                chat_flagged = chat_flagged or bool(hits)
            elif d.kind in ("text", "pdf-text", "ai-extract"):
                src = ("flagged:" if hits else "ai:" if d.kind == "ai-extract" else "evidence:") + str(ev.id)
                other_parts.append((src, d.content))
    desc_hits = aiguard.scan(r.description)
    findings += [{**h, "file": "complainant's description", "read_by": "rules"} for h in desc_hits]
    main_text = "\n".join(chat_parts) if chat_parts else r.description
    analysis = analyse_text(main_text)
    scam_type = analysis["scam_type"] if r.category in FINANCIAL_CATEGORIES else "other"

    # identifiers: chat/description first, then other evidence (identifiers only, never amounts)
    main_src = ("flagged:chat" if chat_flagged else "chat") if chat_parts else ("flagged:description" if desc_hits else "description")
    items = intel.identifiers_from_analysis(analysis["ex"], main_src)
    extra_sources = {}
    for src, text in ([("flagged:description" if desc_hits else "description", r.description)] if chat_parts else []) + other_parts:
        ex2 = extract(parse_chat(text), None)
        found = intel.identifiers_from_analysis(ex2, src)
        if found:
            extra_sources[src] = len(found)
        items += found
    # trusted readings first, so an identifier also read by the rules is never stored as "AI only"
    items.sort(key=lambda it: aiguard.untrusted(it.get("source")))
    intel.save_identifiers(db, r, items)

    r.facts = _facts(analysis, scam_type, extra_sources)
    untrusted_n = sum(1 for i in r.identifiers if aiguard.untrusted(i.source))
    edited = [f"file #{n}: {ev.original_name}"[:120] for n, ev in enumerate(r.evidence, 1)
              for d in ev.derivatives if d.kind == "integrity-signals" and d.note.startswith("Signs of editing")]
    r.facts["security"] = {"prompt_injection": findings[:20], "untrusted_identifiers": untrusted_n, "edit_signs": edited,
                           "rule": "Details read only by the AI, or from a file with an injection attempt, are leads "
                                   "for investigators but never send a bank alert or count in the beneficiary check "
                                   "on their own."}
    if findings:
        audit.record(db, "security.prompt_injection_suspected", actor="system", target_type="report",
                     target_id=r.reference, station_id=r.station_id,
                     detail={"findings": len(findings), "kinds": sorted({f["kind"] for f in findings})}, commit=False)
    r.scam_type = scam_type if r.category in FINANCIAL_CATEGORIES else None
    r.amount_paid = analysis["ex"]["total_paid"]
    if r.amount_paid is None and r.answers.get("amount_paid"):
        try:
            r.amount_paid = float(re.sub(r"[^\d.]", "", str(r.answers["amount_paid"]).replace(",", ".")) or "x")
        except ValueError:
            pass
    r.script_text = analysis["script_text"] if chat_parts else ""

    # timeline (replace previous automatic events)
    r.timeline.clear()
    db.flush()
    order = 0
    if r.incident_when:
        r.timeline.append(TimelineEvent(order=order, at=None, when_text=r.incident_when, kind="incident",
                                        what="Incident (as stated by the complainant)", source="complainant"))
        order += 1
    for e in analysis["timeline"] if chat_parts else []:
        r.timeline.append(TimelineEvent(order=order, at=e["at"], when_text=e["at"].strftime("%d %b %Y %H:%M") if e["at"] else "",
                                        kind=e["kind"], what=e["what"], quote=e["quote"], source="chat"))
        order += 1
    for ev in r.evidence:
        r.timeline.append(TimelineEvent(order=order, at=ev.received_at, when_text=ev.received_at.strftime("%d %b %Y %H:%M UTC"),
                                        kind="evidence", what=f"Evidence received: {ev.original_name} (SHA-256 {ev.sha256[:12]}…)",
                                        source="system"))
        order += 1
    r.timeline.append(TimelineEvent(order=order, at=r.created_at, when_text=r.created_at.strftime("%d %b %Y %H:%M UTC"),
                                    kind="reported", what="Report submitted to Ubufakazi", source="system"))

    # statements in all five languages (draft, for the complainant to check)
    use_scam = r.category in FINANCIAL_CATEGORIES and chat_parts and (
        analysis["ex"]["accounts"] or analysis["ex"]["paid"] or analysis["scammer"])
    place = ", ".join(x for x in (r.town, r.province) if x) or None
    sts = {}
    for lang in LANGS:
        if use_scam:
            sts[lang] = scam_statement(lang, reference=r.reference, name=r.complainant_name, analysis=analysis, scam_type=scam_type)
        else:
            sts[lang] = general_statement(lang, reference=r.reference, name=r.complainant_name, when=r.incident_when,
                                          place=place, description=r.description)
    r.statements = sts
    r.statement = sts.get(r.language, sts["en"])
    r.bank_report = bank_report(reference=r.reference, name=r.complainant_name, analysis=analysis,
                                scam_type=scam_type) if (r.category in FINANCIAL_CATEGORIES and use_scam) else ""
    notes = [d.note for ev in r.evidence for d in ev.derivatives if d.kind == "not-processed"]
    r.processing_note = (f"{len(notes)} media file(s) stored and hashed but not read automatically "
                         "(AI reading not configured)." if notes else "")
    db.flush()
    intel.compute_matches(db, r)
    intel.update_bank_alerts(db, r)


def enqueue(report_id: int, on_done=None):
    """Process in the background (one worker, so SQLite writes and the audit chain stay ordered)."""
    def run():
        process_report(report_id)
        if on_done:
            on_done(report_id)
    if SYNC_PROCESSING:
        run()
        return None
    return _executor.submit(run)


# ------------------------------------------------------------------ officer actions
def change_status(db: Session, r: Report, to: str, *, user_id: int, actor: str, note: str = "", ip: str = "") -> None:
    if to not in STATUSES:
        raise ReportError("Unknown status.")
    if to == r.status:
        return
    with write_lock:
        db.add(StatusChange(report_id=r.id, from_status=r.status, to_status=to, by_user_id=user_id, note=note[:1000]))
        frm, r.status = r.status, to
        audit.record(db, "report.status", actor=actor, actor_user_id=user_id, target_type="report", target_id=r.reference,
                     station_id=r.station_id, ip=ip, detail={"from": frm, "to": to, "note": note[:200]})


def submit_report(*, files: list[tuple[bytes, str, str]] = (), pasted_text: str = "", file_channel: str = "web",
                  **fields) -> dict:
    """One-call submission used by every channel: create the report, store each original, commit.
    `files` is a list of (data, filename, declared_mime). Pasted chat text is stored as an original .txt file too,
    so it is hashed like any other evidence. Returns {"id", "reference", "receipt_key", "rejected": [...]}."""
    rejected = []
    with write_lock, session_scope() as db:
        r, key = create_report(db, **fields)
        if pasted_text and pasted_text.strip():
            add_evidence(db, r, pasted_text.strip().encode("utf-8"), "pasted-messages.txt", declared_mime="text/plain",
                         channel="chat-text", ip=fields.get("ip", ""))
        for data, name, mime in files:
            try:
                add_evidence(db, r, data, name, declared_mime=mime, channel=file_channel, ip=fields.get("ip", ""))
            except storage.RejectedFile as e:
                rejected.append({"name": storage.safe_display_name(name), "reason": str(e)})
        out = {"id": r.id, "reference": r.reference, "receipt_key": key, "rejected": rejected,
               "station": r.station.name, "evidence": [{"name": e.original_name, "sha256": e.sha256, "size": e.size}
                                                        for e in r.evidence]}
    return out


def add_more_evidence(report_id: int, files: list[tuple[bytes, str, str]], *, channel: str, ip: str = "") -> dict:
    """Complainant adds files to an existing report; the report is re-processed (originals untouched)."""
    added, rejected = [], []
    with write_lock, session_scope() as db:
        r = db.get(Report, report_id)
        for data, name, mime in files:
            try:
                ev = add_evidence(db, r, data, name, declared_mime=mime, channel=channel, ip=ip)
                added.append({"name": ev.original_name, "sha256": ev.sha256, "size": ev.size})
            except storage.RejectedFile as e:
                rejected.append({"name": storage.safe_display_name(name), "reason": str(e)})
    return {"added": added, "rejected": rejected}
