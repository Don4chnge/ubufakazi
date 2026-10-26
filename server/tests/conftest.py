"""Test fixtures: every test session gets a fresh temporary database, evidence store and random keys."""
import os
import pathlib
import secrets
import sys

import pyotp
import pytest

SERVER = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER))


@pytest.fixture(scope="session")
def env(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("ubf")
    # Set UBF_TEST_DATABASE_URL=postgresql://... to run the whole suite on Postgres with evidence stored in the DB.
    pg = os.environ.get("UBF_TEST_DATABASE_URL", "")
    os.environ.update({
        "UBF_SECRET_KEY": secrets.token_urlsafe(40), "UBF_HMAC_KEY": secrets.token_urlsafe(40),
        "DATABASE_URL": pg or f"sqlite:///{tmp}/test.db", "UBF_STORAGE_DIR": str(tmp / "evidence"), "UBF_STORAGE": "",
        "TELEGRAM_BOT_TOKEN": "", "GEMINI_API_KEY": "", "UBF_RUN_BOT": "0",
    })
    from ubufakazi_server import config, db, services
    config.reset_settings()
    db.reset_engine()
    services.SYNC_PROCESSING = True
    if pg:
        from ubufakazi_server.db import Base, engine
        from ubufakazi_server import models  # noqa: F401
        Base.metadata.drop_all(engine())
    db.init_db()
    from ubufakazi_server import seed
    from ubufakazi_server.models import User
    from ubufakazi_server.security import hash_password
    creds = {}
    with db.write_lock, db.session_scope() as s:
        st = seed.seed_stations(s)
        for username, role, codes in [("admin", "admin", []), ("officer.mthatha", "officer", ["MTH"]),
                                      ("officer.joburg", "officer", ["JHB", "ALB"]), ("bank.reviewer", "bank_reviewer", [])]:
            pw, secret = secrets.token_urlsafe(12), pyotp.random_base32()
            u = User(username=username, display_name=username, role=role, password_hash=hash_password(pw), totp_secret=secret)
            u.stations = [st[c] for c in codes]
            s.add(u)
            creds[username] = (pw, secret)
        s.flush()
        seed.seed_reports(s)
    return {"tmp": tmp, "creds": creds}


@pytest.fixture(scope="session")
def app(env):
    from ubufakazi_server.app import app as fastapi_app
    return fastapi_app


@pytest.fixture
def client(app):
    from fastapi.testclient import TestClient
    from ubufakazi_server.security import limiter
    limiter.reset()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def login(app, env):
    """Returns a function that signs a user in (password + TOTP) and returns (client, csrf)."""
    from fastapi.testclient import TestClient
    from ubufakazi_server.security import limiter
    clients = []

    def _login(username):
        limiter.reset()
        c = TestClient(app)
        c.__enter__()
        clients.append(c)
        pw, secret = env["creds"][username]
        r = c.post("/api/auth/login", json={"username": username, "password": pw})
        assert r.status_code == 200, r.text
        assert r.json()["mfa_required"] is True
        csrf = r.json()["csrf"]
        r = c.post("/api/auth/mfa", json={"code": pyotp.TOTP(secret).now()}, headers={"X-CSRF-Token": csrf})
        assert r.status_code == 200, r.text
        me = r.json()["me"]
        c.headers.update({"X-CSRF-Token": me["csrf"]})
        return c, me
    yield _login
    for c in clients:
        c.__exit__(None, None, None)


KIT = SERVER.parent / "site" / "demo-kit"


def db_backend():
    from ubufakazi_server.config import get_settings
    return get_settings().storage_backend == "db"
