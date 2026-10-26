"""Synthetic demo data: fictional stations, earlier reports and three fictional syndicates.

Mirrors tools/make_seed.py (the MVP's seed) so both versions tell the same story, but here the raw
identifiers are hashed with the SERVER's secret HMAC key, never a key shipped to browsers.
Every person, account, phone number and website below is invented.
"""
from __future__ import annotations

import datetime as dt
import random

from sqlalchemy.orm import Session

from . import audit, intel
from .extract import show_acc, show_phone
from .models import Report, Station, StatusChange, TimelineEvent
from .stations import DEMO_STATIONS
from .writing import general_statement

SCRIPTS = {
    "job_fee": ("Good morning! Your CV was shortlisted for the Admin Clerk position at Mzansi Retail Group. Salary R12 000 "
                "per month. Are you still interested? Congratulations, you have been selected. To secure your position you "
                "must pay a once-off registration and uniform fee of R1 500. Positions are limited so please pay today. "
                "Complete the onboarding form here. There is also a training fee of R1 200 which must be paid before Monday "
                "or you lose the position."),
    "parcel_swift": ("SwiftParcel: your parcel is held at our depot because customs duty is unpaid. Pay the clearance fee "
                     "within 24 hours or the parcel will be returned. Pay securely on our clearance page and send proof of payment."),
    "invest_double": ("Good day, invest today and receive ten times your money in 7 days with our crypto trading platform. "
                      "Returns are guaranteed and our account manager will guide you. Register on the link below and send proof of payment."),
    "sars_refund": ("SARS: You are due a tax refund. Please verify your banking details using the secure link below within "
                    "24 hours to receive your refund."),
}
SCAM_TEXT = {
    "job": "I was offered a job and asked to pay fees before starting. After paying, the recruiter stopped answering.",
    "parcel": "I received a message that my parcel was held and paid a clearance fee. No parcel arrived.",
    "investment": "I was promised guaranteed returns on an investment. I paid and could not withdraw anything.",
    "marketplace": "I paid a seller on an online marketplace for an item that was never delivered.",
    "romance": "Someone I met online asked me for money for an emergency. After I paid, they disappeared.",
    "sars": "I received a message about a tax refund and was asked to pay a fee or share my banking details.",
    "other": "I was tricked into making a payment and then could not reach the person again.",
}

SYN_ACC = "1047228359"
SYN_PHONES = ["+27614402281", "+27795513060", "+27832207749"]
SYN_DOMAIN = "mzansi-careers-onboard.site"
S2_ACCS = ["5530187264", "5530199012"]
S2_PHONES = ["+27612245873", "+27725561190", "+27836604412"]
S2_DOMAIN = "swiftparcel-clearance.online"
S3_ACC = "7718203345"
S3_DOMAIN = "doublemyrands-invest.site"
STATUS_MIX = ["awaiting_review"] * 5 + ["under_review"] * 3 + ["more_info_required", "prepared_for_visit", "closed"]


def _rows() -> list[dict]:
    rows = []

    def add(date, prov, kind, amount, script, acc=(), phone=(), domain=(), bank="DemoBank"):
        rows.append({"date": date, "province": prov, "kind": kind, "amount": amount, "script": script,
                     "acc": list(acc), "phone": list(phone), "domain": list(domain), "bank": bank})

    for d, p, a, ph, dom in [("2026-08-03", "Gauteng", 9500, 0, True), ("2026-08-19", "KwaZulu-Natal", 12000, 0, False),
                             ("2026-09-02", "Gauteng", 18500, 1, True), ("2026-09-14", "Limpopo", 7000, 1, False),
                             ("2026-09-29", "Western Cape", 22000, 2, True), ("2026-10-08", "Eastern Cape", 15000, 2, True)]:
        add(d, p, "job", a, "job_fee", [SYN_ACC], [SYN_PHONES[ph]], [SYN_DOMAIN] if dom else [])
    s2 = [("2026-07-04", "Gauteng", 850), ("2026-07-11", "Free State", 1200), ("2026-07-19", "KwaZulu-Natal", 650),
          ("2026-07-30", "Mpumalanga", 990), ("2026-08-08", "Gauteng", 1450), ("2026-08-21", "North West", 780),
          ("2026-09-03", "Western Cape", 1100), ("2026-09-17", "Limpopo", 560), ("2026-10-02", "Eastern Cape", 1320)]
    for k, (d, p, a) in enumerate(s2):
        add(d, p, "parcel", a, "parcel_swift", [S2_ACCS[0] if k < 5 else S2_ACCS[1]], [S2_PHONES[k % 3]],
            [S2_DOMAIN] if k % 2 == 0 else [], bank="Fictional Bank B")
    for k, (d, p, a) in enumerate([("2026-06-15", "Gauteng", 12000), ("2026-07-02", "Western Cape", 25000),
                                   ("2026-08-12", "KwaZulu-Natal", 8500), ("2026-09-09", "Gauteng", 40000),
                                   ("2026-09-26", "Northern Cape", 6000)]):
        add(d, p, "investment", a, "invest_double", [S3_ACC], ["+2779" + str(3310450 + k * 1117)], [S3_DOMAIN],
            bank="Fictional Bank C")

    rng = random.Random(2026)
    provinces = ["Gauteng", "KwaZulu-Natal", "Western Cape", "Eastern Cape", "Limpopo", "Mpumalanga", "North West",
                 "Free State", "Northern Cape"]
    weights = [26, 19, 12, 10, 9, 8, 7, 5, 4]
    ranges = {"job": (1500, 15000), "marketplace": (800, 8000), "romance": (5000, 60000), "investment": (2000, 50000),
              "parcel": (300, 3000), "sars": (1000, 9000), "other": (500, 12000)}

    def acc():
        return "".join(str(rng.randint(0, 9)) for _ in range(10))

    def phone():
        return "+27" + rng.choice("678") + "".join(str(rng.randint(0, 9)) for _ in range(8))

    def date():
        m = rng.choice([6, 7, 8, 9, 10])
        return f"2026-{m:02d}-{rng.randint(1, 28) if m < 10 else rng.randint(1, 15):02d}"

    market_acc, romance_acc = acc(), acc()
    for kind, a in [("marketplace", market_acc), ("marketplace", market_acc), ("romance", romance_acc), ("romance", romance_acc)]:
        lo, hi = ranges[kind]
        add(date(), rng.choices(provinces, weights)[0], kind, round(rng.randint(lo, hi), -1), None, [a], [phone()],
            bank="Fictional Bank D")
    kinds = ["job"] * 9 + ["marketplace"] * 13 + ["romance"] * 8 + ["investment"] * 7 + ["parcel"] * 6 + ["sars"] * 7 + ["other"] * 6
    for kind in kinds:
        lo, hi = ranges[kind]
        script = "sars_refund" if kind == "sars" and rng.random() < 0.5 else None
        add(date(), rng.choices(provinces, weights)[0], kind, round(rng.randint(lo, hi), -1), script, [acc()], [phone()],
            bank=rng.choice(["Fictional Bank B", "Fictional Bank C", "Fictional Bank D", "DemoBank"]))
    rows.sort(key=lambda r: r["date"])
    return rows


def seed_stations(db: Session) -> dict[str, Station]:
    out = {}
    for code, name, prov, towns in DEMO_STATIONS:
        st = db.query(Station).filter_by(code=code).first()
        if not st:
            st = Station(code=code, name=name, province=prov, towns=towns)
            db.add(st)
        out[code] = st
    db.flush()
    return out


def seed_reports(db: Session) -> int:
    if db.query(Report).filter_by(is_seed=True).first():
        return 0
    from .stations import route
    stations = {s.code: s for s in db.query(Station).all()}
    rng = random.Random(7)
    created = []
    for i, row in enumerate(_rows(), 1):
        st = stations[route(row["province"], None)]
        town = st.towns[i % len(st.towns)]
        when = dt.date.fromisoformat(row["date"])
        created_at = dt.datetime.combine(when + dt.timedelta(days=rng.randint(0, 3)), dt.time(rng.randint(7, 19), rng.randint(0, 59)))
        desc = SCAM_TEXT[row["kind"]] + f" I paid R{row['amount']:,}".replace(",", " ") + "."
        r = Report(reference=f"UBF-26-SEED{i:02d}", source="seed", category="scam", scam_type=row["kind"], language="en",
                   province=row["province"], town=town, station_id=st.id, incident_when=when.strftime("%d %B %Y"),
                   incident_date=when, description=desc, complainant_name=f"Demo complainant {i:02d}",
                   contact_channel="seed", status=rng.choice(STATUS_MIX), processing_status="ready",
                   amount_paid=float(row["amount"]), script_text=SCRIPTS.get(row["script"] or "", ""), is_seed=True,
                   created_at=created_at, updated_at=created_at,
                   facts={"scam_type": row["kind"], "accounts": [{"value": a, "bank": row["bank"]} for a in row["acc"]],
                          "phones": [show_phone(p) for p in row["phone"]], "domains": row["domain"],
                          "total_paid": float(row["amount"]), "seed": True,
                          "method": "Synthetic demo record (no evidence files)."})
        db.add(r)
        db.flush()
        r.statements = {"en": general_statement("en", reference=r.reference, name=r.complainant_name,
                                                 when=r.incident_when, place=f"{town}, {row['province']}", description=desc)}
        r.statement = r.statements["en"]
        db.add(StatusChange(report_id=r.id, from_status="", to_status=r.status, note="Synthetic seed record", at=created_at))
        r.timeline.append(TimelineEvent(order=0, at=created_at, when_text=r.incident_when, kind="incident",
                                        what="Incident (synthetic)", source="complainant"))
        items = [{"kind": "account", "value": a, "display": show_acc(a), "bank": row["bank"], "source": "seed"} for a in row["acc"]]
        items += [{"kind": "phone", "value": p, "display": show_phone(p), "source": "seed"} for p in row["phone"]]
        items += [{"kind": "domain", "value": d, "display": d, "source": "seed"} for d in row["domain"]]
        intel.save_identifiers(db, r, items)
        created.append(r)
    db.flush()
    for r in created:
        intel.compute_matches(db, r)
        intel.update_bank_alerts(db, r)
    audit.record(db, "seed.loaded", actor="setup", detail={"reports": len(created), "note": "synthetic demo data"})
    return len(created)
