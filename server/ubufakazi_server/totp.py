"""Print the current two-factor code for a demo account (stands in for an authenticator app on stage).

    python -m ubufakazi_server.totp officer.mthatha
"""
from __future__ import annotations

import sys

import pyotp


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("usage: python -m ubufakazi_server.totp <username>")
        return 2
    from .db import SessionLocal
    from .models import User
    db = SessionLocal()
    try:
        u = db.query(User).filter_by(username=argv[0]).first()
        if not u or not u.totp_secret:
            print("No such account, or it has no two-factor secret.")
            return 1
        t = pyotp.TOTP(u.totp_secret)
        import time
        print(f"{t.now()}   (valid for about {30 - int(time.time()) % 30}s more)")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
