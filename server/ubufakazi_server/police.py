"""Station-isolated access to reports, leads and the investigation graph.

The rule everywhere: an officer sees full details only for reports held by their own station(s).
A report at another station can appear ONLY as a restricted stub (station name + which kinds of signal
link it), so officers learn that a connection exists and can request access through proper channels.
"""
from __future__ import annotations

import datetime as dt
from collections import Counter, defaultdict

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Query, Session

from . import intel
from .extract import TYPE_LABEL
from .models import CATEGORIES, STATUS_LABELS, Identifier, IntelMatch, Report, Station
from .security import Principal


def scope_reports(db: Session, p: Principal) -> Query:
    q = db.query(Report)
    if not p.is_admin:
        q = q.filter(Report.station_id.in_(p.station_ids or {-1}))
    return q


def get_report(db: Session, p: Principal, reference: str) -> Report:
    r = db.query(Report).filter_by(reference=reference).first()
    # Same answer for "does not exist" and "not your station", so references cannot be probed.
    if not r or not p.can_see_station(r.station_id):
        raise HTTPException(status_code=404, detail="Report not found.")
    return r


def summary(r: Report) -> dict:
    return {"reference": r.reference, "category": r.category, "category_label": CATEGORIES.get(r.category, r.category),
            "scam_type": r.scam_type, "scam_type_label": TYPE_LABEL.get(r.scam_type or "", None),
            "status": r.status, "status_label": STATUS_LABELS.get(r.status, r.status),
            "processing_status": r.processing_status, "station": r.station.name, "station_code": r.station.code,
            "province": r.province, "town": r.town, "created_at": r.created_at.isoformat() + "Z",
            "incident_when": r.incident_when, "amount_paid": r.amount_paid, "source": r.source, "is_seed": r.is_seed,
            "complainant_name": r.complainant_name, "evidence_count": len(r.evidence),
            "sensitive": bool(r.safety.get("unsafe")) or r.category == "abuse"}


def leads_for(db: Session, r: Report, p: Principal) -> list[dict]:
    out = []
    for m in intel.matches_for(db, r.id):
        oid = m.report_b if m.report_a == r.id else m.report_a
        o = db.get(Report, oid)
        if o is None:
            continue
        visible = p.can_see_station(o.station_id)
        sigs = m.signals if visible else [{"kind": s["kind"], "label": s["label"], "display": s["display"] if s["kind"] != "script" else "",
                                          "reason": s["reason"], "conflicts": s.get("conflicts", [])} for s in m.signals]
        out.append({"reference": o.reference if visible else None, "visible": visible, "station": o.station.name,
                    "station_code": o.station.code, "strength": m.strength, "signals": sigs,
                    "date": o.created_at.date().isoformat() if visible else None,
                    "amount_paid": o.amount_paid if visible else None,
                    "status_label": STATUS_LABELS.get(o.status) if visible else None})
    out.sort(key=lambda x: (x["strength"] != "corroborated", -len(x["signals"])))
    return out


def graph_for(db: Session, r: Report, p: Principal, limit: int = 60) -> dict:
    ids = intel.cluster(db, r.id, limit)
    reports = {x.id: x for x in db.query(Report).filter(Report.id.in_(ids)).all()}
    nodes, edges = [], []
    for rid, x in reports.items():
        vis = p.can_see_station(x.station_id)
        nodes.append({"id": f"r{rid}", "type": "report", "focus": rid == r.id, "visible": vis,
                      "label": x.reference if vis else "Restricted report", "station": x.station.name,
                      "amount": x.amount_paid if vis else None, "date": x.created_at.date().isoformat() if vis else None,
                      "scam_type": TYPE_LABEL.get(x.scam_type or "", None) if vis else None,
                      "status": STATUS_LABELS.get(x.status) if vis else None})
    # identifiers shared by 2+ reports in the cluster; display text only comes from a report the viewer may see
    idents = db.query(Identifier).filter(Identifier.report_id.in_(ids)).all()
    by_key = defaultdict(list)
    for i in idents:
        by_key[(i.kind, i.hmac)].append(i)
    for (kind, hm), group in by_key.items():
        rids = {i.report_id for i in group}
        if len(rids) < 2:
            continue
        shown = next((i for i in group if p.can_see_station(reports[i.report_id].station_id)), None)
        if shown is None:
            continue   # nobody visible holds it: do not reveal the identifier at all
        nid = f"i{kind}{hm[:16]}"
        nodes.append({"id": nid, "type": kind, "label": shown.display, "count": len(rids)})
        for rid in rids:
            edges.append({"source": f"r{rid}", "target": nid, "kind": kind})
    for m in db.query(IntelMatch).filter(IntelMatch.report_a.in_(ids), IntelMatch.report_b.in_(ids)).all():
        for s in m.signals:
            if s["kind"] == "script":
                edges.append({"source": f"r{m.report_a}", "target": f"r{m.report_b}", "kind": "script", "score": s.get("score")})
    visible_amount = sum((n["amount"] or 0) for n in nodes if n["type"] == "report" and n["visible"])
    return {"nodes": nodes, "edges": edges, "truncated": len(ids) >= limit,
            "summary": {"reports": len(reports), "visible": sum(1 for n in nodes if n["type"] == "report" and n["visible"]),
                        "restricted": sum(1 for n in nodes if n["type"] == "report" and not n["visible"]),
                        "stations": len({x.station_id for x in reports.values()}), "visible_amount": visible_amount}}


def clusters(db: Session, p: Principal, min_size: int = 2) -> list[dict]:
    """Connected groups of reports (through possible-connection links) that include at least one visible report."""
    adj = defaultdict(set)
    for a, b in db.query(IntelMatch.report_a, IntelMatch.report_b).all():
        adj[a].add(b)
        adj[b].add(a)
    seen, groups = set(), []
    for start in list(adj):
        if start in seen:
            continue
        comp, stack = set(), [start]
        while stack:
            n = stack.pop()
            if n in comp:
                continue
            comp.add(n)
            stack.extend(adj[n] - comp)
        seen |= comp
        if len(comp) >= min_size:
            groups.append(comp)
    out = []
    for comp in groups:
        reps = db.query(Report).filter(Report.id.in_(comp)).all()
        vis = [x for x in reps if p.can_see_station(x.station_id)]
        if not vis:
            continue
        idents = db.query(Identifier).filter(Identifier.report_id.in_([x.id for x in vis])).all()

        all_cnt = Counter((i.kind, i.hmac) for i in db.query(Identifier).filter(Identifier.report_id.in_(comp)).all())
        shared = []
        for i in idents:
            k = (i.kind, i.hmac)
            if all_cnt[k] >= 2 and not any(s["key"] == k for s in shared):
                shared.append({"key": k, "kind": i.kind, "display": i.display, "reports": all_cnt[k]})
        shared.sort(key=lambda s: -s["reports"])
        dates = sorted(x.created_at for x in reps)
        types = Counter(x.scam_type for x in reps if x.scam_type)
        out.append({"anchor": sorted(vis, key=lambda x: x.created_at)[-1].reference, "size": len(reps), "visible": len(vis),
                    "restricted": len(reps) - len(vis), "stations": len({x.station_id for x in reps}),
                    "provinces": sorted({x.province for x in reps if x.province}),
                    "visible_amount": sum(x.amount_paid or 0 for x in vis),
                    "first": dates[0].date().isoformat(), "last": dates[-1].date().isoformat(),
                    "scam_type": TYPE_LABEL.get(types.most_common(1)[0][0], None) if types else None,
                    "shared": [{k: v for k, v in s.items() if k != "key"} for s in shared[:6]]})
    out.sort(key=lambda c: (-c["size"], c["anchor"]))
    return out


def stats(db: Session, p: Principal) -> dict:
    q = scope_reports(db, p)
    by_status = dict(q.with_entities(Report.status, func.count()).group_by(Report.status).all())
    by_cat = dict(q.with_entities(Report.category, func.count()).group_by(Report.category).all())
    total = sum(by_status.values())
    loss = q.with_entities(func.coalesce(func.sum(Report.amount_paid), 0)).scalar() or 0
    since = dt.datetime.utcnow() - dt.timedelta(days=120)
    days = Counter(d.date().isoformat() for (d,) in q.with_entities(Report.created_at).filter(Report.created_at >= since).all())
    visible_ids = [i for (i,) in q.with_entities(Report.id).all()]
    linked = 0
    if visible_ids:
        linked = db.query(func.count(func.distinct(IntelMatch.report_a))).filter(IntelMatch.report_a.in_(visible_ids)).scalar() or 0
        linked2 = {a for (a,) in db.query(IntelMatch.report_b).filter(IntelMatch.report_b.in_(visible_ids)).all()}
        linked1 = {a for (a,) in db.query(IntelMatch.report_a).filter(IntelMatch.report_a.in_(visible_ids)).all()}
        linked = len(linked1 | linked2)
    return {"total": total, "by_status": {k: {"label": STATUS_LABELS[k], "count": by_status.get(k, 0)} for k in STATUS_LABELS},
            "by_category": {k: {"label": CATEGORIES[k], "count": by_cat.get(k, 0)} for k in CATEGORIES},
            "reported_loss": float(loss), "per_day": sorted(days.items()), "linked_reports": linked,
            "awaiting": by_status.get("awaiting_review", 0) + by_status.get("submitted", 0)}


def stations_for(db: Session, p: Principal) -> list[dict]:
    q = db.query(Station).order_by(Station.province, Station.name)
    if not p.is_admin:
        q = q.filter(Station.id.in_(p.station_ids or {-1}))
    return [{"id": s.id, "code": s.code, "name": s.name, "province": s.province} for s in q.all()]


def search(q: Query, text: str) -> Query:
    like = f"%{text.strip()[:80]}%"
    return q.filter(or_(Report.reference.ilike(like), Report.description.ilike(like), Report.town.ilike(like),
                        Report.complainant_name.ilike(like)))
