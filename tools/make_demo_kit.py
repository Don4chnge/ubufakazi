"""Builds the Ubufakazi demo evidence kit: fictional chats and proofs of payment
that anyone can upload to the site to test it.

Everything is fictional. "Ubuntu Trust Bank" is not a real bank, and every document is
stamped SAMPLE / NOT A REAL PAYMENT.

Run:  python3 tools/make_demo_kit.py
Output: site/demo-kit/  (files + ubufakazi-demo-evidence-kit.zip)
"""
import pathlib
import zipfile

from reportlab.lib.colors import HexColor, Color
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

OUT = pathlib.Path(__file__).resolve().parent.parent / "site" / "demo-kit"
OUT.mkdir(parents=True, exist_ok=True)

CHATS = {
    "case1-lerato-whatsapp-chat.txt": """12/10/2026, 09:14 - Thandi (HR Recruiter): Good morning! Your CV was shortlisted for the Admin Clerk position at Mzansi Retail Group. Salary R14 500 per month. Are you still interested?
12/10/2026, 09:20 - Lerato: Yes I am! Thank you so much
12/10/2026, 09:22 - Thandi (HR Recruiter): Congratulations, you have been selected. To secure your position you must pay a once-off registration and uniform fee of R1 850. Positions are limited so please pay today.
12/10/2026, 09:23 - Thandi (HR Recruiter): Bank: Ubuntu Trust Bank
Acc name: MZ Placements
Acc no: 1047 2283 59
Reference: your name
12/10/2026, 09:25 - Thandi (HR Recruiter): Complete the onboarding form here: https://mzansi-careers-onboard.site/apply
If WhatsApp is slow call me on 071 482 0937
12/10/2026, 09:41 - Lerato: Ok I have paid R1 850 now. Sending proof of payment
12/10/2026, 09:41 - Lerato: case1-lerato-proof-of-payment-1.pdf (file attached)
12/10/2026, 10:05 - Thandi (HR Recruiter): Received. There is also a training fee of R1 650 which must be paid before Monday or you lose the position.
12/10/2026, 10:30 - Lerato: Ok I sent the R1 650 as well
12/10/2026, 10:30 - Lerato: case1-lerato-proof-of-payment-2.pdf (file attached)
12/10/2026, 11:02 - Lerato: Hello? When do I start?
13/10/2026, 08:15 - Lerato: Please answer me
13/10/2026, 08:16 - Lerato: Your number is not going through
""",
    "case2-sipho-whatsapp-chat.txt": """[15/10/2026, 13:02:11] Nomsa (Recruitment): Good morning! Your CV was shortlisted for the Stock Controller position at Mzansi Retail Group. Salary R16 000 per month. Are you still interested?
[15/10/2026, 13:10:45] Sipho: Yes please
[15/10/2026, 13:12:02] Nomsa (Recruitment): Congratulations, you have been selected. To secure your position you must pay a once-off registration and uniform fee of R2 100. Positions are limited so please pay today.
[15/10/2026, 13:12:40] Nomsa (Recruitment): Pay to Ubuntu Trust Bank account 2290 1184 76, account name NS Staffing. Then complete the onboarding form here: mzansi-careers-onboard.site/apply
[15/10/2026, 13:13:05] Nomsa (Recruitment): You can also call me on 068 330 5521
[15/10/2026, 13:40:19] Sipho: I have paid the R2 100. Here is the proof of payment
[15/10/2026, 14:05:51] Sipho: When is my first day?
[16/10/2026, 09:30:02] Sipho: Hello?? Please answer
""",
    "case3-naledi-whatsapp-chat.txt": """14/10/2026, 18:02 - Naledi: Hi, I saw your Facebook Marketplace ad. Is the PlayStation 5 still available?
14/10/2026, 18:05 - Kagiso Deals: Yes still available. R4 200 including courier. I'm in Durban
14/10/2026, 18:07 - Naledi: Can I collect?
14/10/2026, 18:09 - Kagiso Deals: No sorry, only courier. Pay R4 200 and I send today. Many people are asking so pay now to secure it
14/10/2026, 18:10 - Kagiso Deals: Ubuntu Trust Bank
Acc no: 3318 5520 41
Name: K Mthembu
WhatsApp me on 073 905 1184 if there is a problem
14/10/2026, 18:31 - Naledi: Ok I have paid R4 200, sending POP
14/10/2026, 18:40 - Kagiso Deals: Received thanks. Will send the tracking number tomorrow
15/10/2026, 12:15 - Naledi: Hi, where is the tracking number?
16/10/2026, 09:02 - Naledi: Hello? Did you block me?
""",
}

POPS = [
    ("case1-lerato-proof-of-payment-1.pdf", dict(date="12 Oct 2026, 09:39", amount="R1 850,00", name="MZ Placements", acc="1047 2283 59", ref="LERATO M", payer="L MOKOENA", txn="DB-7K2Q-1185")),
    ("case1-lerato-proof-of-payment-2.pdf", dict(date="12 Oct 2026, 10:27", amount="R1 650,00", name="MZ Placements", acc="1047 2283 59", ref="LERATO M", payer="L MOKOENA", txn="DB-7K2Q-1240")),
    ("case2-sipho-proof-of-payment.pdf", dict(date="15 Oct 2026, 13:38", amount="R2 100,00", name="NS Staffing", acc="2290 1184 76", ref="SIPHO N", payer="S NDLOVU", txn="DB-9M4T-0417")),
    ("case3-naledi-proof-of-payment.pdf", dict(date="14 Oct 2026, 18:29", amount="R4 200,00", name="K Mthembu", acc="3318 5520 41", ref="PS5", payer="N DLAMINI", txn="DB-3H8W-2290")),
]

NAVY = HexColor("#1D3B6E")
INK = HexColor("#16223A")
GREY = HexColor("#5B6B84")
LINE = HexColor("#D9DEE7")
RED = HexColor("#B3261E")


def pop_pdf(path, p):
    W, H = A4
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setTitle("Ubuntu Trust Bank proof of payment (SAMPLE)")
    c.setAuthor("Ubufakazi demo kit")
    c.setFillColor(NAVY); c.rect(0, H - 110, W, 110, fill=1, stroke=0)
    c.setFillColor(HexColor("#FFFFFF")); c.setFont("Helvetica-Bold", 30); c.drawString(50, H - 62, "Ubuntu Trust Bank")
    c.setFont("Helvetica", 11); c.drawString(50, H - 84, "Fictional bank for demonstrations")
    c.setFillColor(INK); c.setFont("Helvetica-Bold", 22); c.drawString(50, H - 160, "Proof of payment")
    c.setFont("Helvetica", 10.5); c.setFillColor(GREY); c.drawString(50, H - 180, "Immediate EFT  |  Generated by Ubuntu Trust Bank App")
    rows = [("Date and time", p["date"]), ("Amount", p["amount"]), ("Paid from", p["payer"]),
            ("Beneficiary", p["name"]), ("Beneficiary account", p["acc"]), ("Bank", "Ubuntu Trust Bank"),
            ("Reference", p["ref"]), ("Transaction ID", p["txn"]), ("Status", "Successful")]
    y = H - 235
    for k, v in rows:
        c.setFillColor(GREY); c.setFont("Helvetica", 12); c.drawString(50, y, k)
        c.setFillColor(INK); c.setFont("Helvetica-Bold", 13); c.drawString(240, y, v)
        c.setStrokeColor(LINE); c.setLineWidth(0.8); c.line(50, y - 12, W - 50, y - 12)
        y -= 40
    # watermark
    c.saveState()
    c.translate(W / 2, H / 2 - 40); c.rotate(32)
    c.setFillColor(Color(0.84, 0.19, 0.12, alpha=0.18)); c.setFont("Helvetica-Bold", 120)
    c.drawCentredString(0, 0, "SAMPLE")
    c.restoreState()
    c.setFillColor(RED); c.setFont("Helvetica-Bold", 12)
    c.drawString(50, 70, "DEMO DOCUMENT  |  NOT A REAL PAYMENT  |  FICTIONAL BANK")
    c.setFillColor(GREY); c.setFont("Helvetica", 9)
    c.drawString(50, 52, "Part of the Ubufakazi demo evidence kit by Team CyberThreat (HackSecure 2026).")
    c.save()


def guide_pdf(path):
    W, H = A4
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setTitle("Ubufakazi demo evidence kit: how to use")
    c.setFillColor(HexColor("#060A11")); c.rect(0, H - 130, W, 130, fill=1, stroke=0)
    c.setFillColor(HexColor("#5CF2D6")); c.setFont("Courier-Bold", 9); c.drawString(50, H - 45, "UBUFAKAZI  |  DEMO EVIDENCE KIT")
    c.setFillColor(HexColor("#F4F8FB")); c.setFont("Helvetica-Bold", 26); c.drawString(50, H - 82, "Try it with real files")
    c.setFillColor(HexColor("#B7C4D3")); c.setFont("Helvetica", 11)
    c.drawString(50, H - 104, "Fictional scam evidence you can upload to ubufakazi.netlify.app")
    y = H - 165

    def text(s, size=10.5, bold=False, color=INK, gap=15, x=50):
        nonlocal y
        c.setFillColor(color); c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        c.drawString(x, y, s); y -= gap

    text("How to use", 14, True, gap=20)
    for s in ["1. Open the site and go to \"Tell us what happened\".",
              "2. Click \"Upload chat export (.txt)\" and choose a case's chat file.",
              "3. Click \"Add files\" and choose that case's proof-of-payment PDF(s).",
              "4. Click \"Build my case file\"."]:
        text(s)
    y -= 10
    cases = [
        ("Case 1  |  Lerato  |  Fake job offer", ["case1-lerato-whatsapp-chat.txt", "case1-lerato-proof-of-payment-1.pdf, -2.pdf",
                                                   "case1-scam-website-screenshot.png, case1-recruiter-profile-screenshot.png",
                                                   "case1-bank-confirmation-letter.pdf (the scammer's \"proof we are legit\")"],
         "Expect: \"You are victim #7\". 6 earlier reports, R84 000. Linked by the same bank account,", "even though the phone number is new."),
        ("Case 2  |  Sipho  |  Same scammers, new number and new account", ["case2-sipho-whatsapp-chat.txt", "case2-sipho-proof-of-payment.pdf"],
         "Expect: still linked to the same group, through the website link and the copied message", "script. This is the Scam Fingerprint: dumping a number or account doesn't hide them."),
        ("Case 3  |  Naledi  |  Marketplace scam, a different scammer", ["case3-naledi-whatsapp-chat.txt", "case3-naledi-proof-of-payment.pdf"],
         "Expect: \"No earlier reports match this scammer yet\". Click \"Add my report\" so the next", "victim of this scammer gets linked to Naledi."),
    ]
    for title, files, e1, e2 in cases:
        text(title, 12.5, True, gap=17)
        for f in files:
            text("-  " + f, 10, color=GREY, gap=13, x=62)
        y -= 3
        text(e1, 10.5, gap=14)
        text(e2, 10.5, gap=24)
    text("Tip", 12.5, True, gap=17)
    text("Do case 1, click \"Add my report\", then do case 2: it becomes victim #8.", gap=14)
    text("Use \"Reset demo data\" at the bottom of the site to start again at #7.", gap=14)
    text("The scammer's fake website and profile are on the site: ubufakazi.netlify.app/scam-demo/", gap=26)
    c.setFillColor(HexColor("#FBEDE7")); c.rect(45, y - 30, W - 90, 44, fill=1, stroke=0)
    c.setFillColor(RED); c.setFont("Helvetica-Bold", 10.5)
    c.drawString(55, y - 2, "Everything in this kit is fictional.")
    c.setFont("Helvetica", 10)
    c.drawString(55, y - 18, "\"Ubuntu Trust Bank\" is not a real bank. All people, numbers and payments are made up for the demo.")
    c.setFillColor(GREY); c.setFont("Helvetica", 9)
    c.drawString(50, 40, "Ubufakazi by Team CyberThreat: Thabang Manyama, Amani Tondi, Shaun Matlou  |  HackSecure 2026")
    c.save()


def bank_letter_pdf(path):
    W, H = A4
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setTitle("Ubuntu Trust Bank confirmation of banking details (SAMPLE)")
    c.setFillColor(NAVY); c.rect(0, H - 110, W, 110, fill=1, stroke=0)
    c.setFillColor(HexColor("#FFFFFF")); c.setFont("Helvetica-Bold", 30); c.drawString(50, H - 62, "Ubuntu Trust Bank")
    c.setFont("Helvetica", 11); c.drawString(50, H - 84, "Fictional bank for demonstrations")
    c.setFillColor(INK); c.setFont("Helvetica-Bold", 20); c.drawString(50, H - 160, "Confirmation of banking details")
    c.setFont("Helvetica", 11); c.setFillColor(GREY); c.drawString(50, H - 180, "To whom it may concern")
    rows = [("Account holder", "MZ Placements"), ("Account number", "1047 2283 59"), ("Account type", "Business cheque"),
            ("Branch", "Demo Central"), ("Date opened", "22 July 2026"), ("Date issued", "1 October 2026")]
    y = H - 230
    for k, v in rows:
        c.setFillColor(GREY); c.setFont("Helvetica", 12); c.drawString(50, y, k)
        c.setFillColor(INK); c.setFont("Helvetica-Bold", 13); c.drawString(240, y, v)
        c.setStrokeColor(LINE); c.setLineWidth(0.8); c.line(50, y - 12, W - 50, y - 12)
        y -= 38
    c.setFillColor(INK); c.setFont("Helvetica", 11)
    c.drawString(50, y - 10, "We confirm that the above account is held with Ubuntu Trust Bank and is in good standing.")
    c.drawString(50, y - 60, "______________________")
    c.drawString(50, y - 76, "Branch Manager (fictional)")
    c.saveState(); c.translate(W / 2, H / 2 - 40); c.rotate(32)
    c.setFillColor(Color(0.84, 0.19, 0.12, alpha=0.18)); c.setFont("Helvetica-Bold", 120)
    c.drawCentredString(0, 0, "SAMPLE"); c.restoreState()
    c.setFillColor(RED); c.setFont("Helvetica-Bold", 11)
    c.drawString(50, 90, "RED FLAGS: account opened 3 months ago, not in the company's name, letter sent by a")
    c.drawString(50, 75, "recruiter on WhatsApp. Real employers never ask for fees.")
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, 52, "DEMO DOCUMENT  |  FICTIONAL BANK  |  Ubufakazi demo kit, Team CyberThreat")
    c.save()


def screenshots():
    """Screenshots of the fictional scam pages, as a victim would capture them."""
    try:
        import subprocess, sys, time
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright not installed: skipping screenshots")
        return []
    site = OUT.parent
    srv = subprocess.Popen([sys.executable, "-m", "http.server", "8799", "--bind", "127.0.0.1"], cwd=site,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    shots = [("scam-demo/mzansi-careers/", "case1-scam-website-screenshot.png"),
             ("scam-demo/recruiter-profile/", "case1-recruiter-profile-screenshot.png")]
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(viewport={"width": 430, "height": 900}, device_scale_factor=2)
            for url, name in shots:
                pg.goto("http://127.0.0.1:8799/" + url); pg.wait_for_load_state("networkidle")
                pg.screenshot(path=str(OUT / name), full_page=True)
            b.close()
    finally:
        srv.terminate()
    return [n for _, n in shots]


FILES = OUT.parent / "scam-demo" / "files"
FILES.mkdir(parents=True, exist_ok=True)
bank_letter_pdf(FILES / "demobank-confirmation-letter-mz-placements.pdf")
bank_letter_pdf(OUT / "case1-bank-confirmation-letter.pdf")
SHOTS = screenshots()

for name, body in CHATS.items():
    (OUT / name).write_text(body, encoding="utf-8")
for name, p in POPS:
    pop_pdf(OUT / name, p)
guide_pdf(OUT / "READ-ME-FIRST-how-to-use.pdf")

files = ["READ-ME-FIRST-how-to-use.pdf", "case1-bank-confirmation-letter.pdf", *SHOTS, *CHATS.keys(), *(n for n, _ in POPS)]
zpath = OUT / "ubufakazi-demo-evidence-kit.zip"
with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
    for f in sorted(files):
        z.write(OUT / f, "ubufakazi-demo-evidence-kit/" + f)
print("wrote", len(files), "files +", zpath.name)
