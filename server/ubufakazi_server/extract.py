"""Deterministic extraction rules, ported from the MVP (site/assets/app.js) so results match.

Everything extracted here is UNVERIFIED until a human reviews it.
Adds (2.0): social profile URLs, @usernames, payment references, and a generic
identifier pass over free-text descriptions for non-chat incidents.
"""
from __future__ import annotations

import datetime as dt
import re
from urllib.parse import urlsplit

# ------------------------------------------------------------------ chat parsing
RE_ANDROID = re.compile(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4}),?\s+(\d{1,2}):(\d{2})(?::\d{2})?\s*([ap]\.?\s?m\.?)?\s+-\s+([^:]{1,60}?):\s?(.*)$", re.I)
RE_IOS = re.compile(r"^\[(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4}),?\s+(\d{1,2}):(\d{2})(?::\d{2})?\s*([ap]\.?\s?m\.?)?\]\s*([^:]{1,60}?):\s?(.*)$", re.I)
RE_PLAIN = re.compile(r"^([A-Za-z][^:\n]{0,40}?):\s+(.+)$")
FIELD_LABEL = re.compile(r"^(bank|acc(ount)?(\s*(no|number|name|holder))?|a/c|ref(erence)?|branch(\s*code)?|name|amount|cell|tel|phone)$", re.I)
_INVISIBLE = re.compile("[‎‏‪-‮﻿]")


def _mkdate(m) -> dt.datetime | None:
    d, mo, y, hh, mm, ap = int(m[1]), int(m[2]), int(m[3]), int(m[4]), int(m[5]), m[6]
    if y < 100:
        y += 2000
    if ap:
        pm = "p" in ap.lower()
        if pm and hh < 12:
            hh += 12
        if not pm and hh == 12:
            hh = 0
    if mo > 12 and d <= 12:
        d, mo = mo, d
    try:
        return dt.datetime(y, mo, d, hh, mm)
    except ValueError:
        return None


def parse_chat(raw: str) -> list[dict]:
    text = _INVISIBLE.sub("", raw or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    stamped = any(RE_ANDROID.match(l) or RE_IOS.match(l) for l in lines)
    msgs, cur = [], None
    for line in lines:
        if not line.strip():
            if cur:
                cur["text"] += "\n"
            continue
        m = RE_ANDROID.match(line) or RE_IOS.match(line)
        if m:
            cur = {"date": _mkdate(m), "sender": m[7].strip(), "text": m[8]}
            msgs.append(cur)
            continue
        if not stamped:
            p = RE_PLAIN.match(line)
            if p and not FIELD_LABEL.match(p[1].strip()) and not re.fullmatch(r"https?", p[1], re.I):
                cur = {"date": None, "sender": p[1].strip(), "text": p[2]}
                msgs.append(cur)
                continue
        if cur:
            cur["text"] += "\n" + line
        else:
            cur = {"date": None, "sender": None, "text": line}
            msgs.append(cur)
    out = []
    for m in msgs:
        m["text"] = m["text"].strip()
        if m["text"]:
            m["i"] = len(out)
            out.append(m)
    return out


# ------------------------------------------------------------------ extraction
BANKS = ["DemoBank", "Capitec", "First National Bank", "FNB", "Absa", "Nedbank", "Standard Bank", "TymeBank",
         "Discovery Bank", "African Bank", "Investec", "Bidvest Bank", "Old Mutual", "Access Bank", "Postbank"]
RE_BANK = re.compile(r"\b(" + "|".join(b.replace(" ", r"\s+") for b in BANKS) + r")\b", re.I)
RE_ACC_CTX = re.compile(r"(acc(ount)?\.?\s*(no|number|nr|#)?|a/c|rekening(nommer)?|akhawunti|akhaonto|bank(ing)? details|deposit (in)?to|pay (in)?to|eft (in)?to)\s*[:\-]?\s*$", re.I)
RE_ACC_LINE = re.compile(r"^\s*(acc(ount)?|a/c|akhawunti|akhaonto|rekening)[^\d\n]{0,25}$", re.I)
RE_DIGITS = re.compile(r"(?<![\d+])\d(?:[ \-]?\d){7,11}(?!\d)")
RE_PHONE = re.compile(r"(?<!\d)(?:\+27|0027|0)(?:[ \-]?\(?\d\)?){9}(?!\d)")
RE_AMOUNT = re.compile(r"\bR\s?(\d{1,3}(?:[ , ]\d{3})+|\d+)(?:[.,](\d{2}))?(?!\d)|\b(\d{1,3}(?:[ ,]\d{3})+|\d+)\s?(?:rand|zar)\b", re.I)
RE_URL = re.compile(r"\bhttps?://[^\s<>\"')\]]+", re.I)
RE_DOMAIN = re.compile(r"(?<![@\w.-])((?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:co\.za|org\.za|net\.za|gov\.za|com|net|org|info|xyz|online|site|top|shop|store|club|live|link|click|ly|io|app|me|biz|icu|vip))(/[^\s<>\"')\]]*)?", re.I)
RE_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
RE_PAID = re.compile(r"\b(i('ve| have)? (just )?(paid|sent|transferred|deposited|made (the )?payment)|paid|sent the|transferred|deposited|eft (done|made)|pop|proof of payment|payment (done|made|sent)|(seng|ng)ikhokhile|(send|nd)ihlawulile|ek het[^.!?\n]{0,30}betaal|ke lefile|ke se ke lefile)\b", re.I)
RE_ASK = re.compile(r"\b(pay|fee|deposit|transfer|send|eft|payment|charge|release|khokh[aei]|ukhokhe|hlawul[aei]|uhlawule|betaal|fooi|deposito|lef[ae]|tefo|imali|geld|tjhelete)\b", re.I)
RE_PRESSURE = re.compile(r"\b(today|urgent(ly)?|immediately|asap|limited|last chance|before (monday|tomorrow|friday|\d)|lose (the|your)|within \d+|right now|expires?|namhlanje|ngokushesha|ngoku|ngokukhawuleza|vandag|dadelik|kajeno|hona jwale|kapele)\b", re.I)
RE_GONE = re.compile(r"\b(blocked|not going through|not answering|no answer|unreachable|ignor(ing|ed)|please answer|switched off|deleted|awuphenduli|akaphenduli|antwoord (jy )?nie|geblokkeer|ha o arabe|ha a arabe)\b", re.I)
RE_OFFER = re.compile(r"\b(congratulations|selected|shortlisted|offer|approved|qualif(y|ied)|winner|won|refund (is )?due|guaranteed|halala|ukhethiwe|siyakuvuyisana|o kgethilwe|gekies|baie geluk|goedgekeur)\b", re.I)
SALARYISH = re.compile(r"\b(salary|per month|p/m|pm|monthly|earn|stipend|profit|returns?|win|won|umholo|umvuzo|ngenyanga|salaris|per maand|moputso|ka kgwedi|refund|terugbetaling|ebuyiselwayo|e busetswang|loan|lening|prize)\b", re.I)
# 2.0 additions
SOCIAL_HOSTS = {"facebook.com": "Facebook", "fb.com": "Facebook", "m.facebook.com": "Facebook", "instagram.com": "Instagram",
                "tiktok.com": "TikTok", "x.com": "X", "twitter.com": "X", "linkedin.com": "LinkedIn", "wa.me": "WhatsApp",
                "t.me": "Telegram", "youtube.com": "YouTube"}
RE_USERNAME = re.compile(r"(?<![\w@./])@([A-Za-z0-9_.]{3,30})(?![\w@])")
RE_PAYREF = re.compile(r"\b(?:ref(?:erence)?|verwysing|ireferensi)\s*(?:no\.?|number|#)?\s*[:\-]\s*([A-Za-z0-9][A-Za-z0-9 \-/]{2,28}[A-Za-z0-9])", re.I)


def norm_phone(s: str) -> str | None:
    d = re.sub(r"\D", "", s)
    if d.startswith("0027"):
        d = d[4:]
    elif d.startswith("27") and len(d) == 11:
        d = d[2:]
    elif d.startswith("0"):
        d = d[1:]
    return "+27" + d if len(d) == 9 and d[0] in "12345678" else None


def show_phone(p: str) -> str:
    return "0" + p[3:5] + " " + p[5:8] + " " + p[8:]


def show_acc(a: str) -> str:
    return re.sub(r"(\d{4})(?=\d)", r"\1 ", a)


def mask_acc(a: str) -> str:
    return "•••• " + a[-4:] if len(a) > 4 else a


def reg_domain(host: str) -> str:
    host = host.lower()
    parts = re.sub(r"^www\.", "", host).split(".")
    n = 3 if re.search(r"\.(co|org|net|gov|ac)\.za$", host) else 2
    return ".".join(parts[-n:])


def canonical_bank(s: str) -> str:
    t = re.sub(r"\s+", " ", s).lower()
    if t == "first national bank":
        return "FNB"
    for b in BANKS:
        if b.lower() == t:
            return b
    return s


def _find_bank(text: str, idx: int) -> str | None:
    best = None
    for m in RE_BANK.finditer(text):
        dist = abs(m.start() - idx)
        if best is None or dist < best[1]:
            best = (canonical_bank(m[1]), dist)
    return best[0] if best and best[1] < 160 else None


def _amount(m) -> float:
    whole = re.sub(r"[ , ]", "", m[1] or m[3] or "")
    return float(whole + ("." + m[2] if m[2] else ""))


def _uniq(items, key=lambda x: x):
    seen, out = set(), []
    for it in items:
        k = key(it)
        if k not in seen:
            seen.add(k)
            out.append(it)
    return out


def extract(msgs: list[dict], scammer: str | None) -> dict:
    out = {"accounts": [], "phones": [], "links": [], "emails": [], "paid": [], "requested": [],
           "social": [], "usernames": [], "payment_refs": []}

    def by_scammer(m):
        return scammer and m["sender"] == scammer

    def by_victim(m):
        return scammer and m["sender"] and m["sender"] != scammer

    for m in msgs:
        t = m["text"]
        taken = []
        for d in RE_DIGITS.finditer(t):
            digits = re.sub(r"\D", "", d[0])
            if not 8 <= len(digits) <= 12:
                continue
            before = t[max(0, d.start() - 45):d.start()]
            line_before = t[t.rfind("\n", 0, d.start()) + 1:d.start()]
            bank = _find_bank(t, d.start())
            ctx = bool(RE_ACC_CTX.search(before)) or bool(RE_ACC_LINE.match(line_before))
            if ctx or (bank and not re.match(r"^0[6-8]", digits)):
                out["accounts"].append({"value": digits, "bank": bank, "msg": m["i"]})
                taken.append((d.start(), d.end()))
        for p in RE_PHONE.finditer(t):
            if any(p.start() < b and p.end() > a for a, b in taken):
                continue
            n = norm_phone(p[0])
            if n:
                out["phones"].append({"value": n, "msg": m["i"]})
        urls = [u[0] for u in RE_URL.finditer(t)]
        bare = [u[0] for u in RE_DOMAIN.finditer(t) if not any(u[0] in x for x in urls)]
        for u in urls + bare:
            try:
                host = urlsplit(u if re.match(r"^https?:", u, re.I) else "http://" + u).hostname or ""
            except ValueError:
                continue
            if not host:
                continue
            url = re.sub(r"[.,;:!?]+$", "", u)
            dom = reg_domain(host)
            social = SOCIAL_HOSTS.get(host.lower().removeprefix("www.")) or SOCIAL_HOSTS.get(dom)
            if social:
                out["social"].append({"url": url, "platform": social, "msg": m["i"]})
            else:
                out["links"].append({"url": url, "domain": dom, "msg": m["i"]})
        for e in RE_EMAIL.finditer(t):
            out["emails"].append({"value": e[0].lower(), "msg": m["i"]})
        for u in RE_USERNAME.finditer(t):
            out["usernames"].append({"value": "@" + u[1].lower(), "msg": m["i"]})
        for r in RE_PAYREF.finditer(t):
            ref = r[1].strip()
            if not re.fullmatch(r"(your name|name|[\d ]{8,})", ref, re.I):
                out["payment_refs"].append({"value": ref.upper(), "msg": m["i"]})
        amounts = [v for v in (_amount(a) for a in RE_AMOUNT.finditer(t)) if 0 < v < 10_000_000]
        if amounts:
            if (by_victim(m) or not scammer) and RE_PAID.search(t):
                out["paid"].append({"amounts": [amounts[0]], "msg": m["i"]})
            elif by_scammer(m) and RE_ASK.search(t):
                asked = []
                for line in t.split("\n"):
                    if RE_AMOUNT.search(line) and not SALARYISH.search(line):
                        asked += [_amount(a) for a in RE_AMOUNT.finditer(line)]
                if asked:
                    out["requested"].append({"amounts": asked, "msg": m["i"]})
    any_bank = next((mm[1] for mm in (RE_BANK.search(m["text"]) for m in msgs) if mm), None)
    for a in out["accounts"]:
        if not a["bank"] and any_bank:
            a["bank"] = canonical_bank(any_bank)
    out["accounts"] = _uniq(out["accounts"], lambda a: a["value"])
    out["phones"] = _uniq(out["phones"], lambda p: p["value"])
    out["links"] = _uniq(out["links"], lambda l: l["url"].lower())
    out["social"] = _uniq(out["social"], lambda l: l["url"].lower())
    out["emails"] = _uniq(out["emails"], lambda e: e["value"])
    out["usernames"] = _uniq(out["usernames"], lambda e: e["value"])
    out["payment_refs"] = _uniq(out["payment_refs"], lambda e: e["value"])
    out["domains"] = _uniq([l["domain"] for l in out["links"]])
    out["banks"] = _uniq([a["bank"] for a in out["accounts"] if a["bank"]])
    out["total_paid"] = sum(p["amounts"][0] for p in out["paid"]) if out["paid"] else None
    out["total_requested"] = sum(sum(p["amounts"]) for p in out["requested"]) if out["requested"] else None
    return out


def guess_scammer(msgs: list[dict]) -> str | None:
    senders = _uniq([m["sender"] for m in msgs if m["sender"]])
    if len(senders) < 2:
        return senders[0] if senders else None
    score = {s: 0 for s in senders}
    for m in msgs:
        s = m["sender"]
        if not s:
            continue
        t = m["text"]
        if re.search(r"acc(ount)?|a/c|bank|akhawunti|akhaonto|rekening", t, re.I) and re.search(r"\d{7,}", re.sub(r"[ -]", "", t)):
            score[s] += 3
        if RE_ASK.search(t) and re.search(r"\bR\s?\d", t, re.I):
            score[s] += 2
        if RE_URL.search(t):
            score[s] += 1
        if RE_PAID.search(t):
            score[s] -= 2
        if re.fullmatch(r"(you|me)", s, re.I):
            score[s] -= 5
    return sorted(senders, key=lambda s: -score[s])[0]


SCAM_WORDS = {
    "job": r"\b(cv|position|vacanc(y|ies)|salary|recruit(er|ment)?|interview|job|employ(ed|ment)|hr|onboarding|uniform|learnership|umsebenzi|isikhundla|esikhundleni|kwisikhundla|mosebetsi|pos|salaris|werk|yunifomu|iyunifomu|uniformfooi)\b",
    "marketplace": r"\b(item|selling|seller|buyer|marketplace|gumtree|facebook|still available|collect(ion)?|for sale|beskikbaar|oyithengisayo|isekhona|e rekisang|ad)\b",
    "romance": r"\b(love|darling|baby|honey|miss you|sweetheart|my dear|marry|relationship|ndiyakuthanda|ngiyakuthanda|sithandwa|moratuwa|ke a o rata|liefie|skat)\b",
    "investment": r"\b(invest(ment)?|returns?|profit|crypto|bitcoin|forex|trading|double your|belegging|wins|peeletso|phaello)\b",
    "parcel": r"\b(parcel|package|courier|delivery|customs|clearance|tracking|shipment|iphasela|ipasile|pakkie|phasela|doeane)\b",
    "sars": r"\b(sars|tax refund|efiling|refund|terugbetaling|ebuyiselwayo|e busetswang)\b",
}
TYPE_LABEL = {"job": "Fake job offer", "marketplace": "Online seller / Marketplace", "romance": "Romance scam",
              "investment": "Investment / crypto scam", "parcel": "Courier / parcel fee", "sars": "Fake SARS refund",
              "other": "Scam"}


def detect_type(text: str) -> str:
    best, top = "other", 1
    for k, pat in SCAM_WORDS.items():
        n = len(re.findall(pat, text or "", re.I))
        if n > top:
            best, top = k, n
    return best


# ------------------------------------------------------------------ timeline
def money(n: float | None) -> str:
    if n is None:
        return "—"
    whole = f"{int(round(n)) if n == int(n) else int(n):,}".replace(",", " ")
    return "R" + whole + (f",{round((n % 1) * 100):02d}" if n % 1 else "")


def _clip(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def list_text(arr: list[str], conj: str = "and") -> str:
    return "".join(arr) if len(arr) <= 1 else ", ".join(arr[:-1]) + f" {conj} " + arr[-1]


def build_timeline(msgs: list[dict], scammer: str | None, ex: dict) -> list[dict]:
    ev = []
    acc_msgs = {a["msg"] for a in ex["accounts"]}
    link_msgs = {l["msg"] for l in ex["links"]}
    paid = {p["msg"]: p for p in ex["paid"]}
    ask = {p["msg"]: p for p in ex["requested"]}
    last_scam = None
    for idx, m in enumerate(msgs):
        q = _clip(re.sub(r"\s+", " ", m["text"]), 110)

        def add(kind, what, m=m, q=q):
            ev.append({"kind": kind, "what": what, "at": m["date"], "quote": q, "who": m["sender"]})
        if idx == 0:
            add("start", "First contact" + (f" from {m['sender']}" if m["sender"] else ""))
        if scammer and m["sender"] == scammer:
            last_scam = m
            if idx > 0 and RE_OFFER.search(m["text"]):
                add("offer", "Promise or offer made")
            if m["i"] in ask:
                add("ask", "Payment of " + list_text([money(a) for a in ask[m["i"]]["amounts"]]) + " requested")
            if m["i"] in acc_msgs:
                add("details", "Banking details sent: " + ", ".join(
                    ((a["bank"] + " ") if a["bank"] else "") + show_acc(a["value"]) for a in ex["accounts"] if a["msg"] == m["i"]))
            if m["i"] in link_msgs:
                add("link", "Link sent: " + ", ".join(l["domain"] for l in ex["links"] if l["msg"] == m["i"]))
            if RE_PRESSURE.search(m["text"]):
                add("pressure", "Pressure to act fast")
        elif m["i"] in paid:
            add("paid", "Complainant paid " + money(paid[m["i"]]["amounts"][0]))
        elif RE_GONE.search(m["text"]):
            add("gone", "Complainant cannot reach the other person")
    if last_scam and msgs and last_scam["i"] != msgs[-1]["i"]:
        ev.append({"kind": "gone", "what": "Last reply from the other person", "at": last_scam["date"],
                   "quote": _clip(re.sub(r"\s+", " ", last_scam["text"]), 110), "who": last_scam["sender"]})
    ev = _uniq(ev, lambda e: e["kind"] + "|" + e["quote"])
    if all(e["at"] for e in ev):
        ev.sort(key=lambda e: e["at"])
    return ev


# ------------------------------------------------------------------ script similarity
def shingles(text: str) -> set[str]:
    t = re.sub(r"r?\d[\d\s,.]*", " # ", (text or "").lower())
    words = [w for w in re.sub(r"[^a-z#\s]", " ", t).split() if w]
    return {" ".join(words[i:i + 3]) for i in range(len(words) - 2)}


def containment(case: set[str], tmpl: set[str]) -> float:
    if not case or not tmpl:
        return 0.0
    return len(case & tmpl) / len(tmpl)


SCRIPT_THRESHOLD = 0.35  # same documented threshold as the MVP


def analyse_text(chat_text: str) -> dict:
    """Run the full rule pipeline on chat/text evidence."""
    msgs = parse_chat(chat_text)
    scammer = guess_scammer(msgs)
    ex = extract(msgs, scammer)
    timeline = build_timeline(msgs, scammer, ex) if msgs else []
    script_text = "\n".join(m["text"] for m in msgs if not scammer or m["sender"] == scammer)
    return {"msgs": msgs, "scammer": scammer, "ex": ex, "timeline": timeline, "script_text": script_text,
            "scam_type": detect_type(chat_text)}
