"""Builds site/assets/seed.js: the demo "network" of earlier scam reports.

Every identifier (bank account, phone, link domain, email) is stored ONLY as a
keyed hash (HMAC-SHA256). All data here is fictional, made up for the demo.

Run:  python3 tools/make_seed.py
"""
import hashlib
import hmac
import json
import pathlib
import random

# Demo key. In production this key lives only on the server (env variable).
KEY = b"ubufakazi-demo-key-2026"


def h(kind, value):
    return hmac.new(KEY, f"{kind}:{value}".encode(), hashlib.sha256).hexdigest()


def ids(acc=(), phone=(), domain=(), email=()):
    return {
        "acc": [h("acc", a) for a in acc],
        "phone": [h("phone", p) for p in phone],
        "domain": [h("domain", d) for d in domain],
        "email": [h("email", e) for e in email],
    }


SCRIPTS = {
    "job_fee": {
        "label": "Fake recruitment: 'registration and uniform fee'",
        "text": (
            "Good morning! Your CV was shortlisted for the Admin Clerk position at "
            "Mzansi Retail Group. Salary R12 000 per month. Are you still interested? "
            "Congratulations, you have been selected. To secure your position you must "
            "pay a once-off registration and uniform fee of R1 500. Positions are limited "
            "so please pay today. Complete the onboarding form here. There is also a "
            "training fee of R1 200 which must be paid before Monday or you lose the position."
        ),
    },
    "parcel_customs": {
        "label": "Fake courier: 'customs clearance fee'",
        "text": (
            "Hello, your parcel is being held at customs. To release your parcel you must "
            "pay the clearance fee today otherwise it will be returned to the sender. "
            "Use the link below to track and pay."
        ),
    },
    "sars_refund": {
        "label": "Fake SARS refund",
        "text": (
            "SARS: You are due a tax refund. Please verify your banking details using the "
            "secure link below within 24 hours to receive your refund."
        ),
    },
}

# The demo syndicate: one mule account, three throwaway phone numbers.
SYN_ACC = "1047228359"
SYN_PHONES = ["+27614402281", "+27795513060", "+27832207749"]
SYN_DOMAIN = "mzansi-careers-onboard.site"

reports = [
    ("2026-08-03", "Gauteng", "job", 9500, "job_fee", ids([SYN_ACC], [SYN_PHONES[0]], [SYN_DOMAIN])),
    ("2026-08-19", "KwaZulu-Natal", "job", 12000, "job_fee", ids([SYN_ACC], [SYN_PHONES[0]])),
    ("2026-09-02", "Gauteng", "job", 18500, "job_fee", ids([SYN_ACC], [SYN_PHONES[1]], [SYN_DOMAIN])),
    ("2026-09-14", "Limpopo", "job", 7000, "job_fee", ids([SYN_ACC], [SYN_PHONES[1]])),
    ("2026-09-29", "Western Cape", "job", 22000, "job_fee", ids([SYN_ACC], [SYN_PHONES[2]], [SYN_DOMAIN])),
    ("2026-10-08", "Eastern Cape", "job", 15000, "job_fee", ids([SYN_ACC], [SYN_PHONES[2]], [SYN_DOMAIN])),
]
assert sum(r[3] for r in reports) == 84000

# Two more fictional syndicates, so the network looks like the real world.
SCRIPTS["parcel_swift"] = {
    "label": "Fake courier 'SwiftParcel' customs fee",
    "text": ("SwiftParcel: your parcel is held at our depot because customs duty is unpaid. Pay the clearance fee "
             "within 24 hours or the parcel will be returned. Pay securely on our clearance page and send proof of payment."),
}
SCRIPTS["invest_double"] = {
    "label": "Fake crypto investment 'double your money'",
    "text": ("Good day, invest today and receive ten times your money in 7 days with our crypto trading platform. "
             "Returns are guaranteed and our account manager will guide you. Register on the link below and send proof of payment."),
}
S2_ACCS = ["5530187264", "5530199012"]  # switched to a second mule account halfway
S2_PHONES = ["+27612245873", "+27725561190", "+27836604412"]
S2_DOMAIN = "swiftparcel-clearance.online"
s2 = [("2026-07-04", "Gauteng", 850), ("2026-07-11", "Free State", 1200), ("2026-07-19", "KwaZulu-Natal", 650),
      ("2026-07-30", "Mpumalanga", 990), ("2026-08-08", "Gauteng", 1450), ("2026-08-21", "North West", 780),
      ("2026-09-03", "Western Cape", 1100), ("2026-09-17", "Limpopo", 560), ("2026-10-02", "Eastern Cape", 1320)]
for k, (d, prov, amt) in enumerate(s2):
    acc = S2_ACCS[0] if k < 5 else S2_ACCS[1]
    reports.append((d, prov, "parcel", amt, "parcel_swift", ids([acc], [S2_PHONES[k % 3]], [S2_DOMAIN] if k % 2 == 0 else [])))

S3_ACC = "7718203345"
S3_DOMAIN = "doublemyrands-invest.site"
s3 = [("2026-06-15", "Gauteng", 12000), ("2026-07-02", "Western Cape", 25000), ("2026-08-12", "KwaZulu-Natal", 8500),
      ("2026-09-09", "Gauteng", 40000), ("2026-09-26", "Northern Cape", 6000)]
for k, (d, prov, amt) in enumerate(s3):
    reports.append((d, prov, "investment", amt, "invest_double", ids([S3_ACC], ["+2779" + str(3310450 + k * 1117)], [S3_DOMAIN])))

# Unrelated background reports (random fictional identifiers).
rng = random.Random(2026)
provinces = ["Gauteng", "KwaZulu-Natal", "Western Cape", "Eastern Cape", "Limpopo",
             "Mpumalanga", "North West", "Free State", "Northern Cape"]
weights = [26, 19, 12, 10, 9, 8, 7, 5, 4]
ranges = {"job": (1500, 15000), "marketplace": (800, 8000), "romance": (5000, 60000), "investment": (2000, 50000),
          "parcel": (300, 3000), "sars": (1000, 9000), "other": (500, 12000)}


def rand_acc():
    return "".join(str(rng.randint(0, 9)) for _ in range(10))


def rand_phone():
    return "+27" + rng.choice("678") + "".join(str(rng.randint(0, 9)) for _ in range(8))


def rand_date():
    month = rng.choice([6, 7, 8, 9, 10])
    return f"2026-{month:02d}-{rng.randint(1, 28) if month < 10 else rng.randint(1, 15):02d}"


market_acc, romance_acc = rand_acc(), rand_acc()  # two small 2-report clusters
for tag, kind, acc in [("pair", "marketplace", market_acc), ("pair", "marketplace", market_acc),
                       ("pair", "romance", romance_acc), ("pair", "romance", romance_acc)]:
    lo, hi = ranges[kind]
    reports.append((rand_date(), rng.choices(provinces, weights)[0], kind, round(rng.randint(lo, hi), -1), None,
                    ids([acc], [rand_phone()])))
kinds = ["job"] * 9 + ["marketplace"] * 13 + ["romance"] * 8 + ["investment"] * 7 + ["parcel"] * 6 + ["sars"] * 7 + ["other"] * 6
for kind in kinds:
    lo, hi = ranges[kind]
    script = "sars_refund" if kind == "sars" and rng.random() < 0.5 else None
    reports.append((rand_date(), rng.choices(provinces, weights)[0], kind, round(rng.randint(lo, hi), -1), script,
                    ids([rand_acc()], [rand_phone()])))

reports.sort(key=lambda r: r[0])
out = {
    "version": 1,
    "note": "Fictional demo data. Identifiers are HMAC-SHA256 hashes only.",
    "scripts": SCRIPTS,
    "reports": [
        {"id": f"R-{i + 1:04d}", "date": d, "province": p, "scamType": t, "amount": a,
         "script": s, "ids": x}
        for i, (d, p, t, a, s, x) in enumerate(reports)
    ],
}
path = pathlib.Path(__file__).resolve().parent.parent / "site" / "assets" / "seed.js"
path.write_text("/* Generated by tools/make_seed.py: fictional demo data, hashes only. */\n"
                "window.UBF_SEED = " + json.dumps(out, indent=1) + ";\n")
print(f"wrote {path} with {len(out['reports'])} reports")
