"""Payment-slip integrity signals (digital forensics; NIST SP 800-86 examination).

Edited proofs of payment are common in fraud. These are WARNING SIGNS read from the file's own metadata and
structure, never a verdict: real bank documents can be produced by many tools, and a careful forger can strip
metadata. Every result tells the officer to confirm the payment with the bank.
"""
from __future__ import annotations

import datetime as dt
import io
import re

EDIT_TOOLS = re.compile(r"photoshop|illustrator|gimp|canva|pdfescape|sejda|ilovepdf|smallpdf|pdf-?xchange|nitro|"
                        r"phantompdf|inkscape|pixlr|picsart|snapseed|lightroom|affinity|paint\.net|microsoft word|"
                        r"libreoffice draw|pdf editor|online2pdf|pdf24|wps office", re.I)


def _pdf_date(s: str | None) -> dt.datetime | None:
    m = re.match(r"D:(\d{4})(\d{2})(\d{2})(\d{2})?(\d{2})?(\d{2})?", s or "")
    if not m:
        return None
    y, mo, d, h, mi, se = (int(x) if x else 0 for x in m.groups())
    try:
        return dt.datetime(y, mo, d, h, mi, se)
    except ValueError:
        return None


def check(data: bytes, detected_type: str) -> dict | None:
    """Returns {"warnings": [...], "facts": [...]} or None for file types we do not examine."""
    warnings, facts = [], []
    if detected_type == "pdf":
        import fitz
        try:
            doc = fitz.open(stream=data, filetype="pdf")
            md = doc.metadata or {}
        except Exception:                                    # noqa: BLE001
            return {"warnings": ["The PDF structure could not be read: treat with care."], "facts": []}
        tools = " / ".join(x for x in (md.get("creator"), md.get("producer")) if x)
        facts.append(f"Made with: {tools or 'not stated'}")
        if tools and EDIT_TOOLS.search(tools):
            warnings.append(f"Created or saved with editing software ({tools}).")
        c, m = _pdf_date(md.get("creationDate")), _pdf_date(md.get("modDate"))
        facts.append(f"Created: {c or 'not stated'} · Modified: {m or 'not stated'}")
        if c and m and (m - c) > dt.timedelta(minutes=2):
            warnings.append(f"Modified {m - c} after it was created.")
        saves = data.count(b"%%EOF")
        if saves > 1:
            warnings.append(f"The file was saved {saves} times (incremental updates appended after the original).")
        if not md.get("creator") and not md.get("producer"):
            facts.append("No creator/producer metadata (some generators omit it; editors can strip it).")
    elif detected_type in ("jpeg", "png", "webp"):
        try:
            from PIL import Image
            with Image.open(io.BytesIO(data)) as im:
                ex = im.getexif()
                sw = str(ex.get(0x0131, "") or "")
                when = str(ex.get(0x0132, "") or "")
                orig = str(ex.get_ifd(0x8769).get(0x9003, "") or "")
        except Exception:                                    # noqa: BLE001
            return None
        facts.append(f"Software tag: {sw or 'none'}")
        if sw and EDIT_TOOLS.search(sw):
            warnings.append(f"Saved with image-editing software ({sw}).")
        if when and orig and when != orig:
            warnings.append(f"Changed after it was taken (taken {orig}, last saved {when}).")
    else:
        return None
    return {"warnings": warnings, "facts": facts}


def as_derivative(data: bytes, detected_type: str) -> dict | None:
    res = check(data, detected_type)
    if res is None:
        return None
    lines = [f"WARNING: {w}" for w in res["warnings"]] + res["facts"]
    note = ("Signs of editing found (not proof). Confirm this payment with the bank before relying on the document."
            if res["warnings"] else "No signs of editing in the file's metadata. This does not prove it is genuine.")
    return {"kind": "integrity-signals", "method": "metadata-rules", "content": "\n".join(lines), "ai_generated": False,
            "note": note}
