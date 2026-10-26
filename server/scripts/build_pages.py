"""Generates the public HTML pages in ubufakazi_server/web/ from one shared header/footer.

    python scripts/build_pages.py

Edit the page bodies in PAGES below, then re-run. Each page loads only same-origin CSS/JS (strict CSP).
"""
from __future__ import annotations

import pathlib

WEB = pathlib.Path(__file__).resolve().parent.parent / "ubufakazi_server" / "web"

BRAND_SVG = ('<svg viewBox="0 0 32 32" aria-hidden="true"><path d="M16 3l10 4v8.2c0 6.6-4.3 11.3-10 13.8C10.3 26.5 6 21.8 6 15.2V7z"/>'
             '<path d="M11 17.2c.5-3.2 2.5-5.4 5-5.4s4.5 2.2 5 5.4"/><path d="M13.2 20.6c0-2.6 1.2-4.4 2.8-4.4s2.8 1.8 2.8 4.4"/>'
             '<path d="M16 19.4v4.2"/></svg>')
NAV = [("/", "Home"), ("/report", "Report a Scam"), ("/track", "Track a Case"), ("/share", "Share a Warning"),
       ("/resources", "Resources"), ("/about", "About")]
GITHUB = "https://github.com/Don4chnge/ubufakazi"


def header(active: str, quick_exit: bool = False) -> str:
    links = "".join(f'<a href="{h}"{" aria-current=\"page\"" if h == active else ""}>{t}</a>' for h, t in NAV)
    exit_btn = ('<button class="btn btn-danger btn-small" id="quickExit" type="button" '
                'title="Leave this page immediately (Shift+Esc)">Quick exit</button>') if quick_exit else ""
    return f'''<a class="skip" href="#main">Skip to content</a>
<header class="topbar">
  <a class="brand" href="/" aria-label="Ubufakazi home">{BRAND_SVG}<span class="brand-text"><b>Ubufakazi</b><small>Evidence. Justice. Safer communities.</small></span></a>
  <nav class="pubnav" id="pubnav" aria-label="Main">{links}</nav>
  <span class="spacer"></span>
  <div class="nav-actions">
    {exit_btn}
    <a class="btn btn-ghost btn-small" href="/police">Investigator login</a>
    <a class="btn btn-primary btn-small" href="/report">Report a Scam</a>
    <button class="menu-btn" type="button" aria-label="Menu" aria-controls="pubnav" aria-expanded="false"><svg viewBox="0 0 24 24"><path d="M4 7h16M4 12h16M4 17h16"/></svg></button>
  </div>
</header>'''


FOOTER = f'''<footer class="site-foot">
  <div class="in">
    <div>
      <a class="brand" href="/">{BRAND_SVG}<span class="brand-text"><b>Ubufakazi</b><small>Evidence. Justice. Safer communities.</small></span></a>
      <p class="muted small foot-blurb">Helps scam victims in South Africa preserve evidence, prepare a case pack for the police station and connect reports about the same scammer.</p>
      <div class="social"><a href="{GITHUB}" target="_blank" rel="noopener" aria-label="Source code on GitHub"><svg viewBox="0 0 24 24"><path d="M12 .5a11.5 11.5 0 0 0-3.64 22.41c.58.1.79-.25.79-.56v-2c-3.2.7-3.88-1.37-3.88-1.37-.52-1.33-1.28-1.69-1.28-1.69-1.05-.71.08-.7.08-.7 1.16.08 1.77 1.19 1.77 1.19 1.03 1.77 2.7 1.26 3.36.96.1-.75.4-1.26.73-1.55-2.55-.29-5.24-1.28-5.24-5.69 0-1.26.45-2.29 1.19-3.1-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.17 1.18a11 11 0 0 1 5.78 0c2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.23 2.76.11 3.05.74.81 1.19 1.84 1.19 3.1 0 4.42-2.7 5.39-5.26 5.68.41.36.78 1.06.78 2.14v3.17c0 .31.21.67.8.56A11.5 11.5 0 0 0 12 .5z"/></svg></a></div>
    </div>
    <div><h4>For victims</h4><ul><li><a href="/report">Report a scam</a></li><li><a href="/track">Track a case</a></li><li><a href="/share">Share a warning</a></li><li><a href="/verify">Verify a file</a></li><li><a href="/resources">Get help now</a></li></ul></div>
    <div><h4>For investigators</h4><ul><li><a href="/police">Investigator dashboard</a></li><li><a href="/bank-demo">Bank review (fictional)</a></li><li><a href="/integrations">System status</a></li></ul></div>
    <div><h4>Project</h4><ul><li><a href="/about">About Ubufakazi</a></li><li><a href="{GITHUB}" target="_blank" rel="noopener">Source code</a></li><li><a href="/privacy">Privacy &amp; data deletion</a></li><li><a href="/mvp">Original MVP (offline)</a></li></ul></div>
  </div>
  <div class="legal"><span>Demonstration prototype by Team CyberThreat · HackSecure 2026. Fictional stations, fictional bank and synthetic data.</span><span>Not affiliated with SAPS or any bank. In danger now? Call 10111.</span></div>
</footer>'''


def page(path: str, title: str, desc: str, body: str, scripts: list[str], quick_exit=False, extra_css: list[str] = ()) -> str:
    css = "".join(f'\n<link rel="stylesheet" href="/app/{c}">' for c in ["console.css", *extra_css])
    js = "".join(f'\n<script src="/app/{s}"></script>' for s in ["common.js", *scripts])
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<meta name="theme-color" content="#030812">{'\n<meta name="robots" content="noindex, nofollow">' if path == "/demo-logins" else ""}
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="icon" href="/app/favicon.svg" type="image/svg+xml">{css}
</head>
<body>
{header(path, quick_exit)}
{body}
{FOOTER}{js}
</body>
</html>
'''


SIMPLE = '''<main class="public" id="main">
  <div class="page-hero">
    <div class="kicker">{kicker}</div>
    <h1>{h1}</h1>
    <p class="lead-in">{lead}</p>
  </div>
  {pre}<div id="app"></div>
</main>'''

PAGES = {
    "report.html": dict(path="/report", title="Report a scam · Ubufakazi", quick_exit=True, scripts=["share.js", "report.js"],
        desc="Report a scam or crime, attach evidence, and get a draft statement and case pack to take to the police station.",
        body=SIMPLE.format(kicker="Step 1 · Collect", h1="Tell us what <span class=\"grad\">happened</span>",
            lead="Ubufakazi organises your evidence, fingerprints every file and prepares a draft statement and case pack for you to take to a police station. It is a demonstration: it is not SAPS and it does not open a case.",
            pre='<div class="notice"><b>In danger right now?</b>&nbsp;Call 10111. Gender-based violence: GBV Command Centre 0800 428 428 (free, 24 hours).</div>\n  <p class="hint">Prefer chatting? The same report can be made on Telegram or WhatsApp when those are connected (see <a href="/integrations">System status</a>).</p>\n  ')),
    "track.html": dict(path="/track", title="Track a case · Ubufakazi", scripts=["share.js", "track.js"],
        desc="Check the progress of your Ubufakazi report, see your evidence fingerprints, download your case pack and share a warning.",
        body=SIMPLE.format(kicker="Track", h1="Track your <span class=\"grad\">case</span>",
            lead="Enter the reference and private receipt key you received when you reported. Nobody else can see your report from here.", pre="")),
    "share.html": dict(path="/share", title="Share a scam warning · Ubufakazi", scripts=["share.js", "sharepage.js"],
        desc="Create a social-media scam warning to protect your community, without sharing anyone's private details.",
        body=SIMPLE.format(kicker="Warn your community", h1="Turn your report into a <span class=\"grad\">warning</span>",
            lead="Scammers reuse the same tricks. Make a ready-to-post warning for WhatsApp, Facebook, X or Instagram. Personal details, bank account numbers and case references are never included.", pre="")),
    "verify.html": dict(path="/verify", title="Verify a file · Ubufakazi", scripts=["verify.js"],
        desc="Check that an evidence file has not changed by comparing its SHA-256 fingerprint. Runs in your browser; nothing is uploaded.",
        body=SIMPLE.format(kicker="Step 2 · Preserve", h1="Has this file <span class=\"grad\">changed?</span>",
            lead="Choose a file and paste the SHA-256 fingerprint from your case pack. Your browser calculates the fingerprint itself: <b>the file never leaves this device</b>.", pre="")),
    "integrations.html": dict(path="/integrations", title="System status · Ubufakazi", scripts=["integrations.js"],
        desc="What is and is not connected in the Ubufakazi demonstration.",
        body=SIMPLE.format(kicker="System status", h1="What is <span class=\"grad\">connected</span>",
            lead="An honest list of what this demonstration can and cannot do right now. Nothing here is shown as connected unless it really is.", pre="")),
    "resources.html": dict(path="/resources", title="Get help · Ubufakazi", scripts=[],
        desc="What to do after a scam in South Africa: emergency numbers, your bank, the police station and protecting yourself.",
        body=open(pathlib.Path(__file__).with_name("resources_body.html"), encoding="utf-8").read() if pathlib.Path(__file__).with_name("resources_body.html").exists() else ""),
    "about.html": dict(path="/about", title="About · Ubufakazi", scripts=[],
        desc="Why Ubufakazi exists, how it protects evidence and privacy, and what it does not claim.",
        body=open(pathlib.Path(__file__).with_name("about_body.html"), encoding="utf-8").read() if pathlib.Path(__file__).with_name("about_body.html").exists() else ""),
    "privacy.html": dict(path="/privacy", title="Privacy policy · Ubufakazi", scripts=[],
        desc="How Ubufakazi handles reports and evidence sent through the website, Telegram and WhatsApp, and how to delete your data.",
        body=open(pathlib.Path(__file__).with_name("privacy_body.html"), encoding="utf-8").read()),
    "demo-logins.html": dict(path="/demo-logins", title="Demo logins helper · Ubufakazi", scripts=["demologins.js"],
        desc="Private helper for the demonstration accounts. Runs in your browser only.",
        body=SIMPLE.format(kicker="Team helper", h1="Demo <span class=\"grad\">logins</span>",
            lead="For Team CyberThreat: shows the demonstration accounts' passwords and live two-factor codes from the secret seed. Calculated in your browser; nothing leaves this device.", pre="")),
    "home.html": dict(path="/", title="Ubufakazi · Turn digital evidence into real justice", scripts=["land.js", "globe.js", "share.js", "home.js"],
        extra_css=["home.css"],
        desc="Ubufakazi helps scam victims in South Africa preserve digital evidence, prepare a case pack for the police and connect reports about the same scammer.",
        body=open(pathlib.Path(__file__).with_name("home_body.html"), encoding="utf-8").read() if pathlib.Path(__file__).with_name("home_body.html").exists() else ""),
}


def main():
    for name, p in PAGES.items():
        html = page(p["path"], p["title"], p["desc"], p["body"], p["scripts"], p.get("quick_exit", False), p.get("extra_css", []))
        (WEB / name).write_text(html, encoding="utf-8")
        print("wrote", name)


if __name__ == "__main__":
    main()
