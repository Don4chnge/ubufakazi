"""Station handover: the bridge between Ubufakazi and a real police station, without pretending to be SAPS.

1. The complainant's case pack carries a QR code: <site>/police#/handover/<reference>/<token>.
   The token is an HMAC of the reference, so it proves the person holds the case pack. It grants nothing alone:
   the officer must still sign in with a password and two-factor code.
2. At the station an officer scans it, checks the person in front of them, and accepts the case at their station.
   If the complainant went to a different station than the one Ubufakazi routed to, the case moves there (audited).
3. When the station registers the case in its own system, the officer types in the CAS number it issued.
   Ubufakazi only stores it ("entered by officer"); it never creates, guesses or verifies CAS numbers.
"""
from __future__ import annotations

import datetime as dt
import hmac
import re

from .config import get_settings
from .security import sign

CAS_RE = re.compile(r"^\s*(?:CAS\s*)?(\d{1,5})\s*/\s*(\d{1,2})\s*/\s*(\d{4})\s*$", re.IGNORECASE)


def token_for(reference: str) -> str:
    return sign(f"handover:{reference}")[:24]


def check_token(reference: str, token: str) -> bool:
    return bool(token) and hmac.compare_digest(token_for(reference), token)


def url_for(reference: str) -> str:
    return f"{get_settings().public_base_url}/police#/handover/{reference}/{token_for(reference)}"


def normalise_cas(value: str) -> str:
    """'cas 123/10/2026' -> 'CAS 123/10/2026'. Raises ValueError for anything else."""
    m = CAS_RE.match(value or "")
    if not m:
        raise ValueError("Use the format CAS 123/10/2026 (number / month / year), exactly as SAPS issued it.")
    num, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    this_year = dt.datetime.now(dt.timezone.utc).year
    if not 1 <= month <= 12 or not 2000 <= year <= this_year or num < 1:
        raise ValueError("That CAS number has an impossible month or year. Check it against what SAPS issued.")
    return f"CAS {num}/{month}/{year}"
