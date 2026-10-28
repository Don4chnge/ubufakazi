"""Station handover: QR token, accepting a case at another station, recording the CAS number the station issued."""
from __future__ import annotations

import pytest


@pytest.fixture
def mth_report(app):
    from ubufakazi_server import services
    res = services.submit_report(files=[], pasted_text="Recruiter: pay R1 500 training fee to 1047228359 today.",
                                 source="web", category="scam", language="en", province="Eastern Cape", town="Mthatha",
                                 description="A recruiter asked me to pay a training fee for a job.",
                                 complainant_name="Test Complainant", consent_given=True)
    services.process_report(res["id"])
    return res


def _station_id(code):
    from ubufakazi_server.db import SessionLocal
    from ubufakazi_server.models import Station
    db = SessionLocal()
    try:
        return db.query(Station).filter_by(code=code).one().id
    finally:
        db.close()


def test_bad_token_reveals_nothing(login, mth_report):
    c, _ = login("officer.joburg")
    assert c.get(f"/api/police/handover/{mth_report['reference']}/{'0' * 24}").status_code == 404
    assert c.get(f"/api/police/handover/UBF-00-NOPE00/{'0' * 24}").status_code == 404


def test_token_needs_sign_in(client, mth_report):
    from ubufakazi_server.handover import token_for
    assert client.get(f"/api/police/handover/{mth_report['reference']}/{token_for(mth_report['reference'])}").status_code == 401


def test_accept_at_other_station_moves_case(login, mth_report):
    from ubufakazi_server.handover import token_for
    ref = mth_report["reference"]
    tok = token_for(ref)
    jhb = login("officer.joburg")[0]
    assert jhb.get(f"/api/police/reports/{ref}").status_code == 404                 # not Johannesburg's case yet
    pv = jhb.get(f"/api/police/handover/{ref}/{tok}").json()
    assert pv["routed_station"].endswith("Mthatha branch") and pv["can_open"] is False and pv["complainant_name"] == "Test Complainant"
    mth_id = _station_id("MTH")
    assert jhb.post(f"/api/police/handover/{ref}/{tok}/accept", json={"station_id": mth_id}).status_code == 403
    r = jhb.post(f"/api/police/handover/{ref}/{tok}/accept", json={"station_id": _station_id("JHB")})
    assert r.status_code == 200
    detail = jhb.get(f"/api/police/reports/{ref}").json()
    assert detail["station"].endswith("Johannesburg Central branch")
    assert detail["handover"]["moved"] is True and detail["handover"]["from_station"].endswith("Mthatha branch")
    mth = login("officer.mthatha")[0]
    assert mth.get(f"/api/police/reports/{ref}").status_code == 404                 # moved away from Mthatha
    from ubufakazi_server.db import SessionLocal
    from ubufakazi_server.models import AuditEvent
    db = SessionLocal()
    try:
        actions = {a for (a,) in db.query(AuditEvent.action).filter_by(target_id=ref)}
    finally:
        db.close()
    assert {"report.transferred", "handover.accepted", "handover.viewed"} <= actions


def test_cas_number_entered_by_officer(login, mth_report, client):
    ref = mth_report["reference"]
    c, _ = login("officer.mthatha")
    assert c.post(f"/api/police/reports/{ref}/status", json={"status": "registered_at_station"}).status_code == 400
    for bad in ("12345", "CAS 12/13/2026", "CAS 12/10/1999", "CAS 1/1/2999", "ABC 1/1/2026"):
        assert c.post(f"/api/police/reports/{ref}/cas", json={"cas_number": bad}).status_code == 400, bad
    v = c.post(f"/api/police/reports/{ref}/cas", json={"cas_number": " cas 45 / 10 / 2026 "}).json()
    assert v["cas_number"] == "CAS 45/10/2026" and v["status"] == "registered_at_station"
    d = c.get(f"/api/police/reports/{ref}").json()
    assert d["handover"]["cas_number"] == "CAS 45/10/2026" and d["handover"]["cas_recorded_by"]
    t = client.post("/api/public/track", json={"reference": ref, "key": mth_report["receipt_key"]}).json()
    assert t["registration"]["cas_number"] == "CAS 45/10/2026" and t["status"] == "registered_at_station"


def test_complainant_pack_has_handover_qr(mth_report):
    from ubufakazi_server.casepack import build_case_pack
    from ubufakazi_server.db import SessionLocal
    from ubufakazi_server.models import Report
    db = SessionLocal()
    try:
        r = db.query(Report).filter_by(reference=mth_report["reference"]).one()
        pdf = build_case_pack(db, r, "complainant")
    finally:
        db.close()
    assert pdf[:4] == b"%PDF" and len(pdf) > 3000
