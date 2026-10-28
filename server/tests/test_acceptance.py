"""Ubufakazi 2.0 acceptance tests A-H. Run:  cd server && python -m pytest -q

A  Chatbot reporting flow (channel-neutral engine used by Telegram), quick exit, safety path
B  Evidence integrity: originals, hashes, rejection of unsupported files, derivatives, case pack
C  Police dashboard security: sign-in, two-factor, lockout, CSRF, station isolation, roles
D  Scam intelligence: explainable leads, restricted cross-station stubs, graph, identifier search
E  Bank link: signed API to the fictional Ubuntu Trust Bank, no victim data, decisions flow back
F  Hash-chained audit log: actions recorded, tampering detected
G  Website, public web reporting, track page, honest integration status
H  MVP regression: the Python engine reproduces the MVP's results on the 70-case test pack
"""
import hashlib
import json
import os
import re
import stat

import pyotp
import pytest

from conftest import KIT, SERVER, db_backend

REF = re.compile(r"^UBF-26-[A-Z2-9]{6}$")


def kit(name):
    return (KIT / name).read_bytes()


def run_conversation(steps, conv=None):
    from ubufakazi_server.conversation import Conversation
    c = conv or Conversation(channel="telegram", contact_ref="tg:test")
    outs = []
    for s in steps:
        if isinstance(s, dict):
            outs += c.handle(s.get("text"), file=s.get("file"), location=s.get("location"))
        else:
            outs += c.handle(s)
    return c, outs


LERATO_STEPS = [
    "/start", "English", "Online scam / fraudulent job offer", "Eastern Cape", "Mthatha",
    {"location": (-31.58912, 28.78433)}, "12 October 2026",
    "I was offered an admin clerk job and paid two fees to a recruiter called Thandi. Then she stopped answering.",
    {"file": (kit("case1-lerato-whatsapp-chat.txt"), "case1-lerato-whatsapp-chat.txt", "text/plain")},
    {"file": (kit("case1-lerato-proof-of-payment-1.pdf"), "pop-1.pdf", "application/pdf")},
    {"file": (kit("case1-lerato-proof-of-payment-2.pdf"), "pop-2.pdf", "application/pdf")},
    {"file": (kit("case1-recruiter-profile-screenshot.png"), "profile.png", "image/png")},
    "Done", "R3 500", "Lerato Mokoena (demo)", "Looks right, continue",
]


@pytest.fixture(scope="module")
def lerato(env):
    """The demo victim reports through the chatbot engine."""
    from ubufakazi_server.db import SessionLocal
    from ubufakazi_server.models import Report
    c, outs = run_conversation(LERATO_STEPS + ["I agree, submit"])
    act = next(o.action for o in outs if o.action and o.action["type"] == "submitted")
    from ubufakazi_server import services
    services.process_report(act["id"])          # what the Telegram adapter does right after submission
    db = SessionLocal()
    r = db.query(Report).filter_by(reference=act["reference"]).one()
    yield {"conv": c, "outs": outs, "action": act, "report": r, "db": db}
    db.close()


# ====================================================================== A
class TestA_Chatbot:
    def test_full_flow_creates_routed_report(self, lerato):
        r, act = lerato["report"], lerato["action"]
        assert REF.match(r.reference)
        assert r.station.code == "MTH" and r.source == "telegram" and r.contact_ref == "tg:test"
        assert r.language == "en" and r.category == "scam" and r.complainant_name == "Lerato Mokoena (demo)"
        assert (r.location_lat, r.location_lon) == (-31.59, 28.78)       # rounded, never exact GPS
        assert len(r.evidence) == 4 and r.processing_status == "ready" and r.status == "awaiting_review"
        text = "\n".join(o.text for o in lerato["outs"])
        assert "NOT the police" in text and "10111" in text
        assert act["receipt_key"] in text and "fictional demo station" in text and "fraud line" in text

    def test_consent_recorded_before_storage(self, lerato):
        from ubufakazi_server.models import Consent
        from ubufakazi_server.services import CONSENT_VERSION
        c = lerato["db"].query(Consent).filter_by(report_id=lerato["report"].id).one()
        assert c.version == CONSENT_VERSION and "not SAPS" in c.text

    def test_quick_exit_at_every_step_saves_nothing(self, env):
        from ubufakazi_server.db import SessionLocal
        from ubufakazi_server.models import EvidenceFile, Report
        db = SessionLocal()
        before = (db.query(Report).count(), db.query(EvidenceFile).count())
        for n in range(2, len(LERATO_STEPS) + 1):
            c, _ = run_conversation(LERATO_STEPS[:n])
            outs = c.handle("/stop")
            assert outs[0].action == {"type": "quick_exit"} and "nothing from it was saved" in outs[0].text
            assert c.data == {} and c.files == [] and c.pasted == []
        assert (db.query(Report).count(), db.query(EvidenceFile).count()) == before
        db.close()

    def test_no_id_numbers_and_no_gps_required(self, env):
        c, outs = run_conversation(LERATO_STEPS[:5] + ["Skip"])
        assert c.step == "when"                                  # location skipped without problem
        c, outs = run_conversation(LERATO_STEPS[:14] + ["9001015009087"])
        assert "don't send an ID number" in outs[-1].text and "name" not in c.data

    def test_only_scam_and_banking_fraud_are_offered(self, env):
        c, outs = run_conversation(["/start", "English"])
        assert outs[-1].options == ["Online scam / fraudulent job offer", "Digital banking fraud / suspicious payment"]


# ====================================================================== B
class TestB_Evidence:
    def test_originals_unchanged_hashed_and_read_only(self, lerato):
        from ubufakazi_server import storage
        if db_backend():
            pytest.skip("file backend only (see test_db_originals_are_insert_only)")
        names = ["case1-lerato-whatsapp-chat.txt", "case1-lerato-proof-of-payment-1.pdf",
                 "case1-lerato-proof-of-payment-2.pdf", "case1-recruiter-profile-screenshot.png"]
        for ev, name in zip(lerato["report"].evidence, names):
            original = kit(name)
            p = storage.path_for(ev.uid)
            assert p.read_bytes() == original
            assert ev.sha256 == hashlib.sha256(original).hexdigest() and ev.size == len(original)
            assert not (os.stat(p).st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
            assert ev.uid not in ev.original_name and "/" not in ev.original_name

    def test_derivatives_are_separate_and_labelled(self, lerato):
        ev = {e.original_name: e for e in lerato["report"].evidence}
        assert [d.kind for d in ev["case1-lerato-whatsapp-chat.txt"].derivatives] == ["text"]
        pdf = ev["pop-1.pdf"].derivatives[0]
        assert pdf.kind == "pdf-text" and "1047 2283 59" in pdf.content and not pdf.ai_generated
        img = ev["profile.png"].derivatives[0]
        assert img.kind == "not-processed" and "not configured" in img.note and img.content == ""
        assert "not read automatically" in lerato["report"].processing_note

    def test_facts_extracted(self, lerato):
        r = lerato["report"]
        assert r.amount_paid == 3500 and r.scam_type == "job"
        kinds = {(i.kind, i.display) for i in r.identifiers}
        assert ("account", "1047 2283 59") in kinds and ("phone", "071 482 0937") in kinds
        assert ("domain", "mzansi-careers-onboard.site") in kinds
        assert "1047 2283 59" in r.statement and "Police case number (optional)" in r.bank_report
        assert set(r.statements) == {"en", "zu", "xh", "af", "st"}

    @pytest.mark.parametrize("data,name", [
        (b"MZ\x90\x00\x03" + b"\x00" * 200, "invoice.pdf"),                 # Windows executable renamed
        (b"\x7fELF\x02\x01\x01" + b"\x00" * 200, "photo.jpg"),             # Linux executable renamed
        (b"PK\x03\x04" + os.urandom(200), "chat.zip"),                       # archives are not accepted
        (b"", "empty.txt"),
    ])
    def test_unsupported_files_rejected(self, env, data, name):
        from ubufakazi_server import storage
        from ubufakazi_server.db import SessionLocal
        db = SessionLocal()
        with pytest.raises(storage.RejectedFile):
            storage.store_original(data, name, db=db)
        db.rollback()
        db.close()

    def test_path_traversal_names_are_neutralised(self, env):
        from ubufakazi_server import storage
        from ubufakazi_server.db import SessionLocal
        db = SessionLocal()
        info = storage.store_original(b"hello there this is text", "../../etc/passwd", db=db)
        db.rollback()
        db.close()
        assert info["original_name"] == "passwd" and re.fullmatch(r"[0-9a-f]{32}", info["uid"])

    def test_db_originals_are_insert_only(self, lerato):
        """Database backend: stored bytes equal the originals, and UPDATE is refused by a trigger."""
        if not db_backend():
            pytest.skip("database backend only")
        from sqlalchemy import text
        from ubufakazi_server import storage
        from ubufakazi_server.db import SessionLocal
        ev = lerato["report"].evidence[0]
        assert storage.read_original(ev.uid) == kit("case1-lerato-whatsapp-chat.txt")
        assert storage.rehash(ev.uid) == ev.sha256
        db = SessionLocal()
        with pytest.raises(Exception, match="read-only"):
            db.execute(text("UPDATE evidence_blobs SET data = :d WHERE uid = :u"), {"d": b"forged", "u": ev.uid})
            db.commit()
        db.rollback()
        db.close()
        assert storage.rehash(ev.uid) == ev.sha256

    def test_tampering_with_a_stored_original_is_detected(self, lerato, login):
        from ubufakazi_server import storage
        if db_backend():
            pytest.skip("file backend only: in the database backend tampering is blocked by a trigger")
        ev = lerato["report"].evidence[0]
        c, _ = login("officer.mthatha")
        assert c.post(f"/api/police/evidence/{ev.id}/verify").json()["match"] is True
        p = storage.path_for(ev.uid)
        good = p.read_bytes()
        os.chmod(p, 0o600)
        p.write_bytes(good.replace(b"R1 850", b"R9 850"))
        res = c.post(f"/api/police/evidence/{ev.id}/verify").json()
        assert res["match"] is False and res["recorded_sha256"] == ev.sha256
        p.write_bytes(good)
        os.chmod(p, 0o400)
        assert c.post(f"/api/police/evidence/{ev.id}/verify").json()["match"] is True

    def test_case_packs(self, lerato, login):
        import pymupdf
        from ubufakazi_server.casepack import build_case_pack
        r, db = lerato["report"], lerato["db"]
        text = "".join(p.get_text() for p in pymupdf.open(stream=build_case_pack(db, r, "complainant"), filetype="pdf"))
        for must in ("NOT AN OFFICIAL SAPS DOCUMENT", r.reference, "Fraud dispute statement to the bank", "Evidence register", "SHA-256",
                     r.evidence[0].sha256[:32], "Timeline", "unverified", "10111", "not tamper-proof"):
            assert must in text, must
        assert "UBF-26-SEED" not in text and "Possible connections" not in text   # no other victims' data
        c, _ = login("officer.mthatha")
        res = c.get(f"/api/police/reports/{r.reference}/pack")
        assert res.status_code == 200 and res.headers["content-type"] == "application/pdf"
        ptext = "".join(p.get_text() for p in pymupdf.open(stream=res.content, filetype="pdf"))
        assert "Possible connections" in ptext and "Chain of custody" in ptext and "POLICE COPY" in ptext


# ====================================================================== C
class TestC_PoliceSecurity:
    def test_requires_sign_in(self, client):
        for url in ("/api/police/reports", "/api/police/overview", "/api/utb/cases", "/api/admin/audit"):
            assert client.get(url).status_code == 401

    def test_wrong_password_and_lockout(self, client, env):
        for _ in range(5):
            assert client.post("/api/auth/login", json={"username": "officer.joburg", "password": "nope"}).status_code == 401
        pw = env["creds"]["officer.joburg"][0]
        r = client.post("/api/auth/login", json={"username": "officer.joburg", "password": pw})
        assert r.status_code == 423                                   # locked, even with the right password
        from ubufakazi_server.db import SessionLocal, write_lock
        from ubufakazi_server.models import User
        with write_lock:
            db = SessionLocal()
            db.query(User).filter_by(username="officer.joburg").one().locked_until = None
            db.commit()
            db.close()

    def test_password_alone_is_not_enough(self, client, env):
        pw = env["creds"]["officer.mthatha"][0]
        r = client.post("/api/auth/login", json={"username": "officer.mthatha", "password": pw})
        assert r.json()["mfa_required"] is True
        cookie = r.headers["set-cookie"].lower()
        assert "httponly" in cookie and "samesite=strict" in cookie
        assert client.get("/api/police/reports").status_code == 401
        bad = client.post("/api/auth/mfa", json={"code": "000000"}, headers={"X-CSRF-Token": r.json()["csrf"]})
        assert bad.status_code == 401

    def test_csrf_required_for_changes(self, login, lerato):
        c, me = login("officer.mthatha")
        url = f"/api/police/reports/{lerato['report'].reference}/notes"
        assert c.post(url, json={"body": "x"}, headers={"X-CSRF-Token": "wrong"}).status_code == 403
        assert c.post(url, json={"body": "Called complainant; visit booked."}).status_code == 200

    def test_station_isolation(self, login, lerato):
        mth, _ = login("officer.mthatha")
        jhb, _ = login("officer.joburg")
        ref = lerato["report"].reference
        items = mth.get("/api/police/reports?page_size=100").json()["items"]
        assert items and all(i["station_code"] == "MTH" for i in items)
        assert ref in {i["reference"] for i in items}
        assert jhb.get(f"/api/police/reports/{ref}").status_code == 404        # other station: indistinguishable from missing
        ev = lerato["report"].evidence[0].id
        assert jhb.get(f"/api/police/evidence/{ev}/download").status_code == 404
        assert jhb.post(f"/api/police/reports/{ref}/status", json={"status": "closed"}).status_code == 404
        assert all(i["station_code"] in ("JHB", "ALB") for i in jhb.get("/api/police/reports?page_size=100").json()["items"])

    def test_evidence_inventory_is_station_scoped(self, login, lerato):
        mth, _ = login("officer.mthatha")
        jhb, _ = login("officer.joburg")
        ref = lerato["report"].reference
        mine = mth.get("/api/police/evidence?page_size=100").json()["items"]
        assert ref in {e["reference"] for e in mine} and all(e["station"].endswith("Mthatha") for e in mine)
        theirs = jhb.get("/api/police/evidence?page_size=100").json()["items"]
        assert ref not in {e["reference"] for e in theirs}
        assert all("content" not in e for e in mine)
        assert mth.get("/api/police/evidence", params={"type": "image"}).json()["items"][0]["type"] in ("png", "jpeg", "webp", "gif")

    def test_roles(self, login):
        bank, _ = login("bank.reviewer")
        assert bank.get("/api/police/reports").status_code == 403
        officer, _ = login("officer.mthatha")
        assert officer.get("/api/utb/cases").status_code == 403
        assert officer.get("/api/admin/audit").status_code == 403

    def test_status_workflow_and_download_is_attachment(self, login, lerato):
        c, _ = login("officer.mthatha")
        ref = lerato["report"].reference
        assert c.post(f"/api/police/reports/{ref}/status", json={"status": "under_review", "note": "Checking"}).json()[
            "status_label"] == "Under review"
        assert c.post(f"/api/police/reports/{ref}/status", json={"status": "made_up"}).status_code == 400
        d = c.get(f"/api/police/reports/{ref}")
        assert d.json()["history"][-1]["to"] == "under_review"
        res = c.get(f"/api/police/evidence/{lerato['report'].evidence[0].id}/download")
        assert res.headers["content-type"] == "application/octet-stream" and "attachment" in res.headers["content-disposition"]


# ====================================================================== D
class TestD_Intelligence:
    def test_explainable_corroborated_leads(self, login, lerato):
        c, _ = login("officer.mthatha")
        d = c.get(f"/api/police/reports/{lerato['report'].reference}").json()
        leads = d["leads"]
        assert len(leads) >= 6
        top = leads[0]
        assert top["strength"] == "corroborated"
        kinds = {s["kind"] for s in top["signals"]}
        assert "account" in kinds
        assert all(s["reason"] for L in leads for s in L["signals"])
        script = [s for L in leads for s in L["signals"] if s["kind"] == "script"]
        assert script and all("threshold" in s["reason"] for s in script)

    def test_other_station_reports_are_restricted_stubs(self, login, lerato):
        c, _ = login("officer.mthatha")
        leads = c.get(f"/api/police/reports/{lerato['report'].reference}").json()["leads"]
        hidden = [L for L in leads if not L["visible"]]
        assert hidden, "the syndicate spans several provinces"
        for L in hidden:
            assert L["reference"] is None and L["amount_paid"] is None and L["date"] is None and L["station"]
        admin, _ = login("admin")
        aleads = admin.get(f"/api/police/reports/{lerato['report'].reference}").json()["leads"]
        assert all(L["visible"] and L["reference"] for L in aleads)

    def test_graph(self, login, lerato):
        c, _ = login("officer.mthatha")
        g = c.get(f"/api/police/reports/{lerato['report'].reference}/graph").json()
        acc = [n for n in g["nodes"] if n["type"] == "account"]
        assert acc and acc[0]["label"] == "1047 2283 59" and acc[0]["count"] >= 7
        restricted = [n for n in g["nodes"] if n["type"] == "report" and not n["visible"]]
        assert restricted and all(n["label"] == "Restricted report" and n["amount"] is None for n in restricted)
        assert g["summary"]["stations"] >= 5

    def test_identifier_search_uses_keyed_hash(self, login, lerato):
        c, _ = login("admin")
        items = c.get("/api/police/reports", params={"q": "1047 2283 59", "page_size": 50}).json()["items"]
        assert len(items) >= 7
        items = c.get("/api/police/reports", params={"q": "+27 71 482 0937"}).json()["items"]
        assert lerato["report"].reference in {i["reference"] for i in items}

    def test_clusters(self, login):
        c, _ = login("admin")
        cl = c.get("/api/police/intel/clusters").json()
        assert cl[0]["size"] >= 7 and any(s["kind"] == "account" for s in cl[0]["shared"])

    def test_server_keys_never_reach_the_browser(self, env):
        from ubufakazi_server.config import get_settings
        s = get_settings()
        for folder in (SERVER / "ubufakazi_server" / "web", SERVER.parent / "site"):
            for p in folder.rglob("*"):
                if p.is_file() and p.suffix in (".js", ".html", ".css", ".json"):
                    body = p.read_text(errors="ignore")
                    assert s.hmac_key not in body and s.secret_key not in body


# ====================================================================== E
class TestE_Bank:
    """The bank link, to Ubuntu Trust Bank (a fictional bank reached over a signed API)."""

    def test_alert_reaches_bank_without_victim_data(self, login, lerato):
        from ubufakazi_server import banklink
        from ubufakazi_server.db import SessionLocal
        from ubufakazi_server.models import BankAlert
        c, _ = login("bank.reviewer")
        data = c.get("/api/utb/cases").json()
        assert "fictional bank" in data["notice"] and data["bank"] == "Ubuntu Trust Bank"
        top = next(i for i in data["items"] if i["account"] == "•••• 8359")
        assert top["reports"] >= 7 and top["priority"] == "high" and top["matched"] is True
        detail = c.get(f"/api/utb/cases/{top['id']}").json()
        blob = json.dumps(detail)
        r = lerato["report"]
        for secret in (r.reference, r.complainant_name, "Thandi", "071 482", "1047228359", "Mthatha"):
            assert secret not in blob
        assert len(detail["timeline"]) == top["reports"] and detail["account_detail"]["customer_ref"].startswith("UTB-C-")
        db = SessionLocal()                              # what actually travels to the bank
        try:
            a = db.query(BankAlert).filter(BankAlert.account_display == "•••• 8359").first()
            payload = banklink.build_payload(db, a)
        finally:
            db.close()
        assert set(payload) == {"alert_id", "account_number", "bank_stated", "reports", "total_reported", "provinces",
                                "scam_types", "first_report", "last_report", "timeline", "corroborated_links",
                                "callback_url"}
        assert r.reference not in json.dumps(payload) and r.complainant_name not in json.dumps(payload)

    def test_bank_decision_flows_back_to_officer_and_victim(self, login, lerato, client):
        bank, _ = login("bank.reviewer")
        case = next(i for i in bank.get("/api/utb/cases").json()["items"] if i["account"] == "•••• 8359")
        assert bank.post(f"/api/utb/cases/{case['id']}/action", json={"action": "bogus"}).status_code == 400
        res = bank.post(f"/api/utb/cases/{case['id']}/action", json={"action": "freeze"}).json()
        assert res["status"] == "frozen"
        ref = lerato["report"].reference
        officer, _ = login("officer.mthatha")
        resp = officer.get(f"/api/police/reports/{ref}").json()["bank_responses"]
        assert any(b["status"] == "frozen" and b["bank"] == "Ubuntu Trust Bank" for b in resp)
        t = client.post("/api/public/track", json={"reference": ref, "key": lerato["action"]["receipt_key"]}).json()
        assert any("frozen" in b["status_label"] for b in t["bank_responses"])
        admin, _ = login("admin")
        acts = {e["action"] for e in admin.get("/api/admin/audit?limit=100").json()["events"]}
        assert {"bank.alert_sent", "bank.response_received"} <= acts
        assert admin.get("/api/integrations").json()["bank_link"]["connected"] is True

    def test_bank_api_rejects_unsigned_and_replayed_calls(self, client):
        from ubufakazi_server import banklink
        raw = json.dumps({"alert_id": 1, "account_number": "1047228359"}).encode()
        assert client.post("/utb/api/v1/fraud-alerts", content=raw).status_code == 401
        old = banklink.sign(raw, ts=1_000_000_000)                                  # signed long ago
        assert client.post("/utb/api/v1/fraud-alerts", content=raw, headers={"X-UBF-Signature": old}).status_code == 401
        forged = "t=%d,v1=%s" % (int(__import__("time").time()), "0" * 64)
        assert client.post("/api/bank-link/callback", content=raw, headers={"X-UBF-Signature": forged}).status_code == 401

    def test_account_not_at_bank_is_reported_as_no_match(self, app):
        from ubufakazi_server import banklink, utb
        raw = json.dumps({"alert_id": 999999, "account_number": "9999999999", "reports": 1}).encode()
        res = utb.receive_alert(raw, banklink.sign(raw))
        assert res["status"] == "no_match" and res["case_ref"].startswith("UTB-FC-")


# ====================================================================== F
class TestF_Audit:
    def test_actions_are_recorded_and_chain_intact(self, login, lerato):
        c, _ = login("admin")
        ref = lerato["report"].reference
        actions = {e["action"] for e in c.get(f"/api/police/reports/{ref}/audit").json()}
        assert {"report.created", "evidence.received", "report.processed", "report.viewed"} <= actions
        res = c.get("/api/admin/audit").json()
        assert res["verify"]["intact"] is True and res["verify"]["checked"] > 10
        acts = {e["action"] for e in res["events"]}
        assert "login.success" in acts

    def test_tampering_is_detected(self, env):
        from ubufakazi_server.audit import verify_chain
        from ubufakazi_server.db import SessionLocal, write_lock
        from ubufakazi_server.models import AuditEvent
        with write_lock:
            db = SessionLocal()
            ev = db.query(AuditEvent).order_by(AuditEvent.id).offset(3).first()
            original = dict(ev.detail)
            ev.detail = {**original, "sha256": "0" * 64}
            db.commit()
            res = verify_chain(db)
            assert res["intact"] is False and res["broken_at"] == ev.id
            ev.detail = original
            db.commit()
            assert verify_chain(db)["intact"] is True
            db.close()


# ====================================================================== G
class TestG_WebsiteAndPublic:
    @pytest.mark.parametrize("path", ["/", "/police", "/bank-demo", "/bank", "/report", "/track", "/verify", "/integrations",
                                      "/share", "/resources", "/about", "/privacy", "/mvp", "/demo-logins", "/scam-demo/"])
    def test_pages(self, client, path):
        r = client.get(path)
        assert r.status_code == 200 and "text/html" in r.headers["content-type"]
        assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
        assert r.headers["x-content-type-options"] == "nosniff"

    def test_integrations_are_honest(self, client):
        i = client.get("/api/integrations").json()
        assert i["telegram"]["configured"] is False and i["ai_media_reading"]["configured"] is False
        assert i["saps"]["connected"] is False and i["banks"]["connected"] is False
        assert i["trusted_timestamps"]["configured"] is False and i["whatsapp"]["configured"] is False

    def test_web_report_track_pack_and_more_evidence(self, client):
        files = [("files", ("case2-sipho-whatsapp-chat.txt", kit("case2-sipho-whatsapp-chat.txt"), "text/plain")),
                 ("files", ("bad.exe", b"MZ\x90\x00" + b"\x00" * 100, "application/octet-stream"))]
        form = {"category": "scam", "language": "xh", "province": "Gauteng", "town": "Soweto",
                "description": "I paid a seller for a phone on an online marketplace and it never came.",
                "incident_when": "yesterday"}
        assert client.post("/api/public/reports", data=form, files=files).status_code == 400   # no consent
        r = client.post("/api/public/reports", data={**form, "consent": "yes"}, files=files)
        assert r.status_code == 200, r.text
        out = r.json()
        assert REF.match(out["reference"]) and out["rejected"][0]["name"] == "bad.exe" and len(out["evidence"]) == 1
        body = {"reference": out["reference"], "key": out["receipt_key"]}
        t = client.post("/api/public/track", json=body).json()
        assert t["status"] == "awaiting_review" and t["evidence"][0]["sha256"] == hashlib.sha256(
            kit("case2-sipho-whatsapp-chat.txt")).hexdigest()
        assert client.post("/api/public/track", json={**body, "key": "AAAA-BBBB-CCCC"}).status_code == 404
        pack = client.post("/api/public/pack", json=body)
        assert pack.status_code == 200 and pack.content[:5] == b"%PDF-"
        more = client.post("/api/public/evidence", data=body,
                           files=[("files", ("pop.pdf", kit("case2-sipho-proof-of-payment.pdf"), "application/pdf"))])
        assert more.json()["added"][0]["name"] == "pop.pdf"
        assert len(client.post("/api/public/track", json=body).json()["evidence"]) == 2

    def test_home_is_the_platform_and_mvp_is_separate(self, client):
        home = client.get("/").text
        assert "One syndicate. Many dockets." in home and 'id="globe"' in home and "Build a case file" not in home
        assert "Build a case file" in client.get("/mvp").text

    def test_public_stats_are_aggregates_only(self, client):
        s = client.get("/api/public/stats").json()
        assert set(s) == {"reports", "evidence_files", "linked_reports", "stations", "networks", "demo", "note"}
        assert s["demo"] is True and s["reports"] >= 80 and s["linked_reports"] >= 7 and s["networks"] >= 1

    def test_warning_is_redacted(self, client, lerato):
        from ubufakazi_server import services
        r = lerato["report"]
        db = lerato["db"]
        from ubufakazi_server.db import write_lock
        from ubufakazi_server.security import sha256_hex
        with write_lock:                       # give the chatbot report a known receipt key for this test
            key = services.new_receipt_key()
            r.receipt_hash = sha256_hex(key)
            db.commit()
        w = client.post("/api/public/warning", json={"reference": r.reference, "key": key}).json()
        assert w["scam_type_label"] == "Fake job offer" and len(w["red_flags"]) >= 3
        assert w["optional"]["websites"] == ["mzansi-careers-onboard.site"]
        assert w["optional"]["phones_masked"] == ["071 *** **37"]
        blob = json.dumps(w)
        for private in (r.reference, r.complainant_name, "1047", "Thandi", "071 482 0937", r.description[:20]):
            assert private not in blob
        assert client.post("/api/public/warning", json={"reference": r.reference, "key": "WRONG-KEY1-XXXX"}).status_code == 404

    def test_public_rate_limit(self, client):
        for _ in range(20):
            client.post("/api/public/track", json={"reference": "UBF-26-AAAAAA", "key": "x"})
        assert client.post("/api/public/track", json={"reference": "UBF-26-AAAAAA", "key": "x"}).status_code == 429


# ====================================================================== H
class TestH_MVPRegression:
    def test_engine_matches_mvp_on_70_case_test_pack(self):
        from ubufakazi_server.extract import analyse_text
        pack = SERVER.parent / "site" / "test-pack"
        cases = json.loads((pack / "cases.json").read_text())
        assert len(cases) == 70
        bad = []
        for c in cases:
            chat = (pack / "cases" / c["folder"] / c["chat"]).read_text(encoding="utf-8")
            a = analyse_text(chat)
            if a["scam_type"] != c["type"] or a["ex"]["total_paid"] != c["paid_total"]:
                bad.append((c["id"], a["scam_type"], a["ex"]["total_paid"]))
        assert bad == []

    def test_mvp_site_still_served_unchanged(self, client):
        r = client.get("/assets/app.js")
        assert r.status_code == 200 and "shingle" in r.text.lower()
