# Ubufakazi 2.0: engineering notes

Ubufakazi 2.0 adds a real backend to the MVP. The static MVP in `site/` is unchanged and still works on its own (Netlify). When the 2.0 server serves the same site, a "2.0 is live" band appears on the landing page.

> **Demonstration only.** The stations, the bank (DemoBank) and all earlier reports are fictional. Nothing is connected to SAPS or to any bank. No CAS numbers are issued. Use the demo evidence kit or your own test data.

## Run it (about two minutes)

```bash
cd server
pip install -r requirements.txt
python -m ubufakazi_server.setup          # creates .env with random secrets, the database, demo accounts and 80 synthetic reports
uvicorn ubufakazi_server.app:app --port 8000
```

Open http://localhost:8000. Demo passwords are written to `server/DEMO-CREDENTIALS.txt`. This file is git-ignored and never committed. Every account uses two-factor codes. To get the current code on stage, run:

```bash
python -m ubufakazi_server.totp officer.mthatha
```

You can also scan the `otpauth://` link from the credentials file into an authenticator app.

| Page | What it is |
|---|---|
| `/` | Home: cinematic landing page (canvas globe, live aggregate counts from the demo database) |
| `/report` | Report a scam (same pipeline as Telegram), with Quick exit, browser-side fingerprints and a warning builder on the receipt |
| `/track` | Track a case with reference + private receipt key; case pack download; add evidence; share a warning |
| `/share` | Social-media scam warning builder (image + text, WhatsApp / X / Facebook / download). Never includes names, references, account numbers or evidence |
| `/verify` | SHA-256 check in the browser, nothing uploaded |
| `/resources`, `/about` | What to do after a scam (numbers from gov.za), how linking works, privacy, limitations |
| `/police` | Investigator dashboard: overview, case queue, evidence inventory, scam network (filters + details panel), audit, integrations |
| `/bank-demo` | Fictional DemoBank fraud-review simulation |
| `/integrations` | Honest status of what is connected |
| `/mvp` | The original browser-only MVP (also what Netlify serves) |

Design: one stylesheet (`web/console.css`) with self-hosted Space Grotesk / Inter / JetBrains Mono (SIL OFL), no CDN and a strict
CSP (no inline scripts or styles). Public pages are generated from one header/footer by `server/scripts/build_pages.py`.
The globe is plain canvas 2D using Natural Earth land dots (public domain); no React or 3D library was added, so the
existing stack, tests and deployment stay unchanged.

**Telegram.** Create a bot with @BotFather and put the token in `server/.env` as `TELEGRAM_BOT_TOKEN=...` (never in code or chat). Restart the server. The bot starts inside the server process using long polling, so it needs no public URL.

**AI reading of media (optional).** Set `GEMINI_API_KEY`. Without it, screenshots, voice notes and scans are still stored and hashed, but they are marked "not processed". Nothing is guessed.

**Tests:**

```bash
cd server && python -m pytest -q
```

## Host it online (free): Render + Neon

The server is one Docker container (website, police and bank consoles, API and Telegram bot). The database **and the
evidence files** live in a free Neon Postgres database, so nothing is lost when the free web service restarts.
Originals in the database are insert-only: a trigger refuses any UPDATE.

1. **Neon** ([neon.com](https://neon.com), free, no card): create a project in region *AWS Europe Central (Frankfurt)*.
   Copy the connection string (`postgresql://...`).
2. **Render** ([render.com](https://render.com)): **New > Blueprint**, pick `Don4chnge/ubufakazi`. Render reads
   `render.yaml` (branch `ubufakazi-2`, Docker, free plan, Frankfurt). Paste the Neon string into `DATABASE_URL`.
   `UBF_SECRET_KEY`, `UBF_HMAC_KEY` and `UBF_DEMO_SEED` are generated for you.
3. After the first deploy, set `UBF_PUBLIC_BASE_URL` to your `https://....onrender.com` address (Secure cookies).
4. **Keep it awake:** a free Render service sleeps after 15 minutes without visitors (and the Telegram bot sleeps with
   it). Add a free monitor (e.g. UptimeRobot or cron-job.org) that opens `https://<your-app>/api/health` every 10 minutes.
   One always-on service fits in Render's 750 free hours per month.
5. **Demo logins:** copy `UBF_DEMO_SEED` from Render's Environment tab into your local `server/.env`, then run
   `python -m ubufakazi_server.creds` for each account's password, 2FA setup key and current code.

The first start creates the tables, demo accounts and the 80 synthetic reports; later starts keep everything.
Any Docker host with a persistent volume also works (mount it at `/data`; see `railway.json`).

## Demo script (5 minutes)

1. **Telegram or `/report`.** Report as "Lerato" in Mthatha, Eastern Cape, using `site/demo-kit/case1-*` files.
   - Each file shows a SHA-256 fingerprint as it arrives.
   - You get a reference and a receipt key.
   - The case pack PDF arrives in the chat or downloads from the page.
2. **`/police` as `officer.mthatha`.**
   - Sign in with a password plus a two-factor code.
   - The new report is in the queue with **6+ leads**.
   - Open it. The tabs are Overview (extracted facts, marked unverified), Statement (5 languages), Evidence (Verify re-hashes the stored original) and Leads & graph.
3. **Leads & graph.** The same DemoBank account, phone, website and message template link Lerato to reports at other stations.
   - Those reports show as **restricted**: Mthatha cannot read Johannesburg's files.
   - Sign in as `admin` to see the whole network.
4. **`/bank-demo` as `bank.reviewer`.**
   - Account `•••• 8359` is high priority, with 7+ reports across 5 provinces.
   - The bank sees no names, references or statements. Its buttons are simulated and audited.
5. **Admin → Audit log.** Shows "Chain intact". Explain the hash chain.

## Architecture

```
Telegram (long polling) ─┐
Web form (/report) ──────┼─► conversation.py / app.py ─► services.submit_report
                         │        (consent first)            │ originals → storage.py (magic-byte check, random name, read-only, SHA-256)
                         │                                   ▼
                         │                     services.process_report (background worker)
                         │                       derivatives (text / PDF text / optional AI) kept separate
                         │                       extract.py (MVP rules, ported) → facts, timeline
                         │                       writing.py → statements in 5 languages + bank report
                         │                       intel.py → HMAC identifiers, explainable matches, bank alerts
                         ▼
             SQLite (or Postgres via DATABASE_URL) + hash-chained audit log
                         ▼
   /police (station-isolated)   /bank-demo (masked, no victim data)   casepack.py (PDF)
```

- **FastAPI + SQLAlchemy 2.** SQLite for the laptop demo. `DATABASE_URL` accepts Postgres or Supabase.
- **Accounts.**
  - Passwords are hashed with Argon2id. Every account has TOTP two-factor.
  - Accounts lock for 15 minutes after 5 failed attempts. Login is rate-limited.
  - Sessions use a random token stored only as a hash, in an HttpOnly, SameSite=Strict cookie.
  - Each session has its own CSRF token, required on every change.
- **Station isolation.**
  - Every police query is filtered by the officer's stations.
  - A report at another station returns 404 (exactly like a missing one), so references cannot be probed.
  - In leads and the graph, another station's report appears only as a **restricted stub**: station name and signal kinds, with no reference, amount, date or identifiers.
- **Evidence.**
  - Type is detected from file bytes, not the file name. Executables and archives are rejected.
  - Files are stored under a random UUID and set read-only. Names are sanitised.
  - Downloads are always `application/octet-stream` attachments with a sandbox CSP.
  - Image previews use blob URLs.
  - Verify re-hashes the stored bytes.
- **Identifiers.** Matching is done by HMAC-SHA256 with a server-only key (`UBF_HMAC_KEY`). The MVP's demo key in `site/` is separate and only used by the static demo. A test checks that the server keys never appear in browser files.
- **Audit log.**
  - Append-only and hash-chained: each event hash covers the previous one.
  - Records report creation, evidence receipt, views, downloads, verifications, status changes, notes, packs, logins and bank actions.
  - `verify_chain` finds the first altered event.
- **Security headers.** Strict CSP (`script-src 'self'`, no inline scripts or styles), `frame-ancestors 'none'`, nosniff, no-referrer, and `no-store` on API and console pages.

## Intelligence rules (documented, not statistical)

| Signal | Rule |
|---|---|
| Account, phone, email, website domain, social profile, @username, payment reference | Same keyed hash in both reports |
| Message template | At least 35% of the shorter message set's three-word phrases also appear in the other (with at least 6 phrases). This is the MVP's threshold. |

- **Single lead:** one kind of signal.
- **Corroborated lead:** two or more kinds of signal.
- Conflicts are shown, for example the same account number with different bank names.
- No accuracy percentage is claimed. A lead is a reason to investigate, never proof: accounts can belong to money mules, and numbers can be recycled or spoofed.

## Acceptance tests (`server/tests/test_acceptance.py`)

| | Covers |
|---|---|
| **A** | Chatbot flow end to end, routing to the right demo station, consent stored, rounded location, Quick exit (`/stop`) at **every** step saves nothing, ID numbers refused, abuse path is safety-first and asks before sending the PDF |
| **B** | Originals byte-identical, read-only, hashed; executables, archives and empty files rejected; path traversal neutralised; tampering detected by Verify; complainant pack has no other victims' data; police pack has leads and custody |
| **C** | Sign-in required, wrong password, lockout, password without two-factor rejected, CSRF enforced, station isolation (404), roles separated, status workflow, downloads are attachments |
| **D** | Corroborated leads with reasons, restricted stubs for other stations, graph, identifier search by keyed hash, clusters, server keys absent from frontend files |
| **E** | Bank alerts masked, limited to DemoBank, contain no reference, name, phone or account number, simulated actions audited |
| **F** | Actions recorded, chain intact, editing a past event detected at that event |
| **G** | All pages served with CSP, integrations reported honestly, web report → track → pack → add evidence, rate limiting |
| **H** | The Python engine reproduces the MVP's type and amount on all 70 test-pack cases; the MVP site is still served |

## Known limitations (said out loud)

- **Not SAPS, not a bank.** These are fictional stations and a fictional bank. A real deployment needs SAPS approval, verified receiving channels and a POPIA impact assessment.
- **Timestamps.** "Received" is the server clock. Trusted RFC 3161 timestamps are not configured.
- **Tamper evidence, not tamper-proofing.** The hash chain and file hashes make changes detectable. An attacker with full server access could still delete data. Hourly anchoring of the audit head to an external log would harden this.
- **Hosting.** One container with one volume. Back up `/data` if real use ever follows; the demo data is synthetic.
- **Single process.** The rate limiter is in memory. The audit chain relies on one server process (the bot runs inside it). Multi-instance deployment needs a database-level lock or sequence for the chain.
- **No migrations tool yet.** The schema is created with `create_all`. For changes during the demo, use `setup --reset`.
- **Media.** Images, voice notes and scans are read only when `GEMINI_API_KEY` is set, and the output is always labelled AI-generated and unverified.
- **No live online search.** Ubufakazi does not scrape social media, look up account holders or track anyone. It only compares identifiers that victims themselves reported.
- **WhatsApp.** The adapter is not built. The conversation engine is channel-neutral, so it can be added later.
- **Interface language.** The chatbot interface is in English. Statements are drafted in English, isiZulu, isiXhosa, Afrikaans or Sesotho. The translations should be reviewed by native speakers.
