"""Demo account credentials derived from one secret (UBF_DEMO_SEED), so a hosted server and your laptop agree.

On a host (Railway etc.) you cannot read files inside the container. Instead, set the same UBF_DEMO_SEED on the
host and in your local server/.env, then print the passwords and current two-factor codes on your laptop:

    python -m ubufakazi_server.creds              # passwords, 2FA setup keys and current codes
    python -m ubufakazi_server.creds --new-seed   # generate a strong seed to paste into the host's variables

Anyone with the seed can sign in to the demo accounts: treat it like a password and never commit it.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import sys
import time

WORDS = ["amandla", "ubuntu", "indlela", "isibane", "ilanga", "inkanyezi", "umthetho", "ubulungisa", "imvula", "intaba",
         "umfula", "isikhwama", "ithemba", "inqaba", "ukukhanya", "isiqhamo"]


def _mac(seed: str, label: str) -> bytes:
    return hmac.new(seed.encode(), label.encode(), hashlib.sha256).digest()


def password_for(seed: str, username: str) -> str:
    d = _mac(seed, "password:" + username)
    words = [WORDS[b % len(WORDS)] for b in d[:4]]
    return "-".join(words) + "-" + str(1000 + int.from_bytes(d[4:6], "big") % 9000)


def totp_secret_for(seed: str, username: str) -> str:
    return base64.b32encode(_mac(seed, "totp:" + username)[:20]).decode().rstrip("=")


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if "--new-seed" in argv:
        print(secrets.token_urlsafe(32))
        return 0
    import pyotp
    from .config import get_settings
    from .setup import USERS
    seed = get_settings().demo_seed
    if len(seed) < 20:
        print("UBF_DEMO_SEED is not set (or too short). Put the same value in server/.env and in your host's variables.")
        return 2
    print("UBUFAKAZI DEMO ACCOUNTS (fictional data; keep private)\n")
    for username, display, role, codes in USERS:
        sec = totp_secret_for(seed, username)
        print(f"{username:17} {role:14} password: {password_for(seed, username)}")
        print(f"{'':17} 2FA setup key: {sec}   current code: {pyotp.TOTP(sec).now()} "
              f"(valid ~{30 - int(time.time()) % 30}s)\n")
    print("Add a 2FA setup key in Google/Microsoft Authenticator: '+' > 'Enter a setup key', time-based.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
