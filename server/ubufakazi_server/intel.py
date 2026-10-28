"""Scam intelligence: identifiers, explainable matching and the investigation graph.

Rules (documented, not statistical):
- A shared identifier (same account, phone, email, website domain, social profile, @username or
  payment reference, compared by keyed HMAC) is a SIGNAL.
- Message-template similarity: the share of 3-word phrases of the shorter message set that also appear
  in the other is >= 0.35 (the MVP's threshold), on at least 6 phrases. It is a SIGNAL.
- One signal = "single" lead. Two or more different signal kinds = "corroborated" lead.
- Nothing here proves identity or guilt: an account may belong to a money mule or a compromised holder.
"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import or_
from sqlalchemy.orm import Session

from .extract import containment, mask_acc, shingles, show_acc, show_phone
from .models import BankAlert, Identifier, IntelMatch, Report, FINANCIAL_CATEGORIES
from .security import identifier_hmac

SIGNAL_LABEL = {
    "account": "Same receiving bank account", "phone": "Same phone number", "email": "Same email address",
    "domain": "Same website domain", "social": "Same social media profile", "username": "Same @username",
    "payment_ref": "Same payment reference", "script": "Repeated message template",
}
MIN_PHRASES = 6
SCRIPT_THRESHOLD = 0.35


def identifiers_from_analysis(ex: dict, source: str = "chat") -> list[dict]:
    out = []
    for a in ex.get("accounts", []):
        out.append({"kind": "account", "value": a["value"], "display": show_acc(a["value"]), "bank": a.get("bank"), "source": source})
    for p in ex.get("phones", []):
        out.append({"kind": "phone", "value": p["value"], "display": show_phone(p["value"]), "source": source})
    for e in ex.get("emails", []):
        out.append({"kind": "email", "value": e["value"], "display": e["value"], "source": source})
    for d in ex.get("domains", []):
        out.append({"kind": "domain", "value": d, "display": d, "source": source})
    for s in ex.get("social", []):
        v = s["url"].split("?")[0].rstrip("/").lower().replace("://www.", "://").replace("://m.", "://")
        out.append({"kind": "social", "value": v, "display": f"{s['platform']}: {s['url']}", "source": source})
    for u in ex.get("usernames", []):
        out.append({"kind": "username", "value": u["value"], "display": u["value"], "source": source})
    for r in ex.get("payment_refs", []):
        out.append({"kind": "payment_ref", "value": r["value"], "display": r["value"], "source": source})
    return out


def save_identifiers(db: Session, report: Report, items: list[dict]) -> list[Identifier]:
    have = {(i.kind, i.hmac) for i in report.identifiers}
    saved = []
    for it in items:
        hm = identifier_hmac(it["kind"], it["value"])
        if (it["kind"], hm) in have:
            continue
        have.add((it["kind"], hm))
        ident = Identifier(kind=it["kind"], value=it["value"][:300], display=it["display"][:300],
                           hmac=hm, bank=it.get("bank"), source=it.get("source", "chat"))
        report.identifiers.append(ident)
        saved.append(ident)
    db.flush()
    return saved


def script_similarity(a: str, b: str) -> tuple[float, int, int]:
    sa, sb = shingles(a), shingles(b)
    if len(sa) < MIN_PHRASES or len(sb) < MIN_PHRASES:
        return 0.0, 0, 0
    small, big = (sa, sb) if len(sa) <= len(sb) else (sb, sa)
    return containment(big, small), len(small & big), len(small)


def compute_matches(db: Session, report: Report) -> list[IntelMatch]:
    """(Re)compute possible connections between `report` and every other report."""
    by_other: dict[int, list[dict]] = defaultdict(list)
    mine = {(i.kind, i.hmac): i for i in report.identifiers}
    if mine:
        conds = [(Identifier.kind == k) & (Identifier.hmac == h) for k, h in mine]
        for other in db.query(Identifier).filter(Identifier.report_id != report.id, or_(*conds)).all():
            me = mine[(other.kind, other.hmac)]
            sig = {"kind": other.kind, "label": SIGNAL_LABEL[other.kind], "display": me.display, "hmac": other.hmac,
                   "reason": f"{SIGNAL_LABEL[other.kind]} ({me.display}) appears in both reports.", "conflicts": []}
            if other.kind == "account" and me.bank and other.bank and me.bank != other.bank:
                sig["conflicts"].append(f"Bank names differ: '{me.bank}' vs '{other.bank}'.")
            if not any(s["kind"] == sig["kind"] and s["hmac"] == sig["hmac"] for s in by_other[other.report_id]):
                by_other[other.report_id].append(sig)
    if report.script_text and len(shingles(report.script_text)) >= MIN_PHRASES:
        for oid, otext in db.query(Report.id, Report.script_text).filter(Report.id != report.id, Report.script_text != "").all():
            score, shared, total = script_similarity(report.script_text, otext)
            if score >= SCRIPT_THRESHOLD:
                by_other[oid].append({"kind": "script", "label": SIGNAL_LABEL["script"], "display": f"{shared} of {total} phrases shared",
                                      "hmac": "", "score": round(score, 2), "conflicts": [],
                                      "reason": f"The messages share {shared} of {total} three-word phrases ({round(score * 100)}%), "
                                                f"above the documented {round(SCRIPT_THRESHOLD * 100)}% threshold."})
    out = []
    for oid, signals in by_other.items():
        a, b = sorted((report.id, oid))
        kinds = {s["kind"] for s in signals}
        m = db.query(IntelMatch).filter_by(report_a=a, report_b=b).first()
        if not m:
            m = IntelMatch(report_a=a, report_b=b)
            db.add(m)
        m.signals = signals
        m.strength = "corroborated" if len(kinds) >= 2 else "single"
        out.append(m)
    db.flush()
    return out


def matches_for(db: Session, report_id: int) -> list[IntelMatch]:
    return db.query(IntelMatch).filter(or_(IntelMatch.report_a == report_id, IntelMatch.report_b == report_id)).all()


def cluster(db: Session, report_id: int, max_reports: int = 60) -> set[int]:
    """Reports reachable from report_id through possible-connection links (breadth-first)."""
    seen, frontier = {report_id}, [report_id]
    while frontier and len(seen) < max_reports:
        nxt = []
        for rid in frontier:
            for m in matches_for(db, rid):
                o = m.report_b if m.report_a == rid else m.report_a
                if o not in seen:
                    seen.add(o)
                    nxt.append(o)
        frontier = nxt
    return seen


def update_bank_alerts(db: Session, report: Report) -> list[BankAlert]:
    """Fictional demo alerts: one per receiving account named in a financial report."""
    if report.category not in FINANCIAL_CATEGORIES:
        return []
    from .aiguard import untrusted
    out = []
    for i in report.identifiers:
        if i.kind != "account":
            continue
        if untrusted(i.source) and not any(not untrusted(s) for (s,) in db.query(Identifier.source).filter(
                Identifier.kind == "account", Identifier.hmac == i.hmac).all()):
            continue      # AI-only / injection-flagged: a lead for SAPS, never a bank alert on its own
        al = db.query(BankAlert).filter_by(account_hmac=i.hmac).first()
        if not al:
            al = BankAlert(account_hmac=i.hmac, account_display=mask_acc(i.value), bank_stated=i.bank or "")
            db.add(al)
        elif al.status == "reviewed":
            al.status = "new"   # new report about an already-reviewed account re-opens it
        out.append(al)
    db.flush()
    return out
