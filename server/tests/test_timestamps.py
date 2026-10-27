"""RFC 3161 trusted timestamps: request, verification, storage, dashboard checks and case pack.

A local test authority signs the replies, so no external service is contacted.
"""
from __future__ import annotations

import datetime as dt
import hashlib

import pytest
from asn1crypto import cms, tsp
from asn1crypto import x509 as ax509
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID

from conftest import KIT


class FakeTSA:
    def __init__(self):
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test Timestamp Authority")])
        now = dt.datetime.now(dt.timezone.utc)
        cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(self.key.public_key())
                .serial_number(4242).not_valid_before(now - dt.timedelta(days=1)).not_valid_after(now + dt.timedelta(days=1))
                .sign(self.key, hashes.SHA256()))
        self.cert = ax509.Certificate.load(cert.public_bytes(serialization.Encoding.DER))
        self.calls = 0

    def reply(self, req_der: bytes, *, tamper_imprint: bool = False) -> bytes:
        self.calls += 1
        req = tsp.TimeStampReq.load(req_der)
        imprint = req["message_imprint"]
        if tamper_imprint:
            imprint = {"hash_algorithm": {"algorithm": "sha256"}, "hashed_message": b"\x00" * 32}
        tst = tsp.TSTInfo({"version": "v1", "policy": "1.2.3.4.1", "message_imprint": imprint, "serial_number": 1000 + self.calls,
                           "gen_time": dt.datetime.now(dt.timezone.utc).replace(microsecond=0), "nonce": req["nonce"].native})
        attrs = cms.CMSAttributes([
            cms.CMSAttribute({"type": "content_type", "values": ["tst_info"]}),
            cms.CMSAttribute({"type": "message_digest", "values": [hashlib.sha256(tst.dump()).digest()]}),
        ])
        sig = self.key.sign(attrs.dump(), padding.PKCS1v15(), hashes.SHA256())
        signer = cms.SignerInfo({
            "version": "v1",
            "sid": cms.SignerIdentifier({"issuer_and_serial_number": {"issuer": self.cert.issuer,
                                                                       "serial_number": self.cert.serial_number}}),
            "digest_algorithm": {"algorithm": "sha256"}, "signed_attrs": attrs,
            "signature_algorithm": {"algorithm": "rsassa_pkcs1v15"}, "signature": sig})
        sd = cms.SignedData({"version": "v3", "digest_algorithms": [{"algorithm": "sha256"}],
                             "encap_content_info": {"content_type": "tst_info", "content": tst},
                             "certificates": [self.cert], "signer_infos": [signer]})
        token = cms.ContentInfo({"content_type": "signed_data", "content": sd})
        return tsp.TimeStampResp({"status": {"status": "granted"}, "time_stamp_token": token}).dump()


class _Resp:
    def __init__(self, content, status=200):
        self.content, self.status_code = content, status


@pytest.fixture
def tsa(app, monkeypatch):
    from ubufakazi_server import timestamps
    from ubufakazi_server.config import get_settings
    fake = FakeTSA()
    monkeypatch.setattr(get_settings(), "tsa_url", "https://tsa.test/tsr")
    monkeypatch.setattr(timestamps.httpx, "post", lambda url, content, **kw: _Resp(fake.reply(content)))
    for k, v in {"ok": 0, "failed": 0, "last_ok_at": None, "last_error": None, "tsa_name": None}.items():
        monkeypatch.setitem(timestamps.STATE, k, v)
    return fake


def test_not_configured_is_honest(client):
    t = client.get("/api/integrations").json()["trusted_timestamps"]
    assert t["configured"] is False and "UBF_TSA_URL" in t["note"]


def test_token_verifies_and_detects_changes(tsa):
    from ubufakazi_server import timestamps
    sha = hashlib.sha256(b"evidence").hexdigest()
    stored = timestamps.stamp(sha)
    info = timestamps.public_info(stored)
    assert info and "Test Timestamp Authority" in info["tsa"]
    tsr = timestamps.token_bytes(stored)
    assert timestamps.verify(tsr, sha)["serial"] == info["serial"]
    with pytest.raises(timestamps.TimestampError):
        timestamps.verify(tsr, hashlib.sha256(b"changed evidence").hexdigest())      # a different file
    broken = bytearray(tsr)
    broken[-40] ^= 0xFF                                                                 # corrupt the signature
    with pytest.raises(timestamps.TimestampError):
        timestamps.verify(bytes(broken), sha)


def test_wrong_fingerprint_reply_is_rejected(app, monkeypatch):
    from ubufakazi_server import timestamps
    from ubufakazi_server.config import get_settings
    fake = FakeTSA()
    monkeypatch.setattr(get_settings(), "tsa_url", "https://tsa.test/tsr")
    monkeypatch.setattr(timestamps.httpx, "post", lambda url, content, **kw: _Resp(fake.reply(content, tamper_imprint=True)))
    assert timestamps.stamp_quietly(hashlib.sha256(b"x").hexdigest()) is None
    assert "different fingerprint" in timestamps.STATE["last_error"]


def test_report_evidence_is_timestamped_end_to_end(tsa, login):
    from ubufakazi_server import services
    from ubufakazi_server.casepack import build_case_pack
    from ubufakazi_server.db import SessionLocal
    from ubufakazi_server.models import Report
    data = (KIT / "case2-sipho-whatsapp-chat.txt").read_bytes()
    res = services.submit_report(files=[(data, "chat.txt", "text/plain")], source="web", category="scam", language="en",
                                 province="Eastern Cape", town="Mthatha", description="A test report about a fake job offer.",
                                 consent_given=True)
    services.process_report(res["id"])
    db = SessionLocal()
    try:
        r = db.get(Report, res["id"])
        ev = r.evidence[0]
        assert ev.trusted_timestamp, "evidence should carry an RFC 3161 token"
        pdf = build_case_pack(db, r, "police")
        assert pdf[:4] == b"%PDF"
        ev_id = ev.id
    finally:
        db.close()
    c, _ = login("officer.mthatha")
    detail = c.get(f"/api/police/reports/{res['reference']}").json()
    assert detail["evidence"][0]["timestamp"]["tsa"] == "Test Timestamp Authority"
    v = c.post(f"/api/police/evidence/{ev_id}/verify", json={}).json()
    assert v["match"] is True and v["timestamp_ok"] is True
    t = c.get(f"/api/police/evidence/{ev_id}/timestamp")
    assert t.status_code == 200 and t.headers["content-type"] == "application/timestamp-reply"
    assert "attachment" in t.headers["content-disposition"]
    status = c.get("/api/integrations").json()["trusted_timestamps"]
    assert status["configured"] is True and "never the file" in status["note"]
