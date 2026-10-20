<div align="center">

# Ubufakazi

### Evidence that holds up when it matters.

**From scam victim to police-ready case file in 60 seconds.**

[![Live demo](https://img.shields.io/badge/Live%20demo-ubufakazi.netlify.app-5CF2D6?style=for-the-badge&labelColor=0B1016)](https://ubufakazi.netlify.app)
[![Pitch deck](https://img.shields.io/badge/Pitch%20deck-PDF-FF8F72?style=for-the-badge&labelColor=0B1016)](docs/Ubufakazi_Hackathon_Deck.pdf)

[![Netlify](https://img.shields.io/badge/hosted%20on-Netlify-00C7B7?logo=netlify&logoColor=white)](https://ubufakazi.netlify.app)
![HackSecure 2026](https://img.shields.io/badge/HackSecure-2026-0B1016)
![Track](https://img.shields.io/badge/Track%204-Digital%20Forensics%20Lite-0B1016)
![Languages](https://img.shields.io/badge/statements-5%20SA%20languages-0B1016)
![Data](https://img.shields.io/badge/demo%20data-100%25%20fictional-0B1016)

**Team CyberThreat** · Thabang Manyama (team lead) · Amani Tondi · Shaun Matlou

</div>

![Ubufakazi landing screen](docs/screenshot-landing.jpg)

## Quick links

| What | Link |
|---|---|
| Live app | **https://ubufakazi.netlify.app** |
| Pitch deck (PDF) | [docs/Ubufakazi_Hackathon_Deck.pdf](docs/Ubufakazi_Hackathon_Deck.pdf) |
| Demo scammer to investigate | [ubufakazi.netlify.app/scam-demo](https://ubufakazi.netlify.app/scam-demo/) |
| Demo evidence kit (3 victims, zip) | [ubufakazi-demo-evidence-kit.zip](https://ubufakazi.netlify.app/demo-kit/ubufakazi-demo-evidence-kit.zip) |
| Test pack for judges (70 cases, zip) | [ubufakazi-test-pack.zip](https://ubufakazi.netlify.app/test-pack/ubufakazi-test-pack.zip) |
| Test pack guide (PDF) | [READ-ME-FIRST_test-pack-guide.pdf](https://ubufakazi.netlify.app/test-pack/READ-ME-FIRST_test-pack-guide.pdf) |

## The problem

South Africans lose billions of rand a year to scams: fake job offers, fake couriers, marketplace sellers, romance and crypto schemes. Most victims never get a case opened that goes anywhere, because:

- **Evidence is messy.** It sits in WhatsApp chats, screenshots and proof-of-payment slips that police and banks can't easily use, and that can be questioned later.
- **Every report looks small on its own.** One R3 500 loss gets ignored. Seven victims of the same syndicate is a case, but nobody connects them.
- **Scammers switch numbers.** Blocking one number does nothing when they use a new one the next day.

## What Ubufakazi does

*Ubufakazi* is isiZulu for "evidence" or "testimony".

1. **Lock the evidence.** Every chat, screenshot and payment slip gets a SHA-256 fingerprint the moment it's reported. If one pixel changes later, the fingerprint won't match.
2. **Pull out the scammer's details.** South African bank accounts, phone numbers (+27 / 0XX), links, emails and rand amounts are found automatically, along with a timeline of the scam: offer, payment request, pressure, payment, silence.
3. **Link the victims with a Scam Fingerprint.** Accounts, phones and link domains are stored only as keyed HMAC-SHA256 hashes, plus a fingerprint of the message script. That means a scammer who changes their number is still linked by the bank account, the site or the script.
4. **Write it up.** The app writes an affidavit-style statement in English, isiZulu, isiXhosa, Afrikaans or Sesotho, plus a bank fraud report and a downloadable PDF case pack.

![A case file showing victim #7 linked to 6 earlier reports](docs/screenshot-case-file.jpg)

## Try the 60-second demo

1. Open **https://ubufakazi.netlify.app** and click **Build a case file**.
2. Click **"Fake job offer"**, then **Build my case file**.
3. The red card says **"You are victim #7"**: 6 earlier reports and R84 000 lost, linked by the **same bank account** even though the scammer used a **new phone number**.
4. Scroll through the evidence fingerprints, scammer details, timeline, statement (switch languages with the tabs) and bank report. Click **Download case pack (PDF)**.
5. Click **Add my report**, then **Start a new case**, then **"Same scammer, new number & new account"**, then build.
   It now says **victim #8**, linked by the **link** and the **message script**, even though both the phone and the bank account changed.

Click **Reset demo data** in the footer before presenting, so the count starts at #7 again.

**Test it with your own files:** download the [test pack](https://ubufakazi.netlify.app/test-pack/ubufakazi-test-pack.zip). It has 70 fictional cases, each with a WhatsApp chat export and proof-of-payment PDFs: 50 in English and 5 each in isiZulu, isiXhosa, Afrikaans and Sesotho. The language is in every file name. Upload any case and compare the result with the guide PDF.

## What's real in this prototype

| Feature | How it works |
|---|---|
| Evidence locking | Real SHA-256 of every file and the chat text (Web Crypto API), plus a case manifest fingerprint |
| Extraction | Rules for SA bank accounts, phone numbers, links, emails and rand amounts, with keywords in 5 languages |
| Timeline | Parses real WhatsApp exports in both the Android and iPhone formats |
| Scam Fingerprint | HMAC-SHA256 of identifiers plus message-script similarity (3-word shingles), matched against a fictional network of 80 earlier reports and 3 syndicates |
| Statements | English, isiZulu, isiXhosa, Afrikaans and Sesotho drafts (have a fluent speaker check the translations) |
| Case pack | PDF made in the browser with jsPDF |
| Investigation material | A fictional scammer website, social profile and bank confirmation letter, all clearly labelled as demo content |
| Tested | All 70 test-pack cases pass an automated check (`tools/validate_test_pack.py`) |

## Security and privacy

- **Nothing is uploaded.** Chats, files and names never leave the browser in this prototype.
- **Strict security headers.** Content Security Policy, X-Frame-Options and related headers are set in `site/_headers`. There are no third-party scripts, trackers or font services: everything is bundled.
- **Safe rendering.** All user text goes into the page through `textContent`, never `innerHTML`, so a malicious chat can't inject code.
- **Hashed identifiers.** The demo network (`site/assets/seed.js`) stores scammer identifiers only as keyed hashes.
- **Consent first.** A report joins the network only when the victim clicks **Add my report**.

**Prototype limits:** the HMAC key is in the browser and added reports are saved only in that browser. In the full build, fingerprints are computed on a server in a South African cloud region with a secret key, evidence is encrypted, an independent RFC 3161 timestamp authority (such as FreeTSA) proves when files were locked, and the system is designed for POPIA compliance.

## Hackathon plan (27–28 October 2026)

| Who | Builds |
|---|---|
| **Thabang Manyama** | Telegram bot and FastAPI backend on Render, server-side HMAC and FreeTSA timestamps |
| **Amani Tondi** | Gemini AI extraction for screenshots and messy chats, with the current rules as the fallback |
| **Shaun Matlou** | Supabase database for the shared victim network, investigator dashboard, polished PDF case pack |

## Run it yourself

There's no build step: the site is plain HTML, CSS and JavaScript.

```bash
git clone https://github.com/Don4chnge/ubufakazi.git
cd ubufakazi/site
python3 -m http.server 8000
# open http://localhost:8000
```

**Deploy:** Netlify reads `netlify.toml` and publishes the `site` folder. Every push to `main` deploys automatically to https://ubufakazi.netlify.app.

## Project structure

```
site/                          the website (deployed to Netlify)
  index.html                   landing screen and case builder
  _headers                     security headers
  assets/app.js                engine: lock, extract, timeline, link, write, PDF
  assets/hero.js, hero.css     animated fingerprint landing screen
  assets/app.css               styles
  assets/seed.js               fictional network of 80 reports (hashes only)
  assets/vendor/               jsPDF (MIT licence)
  assets/fonts/                Oswald, Barlow, Barlow Condensed, IBM Plex Mono (SIL OFL)
  scam-demo/                   fictional scammer website, profile and bank letter
  demo-kit/                    3-victim evidence kit
  test-pack/                   70-case test pack, guide PDF and zip
docs/                          pitch deck PDF and screenshots
tools/
  make_seed.py                 builds the fictional network
  make_demo_kit.py             builds the demo evidence kit
  make_test_pack.py            builds the 70-case test pack
  validate_test_pack.py        runs every test case through the site in a headless browser
netlify.toml                   Netlify settings
```

## Disclaimer

All names, numbers, accounts, websites and reports in this project are **fictional** and made for demonstration only. "DemoBank" is not a real bank. Ubufakazi is a hackathon prototype, not legal advice, and it doesn't replace reporting to SAPS or your bank.

---

<div align="center">

**Team CyberThreat**, a threat to cybercriminals. HackSecure 2026.

</div>
