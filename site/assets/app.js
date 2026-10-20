/* Ubufakazi MVP · Team CyberThreat · HackSecure 2026
 *
 * Everything runs in the browser. No chat, file or name is uploaded anywhere.
 *  1. Lock:     SHA-256 fingerprint of every evidence file (Web Crypto).
 *  2. Extract:  rules for SA bank accounts, phone numbers, links, amounts.
 *  3. Timeline: parsed from WhatsApp chat exports (Android + iPhone formats).
 *  4. Link:     "Scam Fingerprint" = keyed hashes (HMAC-SHA256) of account,
 *               phones, link domains + message-script similarity, matched
 *               against the network of earlier reports (assets/seed.js).
 *  5. Write:    statement (English / isiZulu draft), bank report, PDF case pack.
 */
(function () {
  'use strict';

  // Demo only: in production this key lives on the server, never in the browser.
  const HMAC_KEY = 'ubufakazi-demo-key-2026';
  const SCRIPT_THRESHOLD = 0.35;
  const LOCAL_KEY = 'ubf-local-reports-v1';
  const SEED = window.UBF_SEED || { scripts: {}, reports: [] };

  // ---------------------------------------------------------------- helpers
  const $ = (sel, root = document) => root.querySelector(sel);
  const enc = new TextEncoder();
  const hex = (buf) => Array.from(new Uint8Array(buf), (b) => b.toString(16).padStart(2, '0')).join('');
  const sha256 = async (data) => hex(await crypto.subtle.digest('SHA-256', typeof data === 'string' ? enc.encode(data) : data));
  let keyPromise = null;
  const hmac = async (msg) => {
    keyPromise = keyPromise || crypto.subtle.importKey('raw', enc.encode(HMAC_KEY), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
    return hex(await crypto.subtle.sign('HMAC', await keyPromise, enc.encode(msg)));
  };
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  /** Build DOM safely: all text goes through textContent, never innerHTML. */
  function h(tag, attrs, ...kids) {
    const el = document.createElement(tag);
    if (attrs) for (const [k, v] of Object.entries(attrs)) {
      if (v == null || v === false) continue;
      if (k === 'class') el.className = v;
      else if (k === 'text') el.textContent = v;
      else el.setAttribute(k, v === true ? '' : v);
    }
    for (const kid of kids.flat()) if (kid != null && kid !== false) el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
    return el;
  }

  const rand = (n) => Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  const money = (n) => (n == null ? '—' : 'R' + rand(n) + (n % 1 ? ',' + String(Math.round((n % 1) * 100)).padStart(2, '0') : ''));
  const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  const MONTHS_ZU = ['Januwari', 'Februwari', 'Mashi', 'Ephreli', 'Meyi', 'Juni', 'Julayi', 'Agasti', 'Septhemba', 'Okthoba', 'Novemba', 'Disemba'];
  const pad = (n) => String(n).padStart(2, '0');
  const fmtDate = (d) => (d ? `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}` : null);
  const fmtDateZu = (d) => (d ? `${d.getDate()} ${MONTHS_ZU[d.getMonth()]} ${d.getFullYear()}` : null);
  const fmtTime = (d) => (d ? `${pad(d.getHours())}:${pad(d.getMinutes())}` : null);
  const fmtStamp = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  const fmtBytes = (n) => (n < 1024 ? n + ' B' : n < 1048576 ? (n / 1024).toFixed(1) + ' KB' : (n / 1048576).toFixed(1) + ' MB');
  const uniq = (arr, key = (x) => x) => { const s = new Set(); return arr.filter((x) => { const k = key(x); if (s.has(k)) return false; s.add(k); return true; }); };
  const clip = (s, n) => (s.length > n ? s.slice(0, n - 1).trimEnd() + '…' : s);
  const listText = (arr, and = 'and') => (arr.length <= 1 ? arr.join('') : arr.slice(0, -1).join(', ') + ` ${and} ` + arr[arr.length - 1]);

  function toast(msg) {
    const t = h('div', { class: 'toast', role: 'status', text: msg });
    document.body.append(t);
    setTimeout(() => t.remove(), 2200);
  }

  // ---------------------------------------------------------------- 1. chat parsing
  const RE_ANDROID = /^(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4}),?\s+(\d{1,2}):(\d{2})(?::\d{2})?\s*([ap]\.?\s?m\.?)?\s+-\s+([^:]{1,60}?):\s?(.*)$/i;
  const RE_IOS = /^\[(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4}),?\s+(\d{1,2}):(\d{2})(?::\d{2})?\s*([ap]\.?\s?m\.?)?\]\s*([^:]{1,60}?):\s?(.*)$/i;
  const RE_PLAIN = /^([A-Za-z][^:\n]{0,40}?):\s+(.+)$/;
  const FIELD_LABEL = /^(bank|acc(ount)?(\s*(no|number|name|holder))?|a\/c|ref(erence)?|branch(\s*code)?|name|amount|cell|tel|phone)$/i;

  function mkDate(m) {
    let [d, mo, y, hh, mm, ap] = [+m[1], +m[2], +m[3], +m[4], +m[5], m[6]];
    if (y < 100) y += 2000;
    if (ap) { const pm = /p/i.test(ap); if (pm && hh < 12) hh += 12; if (!pm && hh === 12) hh = 0; }
    if (mo > 12 && d <= 12) [d, mo] = [mo, d]; // tolerate MM/DD exports
    const dt = new Date(y, mo - 1, d, hh, mm);
    return isNaN(dt) ? null : dt;
  }

  function parseChat(raw) {
    const text = raw.replace(/[‎‏‪-‮﻿]/g, '').replace(/\r\n?/g, '\n');
    const lines = text.split('\n');
    const stamped = lines.some((l) => RE_ANDROID.test(l) || RE_IOS.test(l));
    const msgs = [];
    let cur = null;
    for (const line of lines) {
      if (!line.trim()) { if (cur) cur.text += '\n'; continue; }
      const m = line.match(RE_ANDROID) || line.match(RE_IOS);
      if (m) { cur = { date: mkDate(m), sender: m[7].trim(), text: m[8] }; msgs.push(cur); continue; }
      if (!stamped) {
        const p = line.match(RE_PLAIN);
        if (p && !FIELD_LABEL.test(p[1].trim()) && !/^https?$/i.test(p[1])) { cur = { date: null, sender: p[1].trim(), text: p[2] }; msgs.push(cur); continue; }
      }
      if (cur) cur.text += '\n' + line;
      else { cur = { date: null, sender: null, text: line }; msgs.push(cur); }
    }
    msgs.forEach((m, i) => { m.text = m.text.trim(); m.i = i; });
    return msgs.filter((m) => m.text);
  }

  // ---------------------------------------------------------------- 2. extraction
  const BANKS = ['DemoBank', 'Capitec', 'First National Bank', 'FNB', 'Absa', 'Nedbank', 'Standard Bank', 'TymeBank', 'Discovery Bank', 'African Bank', 'Investec', 'Bidvest Bank', 'Old Mutual', 'Access Bank', 'Postbank'];
  const RE_BANK = new RegExp('\\b(' + BANKS.map((b) => b.replace(/ /g, '\\s+')).join('|') + ')\\b', 'i');
  const RE_ACC_CTX = /(acc(ount)?\.?\s*(no|number|nr|#)?|a\/c|rekening|bank(ing)? details|deposit (in)?to|pay (in)?to|eft (in)?to)\s*[:\-]?\s*$/i;
  const RE_DIGITS = /(?<![\d+])\d(?:[ \-]?\d){7,11}(?!\d)/g;
  const RE_PHONE = /(?<![\d])(?:\+27|0027|0)(?:[ \-]?\(?\d\)?){9}(?![\d])/g;
  const RE_AMOUNT = /\bR\s?(\d{1,3}(?:[ , ]\d{3})+|\d+)(?:[.,](\d{2}))?(?!\d)|\b(\d{1,3}(?:[ ,]\d{3})+|\d+)\s?(?:rand|zar)\b/gi;
  const RE_URL = /\bhttps?:\/\/[^\s<>"')\]]+/gi;
  const RE_DOMAIN = /(?<![@\w.-])((?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:co\.za|org\.za|net\.za|gov\.za|com|net|org|info|xyz|online|site|top|shop|store|club|live|link|click|ly|io|app|me|biz|icu|vip))(\/[^\s<>"')\]]*)?/gi;
  const RE_EMAIL = /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi;
  const RE_PAID = /\b(i('ve| have)? (just )?(paid|sent|transferred|deposited|made (the )?payment)|paid|sent the|transferred|deposited|eft (done|made)|pop|proof of payment|payment (done|made|sent))\b/i;
  const RE_ASK = /\b(pay|fee|deposit|transfer|send|eft|payment|charge|release)\b/i;
  const RE_PRESSURE = /\b(today|urgent(ly)?|immediately|asap|limited|last chance|before (monday|tomorrow|friday|\d)|lose (the|your)|within \d+|right now|expires?)\b/i;
  const RE_GONE = /\b(blocked|not going through|not answering|no answer|unreachable|ignor(ing|ed)|please answer|switched off|deleted)\b/i;

  function normPhone(s) {
    let d = s.replace(/\D/g, '');
    if (d.startsWith('0027')) d = d.slice(4); else if (d.startsWith('27') && d.length === 11) d = d.slice(2); else if (d.startsWith('0')) d = d.slice(1);
    return d.length === 9 && /^[1-8]/.test(d) ? '+27' + d : null;
  }
  const showPhone = (p) => '0' + p.slice(3, 5) + ' ' + p.slice(5, 8) + ' ' + p.slice(8);
  function regDomain(host) {
    const parts = host.toLowerCase().replace(/^www\./, '').split('.');
    const n = /\.(co|org|net|gov|ac)\.za$/.test(host.toLowerCase()) ? 3 : 2;
    return parts.slice(-n).join('.');
  }
  const showAcc = (a) => a.replace(/(\d{4})(?=\d)/g, '$1 ');

  function findBank(text, idx) {
    let best = null;
    const re = new RegExp(RE_BANK.source, 'gi');
    let m;
    while ((m = re.exec(text))) {
      const dist = Math.abs(m.index - idx);
      if (!best || dist < best.dist) best = { name: canonicalBank(m[1]), dist };
    }
    return best && best.dist < 160 ? best.name : null;
  }
  function canonicalBank(s) {
    const t = s.replace(/\s+/g, ' ').toLowerCase();
    if (t === 'first national bank') return 'FNB';
    return BANKS.find((b) => b.toLowerCase() === t) || s;
  }

  function extract(msgs, scammerName) {
    const out = { accounts: [], phones: [], links: [], emails: [], paid: [], requested: [], banks: [] };
    const byScammer = (m) => scammerName && m.sender === scammerName;
    const byVictim = (m) => scammerName && m.sender && m.sender !== scammerName;

    for (const m of msgs) {
      const t = m.text;
      const taken = [];
      // bank accounts: long digit runs with account words just before them, or a bank name close by
      for (const d of t.matchAll(RE_DIGITS)) {
        const digits = d[0].replace(/\D/g, '');
        if (digits.length < 8 || digits.length > 12) continue;
        const before = t.slice(Math.max(0, d.index - 45), d.index);
        const lineStart = t.lastIndexOf('\n', d.index) + 1;
        const lineBefore = t.slice(lineStart, d.index);
        const bank = findBank(t, d.index);
        const ctx = RE_ACC_CTX.test(before) || /acc|a\/c|account/i.test(lineBefore);
        if (ctx || (bank && !/^0[6-8]/.test(digits))) {
          out.accounts.push({ value: digits, bank, msg: m.i });
          taken.push([d.index, d.index + d[0].length]);
        }
      }
      // phone numbers (skip spans already taken as accounts)
      for (const p of t.matchAll(RE_PHONE)) {
        if (taken.some(([a, b]) => p.index < b && p.index + p[0].length > a)) continue;
        const n = normPhone(p[0]);
        if (n) out.phones.push({ value: n, msg: m.i });
      }
      // links
      const urls = [...t.matchAll(RE_URL)].map((u) => u[0]);
      const bare = [...t.matchAll(RE_DOMAIN)].map((u) => u[0]).filter((u) => !urls.some((x) => x.includes(u)));
      for (const u of [...urls, ...bare]) {
        let host;
        try { host = new URL(/^https?:/i.test(u) ? u : 'http://' + u).hostname; } catch { continue; }
        out.links.push({ url: u.replace(/[.,;:!?]+$/, ''), domain: regDomain(host), msg: m.i });
      }
      for (const e of t.matchAll(RE_EMAIL)) out.emails.push({ value: e[0].toLowerCase(), msg: m.i });
      // amounts
      const amounts = [];
      for (const a of t.matchAll(RE_AMOUNT)) {
        const whole = (a[1] || a[3] || '').replace(/[ , ]/g, '');
        const v = parseFloat(whole + (a[2] ? '.' + a[2] : ''));
        if (v > 0 && v < 10000000) amounts.push(v);
      }
      if (amounts.length) {
        const salaryish = /\b(salary|per month|p\/m|pm|monthly|earn|stipend|profit|returns?|win|won)\b/i;
        if ((byVictim(m) || !scammerName) && RE_PAID.test(t)) out.paid.push({ amounts: [amounts[0]], msg: m.i });
        else if (byScammer(m) && RE_ASK.test(t)) {
          const hasAmount = new RegExp(RE_AMOUNT.source, 'i');
          const lines = t.split('\n').filter((l) => hasAmount.test(l) && !salaryish.test(l));
          const asked = [];
          for (const l of lines) for (const a of l.matchAll(RE_AMOUNT)) {
            const whole = (a[1] || a[3] || '').replace(/[ , ]/g, '');
            asked.push(parseFloat(whole + (a[2] ? '.' + a[2] : '')));
          }
          if (asked.length) out.requested.push({ amounts: asked, msg: m.i });
        }
      }
    }
    // a bank named anywhere in the chat, for accounts without one nearby
    const anyBank = msgs.map((m) => (m.text.match(RE_BANK) || [])[1]).find(Boolean);
    out.accounts.forEach((a) => { if (!a.bank && anyBank) a.bank = canonicalBank(anyBank); });

    out.accounts = uniq(out.accounts, (a) => a.value);
    out.phones = uniq(out.phones, (p) => p.value);
    out.links = uniq(out.links, (l) => l.url.toLowerCase());
    out.emails = uniq(out.emails, (e) => e.value);
    out.domains = uniq(out.links.map((l) => l.domain));
    out.banks = uniq(out.accounts.map((a) => a.bank).filter(Boolean));
    out.totalPaid = out.paid.length ? out.paid.reduce((s, p) => s + p.amounts[0], 0) : null;
    out.totalRequested = out.requested.length ? out.requested.reduce((s, p) => s + p.amounts.reduce((a, b) => a + b, 0), 0) : null;
    return out;
  }

  function guessScammer(msgs) {
    const senders = uniq(msgs.map((m) => m.sender).filter(Boolean));
    if (senders.length < 2) return senders[0] || null;
    const score = Object.fromEntries(senders.map((s) => [s, 0]));
    for (const m of msgs) {
      if (!m.sender) continue;
      if (/acc(ount)?|a\/c|bank/i.test(m.text) && /\d{7,}/.test(m.text.replace(/[ -]/g, ''))) score[m.sender] += 3;
      if (RE_ASK.test(m.text) && /\bR\s?\d/i.test(m.text)) score[m.sender] += 2;
      if (RE_URL.test(m.text)) score[m.sender] += 1;
      RE_URL.lastIndex = 0;
      if (RE_PAID.test(m.text)) score[m.sender] -= 2;
      if (/^(you|me)$/i.test(m.sender)) score[m.sender] -= 5;
    }
    return senders.sort((a, b) => score[b] - score[a])[0];
  }

  const SCAM_WORDS = {
    job: /\b(cv|position|vacanc(y|ies)|salary|recruit(er|ment)?|interview|job|employ(ed|ment)|hr|onboarding|uniform)\b/gi,
    marketplace: /\b(item|selling|seller|buyer|marketplace|gumtree|facebook|still available|collect(ion)?|for sale)\b/gi,
    romance: /\b(love|darling|baby|honey|miss you|sweetheart|my dear|marry|relationship)\b/gi,
    investment: /\b(invest(ment)?|returns?|profit|crypto|bitcoin|forex|trading|double your)\b/gi,
    parcel: /\b(parcel|courier|delivery|customs|clearance|tracking|shipment)\b/gi,
    sars: /\b(sars|tax refund|efiling|refund)\b/gi,
  };
  function detectType(text) {
    let best = 'other', top = 1;
    for (const [k, re] of Object.entries(SCAM_WORDS)) { const n = (text.match(re) || []).length; if (n > top) { top = n; best = k; } }
    return best;
  }
  // Demo only: fictional scam sites we host a safe copy of. Real scam links are never opened.
  const DEMO_SNAPSHOTS = { 'mzansi-careers-onboard.site': 'scam-demo/mzansi-careers/' };

  const TYPE_LABEL = { job: 'Fake job offer', marketplace: 'Online seller / Marketplace', romance: 'Romance scam', investment: 'Investment / crypto scam', parcel: 'Courier / parcel fee', sars: 'Fake SARS refund', other: 'Scam' };

  // ---------------------------------------------------------------- 3. timeline
  function buildTimeline(msgs, scammer, ex) {
    const ev = [];
    const accMsgs = new Set(ex.accounts.map((a) => a.msg));
    const linkMsgs = new Set(ex.links.map((l) => l.msg));
    const paidMsgs = new Map(ex.paid.map((p) => [p.msg, p]));
    const askMsgs = new Map(ex.requested.map((p) => [p.msg, p]));
    const isScam = (m) => m.sender === scammer;
    let lastScam = null;
    msgs.forEach((m, idx) => {
      const q = clip(m.text.replace(/\s+/g, ' '), 110);
      const add = (kind, what) => ev.push({ kind, what, date: m.date, quote: q, who: m.sender });
      if (idx === 0) add('start', `First contact${m.sender ? ' from ' + m.sender : ''}`);
      if (isScam(m)) {
        lastScam = m;
        if (idx > 0 && /\b(congratulations|selected|shortlisted|offer|approved|qualif(y|ied)|winner|won|refund (is )?due|guaranteed)\b/i.test(m.text)) add('offer', 'Promise or offer made');
        if (askMsgs.has(m.i)) add('ask', 'Payment of ' + listText(askMsgs.get(m.i).amounts.map(money)) + ' requested');
        if (accMsgs.has(m.i)) add('details', 'Banking details sent: ' + ex.accounts.filter((a) => a.msg === m.i).map((a) => (a.bank ? a.bank + ' ' : '') + showAcc(a.value)).join(', '));
        if (linkMsgs.has(m.i)) add('link', 'Link sent: ' + ex.links.filter((l) => l.msg === m.i).map((l) => l.domain).join(', '));
        if (RE_PRESSURE.test(m.text)) add('pressure', 'Pressure to act fast');
      } else if (paidMsgs.has(m.i)) add('paid', 'Victim paid ' + money(paidMsgs.get(m.i).amounts[0]));
      else if (RE_GONE.test(m.text)) add('gone', 'Victim cannot reach the scammer');
    });
    if (lastScam && lastScam.i !== msgs[msgs.length - 1].i) {
      ev.push({ kind: 'gone', what: 'Last reply from the scammer', date: lastScam.date, quote: clip(lastScam.text.replace(/\s+/g, ' '), 110), who: lastScam.sender, order: lastScam.i });
    }
    // de-duplicate repeated kinds within the same message, keep chronological order
    return uniq(ev, (e) => e.kind + '|' + e.quote).sort((a, b) => (a.date && b.date ? a.date - b.date : 0));
  }

  // ---------------------------------------------------------------- 4. Scam Fingerprint linking
  function shingles(text) {
    const words = text.toLowerCase().replace(/r?\d[\d\s,.]*/g, ' # ').replace(/[^a-z#\s]/g, ' ').split(/\s+/).filter(Boolean);
    const s = new Set();
    for (let i = 0; i + 2 < words.length; i++) s.add(words[i] + ' ' + words[i + 1] + ' ' + words[i + 2]);
    return s;
  }
  function containment(caseSet, tmplSet) {
    if (!tmplSet.size || !caseSet.size) return 0;
    let n = 0;
    for (const x of tmplSet) if (caseSet.has(x)) n++;
    return n / tmplSet.size;
  }
  const scriptSets = Object.fromEntries(Object.entries(SEED.scripts || {}).map(([k, v]) => [k, shingles(v.text)]));

  function localReports() {
    try { return JSON.parse(localStorage.getItem(LOCAL_KEY) || '[]'); } catch { return []; }
  }
  function saveLocalReports(list) {
    try { localStorage.setItem(LOCAL_KEY, JSON.stringify(list)); return true; } catch { return false; }
  }

  async function fingerprint(ex) {
    const out = { acc: [], phone: [], domain: [], email: [] };
    for (const a of ex.accounts) out.acc.push(await hmac('acc:' + a.value));
    for (const p of ex.phones) out.phone.push(await hmac('phone:' + p.value));
    for (const d of ex.domains) out.domain.push(await hmac('domain:' + d));
    for (const e of ex.emails) out.email.push(await hmac('email:' + e.value));
    return out;
  }

  function link(fp, scammerText) {
    const reports = [...(SEED.reports || []), ...localReports()];
    const caseSh = shingles(scammerText);
    const scriptScores = Object.fromEntries(Object.entries(scriptSets).map(([k, set]) => [k, containment(caseSh, set)]));
    const bestScript = Object.entries(scriptScores).sort((a, b) => b[1] - a[1])[0] || [null, 0];
    const hits = new Map();
    const signal = { acc: new Set(), phone: new Set(), domain: new Set(), script: new Set() };
    const mark = (r, kind) => { hits.set(r.id, r); signal[kind].add(r.id); };
    for (const r of reports) {
      for (const kind of ['acc', 'phone', 'domain', 'email']) {
        if ((r.ids[kind] || []).some((x) => fp[kind].includes(x))) mark(r, kind === 'email' ? 'acc' : kind);
      }
      if (r.script && scriptScores[r.script] >= SCRIPT_THRESHOLD) mark(r, 'script');
    }
    // expand once through shared fingerprints (same account or number as a linked report)
    const shared = { acc: new Set(), phone: new Set(), domain: new Set() };
    for (const r of hits.values()) for (const k of Object.keys(shared)) (r.ids[k] || []).forEach((x) => shared[k].add(x));
    for (const r of reports) {
      if (hits.has(r.id)) continue;
      if (Object.keys(shared).some((k) => (r.ids[k] || []).some((x) => shared[k].has(x)))) hits.set(r.id, r);
    }
    const list = [...hits.values()].sort((a, b) => a.date.localeCompare(b.date));
    const phones = new Set(); const accs = new Set();
    list.forEach((r) => { (r.ids.phone || []).forEach((x) => phones.add(x)); (r.ids.acc || []).forEach((x) => accs.add(x)); });
    fp.phone.forEach((x) => phones.add(x)); fp.acc.forEach((x) => accs.add(x));
    return {
      reports: list,
      count: list.length,
      networkSize: reports.length,
      total: list.reduce((s, r) => s + (r.amount || 0), 0),
      provinces: uniq(list.map((r) => r.province).filter((p) => p && p !== '—')),
      first: list[0] && list[0].date,
      last: list[list.length - 1] && list[list.length - 1].date,
      signal,
      scriptId: bestScript[1] >= SCRIPT_THRESHOLD ? bestScript[0] : null,
      scriptScore: bestScript[1],
      distinctPhones: phones.size,
      distinctAccounts: accs.size,
    };
  }

  // ---------------------------------------------------------------- 5. writing
  const OFFER_EN = {
    job: 'offered me a job and told me I had been selected',
    marketplace: 'offered to sell me an item',
    romance: 'built a relationship with me and then asked me for money',
    investment: 'offered me an investment with high returns',
    parcel: 'told me a parcel was being held and needed a fee to be released',
    sars: 'told me I was due a tax refund from SARS',
    other: 'made me an offer',
  };
  const OUTCOME_EN = {
    job: 'I never received the job, and the person stopped responding',
    marketplace: 'I never received the item, and the person stopped responding',
    romance: 'the person kept asking for more money and then stopped responding',
    investment: 'I never received any returns or my money back, and the person stopped responding',
    parcel: 'no parcel was delivered, and the person stopped responding',
    sars: 'I never received any refund',
    other: 'I did not receive what was promised, and the person stopped responding',
  };
  const OFFER_ZU = {
    job: 'wangethembisa umsebenzi wathi ngikhethiwe',
    marketplace: 'wathi uzongithengisela impahla',
    romance: 'wakha ubudlelwano nami wabe esecela imali',
    investment: 'wangethembisa ukutshala imali okuzongizuzisa kakhulu',
    parcel: 'wathi kukhona iphasela elibanjiwe okudingeka likhokhelwe ukuze likhishwe',
    sars: 'wathi ngizobuyiselwa imali yentela yi-SARS',
    other: 'wangethembisa okuthile',
  };
  const OUTCOME_ZU = {
    job: 'Angizange ngiwuthole umsebenzi, futhi lo muntu wayeka ukuphendula.',
    marketplace: 'Angizange ngiyithole impahla, futhi lo muntu wayeka ukuphendula.',
    romance: 'Lo muntu waqhubeka ecela imali eyengeziwe wabe eseyeka ukuphendula.',
    investment: 'Angizange ngithole nzuzo noma imali yami ibuyiswe, futhi lo muntu wayeka ukuphendula.',
    parcel: 'Alikho iphasela elalethwa, futhi lo muntu wayeka ukuphendula.',
    sars: 'Angizange ngiyithole imali ebuyiselwayo.',
    other: 'Angizange ngikuthole engakuthenjiswa, futhi lo muntu wayeka ukuphendula.',
  };

  // More statement languages (drafts: a fluent speaker should check them before signing).
  const LANG_NAMES = { en: 'English', zu: 'isiZulu', xh: 'isiXhosa', af: 'Afrikaans', st: 'Sesotho' };
  const EXTRA_LANGS = {
    af: {
      months: ['Januarie', 'Februarie', 'Maart', 'April', 'Mei', 'Junie', 'Julie', 'Augustus', 'September', 'Oktober', 'November', 'Desember'],
      and: 'en', title: 'VERKLARING VAN KLAGER', nameph: '[jou volle naam]',
      intro: (n) => `Ek, ${n}, verklaar soos volg:`,
      l1: (d, a, ph) => `1. Op ${d} is ek op WhatsApp gekontak deur 'n persoon wat die naam "${a}"${ph ? ' en die nommer' + (ph.n > 1 ? 's ' : ' ') + ph.t : ''} gebruik.`,
      offer: { job: "my 'n werk aangebied en gesê dat ek gekies is", marketplace: "aangebied om 'n item aan my te verkoop", romance: "'n verhouding met my opgebou en my toe vir geld gevra", investment: "my 'n belegging met hoë opbrengste aangebied", parcel: "gesê dat 'n pakkie teruggehou word en dat 'n fooi betaal moet word om dit vry te stel", sars: "gesê dat ek 'n belastingterugbetaling van SARS sou ontvang", other: "my 'n aanbod gemaak" },
      l2: (o) => `2. Hierdie persoon het ${o}.`,
      acc: (a) => 'rekening ' + showAcc(a.value) + (a.bank ? ' by ' + a.bank : ''),
      l3: (t) => (t ? `3. Hulle het my gevra om betaling te maak in ${t}.` : '3. Hulle het my gevra om \'n betaling te maak.'),
      l4: (amt, d) => `4. Ek het 'n totaal van ${amt} betaal${d ? ' op ' + d : ''}.`,
      outcome: { job: 'het ek nooit die werk gekry nie, en die persoon het opgehou om te antwoord', marketplace: 'het ek nooit die item ontvang nie, en die persoon het opgehou om te antwoord', romance: 'het die persoon aangehou om meer geld te vra en toe opgehou om te antwoord', investment: 'het ek geen opbrengs of my geld terug ontvang nie, en die persoon het opgehou om te antwoord', parcel: 'is geen pakkie afgelewer nie, en die persoon het opgehou om te antwoord', sars: 'het ek geen terugbetaling ontvang nie', other: 'het ek nie ontvang wat belowe is nie, en die persoon het opgehou om te antwoord' },
      l5: (o) => `5. Nadat ek betaal het, ${o}.`,
      l6: (t) => `6. Hulle het my ook 'n skakel na ${t} gestuur.`,
      notKnown: 'Ek het nie hierdie persoon geken nie en het hulle nie toestemming gegee om my geld te hou nie.',
      attach: (id) => `Ek heg die bewyse aan wat in Ubufakazi-saaklêer ${id} gelys word. Elke lêer het 'n SHA-256-vingerafdruk sodat enige latere verandering opgespoor kan word.`,
      request: "Ek versoek dat 'n saak van bedrog geopen word.",
      sign: 'Handtekening: ______________________     Datum: ______________',
      amountph: '[bedrag]', dateph: '[datum]', aliasph: '[naam]',
    },
    xh: {
      months: ['Janyuwari', 'Februwari', 'Matshi', 'Epreli', 'Meyi', 'Juni', 'Julayi', 'Agasti', 'Septemba', 'Okthobha', 'Novemba', 'Disemba'],
      and: 'kunye', title: 'INGXELO YOMMANGALELI', nameph: '[igama lakho]',
      intro: (n) => `Mna, ${n}, ndithi:`,
      l1: (d, a, ph) => `1. Ngomhla we-${d}, ndaqhagamshelwa kuWhatsApp ngumntu osebenzisa igama elithi "${a}"${ph ? ', nenombolo ' + ph.t : ''}.`,
      offer: { job: 'wandithembisa umsebenzi wathi ndikhethiwe', marketplace: 'wathi uza kundithengisela into', romance: 'wakha ubudlelwane nam waza wacela imali', investment: 'wandithembisa utyalo-mali olunenzuzo ephezulu', parcel: 'wathi kukho ipasile ebanjiweyo ekufuneka ihlawulelwe ukuze ikhululwe', sars: 'wathi ndiza kubuyiselwa imali yerhafu yi-SARS', other: 'wandithembisa into ethile' },
      l2: (o) => `2. Lo mntu ${o}.`,
      acc: (a) => 'akhawunti ' + (a.bank ? 'yase' + a.bank + ' ' : '') + showAcc(a.value),
      l3: (t) => (t ? `3. Wandicela ukuba ndihlawule imali kwi-${t}.` : '3. Wandicela ukuba ndihlawule imali.'),
      l4: (amt, d) => `4. Ndahlawula imali eyi-${amt}${d ? ' ngomhla we-' + d : ''}.`,
      outcome: { job: 'Andizange ndiwufumane umsebenzi, kwaye lo mntu wayeka ukuphendula.', marketplace: 'Andizange ndiyifumane loo nto, kwaye lo mntu wayeka ukuphendula.', romance: 'Lo mntu waqhubeka ecela imali engakumbi waza wayeka ukuphendula.', investment: 'Andizange ndifumane nzuzo okanye imali yam ibuyiselwe, kwaye lo mntu wayeka ukuphendula.', parcel: 'Akukho pasile yafika, kwaye lo mntu wayeka ukuphendula.', sars: 'Andizange ndiyifumane imali ebuyiselwayo.', other: 'Andizange ndikufumane endakuthenjiswayo, kwaye lo mntu wayeka ukuphendula.' },
      l5: (o) => `5. ${o}`,
      l6: (t) => `6. Wandithumelela nekhonkco (link) eliya ku-${t}.`,
      notKnown: 'Andimazi lo mntu, kwaye andizange ndimnike imvume yokugcina imali yam.',
      attach: (id) => `Ndincamathisela ubungqina obudweliswe kwifayile yetyala (${id}). Ifayile nganye inesitampu sedijithali (SHA-256), ukuze naluphi na utshintsho lubonakale.`,
      request: 'Ndicela ukuba kuvulwe ityala lobuqhophololo (fraud).',
      sign: 'Utyikityo: ______________________     Umhla: ______________',
      amountph: '[isixa]', dateph: '[umhla]', aliasph: '[igama]',
    },
    st: {
      months: ['Pherekgong', 'Hlakola', 'Hlakubele', 'Mmesa', 'Motsheanong', 'Phupjane', 'Phupu', 'Phato', 'Lwetse', 'Mphalane', 'Pudungwana', 'Tshitwe'],
      and: 'le', title: 'POLELO YA MMELAEDI', nameph: '[lebitso la hao]',
      intro: (n) => `Nna, ${n}, ke re:`,
      l1: (d, a, ph) => `1. Ka la ${d}, motho ya sebedisang lebitso la "${a}"${ph ? ' le nomoro ' + ph.t : ''} o ile a ikopanya le nna ho WhatsApp.`,
      offer: { job: 'o ile a ntshepisa mosebetsi mme a re ke kgethilwe', marketplace: 'o ile a re o tla nthekisetsa thepa', romance: 'o ile a aha kamano le nna mme a nkopa tjhelete', investment: 'o ile a ntshepisa peeletso e nang le phaello e hodimo', parcel: 'o ile a re ho na le phasela e tshwerweng e hlokang ho lefellwa hore e lokollwe', sars: 'o ile a re ke tla busetswa tjhelete ya lekgetho ke SARS', other: 'o ile a ntshepisa ho itseng' },
      l2: (o) => `2. Motho enwa ${o}.`,
      acc: (a) => 'akhaontong ' + (a.bank ? 'ya ' + a.bank + ' ' : '') + showAcc(a.value),
      l3: (t) => (t ? `3. O ile a nkopa hore ke lefe tjhelete ${t}.` : '3. O ile a nkopa hore ke lefe tjhelete.'),
      l4: (amt, d) => `4. Ke lefile kakaretso ya ${amt}${d ? ' ka la ' + d : ''}.`,
      outcome: { job: 'Ha ke a ka ka fumana mosebetsi, mme motho enwa o ile a kgaotsa ho araba.', marketplace: 'Ha ke a ka ka fumana thepa, mme motho enwa o ile a kgaotsa ho araba.', romance: 'Motho enwa o ile a tswela pele ho kopa tjhelete e eketsehileng mme a kgaotsa ho araba.', investment: 'Ha ke a ka ka fumana phaello kapa tjhelete ya ka e busetswa, mme motho enwa o ile a kgaotsa ho araba.', parcel: 'Ha ho phasela e ileng ya fihla, mme motho enwa o ile a kgaotsa ho araba.', sars: 'Ha ke a ka ka fumana tjhelete e busetswang.', other: 'Ha ke a ka ka fumana se neng se tshepisitswe, mme motho enwa o ile a kgaotsa ho araba.' },
      l5: (o) => `5. ${o}`,
      l6: (t) => `6. O ile a nthomella le lehokela (link) le yang ho ${t}.`,
      notKnown: 'Ha ke mo tsebe motho enwa, mme ha ke a mo fa tumello ya ho boloka tjhelete ya ka.',
      attach: (id) => `Ke kenya bopaki bo thathamisitsweng faeleng ya nyewe (${id}). Faele ka nngwe e na le setempe sa dijithale (SHA-256), hore phetoho efe kapa efe e bonahale.`,
      request: 'Ke kopa hore ho bulwe nyewe ya bomenemene (fraud).',
      sign: 'Tshaeno: ______________________     Letsatsi: ______________',
      amountph: '[kakaretso]', dateph: '[letsatsi]', aliasph: '[lebitso]',
    },
  };

  function writeStatementExtra(c, L) {
    const ex = c.ex;
    const fd = (d) => `${d.getDate()} ${L.months[d.getMonth()]} ${d.getFullYear()}`;
    const first = c.msgs.find((m) => m.date);
    const payDates = ex.paid.map((p) => c.msgs.find((m) => m.i === p.msg)).filter((m) => m && m.date).map((m) => m.date);
    const phones = ex.phones.map((p) => showPhone(p.value));
    return [
      L.title, '',
      L.intro(c.victimName || L.nameph), '',
      L.l1(first ? fd(first.date) : L.dateph, c.scammer || L.aliasph, phones.length ? { n: phones.length, t: listText(phones, L.and) } : null),
      L.l2(L.offer[c.type]),
      L.l3(ex.accounts.length ? listText(ex.accounts.map(L.acc), L.and) : ''),
      L.l4(ex.totalPaid != null ? money(ex.totalPaid) : L.amountph, payDates.length ? listText(uniq(payDates.map(fd)), L.and) : ''),
      L.l5(L.outcome[c.type]),
      ex.domains.length ? L.l6(listText(ex.domains, L.and)) : null,
      '', L.notKnown, L.attach(c.caseId), '', L.request, '', L.sign,
    ].filter((l) => l !== null).join('\n');
  }

  function writeStatement(c, lang) {
    if (EXTRA_LANGS[lang]) return writeStatementExtra(c, EXTRA_LANGS[lang]);
    const ex = c.ex;
    const name = c.victimName || (lang === 'zu' ? '[igama lakho]' : '[your full name]');
    const first = c.msgs.find((m) => m.date);
    const payDates = ex.paid.map((p) => c.msgs.find((m) => m.i === p.msg)).filter((m) => m && m.date).map((m) => m.date);
    const phones = ex.phones.map((p) => showPhone(p.value));
    const accs = ex.accounts.map((a) => (a.bank ? a.bank + ' ' : '') + 'account ' + showAcc(a.value));
    const files = c.evidence.map((f) => f.name);
    if (lang === 'zu') {
      const accsZu = ex.accounts.map((a) => 'akhawunti ' + (a.bank ? 'yase-' + a.bank + ' ' : '') + showAcc(a.value));
      return [
        'ISITATIMENDE SOMMANGALELI',
        '',
        `Mina, ${name}, ngithi:`,
        '',
        `1. Ngomhla ka-${first ? fmtDateZu(first.date) : '[usuku]'}, ngathintwa ku-WhatsApp umuntu ozibiza ngokuthi ngu-"${c.scammer || '[igama]'}"${phones.length ? ', esebenzisa inombolo ' + listText(phones, 'no-') : ''}.`,
        `2. Lo muntu ${OFFER_ZU[c.type]}.`,
        ex.accounts.length ? `3. Wangicela ukuthi ngikhokhe imali ku-${listText(accsZu, 'no-')}.` : '3. Wangicela ukuthi ngikhokhe imali.',
        `4. Ngakhokha isamba esingu-${ex.totalPaid != null ? money(ex.totalPaid) : '[isamba]'}${payDates.length ? ' ngomhla ka-' + listText(uniq(payDates.map(fmtDateZu)), 'no-') : ''}.`,
        `5. ${OUTCOME_ZU[c.type]}`,
        ex.domains.length ? `6. Wangithumelela nesixhumanisi (link) esiya ku-${listText(ex.domains, 'no-')}.` : null,
        '',
        'Angimazi lo muntu, futhi angizange ngimnike imvume yokugcina imali yami.',
        `Nginamathisele ubufakazi obubhalwe kuleli fayela lecala (${c.caseId}). Ifayela ngalinye linesigxivizo sedijithali (SHA-256), ukuze noma yiluphi ushintsho lubonakale.`,
        '',
        'Ngicela ukuthi kuvulwe icala lokukhwabanisa (fraud).',
        '',
        'Isiginesha: ______________________     Usuku: ______________',
      ].filter((l) => l !== null).join('\n');
    }
    return [
      'COMPLAINANT STATEMENT',
      '',
      `I, ${name}, state the following:`,
      '',
      `1. On ${first ? fmtDate(first.date) : '[date]'}, I was contacted on WhatsApp by a person using the name "${c.scammer || '[name]'}"${phones.length ? ' and the number' + (phones.length > 1 ? 's ' : ' ') + listText(phones) : ''}.`,
      `2. This person ${OFFER_EN[c.type]}.`,
      ex.accounts.length ? `3. They asked me to make payment into ${listText(accs)}.` : '3. They asked me to make a payment.',
      `4. I paid a total of ${ex.totalPaid != null ? money(ex.totalPaid) : '[amount]'}${payDates.length ? ' on ' + listText(uniq(payDates.map(fmtDate))) : ''}.`,
      `5. After I paid, ${OUTCOME_EN[c.type]}.`,
      ex.domains.length ? `6. They also sent me a link to ${listText(ex.domains)}.` : null,
      '',
      'I did not know this person and I did not give them permission to keep my money.',
      `I attach the evidence listed in Ubufakazi case file ${c.caseId}${files.length ? ' (' + files.length + ' file' + (files.length > 1 ? 's' : '') + ')' : ''}. Each file has a SHA-256 fingerprint so that any later change to it can be detected.`,
      '',
      'I request that a case of fraud be opened.',
      '',
      'Signature: ______________________     Date: ______________',
    ].filter((l) => l !== null).join('\n');
  }

  function writeBankReport(c) {
    const ex = c.ex;
    const payDates = ex.paid.map((p) => c.msgs.find((m) => m.i === p.msg)).filter((m) => m && m.date).map((m) => fmtDate(m.date) + ' ' + fmtTime(m.date));
    return [
      'To: Fraud department, [your bank]',
      'Subject: Fraud report: request to trace and stop funds',
      '',
      'I am reporting payment(s) I made to a fraudster.',
      '',
      `Amount paid: ${ex.totalPaid != null ? money(ex.totalPaid) : '[amount]'}`,
      `Date(s) and time(s): ${payDates.length ? payDates.join('; ') : '[date and time of each payment]'}`,
      `Paid into: ${ex.accounts.length ? ex.accounts.map((a) => (a.bank || '[bank]') + ', account ' + showAcc(a.value)).join('; ') : '[receiving bank and account number]'}`,
      `Fraudster's name used: ${c.scammer || '[name]'}`,
      `Fraudster's phone number(s): ${ex.phones.length ? ex.phones.map((p) => showPhone(p.value)).join(', ') : '[number]'}`,
      `Type of scam: ${TYPE_LABEL[c.type]}`,
      'SAPS case number: [add once opened]',
      `Ubufakazi case file: ${c.caseId}`,
      '',
      'Please investigate the receiving account and stop or freeze the funds where possible. The full evidence pack is attached.',
      '',
      `${c.victimName || '[your name]'}`,
      '[your account number] · [your phone number]',
    ].join('\n');
  }

  // ---------------------------------------------------------------- evidence files
  const state = { files: [], result: null, lang: 'en', added: false };

  function renderFiles() {
    const ul = $('#fileList');
    ul.replaceChildren(...state.files.map((f, i) => {
      const thumb = f.url ? h('img', { src: f.url, alt: '' }) : h('span', { class: 'ficon', text: (f.name.split('.').pop() || 'file').toUpperCase().slice(0, 4) });
      const rm = h('button', { type: 'button', class: 'btn btn-small btn-ghost', 'aria-label': 'Remove ' + f.name, text: 'Remove' });
      rm.addEventListener('click', () => { if (f.url) URL.revokeObjectURL(f.url); state.files.splice(i, 1); renderFiles(); });
      return h('li', null, thumb, h('span', { class: 'fname', text: f.name }), h('span', { class: 'fsize', text: fmtBytes(f.size) }), rm);
    }));
  }
  function addFiles(list) {
    for (const file of list) {
      if (state.files.some((f) => f.name === file.name && f.size === file.size)) continue;
      state.files.push({ file, name: file.name, size: file.size, type: file.type, url: file.type.startsWith('image/') ? URL.createObjectURL(file) : null });
    }
    renderFiles();
  }

  // ---------------------------------------------------------------- demo cases (fictional)
  const DEMO_A = {
    name: 'Lerato Mokoena',
    chat: `12/10/2026, 09:14 - Thandi (HR Recruiter): Good morning! Your CV was shortlisted for the Admin Clerk position at Mzansi Retail Group. Salary R14 500 per month. Are you still interested?
12/10/2026, 09:20 - Lerato: Yes I am! Thank you so much
12/10/2026, 09:22 - Thandi (HR Recruiter): Congratulations, you have been selected. To secure your position you must pay a once-off registration and uniform fee of R1 850. Positions are limited so please pay today.
12/10/2026, 09:23 - Thandi (HR Recruiter): Bank: DemoBank
Acc name: MZ Placements
Acc no: 1047 2283 59
Reference: your name
12/10/2026, 09:25 - Thandi (HR Recruiter): Complete the onboarding form here: https://mzansi-careers-onboard.site/apply
If WhatsApp is slow call me on 071 482 0937
12/10/2026, 09:41 - Lerato: Ok I have paid R1 850 now. Sending proof of payment
12/10/2026, 10:05 - Thandi (HR Recruiter): Received. There is also a training fee of R1 650 which must be paid before Monday or you lose the position.
12/10/2026, 10:30 - Lerato: Ok I sent the R1 650 as well
12/10/2026, 11:02 - Lerato: Hello? When do I start?
13/10/2026, 08:15 - Lerato: Please answer me
13/10/2026, 08:16 - Lerato: Your number is not going through`,
    pops: [{ amount: 'R1 850,00', date: '12 Oct 2026  09:39', ref: 'LERATO M', acc: '1047 2283 59', name: 'MZ Placements' },
           { amount: 'R1 650,00', date: '12 Oct 2026  10:27', ref: 'LERATO M', acc: '1047 2283 59', name: 'MZ Placements' }],
  };
  const DEMO_B = {
    name: 'Sipho Ndlovu',
    chat: `[15/10/2026, 13:02:11] Nomsa (Recruitment): Good morning! Your CV was shortlisted for the Stock Controller position at Mzansi Retail Group. Salary R16 000 per month. Are you still interested?
[15/10/2026, 13:10:45] Sipho: Yes please
[15/10/2026, 13:12:02] Nomsa (Recruitment): Congratulations, you have been selected. To secure your position you must pay a once-off registration and uniform fee of R2 100. Positions are limited so please pay today.
[15/10/2026, 13:12:40] Nomsa (Recruitment): Pay to DemoBank account 2290 1184 76, account name NS Staffing. Then complete the onboarding form here: mzansi-careers-onboard.site/apply
[15/10/2026, 13:13:05] Nomsa (Recruitment): You can also call me on 068 330 5521
[15/10/2026, 13:40:19] Sipho: I have paid the R2 100. Here is the proof of payment
[15/10/2026, 14:05:51] Sipho: When is my first day?
[16/10/2026, 09:30:02] Sipho: Hello?? Please answer`,
    pops: [{ amount: 'R2 100,00', date: '15 Oct 2026  13:38', ref: 'SIPHO N', acc: '2290 1184 76', name: 'NS Staffing' }],
  };

  /** Draws an obviously fictional "DemoBank" proof of payment, marked SAMPLE. */
  function makePop(p, n) {
    const cv = document.createElement('canvas');
    cv.width = 720; cv.height = 900;
    const g = cv.getContext('2d');
    g.fillStyle = '#f6f7f9'; g.fillRect(0, 0, 720, 900);
    g.fillStyle = '#1d3b6e'; g.fillRect(0, 0, 720, 120);
    g.fillStyle = '#fff'; g.font = 'bold 40px sans-serif'; g.fillText('DemoBank', 40, 74);
    g.font = '18px sans-serif'; g.fillText('Fictional bank for demonstrations', 40, 102);
    g.fillStyle = '#16223a'; g.font = 'bold 30px sans-serif'; g.fillText('Proof of payment', 40, 190);
    const rows = [['Date', p.date], ['Amount', p.amount], ['Beneficiary', p.name], ['Account number', p.acc], ['Bank', 'DemoBank'], ['Reference', p.ref], ['Status', 'Successful']];
    g.font = '22px sans-serif';
    rows.forEach(([k, v], i) => {
      const y = 260 + i * 62;
      g.fillStyle = '#5b6b84'; g.fillText(k, 40, y);
      g.fillStyle = '#16223a'; g.font = 'bold 24px sans-serif'; g.fillText(v, 300, y); g.font = '22px sans-serif';
      g.fillStyle = '#d9dee7'; g.fillRect(40, y + 20, 640, 2);
    });
    g.save(); g.translate(360, 640); g.rotate(-0.42);
    g.fillStyle = 'rgba(214, 48, 30, 0.22)'; g.font = 'bold 120px sans-serif'; g.textAlign = 'center'; g.fillText('SAMPLE', 0, 0);
    g.restore();
    g.fillStyle = '#b3261e'; g.font = 'bold 20px sans-serif'; g.fillText('DEMO DOCUMENT · NOT A REAL PAYMENT', 40, 860);
    return new Promise((res) => cv.toBlob((b) => res(new File([b], `proof-of-payment-${n}.png`, { type: 'image/png' })), 'image/png'));
  }

  async function loadDemo(d) {
    $('#victimName').value = d.name;
    $('#chat').value = d.chat;
    $('#scamType').value = 'auto';
    state.files.forEach((f) => f.url && URL.revokeObjectURL(f.url));
    state.files = [];
    const pops = await Promise.all(d.pops.map((p, i) => makePop(p, i + 1)));
    addFiles(pops);
    setMsg('Demo case loaded. Press "Build my case file".');
    $('#buildBtn').focus();
  }

  // ---------------------------------------------------------------- main flow
  function setMsg(text, err) { const m = $('#formMsg'); m.textContent = text; m.classList.toggle('err', !!err); }

  async function build(ev) {
    ev.preventDefault();
    const chat = $('#chat').value.trim();
    if (!chat && !state.files.length) { setMsg('Paste the scam chat or add at least one file first.', true); $('#chat').focus(); return; }
    setMsg('');
    $('#buildBtn').disabled = true;
    const prog = $('#progress');
    prog.hidden = false; $('#results').hidden = true;
    const steps = [...prog.querySelectorAll('li')];
    steps.forEach((s) => s.classList.remove('active', 'done'));
    prog.scrollIntoView({ block: 'start' });
    const step = async (i, fn) => { steps[i].classList.add('active'); const [r] = await Promise.all([fn(), sleep(520)]); steps[i].classList.replace('active', 'done'); return r; };

    try {
      const lockedAt = new Date();
      // 1. lock evidence
      const evidence = await step(0, async () => {
        const items = [];
        if (chat) items.push({ name: 'chat-transcript.txt', size: enc.encode(chat).length, sha: await sha256(chat) });
        for (const f of state.files) items.push({ name: f.name, size: f.size, sha: await sha256(await f.file.arrayBuffer()) });
        return items;
      });
      // 2. extract
      const msgs = parseChat(chat);
      const scammer = guessScammer(msgs);
      const ex = await step(1, async () => extract(msgs, scammer));
      const scammerText = msgs.filter((m) => !scammer || m.sender === scammer).map((m) => m.text).join('\n');
      const typeSel = $('#scamType').value;
      const type = typeSel === 'auto' ? detectType(chat) : typeSel;
      // 3. timeline
      const timeline = await step(2, async () => (msgs.length ? buildTimeline(msgs, scammer, ex) : []));
      // 4. link
      const fp = await fingerprint(ex);
      const linked = await step(3, async () => link(fp, scammerText));
      // 5. write
      const manifest = JSON.stringify({ evidence: evidence.map((e) => [e.name, e.sha]), accounts: ex.accounts.map((a) => a.value), phones: ex.phones.map((p) => p.value), lockedAt: lockedAt.toISOString() });
      const manifestSha = await sha256(manifest);
      const caseId = 'UBF-' + manifestSha.slice(0, 8).toUpperCase();
      const c = { caseId, manifestSha, lockedAt, evidence, msgs, scammer, ex, type, timeline, fp, linked, victimName: $('#victimName').value.trim(), scammerText };
      await step(4, async () => { c.statement = Object.fromEntries(Object.keys(LANG_NAMES).map((l) => [l, writeStatement(c, l)])); c.bank = writeBankReport(c); });
      state.result = c; state.added = false; state.lang = $('#lang').value;
      await sleep(250);
      renderResults(c);
      prog.hidden = true;
      $('#results').hidden = false;
      $('#results').scrollIntoView({ block: 'start' });
      $('#linkCard').focus({ preventScroll: true });
    } catch (err) {
      console.error(err);
      prog.hidden = true;
      setMsg('Something went wrong building the case file: ' + err.message, true);
    } finally {
      $('#buildBtn').disabled = false;
    }
  }

  function renderResults(c) {
    $('#caseId').textContent = c.caseId;

    // link card
    const L = c.linked, card = $('#linkCard');
    card.replaceChildren();
    if (L.count > 0) {
      card.className = 'link-card hit';
      const sig = (on, title, sub) => h('div', { class: 'sig ' + (on ? 'on' : 'off') }, h('b', { text: title }), h('span', { text: sub }));
      const n = (s) => s.size;
      const months = L.first ? `between ${fmtDate(new Date(L.first))} and ${fmtDate(new Date(L.last))}` : '';
      card.append(
        h('div', { class: 'link-top' },
          h('div', { class: 'victim-no' }, '#' + (L.count + 1), h('small', { text: 'YOU ARE VICTIM' })),
          h('div', { class: 'link-msg' },
            h('p', { class: 'link-kicker', text: 'You are not alone' }),
            h('p', { class: 'link-head', text: `This scammer has been reported by ${L.count} other ${L.count === 1 ? 'person' : 'people'}. Combined losses: ${money(L.total)}.` }),
            h('p', { class: 'link-sub', text: [months, L.provinces.length ? `across ${listText(L.provinces)}` : ''].filter(Boolean).join(', ') + '.' }))),
        h('div', { class: 'signals' },
          sig(n(L.signal.acc), 'Bank account', n(L.signal.acc) ? `Same account in ${n(L.signal.acc)} report${n(L.signal.acc) > 1 ? 's' : ''}` : 'New account'),
          sig(n(L.signal.phone), 'Phone number', n(L.signal.phone) ? `Same number in ${n(L.signal.phone)} report${n(L.signal.phone) > 1 ? 's' : ''}` : 'New number'),
          sig(n(L.signal.domain), 'Link', n(L.signal.domain) ? `Same site in ${n(L.signal.domain)} report${n(L.signal.domain) > 1 ? 's' : ''}` : 'No match'),
          sig(n(L.signal.script), 'Message script', L.scriptId ? `${Math.round(L.scriptScore * 100)}% match to a known script` : 'No match')),
        h('p', { class: 'link-foot', text: `Scam Fingerprint: this group has used ${L.distinctPhones} phone number${L.distinctPhones === 1 ? '' : 's'} and ${L.distinctAccounts} bank account${L.distinctAccounts === 1 ? '' : 's'}. ${L.distinctAccounts > 1 ? 'Switching numbers and bank accounts' : 'Switching numbers'} doesn't hide them. Checked against ${L.networkSize} reports in the network.` }),
      );
    } else {
      card.className = 'link-card clear';
      card.append(h('p', { class: 'link-kicker', text: 'Scam Fingerprint' }),
        h('p', { class: 'link-head', text: 'No earlier reports match this scammer yet.' }),
        h('p', { class: 'link-sub', text: `Checked against ${L.networkSize} reports in the network. Add your report below: if this scammer strikes again, the next victim will be linked to you.` }));
    }

    // evidence
    $('#hashTable tbody').replaceChildren(...c.evidence.map((e) => h('tr', null,
      h('td', null, h('div', { text: e.name }), h('div', { class: 'hint', text: fmtBytes(e.size) })),
      h('td', null, h('span', { class: 'hash', text: e.sha })))));
    $('#lockedAt').textContent = `Locked at ${fmtStamp(c.lockedAt)} (device time). Case manifest fingerprint: ${c.manifestSha.slice(0, 16)}…`;

    // facts
    const chips = (arr, cls) => (arr.length ? arr.map((t) => h('span', { class: 'chip ' + (cls || ''), text: t })) : [h('span', { class: 'none', text: 'None found' })]);
    const ex = c.ex;
    $('#facts').replaceChildren(
      h('dt', { text: 'Name used' }), h('dd', null, chips(c.scammer ? [c.scammer] : [])),
      h('dt', { text: 'Bank accounts' }), h('dd', null, chips(ex.accounts.map((a) => (a.bank ? a.bank + ' · ' : '') + showAcc(a.value)), 'warn')),
      h('dt', { text: 'Phone numbers' }), h('dd', null, chips(ex.phones.map((p) => showPhone(p.value)), 'warn')),
      h('dt', { text: 'Links' }), h('dd', null, ex.links.length ? ex.links.map((l) => {
        const snap = DEMO_SNAPSHOTS[l.domain];
        return h('span', { class: 'link-item' }, h('span', { class: 'chip warn', text: l.url }),
          snap ? h('a', { class: 'snap', href: snap, target: '_blank', rel: 'noopener noreferrer', text: 'Open demo copy of this site' }) : null);
      }) : chips([])),
      ...(ex.emails.length ? [h('dt', { text: 'Emails' }), h('dd', null, chips(ex.emails.map((e) => e.value), 'warn'))] : []),
      h('dt', { text: 'Scam type' }), h('dd', null, chips([TYPE_LABEL[c.type]])),
      h('dt', { text: 'Amount paid' }), h('dd', null, ex.totalPaid != null ? h('span', { class: 'total', text: money(ex.totalPaid) }) : h('span', { class: 'none', text: 'Not found in the chat. Add it to your statement.' })),
    );

    // timeline
    $('#timeline').replaceChildren(...(c.timeline.length ? c.timeline.map((e) => h('li', { class: 'k-' + e.kind },
      h('div', { class: 'tl-when', text: e.date ? `${fmtDate(e.date)} · ${fmtTime(e.date)}` : (e.who || '') }),
      h('div', { class: 'tl-what', text: e.what }),
      h('div', { class: 'tl-quote', text: '"' + e.quote + '"' }))) : [h('li', null, h('div', { class: 'tl-what', text: 'No chat messages to build a timeline from.' }))]));

    // statement + bank report
    setLang(state.lang, false);
    $('#bankReport').value = c.bank;

    // consent
    const consent = $('#consentCard');
    consent.classList.remove('done');
    $('#consentBtn').disabled = false;
    $('#consentBtn').textContent = 'Add my report';
  }

  function setLang(lang, keepEdits = true) {
    const c = state.result;
    if (!c) return;
    // keep the victim's edits to the tab they are leaving
    if (keepEdits && state.lang) c.statement[state.lang] = $('#statement').value;
    state.lang = lang;
    $('#statement').value = c.statement[lang];
    document.querySelectorAll('.tabs .tab').forEach((t) => t.setAttribute('aria-selected', String(t.dataset.lang === lang)));
    $('#zuNote').hidden = lang === 'en';
  }

  function addReport() {
    const c = state.result;
    if (!c || state.added) return;
    const list = localReports();
    list.push({
      id: 'L-' + c.caseId.slice(4),
      date: (c.msgs.find((m) => m.date) || { date: new Date() }).date.toISOString().slice(0, 10),
      province: '—',
      scamType: c.type,
      amount: c.ex.totalPaid || 0,
      script: c.linked.scriptId,
      ids: { acc: c.fp.acc, phone: c.fp.phone, domain: c.fp.domain, email: c.fp.email },
    });
    const ok = saveLocalReports(list);
    state.added = true;
    $('#consentBtn').disabled = true;
    $('#consentBtn').textContent = ok ? 'Report added' : 'Could not save in this browser';
    $('#consentCard').classList.add('done');
    toast(ok ? 'Added. The next victim of this scammer will be linked to you.' : 'Storage is blocked in this browser.');
  }

  // ---------------------------------------------------------------- PDF case pack
  function pdfSafe(s) {
    return String(s).replace(/[‘’]/g, "'").replace(/[“”]/g, '"').replace(/[–—]/g, '-').replace(/…/g, '...').replace(/[  ]/g, ' ').replace(/[^\x09\x0a\x0d\x20-\x7e -ÿ]/g, '');
  }

  function makePdf() {
    const c = state.result;
    if (!c || !window.jspdf) { toast('PDF tool did not load. Refresh the page.'); return; }
    if (c.statement) c.statement[state.lang] = $('#statement').value;
    const bank = $('#bankReport').value;
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF({ unit: 'mm', format: 'a4' });
    const W = 210, H = 297, M = 16, CW = W - 2 * M;
    let y = 0;
    const ink = () => doc.setTextColor(18, 22, 29);
    const muted = () => doc.setTextColor(84, 96, 112);
    const newPage = () => { doc.addPage(); y = 20; };
    const need = (mm) => { if (y + mm > H - 18) newPage(); };
    const heading = (num, title) => {
      need(16);
      y += 4;
      doc.setFont('courier', 'bold'); doc.setFontSize(9); doc.setTextColor(8, 122, 108); doc.text(num, M, y);
      doc.setFont('helvetica', 'bold'); doc.setFontSize(13); ink(); doc.text(pdfSafe(title), M + 10, y);
      y += 2.5; doc.setDrawColor(18, 22, 29); doc.setLineWidth(0.4); doc.line(M, y, W - M, y); y += 6;
    };
    const para = (text, opts = {}) => {
      doc.setFont(opts.font || 'helvetica', opts.bold ? 'bold' : 'normal'); doc.setFontSize(opts.size || 10);
      opts.muted ? muted() : ink();
      const lh = (opts.size || 10) * 0.43;
      for (const raw of pdfSafe(text).split('\n')) {
        const lines = raw ? doc.splitTextToSize(raw, opts.width || CW) : [''];
        for (const l of lines) { need(lh); doc.text(l, opts.x || M, y); y += lh; }
      }
      y += opts.after == null ? 2 : opts.after;
    };
    const kv = (k, v) => {
      doc.setFont('helvetica', 'normal'); doc.setFontSize(8.5); muted();
      const lines = doc.splitTextToSize(pdfSafe(v), CW - 42);
      need(lines.length * 4.4 + 1.5);
      doc.text(pdfSafe(k).toUpperCase(), M, y);
      doc.setFontSize(10); ink(); doc.text(lines, M + 42, y);
      y += lines.length * 4.4 + 1.6;
    };

    // header band
    doc.setFillColor(6, 10, 17); doc.rect(0, 0, W, 42, 'F');
    doc.setFont('courier', 'bold'); doc.setFontSize(8.5); doc.setTextColor(92, 242, 214);
    doc.text('UBUFAKAZI  |  SCAM CASE FILE', M, 13);
    doc.setFont('helvetica', 'bold'); doc.setFontSize(22); doc.setTextColor(244, 248, 251);
    doc.text(c.caseId, M, 26);
    doc.setFont('helvetica', 'normal'); doc.setFontSize(9.5); doc.setTextColor(183, 196, 211);
    doc.text(pdfSafe(`${TYPE_LABEL[c.type]}  |  Prepared ${fmtStamp(new Date())}  |  Evidence locked ${fmtStamp(c.lockedAt)}`), M, 34);
    y = 50;
    doc.setFillColor(251, 237, 231); doc.rect(M, y - 4.5, CW, 9, 'F');
    doc.setFont('helvetica', 'bold'); doc.setFontSize(8.5); doc.setTextColor(185, 60, 18);
    doc.text('DEMO PROTOTYPE (HackSecure 2026). Not an official document. Built from fictional demo data.', M + 3, y + 1);
    y += 12;

    heading('01', 'Summary');
    const ex = c.ex;
    kv('Complainant', c.victimName || '[name]');
    kv('Name used by scammer', c.scammer || 'Unknown');
    kv('Amount paid', ex.totalPaid != null ? money(ex.totalPaid) : 'Not stated in chat');
    kv('Bank accounts', ex.accounts.length ? ex.accounts.map((a) => (a.bank ? a.bank + ' ' : '') + showAcc(a.value)).join(', ') : 'None found');
    kv('Phone numbers', ex.phones.length ? ex.phones.map((p) => showPhone(p.value)).join(', ') : 'None found');
    kv('Links', ex.links.length ? ex.links.map((l) => l.url).join(', ') : 'None found');

    const L = c.linked;
    need(30);
    y += 2;
    if (L.count > 0) {
      const lines = doc.splitTextToSize(pdfSafe(`This scammer's fingerprint matches ${L.count} earlier report${L.count === 1 ? '' : 's'} with combined losses of ${money(L.total)} (${fmtDate(new Date(L.first))} to ${fmtDate(new Date(L.last))}${L.provinces.length ? ', ' + L.provinces.join(', ') : ''}). Linked by: ${[L.signal.acc.size && 'bank account', L.signal.phone.size && 'phone number', L.signal.domain.size && 'link', L.signal.script.size && 'message script'].filter(Boolean).join(', ')}. The group has used ${L.distinctPhones} phone numbers and ${L.distinctAccounts} bank account(s).`), CW - 34);
      const bh = Math.max(24, lines.length * 4.4 + 12);
      doc.setFillColor(255, 243, 239); doc.setDrawColor(241, 201, 185); doc.rect(M, y, CW, bh, 'FD');
      doc.setFont('helvetica', 'bold'); doc.setFontSize(24); doc.setTextColor(185, 60, 18); doc.text('#' + (L.count + 1), M + 5, y + 14);
      doc.setFontSize(7); doc.text('VICTIM', M + 5, y + 19);
      doc.setFont('helvetica', 'bold'); doc.setFontSize(10.5); ink(); doc.text('Linked reports: possible syndicate', M + 32, y + 7);
      doc.setFont('helvetica', 'normal'); doc.setFontSize(9.5); doc.text(lines, M + 32, y + 12.5);
      y += bh + 6;
    } else {
      para('No earlier reports match this scammer yet.', { muted: true });
    }

    heading('02', 'Evidence register');
    para('Each file below was fingerprinted with SHA-256 when it was submitted. Recomputing the fingerprint of the original file and comparing it with this register shows whether it has been changed.', { size: 9, muted: true, after: 3 });
    c.evidence.forEach((e, i) => {
      need(12);
      doc.setFont('helvetica', 'bold'); doc.setFontSize(9.5); ink();
      doc.text(pdfSafe(`${i + 1}. ${e.name}`), M, y);
      doc.setFont('helvetica', 'normal'); muted(); doc.text(fmtBytes(e.size), W - M, y, { align: 'right' });
      y += 4.4;
      doc.setFont('courier', 'normal'); doc.setFontSize(8.2); doc.setTextColor(8, 122, 108);
      doc.text(e.sha, M + 4, y);
      y += 6;
    });
    para(`Case manifest SHA-256: ${c.manifestSha}`, { font: 'courier', size: 8, muted: true });

    heading('03', 'Timeline');
    if (!c.timeline.length) para('No dated chat messages were provided.', { muted: true });
    c.timeline.forEach((e) => {
      need(14);
      doc.setFont('courier', 'normal'); doc.setFontSize(8.2); muted();
      doc.text(pdfSafe(e.date ? `${fmtDate(e.date)} ${fmtTime(e.date)}` : (e.who || '')), M, y);
      doc.setFont('helvetica', 'bold'); doc.setFontSize(9.8); ink();
      const what = doc.splitTextToSize(pdfSafe(e.what), CW - 44);
      doc.text(what, M + 44, y);
      y += what.length * 4.2;
      doc.setFont('helvetica', 'normal'); doc.setFontSize(8.8); muted();
      const q = doc.splitTextToSize(pdfSafe('"' + e.quote + '"'), CW - 44);
      need(q.length * 3.9);
      doc.text(q, M + 44, y);
      y += q.length * 3.9 + 3;
    });

    newPage();
    heading('04', state.lang === 'en' ? 'Statement' : `Statement (${LANG_NAMES[state.lang]} draft)`);
    para(c.statement[state.lang], { size: 10.2, after: 4 });
    if (state.lang !== 'en') para(`${LANG_NAMES[state.lang]} draft: check with a fluent speaker before signing.`, { size: 8.5, muted: true });

    heading('05', 'Report for the bank');
    para(bank, { size: 9.8 });

    heading('06', 'Next steps');
    para('1. Call your bank\'s fraud line immediately and give them section 05.\n2. Open a case at your nearest SAPS station. Bring this case pack and your phone with the original chats.\n3. Do not delete the chats until the police have what they need.\n4. Add the SAPS case number to your bank report once you have it.', { size: 9.8 });

    // footers
    const pages = doc.getNumberOfPages();
    for (let p = 1; p <= pages; p++) {
      doc.setPage(p);
      doc.setDrawColor(220, 227, 234); doc.setLineWidth(0.3); doc.line(M, H - 12, W - M, H - 12);
      doc.setFont('helvetica', 'normal'); doc.setFontSize(7.5); doc.setTextColor(84, 96, 112);
      doc.text(pdfSafe(`Ubufakazi by Team CyberThreat  |  ${c.caseId}  |  Demo prototype`), M, H - 7.5);
      doc.text(`Page ${p} of ${pages}`, W - M, H - 7.5, { align: 'right' });
    }
    doc.setProperties({ title: `Ubufakazi case file ${c.caseId}`, subject: 'Scam case file (demo)', creator: 'Ubufakazi by Team CyberThreat' });
    doc.save(`${c.caseId}_case_pack.pdf`);
  }

  // ---------------------------------------------------------------- wire up
  function init() {
    $('#caseForm').addEventListener('submit', build);
    $('#demoA').addEventListener('click', () => loadDemo(DEMO_A));
    $('#demoB').addEventListener('click', () => loadDemo(DEMO_B));
    $('#evidence').addEventListener('change', (e) => { addFiles(e.target.files); e.target.value = ''; });
    $('#chatFile').addEventListener('change', async (e) => {
      const f = e.target.files[0];
      if (!f) return;
      $('#chat').value = await f.text();
      setMsg(`Loaded chat export "${f.name}".`);
      e.target.value = '';
    });
    const drop = $('#drop');
    ['dragenter', 'dragover'].forEach((t) => drop.addEventListener(t, (e) => { e.preventDefault(); drop.classList.add('over'); }));
    ['dragleave', 'drop'].forEach((t) => drop.addEventListener(t, (e) => { e.preventDefault(); drop.classList.remove('over'); }));
    drop.addEventListener('drop', (e) => {
      const files = [...e.dataTransfer.files];
      const txt = files.find((f) => /\.txt$/i.test(f.name));
      if (txt && !$('#chat').value.trim()) txt.text().then((t) => { $('#chat').value = t; });
      addFiles(files.filter((f) => f !== txt));
    });
    document.querySelectorAll('.tabs .tab').forEach((t) => t.addEventListener('click', () => setLang(t.dataset.lang)));
    $('#pdfBtn').addEventListener('click', makePdf);
    $('#consentBtn').addEventListener('click', addReport);
    $('#newBtn').addEventListener('click', () => {
      $('#caseForm').reset();
      state.files.forEach((f) => f.url && URL.revokeObjectURL(f.url));
      state.files = []; state.result = null;
      renderFiles(); setMsg('');
      $('#results').hidden = true;
      $('#report').scrollIntoView({ block: 'start' });
    });
    $('#resetBtn').addEventListener('click', () => {
      try { localStorage.removeItem(LOCAL_KEY); } catch { /* ignore */ }
      toast('Demo data reset. Only the sample network remains.');
    });
    document.querySelectorAll('[data-copy]').forEach((b) => b.addEventListener('click', async () => {
      const t = $('#' + b.dataset.copy).value;
      try { await navigator.clipboard.writeText(t); toast('Copied'); } catch { $('#' + b.dataset.copy).select(); toast('Press Ctrl+C to copy'); }
    }));
  }

  // expose the engine for testing in the browser console
  window.UBF = { parseChat, extract, guessScammer, detectType, shingles, containment };
  init();
})();
