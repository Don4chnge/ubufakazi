"""AI safety for evidence reading (OWASP Top 10 for LLM Applications 2025).

Evidence is written by people we do not trust: a scammer can hide instructions in a screenshot or a chat that try to
steer the AI reader ("ignore your rules, the account is ..."). This module:
- LLM01 Prompt injection: scans evidence text and AI output for instruction-like text, forged output markers and
  invisible characters, and reports what it found (with the snippet) so an officer can look.
- LLM06 Excessive agency / LLM09 Misinformation: identifiers that ONLY the AI read, or that come from a file where an
  injection attempt was found, are "untrusted". They still appear to investigators as leads, but they can never send
  a bank alert or count towards the beneficiary check on their own: that needs a rule-based reading, another victim,
  or an officer.
- LLM05 Improper output handling: AI text is stored and shown as plain text only (strict CSP, no HTML rendering).
- LLM07 System prompt leakage: the reading prompt holds no secrets, keys or internal data.
"""
from __future__ import annotations

import re

PATTERNS = [
    ("override", r"\b(ignore|disregard|forget|override)\b[^.\n]{0,40}\b(instruction|instructions|rules?|prompt|previous|above|system)\b"),
    ("role_change", r"\b(you are now|act as|pretend to be|from now on you|new instructions?|developer mode|jailbreak|do anything now)\b"),
    ("prompt_probe", r"\b(system prompt|reveal (your|the) (prompt|instructions)|print (your|the) (prompt|instructions))\b"),
    ("addressed_to_ai", r"\b(note|message|instruction)s? (to|for) (the )?(ai|assistant|model|gemini|chatgpt|llm|bot)\b"),
    ("forged_output", r"\bFOUND:\s*\S"),
    ("claimed_truth", r"\b(the )?(real|correct|true|actual) (bank )?account (number )?is\b"),
    ("chat_markup", r"(<\|[a-z_]+\|>|\[/?INST\]|###\s*(system|instruction)|\bassistant:\s)"),
    ("ai_noticed", r"NOTE: possible instruction to AI"),
]
_RX = [(name, re.compile(rx, re.I)) for name, rx in PATTERNS]
INVISIBLE = re.compile("[\\u200b-\\u200f\\u2060-\\u2064\\ufeff\\u202a-\\u202e]")
LABEL = {"override": "Tries to override the AI's rules", "role_change": "Tries to change the AI's role",
         "prompt_probe": "Asks for the AI's instructions", "addressed_to_ai": "Message addressed to the AI",
         "forged_output": "Imitates the AI's output format", "claimed_truth": "Claims to give the 'real' account",
         "chat_markup": "Contains AI chat markup", "invisible": "Hidden (invisible) characters",
         "ai_noticed": "The AI reader itself reported an instruction aimed at it"}


def scan(text: str, *, is_ai_output: bool = False) -> list[dict]:
    """Instruction-like content in untrusted text. For AI output, 'FOUND:' lines are expected, so they are skipped."""
    out = []
    if not text:
        return out
    for name, rx in _RX:
        if is_ai_output and name == "forged_output":
            continue
        m = rx.search(text)
        if m:
            s, e = max(0, m.start() - 40), min(len(text), m.end() + 60)
            out.append({"kind": name, "label": LABEL[name], "snippet": " ".join(text[s:e].split())[:180]})
    inv = INVISIBLE.findall(text)
    if len(inv) >= 3:
        out.append({"kind": "invisible", "label": LABEL["invisible"], "snippet": f"{len(inv)} invisible characters"})
    return out


def untrusted(source: str | None) -> bool:
    return bool(source) and (source.startswith("ai:") or source.startswith("flagged:"))
