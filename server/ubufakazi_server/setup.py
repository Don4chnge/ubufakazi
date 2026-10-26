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

from .config import SERVER_DIR, get_settings, reset_settings

USERS = [
    # username, display name, role, station codes
    ("admin", "Demo Administrator", "admin", []),
    ("officer.mthatha", "Demo Officer (Mthatha)", "officer", ["MTH"]),
    ("officer.joburg", "Demo Officer (Johannesburg)", "officer", ["JHB", "ALB"]),
    ("officer.durban", "Demo Officer (Durban)", "officer", ["DBN"]),
    ("bank.reviewer", "DemoBank Fraud Reviewer (fictional bank)", "bank_reviewer", []),
]
ENV_FILE = SERVER_DIR / ".env"
CREDS_FILE = SERVER_DIR / "DEMO-CREDENTIALS.txt"


def _password() -> str:
    words = ["amandla", "ubuntu", "indlela", "isibane", "ilanga", "inkanyezi", "umthetho", "ubulungisa", "imvula", "intaba"]
    return "-".join(secrets.choice(words) for _ in range(3)) + "-" + str(secrets.randbelow(9000) + 1000)


def write_env() -> bool:
    if ENV_FILE.exists():
        return False
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
    data_dir = SERVER_DIR / "data"
    if args.reset and data_dir.exists():
        shutil.rmtree(data_dir, onerror=lambda f, p, e: (__import__("os").chmod(p, 0o600), f(p)))
        CREDS_FILE.unlink(missing_ok=True)
        print("Deleted ./data")
    data_dir.mkdir(exist_ok=True)
    s.storage_dir.mkdir(parents=True, exist_ok=True)

    from .db import init_db, session_scope, write_lock
    from .models import Station, User
    from .security import hash_password, new_totp_secret, totp_uri
    from . import audit, seed

    init_db()
    created_users = []
    with write_lock, session_scope() as db:
        stations = seed.seed_stations(db)
        for username, display, role, codes in USERS:
            if db.query(User).filter_by(username=username).first():
                continue
            pw = _password()
            secret = new_totp_secret()
            u = User(username=username, display_name=display, role=role, password_hash=hash_password(pw), totp_secret=secret)
            u.stations = [stations[c] for c in codes]
            db.add(u)
            created_users.append((username, role, codes, pw, secret))
        db.flush()
        n = 0 if args.no_seed else seed.seed_reports(db)
        if created_users:
            audit.record(db, "setup.users", actor="setup", detail={"created": [u[0] for u in created_users]})
        st_count = db.query(Station).count()

    if created_users:
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
        print("Telegram token found. Start the bot:  python -m ubufakazi_server.bot")
    else:
        print("Telegram: not configured (add TELEGRAM_BOT_TOKEN to .env to enable the bot).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
