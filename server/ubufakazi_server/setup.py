"""One-command local setup for the demo.

    python -m ubufakazi_server.setup            # create .env (random secrets), database, stations, users, seed data
    python -m ubufakazi_server.setup --reset    # wipe ./data and start again (demo data only!)

Demo account passwords are random and written to DEMO-CREDENTIALS.txt (git-ignored), never printed into code.
Every account uses two-factor codes; get the current code with:  python -m ubufakazi_server.totp <username>
"""
from __future__ import annotations

import argparse
import secrets
import shutil
import sys

import os

from .config import SERVER_DIR, data_dir, get_settings, reset_settings

USERS = [
    # username, display name, role, station codes
    ("admin", "Demo Administrator", "admin", []),
    ("officer.mthatha", "Demo Officer (Mthatha)", "officer", ["MTH"]),
    ("officer.joburg", "Demo Officer (Johannesburg)", "officer", ["JHB", "ALB"]),
    ("officer.durban", "Demo Officer (Durban)", "officer", ["DBN"]),
    ("bank.reviewer", "DemoBank Fraud Reviewer (fictional bank)", "bank_reviewer", []),
]
# On a host with a persistent volume (UBF_DATA_DIR), generated secrets are kept on the volume so they survive restarts.
ENV_FILE = (data_dir() / ".env") if os.environ.get("UBF_DATA_DIR") else SERVER_DIR / ".env"
CREDS_FILE = SERVER_DIR / "DEMO-CREDENTIALS.txt"


def _password() -> str:
    words = ["amandla", "ubuntu", "indlela", "isibane", "ilanga", "inkanyezi", "umthetho", "ubulungisa", "imvula", "intaba"]
    return "-".join(secrets.choice(words) for _ in range(3)) + "-" + str(secrets.randbelow(9000) + 1000)


def write_env() -> bool:
    if ENV_FILE.exists():
        return False
    if os.environ.get("UBF_DATA_DIR"):
        # hosted: only generate what the host's variables do not already provide
        ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"{k}={secrets.token_urlsafe(48)}" for k in ("UBF_SECRET_KEY", "UBF_HMAC_KEY") if not os.environ.get(k)]
        ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
        ENV_FILE.chmod(0o600)
        return True
    example = (SERVER_DIR / ".env.example").read_text(encoding="utf-8")
    lines = []
    for line in example.splitlines():
        if line.startswith("UBF_SECRET_KEY="):
            line = "UBF_SECRET_KEY=" + secrets.token_urlsafe(48)
        elif line.startswith("UBF_HMAC_KEY="):
            line = "UBF_HMAC_KEY=" + secrets.token_urlsafe(48)
        lines.append(line)
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ENV_FILE.chmod(0o600)
    return True


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reset", action="store_true", help="delete ./data (database + evidence) first")
    ap.add_argument("--no-seed", action="store_true", help="do not load the synthetic earlier reports")
    args = ap.parse_args(argv)

    if write_env():
        print(f"Created {ENV_FILE.name} with new random secrets.")
    reset_settings()
    s = get_settings()
    ddir = data_dir()
    if args.reset and ddir.exists():
        for child in ddir.iterdir():
            if child.name == ".env":
                continue          # keep the secrets
            shutil.rmtree(child, onerror=lambda f, p, e: (os.chmod(p, 0o600), f(p))) if child.is_dir() else child.unlink()
        CREDS_FILE.unlink(missing_ok=True)
        print(f"Deleted demo data in {ddir}")
    ddir.mkdir(parents=True, exist_ok=True)
    s.storage_dir.mkdir(parents=True, exist_ok=True)

    from .db import init_db, session_scope, write_lock
    from .models import Station, User
    from .security import hash_password, new_totp_secret, totp_uri
    from . import audit, seed
    from .creds import password_for, totp_secret_for

    init_db()
    created_users = []
    with write_lock, session_scope() as db:
        stations = seed.seed_stations(db)
        for username, display, role, codes in USERS:
            if db.query(User).filter_by(username=username).first():
                continue
            if s.demo_seed:
                pw, secret = password_for(s.demo_seed, username), totp_secret_for(s.demo_seed, username)
            else:
                pw, secret = _password(), new_totp_secret()
            u = User(username=username, display_name=display, role=role, password_hash=hash_password(pw), totp_secret=secret)
            u.stations = [stations[c] for c in codes]
            db.add(u)
            created_users.append((username, role, codes, pw, secret))
        db.flush()
        n = 0 if args.no_seed else seed.seed_reports(db)
        if created_users:
            audit.record(db, "setup.users", actor="setup", detail={"created": [u[0] for u in created_users]})
        st_count = db.query(Station).count()

    if created_users and s.demo_seed:
        print(f"Created {len(created_users)} demo accounts from UBF_DEMO_SEED. See them with: python -m ubufakazi_server.creds")
    elif created_users:
        with CREDS_FILE.open("a", encoding="utf-8") as f:
            f.write("UBUFAKAZI 2.0 DEMO ACCOUNTS (fictional, local demo only, do not commit)\n")
            f.write("Two-factor code:  python -m ubufakazi_server.totp <username>   (or scan the otpauth link)\n\n")
            for username, role, codes, pw, secret in created_users:
                f.write(f"{username:18} role={role:14} stations={','.join(codes) or '-':8} password={pw}\n")
                f.write(f"{'':18} totp_secret={secret}\n{'':18} {totp_uri(secret, username)}\n\n")
        CREDS_FILE.chmod(0o600)
        print(f"Created {len(created_users)} demo accounts. Passwords are in {CREDS_FILE.name} (git-ignored).")
    print(f"Stations: {st_count} fictional demo stations. Seed reports added: {n}.")
    print("Start the server:  uvicorn ubufakazi_server.app:app --port 8000   then open http://localhost:8000")
    if s.telegram_token:
        print("Telegram token found: the bot starts together with the server.")
    else:
        print("Telegram: not configured (set TELEGRAM_BOT_TOKEN in .env or your host's variables to enable the bot).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
