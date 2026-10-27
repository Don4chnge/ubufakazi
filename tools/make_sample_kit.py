"""Builds the Ubufakazi SAMPLE evidence kit: fictional evidence for every report category, in every format the
system accepts (WhatsApp chat exports, screenshots, PDFs, MP3 voice notes and MP4 videos).

Everything is invented. People, numbers, accounts and websites are made up; "Ubuntu Trust Bank" is a fictional bank;
every image, PDF and video is marked SAMPLE, and every voice note ends by saying it is a fictional sample.
Nothing here depicts a real person or a real crime. Abuse and threat samples are deliberately non-graphic.

Needs: Pillow, reportlab, ffmpeg and espeak-ng (voices). Playwright is optional (website screen recording).
Run:   python3 tools/make_sample_kit.py
Out:   site/demo-kit/samples/<category>/...  and  site/demo-kit/ubufakazi-sample-evidence-all-categories.zip
"""
from __future__ import annotations

import math
import pathlib
import shutil
import subprocess
import tempfile
import zipfile

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

ROOT = pathlib.Path(__file__).resolve().parent.parent
KIT = ROOT / "site" / "demo-kit"
OUT = KIT / "samples"
FONT_DIR = ROOT / "server" / "ubufakazi_server" / "web" / "fonts"
TAG = "This recording is a fictional sample made for the Ubufakazi demonstration."


def font(size: int, bold: bool = False):
    for name in (["Inter-Bold.ttf", "DejaVuSans-Bold.ttf"] if bold else ["Inter-Regular.ttf", "DejaVuSans.ttf"]):
        for base in (FONT_DIR, pathlib.Path("/usr/share/fonts/truetype/dejavu")):
            p = base / name
            if p.exists():
                return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ------------------------------------------------------------------------------------------------ voice notes (MP3)
def voice(path: pathlib.Path, lines: list[tuple[str, str]], phone: bool = False) -> None:
    """lines: (espeak voice, text). Rendered to WAV per line, joined, optionally phone-band filtered, then MP3."""
    with tempfile.TemporaryDirectory() as td:
        parts = []
        for i, (v, text) in enumerate(lines + [("en-gb", TAG)]):
            wav = pathlib.Path(td) / f"{i}.wav"
            run(["espeak-ng", "-v", v, "-s", "150", "-p", "45", "-g", "6", "-w", str(wav), text])
            parts.append(wav)
        lst = pathlib.Path(td) / "list.txt"
        lst.write_text("".join(f"file '{p}'\n" for p in parts))
        af = ["-af", "highpass=f=300,lowpass=f=3400,volume=1.6"] if phone else ["-af", "volume=1.4"]
        run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), *af, "-ac", "1", "-ar", "22050",
             "-codec:a", "libmp3lame", "-b:a", "64k", str(path)])


# ------------------------------------------------------------------------------------------------ images
def phone_screenshot(path: pathlib.Path, title: str, subtitle: str, bubbles: list[tuple[str, str, str]],
                     theme: str = "sms") -> None:
    """bubbles: (side 'in'/'out', text, time). A plain, obviously generic phone-style screenshot."""
    W, H = 720, 1480
    bg = {"sms": "#F2F3F5", "social": "#FFFFFF"}[theme]
    im = Image.new("RGB", (W, H), bg)
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 150], fill="#1F2A3A")
    d.text((32, 30), "9:41", font=font(26, True), fill="white")
    d.text((32, 70), title, font=font(34, True), fill="white")
    d.text((32, 112), subtitle, font=font(22), fill="#B9C4D3")
    y = 190
    for side, text, t in bubbles:
        words, lines, cur = text.split(), [], ""
        for w in words:
            if d.textlength((cur + " " + w).strip(), font=font(27)) > 470:
                lines.append(cur)
                cur = w
            else:
                cur = (cur + " " + w).strip()
        lines.append(cur)
        h = 40 * len(lines) + 56
        x0 = 32 if side == "in" else W - 32 - 540
        d.rounded_rectangle([x0, y, x0 + 540, y + h], 26, fill="#FFFFFF" if side == "in" else "#CDE8FF",
                            outline="#D7DCE3")
        for i, ln in enumerate(lines):
            d.text((x0 + 24, y + 18 + 40 * i), ln, font=font(27), fill="#16223A")
        d.text((x0 + 540 - 110, y + h - 34), t, font=font(20), fill="#6B778A")
        y += h + 26
    stamp(im)
    im.save(path, optimize=True)


def stamp(im: Image.Image) -> None:
    d = ImageDraw.Draw(im)
    W, H = im.size
    d.rectangle([0, H - 64, W, H], fill="#B3261E")
    d.text((24, H - 48), "SAMPLE · FICTIONAL · Ubufakazi demo evidence", font=font(22, True), fill="white")


def illustration(path: pathlib.Path, caption: str, draw_fn) -> None:
    im = Image.new("RGB", (1200, 900), "#D9DDE2")
    draw_fn(ImageDraw.Draw(im))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 1200, 60], fill="#16223A")
    d.text((20, 14), caption, font=font(28, True), fill="white")
    stamp(im)
    im.save(path, quality=88)


# ------------------------------------------------------------------------------------------------ videos (MP4)
def cctv_video(path: pathlib.Path) -> None:
    """A drawn, CCTV-style clip: a figure walks to a parked car, takes a bag and leaves. Clearly an illustration."""
    W, H, fps, n = 640, 360, 12, 12 * 12
    with tempfile.TemporaryDirectory() as td:
        for f in range(n):
            im = Image.new("RGB", (W, H), "#3B4148")
            d = ImageDraw.Draw(im)
            for x in range(0, W, 80):
                d.line([x, 250, x + 40, 360], fill="#565D66", width=3)
            d.rectangle([0, 230, W, 236], fill="#6B737C")
            d.rounded_rectangle([360, 170, 560, 245], 18, fill="#25303D")            # parked car
            d.rectangle([390, 180, 470, 210], fill="#1A222C" if f < 70 else "#9AA4AF")  # window (broken later)
            d.ellipse([380, 232, 420, 262], fill="#111")
            d.ellipse([500, 232, 540, 262], fill="#111")
            t = f / n
            px = 40 + min(t, 0.45) / 0.45 * 300 if t < 0.7 else 340 - (t - 0.7) / 0.3 * 340
            leg = 10 * math.sin(f * 0.9)
            d.ellipse([px - 14, 118, px + 14, 146], fill="#C9CED4")                   # figure (hooded)
            d.rounded_rectangle([px - 16, 146, px + 16, 200], 8, fill="#8C949E")
            d.line([px - 8, 200, px - 8 + leg, 245], fill="#8C949E", width=9)
            d.line([px + 8, 200, px + 8 - leg, 245], fill="#8C949E", width=9)
            if t >= 0.62:
                d.rectangle([px + 14, 165, px + 44, 192], fill="#B98A3E")             # the bag
            d.rectangle([0, 0, W, 26], fill="#000")
            secs = 5 + f // fps
            d.text((8, 4), f"CAM 02 · PARKING BAY · 2026-10-20 21:14:{secs:02d}", font=font(15, True), fill="#E8E8E8")
            d.text((W - 92, 4), "● REC", font=font(15, True), fill="#FF5A4F")
            d.rectangle([0, H - 26, W, H], fill="#B3261E")
            d.text((8, H - 22), "SAMPLE · FICTIONAL ILLUSTRATION · Ubufakazi demo", font=font(15, True), fill="white")
            im.save(pathlib.Path(td) / f"f{f:04d}.png")
        run(["ffmpeg", "-y", "-framerate", str(fps), "-i", str(pathlib.Path(td) / "f%04d.png"), "-c:v", "libx264",
             "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-crf", "28", str(path)])


def screen_recording(path: pathlib.Path, url_path: str) -> bool:
    """Records a scroll through one of the fictional scam pages (needs Playwright)."""
    try:
        import sys
        import time
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False
    site = ROOT / "site"
    srv = subprocess.Popen([sys.executable, "-m", "http.server", "8798", "--bind", "127.0.0.1"], cwd=site,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    try:
        with tempfile.TemporaryDirectory() as td, sync_playwright() as p:
            b = p.chromium.launch()
            ctx = b.new_context(viewport={"width": 430, "height": 820}, record_video_dir=td,
                                record_video_size={"width": 430, "height": 820})
            pg = ctx.new_page()
            pg.goto("http://127.0.0.1:8798/" + url_path)
            pg.wait_for_timeout(1200)
            for _ in range(14):
                pg.mouse.wheel(0, 260)
                pg.wait_for_timeout(450)
            pg.wait_for_timeout(800)
            video = pg.video.path()
            ctx.close()
            b.close()
            banner = pathlib.Path(td) / "banner.png"
            im = Image.new("RGB", (430, 30), "#B3261E")
            ImageDraw.Draw(im).text((10, 6), "SAMPLE · FICTIONAL · Ubufakazi demo", font=font(15, True), fill="white")
            im.save(banner)
            run(["ffmpeg", "-y", "-i", video, "-i", str(banner), "-filter_complex", "overlay=0:main_h-overlay_h",
                 "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-crf", "30", str(path)])
        return True
    finally:
        srv.terminate()


# ------------------------------------------------------------------------------------------------ PDFs
def letter_pdf(path: pathlib.Path, org: str, title: str, rows: list[tuple[str, str]], body: list[str],
               color: str = "#1D3B6E") -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    W, H = A4
    c.setTitle(f"{title} (SAMPLE)")
    c.setFillColor(HexColor(color))
    c.rect(0, H - 100, W, 100, stroke=0, fill=1)
    c.setFillColor(HexColor("#FFFFFF"))
    c.setFont("Helvetica-Bold", 24)
    c.drawString(50, H - 58, org)
    c.setFont("Helvetica", 10)
    c.drawString(50, H - 80, "Fictional organisation · sample document for the Ubufakazi demonstration")
    c.setFillColor(HexColor("#16223A"))
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, H - 140, title)
    y = H - 175
    for k, v in rows:
        c.setFont("Helvetica", 10)
        c.setFillColor(HexColor("#5B6B84"))
        c.drawString(50, y, k)
        c.setFillColor(HexColor("#16223A"))
        c.setFont("Helvetica-Bold", 10.5)
        c.drawString(210, y, v)
        y -= 22
    y -= 10
    c.setFont("Helvetica", 10.5)
    for para in body:
        line = ""
        for w in para.split():
            if c.stringWidth(line + " " + w, "Helvetica", 10.5) > W - 100:
                c.drawString(50, y, line.strip())
                y -= 15
                line = w
            else:
                line += " " + w
        c.drawString(50, y, line.strip())
        y -= 24
    c.saveState()
    c.setFillColor(HexColor("#B3261E"))
    c.setFillAlpha(0.13)
    c.setFont("Helvetica-Bold", 80)
    c.translate(W / 2, H / 2 - 60)
    c.rotate(30)
    c.drawCentredString(0, 0, "SAMPLE")
    c.restoreState()
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(HexColor("#B3261E"))
    c.drawString(50, 40, "SAMPLE - FICTIONAL - NOT A REAL DOCUMENT - made for the Ubufakazi demonstration")
    c.save()


# ================================================================================================ the kit
CATEGORIES = {}


def category(folder, label, readme):
    def deco(fn):
        CATEGORIES[folder] = (label, readme, fn)
        return fn
    return deco


@category("01-online-scam-job-offer", "Online scam / fraudulent job offer",
          "Lerato paid a fake recruiter twice. Use the original demo kit files (case1-*) plus these: a voice note from the "
          "'recruiter' and a screen recording of the fake careers website. Report it in Mthatha, Eastern Cape.")
def cat_scam(d: pathlib.Path):
    for f in ["case1-lerato-whatsapp-chat.txt", "case1-lerato-proof-of-payment-1.pdf", "case1-lerato-proof-of-payment-2.pdf",
              "case1-scam-website-screenshot.png", "case1-recruiter-profile-screenshot.png", "case1-bank-confirmation-letter.pdf"]:
        if (KIT / f).exists():
            shutil.copy(KIT / f, d / f)
    voice(d / "recruiter-voice-note.mp3", [("en-gb+f3",
        "Hi Lerato, it's Thandi from Mzansi Retail Group. Congratulations again on the admin clerk position. "
        "Please remember the training fee of one thousand six hundred and fifty rand must be paid before Monday, "
        "otherwise we give the position to the next candidate. Pay into the Ubuntu Trust Bank account, "
        "one zero four seven, two two eight three, five nine, reference your name. Then send me the proof on WhatsApp.")])
    screen_recording(d / "fake-careers-website-recording.mp4", "scam-demo/mzansi-careers/")


@category("02-digital-banking-fraud", "Digital banking fraud / suspicious payment",
          "Sizwe got an SMS and a phone call from a fake 'fraud department', gave his one-time PIN, and two payments left "
          "his account. Evidence: the SMS screenshot, a recording of the call, his statement showing the debits, and his "
          "WhatsApp chat with the caller. Report it in Gauteng, Johannesburg.")
def cat_banking(d: pathlib.Path):
    phone_screenshot(d / "fake-bank-sms-screenshot.png", "Messages", "+27 61 880 4417", [
        ("in", "UTB ALERT: A login to your Ubuntu Trust Bank app from a new device was detected. If this was not you, "
               "call our fraud desk on 061 880 4417 immediately.", "08:02"),
        ("in", "Your one-time PIN is 482913. Never share this PIN with anyone, including bank staff.", "08:09"),
        ("in", "Payment of R7 450.00 to beneficiary 'SECURE HOLD' was successful.", "08:11"),
        ("in", "Payment of R5 200.00 to beneficiary 'SECURE HOLD' was successful.", "08:14"),
    ])
    voice(d / "fake-bank-call-recording.mp3", [
        ("en-us+m3", "Good morning, am I speaking with Mister Sizwe Khumalo? This is Kevin from the Ubuntu Trust Bank fraud department."),
        ("en-gb+m1", "Yes, speaking. I just got an SMS about a login."),
        ("en-us+m3", "Correct sir, someone is trying to access your account. To block them I need to move your money to a "
                     "secure holding account. You will receive a PIN now. Please read it to me."),
        ("en-gb+m1", "Okay. The PIN is four eight two, nine one three."),
        ("en-us+m3", "Thank you sir, your money is now safe. Do not call the branch, it will delay the process."),
    ], phone=True)
    letter_pdf(d / "account-statement-unauthorised-debits.pdf", "Ubuntu Trust Bank", "Account statement (extract)", [
        ("Account holder", "S KHUMALO"), ("Account", "Everyday account ...6621"), ("Period", "20 Oct 2026 - 21 Oct 2026"),
        ("20 Oct 08:11", "EFT to 'SECURE HOLD' acc 6230 4418 02   -R7 450,00"),
        ("20 Oct 08:14", "EFT to 'SECURE HOLD' acc 6230 4418 02   -R5 200,00"),
        ("Closing balance", "R1 312,40"),
    ], ["The two payments above were not authorised by the account holder. He disputes them.",
        "A real bank never asks you to move money to a 'safe' or 'holding' account, and never asks for your PIN."])
    (d / "whatsapp-chat-with-caller.txt").write_text(
        "20/10/2026, 08:20 - +27 61 880 4417: Sir this is Kevin from UTB fraud. Your funds are secured in holding account 6230 4418 02.\n"
        "20/10/2026, 08:21 - Sizwe: When will the money come back to my account?\n"
        "20/10/2026, 08:23 - +27 61 880 4417: Within 24 hours. Do not visit the branch or call the bank, it will reverse the protection.\n"
        "21/10/2026, 09:05 - Sizwe: It's been 24 hours. Where is my R12 650?\n"
        "21/10/2026, 09:40 - Sizwe: Hello??\n", encoding="utf-8")


@category("03-theft-property", "Theft or property incident",
          "A laptop bag was taken from Ayanda's parked car. Evidence: a CCTV-style clip from the parking bay (a drawn "
          "illustration), a photo of the broken window, proof of purchase of the laptop with its serial number, and a "
          "list of what was taken. Report it in KwaZulu-Natal, Durban.")
def cat_theft(d: pathlib.Path):
    cctv_video(d / "parking-cctv-clip.mp4")

    def car(dr):
        dr.rounded_rectangle([200, 260, 1000, 640], 60, fill="#2C3A4B")
        dr.rectangle([300, 300, 620, 470], fill="#7E8A97")
        for i in range(14):
            dr.line([460, 385, 300 + i * 23, 300 if i % 2 else 470], fill="#E8ECF0", width=3)
        dr.ellipse([270, 600, 400, 730], fill="#111")
        dr.ellipse([800, 600, 930, 730], fill="#111")
        dr.text((300, 760), "broken rear window (drawn illustration)", font=font(34, True), fill="#16223A")
    illustration(d / "broken-car-window-photo.jpg", "Photo · 20 Oct 2026 21:31 · Durban", car)
    letter_pdf(d / "laptop-proof-of-purchase.pdf", "TechHub Stores (fictional)", "Tax invoice", [
        ("Invoice", "TH-55821"), ("Date", "03 Mar 2026"), ("Customer", "A NAIDOO"),
        ("Item", "Laptop 14-inch, model TH-Pro 5"), ("Serial number", "THP5-7Q2X-88410"), ("Price", "R12 999,00"),
    ], ["Keep this invoice: the serial number helps police identify the laptop if it is recovered."], color="#0F5E57")
    (d / "list-of-stolen-items.txt").write_text(
        "Items taken from my car, 20 October 2026, about 21:14, parking bay at the shopping centre, Durban:\n"
        "- Laptop (TH-Pro 5, serial THP5-7Q2X-88410), value R12 999\n"
        "- Black laptop bag with charger, value about R650\n"
        "- Work access card\n"
        "The rear window was broken. Centre security has CCTV from camera 02.\n", encoding="utf-8")


@category("04-abuse-domestic-violence", "Physical abuse / domestic violence",
          "Non-graphic sample only. Thuli recorded what happened in her own words, kept the messages, and photographed "
          "the damaged door. In a real situation, safety comes first: call 10111 or the GBV Command Centre on "
          "0800 428 428. This category starts with a safety question and offers a quick exit.")
def cat_abuse(d: pathlib.Path):
    voice(d / "my-own-voice-memo.mp3", [("en-gb+f2",
        "This is my own note, recorded on Saturday the eighteenth of October. Last night my partner came home angry, "
        "shouted at me and pushed me against the wall in the passage. He broke the bedroom door when I locked myself in. "
        "I left with the children and stayed with my sister. I want this written down in case I need it later.")])

    def door(dr):
        dr.rectangle([400, 120, 800, 840], fill="#A07A52")
        dr.line([600, 240, 520, 520], fill="#3B2A1A", width=8)
        dr.line([520, 520, 640, 700], fill="#3B2A1A", width=6)
        dr.ellipse([760, 470, 784, 494], fill="#D4AF37")
        dr.text((60, 420), "damaged bedroom door\n(drawn illustration)", font=font(32, True), fill="#16223A")
    illustration(d / "damaged-door-photo.jpg", "Photo · 17 Oct 2026 23:40", door)
    (d / "messages-from-partner.txt").write_text(
        "17/10/2026, 22:58 - Partner: Where are you? Open this door now\n"
        "17/10/2026, 23:05 - Partner: You think you can hide from me\n"
        "18/10/2026, 07:30 - Partner: Come back home today or you will see what happens\n"
        "18/10/2026, 07:31 - Thuli: I am safe at my sister. Please leave me alone\n", encoding="utf-8")


@category("05-threats-harassment", "Threats or harassment",
          "Bongani is being harassed online after a dispute. Evidence: a screenshot of comments from a fake profile, a "
          "threatening voice note, and the WhatsApp messages. Non-graphic sample. Report it in Western Cape, Cape Town.")
def cat_threats(d: pathlib.Path):
    phone_screenshot(d / "harassing-comments-screenshot.png", "Comments", "on Bongani's post · 23 Oct 2026", [
        ("in", "@cpt_truth_2026: Everyone, this guy is a thief. Don't buy from him.", "19:02"),
        ("in", "@cpt_truth_2026: I know where you work in Bellville. See you soon.", "19:05"),
        ("in", "@cpt_truth_2026: Delete your page or I will post your address.", "19:20"),
        ("out", "Bongani: Please stop. I have reported this account.", "19:31"),
    ], theme="social")
    voice(d / "threatening-voice-note.mp3", [("en-us+m4",
        "Bongani, you think you are clever reporting my account. I know where you work and I know your car. "
        "Pay back the two thousand rand by Friday or you will regret it.")])
    (d / "whatsapp-messages.txt").write_text(
        "23/10/2026, 21:10 - +27 74 552 1093: You have until Friday to pay the R2 000\n"
        "23/10/2026, 21:12 - +27 74 552 1093: I know your car, the white Polo\n"
        "24/10/2026, 06:45 - Bongani: Who is this? Stop messaging me\n"
        "24/10/2026, 06:50 - +27 74 552 1093: You will see who\n", encoding="utf-8")


@category("06-evidence-tampering-misconduct", "Suspected evidence tampering or misconduct",
          "Two copies of the same proof of payment: the original and an altered one where the amount was changed. "
          "Upload both on the Verify page or in a report: their SHA-256 fingerprints differ, which is how tampering is "
          "detected. Also a voice note in which someone asks for money to 'speed up' a case (fictional, no real station).")
def cat_misconduct(d: pathlib.Path):
    rows = [("Date", "16 Oct 2026, 11:05"), ("Beneficiary", "Pretoria Car Sales"), ("Account", "4471 2093 18"),
            ("Reference", "DEPOSIT VW"), ("Transaction", "UTB-5P1X-7720")]
    letter_pdf(d / "proof-of-payment-ORIGINAL.pdf", "Ubuntu Trust Bank", "Proof of payment",
               rows[:1] + [("Amount", "R15 000,00")] + rows[1:], ["Status: Successful."])
    letter_pdf(d / "proof-of-payment-ALTERED.pdf", "Ubuntu Trust Bank", "Proof of payment",
               rows[:1] + [("Amount", "R1 500,00")] + rows[1:], ["Status: Successful."])
    voice(d / "request-for-money-voice-note.mp3", [("en-gb+m2",
        "Ja, about your case. These things take long, you know. If you want it to move faster, "
        "bring something small for cold drinks when you come on Monday. Two hundred rand will help a lot.")])
    (d / "what-happened.txt").write_text(
        "I paid a R15 000 deposit for a car. The seller now shows a proof of payment that says R1 500 and says I still owe him.\n"
        "My original proof of payment and his copy are both attached. They look the same except for the amount.\n"
        "Separately, someone who said he works on my case asked me for money to make it go faster (voice note attached).\n",
        encoding="utf-8")


@category("07-other-incident", "Other reportable incident",
          "Someone used Pieter's identity to open a store account. Evidence: the store's letter about an account he never "
          "opened, an SMS about the new account, and his own voice note in Afrikaans. Report it in Free State, Bloemfontein.")
def cat_other(d: pathlib.Path):
    letter_pdf(d / "store-account-letter.pdf", "Karoo Furnishers (fictional)", "Welcome to your new store account", [
        ("Account holder", "P VAN WYK"), ("Account number", "KF-0093-1186"), ("Opened", "09 Oct 2026, Bloemfontein branch"),
        ("Credit limit", "R18 000,00"), ("First purchase", "R16 450,00 - lounge suite"),
    ], ["Thank you for opening an account with us. Your first instalment of R1 120,00 is due on 1 November 2026."],
        color="#5B3A1D")
    phone_screenshot(d / "new-account-sms-screenshot.png", "Messages", "KAROO FURN", [
        ("in", "Welcome to Karoo Furnishers! Your account KF-0093-1186 is open. First instalment R1 120 due 01/11.", "10:42"),
        ("out", "I did not open any account with you. Who opened this?", "10:50"),
    ])
    voice(d / "my-voice-note-afrikaans.mp3", [("af",
        "Hallo, dit is Pieter van Wyk. Ek het vandag 'n brief gekry oor 'n winkelrekening wat ek nooit oopgemaak het nie. "
        "Iemand het my naam en my besonderhede gebruik. Ek wil dit aanmeld."),
        ("en-gb", "In English: someone used my name and details to open a store account. I want to report it.")])


def readme_pdf(path: pathlib.Path) -> None:
    body = ["Every file in this kit is FICTIONAL and made for the Ubufakazi demonstration. People, phone numbers, "
            "accounts and websites are invented. Ubuntu Trust Bank, TechHub Stores and Karoo Furnishers are not real.",
            "How to use: open ubufakazi.onrender.com/report (or the Telegram bot), choose the category that matches the "
            "folder, and attach the files from that folder. Voice notes (MP3) and videos (MP4) are accepted; with AI "
            "reading switched on, voice notes are transcribed and marked as unverified.",
            "Abuse and threat samples are deliberately non-graphic. In a real emergency call 10111. Gender-based "
            "violence: GBV Command Centre 0800 428 428."]
    rows = [(f"{k[:2]}  {v[0]}", "") for k, v in CATEGORIES.items()]
    letter_pdf(path, "Ubufakazi sample evidence kit", "Read me first", rows, body, color="#0B1B2B")


def write_index() -> None:
    """A plain page listing every sample with a download link (uses the site's stylesheet; no inline styles)."""
    from html import escape
    kinds = {".mp3": "voice note", ".mp4": "video", ".pdf": "PDF", ".png": "screenshot", ".jpg": "photo", ".txt": "text / chat"}
    sections = []
    for folder, (label, readme, _) in CATEGORIES.items():
        rows = "".join(
            f'<tr><td><a href="{escape(folder)}/{escape(p.name)}" download>{escape(p.name)}</a></td>'
            f'<td>{kinds.get(p.suffix, p.suffix)}</td><td class="num">{max(1, p.stat().st_size // 1024)} KB</td></tr>'
            for p in sorted((OUT / folder).iterdir()) if p.name != "README.txt")
        sections.append(f'<section class="panel"><div class="kicker">{escape(folder[:2])}</div><h2>{escape(label)}</h2>'
                        f'<p class="muted">{escape(readme)}</p><div class="table-wrap"><table class="data"><thead><tr>'
                        f'<th>File</th><th>Kind</th><th class="num">Size</th></tr></thead><tbody>{rows}</tbody></table>'
                        f'</div></section>')
    (OUT / "index.html").write_text(f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sample evidence kit · Ubufakazi</title><link rel="icon" href="/app/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="/app/console.css"></head>
<body><main class="public" id="main">
<div class="page-hero"><div class="kicker">Demo · fictional</div><h1>Sample evidence kit</h1>
<p class="lead-in">Fictional evidence for every report category: chats, screenshots, PDFs, voice notes (MP3) and videos (MP4).
Use them on <a href="/report">Report a Scam</a> or with the Telegram bot. Everything is invented and marked SAMPLE.</p>
<p><a class="btn btn-primary" href="../ubufakazi-sample-evidence-all-categories.zip" download>Download everything (ZIP)</a>
<a class="btn btn-ghost" href="READ-ME-FIRST.pdf" download>Read me first (PDF)</a></p></div>
<div class="stack">{''.join(sections)}</div>
<p class="foot-note">In a real emergency call 10111. Gender-based violence: GBV Command Centre 0800 428 428.</p>
</main></body></html>
""", encoding="utf-8")


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    files = []
    for folder, (label, readme, fn) in CATEGORIES.items():
        d = OUT / folder
        d.mkdir()
        fn(d)
        (d / "README.txt").write_text(f"{label}\n\n{readme}\n\nAll files are fictional samples.\n", encoding="utf-8")
        files += sorted(p for p in d.iterdir())
        print(f"{folder}: {', '.join(p.name for p in sorted(d.iterdir()))}")
    readme_pdf(OUT / "READ-ME-FIRST.pdf")
    files.append(OUT / "READ-ME-FIRST.pdf")
    write_index()
    zpath = KIT / "ubufakazi-sample-evidence-all-categories.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(f, "ubufakazi-sample-evidence/" + str(f.relative_to(OUT)))
    print("wrote", len(files), "files +", zpath.name, f"({zpath.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
