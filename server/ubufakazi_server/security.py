"""Authentication, authorisation, CSRF protection, rate limiting and MFA.

- Passwords: Argon2id (argon2-cffi).
- Sessions: random 256-bit token in an HttpOnly, SameSite=Strict cookie; only its SHA-256 is stored.
- CSRF: every state-changing request on a session must send the session's CSRF token in X-CSRF-Token.
- MFA: TOTP (RFC 6238) for users that have it enabled; the session stays "mfa_pending" until verified.
- Rate limits: in-memory sliding windows per key (fine for one demo server; use Redis for several).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import secrets
import threading
import time
from collections import defaultdict, deque

import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import LoginSession, User, utcnow

SESSION_COOKIE = "ubf_session"
_ph = PasswordHasher()  # Argon2id defaults


def hash_password(pw: str) -> str:
    return _ph.hash(pw)


def verify_password(stored: str, pw: str) -> bool:
    try:
        return _ph.verify(stored, pw)
    except (VerificationError, InvalidHashError):
        return False


def sha256_hex(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()


def identifier_hmac(kind: str, value: str) -> str:
    """Keyed hash used to compare identifiers across reports without exposing them. Server-side only."""
    key = get_settings().hmac_key.encode()
    return hmac.new(key, f"{kind}:{value}".encode(), hashlib.sha256).hexdigest()


def sign(value: str) -> str:
    key = get_settings().secret_key.encode()
    return hmac.new(key, value.encode(), hashlib.sha256).hexdigest()


# ------------------------------------------------------------------ rate limiting
class RateLimiter:
    def __init__(self):
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window_s: int) -> bool:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > window_s:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True

    def reset(self):
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def rate_limit(request: Request, bucket: str, limit: int, window_s: int):
    if not limiter.check(f"{bucket}:{client_ip(request)}", limit, window_s):
        raise HTTPException(status_code=429, detail="Too many requests. Please wait a minute and try again.")


# ------------------------------------------------------------------ sessions
def create_session(db: Session, user: User, ip: str, mfa_pending: bool) -> tuple[str, LoginSession]:
    token = secrets.token_urlsafe(32)
    s = LoginSession(token_hash=sha256_hex(token), csrf_token=secrets.token_urlsafe(24), user_id=user.id,
                     mfa_pending=mfa_pending, ip=ip,
                     expires_at=utcnow() + dt.timedelta(hours=get_settings().session_hours))
    db.add(s)
    db.commit()
    return token, s


def set_session_cookie(response, token: str):
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="strict",
                        secure=get_settings().cookie_secure, max_age=get_settings().session_hours * 3600, path="/")


def clear_session_cookie(response):
    response.delete_cookie(SESSION_COOKIE, path="/")


def load_session(request: Request, db: Session) -> LoginSession | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token or len(token) > 200:
        return None
    s = db.query(LoginSession).filter_by(token_hash=sha256_hex(token)).first()
    if not s or s.expires_at < utcnow() or not s.user.active:
        return None
    return s


class Principal:
    def __init__(self, session: LoginSession):
        self.session = session
        self.user: User = session.user
        self.station_ids: set[int] = {st.id for st in self.user.stations}

    @property
    def is_admin(self) -> bool:
        return self.user.role == "admin"

    def can_see_station(self, station_id: int) -> bool:
        return self.is_admin or station_id in self.station_ids


def _require_csrf(request: Request, s: LoginSession):
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        sent = request.headers.get("X-CSRF-Token", "")
        if not sent or not hmac.compare_digest(sent, s.csrf_token):
            raise HTTPException(status_code=403, detail="Security check failed (CSRF). Reload the page.")


def current_principal(request: Request, db: Session = Depends(get_db)) -> Principal:
    s = load_session(request, db)
    if not s:
        raise HTTPException(status_code=401, detail="Please sign in.")
    if s.mfa_pending:
        raise HTTPException(status_code=401, detail="Two-factor verification required.")
    _require_csrf(request, s)
    return Principal(s)


def require_roles(*roles: str):
    def dep(p: Principal = Depends(current_principal)) -> Principal:
        if p.user.role not in roles:
            raise HTTPException(status_code=403, detail="Your role cannot access this.")
        return p
    return dep


# ------------------------------------------------------------------ TOTP
def new_totp_secret() -> str:
    return pyotp.random_base32()


def verify_totp(secret: str, code: str) -> bool:
    code = (code or "").strip().replace(" ", "")
    return bool(secret) and code.isdigit() and pyotp.TOTP(secret).verify(code, valid_window=1)


def totp_uri(secret: str, username: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name="Ubufakazi DEMO")
