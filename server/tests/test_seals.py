"""Sealed case packs: the printed seal and the exact PDF bytes can be checked publicly; any change breaks it."""
from __future__ import annotations

import hashlib
import re


def test_case_pack_is_sealed_and_tampering_is_detected(login, client):
    import fitz
    c, _ = login("officer.mthatha")
    ref = c.get("/api/police/reports?page_size=1").json()["items"][0]["reference"]
    r = c.get(f"/api/police/reports/{ref}/pack")
    assert r.status_code == 200
    pdf = r.content
    text = "".join(p.get_text() for p in fitz.open(stream=pdf, filetype="pdf"))
    seal_id = re.search(r"SEAL-[0-9A-F]{16}", text).group(0)
    s = client.get(f"/api/public/seal/{seal_id}").json()
    assert s["sha256"] == hashlib.sha256(pdf).hexdigest() and s["reference"] == ref and s["issued_to"] == "a bank fraud investigator"
    assert client.get("/api/public/seal-by-hash/" + s["sha256"]).json()["seal_id"] == seal_id
    tampered = pdf.replace(b"Ubufakazi", b"Ubufakazl", 1)
    assert client.get("/api/public/seal-by-hash/" + hashlib.sha256(tampered).hexdigest()).status_code == 404
    assert client.get("/api/public/seal/SEAL-0000000000000000").status_code == 404
