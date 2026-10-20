"""Builds the Ubufakazi test pack: 70 fictional scam cases for judges to test the site.

50 cases in English and 5 each in isiZulu, isiXhosa, Afrikaans and Sesotho, covering every
scam type. Each case folder has a WhatsApp-style chat export (.txt) and proof-of-payment
PDF(s) from the fictional "DemoBank", stamped SAMPLE. The language is in every folder name,
file name and PDF title.

Run:  python3 tools/make_test_pack.py            (cases + zip, guide without results)
      python3 tools/make_test_pack.py --guide    (rebuild the guide using test-results.json)
Output: site/test-pack/
"""
import json
import pathlib
import random
import sys
import zipfile

from reportlab.lib.colors import Color, HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "test-pack"
CASES_DIR = OUT / "cases"
rng = random.Random(70)

LANGS = {"EN": "English", "ZU": "isiZulu", "XH": "isiXhosa", "AF": "Afrikaans", "ST": "Sesotho"}
TYPE_LABEL = {"job": "Fake job offer", "marketplace": "Online seller / Marketplace", "romance": "Romance",
              "investment": "Investment / crypto", "parcel": "Courier / parcel fee", "sars": "Fake SARS refund",
              "other": "Something else"}

# The three fictional syndicates already in the site's demo network (site/assets/seed.js).
S1_ACC, S2_ACC, S3_ACC = "1047 2283 59", "5530 1990 12", "7718 2033 45"

VICTIMS = ["Lindiwe", "Sibusiso", "Ayanda", "Thabo", "Nomvula", "Kagiso", "Zanele", "Pieter", "Lerato", "Mpho",
           "Naledi", "Bongani", "Refilwe", "Anele", "Johan", "Busisiwe", "Tshepo", "Khanyisile", "Sizwe", "Palesa",
           "Ntombi", "Lebo", "Andile", "Precious", "Karabo", "Themba", "Nandi", "Vusi", "Marelize", "Siyabonga"]
SURNAMES = ["Dlamini", "Nkosi", "Mokoena", "Botha", "Khumalo", "Ndlovu", "Mahlangu", "Mthembu", "Naidoo", "Molefe",
            "Van Wyk", "Zulu", "Sithole", "Mabaso", "Pillay", "Masilela", "Radebe", "Coetzee", "Mabena", "Tau"]
ITEMS = ["PlayStation 5", "iPhone 13", "double-door fridge", "washing machine", "L-shaped couch", "gaming laptop",
         "set of 17-inch mag wheels", "baby pram", "Samsung TV 55-inch", "bicycle"]
CITIES = ["Durban", "Polokwane", "Gqeberha", "Bloemfontein", "Pretoria", "Rustenburg", "East London", "Kimberley"]
POSITIONS = ["Admin Clerk", "Stock Controller", "Receptionist", "Cashier", "Packer", "Driver"]
ROM_ALIASES = ["Daniel Morgan", "James Carter", "Michael Adams", "Lisa Brown", "Kevin Walsh", "Sarah Collins"]


def acc():
    return f"{rng.randint(1, 9)}{rng.randint(100, 999)} {rng.randint(1000, 9999)} {rng.randint(10, 99)}"


def phone():
    p = rng.choice(["06", "07", "08"]) + str(rng.randint(1, 9))
    return f"{p} {rng.randint(100, 999)} {rng.randint(1000, 9999)}"


def rand_amt(lo, hi, step=50):
    return rng.randrange(lo, hi, step)


def R(n, style=None):
    style = style or rng.choice(["space", "space", "comma", "plain"])
    s = f"{n:,}"
    return "R" + (s.replace(",", " ") if style == "space" else s if style == "comma" else str(n))


def domain(kind):
    a = rng.choice(["quick", "secure", "smart", "my", "best", "fast", "go", "true"])
    b = {"investment": rng.choice(["fx-profits", "crypto-gains", "wealth-club", "trade-pro"]),
         "parcel": rng.choice(["parcel-track", "courier-redeliver", "delivery-fees"]),
         "sars": rng.choice(["refund-verify", "taxrefund-claim", "efund-portal"])}[kind]
    return f"{a}{b}-{rng.randint(10, 99)}.{rng.choice(['site', 'online', 'xyz', 'top'])}"


# ---------------------------------------------------------------- English templates
def t_job_s1(c):
    c.update(a1=rand_amt(1500, 2600), a2=rand_amt(1200, 2000), sal=rng.choice([12500, 14500, 16000, 13800]))
    lines = [
        ("S", f"Good morning! Your CV was shortlisted for the {c['pos']} position at Mzansi Retail Group. Salary {R(c['sal'])} per month. Are you still interested?"),
        ("V", "Yes I am, thank you"),
        ("S", f"Congratulations, you have been selected. To secure your position you must pay a once-off registration and uniform fee of {R(c['a1'])}. Positions are limited so please pay today."),
        ("S", f"Bank: DemoBank\nAcc name: {c['accname']}\nAcc no: {c['acc']}"),
        ("S", f"Complete the onboarding form here: https://mzansi-careers-onboard.site/apply\nIf WhatsApp is slow call me on {c['phone']}"),
        ("V", f"I have paid {R(c['a1'])} now. Sending proof of payment"),
        ("S", f"Received. There is also a training fee of {R(c['a2'])} which must be paid before Monday or you lose the position."),
        ("V", f"Ok I sent the {R(c['a2'])} as well"),
        ("V", "Hello? When do I start?"),
        ("V", "Your number is not going through"),
    ]
    if c.get("no_link"):
        lines[4] = ("S", f"Fill in the onboarding form I will send you. If WhatsApp is slow call me on {c['phone']}")
    return lines, [c["a1"], c["a2"]]


def t_job_a(c):
    c.update(a1=rand_amt(450, 1500), sal=rng.choice([6500, 7800, 9200]))
    return [
        ("S", f"Hi {c['v']}, I'm {c['alias']} from the recruitment office. We got your CV from the job portal. We have a General Worker post paying {R(c['sal'])} per month."),
        ("V", "Good day, yes I'm interested"),
        ("S", f"Before we place you, you must pay {R(c['a1'])} for police clearance and medicals. Pay today please, interviews start tomorrow."),
        ("S", f"Pay to DemoBank account {c['acc']}. Reference: your name"),
        ("V", f"I have paid {R(c['a1'])}. Here is the proof of payment"),
        ("S", "Thank you. HR will call you to confirm your start date"),
        ("V", "Nobody called me"),
        ("V", "Hello?? You are not answering"),
    ], [c["a1"]]


def t_job_b(c):
    c.update(a1=rand_amt(350, 900), a2=rand_amt(1500, 3500), sal=rng.choice([3500, 4000, 4500]))
    return [
        ("S", f"CONGRATULATIONS! You qualify for the 2027 learnership programme with a monthly stipend of {R(c['sal'])}. Only {R(c['a1'])} admin fee to secure your spot. Spaces are limited, pay today."),
        ("V", "Is this real? How do I pay?"),
        ("S", f"Pay into DemoBank acc {c['acc']} and send POP to this number. Or call {c['phone']}"),
        ("V", f"I paid {R(c['a1'])} just now"),
        ("S", f"Received. Now pay {R(c['a2'])} for your training laptop deposit before Friday"),
        ("V", f"I sent the {R(c['a2'])}"),
        ("V", "When does the learnership start?"),
        ("V", "Your number is not going through"),
    ], [c["a1"], c["a2"]]


def t_mk_a(c):
    c.update(a1=rand_amt(1200, 8000))
    return [
        ("V", f"Hi, I saw your Facebook Marketplace ad. Is the {c['item']} still available?"),
        ("S", f"Yes still available. {R(c['a1'])} including courier. I'm in {c['city']}"),
        ("V", "Can I collect?"),
        ("S", f"No sorry, only courier. Pay {R(c['a1'])} and I send today. Many people are asking so pay now to secure it"),
        ("S", f"DemoBank\nAcc no: {c['acc']}\nName: {c['accname']}\nWhatsApp me on {c['phone']} if there is a problem"),
        ("V", f"Ok I have paid {R(c['a1'])}, sending POP"),
        ("S", "Received thanks. Will send the tracking number tomorrow"),
        ("V", "Hi, where is the tracking number?"),
        ("V", "Hello? Did you block me?"),
    ], [c["a1"]]


def t_mk_b(c):
    c.update(a1=rand_amt(500, 1500), a2=rand_amt(1500, 6000))
    return [
        ("V", f"Hello, I saw your ad for the {c['item']} on Marketplace. Still for sale?"),
        ("S", f"Yes. {R(c['a1'] + c['a2'])}. Pay a deposit of {R(c['a1'])} to hold it, someone else wants it today"),
        ("S", f"DemoBank account {c['acc']}. My number is {c['phone']}"),
        ("V", f"I've paid the {R(c['a1'])} deposit"),
        ("S", f"Thanks. Pay the balance of {R(c['a2'])} and the courier collects tomorrow"),
        ("V", f"Sent the {R(c['a2'])}"),
        ("V", "The courier never came. Please answer"),
    ], [c["a1"], c["a2"]]


def t_rom_a(c):
    c.update(a1=rand_amt(2500, 9000), a2=rand_amt(4000, 15000))
    return [
        ("S", f"Hello dear, I'm {c['alias']}. I saw your profile and I like your smile"),
        ("V", "Hi, thank you"),
        ("S", "I'm an engineer working on an oil rig. I miss you so much my love"),
        ("S", f"My darling, I sent you a gift but customs is holding it. Please help me pay {R(c['a1'])} and I will pay you back when I land"),
        ("S", f"Pay to DemoBank account {c['acc']}. Call me on {c['phone']}"),
        ("V", f"I have sent {R(c['a1'])} my love"),
        ("S", f"Thank you baby. They now want {R(c['a2'])} for insurance, please send today"),
        ("V", f"I sent {R(c['a2'])} too"),
        ("V", "Why are you not answering my calls?"),
    ], [c["a1"], c["a2"]]


def t_rom_b(c):
    c.update(a1=rand_amt(3000, 12000), a2=rand_amt(2000, 8000))
    return [
        ("S", "Good evening sweetheart, how was your day?"),
        ("V", "Long day but good"),
        ("S", f"I love you. I need a small favour, my bank card is blocked overseas and I need {R(c['a1'])} for my flight ticket to come see you. Call me on {c['phone']}"),
        ("S", f"Use DemoBank acc {c['acc']}, it's my friend's account"),
        ("V", f"Ok I have paid {R(c['a1'])}"),
        ("S", f"You are the best. Just {R(c['a2'])} more for the visa fee"),
        ("V", f"I have transferred {R(c['a2'])}"),
        ("V", "You blocked me??"),
    ], [c["a1"], c["a2"]]


def t_inv_s3(c):
    c.update(a1=rand_amt(2000, 10000), a2=rand_amt(1500, 5000))
    return [
        ("S", "Good day, invest today and receive ten times your money in 7 days with our crypto trading platform. Returns are guaranteed and our account manager will guide you. Register on the link below and send proof of payment."),
        ("S", "https://doublemyrands-invest.site/register"),
        ("V", "How much is the minimum?"),
        ("S", f"Minimum is {R(c['a1'])}. Pay to DemoBank account {c['acc']} and you get {R(c['a1'] * 10)} next week"),
        ("V", f"I have paid {R(c['a1'])}"),
        ("S", f"Your profit is ready! Pay {R(c['a2'])} withdrawal tax to release it"),
        ("V", f"I sent {R(c['a2'])}"),
        ("V", "I still don't have my money. Please answer"),
    ], [c["a1"], c["a2"]]


def t_inv_a(c):
    c.update(a1=rand_amt(2000, 20000), a2=rand_amt(1000, 6000))
    c["dom"] = domain("investment")
    return [
        ("S", f"Hi {c['v']}, I'm {c['alias']}, a forex trader. I made {R(c['a1'] * 3)} profit for my clients this week. Want to join?"),
        ("V", "How does it work?"),
        ("S", f"You invest {R(c['a1'])} and I trade for you. Guaranteed profit in 48 hours. Join our platform at https://{c['dom']}/join"),
        ("S", f"Pay to DemoBank acc {c['acc']}"),
        ("V", f"Done, I paid {R(c['a1'])}"),
        ("S", f"Your account shows {R(c['a1'] * 3)} profit! Pay {R(c['a2'])} activation fee to withdraw"),
        ("V", f"I have paid {R(c['a2'])}"),
        ("V", "The website is gone and you are not answering"),
    ], [c["a1"], c["a2"]]


def t_par_s2(c):
    c.update(a1=rand_amt(350, 1200), a2=rand_amt(200, 600))
    return [
        ("S", "SwiftParcel: your parcel is held at our depot because customs duty is unpaid. Pay the clearance fee within 24 hours or the parcel will be returned. Pay securely on our clearance page and send proof of payment."),
        ("S", f"Clearance page: https://swiftparcel-clearance.online/pay\nFee: {R(c['a1'])}\nDemoBank acc {c['acc']}"),
        ("V", f"I have paid {R(c['a1'])}. When will it be delivered?"),
        ("S", f"Thank you. A redelivery fee of {R(c['a2'])} is now due today"),
        ("V", f"I sent {R(c['a2'])}"),
        ("V", "No parcel arrived. Please answer"),
    ], [c["a1"], c["a2"]]


def t_par_a(c):
    c.update(a1=rand_amt(150, 900))
    c["dom"] = domain("parcel")
    return [
        ("S", f"Hello, this is the courier. Your package could not be delivered because the address is incomplete. Pay {R(c['a1'])} redelivery fee at https://{c['dom']}/track"),
        ("V", "What package?"),
        ("S", f"Your online order. Pay today or it is returned to the sender. You can also pay to DemoBank account {c['acc']}"),
        ("V", f"Ok I have paid {R(c['a1'])}"),
        ("S", "Received. Delivery tomorrow"),
        ("V", "Nothing was delivered. Your number is not going through"),
    ], [c["a1"]]


def t_sars_a(c):
    c.update(a1=rand_amt(300, 1500), refund=rand_amt(3000, 12000))
    c["dom"] = domain("sars")
    return [
        ("S", f"SARS: You are due a tax refund of {R(c['refund'])}. Please verify your banking details using the secure link below within 24 hours to receive your refund."),
        ("S", f"https://{c['dom']}/verify"),
        ("V", "I submitted my details. When do I get the refund?"),
        ("S", f"To release the refund pay an admin fee of {R(c['a1'])} to DemoBank account {c['acc']}"),
        ("V", f"I have paid {R(c['a1'])}"),
        ("V", "No refund came. Please answer"),
    ], [c["a1"]]


def t_sars_b(c):
    c.update(a1=rand_amt(1500, 6000), a2=rand_amt(500, 2000))
    return [
        ("S", f"Good day, I am calling from SARS. You have an outstanding penalty of {R(c['a1'])}. Pay today or a warrant will be issued for your arrest."),
        ("S", f"Pay to DemoBank acc {c['acc']} and send proof. Call me on {c['phone']}"),
        ("V", f"I paid {R(c['a1'])}. Please cancel the warrant"),
        ("S", f"Received. There is also an interest amount of {R(c['a2'])}"),
        ("V", f"I sent {R(c['a2'])}"),
        ("V", "SARS says they never called me. You are not answering"),
    ], [c["a1"], c["a2"]]


def t_loan(c):
    c.update(a1=rand_amt(500, 2000), a2=rand_amt(400, 1500), loan=rng.choice([15000, 20000, 30000]))
    return [
        ("S", f"Good news! Your loan of {R(c['loan'])} has been approved. Pay the insurance fee of {R(c['a1'])} today to release the money."),
        ("S", f"DemoBank account {c['acc']}. Questions? {c['phone']}"),
        ("V", f"I have paid {R(c['a1'])}"),
        ("S", f"Thank you. There is one more legal fee of {R(c['a2'])}"),
        ("V", f"I sent {R(c['a2'])}"),
        ("V", "I never got the loan. You are not answering"),
    ], [c["a1"], c["a2"]]


def t_family(c):
    c.update(a1=rand_amt(1000, 4000), a2=rand_amt(800, 2500))
    return [
        ("S", f"Hi Mom, it's me {c['child']}. This is my new number, my phone fell in water"),
        ("V", "Hello my child"),
        ("S", f"I need {R(c['a1'])} urgently for my rent, please send now. I will pay you back tomorrow"),
        ("S", f"Pay to my friend's account: DemoBank {c['acc']}"),
        ("V", f"I have sent {R(c['a1'])}"),
        ("S", f"Thank you Mom. Please send {R(c['a2'])} more"),
        ("V", f"I sent {R(c['a2'])}. I called your old number and you say it's not you!"),
    ], [c["a1"], c["a2"]]


def t_lottery(c):
    c.update(a1=rand_amt(500, 1500), a2=rand_amt(1000, 3000), prize=rng.choice([150000, 250000, 500000]))
    return [
        ("S", f"Congratulations! Your number won {R(c['prize'])} in the Lucky Draw. Pay {R(c['a1'])} release fee to claim your prize today"),
        ("S", f"DemoBank acc {c['acc']}. Call {c['phone']}"),
        ("V", f"I paid {R(c['a1'])}"),
        ("S", f"Pay {R(c['a2'])} tax to release the prize"),
        ("V", f"I sent the {R(c['a2'])}"),
        ("V", "No prize money. You blocked me"),
    ], [c["a1"], c["a2"]]


# ---------------------------------------------------------------- other languages (fictional, draft translations)
def zu_job(c):
    c.update(a1=rand_amt(1500, 2600), sal=14500)
    return [("S", f"Sawubona! I-CV yakho ikhethiwe esikhundleni se-{c['pos']} e-Mzansi Retail Group. Umholo u-{R(c['sal'])} ngenyanga. Usanesifiso?"),
            ("V", "Yebo ngiyafisa, ngiyabonga"),
            ("S", f"Halala, ukhethiwe. Kufanele ukhokhe imali yokubhalisa neyunifomu engu-{R(c['a1'])} namhlanje ukuze uthole lesi sikhundla."),
            ("S", f"Bank: DemoBank\nAkhawunti: {S1_ACC}\nIgama: MZ Placements"),
            ("S", f"Ngishayele ku-{c['phone']} uma kunenkinga"),
            ("V", f"Sengikhokhile u-{R(c['a1'])}. Nansi i-proof of payment"),
            ("V", "Ngiqala nini?"),
            ("V", "Sawubona? Awuphenduli")], [c["a1"]]


def zu_mk(c):
    c.update(a1=rand_amt(1000, 5000))
    return [("V", f"Sawubona, ngibona i-{c['item']} oyithengisayo ku-Marketplace. Isekhona?"),
            ("S", f"Yebo isekhona, {R(c['a1'])}. Ngizoyithumela nge-courier."),
            ("V", "Ngingeze ngiyilande?"),
            ("S", f"Cha, khokha imali engu-{R(c['a1'])} kuqala. Abantu abaningi bayayifuna."),
            ("S", f"DemoBank account {c['acc']}\nWhatsApp {c['phone']}"),
            ("V", f"Sengikhokhile u-{R(c['a1'])}"),
            ("S", "Ngiyibonile. Ngizokuthumelela i-tracking number kusasa"),
            ("V", "Ayikho i-tracking number. Awuphenduli?")], [c["a1"]]


def zu_par(c):
    c.update(a1=rand_amt(200, 900), a2=rand_amt(150, 500)); c["dom"] = domain("parcel")
    return [("S", f"Sawubona, iphasela lakho libanjwe e-customs. Khokha imali engu-{R(c['a1'])} namhlanje ngaphandle kwalokho lizobuyiselwa."),
            ("S", f"Khokhela ku-DemoBank account {c['acc']}. Landela iphasela lakho ku-https://{c['dom']}/track"),
            ("V", f"Ngikhokhile u-{R(c['a1'])}"),
            ("S", f"Kukhona enye imali engu-{R(c['a2'])} ye-delivery"),
            ("V", f"Sengikhokhile u-{R(c['a2'])}. Ngicela iphasela lami"),
            ("V", "Alikho iphasela. Awuphenduli")], [c["a1"], c["a2"]]


def zu_sars(c):
    c.update(a1=rand_amt(300, 1500), refund=rand_amt(3000, 12000)); c["dom"] = domain("sars")
    return [("S", f"SARS: Unemali ebuyiselwayo engu-{R(c['refund'])}. Ukuze uyithole khokha imali yokuphatha engu-{R(c['a1'])} namhlanje."),
            ("S", f"Akhawunti: DemoBank {c['acc']}. Qinisekisa ku-https://{c['dom']}/verify"),
            ("V", f"Sengikhokhile u-{R(c['a1'])}. Ngizoyithola nini imali yami?"),
            ("S", "Ngemva kwamahora angu-48"),
            ("V", "Akukho mali efikile. Awuphenduli")], [c["a1"]]


def zu_family(c):
    c.update(a1=rand_amt(1000, 4000), a2=rand_amt(800, 2500))
    return [("S", f"Mama, yimi {c['child']}. Le yinombolo yami entsha, ifoni yami iwele emanzini."),
            ("V", "Sawubona mntanami"),
            ("S", f"Ngicela ungithumelele u-{R(c['a1'])} manje, kuphuthumile. Ngizokubuyisela kusasa."),
            ("S", f"Khokhela ku-DemoBank akhawunti {c['acc']}, eyomngane wami"),
            ("V", f"Sengikhokhile u-{R(c['a1'])} mntanami"),
            ("S", f"Ngiyabonga mama. Ngicela u-{R(c['a2'])} futhi"),
            ("V", f"Sengikhokhile u-{R(c['a2'])}. Ngishayele inombolo yakho endala, uthi akuyena wena!")], [c["a1"], c["a2"]]


def xh_job(c):
    c.update(a1=rand_amt(1500, 2600), sal=16000)
    return [("S", f"Molo! I-CV yakho ikhethiwe kwisikhundla se-{c['pos']} e-Mzansi Retail Group. Umvuzo yi-{R(c['sal'])} ngenyanga. Usanomdla?"),
            ("V", "Ewe ndinomdla, enkosi"),
            ("S", f"Siyakuvuyisana, ukhethiwe. Kufuneka uhlawule imali yobhaliso neyunifomu eyi-{R(c['a1'])} namhlanje."),
            ("S", f"Hlawulela kwi-DemoBank account {S1_ACC}, igama MZ Placements"),
            ("S", f"Nditsalele ku-{c['phone']}"),
            ("V", f"Ndihlawulile i-{R(c['a1'])}. Nantsi i-proof of payment"),
            ("V", "Ndiqala nini?"),
            ("V", "Molo? Awuphenduli")], [c["a1"]]


def xh_mk(c):
    c.update(a1=rand_amt(1000, 5000))
    return [("V", f"Molo, ndibona i-{c['item']} oyithengisayo ku-Marketplace. Isekhona?"),
            ("S", f"Ewe isekhona, {R(c['a1'])}. Ndiza kuyithumela nge-courier."),
            ("S", f"Hlawula imali eyi-{R(c['a1'])} kuqala. Abantu abaninzi bayayifuna."),
            ("S", f"DemoBank account {c['acc']}\nWhatsApp {c['phone']}"),
            ("V", f"Ndihlawulile i-{R(c['a1'])}"),
            ("S", "Ndiyibonile. Ndiza kukuthumelela i-tracking number ngomso"),
            ("V", "Akukho tracking number. Awuphenduli?")], [c["a1"]]


def xh_par(c):
    c.update(a1=rand_amt(200, 900), a2=rand_amt(150, 500)); c["dom"] = domain("parcel")
    return [("S", f"Molo, ipasile yakho ibanjwe kwi-customs. Hlawula imali eyi-{R(c['a1'])} namhlanje okanye iza kubuyiselwa."),
            ("S", f"Hlawulela kwi-DemoBank account {c['acc']}. Landela ipasile yakho ku-https://{c['dom']}/track"),
            ("V", f"Ndihlawulile i-{R(c['a1'])}"),
            ("S", f"Kukho enye imali eyi-{R(c['a2'])} ye-delivery"),
            ("V", f"Ndihlawulile i-{R(c['a2'])}. Ndicela ipasile yam"),
            ("V", "Akukho pasile. Awuphenduli")], [c["a1"], c["a2"]]


def xh_sars(c):
    c.update(a1=rand_amt(300, 1500), refund=rand_amt(3000, 12000)); c["dom"] = domain("sars")
    return [("S", f"SARS: Unemali ebuyiselwayo eyi-{R(c['refund'])}. Ukuze uyifumane hlawula imali yolawulo eyi-{R(c['a1'])} namhlanje."),
            ("S", f"Akhawunti: DemoBank {c['acc']}. Qinisekisa ku-https://{c['dom']}/verify"),
            ("V", f"Ndihlawulile i-{R(c['a1'])}. Ndiza kuyifumana nini imali yam?"),
            ("S", "Emva kweeyure ezingama-48"),
            ("V", "Akukho mali ifikileyo. Awuphenduli")], [c["a1"]]


def xh_rom(c):
    c.update(a1=rand_amt(2500, 9000), a2=rand_amt(3000, 10000))
    return [("S", f"Molo sithandwa, ndingu-{c['alias']}, ndisebenza kwi-oil rig elwandle."),
            ("V", "Molo, enkosi"),
            ("S", f"Ndiyakuthanda. Ndidinga i-{R(c['a1'])} ukuhlawula i-customs yepakethe yam, ndiza kukubuyisela."),
            ("S", f"DemoBank account {c['acc']}. Nditsalele ku-{c['phone']}"),
            ("V", f"Ndihlawulile i-{R(c['a1'])} sithandwa"),
            ("S", f"Enkosi. Ndidinga i-{R(c['a2'])} ngoku"),
            ("V", f"Ndihlawulile i-{R(c['a2'])}. Kutheni awuphenduli iminxeba yam?")], [c["a1"], c["a2"]]


def af_job(c):
    c.update(a1=rand_amt(1500, 2600), sal=13800)
    return [("S", f"Goeiemôre! Jou CV is gekies vir die pos van {c['pos']} by Mzansi Retail Group. Salaris {R(c['sal'])} per maand. Stel jy nog belang?"),
            ("V", "Ja, baie dankie!"),
            ("S", f"Baie geluk, jy is gekies. Jy moet vandag 'n eenmalige registrasie- en uniformfooi van {R(c['a1'])} betaal om jou pos te verseker."),
            ("S", f"Bank: DemoBank\nRekening: {S1_ACC}\nNaam: MZ Placements"),
            ("S", f"Bel my op {c['phone']}"),
            ("V", f"Ek het die {R(c['a1'])} betaal. Hier is die bewys van betaling"),
            ("V", "Wanneer begin ek?"),
            ("V", "Hallo? Hoekom antwoord jy nie?")], [c["a1"]]


def af_mk(c):
    c.update(a1=rand_amt(1000, 5000))
    return [("V", f"Hallo, is die {c['item']} op Marketplace nog beskikbaar?"),
            ("S", f"Ja nog beskikbaar, {R(c['a1'])}. Ek stuur met koerier."),
            ("V", "Kan ek dit kom haal?"),
            ("S", f"Nee, betaal eers {R(c['a1'])}. Baie mense vra daarvoor."),
            ("S", f"DemoBank rekening {c['acc']}\nWhatsApp {c['phone']}"),
            ("V", f"Ek het {R(c['a1'])} betaal"),
            ("S", "Ontvang. Ek stuur môre die opsporingsnommer"),
            ("V", "Geen opsporingsnommer nie. Het jy my geblokkeer?")], [c["a1"]]


def af_par(c):
    c.update(a1=rand_amt(200, 900), a2=rand_amt(150, 500)); c["dom"] = domain("parcel")
    return [("S", f"Hallo, jou pakkie word by doeane gehou. Betaal vandag {R(c['a1'])} of dit word teruggestuur."),
            ("S", f"Betaal in DemoBank rekening {c['acc']}. Volg jou pakkie op https://{c['dom']}/track"),
            ("V", f"Ek het {R(c['a1'])} betaal"),
            ("S", f"Daar is nog 'n afleweringsfooi van {R(c['a2'])}"),
            ("V", f"Ek het die {R(c['a2'])} ook betaal. Waar is my pakkie?"),
            ("V", "Geen pakkie nie. Jy antwoord nie")], [c["a1"], c["a2"]]


def af_sars(c):
    c.update(a1=rand_amt(300, 1500), refund=rand_amt(3000, 12000)); c["dom"] = domain("sars")
    return [("S", f"SARS: Jy het 'n terugbetaling van {R(c['refund'])}. Betaal vandag 'n administrasiefooi van {R(c['a1'])} om dit vry te stel."),
            ("S", f"Rekening: DemoBank {c['acc']}. Bevestig op https://{c['dom']}/verify"),
            ("V", f"Ek het {R(c['a1'])} betaal. Wanneer kry ek my geld?"),
            ("S", "Binne 48 uur"),
            ("V", "Geen geld nie. Jy antwoord nie")], [c["a1"]]


def af_loan(c):
    c.update(a1=rand_amt(500, 2000), a2=rand_amt(400, 1500), loan=20000)
    return [("S", f"Goeie nuus! Jou lening van {R(c['loan'])} is goedgekeur. Betaal net die versekeringsfooi van {R(c['a1'])} vandag om die geld vry te stel."),
            ("S", f"DemoBank rekening {c['acc']}. Bel {c['phone']}"),
            ("V", f"Ek het die {R(c['a1'])} betaal"),
            ("S", f"Dankie. Daar is nog 'n fooi van {R(c['a2'])}"),
            ("V", f"Ek het {R(c['a2'])} betaal"),
            ("V", "Ek het nooit die lening ontvang nie. Jy antwoord nie")], [c["a1"], c["a2"]]


def st_job(c):
    c.update(a1=rand_amt(1500, 2600), sal=12500)
    return [("S", f"Dumela! CV ya hao e kgethilwe bakeng sa mosebetsi wa {c['pos']} ho Mzansi Retail Group. Moputso ke {R(c['sal'])} ka kgwedi. O sa ntse o thahasella?"),
            ("V", "E, ke a leboha!"),
            ("S", f"Halala, o kgethilwe. O tlameha ho lefa tefo ya ngodiso le yunifomo ya {R(c['a1'])} kajeno."),
            ("S", f"Bank: DemoBank\nAccount: {S1_ACC}\nLebitso: MZ Placements"),
            ("S", f"Ntletsetse ho {c['phone']}"),
            ("V", f"Ke lefile {R(c['a1'])}. Proof of payment ke ena"),
            ("V", "Ke qala neng?"),
            ("V", "Dumela? Ha o arabe")], [c["a1"]]


def st_mk(c):
    c.update(a1=rand_amt(1000, 5000))
    return [("V", f"Dumela, {c['item']} eo o e rekisang ho Marketplace e sa ntse e le teng?"),
            ("S", f"E, e sa le teng, {R(c['a1'])}. Ke tla e romela ka courier."),
            ("S", f"Lefa {R(c['a1'])} pele. Batho ba bangata ba a e batla."),
            ("S", f"DemoBank account {c['acc']}\nWhatsApp {c['phone']}"),
            ("V", f"Ke lefile {R(c['a1'])}"),
            ("S", "Ke e bone. Ke tla o romella tracking number hosane"),
            ("V", "Ha ho tracking number. Ha o arabe?")], [c["a1"]]


def st_par(c):
    c.update(a1=rand_amt(200, 900), a2=rand_amt(150, 500)); c["dom"] = domain("parcel")
    return [("S", f"Dumela, phasela ya hao e tshwerwe ho customs. Lefa {R(c['a1'])} kajeno ho seng jwalo e tla kgutlisetswa."),
            ("S", f"Lefa ho DemoBank account {c['acc']}. Latela phasela ya hao ho https://{c['dom']}/track"),
            ("V", f"Ke lefile {R(c['a1'])}"),
            ("S", f"Ho na le tefo e nngwe ya delivery ya {R(c['a2'])}"),
            ("V", f"Ke lefile {R(c['a2'])}. Phasela ya ka e kae?"),
            ("V", "Ha ho phasela. Ha o arabe")], [c["a1"], c["a2"]]


def st_sars(c):
    c.update(a1=rand_amt(300, 1500), refund=rand_amt(3000, 12000)); c["dom"] = domain("sars")
    return [("S", f"SARS: O na le tjhelete e busetswang ya {R(c['refund'])}. Lefa tefo ya tsamaiso ya {R(c['a1'])} kajeno hore o e fumane."),
            ("S", f"Account: DemoBank {c['acc']}. Netefatsa ho https://{c['dom']}/verify"),
            ("V", f"Ke lefile {R(c['a1'])}. Ke tla fumana tjhelete ya ka neng?"),
            ("S", "Ka mora dihora tse 48"),
            ("V", "Ha ho tjhelete e fihlileng. Ha o arabe")], [c["a1"]]


def st_rom(c):
    c.update(a1=rand_amt(2500, 9000), a2=rand_amt(3000, 10000))
    return [("S", f"Dumela moratuwa, ke {c['alias']}, ke sebetsa sekepeng sa oli."),
            ("V", "Dumela, ke a leboha"),
            ("S", f"Ke a o rata. Ke hloka {R(c['a1'])} ho lefa customs ya phuthelwana ya ka, ke tla o busetsa."),
            ("S", f"DemoBank account {c['acc']}. Ntletsetse ho {c['phone']}"),
            ("V", f"Ke lefile {R(c['a1'])} moratuwa"),
            ("S", f"Ke a leboha. Ke hloka {R(c['a2'])} hape"),
            ("V", f"Ke lefile {R(c['a2'])}. Hobaneng o sa arabe mehala ya ka? Ha o arabe")], [c["a1"], c["a2"]]


# ---------------------------------------------------------------- case plan
SCAMMER_NAMES = {
    "job": ["Thandi (HR Recruiter)", "Recruitment Office", "HR Nomsa", "Learnership Desk", "Mr Dube HR"],
    "marketplace": ["Kagiso Deals", "Sipho Sells", "Bargain Ben", "Marketplace Seller", "Zinhle Store"],
    "romance": ROM_ALIASES, "investment": ["Crypto Wealth Club", "FX Mentor Tumi", "Trader Lwazi", "Wealth Manager"],
    "parcel": ["SwiftParcel", "Courier Desk", "Delivery Notice"], "sars": ["SARS Refunds", "SARS Official", "Tax Office"],
    "other": ["Quick Loans", "Lucky Draw SA", "New Number"],
}
plan = []  # (lang, type, template, extra)
M_ACC, M_PHONES = acc(), [phone(), phone(), phone()]
R_PHONE = phone()
EN = [
    ("job", t_job_s1, {"acc": S1_ACC, "note": "s1"}), ("job", t_job_s1, {"note": "s1-new-acc"}),
    ("job", t_job_s1, {"note": "s1-script-only", "no_link": True}),
    ("job", t_job_a, {}), ("job", t_job_a, {}), ("job", t_job_a, {}),
    ("job", t_job_b, {}), ("job", t_job_b, {}), ("job", t_job_b, {}),
    ("marketplace", t_mk_a, {"acc": M_ACC, "phone": M_PHONES[0], "note": "cluster-m"}),
    ("marketplace", t_mk_b, {"acc": M_ACC, "phone": M_PHONES[1], "note": "cluster-m"}),
    ("marketplace", t_mk_a, {"acc": M_ACC, "phone": M_PHONES[2], "note": "cluster-m"}),
    ("marketplace", t_mk_a, {}), ("marketplace", t_mk_a, {}), ("marketplace", t_mk_a, {}),
    ("marketplace", t_mk_b, {}), ("marketplace", t_mk_b, {}), ("marketplace", t_mk_b, {}),
    ("romance", t_rom_a, {"phone": R_PHONE, "note": "cluster-r"}), ("romance", t_rom_b, {"phone": R_PHONE, "note": "cluster-r"}),
    ("romance", t_rom_a, {}), ("romance", t_rom_a, {}), ("romance", t_rom_b, {}), ("romance", t_rom_b, {}),
    ("investment", t_inv_s3, {"acc": S3_ACC, "note": "s3"}), ("investment", t_inv_s3, {"note": "s3-new-acc"}),
    ("investment", t_inv_a, {}), ("investment", t_inv_a, {}), ("investment", t_inv_a, {}), ("investment", t_inv_a, {}),
    ("investment", t_inv_a, {}),
    ("parcel", t_par_s2, {"acc": S2_ACC, "note": "s2"}), ("parcel", t_par_s2, {"acc": S2_ACC, "note": "s2"}),
    ("parcel", t_par_s2, {"note": "s2-new-acc"}),
    ("parcel", t_par_a, {}), ("parcel", t_par_a, {}), ("parcel", t_par_a, {}), ("parcel", t_par_a, {}), ("parcel", t_par_a, {}),
    ("sars", t_sars_a, {}), ("sars", t_sars_a, {}), ("sars", t_sars_a, {}),
    ("sars", t_sars_b, {}), ("sars", t_sars_b, {}), ("sars", t_sars_b, {}),
    ("other", t_loan, {}), ("other", t_loan, {}), ("other", t_family, {}), ("other", t_family, {}), ("other", t_lottery, {}),
]
assert len(EN) == 50
OTHERS = {
    "ZU": [("job", zu_job, {"acc": S1_ACC, "note": "s1"}), ("marketplace", zu_mk, {}), ("parcel", zu_par, {}), ("sars", zu_sars, {}), ("other", zu_family, {})],
    "XH": [("job", xh_job, {"acc": S1_ACC, "note": "s1"}), ("marketplace", xh_mk, {}), ("parcel", xh_par, {}), ("sars", xh_sars, {}), ("romance", xh_rom, {})],
    "AF": [("job", af_job, {"acc": S1_ACC, "note": "s1"}), ("marketplace", af_mk, {}), ("parcel", af_par, {}), ("sars", af_sars, {}), ("other", af_loan, {})],
    "ST": [("job", st_job, {"acc": S1_ACC, "note": "s1"}), ("marketplace", st_mk, {}), ("parcel", st_par, {}), ("sars", st_sars, {}), ("romance", st_rom, {})],
}
for t in EN:
    plan.append(("EN",) + t)
for lg, items in OTHERS.items():
    for t in items:
        plan.append((lg,) + t)

NAVY, INK, GREY, LINE, RED = HexColor("#1D3B6E"), HexColor("#16223A"), HexColor("#5B6B84"), HexColor("#D9DEE7"), HexColor("#B3261E")


def pop_pdf(path, cid, lang, p):
    W, H = A4
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setTitle(f"Test case {cid} ({lang}): DemoBank proof of payment (SAMPLE)")
    c.setFillColor(NAVY); c.rect(0, H - 110, W, 110, fill=1, stroke=0)
    c.setFillColor(HexColor("#FFFFFF")); c.setFont("Helvetica-Bold", 30); c.drawString(50, H - 62, "DemoBank")
    c.setFont("Helvetica", 11); c.drawString(50, H - 84, "Fictional bank for demonstrations")
    c.setFont("Helvetica-Bold", 11); c.drawRightString(W - 50, H - 62, f"TEST CASE {cid}")
    c.drawRightString(W - 50, H - 80, f"LANGUAGE: {lang.upper()}")
    c.setFillColor(INK); c.setFont("Helvetica-Bold", 22); c.drawString(50, H - 160, "Proof of payment")
    c.setFont("Helvetica", 10.5); c.setFillColor(GREY); c.drawString(50, H - 180, "Immediate EFT  |  Generated by DemoBank App")
    rows = [("Date and time", p["date"]), ("Amount", p["amount"]), ("Paid from", p["payer"]),
            ("Beneficiary", p["name"]), ("Beneficiary account", p["acc"]), ("Bank", "DemoBank"),
            ("Reference", p["ref"]), ("Transaction ID", p["txn"]), ("Status", "Successful")]
    y = H - 235
    for k, v in rows:
        c.setFillColor(GREY); c.setFont("Helvetica", 12); c.drawString(50, y, k)
        c.setFillColor(INK); c.setFont("Helvetica-Bold", 13); c.drawString(240, y, v)
        c.setStrokeColor(LINE); c.setLineWidth(0.8); c.line(50, y - 12, W - 50, y - 12)
        y -= 40
    c.saveState(); c.translate(W / 2, H / 2 - 40); c.rotate(32)
    c.setFillColor(Color(0.84, 0.19, 0.12, alpha=0.18)); c.setFont("Helvetica-Bold", 120)
    c.drawCentredString(0, 0, "SAMPLE"); c.restoreState()
    c.setFillColor(RED); c.setFont("Helvetica-Bold", 12)
    c.drawString(50, 70, "DEMO DOCUMENT  |  NOT A REAL PAYMENT  |  FICTIONAL BANK")
    c.setFillColor(GREY); c.setFont("Helvetica", 9)
    c.drawString(50, 52, f"Ubufakazi test pack by Team CyberThreat (HackSecure 2026)  |  Case {cid}  |  {lang}")
    c.save()


def build_cases():
    cases = []
    counters = {k: 0 for k in LANGS}
    for lg, kind, fn, extra in plan:
        counters[lg] += 1
        cid = f"{lg}-{counters[lg]:02d}"
        v = rng.choice(VICTIMS); sur = rng.choice(SURNAMES)
        c = {"v": v, "alias": rng.choice(ROM_ALIASES) if kind == "romance" else rng.choice(SCAMMER_NAMES[kind]),
             "acc": acc(), "phone": phone(), "pos": rng.choice(POSITIONS), "item": rng.choice(ITEMS),
             "city": rng.choice(CITIES), "child": rng.choice(VICTIMS), "accname": rng.choice(["MZ Placements", "K Mthembu", "T Ndaba", "B Moloi", "Star Traders"])}
        c.update(extra)
        lines, paid = fn(c)
        scam_name = "Thandi (HR Recruiter)" if extra.get("note", "").startswith("s1") else ("SwiftParcel" if extra.get("note", "").startswith("s2") else c["alias"])
        if kind == "other" and fn in (t_family, zu_family):
            scam_name = "New Number"
        # timestamps
        day = rng.randint(1, 16); hh, mm_ = rng.randint(8, 18), rng.randint(0, 50)
        ios = rng.random() < 0.4
        out, pay_times = [], []
        for who, text in lines:
            mm_ += rng.randint(1, 25)
            if mm_ >= 60:
                hh += mm_ // 60; mm_ %= 60
            if hh >= 22:
                day += 1; hh = 8
            sender = scam_name if who == "S" else v
            stamp_d = f"{day:02d}/10/2026"
            if ios:
                out.append(f"[{stamp_d}, {hh:02d}:{mm_:02d}:{rng.randint(10, 59)}] {sender}: {text}")
            else:
                out.append(f"{stamp_d}, {hh:02d}:{mm_:02d} - {sender}: {text}")
            if who == "V" and any(R(a, s) in text for a in paid for s in ("space", "comma", "plain")):
                pay_times.append(f"{day:02d} Oct 2026, {hh:02d}:{max(0, mm_ - 2):02d}")
        lang = LANGS[lg]
        folder = CASES_DIR / f"{cid}_{lang.upper()}_{kind}"
        folder.mkdir(parents=True, exist_ok=True)
        chat_name = f"{cid}_{lang.upper()}_whatsapp-chat.txt"
        (folder / chat_name).write_text("\n".join(out) + "\n", encoding="utf-8")
        pops = []
        for k, a in enumerate(paid):
            pname = f"{cid}_{lang.upper()}_proof-of-payment-{k + 1}.pdf"
            pop_pdf(folder / pname, cid, lang, {
                "date": pay_times[k] if k < len(pay_times) else f"{day:02d} Oct 2026",
                "amount": R(a, "space") + ",00", "payer": f"{v[0]} {sur.upper()}", "name": c["accname"],
                "acc": c["acc"], "ref": v.upper()[:10], "txn": f"DB-{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}"})
            pops.append(pname)
        cases.append({"id": cid, "lang": lang, "type": kind, "type_label": TYPE_LABEL[kind], "victim": f"{v} {sur}",
                      "folder": folder.name, "chat": chat_name, "pops": pops, "paid_total": sum(paid),
                      "note": extra.get("note", "")})
    return cases


EXPECT = {
    "s1": "Links to the fake job syndicate: victim #7, 6 earlier reports, R84 000 (same bank account).",
    "s1-new-acc": "Links to the fake job syndicate through the website link and message script, even with a new account.",
    "s1-script-only": "Links to the fake job syndicate through the copied message script only.",
    "s2": "Links to the fake courier syndicate 'SwiftParcel' (same account, link and script).",
    "s2-new-acc": "Links to 'SwiftParcel' through the link and script, even with a new account.",
    "s3": "Links to the fake crypto syndicate (same account, link and script).",
    "s3-new-acc": "Links to the fake crypto syndicate through the link and script.",
    "cluster-m": "Linked set: build one of EN-10, EN-11, EN-12, click Add my report, then build another: they link.",
    "cluster-r": "Linked pair: build EN-19, Add my report, then build EN-20: same phone number, so they link.",
}


def guide_pdf(cases, results):
    path = OUT / "READ-ME-FIRST_test-pack-guide.pdf"
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=14 * mm, rightMargin=14 * mm, topMargin=14 * mm, bottomMargin=14 * mm,
                            title="Ubufakazi test pack: guide", author="Team CyberThreat")
    h1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=20, leading=24, textColor=INK, spaceAfter=6)
    h2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=12.5, leading=16, textColor=INK, spaceBefore=10, spaceAfter=4)
    body = ParagraphStyle("b", fontName="Helvetica", fontSize=9.5, leading=13, textColor=INK)
    small = ParagraphStyle("s", fontName="Helvetica", fontSize=7.8, leading=10, textColor=INK)
    smallb = ParagraphStyle("sb", parent=small, fontName="Helvetica-Bold")
    story = [Paragraph("Ubufakazi test pack: 70 fictional scam cases", h1),
             Paragraph("For judges and testers. 50 cases in <b>English</b>, 5 each in <b>isiZulu</b>, <b>isiXhosa</b>, "
                       "<b>Afrikaans</b> and <b>Sesotho</b>, covering every scam type. Everything is fictional: "
                       "\"DemoBank\" is not a real bank and every document is stamped SAMPLE. Non-English chats are "
                       "draft translations.", body),
             Paragraph("How to test a case", h2),
             Paragraph("1. Open ubufakazi.netlify.app and click <b>Build a case file</b>.<br/>"
                       "2. Click <b>Upload chat export (.txt)</b> and choose the case's chat file.<br/>"
                       "3. Click <b>Add files</b> and choose the case's proof-of-payment PDF(s).<br/>"
                       "4. Optional: set <b>Statement language</b> to the case's language.<br/>"
                       "5. Click <b>Build my case file</b> and compare with the table below.<br/>"
                       "Use <b>Reset demo data</b> (bottom of the site) to clear reports you added.", body),
             Paragraph("Cases", h2)]
    rows = [[Paragraph(x, smallb) for x in ["Case", "Language", "Scam type", "Paid", "What the site shows (tested)"]]]
    for c in cases:
        r = results.get(c["id"], {})
        shown = r.get("summary", "")
        exp = EXPECT.get(c["note"], "")
        text = (shown + ("<br/><i>" + exp + "</i>" if exp else "")) if shown else (exp or "No earlier reports match.")
        rows.append([Paragraph(f"<b>{c['id']}</b>", small), Paragraph(c["lang"], small), Paragraph(c["type_label"], small),
                     Paragraph(R(c["paid_total"], "space"), small), Paragraph(text, small)])
    t = Table(rows, colWidths=[16 * mm, 20 * mm, 30 * mm, 18 * mm, None], repeatRows=1)
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
                           ("LINEBELOW", (0, 1), (-1, -1), 0.3, LINE), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                           ("TOPPADDING", (0, 0), (-1, -1), 4),
                           ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#FFFFFF"), HexColor("#F6F8FA")])]))
    story += [t, Spacer(1, 8),
              Paragraph("Ubufakazi by Team CyberThreat: Thabang Manyama, Amani Tondi, Shaun Matlou | HackSecure 2026", small)]
    doc.build(story)


def make_zip(cases):
    zpath = OUT / "ubufakazi-test-pack.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(OUT / "READ-ME-FIRST_test-pack-guide.pdf", "ubufakazi-test-pack/READ-ME-FIRST_test-pack-guide.pdf")
        for c in cases:
            for f in [c["chat"], *c["pops"]]:
                z.write(CASES_DIR / c["folder"] / f, f"ubufakazi-test-pack/{c['folder']}/{f}")
    return zpath


if __name__ == "__main__":
    if "--guide" in sys.argv:
        cases = json.loads((OUT / "cases.json").read_text())
        results = json.loads((ROOT / "tools" / "test-results.json").read_text())
    else:
        cases = build_cases()
        (OUT / "cases.json").write_text(json.dumps(cases, indent=1))
        results = {}
    guide_pdf(cases, results)
    z = make_zip(cases)
    print(f"{len(cases)} cases, zip {z.stat().st_size // 1024} KB")
