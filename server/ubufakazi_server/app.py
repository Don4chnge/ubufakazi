"""Ubufakazi 2.0 web server: public reporting API, private police and bank-demo APIs, and the website.

Run:  uvicorn ubufakazi_server.app:app --port 8000
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import threading
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import PlainTextResponse, FileResponse, JSONResponse, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from . import payee, ai, audit, banklink, bot, handover, police, services, storage, timestamps, utb, whatsapp
from .casepack import build_case_pack
from .config import SITE_DIR, WEB_DIR, get_settings
from .db import get_db, init_db, write_lock
from .extract import TYPE_LABEL, norm_phone, reg_domain
from .models import (CATEGORIES, CATEGORY_LABELS, STATUS_LABELS, STATUSES, AuditEvent, BankAlert, EvidenceFile, Identifier, IntelMatch,
                     Note, Report, Station, StationHandover, StatusChange, User, utcnow)
from .security import (Principal, clear_session_cookie, client_ip, create_session, current_principal, hash_password,
                       identifier_hmac, load_session, rate_limit, require_roles, set_session_cookie, verify_password,
                       verify_totp, _require_csrf)
from .stations import PROVINCES, towns_by_province
from .writing import LANG_NAMES

VERSION = "2.0.0-demo"
MAX_BODY = 110 * 1024 * 1024
LOCK_AFTER = 5
LOCK_MINUTES = 15

def _bank_startup() -> None:
    """The demo's fictional bank was called DemoBank before; it is now Ubuntu Trust Bank. Idempotent."""
    from sqlalchemy import update
    from .db import session_scope
    with write_lock, session_scope() as db:
        db.execute(update(Identifier).where(Identifier.bank == "DemoBank").values(bank=banklink.BANK_NAME))
        db.execute(update(BankAlert).where(BankAlert.bank_stated == "DemoBank").values(bank_stated=banklink.BANK_NAME))
        db.execute(update(User).where(User.username == "bank.reviewer")
                   .values(display_name="Ubuntu Trust Bank fraud analyst (fictional bank)"))
        utb.seed_registry(db)


@asynccontextmanager
async def lifespan(_app):
    get_settings()          # refuse to start without real secrets
    init_db()
    get_settings().storage_dir.mkdir(parents=True, exist_ok=True)
    _bank_startup()
    if os.environ.get("UBF_RUN_BOT", "1") == "1":
        threading.Thread(target=banklink.keep_delivering, daemon=True).start()
        await bot.start_bot()
        await whatsapp.check_connection()
    yield
    await bot.stop_bot()


app = FastAPI(title="Ubufakazi 2.0 (demo)", version=VERSION, docs_url=None, redoc_url=None, openapi_url=None,
              lifespan=lifespan)


# ------------------------------------------------------------------ middleware
CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; font-src 'self'; "
       "connect-src 'self'; media-src 'self' blob:; object-src 'none'; base-uri 'none'; form-action 'self'; "
       "frame-ancestors 'none'")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    cl = request.headers.get("content-length")
    if cl and cl.isdigit() and int(cl) > MAX_BODY:
        return JSONResponse({"detail": "Upload too large."}, status_code=413)
    resp = await call_next(request)
    h = resp.headers
    h.setdefault("Content-Security-Policy", CSP)
    h["X-Content-Type-Options"] = "nosniff"
    h["X-Frame-Options"] = "DENY"
    h["Referrer-Policy"] = "no-referrer"
    h["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
    h["Cross-Origin-Opener-Policy"] = "same-origin"
    if get_settings().cookie_secure:
        h["Strict-Transport-Security"] = "max-age=31536000"
    p = request.url.path
    if p.startswith("/api/") or p in ("/police", "/bank-demo", "/track"):
        h["Cache-Control"] = "no-store"
    return resp


def _err(status: int, msg: str):
    raise HTTPException(status_code=status, detail=msg)


# ------------------------------------------------------------------ public: meta, health, integrations
@app.get("/api/health")
def health():
    return {"ok": True, "version": VERSION, "demo": True}


def _bot_status() -> dict:
    if not get_settings().telegram_token:
        return {"configured": False, "running": False, "note": "Not configured: add TELEGRAM_BOT_TOKEN to server/.env."}
    st = bot.STATE
    if st["running"]:
        return {"configured": True, "running": True, "username": st["username"],
                "note": f"Running as @{st['username']} (long polling, started {st['started_at'][:16]} UTC)."}
    return {"configured": True, "running": False, "note": st["error"] or "Token present but the bot is not running."}


@app.get("/api/integrations")
def integrations(db: Session = Depends(get_db)):
    s = get_settings()
    return {
        "telegram": _bot_status(),
        "whatsapp": whatsapp.status(),
        "ai_media_reading": ai.status(),
        "trusted_timestamps": timestamps.status(),
        "station_handover": {"working": True, "note": "Working. The complainant shows the QR code on their case pack; "
                                                      "an officer signs in, accepts the case at their station and records "
                                                      "the CAS number the station issued (shown as 'entered by officer')."},
        "saps": {"connected": False, "note": "Deliberately not connected to SAPS's own systems, and never claimed to be. "
                                             "Ubufakazi never creates or checks CAS numbers. Stations in this demo are fictional."},
        "bank_link": banklink.status(db),
        "banks": {"connected": False, "note": "Deliberately not connected to any real bank. Ubuntu Trust Bank is fictional; "
                                              "a real bank would need a partnership and data-sharing agreement."},
        "database": "postgres" if s.database_url.startswith("postgres") else "sqlite",
    }


# ------------------------------------------------------------------ WhatsApp webhook (Meta Cloud API)
@app.get("/api/whatsapp/webhook")
def whatsapp_verify(request: Request):
    """Meta's one-time check when the webhook URL is saved in the Meta developer dashboard."""
    if not whatsapp.configured():
        raise HTTPException(404, "WhatsApp is not configured.")
    q = request.query_params
    challenge = whatsapp.verify_challenge(q.get("hub.mode"), q.get("hub.verify_token"), q.get("hub.challenge"))
    if challenge is None:
        raise HTTPException(403, "Verification failed.")
    return Response(challenge, media_type="text/plain")


@app.post("/api/whatsapp/webhook")
async def whatsapp_webhook(request: Request):
    if not whatsapp.configured():
        raise HTTPException(404, "WhatsApp is not configured.")
    raw = await request.body()
    if len(raw) > 1_000_000:
        raise HTTPException(413, "Too large.")
    whatsapp.STATE["webhook_calls"] += 1
    if not whatsapp.verify_signature(raw, request.headers.get("X-Hub-Signature-256")):
        whatsapp.STATE["bad_signatures"] += 1
        raise HTTPException(403, "Bad signature.")
    try:
        payload = json.loads(raw)
    except ValueError:
        raise HTTPException(400, "Not JSON.")
    for c in whatsapp.dispatch(payload if isinstance(payload, dict) else {}):
        await c
    return {"ok": True}


@app.get("/api/public/stats")
def public_stats(db: Session = Depends(get_db)):
    """Aggregate counts only (no case details), for the home page. All data in this demo is synthetic."""
    linked = {a for (a,) in db.query(IntelMatch.report_a).all()} | {b for (b,) in db.query(IntelMatch.report_b).all()}
    from .models import Station
    return {"reports": db.query(func.count(Report.id)).scalar() or 0,
            "evidence_files": db.query(func.count(EvidenceFile.id)).scalar() or 0,
            "linked_reports": len(linked), "stations": db.query(func.count(Station.id)).scalar() or 0,
            "networks": len(police.clusters(db, _AllSeeing())) if linked else 0,
            "demo": True, "note": "Synthetic demonstration data, not real cases."}


class _AllSeeing:
    """Used only to count networks for public aggregate stats (no details are returned)."""
    is_admin = True

    def can_see_station(self, _sid):
        return True


@app.get("/api/public/seal/{seal_id}")
def public_seal(seal_id: str, request: Request, db: Session = Depends(get_db)):
    """Seal details for /verify. The seal id is random and printed only on the PDF itself."""
    rate_limit(request, "seal", 40, 300)
    from .models import DocumentSeal
    from . import seals
    s = db.query(DocumentSeal).filter_by(seal_id=seal_id.strip().upper()[:24]).first()
    if not s or not s.sha256:
        _err(404, "No document with this seal was issued by Ubufakazi.")
    return seals.public(s)


@app.get("/api/public/seal-by-hash/{sha256}")
def public_seal_by_hash(sha256: str, request: Request, db: Session = Depends(get_db)):
    """Is this exact file a document Ubufakazi issued? Needs the file's full fingerprint (computed in the browser)."""
    rate_limit(request, "seal", 40, 300)
    from .models import DocumentSeal
    from . import seals
    h = sha256.strip().lower()
    if len(h) != 64 or any(c not in "0123456789abcdef" for c in h):
        _err(400, "Not a SHA-256 fingerprint.")
    s = db.query(DocumentSeal).filter_by(sha256=h).first()
    if not s:
        _err(404, "This exact file was not issued by Ubufakazi (or it was changed after it was issued).")
    return seals.public(s)


_SEC_CACHE: dict = {}


@app.get("/api/public/security")
def public_security(request: Request, db: Session = Depends(get_db)):
    """Live security self-checks for /security. Aggregates only; cached for 60 seconds."""
    rate_limit(request, "security", 30, 60)
    import json as _json
    import time as _time
    from . import payee
    if _SEC_CACHE.get("at", 0) > _time.time() - 60:
        return _SEC_CACHE["data"]
    from .models import DocumentSeal, BeneficiaryCheck

    def _load(name):
        try:
            return _json.loads((WEB_DIR / name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
    chain = audit.verify_chain(db)
    data = {
        "audit_chain": {"intact": chain["intact"], "events": chain["checked"]},
        "timestamps": timestamps.status(),
        "ai": {"configured": ai.available(), **{k: v for k, v in ai.usage().items()}},
        "dependency_scan": _load("security-scan.json"),
        "tests": _load("security-tests.json"),
        "seals_issued": db.query(func.count(DocumentSeal.id)).scalar() or 0,
        "beneficiary_checks": db.query(func.count(BeneficiaryCheck.id)).scalar() or 0,
        "subscribed_banks": len(payee.SUBSCRIBERS),
        "csp": CSP, "https_only": get_settings().cookie_secure,
    }
    _SEC_CACHE.update(at=_time.time(), data=data)
    return data


@app.get("/.well-known/security.txt", response_class=PlainTextResponse)
def security_txt():
    base = get_settings().public_base_url
    return ("Contact: https://github.com/Don4chnge/ubufakazi/security/advisories/new\n"
            "Expires: 2027-10-28T00:00:00.000Z\n"
            f"Policy: {base}/security\n"
            f"Canonical: {base}/.well-known/security.txt\n"
            "Preferred-Languages: en\n")


@app.get("/api/public/meta")
def meta():
    return {"categories": CATEGORIES, "languages": LANG_NAMES, "provinces": PROVINCES, "towns": towns_by_province(),
            "consent": {"version": services.CONSENT_VERSION, "text": services.CONSENT_TEXT},
            "limits": {"max_files": get_settings().max_files_per_report,
                       "max_file_mb": get_settings().max_upload_bytes // (1024 * 1024)},
            "statuses": STATUS_LABELS}


# ------------------------------------------------------------------ public: report, track, pack, add evidence
async def _read_files(files: list[UploadFile] | None) -> list[tuple[bytes, str, str]]:
    out = []
    limit = get_settings().max_upload_bytes
    for f in files or []:
        if not f.filename:
            continue
        data = await f.read(limit + 1)
        out.append((data, f.filename, f.content_type or ""))
    if len(out) > get_settings().max_files_per_report:
        _err(400, f"At most {get_settings().max_files_per_report} files per report.")
    return out


@app.post("/api/public/reports")
async def public_report(request: Request, category: str = Form(...), language: str = Form("en"),
                        province: str = Form(...), town: str = Form(""), description: str = Form(...),
                        incident_when: str = Form(""), complainant_name: str = Form(""), amount_paid: str = Form(""),
                        pasted_text: str = Form(""), unsafe: str = Form(""), consent: str = Form(""),
                        files: Optional[list[UploadFile]] = File(None)):
    rate_limit(request, "public-report", 6, 600)
    if consent != "yes":
        _err(400, "Please read and accept the consent notice first.")
    if province not in PROVINCES:
        _err(400, "Please choose a province.")
    if len(pasted_text) > 300_000:
        _err(400, "Pasted text is too long. Upload the chat export as a .txt file instead.")
    blobs = await _read_files(files)
    answers = {"amount_paid": amount_paid.strip()[:40]} if amount_paid.strip() else {}
    try:
        out = services.submit_report(files=blobs, pasted_text=pasted_text, file_channel="web", source="web",
                                     category=category, language=language, province=province, town=town,
                                     description=description, incident_when=incident_when,
                                     complainant_name=complainant_name, contact_channel="web", answers=answers,
                                     safety={"unsafe": unsafe == "yes"} if category in ("abuse", "threats") else {},
                                     consent_given=True, ip=client_ip(request))
    except services.ReportError as e:
        _err(400, str(e))
    services.enqueue(out["id"])
    out.pop("id")
    return out


class TrackIn(BaseModel):
    reference: str = Field(max_length=24)
    key: str = Field(max_length=24)


def _receipt_report(db: Session, request: Request, body: TrackIn) -> Report:
    rate_limit(request, "track", 20, 300)
    r = db.query(Report).filter_by(reference=body.reference.strip().upper()).first()
    if not services.check_receipt(r, body.key):
        _err(404, "No report matches that reference and receipt key.")
    return r


@app.post("/api/public/track")
def track(body: TrackIn, request: Request, db: Session = Depends(get_db)):
    r = _receipt_report(db, request, body)
    hist = db.query(StatusChange).filter_by(report_id=r.id).order_by(StatusChange.at).all()
    return {"reference": r.reference, "status": r.status, "status_label": STATUS_LABELS[r.status],
            "processing_status": r.processing_status, "station": r.station.name, "submitted": r.created_at.isoformat() + "Z",
            "history": [{"at": h.at.isoformat() + "Z", "label": STATUS_LABELS.get(h.to_status, h.to_status)} for h in hist],
            "evidence": [{"name": e.original_name, "sha256": e.sha256, "size": e.size, "type": e.detected_type,
                          "received": e.received_at.isoformat() + "Z"} for e in r.evidence],
            "statement_ready": bool(r.statement),
            "bank_responses": [{"bank": b["bank"], "status_label": b["status_label"], "note": b["note"], "at": b["at"]}
                               for b in banklink.responses_for_report(db, r)],
            "registration": ({"station": h["station"], "cas_number": h["cas_number"], "at": h["cas_recorded_at"]}
                             if (h := _handover_info(db, r)) and h["cas_number"] else None)}


@app.post("/api/public/pack")
def public_pack(body: TrackIn, request: Request, db: Session = Depends(get_db)):
    r = _receipt_report(db, request, body)
    if r.processing_status != "ready":
        _err(409, "Your case pack is still being prepared. Try again in a few seconds.")
    pdf = build_case_pack(db, r, "complainant")
    with write_lock:
        audit.record(db, "pack.complainant", actor="complainant", target_type="report", target_id=r.reference,
                     station_id=r.station_id, ip=client_ip(request))
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="Ubufakazi-{r.reference}.pdf"'})


RED_FLAGS = {
    "ask": "Asked for money upfront (a 'fee' before you get the job, parcel, prize or refund)",
    "pressure": "Pressured you to pay quickly ('today', 'urgent', 'or you lose it')",
    "details": "Asked you to pay into a personal or unrelated bank account",
    "link": "Sent a link to a website outside the official one",
    "offer": "Promised something too good to be true",
    "gone": "Stopped answering or blocked you after you paid",
}


@app.post("/api/public/warning")
def public_warning(body: TrackIn, request: Request, db: Session = Depends(get_db)):
    """Redacted facts for a social-media scam warning. Never returns names, account numbers, references,
    statements or evidence. Optional items (website, partly hidden number) are only shown if the user ticks them."""
    r = _receipt_report(db, request, body)
    kinds = {e.kind for e in r.timeline}
    flags = [txt for k, txt in RED_FLAGS.items() if k in kinds]
    domains = [i.display for i in r.identifiers if i.kind == "domain"][:3]
    phones = [i.display for i in r.identifiers if i.kind == "phone"][:2]
    masked = [p[:3] + " *** **" + p.replace(" ", "")[-2:] for p in phones]
    with write_lock:
        audit.record(db, "warning.prepared", actor="complainant", target_type="report", target_id=r.reference,
                     station_id=r.station_id, ip=client_ip(request))
    return {"category": r.category, "category_label": CATEGORY_LABELS.get(r.category, r.category),
            "scam_type": r.scam_type, "scam_type_label": TYPE_LABEL.get(r.scam_type or "", None),
            "red_flags": flags, "optional": {"websites": domains, "phones_masked": masked},
            "province": r.province}


@app.post("/api/public/evidence")
async def public_add_evidence(request: Request, reference: str = Form(...), key: str = Form(...),
                              files: list[UploadFile] = File(...), db: Session = Depends(get_db)):
    r = _receipt_report(db, request, TrackIn(reference=reference[:24], key=key[:24]))
    if r.status == "closed":
        _err(409, "This report is closed in Ubufakazi.")
    blobs = await _read_files(files)
    if len(r.evidence) + len(blobs) > get_settings().max_files_per_report:
        _err(400, "Too many files for one report.")
    out = services.add_more_evidence(r.id, blobs, channel="web", ip=client_ip(request))
    if out["added"]:
        services.enqueue(r.id)
    return out


# ------------------------------------------------------------------ auth
class LoginIn(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(max_length=200)


class CodeIn(BaseModel):
    code: str = Field(max_length=12)


_DUMMY_HASH = hash_password("timing-equaliser-not-a-password")


def _me(s, principal_user: User) -> dict:
    u = principal_user
    return {"username": u.username, "display_name": u.display_name, "role": u.role, "csrf": s.csrf_token,
            "stations": [{"code": st.code, "name": st.name} for st in u.stations], "mfa": bool(u.totp_secret)}


@app.post("/api/auth/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    rate_limit(request, "login", 10, 300)
    ip = client_ip(request)
    with write_lock:
        u = db.query(User).filter_by(username=body.username.strip().lower()).first()
        if u and u.locked_until and u.locked_until > utcnow():
            audit.record(db, "login.locked", actor=f"user:{u.username}", actor_user_id=u.id, ip=ip)
            _err(423, f"Too many failed attempts. Try again after {LOCK_MINUTES} minutes.")
        ok = verify_password(u.password_hash if u else _DUMMY_HASH, body.password) and bool(u) and u.active
        if not ok:
            if u:
                u.failed_logins += 1
                if u.failed_logins >= LOCK_AFTER:
                    u.locked_until = utcnow() + dt.timedelta(minutes=LOCK_MINUTES)
                    u.failed_logins = 0
            audit.record(db, "login.failed", actor=f"user:{body.username[:40]}", actor_user_id=u.id if u else None, ip=ip)
            _err(401, "Wrong username or password.")
        u.failed_logins = 0
        db.commit()
    token, s = create_session(db, u, ip, mfa_pending=bool(u.totp_secret))
    resp = JSONResponse({"mfa_required": s.mfa_pending, "csrf": s.csrf_token,
                         **({} if s.mfa_pending else {"me": _me(s, u)})})
    set_session_cookie(resp, token)
    if not s.mfa_pending:
        with write_lock:
            audit.record(db, "login.success", actor=f"user:{u.username}", actor_user_id=u.id, ip=ip)
    return resp


@app.post("/api/auth/mfa")
def mfa(body: CodeIn, request: Request, db: Session = Depends(get_db)):
    rate_limit(request, "mfa", 10, 300)
    s = load_session(request, db)
    if not s or not s.mfa_pending:
        _err(401, "Please sign in again.")
    _require_csrf(request, s)
    u = s.user
    if not verify_totp(u.totp_secret, body.code):
        with write_lock:
            audit.record(db, "login.mfa_failed", actor=f"user:{u.username}", actor_user_id=u.id, ip=client_ip(request))
        _err(401, "That code is not valid. Codes change every 30 seconds.")
    with write_lock:
        db.delete(s)
        db.commit()
    token, s2 = create_session(db, u, client_ip(request), mfa_pending=False)   # new token after MFA
    with write_lock:
        audit.record(db, "login.success", actor=f"user:{u.username}", actor_user_id=u.id, ip=client_ip(request),
                     detail={"mfa": True})
    resp = JSONResponse({"me": _me(s2, u)})
    set_session_cookie(resp, token)
    return resp


@app.get("/api/auth/me")
def me(request: Request, db: Session = Depends(get_db)):
    s = load_session(request, db)
    if not s or s.mfa_pending:
        _err(401, "Please sign in.")
    return _me(s, s.user)


@app.post("/api/auth/logout")
def logout(request: Request, p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    with write_lock:
        s = db.merge(p.session)
        audit.record(db, "logout", actor=f"user:{p.user.username}", actor_user_id=p.user.id, ip=client_ip(request),
                     commit=False)
        db.delete(s)
        db.commit()
    resp = JSONResponse({"ok": True})
    clear_session_cookie(resp)
    return resp


# ------------------------------------------------------------------ police
officer = require_roles("admin", "officer")


def _actor(p: Principal) -> str:
    return f"user:{p.user.username}"


def _ident_ids(db: Session, text: str) -> set[int]:
    """Report ids whose identifiers match the search text (compared by keyed hash, never by raw scan)."""
    t = text.strip()
    cands = []
    digits = re.sub(r"\D", "", t)
    if 8 <= len(digits) <= 12:
        cands.append(("account", digits))
    ph = norm_phone(t)
    if ph:
        cands.append(("phone", ph))
    if "@" in t and "." in t:
        cands.append(("email", t.lower()))
    elif t.startswith("@"):
        cands.append(("username", t.lower()))
    if re.fullmatch(r"(https?://)?[a-z0-9.-]+\.[a-z]{2,}(/\S*)?", t.lower()):
        host = re.sub(r"^https?://", "", t.lower()).split("/")[0]
        cands.append(("domain", reg_domain(host)))
    ids = set()
    for kind, val in cands:
        ids |= {rid for (rid,) in db.query(Identifier.report_id).filter_by(kind=kind, hmac=identifier_hmac(kind, val)).all()}
    return ids


@app.get("/api/police/overview")
def police_overview(p: Principal = Depends(officer), db: Session = Depends(get_db)):
    return {"stats": police.stats(db, p), "stations": police.stations_for(db, p),
            "statuses": STATUS_LABELS, "categories": CATEGORIES}


@app.get("/api/police/reports")
def police_reports(status: str = "", category: str = "", station: str = "", q: str = "", linked: int = 0,
                   sort: str = "newest", page: int = 1, page_size: int = 25,
                   p: Principal = Depends(officer), db: Session = Depends(get_db)):
    query = police.scope_reports(db, p)
    if status in STATUSES:
        query = query.filter(Report.status == status)
    elif status == "open":
        query = query.filter(Report.status != "closed")
    if category in CATEGORY_LABELS:
        query = query.filter(Report.category == category)
    if station:
        query = query.join(Report.station).filter_by(code=station[:12])
    if q.strip():
        ids = _ident_ids(db, q)
        query = query.filter(Report.id.in_(ids)) if ids else police.search(query, q)
    if linked:
        a = {x for (x,) in db.query(IntelMatch.report_a).all()} | {x for (x,) in db.query(IntelMatch.report_b).all()}
        query = query.filter(Report.id.in_(a or {-1}))
    order = {"newest": Report.created_at.desc(), "oldest": Report.created_at.asc(),
             "amount": Report.amount_paid.desc().nulls_last()}.get(sort, Report.created_at.desc())
    page_size = max(5, min(page_size, 100))
    total = query.count()
    rows = query.order_by(order).offset((max(page, 1) - 1) * page_size).limit(page_size).all()
    ids = [r.id for r in rows]
    lead_counts = {}
    if ids:
        for a, b, strength in db.query(IntelMatch.report_a, IntelMatch.report_b, IntelMatch.strength).filter(
                (IntelMatch.report_a.in_(ids)) | (IntelMatch.report_b.in_(ids))).all():
            for x in (a, b):
                if x in ids:
                    c = lead_counts.setdefault(x, {"leads": 0, "corroborated": 0})
                    c["leads"] += 1
                    c["corroborated"] += strength == "corroborated"
    items = [{**police.summary(r), **lead_counts.get(r.id, {"leads": 0, "corroborated": 0})} for r in rows]
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@app.get("/api/police/evidence")
def police_evidence(q: str = "", type: str = "", page: int = 1, page_size: int = 30,
                    p: Principal = Depends(officer), db: Session = Depends(get_db)):
    """Evidence inventory across the reports this officer may see (metadata only, never file contents)."""
    query = db.query(EvidenceFile).join(Report, EvidenceFile.report_id == Report.id)
    if not p.is_admin:
        query = query.filter(Report.station_id.in_(p.station_ids or {-1}))
    groups = {"image": ("jpeg", "png", "webp", "gif"), "document": ("pdf",), "text": ("txt",),
              "audio": ("mp3", "ogg", "wav", "m4a"), "video": ("mp4", "mov", "webm")}
    if type in groups:
        query = query.filter(EvidenceFile.detected_type.in_(groups[type]))
    if q.strip():
        like = f"%{q.strip()[:80]}%"
        query = query.filter((EvidenceFile.original_name.ilike(like)) | (EvidenceFile.sha256.ilike(like)) |
                             (Report.reference.ilike(like)))
    page_size = max(5, min(page_size, 100))
    total = query.count()
    rows = query.order_by(EvidenceFile.received_at.desc()).offset((max(page, 1) - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "items": [
        {"id": e.id, "name": e.original_name, "type": e.detected_type, "size": e.size, "sha256": e.sha256,
         "received_at": e.received_at.isoformat() + "Z", "channel": e.channel, "reference": e.report.reference,
         "station": e.report.station.name, "previewable": e.detected_type in ("jpeg", "png", "webp", "gif"),
         "processed": [d.kind for d in e.derivatives]} for e in rows]}


@app.get("/api/police/reports/{reference}")
def police_report(reference: str, request: Request, p: Principal = Depends(officer), db: Session = Depends(get_db)):
    r = police.get_report(db, p, reference)
    with write_lock:
        audit.record(db, "report.viewed", actor=_actor(p), actor_user_id=p.user.id, target_type="report",
                     target_id=r.reference, station_id=r.station_id, ip=client_ip(request))
    from .models import Consent
    consent = db.query(Consent).filter_by(report_id=r.id).first()
    return {
        **police.summary(r),
        "description": r.description, "answers": r.answers, "safety": r.safety, "language": r.language,
        "location": {"lat": r.location_lat, "lon": r.location_lon, "precision": "about 1 km"} if r.location_lat else None,
        "facts": r.facts, "statement": r.statement, "statements": r.statements, "bank_report": r.bank_report,
        "processing_note": r.processing_note,
        "consent": {"version": consent.version, "given_at": consent.given_at.isoformat() + "Z"} if consent else None,
        "evidence": [{"id": e.id, "name": e.original_name, "type": e.detected_type, "declared_mime": e.declared_mime,
                      "size": e.size, "sha256": e.sha256, "received_at": e.received_at.isoformat() + "Z", "channel": e.channel,
                      "trusted_timestamp": bool(e.trusted_timestamp),
                      "timestamp": timestamps.public_info(e.trusted_timestamp),
                      "previewable": e.detected_type in ("jpeg", "png", "webp", "gif"),
                      "derivatives": [{"kind": d.kind, "method": d.method, "ai_generated": d.ai_generated, "note": d.note,
                                       "content": d.content[:20000], "truncated": len(d.content) > 20000,
                                       "content_sha256": d.content_sha256} for d in e.derivatives]}
                     for e in r.evidence],
        "timeline": [{"when": e.when_text, "at": e.at.isoformat() if e.at else None, "kind": e.kind, "what": e.what,
                      "quote": e.quote, "source": e.source} for e in r.timeline],
        "identifiers": [{"kind": i.kind, "display": i.display, "bank": i.bank, "source": i.source} for i in r.identifiers],
        "history": [{"at": h.at.isoformat() + "Z", "from": h.from_status, "to": h.to_status,
                     "to_label": STATUS_LABELS.get(h.to_status, h.to_status), "note": h.note,
                     "by": (db.get(User, h.by_user_id).display_name if h.by_user_id else "Ubufakazi")}
                    for h in db.query(StatusChange).filter_by(report_id=r.id).order_by(StatusChange.at)],
        "notes": [{"at": n.created_at.isoformat() + "Z", "by": n.author.display_name, "body": n.body}
                  for n in db.query(Note).filter_by(report_id=r.id).order_by(Note.created_at)],
        "leads": police.leads_for(db, r, p),
        "handover": _handover_info(db, r),
        "bank_responses": banklink.responses_for_report(db, r),
    }


def _evidence(db: Session, p: Principal, evidence_id: int) -> EvidenceFile:
    e = db.get(EvidenceFile, evidence_id)
    if not e or not p.can_see_station(e.report.station_id):
        _err(404, "Not found.")
    return e


@app.get("/api/police/evidence/{evidence_id}/download")
def evidence_download(evidence_id: int, request: Request, inline: int = 0, p: Principal = Depends(officer),
                      db: Session = Depends(get_db)):
    e = _evidence(db, p, evidence_id)
    data = storage.read_original(e.uid)
    with write_lock:
        audit.record(db, "evidence.previewed" if inline else "evidence.downloaded", actor=_actor(p), actor_user_id=p.user.id,
                     target_type="evidence", target_id=e.id, station_id=e.report.station_id, ip=client_ip(request),
                     detail={"report": e.report.reference, "sha256": e.sha256})
    if inline and e.detected_type in ("jpeg", "png", "webp", "gif"):
        return Response(data, media_type=storage.TYPES[e.detected_type][1],
                        headers={"Content-Security-Policy": "default-src 'none'; sandbox"})
    return Response(data, media_type="application/octet-stream",
                    headers={"Content-Disposition": f'attachment; filename="{e.report.reference}-{e.id}-{e.original_name}"',
                             "Content-Security-Policy": "default-src 'none'; sandbox"})


@app.post("/api/police/evidence/{evidence_id}/verify")
def evidence_verify(evidence_id: int, request: Request, p: Principal = Depends(officer), db: Session = Depends(get_db)):
    e = _evidence(db, p, evidence_id)
    now = storage.rehash(e.uid)
    ok = now == e.sha256
    ts_ok, ts_note = None, None
    if e.trusted_timestamp:
        try:
            info = timestamps.verify(timestamps.token_bytes(e.trusted_timestamp), now)
            ts_ok, ts_note = True, f"Trusted timestamp valid: {info['gen_time']} by {info['tsa']}"
        except (timestamps.TimestampError, ValueError, KeyError) as ex:
            ts_ok, ts_note = False, f"Trusted timestamp does NOT match: {ex}"
    with write_lock:
        audit.record(db, "evidence.verified", actor=_actor(p), actor_user_id=p.user.id, target_type="evidence",
                     target_id=e.id, station_id=e.report.station_id, ip=client_ip(request),
                     detail={"match": ok, "timestamp_ok": ts_ok, "report": e.report.reference})
    return {"match": ok, "recorded_sha256": e.sha256, "current_sha256": now, "checked_at": utcnow().isoformat() + "Z",
            "timestamp_ok": ts_ok, "timestamp_note": ts_note}


@app.get("/api/police/evidence/{evidence_id}/timestamp")
def evidence_timestamp(evidence_id: int, request: Request, p: Principal = Depends(officer), db: Session = Depends(get_db)):
    """The RFC 3161 reply (.tsr) for independent checking with openssl."""
    e = _evidence(db, p, evidence_id)
    if not e.trusted_timestamp:
        raise HTTPException(404, "This file has no trusted timestamp.")
    with write_lock:
        audit.record(db, "evidence.timestamp_downloaded", actor=_actor(p), actor_user_id=p.user.id, target_type="evidence",
                     target_id=e.id, station_id=e.report.station_id, ip=client_ip(request),
                     detail={"report": e.report.reference})
    return Response(timestamps.token_bytes(e.trusted_timestamp), media_type="application/timestamp-reply",
                    headers={"Content-Disposition": f'attachment; filename="{e.report.reference}-{e.id}.tsr"',
                             "Content-Security-Policy": "default-src 'none'; sandbox"})


# ------------------------------------------------------------------ station handover (no SAPS connection)
def _handover_info(db: Session, r: Report) -> dict | None:
    h = db.query(StationHandover).filter_by(report_id=r.id).first()
    if not h:
        return None
    by = db.get(User, h.accepted_by_user_id)
    cas_by = db.get(User, h.cas_recorded_by_user_id) if h.cas_recorded_by_user_id else None
    return {"station": db.get(Station, h.station_id).name, "from_station": db.get(Station, h.from_station_id).name,
            "moved": h.station_id != h.from_station_id, "accepted_by": by.display_name if by else "-",
            "accepted_at": h.accepted_at.isoformat() + "Z", "cas_number": h.cas_number,
            "cas_recorded_by": cas_by.display_name if cas_by else None,
            "cas_recorded_at": h.cas_recorded_at.isoformat() + "Z" if h.cas_recorded_at else None}


def _handover_report(db: Session, request: Request, reference: str, token: str) -> Report:
    rate_limit(request, "handover", 20, 300)
    r = db.query(Report).filter_by(reference=reference).first()
    if not r or not handover.check_token(reference, token):
        _err(404, "This handover code is not valid. Ask the complainant for their Ubufakazi case pack.")
    return r


@app.get("/api/police/handover/{reference}/{token}")
def handover_preview(reference: str, token: str, request: Request, p: Principal = Depends(officer),
                     db: Session = Depends(get_db)):
    """What an officer sees after scanning a complainant's QR code, before accepting the case at their station."""
    r = _handover_report(db, request, reference, token)
    with write_lock:
        audit.record(db, "handover.viewed", actor=_actor(p), actor_user_id=p.user.id, target_type="report",
                     target_id=r.reference, station_id=r.station_id, ip=client_ip(request))
    mine = [{"id": st.id, "name": st.name} for st in (db.query(Station).order_by(Station.name).all() if p.is_admin
                                                      else p.user.stations)]
    return {"reference": r.reference, "category_label": CATEGORY_LABELS.get(r.category, r.category),
            "received": r.created_at.isoformat() + "Z", "routed_station": r.station.name,
            "routed_station_id": r.station_id, "complainant_name": r.complainant_name,
            "town": r.town, "province": r.province, "evidence_count": len(r.evidence),
            "can_open": p.can_see_station(r.station_id), "my_stations": mine, "handover": _handover_info(db, r)}


class HandoverIn(BaseModel):
    station_id: int


@app.post("/api/police/handover/{reference}/{token}/accept")
def handover_accept(reference: str, token: str, body: HandoverIn, request: Request, p: Principal = Depends(officer),
                    db: Session = Depends(get_db)):
    r = _handover_report(db, request, reference, token)
    if not p.is_admin and body.station_id not in p.station_ids:
        _err(403, "You can only accept a case at your own station.")
    st = db.get(Station, body.station_id)
    if not st:
        _err(400, "Unknown station.")
    with write_lock:
        h = db.query(StationHandover).filter_by(report_id=r.id).first()
        frm = r.station_id
        if h is None:
            h = StationHandover(report_id=r.id, station_id=st.id, from_station_id=frm, accepted_by_user_id=p.user.id)
            db.add(h)
        else:
            h.station_id, h.accepted_by_user_id, h.accepted_at = st.id, p.user.id, utcnow()
        if frm != st.id:
            r.station_id = st.id
            audit.record(db, "report.transferred", actor=_actor(p), actor_user_id=p.user.id, target_type="report",
                         target_id=r.reference, station_id=st.id, ip=client_ip(request),
                         detail={"from_station": frm, "to_station": st.id, "reason": "complainant presented case pack"})
        audit.record(db, "handover.accepted", actor=_actor(p), actor_user_id=p.user.id, target_type="report",
                     target_id=r.reference, station_id=st.id, ip=client_ip(request), detail={"station": st.code})
        db.add(StatusChange(report_id=r.id, from_status=r.status, to_status=r.status, by_user_id=p.user.id,
                            note=f"Complainant presented the case pack at {st.name}; case accepted there."))
        db.commit()
    return {"reference": r.reference, "station": st.name}


class CasIn(BaseModel):
    cas_number: str = Field(min_length=3, max_length=40)


@app.post("/api/police/reports/{reference}/cas")
def record_cas(reference: str, body: CasIn, request: Request, p: Principal = Depends(officer), db: Session = Depends(get_db)):
    """Stores the CAS number the station issued. Typed in by an officer; never generated or checked against SAPS."""
    r = police.get_report(db, p, reference)
    try:
        cas = handover.normalise_cas(body.cas_number)
    except ValueError as e:
        _err(400, str(e))
    with write_lock:
        h = db.query(StationHandover).filter_by(report_id=r.id).first()
        if h is None:
            h = StationHandover(report_id=r.id, station_id=r.station_id, from_station_id=r.station_id,
                                accepted_by_user_id=p.user.id)
            db.add(h)
        h.cas_number, h.cas_recorded_by_user_id, h.cas_recorded_at = cas, p.user.id, utcnow()
        audit.record(db, "report.cas_recorded", actor=_actor(p), actor_user_id=p.user.id, target_type="report",
                     target_id=r.reference, station_id=r.station_id, ip=client_ip(request), detail={"cas_number": cas})
        db.flush()
    services.change_status(db, r, "registered_at_station", user_id=p.user.id, actor=_actor(p),
                           note=f"{cas} recorded by the officer (issued by {r.station.name}; not verified with SAPS)",
                           ip=client_ip(request))
    db.commit()
    return {"cas_number": cas, "status": r.status, "status_label": STATUS_LABELS[r.status]}


class StatusIn(BaseModel):
    status: str
    note: str = Field("", max_length=1000)


@app.post("/api/police/reports/{reference}/status")
def set_status(reference: str, body: StatusIn, request: Request, p: Principal = Depends(officer),
               db: Session = Depends(get_db)):
    r = police.get_report(db, p, reference)
    if body.status == "registered_at_station":
        _err(400, "Record the CAS number the station issued to mark the case as registered.")
    try:
        services.change_status(db, r, body.status, user_id=p.user.id, actor=_actor(p), note=body.note, ip=client_ip(request))
    except services.ReportError as e:
        _err(400, str(e))
    return {"status": r.status, "status_label": STATUS_LABELS[r.status]}


class NoteIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


@app.post("/api/police/reports/{reference}/notes")
def add_note(reference: str, body: NoteIn, request: Request, p: Principal = Depends(officer), db: Session = Depends(get_db)):
    r = police.get_report(db, p, reference)
    with write_lock:
        db.add(Note(report_id=r.id, author_id=p.user.id, body=body.body.strip()))
        audit.record(db, "note.added", actor=_actor(p), actor_user_id=p.user.id, target_type="report",
                     target_id=r.reference, station_id=r.station_id, ip=client_ip(request), detail={"length": len(body.body)})
    return {"ok": True}


@app.post("/api/police/reports/{reference}/reprocess")
def reprocess(reference: str, request: Request, p: Principal = Depends(officer), db: Session = Depends(get_db)):
    r = police.get_report(db, p, reference)
    if r.is_seed:
        _err(400, "Synthetic seed records have no evidence to process.")
    with write_lock:
        audit.record(db, "report.reprocess", actor=_actor(p), actor_user_id=p.user.id, target_type="report",
                     target_id=r.reference, station_id=r.station_id, ip=client_ip(request))
    services.enqueue(r.id)
    return {"ok": True}


@app.get("/api/police/reports/{reference}/pack")
def police_pack(reference: str, request: Request, p: Principal = Depends(officer), db: Session = Depends(get_db)):
    r = police.get_report(db, p, reference)
    pdf = build_case_pack(db, r, "police", viewer=p, leads=police.leads_for(db, r, p))
    with write_lock:
        audit.record(db, "pack.police", actor=_actor(p), actor_user_id=p.user.id, target_type="report",
                     target_id=r.reference, station_id=r.station_id, ip=client_ip(request))
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="Ubufakazi-{r.reference}-POLICE.pdf"'})


@app.get("/api/police/reports/{reference}/graph")
def report_graph(reference: str, p: Principal = Depends(officer), db: Session = Depends(get_db)):
    return police.graph_for(db, police.get_report(db, p, reference), p)


@app.get("/api/police/reports/{reference}/audit")
def report_audit(reference: str, p: Principal = Depends(officer), db: Session = Depends(get_db)):
    r = police.get_report(db, p, reference)
    ev_ids = [str(e.id) for e in r.evidence] or ["-"]
    q = db.query(AuditEvent).filter(((AuditEvent.target_type == "report") & (AuditEvent.target_id == r.reference)) |
                                    ((AuditEvent.target_type == "evidence") & (AuditEvent.target_id.in_(ev_ids))))
    return [{"id": a.id, "at": a.at.isoformat() + "Z", "action": a.action, "actor": a.actor, "target": f"{a.target_type}:{a.target_id}",
             "hash": a.hash, "prev_hash": a.prev_hash} for a in q.order_by(AuditEvent.id).limit(500)]


@app.get("/api/police/intel/clusters")
def intel_clusters(p: Principal = Depends(officer), db: Session = Depends(get_db)):
    return police.clusters(db, p)


@app.get("/api/police/intel/board")
def police_board(p: Principal = Depends(officer), db: Session = Depends(get_db)):
    return police.board(db, p)


@app.get("/api/police/audit/verify")
def audit_verify(p: Principal = Depends(officer), db: Session = Depends(get_db)):
    return audit.verify_chain(db)


@app.get("/api/admin/audit")
def admin_audit(limit: int = 100, p: Principal = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    rows = db.query(AuditEvent).order_by(AuditEvent.id.desc()).limit(max(1, min(limit, 500))).all()
    return {"verify": audit.verify_chain(db),
            "events": [{"id": a.id, "at": a.at.isoformat() + "Z", "action": a.action, "actor": a.actor,
                        "target": f"{a.target_type}:{a.target_id}" if a.target_type else "", "ip": a.ip,
                        "hash": a.hash} for a in rows]}


# ------------------------------------------------------------------ bank link (to the fictional Ubuntu Trust Bank)
bank_role = require_roles("admin", "bank_reviewer")


@app.post("/api/bank-link/callback")
async def bank_callback(request: Request):
    """The bank reports a decision back to Ubufakazi. Signed; no session needed."""
    raw = await request.body()
    try:
        return await run_in_threadpool(banklink.receive_callback, raw, request.headers.get("X-UBF-Signature"))
    except PermissionError:
        _signature_rejected(request, "bank-link callback")
        _err(401, "Bad signature.")
    except (ValueError, KeyError):
        _err(400, "Bad request.")


def _signature_rejected(request: Request, where: str) -> None:
    from .db import session_scope
    with write_lock, session_scope() as db:
        audit.record(db, "bank.signature_rejected", actor="unknown", ip=client_ip(request), detail={"endpoint": where})


@app.get("/api/admin/security")
def admin_security(p: Principal = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    from . import secmon
    return secmon.alerts(db)


# ------------------------------------------------------------------ beneficiary check (subscribed banks only)
@app.post("/api/v1/beneficiary-check")
async def beneficiary_check(request: Request):
    raw = await request.body()
    try:
        return await run_in_threadpool(payee.handle, raw, request.headers)
    except payee.CheckRefused as e:
        _err(e.status, e.message)


@app.post("/api/utb/payment-check")
async def utb_payment_check(request: Request, p: Principal = Depends(bank_role)):
    """The fictional bank's own app backend: its customer is about to pay a new beneficiary."""
    try:
        body = await request.json()
        assert isinstance(body, dict)
    except Exception:                                        # noqa: BLE001
        _err(400, "Bad request.")
    number = "".join(ch for ch in str(body.get("account_number", "")) if ch.isdigit())
    if not 6 <= len(number) <= 16:
        _err(400, "Enter an account number of 6 to 16 digits.")
    try:
        amount = float(body["amount"]) if body.get("amount") not in (None, "") else None
    except (TypeError, ValueError):
        _err(400, "Enter a valid amount.")
    status, res = await run_in_threadpool(payee.client_check, "utb", number, amount)
    if status != 200:
        _err(502, "Ubufakazi did not answer the check (HTTP %s)." % status)
    return res


# ------------------------------------------------------------------ Ubuntu Trust Bank (FICTIONAL bank, own API)
@app.post("/utb/api/v1/fraud-alerts", status_code=202)
async def utb_receive(request: Request):
    raw = await request.body()
    if len(raw) > 200_000:
        _err(413, "Too large.")
    try:
        return await run_in_threadpool(utb.receive_alert, raw, request.headers.get("X-UBF-Signature"))
    except PermissionError:
        _signature_rejected(request, "fictional bank fraud-alert API")
        _err(401, "Bad signature.")
    except (ValueError, KeyError):
        _err(400, "Bad request.")


@app.get("/api/utb/cases")
def utb_cases(p: Principal = Depends(bank_role), db: Session = Depends(get_db)):
    from .models import UtbCase
    utb.seed_registry(db)
    items = [utb.case_row(db, c) for c in db.query(UtbCase).all()]
    syncing = False
    if not items and db.query(BankAlert).filter(BankAlert.bank_stated.in_(banklink.ROUTED_BANKS)).first():
        banklink.backfill_soon()                 # alerts exist but have not reached the bank yet
        syncing = True
    items.sort(key=lambda x: ({"received": 0, "investigating": 1, "frozen": 2}.get(x["status"], 3), -x["reports"],
                              -x["total_reported"]))
    return {"bank": utb.NAME, "statuses": utb.STATUS, "items": items, "syncing": syncing,
            "notice": "Ubuntu Trust Bank is a fictional bank. These alerts arrived from Ubufakazi over its signed API. "
                      "No real bank, account or person is involved."}


@app.get("/api/utb/cases/{case_id}")
def utb_case(case_id: int, p: Principal = Depends(bank_role), db: Session = Depends(get_db)):
    from .models import UtbCase
    c = db.get(UtbCase, case_id)
    if not c:
        _err(404, "Not found.")
    return utb.case_detail(db, c)


class UtbActionIn(BaseModel):
    action: str


@app.post("/api/utb/cases/{case_id}/action")
def utb_action(case_id: int, body: UtbActionIn, request: Request, p: Principal = Depends(bank_role)):
    try:
        return utb.act(case_id, body.action, by=p.user.display_name)
    except LookupError:
        _err(404, "Not found.")
    except ValueError as e:
        _err(400, str(e))


# ------------------------------------------------------------------ pages + website
PAGES = {"/": "home.html", "/demo-logins": "demo-logins.html", "/share": "share.html", "/resources": "resources.html", "/about": "about.html",
         "/police": "police.html", "/bank-demo": "bank.html", "/bank": "bank.html", "/report": "report.html", "/track": "track.html",
         "/verify": "verify.html", "/integrations": "integrations.html", "/privacy": "privacy.html", "/banks": "banks.html", "/security": "security.html"}


def _page(name: str):
    def handler():
        return FileResponse(WEB_DIR / name, media_type="text/html")
    return handler


for _path, _file in PAGES.items():
    app.add_api_route(_path, _page(_file), methods=["GET"], include_in_schema=False)


@app.get("/mvp", include_in_schema=False)
def mvp_page():
    """The original browser-only MVP case builder (also what the Netlify site serves)."""
    return FileResponse(SITE_DIR / "index.html", media_type="text/html")

app.mount("/app", StaticFiles(directory=WEB_DIR), name="web")
app.mount("/", StaticFiles(directory=SITE_DIR, html=True), name="site")
