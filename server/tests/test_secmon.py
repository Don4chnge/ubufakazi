"""Security alert centre: brute force, rejected bank signatures and injection attempts show up; admin only."""
from __future__ import annotations


def test_alerts_from_audit_log(login, client):
    for _ in range(6):
        client.post("/api/auth/login", json={"username": "ghost.user", "password": "wrong-password-1"})
    client.post("/api/bank-link/callback", content=b'{"x":1}', headers={"X-UBF-Signature": "t=1,v1=00"})
    c, _ = login("admin")
    d = c.get("/api/admin/security").json()
    rules = {a["rule"] for a in d["alerts"]}
    assert "brute_force" in rules and "bank.signature_rejected" in rules
    assert d["audit_chain"]["intact"] is True
    o, _ = login("officer.mthatha")
    assert o.get("/api/admin/security").status_code == 403
