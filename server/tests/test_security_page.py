"""Public security page: live checks are aggregates only; security.txt is served."""
from __future__ import annotations


def test_security_page_and_checks(client):
    assert client.get("/security").status_code == 200
    d = client.get("/api/public/security").json()
    assert d["audit_chain"]["intact"] is True and "max_per_hour" in d["ai"]
    assert not any(k in str(d) for k in ("UBF-26-", "complainant_name", "password"))
    t = client.get("/.well-known/security.txt").text
    assert t.startswith("Contact: https://github.com/") and "Expires:" in t
