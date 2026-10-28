"""Channel-neutral reporting conversation (used by the Telegram bot; a WhatsApp adapter can reuse it).

The adapter passes in text, files or a location and sends back the replies. State lives in memory only
(no evidence is written to disk before the complainant consents). /stop clears everything at any step.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Callable

from .models import CATEGORIES, CATEGORY_LABELS, FINANCIAL_CATEGORIES
from .stations import DEMO_STATIONS, PROVINCES, route, towns_by_province
from .writing import LANG_NAMES
from . import services

MAX_FILES = 20
MAX_PASTE = 200_000
STOP_WORDS = {"/stop", "stop", "/exit", "exit", "/cancel", "cancel", "yima", "ima", "emisa", "stop asseblief"}
SKIP = "Skip"
DONE = "Done"
EMERGENCY = ("Police emergency: 10111 (free from any phone). Gender-based violence: GBV Command Centre "
             "0800 428 428 (free, 24 hours).")


@dataclass
class Out:
    text: str
    options: list[str] | None = None
    action: dict | None = None          # e.g. {"type": "submitted", ...} for the adapter


@dataclass
class Pending:
    data: bytes
    name: str
    mime: str
    sha256: str


@dataclass
class Conversation:
    """One complainant's draft report. `submit` defaults to services.submit_report."""
    channel: str = "telegram"
    contact_ref: str | None = None
    submit: Callable[..., dict] | None = None
    step: str = "new"
    data: dict = field(default_factory=dict)
    files: list[Pending] = field(default_factory=list)
    pasted: list[str] = field(default_factory=list)
    submitted: list[str] = field(default_factory=list)     # references submitted from this chat

    # ---------------------------------------------------------------- entry point
    def handle(self, text: str | None = None, *, file: tuple[bytes, str, str] | None = None,
               location: tuple[float, float] | None = None) -> list[Out]:
        t = (text or "").strip()
        low = t.lower()
        if low in STOP_WORDS:
            return self.stop()
        if low in ("/start", "/new", "/report"):
            return self.start()
        if low == "/help":
            return [Out(self._help())]
        if low == "/status":
            return [Out(self._status_text())]
        if low in ("/pack", "/pdf", "pdf", "case pack", "send pdf", "send the pdf") and self.submitted \
                and self.step in ("submitted", "pack_choice", "new"):
            self.step = "submitted"
            return [Out("Preparing your case pack (PDF)…", action={"type": "send_pack", "reference": self.submitted[-1]})]
        if self.step in ("new", "submitted"):
            if self.step == "submitted":
                return [Out(f"Your report {self.submitted[-1]} has been submitted. Send /new to report something else, "
                            "or /status to see where your reports are.")]
            return self.start()
        handler = getattr(self, f"_on_{self.step}")
        return handler(t, file, location)

    # ---------------------------------------------------------------- control
    def start(self) -> list[Out]:
        self.data, self.files, self.pasted = {}, [], []
        self.step = "language"
        return [Out("Sawubona · Molo · Dumela · Hallo · Hello\n\n"
                    "I'm Ubufakazi, a DEMO reporting assistant (a hackathon prototype by Team CyberThreat). I help you turn "
                    "what happened into an organised report, a draft statement and a case pack. Your report goes to the "
                    "fraud desk of the bank branch for your area: the bank links it to other victims, can block the "
                    "scammer's account and escalates the case to SAPS.\n\n"
                    "I am NOT the police (SAPS) and I cannot open a case. In danger right now? Call 10111.\n"
                    "Type /stop at any time to stop and clear this draft."),
                Out("Which language should your statement be written in?", list(LANG_NAMES.values()))]

    def stop(self) -> list[Out]:
        had_draft = self.step not in ("new", "submitted")
        self.data, self.files, self.pasted = {}, [], []
        self.step = "submitted" if self.submitted else "new"
        msg = ("Stopped. Your draft has been cleared and nothing from it was saved." if had_draft
               else "Stopped. There was no draft in progress.")
        if self.submitted:
            msg += " Reports you already submitted are kept safely."
        msg += "\nSend /new whenever you want to start again. " + EMERGENCY
        return [Out(msg, action={"type": "quick_exit"})]

    def _help(self) -> str:
        return ("/new: start a report\n/stop: stop and clear the draft (quick exit)\n/status: see your submitted reports\n"
                "/pack: get the case pack (PDF) of your last report\n"
                "This is a demonstration service. It is not SAPS. " + EMERGENCY)

    def _status_text(self) -> str:
        if not self.submitted:
            return "You have not submitted a report from this chat yet. Send /new to start."
        return ("Your reports (check progress on the Track page with your reference and receipt key):\n"
                + "\n".join(f"- {r}" for r in self.submitted))

    # ---------------------------------------------------------------- steps
    def _choose(self, t: str, options: list[str]) -> int | None:
        if t.isdigit() and 1 <= int(t) <= len(options):
            return int(t) - 1
        low = t.lower()
        for i, o in enumerate(options):
            if low == o.lower():
                return i
        return None

    def _on_language(self, t, file, loc):
        names = list(LANG_NAMES.values())
        i = self._choose(t, names)
        if i is None:
            return [Out("Please choose a language from the list.", names)]
        self.data["language"] = list(LANG_NAMES)[i]
        self.step = "category"
        note = "" if self.data["language"] == "en" else (
            f"\n(I'll keep chatting in English for now, but your statement will be drafted in {names[i]}.)")
        return [Out("What happened? Choose the closest option." + note, list(CATEGORIES.values()))]

    def _on_category(self, t, file, loc):
        labels = list(CATEGORIES.values())
        i = self._choose(t, labels)
        if i is None:
            return [Out("Please choose one of the options.", labels)]
        cat = list(CATEGORIES)[i]
        self.data["category"] = cat
        if cat in ("abuse", "threats"):
            self.step = "safety"
            return [Out("Before anything else: are you safe right now?", ["I'm safe right now", "I'm not safe / not sure"])]
        return self._ask_province()

    def _on_safety(self, t, file, loc):
        if t.lower().startswith("i'm safe") or t == "1":
            self.data["unsafe"] = False
            return self._ask_province()
        if t.lower().startswith("i'm not") or t == "2":
            self.data["unsafe"] = True
            self.step = "safety_next"
            return [Out("Your safety comes first.\n" + EMERGENCY +
                        "\n\nYou can finish this report later. If someone might see this phone, send /stop and I will stop "
                        "and clear this draft (on Telegram I also try to delete our messages).",
                        ["Continue my report", "Stop for now"])]
        return [Out("Please choose an option.", ["I'm safe right now", "I'm not safe / not sure"])]

    def _on_safety_next(self, t, file, loc):
        if t.lower().startswith("stop") or t == "2":
            return self.stop()
        return self._ask_province()

    def _ask_province(self):
        self.step = "province"
        return [Out("Which province did it happen in?", PROVINCES)]

    def _on_province(self, t, file, loc):
        i = self._choose(t, PROVINCES)
        if i is None:
            return [Out("Please choose a province.", PROVINCES)]
        self.data["province"] = PROVINCES[i]
        self.step = "town"
        towns = towns_by_province()[PROVINCES[i]]
        return [Out("Which town or area? Choose one, or type the name.", towns + ["Other (type it)"])]

    def _on_town(self, t, file, loc):
        if not t or t.lower().startswith("other"):
            return [Out("Please type the name of your town or area.")]
        self.data["town"] = t[:80]
        code = route(self.data["province"], t)
        self.data["station"] = next(n for c, n, _, _ in DEMO_STATIONS if c == code)
        self.step = "location"
        return [Out("Optional: share an approximate location (tap the attachment button, then Location), or tap Skip.\n"
                    "Location is never required. If you share it, I round it to about 1 km.", [SKIP])]

    def _on_location(self, t, file, loc):
        if loc:
            self.data["location"] = (round(loc[0], 2), round(loc[1], 2))
        elif t.lower() != SKIP.lower():
            return [Out("Share a location or tap Skip.", [SKIP])]
        self.step = "when"
        return [Out("When did it happen? For example: 'yesterday', '12 October' or '12/10/2026'. "
                    "Type 'not sure' if you don't know.")]

    def _on_when(self, t, file, loc):
        if not t:
            return [Out("Please type when it happened (or 'not sure').")]
        self.data["when"] = "" if t.lower() in ("not sure", "unsure", "don't know") else t[:80]
        self.step = "describe"
        return [Out("In your own words, what happened? A few sentences is enough. Don't include your ID number.")]

    def _on_describe(self, t, file, loc):
        if len(t) < 10:
            return [Out("Please write at least one full sentence about what happened.")]
        self.data["description"] = t[:8000]
        self.step = "evidence"
        if self.data["category"] in FINANCIAL_CATEGORIES:
            msg = ("Now send your evidence. You can send as many as you need:\n"
                   "- screenshots or photos\n- proof of payment (PDF or image)\n- voice notes\n"
                   "- the WhatsApp chat export (.txt), or paste the other person's messages as text\n"
                   "Each file gets a digital fingerprint (SHA-256) the moment it arrives. Tap Done when finished.")
        elif self.data["category"] in ("abuse", "threats"):
            msg = ("If you have evidence (messages, photos, voice notes) you can send it now, but only if it is safe to do so. "
                   "Tap Done when finished, or Done straight away to skip.")
        else:
            msg = "If you have evidence (photos, documents, messages, voice notes), send it now. Tap Done when finished."
        return [Out(msg, [DONE])]

    def _on_evidence(self, t, file, loc):
        if file:
            data, name, mime = file
            if len(self.files) >= MAX_FILES:
                return [Out(f"That's the maximum of {MAX_FILES} files. Tap Done to continue.", [DONE])]
            from .storage import sniff
            if not data or sniff(data) is None:
                return [Out(f"I can't accept '{name}': this file type is not supported. Send images, PDFs, audio, video "
                            "or text.", [DONE])]
            digest = hashlib.sha256(data).hexdigest()
            if any(p.sha256 == digest for p in self.files):
                return [Out(f"I already have that file ({name}).", [DONE])]
            self.files.append(Pending(data, name, mime, digest))
            return [Out(f"Received {name}\nSHA-256 fingerprint: {digest[:16]}…\n({len(self.files)} file(s) so far.) "
                        "Send more, or tap Done.", [DONE])]
        if t.lower() in (DONE.lower(), "skip", "no", "none"):
            return self._after_evidence()
        if t:
            if sum(len(p) for p in self.pasted) + len(t) > MAX_PASTE:
                return [Out("That's a lot of text. Please send the chat export as a .txt file instead.", [DONE])]
            self.pasted.append(t)
            return [Out(f"Saved the pasted text ({len(t)} characters). It will be stored as evidence with its own "
                        "fingerprint. Send more, or tap Done.", [DONE])]
        return [Out("Send a file or text, or tap Done.", [DONE])]

    def _after_evidence(self):
        cat = self.data["category"]
        self.step = "followup"
        if cat in FINANCIAL_CATEGORIES:
            return [Out("Did you pay any money? If yes, how much in total? (for example R3 500)", ["No payment"])]
        if cat == "theft":
            return [Out("What was taken, and roughly what was it worth?", [SKIP])]
        if cat in ("abuse", "threats"):
            return [Out("Optional: is the person known to you?", ["Yes, known to me", "No, a stranger", "Prefer not to say"])]
        if cat == "misconduct":
            return [Out("Which station, office or item of evidence is this about?", [SKIP])]
        return self._ask_name()

    def _on_followup(self, t, file, loc):
        cat = self.data["category"]
        answers = self.data.setdefault("answers", {})
        if t and t.lower() not in ("skip", "no payment", "prefer not to say"):
            key = {"scam": "amount_paid", "banking_fraud": "amount_paid", "theft": "items_taken",
                   "abuse": "person_known", "threats": "person_known", "misconduct": "about"}.get(cat, "extra")
            answers[key] = t[:300]
        elif t.lower() == "no payment":
            answers["amount_paid"] = "No payment"
        return self._ask_name()

    def _ask_name(self):
        self.step = "name"
        return [Out("What name should appear on your draft statement? You can tap Skip and write it at the station. "
                    "I will never ask for your ID number.", [SKIP])]

    def _on_name(self, t, file, loc):
        if t and t.lower() != "skip":
            if re.search(r"\d{13}", t):
                return [Out("Please don't send an ID number. Just your name, or tap Skip.", [SKIP])]
            self.data["name"] = t[:120]
        self.step = "summary"
        d = self.data
        ev = f"{len(self.files)} file(s)" + (f" + {len(self.pasted)} pasted message block(s)" if self.pasted else "")
        lines = [
            "Please check your report:",
            f"- What happened: {CATEGORY_LABELS.get(d['category'], d['category'])}",
            f"- Where: {d['town']}, {d['province']}",
            f"- Will be sent to: {d['station']} fraud desk (fictional bank)",
            f"- When: {d.get('when') or 'not sure'}",
            f"- Evidence: {ev}",
            f"- Statement language: {LANG_NAMES[d['language']]}",
            f"- Name on statement: {d.get('name') or '(to add at the station)'}",
            f"- Your words: {d['description'][:220]}{'…' if len(d['description']) > 220 else ''}",
        ]
        return [Out("\n".join(lines), ["Looks right, continue", "Start again"])]

    def _on_summary(self, t, file, loc):
        if t.lower().startswith("start again") or t == "2":
            return self.start()
        if not (t.lower().startswith("looks right") or t == "1"):
            return [Out("Please choose an option.", ["Looks right, continue", "Start again"])]
        self.step = "consent"
        return [Out(services.CONSENT_TEXT, ["I agree, submit", "Cancel"])]

    def _on_consent(self, t, file, loc):
        if t.lower().startswith("cancel") or t == "2":
            return self.stop()
        if not (t.lower().startswith("i agree") or t == "1"):
            return [Out("Please choose 'I agree, submit' or 'Cancel'.", ["I agree, submit", "Cancel"])]
        d = self.data
        submit = self.submit or services.submit_report
        try:
            res = submit(files=[(p.data, p.name, p.mime) for p in self.files], pasted_text="\n\n".join(self.pasted),
                         file_channel=self.channel, source=self.channel, category=d["category"], language=d["language"],
                         province=d["province"], town=d["town"], description=d["description"],
                         incident_when=d.get("when"), complainant_name=d.get("name"), contact_channel=self.channel,
                         contact_ref=self.contact_ref, answers=d.get("answers", {}),
                         safety={"unsafe": bool(d.get("unsafe"))} if d["category"] in ("abuse", "threats") else {},
                         location=d.get("location"), consent_given=True)
        except services.ReportError as e:
            return [Out(f"I couldn't submit that: {e}")]
        self.submitted.append(res["reference"])
        sensitive = d["category"] in ("abuse", "threats")
        self.data, self.files, self.pasted = {}, [], []
        self.step = "submitted"
        rejected = "".join(f"\nNot accepted: {x['name']} ({x['reason']})" for x in res.get("rejected", []))
        out = [Out(f"Report submitted.\n\nReference: {res['reference']}\nReceipt key: {res['receipt_key']}\n\n"
                   "Keep the receipt key private. With the reference it lets you check progress and download your case "
                   f"pack on the Ubufakazi Track page: {services.track_url()}\n"
                   "Send /pack at any time to get the case pack (PDF) in this chat.\n"
                   f"Your report was sent to the {res['station']} fraud desk (a fictional bank). The bank links it to other "
                   "victims and escalates the case to SAPS. No SAPS case number exists yet; keep your case pack." + rejected,
                   action={"type": "submitted", "id": res["id"], "reference": res["reference"],
                           "receipt_key": res["receipt_key"], "sensitive": sensitive})]
        if sensitive:
            out.append(Out("Should I send your case pack (PDF) here in this chat? Choose 'No' if someone else can see this "
                           "phone. You can always download it later on the Track page.", ["Yes, send it", "No"],
                           action={"type": "ask_send_pack"}))
            self.step = "pack_choice"
        return out

    def _on_pack_choice(self, t, file, loc):
        low = t.lower().strip()
        if low.startswith(("yes", "send", "pdf", "ok", "please")) or low == "1":
            self.step = "submitted"
            return [Out("Preparing your case pack (PDF)…", action={"type": "send_pack", "reference": self.submitted[-1]})]
        if low.startswith(("no", "don't", "dont", "not now")) or low == "2":
            self.step = "submitted"
            return [Out("OK, I won't send it here. When it's safe, send /pack to get it in this chat, or use the "
                        "Track page with your reference and receipt key.")]
        return [Out("Should I send your case pack (PDF) here? Tap 'Yes, send it' or 'No'.", ["Yes, send it", "No"])]
