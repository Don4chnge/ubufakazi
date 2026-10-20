"""Runs every test-pack case through the site in a headless browser and records what it shows.

Needs Playwright with Chromium. Run from the repo root:
    python3 tools/validate_test_pack.py
Writes tools/test-results.json, then run:  python3 tools/make_test_pack.py --guide
"""
import json
import re
import pathlib
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
PACK = SITE / "test-pack"
LANG = {"English": "en", "isiZulu": "zu", "isiXhosa": "xh", "Afrikaans": "af", "Sesotho": "st"}
TYPE_LABEL = {"job": "Fake job offer", "marketplace": "Online seller / Marketplace", "romance": "Romance scam",
              "investment": "Investment / crypto scam", "parcel": "Courier / parcel fee", "sars": "Fake SARS refund",
              "other": "Scam"}


def rand(n):
    return "R" + f"{n:,}".replace(",", " ")


def run_case(pg, c):
    folder = PACK / "cases" / c["folder"]
    pg.set_input_files("#chatFile", str(folder / c["chat"]))
    pg.wait_for_timeout(150)
    pg.set_input_files("#evidence", [str(folder / p) for p in c["pops"]])
    pg.select_option("#lang", LANG[c["lang"]])
    pg.click("#buildBtn")
    pg.wait_for_selector("#results:not([hidden])", timeout=15000)
    pg.wait_for_timeout(150)
    head = pg.inner_text("#linkCard .link-head")
    victim = pg.locator("#linkCard .victim-no").inner_text().split("\n")[0] if pg.locator("#linkCard .victim-no").count() else ""
    facts = pg.evaluate("""() => { const o = {}; const dl = document.querySelector('#facts');
      let k = null; for (const el of dl.children) { if (el.tagName === 'DT') k = el.textContent.trim().toUpperCase(); else o[k] = el.innerText.trim(); } return o; }""")
    signals = pg.evaluate("() => [...document.querySelectorAll('#linkCard .sig.on b')].map(b => b.textContent.trim())")
    statement = pg.input_value("#statement")
    rows = pg.locator("#hashTable tbody tr").count()
    return {"head": head, "victim": victim, "facts": facts, "signals": signals, "statement_ok": len(statement) > 200, "evidence_rows": rows}


def summary(c, r):
    f = r["facts"]
    found = []
    if f.get("BANK ACCOUNTS", "None found") != "None found":
        found.append("account")
    phones = [x for x in f.get("PHONE NUMBERS", "").split("\n") if x and x != "None found"]
    if phones:
        found.append(f"{len(phones)} phone number{'s' if len(phones) > 1 else ''}")
    if f.get("LINKS", "None found") != "None found":
        found.append("link")
    paid = f.get("AMOUNT PAID", "")
    if paid.startswith("R"):
        found.append(paid + " paid")
    found.append(f.get("SCAM TYPE", ""))
    if r["victim"]:
        m = re.search(r"BY (\d+) OTHER .*LOSSES: (R[\d ]+)", r["head"].upper())
        n, amt = (m.group(1), m.group(2).strip()) if m else ("?", "?")
        lead = f"Victim {r['victim']}: linked to {n} earlier report{'s' if n != '1' else ''} ({amt} lost)."
        if r["signals"]:
            lead += f" Linked by {', '.join(s.lower() for s in r['signals'])}."
    else:
        lead = "No earlier reports match."
    return f"{lead} Found: {', '.join(found)}."


def main():
    cases = json.loads((PACK / "cases.json").read_text())
    srv = subprocess.Popen([sys.executable, "-m", "http.server", "8811", "--bind", "127.0.0.1"], cwd=SITE,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    results, problems, errors = {}, [], []
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(viewport={"width": 1366, "height": 900})
            pg.on("pageerror", lambda e: errors.append(str(e)))
            pg.goto("http://127.0.0.1:8811/")
            for c in cases:
                pg.evaluate("localStorage.clear()")
                pg.goto("http://127.0.0.1:8811/")
                r = run_case(pg, c)
                r["summary"] = summary(c, r)
                results[c["id"]] = r
                f = r["facts"]
                exp_paid = rand(c["paid_total"])
                if f.get("AMOUNT PAID") != exp_paid:
                    problems.append(f"{c['id']}: paid {f.get('AMOUNT PAID')!r} expected {exp_paid}")
                if f.get("SCAM TYPE") != TYPE_LABEL[c["type"]]:
                    problems.append(f"{c['id']}: type {f.get('SCAM TYPE')!r} expected {TYPE_LABEL[c['type']]}")
                if f.get("BANK ACCOUNTS", "None found") == "None found":
                    problems.append(f"{c['id']}: no account found")
                if not r["statement_ok"]:
                    problems.append(f"{c['id']}: statement too short")
                if c["note"].startswith(("s1", "s2", "s3")) and not r["victim"]:
                    problems.append(f"{c['id']}: expected a syndicate link, got none")
                if not c["note"] and r["victim"] and c["type"] != "sars":
                    problems.append(f"{c['id']}: unexpected link: {r['head']}")
            # linked-set checks: add the first report, then build the second
            for first, second in [("EN-10", "EN-11"), ("EN-19", "EN-20")]:
                pg.evaluate("localStorage.clear()"); pg.goto("http://127.0.0.1:8811/")
                cmap = {c["id"]: c for c in cases}
                run_case(pg, cmap[first]); pg.click("#consentBtn"); pg.wait_for_timeout(150)
                pg.goto("http://127.0.0.1:8811/")
                r = run_case(pg, cmap[second])
                print(f"linked-set {first} -> {second}: {r['head']}")
                if not r["victim"]:
                    problems.append(f"{second}: did not link to {first} after adding it")
            b.close()
    finally:
        srv.terminate()
    (ROOT / "tools" / "test-results.json").write_text(json.dumps(results, indent=1))
    for cid, r in results.items():
        print(cid, "|", r["summary"])
    print("\nPROBLEMS:", problems or "none")
    print("PAGE ERRORS:", errors or "none")


if __name__ == "__main__":
    main()
