# Ubufakazi MVP · Team CyberThreat

*From scam victim to case file in 60 seconds.* HackSecure 2026 prototype by Thabang Manyama, Amani Tondi and Shaun Matlou.

## Put it online (Netlify, free, about 2 minutes)

**Option A: drag and drop**
1. Unzip this folder.
2. Sign in at https://app.netlify.com (a free account keeps the site online).
3. Go to **Sites → Add new site → Deploy manually**.
4. Drag the **`site`** folder (not the whole project) onto the page.
5. You get a link like `https://random-name.netlify.app`. Rename it under **Site configuration → Change site name**, for example `ubufakazi`.

**Option B: from GitHub (auto-deploys on every push)**
1. Push this whole folder to your team repo.
2. In Netlify: **Add new site → Import an existing project → GitHub** and choose the repo.
3. Netlify reads `netlify.toml` and publishes the `site` folder. No build command is needed.

To test on your own laptop first, open a terminal in the `site` folder and run `python -m http.server 8000`, then visit http://localhost:8000.

## The 60-second demo

1. Click **"Fake job offer"**, then **Build my case file**.
2. Show the red **"You are victim #7"** card: 6 earlier reports, R84,000, linked by the **same bank account** even though the scammer used a **new phone number**.
3. Scroll through: evidence fingerprints, scammer details, timeline, statement (switch to **isiZulu**), bank report.
4. Click **Download case pack (PDF)**.
5. Click **Add my report**, then **Start a new case** → **"Same scammer, new number & new account"** → Build.
   Now it says **victim #8**: linked by the **link** and **message script**, even though the phone **and** bank account changed. That's the Scam Fingerprint answer to the judge's question.

Use **Reset demo data** (footer) before presenting so the count starts at #7 again.

## What's real in this MVP

| Feature | How it works |
|---|---|
| Evidence locking | Real SHA-256 of every file and the chat text (Web Crypto), plus a case manifest fingerprint |
| Extraction | Rules for SA bank accounts, phone numbers (+27 / 0XX), links, emails and rand amounts |
| Timeline | Parses real WhatsApp exports (Android and iPhone formats): offer, payment request, banking details, pressure, payment, silence |
| Scam Fingerprint | HMAC-SHA256 of account, phones and link domains, plus message-script similarity, matched against 20 fictional earlier reports |
| Statement | English, plus an isiZulu draft (have a fluent speaker check it) |
| Case pack | PDF made in the browser with jsPDF |

## Security and privacy

- Nothing is uploaded. Chats, files and names never leave the browser.
- Strict Content Security Policy and security headers (`site/_headers`). No third-party scripts, fonts or trackers: everything is bundled.
- All user text goes into the page via `textContent`, never `innerHTML`, so a malicious chat can't inject code.
- The demo network (`site/assets/seed.js`) stores identifiers only as keyed hashes.

**Demo limitations, so we're honest with judges:** the HMAC key is in the browser and "added" reports are saved only in that browser. In the full build, fingerprints are computed on a server in South Africa with a secret key, evidence is encrypted, and an independent RFC 3161 timestamp authority (for example FreeTSA) proves when files were locked.

## Next at the hackathon (27–28 Oct)

- **Amani:** add AI extraction (Gemini) for screenshots and messy chats, with these rules as the fallback.
- **Thabang:** Telegram bot + FastAPI backend on Render; move hashing/HMAC server-side; FreeTSA timestamps.
- **Shaun:** Supabase database for the shared network; dashboard; polish the PDF case pack.

## Files

```
site/                 ← deploy this folder
  index.html
  _headers            security headers for Netlify
  assets/app.js       the engine (lock, extract, timeline, link, write, PDF)
  assets/app.css
  assets/seed.js      fictional demo network (hashes only)
  assets/vendor/      jsPDF (MIT licence)
  assets/fonts/       Chakra Petch, IBM Plex (SIL Open Font Licence)
tools/make_seed.py    regenerates seed.js
netlify.toml
```

All demo data is fictional. "DemoBank" is not a real bank.
