"""Trusted timestamps (RFC 3161) for evidence fingerprints.

Only the SHA-256 fingerprint of a file is sent to the timestamp authority (TSA), never the file. The TSA signs
"this fingerprint existed at this time"; the signed reply (a .tsr token) is stored next to the original.
Anyone can check it later without trusting Ubufakazi, for example:

    openssl ts -verify -data <evidence file> -in <token.tsr> -CAfile <tsa cacert.pem> -untrusted <tsa.crt>

Enabled only when UBF_TSA_URL is set (e.g. https://freetsa.org/tsr). Failures never block a report: the
evidence keeps its server-clock time and the problem is shown on /integrations.
"""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import logging
import secrets

import httpx
from asn1crypto import tsp
from cryptography import x509 as cx509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa

from .config import get_settings

log = logging.getLogger("ubufakazi.timestamps")
STATE = {"ok": 0, "failed": 0, "last_ok_at": None, "last_error": None, "tsa_name": None}
HASHES = {"sha1": hashes.SHA1, "sha256": hashes.SHA256, "sha384": hashes.SHA384, "sha512": hashes.SHA512}


class TimestampError(Exception):
    pass


def configured() -> bool:
    return bool(get_settings().tsa_url)


def status() -> dict:
    url = get_settings().tsa_url
    if not url:
        return {"configured": False, "note": "Not configured. Times are the server's clock, not RFC 3161 tokens "
                                             "(set UBF_TSA_URL to enable)."}
    host = httpx.URL(url).host
    if STATE["last_error"] and not STATE["ok"]:
        return {"configured": False, "note": f"Timestamp authority {host} set, but no token obtained yet: {STATE['last_error']}"}
    parts = [f"Evidence fingerprints are timestamped by {STATE['tsa_name'] or host} (RFC 3161). Only the SHA-256 "
             "fingerprint is sent, never the file."]
    if STATE["ok"]:
        parts.append(f"{STATE['ok']} token(s) obtained since the last restart, last at {STATE['last_ok_at'][:16]} UTC.")
    else:
        parts.append("Waiting for the first evidence file.")
    if STATE["last_error"]:
        parts.append(f"Last problem: {STATE['last_error']}")
    return {"configured": True, "note": " ".join(parts)}


def build_request(sha256_hex: str) -> tuple[bytes, int]:
    nonce = secrets.randbits(63)
    req = tsp.TimeStampReq({
        "version": "v1",
        "message_imprint": {"hash_algorithm": {"algorithm": "sha256"}, "hashed_message": bytes.fromhex(sha256_hex)},
        "nonce": nonce, "cert_req": True,
    })
    return req.dump(), nonce


def verify(tsr: bytes, sha256_hex: str, nonce: int | None = None) -> dict:
    """Checks a TSA reply: granted, same fingerprint, same nonce, and a valid signature by the certificate in the token.
    Returns {"gen_time", "tsa", "serial", "policy"}. Raises TimestampError. (Checking the TSA certificate's chain to
    a trusted root is left to openssl, see the module docstring.)"""
    try:
        resp = tsp.TimeStampResp.load(tsr)
        state = resp["status"]["status"].native
        if state not in ("granted", "granted_with_mods"):
            raise TimestampError(f"the authority refused the request ({state})")
        sd = resp["time_stamp_token"]["content"]
        econtent = sd["encap_content_info"]["content"]
        tst = econtent.parsed
        if tst["message_imprint"]["hashed_message"].native != bytes.fromhex(sha256_hex):
            raise TimestampError("the token is for a different fingerprint")
        if nonce is not None and tst["nonce"].native != nonce:
            raise TimestampError("the token does not answer our request (nonce mismatch)")
        signer = sd["signer_infos"][0]
        digest_name = signer["digest_algorithm"]["algorithm"].native
        if digest_name not in HASHES:
            raise TimestampError(f"unsupported digest {digest_name}")
        attrs = {a["type"].native: a["values"][0].native for a in signer["signed_attrs"]}
        if attrs.get("message_digest") != hashlib.new(digest_name, econtent.contents).digest():
            raise TimestampError("the signed data does not match the token content")
        sid = signer["sid"]
        certs = [c.chosen for c in sd["certificates"] or [] if c.name == "certificate"]
        if sid.name == "subject_key_identifier":
            cert = next((c for c in certs if c.key_identifier == sid.chosen.native), None)
        else:
            cert = next((c for c in certs if c.serial_number == sid.chosen["serial_number"].native
                         and c.issuer == sid.chosen["issuer"]), None)
        if cert is None:
            raise TimestampError("the token does not include the authority's certificate")
        signed = bytearray(signer["signed_attrs"].dump())
        signed[0] = 0x31                                    # [0] IMPLICIT -> SET OF, as signed
        key = cx509.load_der_x509_certificate(cert.dump()).public_key()
        h = HASHES[digest_name]()
        sig = signer["signature"].native
        algo = signer["signature_algorithm"]["algorithm"].native
        if isinstance(key, rsa.RSAPublicKey):
            pad = padding.PSS(padding.MGF1(h), padding.PSS.AUTO) if algo == "rsassa_pss" else padding.PKCS1v15()
            key.verify(sig, bytes(signed), pad, h)
        elif isinstance(key, ec.EllipticCurvePublicKey):
            key.verify(sig, bytes(signed), ec.ECDSA(h))
        else:
            raise TimestampError("unsupported key type")
        gen = tst["gen_time"].native
        return {"gen_time": gen.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
                "tsa": (cert.subject.native.get("common_name") or cert.subject.human_friendly)[:200], "serial": str(tst["serial_number"].native),
                "policy": tst["policy"].dotted}
    except TimestampError:
        raise
    except Exception as e:                                   # malformed reply, bad signature, ...
        raise TimestampError(f"the reply could not be verified ({type(e).__name__})") from e


def stamp(sha256_hex: str, timeout: float = 20.0) -> str:
    """Gets and verifies a token. Returns the JSON stored in EvidenceFile.trusted_timestamp."""
    url = get_settings().tsa_url
    body, nonce = build_request(sha256_hex)
    try:
        r = httpx.post(url, content=body, timeout=timeout,
                       headers={"Content-Type": "application/timestamp-query", "Accept": "application/timestamp-reply"})
    except httpx.HTTPError as e:
        raise TimestampError(f"could not reach the authority ({type(e).__name__})") from e
    if r.status_code != 200:
        raise TimestampError(f"the authority answered HTTP {r.status_code}")
    info = verify(r.content, sha256_hex, nonce)
    return json.dumps({**info, "url": url, "tsr": base64.b64encode(r.content).decode()})


def stamp_quietly(sha256_hex: str) -> str | None:
    """stamp() that records success or failure in STATE instead of raising."""
    if not configured():
        return None
    try:
        token = stamp(sha256_hex)
    except TimestampError as e:
        STATE["failed"] += 1
        STATE["last_error"] = str(e)[:200]
        log.warning("timestamp failed: %s", e)
        return None
    info = json.loads(token)
    STATE["ok"] += 1
    STATE["last_ok_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    STATE["tsa_name"] = info["tsa"]
    STATE["last_error"] = None
    return token


def public_info(stored: str | None) -> dict | None:
    """What the dashboard and case pack show (no raw token)."""
    if not stored:
        return None
    try:
        d = json.loads(stored)
        return {"gen_time": d["gen_time"], "tsa": d["tsa"], "serial": d["serial"]}
    except (ValueError, KeyError):
        return None


def token_bytes(stored: str) -> bytes:
    return base64.b64decode(json.loads(stored)["tsr"])
