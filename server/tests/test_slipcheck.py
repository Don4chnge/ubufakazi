"""Payment-slip integrity signals: edited files raise warning signs; clean generated files do not."""
from __future__ import annotations

import io

from conftest import KIT


def _pdf(edit: bool) -> bytes:
    import fitz
    from reportlab.pdfgen import canvas
    b = io.BytesIO()
    c = canvas.Canvas(b)
    c.drawString(72, 720, "Proof of payment R1 850 to account 1047228359")
    c.save()
    if not edit:
        return b.getvalue()
    doc = fitz.open(stream=b.getvalue(), filetype="pdf")
    doc.set_metadata({"producer": "Adobe Photoshop 25.0", "creator": "Adobe Photoshop 25.0",
                      "creationDate": "D:20261012090000", "modDate": "D:20261013180000"})
    return doc.tobytes() + b"\n%%EOF\n"                     # an appended update, as editors leave behind


def test_edited_slip_raises_warning_signs():
    from ubufakazi_server import slipcheck
    res = slipcheck.check(_pdf(edit=True), "pdf")
    assert any("editing software" in w for w in res["warnings"]) and any("Modified" in w for w in res["warnings"])
    assert slipcheck.check(_pdf(edit=False), "pdf")["warnings"] == []


def test_no_false_alarms_on_the_sample_kit():
    from ubufakazi_server import slipcheck
    for p in (KIT / "samples").rglob("*"):
        t = {".pdf": "pdf", ".png": "png", ".jpg": "jpeg"}.get(p.suffix)
        if t and "red-team" not in str(p):
            assert slipcheck.check(p.read_bytes(), t)["warnings"] == [], p.name
