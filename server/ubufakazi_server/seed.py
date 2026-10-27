"""Synthetic demo data: fictional stations, earlier reports and four fictional syndicates across all nine provinces.

Mirrors tools/make_seed.py (the MVP's seed) so both versions tell the same story, but here the raw
identifiers are hashed with the SERVER's secret HMAC key, never a key shipped to browsers.
Every person, account, phone number and website below is invented.
"""
from __future__ import annotations

import datetime as dt
import random

from sqlalchemy import or_
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

SEED_VERSION = 2

SYN_ACC = "1047228359"
SYN_PHONES = ["+27614402281", "+27795513060", "+27832207749"]
SYN_DOMAIN = "mzansi-careers-onboard.site"
S2_ACCS = ["5530187264", "5530199012"]
S2_PHONES = ["+27612245873", "+27725561190", "+27836604412"]
S2_DOMAIN = "swiftparcel-clearance.online"
S3_ACC = "7718203345"
S3_DOMAIN = "doublemyrands-invest.site"
S4_ACCS = ["6230441802", "6230457719"]            # "SECURE HOLD" mule accounts (bank impersonation / OTP fraud)
S4_PHONES = ["+27618804417", "+27673390218"]
STATUS_MIX = ["awaiting_review"] * 5 + ["under_review"] * 3 + ["more_info_required", "prepared_for_visit", "closed"]
SCRIPTS["bank_otp"] = ("UTB ALERT: A login to your Ubuntu Trust Bank app from a new device was detected. If this was not "
                       "you, call our fraud desk immediately. Your one-time PIN is never needed to cancel a payment but our "
                       "agent will help you move your funds to a secure holding account while we block the device.")
SCAM_TEXT["bank_impersonation"] = ("Someone called pretending to be my bank's fraud department and asked for my one-time PIN. "
                                   "Money then left my account without my permission.")
# Where each syndicate's victims were scammed: (date, town, amount). The town decides the station's jurisdiction.
S1_VICTIMS = [("2026-08-03", "Soweto", 9500), ("2026-08-19", "Umlazi", 12000), ("2026-08-30", "Pretoria", 4500),
              ("2026-09-02", "Sandton", 18500), ("2026-09-14", "Polokwane", 7000), ("2026-09-21", "Welkom", 3200),
              ("2026-09-29", "Khayelitsha", 22000), ("2026-10-08", "Gqeberha", 15000), ("2026-10-13", "Rustenburg", 2700)]
S2_VICTIMS = [("2026-07-04", "Kempton Park", 850), ("2026-07-11", "Bloemfontein", 1200), ("2026-07-19", "Pietermaritzburg", 650),
              ("2026-07-30", "Mbombela", 990), ("2026-08-08", "Germiston", 1450), ("2026-08-21", "Klerksdorp", 780),
              ("2026-09-03", "Bellville", 1100), ("2026-09-17", "Tzaneen", 560), ("2026-10-02", "East London", 1320),
              ("2026-10-11", "Kimberley", 940)]
S3_VICTIMS = [("2026-06-15", "Sandton", 12000), ("2026-07-02", "Stellenbosch", 25000), ("2026-08-12", "Richards Bay", 8500),
              ("2026-09-09", "Centurion", 40000), ("2026-09-26", "Upington", 6000), ("2026-10-06", "George", 18000)]
S4_VICTIMS = [("2026-09-05", "Vanderbijlpark", 12650), ("2026-09-12", "Mahikeng", 8900), ("2026-09-18", "Secunda", 15400),
              ("2026-09-24", "Thohoyandou", 6300), ("2026-10-01", "Newcastle", 21000), ("2026-10-07", "Bethlehem", 9800),
              ("2026-10-12", "Mdantsane", 4700), ("2026-10-15", "Paarl", 17250), ("2026-10-18", "Springbok", 5600),
              ("2026-10-20", "Randburg", 11300)]


def _rows() -> list[dict]:
    from .stations import DEMO_STATIONS, STATION_BY_CODE, jurisdiction_of
    rows = []

    def add(date, town, kind, amount, script, acc=(), phone=(), domain=(), bank="Ubuntu Trust Bank", category="scam"):
        prov = STATION_BY_CODE[jurisdiction_of(town)][1]
        rows.append({"date": date, "province": prov, "town": town, "kind": kind, "amount": amount, "script": script,
                     "acc": list(acc), "phone": list(phone), "domain": list(domain), "bank": bank, "category": category})

    for k, (d, t, a) in enumerate(S1_VICTIMS):          # fake-job syndicate, mule account at Ubuntu Trust Bank
        add(d, t, "job", a, "job_fee", [SYN_ACC], [SYN_PHONES[k % 3]], [SYN_DOMAIN] if k % 3 != 1 else [])
    for k, (d, t, a) in enumerate(S2_VICTIMS):          # courier-fee syndicate, two accounts at Fictional Bank B
        add(d, t, "parcel", a, "parcel_swift", [S2_ACCS[0] if k < 5 else S2_ACCS[1]], [S2_PHONES[k % 3]],
            [S2_DOMAIN] if k % 2 == 0 else [], bank="Fictional Bank B")
    for k, (d, t, a) in enumerate(S3_VICTIMS):          # crypto doubling syndicate, Fictional Bank C
        add(d, t, "investment", a, "invest_double", [S3_ACC], ["+2779" + str(3310450 + k * 1117)], [S3_DOMAIN],
            bank="Fictional Bank C")
    for k, (d, t, a) in enumerate(S4_VICTIMS):          # bank-impersonation / OTP syndicate, mules at Ubuntu Trust Bank
        add(d, t, "bank_impersonation", a, "bank_otp", [S4_ACCS[0] if k < 6 else S4_ACCS[1]], [S4_PHONES[k % 2]],
            bank="Ubuntu Trust Bank", category="banking_fraud")

    # Unlinked single reports across every demo station's jurisdiction: what a station normally sees.
    rng = random.Random(2026)
    ranges = {"job": (1500, 15000), "marketplace": (800, 8000), "romance": (5000, 60000), "investment": (2000, 50000),
              "parcel": (300, 3000), "sars": (1000, 9000), "bank_impersonation": (2500, 30000)}

    def acc():
        return "".join(str(rng.randint(0, 9)) for _ in range(10))

    def phone():
        return "+27" + rng.choice("678") + "".join(str(rng.randint(0, 9)) for _ in range(8))

    def date():
        m = rng.choice([6, 7, 8, 9, 10])
        return f"2026-{m:02d}-{rng.randint(1, 28) if m < 10 else rng.randint(1, 20):02d}"

    kinds = ["marketplace", "job", "romance", "investment", "sars", "bank_impersonation", "parcel"]
    for n, (code, _, _, towns) in enumerate(DEMO_STATIONS):
        for j in range(2 if n % 3 else 1):
            kind = kinds[(n + j) % len(kinds)]
            lo, hi = ranges[kind]
            add(date(), towns[(n + j) % len(towns)], kind, round(rng.randint(lo, hi), -1),
                "sars_refund" if kind == "sars" and j == 0 else None, [acc()], [phone()],
                bank=rng.choice(["Fictional Bank B", "Fictional Bank C", "Fictional Bank D", "Ubuntu Trust Bank"]),
                category="banking_fraud" if kind == "bank_impersonation" else "scam")
    rows.sort(key=lambda r: r["date"])
    return rows


def seed_stations(db: Session) -> dict[str, Station]:
    out = {}
    for code, name, prov, towns in DEMO_STATIONS:
        st = db.query(Station).filter_by(code=code).first()
        if not st:
            st = Station(code=code, name=name, province=prov, towns=towns)
            db.add(st)
        elif (st.name, st.province, list(st.towns or [])) != (name, prov, towns):
            st.name, st.province, st.towns = name, prov, list(towns)     # jurisdictions follow stations.py
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
        st = stations[route(row["province"], row["town"])]      # the jurisdiction where the victim was scammed
        town = row["town"]
        when = dt.date.fromisoformat(row["date"])
        created_at = dt.datetime.combine(when + dt.timedelta(days=rng.randint(0, 3)), dt.time(rng.randint(7, 19), rng.randint(0, 59)))
        desc = SCAM_TEXT[row["kind"]] + f" I paid R{row['amount']:,}".replace(",", " ") + "."
        r = Report(reference=f"UBF-26-SEED{i:03d}", source="seed", category=row["category"], scam_type=row["kind"], language="en",
                   province=row["province"], town=town, station_id=st.id, incident_when=when.strftime("%d %B %Y"),
                   incident_date=when, description=desc, complainant_name=f"Demo complainant {i:02d}",
                   contact_channel="seed", status=rng.choice(STATUS_MIX), processing_status="ready",
                   amount_paid=float(row["amount"]), script_text=SCRIPTS.get(row["script"] or "", ""), is_seed=True,
                   created_at=created_at, updated_at=created_at,
                   facts={"scam_type": row["kind"], "accounts": [{"value": a, "bank": row["bank"]} for a in row["acc"]],
                          "phones": [show_phone(p) for p in row["phone"]], "domains": row["domain"],
                          "total_paid": float(row["amount"]), "seed": True, "seed_version": SEED_VERSION,
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


def refresh_seed(db: Session) -> int:
    """Load the synthetic data, replacing an older version of it. Real (non-seed) reports are never touched."""
    from .models import (BankAlert, BankDelivery, Consent, Identifier, IntelMatch, Note, ProcessingJob,
                         StationHandover, UtbCase, UtbEvent)
    seeds = db.query(Report).filter_by(is_seed=True).all()
    if seeds and all((r.facts or {}).get("seed_version") == SEED_VERSION for r in seeds):
        return 0
    ids = [r.id for r in seeds]
    if ids:
        db.query(IntelMatch).filter(or_(IntelMatch.report_a.in_(ids), IntelMatch.report_b.in_(ids))).delete(synchronize_session=False)
        for model in (Identifier, TimelineEvent, StatusChange, Note, Consent, ProcessingJob, StationHandover):
            db.query(model).filter(model.report_id.in_(ids)).delete(synchronize_session=False)
        db.query(Report).filter(Report.id.in_(ids)).delete(synchronize_session=False)
        db.flush()
        db.expire_all()
    n = seed_reports(db)
    live = {h for (h,) in db.query(Identifier.hmac).filter(Identifier.kind == "account").all()}
    for al in db.query(BankAlert).all():                 # alerts about accounts no report names any more
        if al.account_hmac not in live:
            for c in db.query(UtbCase).filter_by(source_alert_id=al.id).all():
                db.query(UtbEvent).filter_by(case_id=c.id).delete(synchronize_session=False)
                db.delete(c)
            db.query(BankDelivery).filter_by(alert_id=al.id).delete(synchronize_session=False)
            db.delete(al)
    db.flush()
    for r in db.query(Report).filter_by(is_seed=False).all():   # re-link real reports to the new synthetic network
        intel.compute_matches(db, r)
        intel.update_bank_alerts(db, r)
    if ids:
        audit.record(db, "seed.replaced", actor="setup", detail={"removed": len(ids), "added": n, "version": SEED_VERSION})
    return n
