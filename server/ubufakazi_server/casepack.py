"""PDF case pack (reportlab). Two audiences:

- "complainant": what the victim takes to the station. Never contains other people's reports.
- "police": adds possible connections (investigative leads), status history, notes and the custody log.

Every automatically extracted or AI-generated item is labelled as unverified.
"""
from __future__ import annotations

import datetime as dt
import io
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)
from sqlalchemy.orm import Session

from . import handover, timestamps
from .extract import TYPE_LABEL, money
from .models import CATEGORY_LABELS, STATUS_LABELS, AuditEvent, Note, Report, Station, StationHandover, StatusChange
from .writing import LANG_NAMES

INK = colors.HexColor("#0B1016")
MUTED = colors.HexColor("#5B6B7D")
ACCENT = colors.HexColor("#0F8F7B")
ALERT = colors.HexColor("#B4442A")
LINE = colors.HexColor("#C9D3DD")
TINT = colors.HexColor("#EEF6F4")
WARN_TINT = colors.HexColor("#FBEDE8")

_REPL = {"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", "…": "...",
         "·": "-", "→": "->", "•": "-", " ": " ", " ": " ", " ": " ", "≥": ">="}


def t(s) -> str:
    """Sanitise to the Latin-1 range of the built-in PDF fonts, then escape for reportlab markup."""
    s = "" if s is None else str(s)
    for a, b in _REPL.items():
        s = s.replace(a, b)
    s = s.encode("latin-1", "replace").decode("latin-1")
    return escape(s)


def _styles():
    base = dict(fontName="Helvetica", fontSize=9.5, leading=13.2, textColor=INK, alignment=TA_LEFT)
    return {
        "body": ParagraphStyle("body", **base),
        "small": ParagraphStyle("small", **{**base, "fontSize": 8, "leading": 10.5, "textColor": MUTED}),
        "mono": ParagraphStyle("mono", **{**base, "fontName": "Courier", "fontSize": 7.6, "leading": 9.6}),
        "stmt": ParagraphStyle("stmt", **{**base, "fontSize": 10, "leading": 14.5}),
        "h1": ParagraphStyle("h1", **{**base, "fontName": "Helvetica-Bold", "fontSize": 20, "leading": 24}),
        "h2": ParagraphStyle("h2", **{**base, "fontName": "Helvetica-Bold", "fontSize": 12.5, "leading": 16,
                                      "spaceBefore": 10, "spaceAfter": 5, "textColor": ACCENT}),
        "label": ParagraphStyle("label", **{**base, "fontName": "Helvetica-Bold", "fontSize": 7.6, "leading": 10,
                                         "textColor": MUTED}),
        "cell": ParagraphStyle("cell", **{**base, "fontSize": 8.4, "leading": 11}),
        "cellb": ParagraphStyle("cellb", **{**base, "fontName": "Helvetica-Bold", "fontSize": 8.4, "leading": 11}),
    }


def _box(flow, tint=TINT, border=ACCENT):
    tb = Table([[flow]], colWidths=[174 * mm])
    tb.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), tint), ("LINEBEFORE", (0, 0), (0, -1), 2.2, border),
                            ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return tb


def _grid(rows, widths, S, header=True):
    data = [[Paragraph(c if isinstance(c, str) else t(c), S["cellb" if (header and i == 0) else "cell"]) for c in row]
            for i, row in enumerate(rows)]
    tb = Table(data, colWidths=[w * mm for w in widths], repeatRows=1 if header else 0)
    style = [("GRID", (0, 0), (-1, -1), 0.4, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), TINT))
    tb.setStyle(TableStyle(style))
    return tb


def _fmt(d: dt.datetime | None) -> str:
    return d.strftime("%d %b %Y %H:%M UTC") if d else "-"


def _handover_box(r: Report, S):
    """QR code the complainant shows at the station. It only helps an officer find the report after signing in."""
    from reportlab.graphics.barcode.qr import QrCodeWidget
    from reportlab.graphics.shapes import Drawing
    w = QrCodeWidget(handover.url_for(r.reference))
    x0, y0, x1, y1 = w.getBounds()
    size = 34 * mm
    d = Drawing(size, size, transform=[size / (x1 - x0), 0, 0, size / (y1 - y0), 0, 0])
    d.add(w)
    text = Paragraph(
        "<b>At the police station: show this code to the officer.</b><br/>"
        "Scanning it lets the officer open your Ubufakazi report <i>after</i> signing in with their own password and "
        "two-factor code, and accept the case at that station, even if it is not the station Ubufakazi suggested. "
        "It does not register the case by itself: the station registers it in its own system and gives you a CAS "
        f"number.<br/><font size='7'>Reference {escape(r.reference)}. Keep this pack private. On a computer, the officer can "
        f"also open <a href='{escape(handover.url_for(r.reference))}' color='#0A7C74'>this handover link</a>.</font>", S["small"])
    tb = Table([[d, text]], colWidths=[38 * mm, 136 * mm])
    tb.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                            ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return tb


def _seal_box(seal_id: str, S):
    """QR code that lets anyone check this PDF is genuine and unchanged (see seals.py)."""
    from reportlab.graphics.barcode.qr import QrCodeWidget
    from reportlab.graphics.shapes import Drawing
    from .services import track_url
    url = track_url().rsplit("/track", 1)[0] + f"/verify?seal={seal_id}"
    w = QrCodeWidget(url)
    x0, y0, x1, y1 = w.getBounds()
    size = 26 * mm
    d = Drawing(size, size, transform=[size / (x1 - x0), 0, 0, size / (y1 - y0), 0, 0])
    d.add(w)
    text = Paragraph(
        f"<b>DOCUMENT SEAL {escape(seal_id)}</b><br/>This PDF is sealed by Ubufakazi: its SHA-256 fingerprint was recorded "
        "when it was issued, with an independent RFC 3161 timestamp. Scan the code, or open "
        f"<a href='{escape(url)}' color='#0A7C74'>{escape(url)}</a>, and drop this PDF on the page: it shows "
        "<b>Authentic</b> only if not a single character has changed.", S["small"])
    tb = Table([[d, text]], colWidths=[30 * mm, 144 * mm])
    tb.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("BOX", (0, 0), (-1, -1), 0.8, ACCENT),
                            ("BACKGROUND", (0, 0), (-1, -1), TINT),
                            ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    return tb


def build_case_pack(db: Session, r: Report, audience: str = "complainant", viewer=None, leads: list[dict] | None = None) -> bytes:
    """Issues a SEALED case pack (see seals.py). leads: pre-computed, access-filtered connections (police only)."""
    from . import seals
    who = (f"officer:{viewer.user.username}" if viewer is not None and getattr(viewer, "user", None) else audience)
    seal_id = seals.new_seal("case_pack_police" if audience == "police" else "case_pack_complainant", r.reference, who,
                             r.station_id)
    pdf = _build_case_pack(db, r, audience, viewer, leads, seal_id)
    seals.finish(seal_id, pdf)
    return pdf


def _build_case_pack(db: Session, r: Report, audience: str, viewer, leads, seal_id: str) -> bytes:
    S = _styles()
    buf = io.BytesIO()
    police = audience == "police"
    generated = dt.datetime.now(dt.timezone.utc).strftime("%d %b %Y %H:%M UTC")

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(ALERT)
        canvas.rect(0, A4[1] - 9 * mm, A4[0], 9 * mm, stroke=0, fill=1)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 7.6)
        canvas.drawString(18 * mm, A4[1] - 6 * mm,
                          "DEMONSTRATION - NOT AN OFFICIAL SAPS DOCUMENT - NO CASE NUMBER ISSUED - FICTIONAL STATIONS")
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 7.4)
        canvas.drawString(18 * mm, 10 * mm, f"Ubufakazi case pack {r.reference} - {'POLICE COPY (restricted)' if police else 'Complainant copy'}"
                                            f" - generated {generated}")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=17 * mm,
                            bottomMargin=17 * mm, title=f"Ubufakazi case pack {r.reference}", author="Ubufakazi (demo)",
                            subject="Draft case pack, demonstration only")
    f = []
    P = lambda s, st="body": Paragraph(s, S[st])  # noqa: E731

    # ---------------------------------------------------------------- cover
    f.append(P("UBUFAKAZI - DRAFT CASE PACK", "label"))
    f.append(P(t(r.reference), "h1"))
    f.append(Spacer(1, 4))
    facts = r.facts or {}
    cover = [
        ["Category", CATEGORY_LABELS.get(r.category, r.category)],
        ["Type (detected)", facts.get("scam_type_label") or TYPE_LABEL.get(r.scam_type or "", "-")],
        ["Demo station", f"{r.station.name} (fictional, for demonstration only)"],
        ["Area", ", ".join(x for x in (r.town, r.province) if x) or "-"],
        ["When it happened (as stated)", r.incident_when or "-"],
        ["Submitted", _fmt(r.created_at) + f" via {r.source}"],
        ["Status in Ubufakazi", STATUS_LABELS.get(r.status, r.status)],
        ["Statement language", LANG_NAMES.get(r.language, r.language)],
        ["Amount paid (extracted)", money(r.amount_paid) if r.amount_paid else "-"],
        ["Evidence files", str(len(r.evidence))],
    ]
    ho = db.query(StationHandover).filter_by(report_id=r.id).first()
    if ho and ho.cas_number:
        cover.append(["Registered at station", f"{ho.cas_number} at {db.get(Station, ho.station_id).name} "
                                               "(entered by the officer; not verified with SAPS)"])
    f.append(_kv(cover, S))
    f.append(Spacer(1, 6))
    f.append(_seal_box(seal_id, S))
    f.append(Spacer(1, 8))
    f.append(_box(P(
        "<b>What this is.</b> A draft prepared automatically from what the complainant reported, so the station visit is "
        "faster. It is <b>not</b> a sworn statement and <b>not</b> registered with SAPS: no CAS number exists until SAPS "
        "registers the case. Items marked <i>extracted</i> or <i>AI-generated</i> are unverified until an officer checks "
        "them against the original files.", "small"), WARN_TINT, ALERT))
    if not police:
        f.append(Spacer(1, 8))
        f.append(P("What to do next", "h2"))
        for i, line in enumerate([
            "Call your bank's fraud line now. The faster the bank acts, the more likely the money can be frozen and recalled.",
            "Read the fraud dispute statement below, correct anything wrong, sign it and send it with this pack to your bank. A draft bank fraud report is included too.",
            "If the account you paid is at a bank connected to Ubufakazi, that bank has already received a fraud alert (in this demo: Ubuntu Trust Bank, a fictional bank).",
            "You can also report at a police station: this pack includes everything they need, with a QR code for the officer.",
            "Keep the original files (screenshots, chats, receipts). Their fingerprints (SHA-256) are listed in this pack, so anyone can check they were not changed.",
            "In danger right now? Call 10111. Gender-based violence: GBV Command Centre 0800 428 428.",
        ], 1):
            f.append(P(f"<b>{i}.</b> {t(line)}"))
        f.append(Spacer(1, 8))
        f.append(_handover_box(r, S))
    if r.safety.get("unsafe") or r.category == "abuse":
        f.append(Spacer(1, 6))
        f.append(_box(P("<b>Sensitive report.</b> Handle with care: do not contact the complainant through shared devices "
                        "or channels the other person can see. Emergency: 10111. GBV Command Centre: 0800 428 428.", "small"),
                      WARN_TINT, ALERT))

    # ---------------------------------------------------------------- complainant's account
    f.append(P("1. The complainant's account (their own words)", "h2"))
    f.append(P(t(r.description).replace("\n", "<br/>")))
    if r.answers:
        rows = [["Question", "Answer"]] + [[k.replace("_", " ").capitalize(), str(v)] for k, v in r.answers.items() if v]
        if len(rows) > 1:
            f.append(Spacer(1, 4))
            f.append(_grid(rows, [60, 114], S))

    # ---------------------------------------------------------------- statement
    f.append(PageBreak())
    f.append(P(f"2. Fraud dispute statement to the bank ({t(LANG_NAMES.get(r.language, r.language))})", "h2"))
    f.append(P(t(r.statement or "Not prepared yet.").replace("\n", "<br/>"), "stmt"))
    if police and r.language != "en" and (r.statements or {}).get("en"):
        f.append(Spacer(1, 8))
        f.append(P("English version (for the officer)", "h2"))
        f.append(P(t(r.statements["en"]).replace("\n", "<br/>"), "stmt"))

    # ---------------------------------------------------------------- extracted facts
    f.append(P("3. Facts extracted from the evidence (unverified)", "h2"))
    f.append(P(t(facts.get("method") or "Not processed yet."), "small"))
    rows = [["What", "Value", "Source"]]
    for i in r.identifiers:
        label = {"account": "Receiving account", "phone": "Phone number", "email": "Email", "domain": "Website",
                 "social": "Social media profile", "username": "@username", "payment_ref": "Payment reference",
                 "url": "Link"}.get(i.kind, i.kind)
        val = i.display + (f" ({i.bank})" if i.bank else "")
        rows.append([label, val, _source_label(i.source, r)])
    if facts.get("suspect_alias"):
        rows.append(["Name the other person used", facts["suspect_alias"], "chat"])
    if facts.get("total_paid") is not None:
        rows.append(["Total paid", money(facts["total_paid"]), "chat"])
    f.append(_grid(rows, [44, 90, 40], S) if len(rows) > 1 else P("No identifiers found automatically.", "small"))

    # ---------------------------------------------------------------- timeline
    if r.timeline:
        f.append(P("4. Timeline", "h2"))
        rows = [["When", "What happened", "Source"]]
        for e in r.timeline:
            what = t(e.what) + (f'<br/><font color="#5B6B7D" size="7.4">"{t(e.quote)}"</font>' if e.quote else "")
            rows.append([e.when_text or "-", what, {"chat": "chat (extracted)", "complainant": "complainant",
                                                    "system": "Ubufakazi"}.get(e.source, e.source)])
        f.append(_grid(rows, [34, 110, 30], S))

    # ---------------------------------------------------------------- evidence register
    f.append(PageBreak())
    f.append(P("5. Evidence register and integrity", "h2"))
    f.append(P("Each original file is stored exactly as received and never changed. Its SHA-256 fingerprint was calculated "
               "by the Ubufakazi server when the file arrived. To check a copy, calculate its SHA-256 (for example on the "
               "Ubufakazi verify page, which works offline in the browser) and compare it with the value below. "
               "'Received' is the server's clock; trusted third-party timestamps, where present, are listed below the table.", "small"))
    f.append(Spacer(1, 4))
    rows = [["#", "File", "Type / size", "Received", "SHA-256"]]
    for n, ev in enumerate(r.evidence, 1):
        rows.append([str(n), ev.original_name, f"{ev.detected_type} / {_size(ev.size)}", _fmt(ev.received_at),
                     f'<font name="Courier" size="6.6">{ev.sha256[:32]}<br/>{ev.sha256[32:]}</font>'])
    f.append(_grid(rows, [7, 50, 25, 32, 60], S) if len(rows) > 1 else P("No files were attached.", "small"))
    stamped = [(n, ev, timestamps.public_info(ev.trusted_timestamp)) for n, ev in enumerate(r.evidence, 1)
               if ev.trusted_timestamp]
    if stamped:
        f.append(Spacer(1, 6))
        f.append(P("Trusted timestamps (RFC 3161)", "label"))
        f.append(P("An independent timestamp authority signed each file's SHA-256 fingerprint at the time shown. Only the "
                   "fingerprint was sent, never the file. The signed tokens (.tsr) can be checked without Ubufakazi, "
                   "for example with 'openssl ts -verify'.", "small"))
        rows = [["#", "Timestamp (UTC)", "Authority", "Token serial"]]
        for n, ev, info in stamped:
            if info:
                rows.append([str(n), escape(info["gen_time"].replace("T", " ").replace("Z", "")), escape(info["tsa"]),
                             escape(info["serial"])])
        f.append(_grid(rows, [7, 40, 85, 42], S))
    derived = [(ev, d) for ev in r.evidence for d in ev.derivatives]
    if derived:
        f.append(Spacer(1, 6))
        f.append(P("Derived material (kept separately from the originals)", "label"))
        rows = [["From file", "Kind", "Method", "Note"]]
        for ev, d in derived:
            kind = d.kind + (" (AI-GENERATED, unverified)" if d.ai_generated else "")
            rows.append([ev.original_name, kind, d.method, d.note])
        f.append(_grid(rows, [46, 34, 28, 66], S))

    # ---------------------------------------------------------------- bank report
    if r.bank_report:
        f.append(P("6. Draft fraud report for the complainant's bank", "h2"))
        f.append(P("For the complainant to send to their own bank. Ubufakazi has not contacted any bank.", "small"))
        f.append(Spacer(1, 3))
        f.append(_box(P(t(r.bank_report).replace("\n", "<br/>"), "cell")))

    # ---------------------------------------------------------------- police-only sections
    if police:
        f.append(PageBreak())
        f.append(P("7. Possible connections (investigative leads)", "h2"))
        f.append(P("A lead means another report shares an identifier or message template with this one. It is a reason "
                   "to look further, not proof that the same person is responsible: accounts can belong to money mules, "
                   "and numbers can be recycled or spoofed. Rule: one shared signal = single lead; two or more different "
                   "kinds = corroborated lead.", "small"))
        if leads:
            rows = [["Other report", "Held by", "Signals and reasons", "Lead"]]
            for L in leads:
                reasons = "<br/>".join("- " + t(s["reason"]) + ("".join(f'<br/><font color="#B4442A">  Conflict: {t(c)}</font>'
                                                                         for c in s.get("conflicts", [])))
                                       for s in L["signals"])
                rows.append([t(L["reference"]) if L["visible"] else "<i>Restricted</i>", t(L["station"]), reasons,
                             t(L["strength"])])
            f.append(_grid(rows, [28, 34, 92, 20], S))
        else:
            f.append(P("No possible connections found.", "small"))

        f.append(P("8. Status history and notes", "h2"))
        rows = [["When", "Change", "By / note"]]
        for sc in db.query(StatusChange).filter_by(report_id=r.id).order_by(StatusChange.at):
            rows.append([_fmt(sc.at), f"{STATUS_LABELS.get(sc.from_status, '-') if sc.from_status else 'New'} -> "
                                      f"{STATUS_LABELS.get(sc.to_status, sc.to_status)}", sc.note or "-"])
        for nt in db.query(Note).filter_by(report_id=r.id).order_by(Note.created_at):
            rows.append([_fmt(nt.created_at), "Note", f"{nt.author.display_name}: {nt.body}"])
        f.append(_grid(rows, [34, 60, 80], S))

        f.append(P("9. Chain of custody (from the hash-chained audit log)", "h2"))
        ev_ids = [str(e.id) for e in r.evidence]
        q = db.query(AuditEvent).filter(((AuditEvent.target_type == "report") & (AuditEvent.target_id == r.reference)) |
                                        ((AuditEvent.target_type == "evidence") & (AuditEvent.target_id.in_(ev_ids or ["-"]))))
        rows = [["When", "Action", "Actor", "Event hash"]]
        for a in q.order_by(AuditEvent.id).limit(200):
            rows.append([_fmt(a.at), a.action + (f" #{a.target_id}" if a.target_type == "evidence" else ""), a.actor,
                         f'<font name="Courier" size="6.6">{a.hash[:20]}...</font>'])
        f.append(_grid(rows, [34, 50, 50, 40], S))
        if viewer is not None:
            f.append(Spacer(1, 4))
            f.append(P(t(f"Police copy generated for {viewer.user.display_name} ({viewer.user.username}). "
                         "This download is recorded in the audit log."), "small"))

    f.append(P("Limitations", "h2"))
    f.append(P("Ubufakazi is a hackathon prototype using fictional stations and synthetic data. It is not connected to SAPS "
               "or any bank, and it cannot confirm who owns an account or number. Automatic extraction uses documented "
               "rules and can miss or misread details. The platform reduces the risk of undetected changes; it is not "
               "tamper-proof.", "small"))
    doc.build(f, onFirstPage=on_page, onLaterPages=on_page)
    return buf.getvalue()


def _kv(rows, S):
    data = [[Paragraph(t(a), S["label"]), Paragraph(t(b), S["cell"])] for a, b in rows]
    tb = Table(data, colWidths=[52 * mm, 122 * mm])
    tb.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 3),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    return tb


def _size(n: int) -> str:
    return f"{n} B" if n < 1024 else f"{n / 1024:.1f} KB" if n < 1024 * 1024 else f"{n / 1048576:.1f} MB"


def _source_label(src: str, r: Report) -> str:
    if src.startswith("evidence:"):
        ev_id = int(src.split(":")[1])
        for n, ev in enumerate(r.evidence, 1):
            if ev.id == ev_id:
                return f"file #{n} (extracted)"
    if src.startswith(("ai:", "flagged:")):
        kind, _, rest = src.partition(":")
        base = _source_label("evidence:" + rest, r) if rest.isdigit() else _source_label(rest, r)
        return base + (" · AI-read, unverified" if kind == "ai" else " · injection flagged")
    return {"chat": "chat (extracted)", "description": "complainant's words", "seed": "synthetic"}.get(src, src)
