/* Demo-account helper. Derives each demo account's password and two-factor code from UBF_DEMO_SEED
   exactly like server/ubufakazi_server/creds.py does, using the browser's Web Crypto.
   The seed is never sent anywhere: there is no network request on this page. */
"use strict";

(() => {
  const { el, toast } = UBF;
  const WORDS = ["amandla", "ubuntu", "indlela", "isibane", "ilanga", "inkanyezi", "umthetho", "ubulungisa", "imvula", "intaba",
    "umfula", "isikhwama", "ithemba", "inqaba", "ukukhanya", "isiqhamo"];
  const USERS = [["admin", "Administrator (all stations, audit log)"], ["officer.mthatha", "Officer · Demo Station Mthatha"],
    ["officer.joburg", "Officer · Johannesburg Central + Alberton"], ["officer.durban", "Officer · Durban Central"],
    ["bank.reviewer", "DemoBank fraud reviewer (bank demo)"]];
  const enc = new TextEncoder();

  async function hmac(alg, keyBytes, msgBytes) {
    const k = await crypto.subtle.importKey("raw", keyBytes, { name: "HMAC", hash: alg }, false, ["sign"]);
    return new Uint8Array(await crypto.subtle.sign("HMAC", k, msgBytes));
  }
  function b32(bytes) {
    const A = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"; let bits = 0, val = 0, out = "";
    for (const b of bytes) { val = (val << 8) | b; bits += 8; while (bits >= 5) { out += A[(val >>> (bits - 5)) & 31]; bits -= 5; } }
    if (bits > 0) out += A[(val << (5 - bits)) & 31];
    return out;
  }
  async function totp(secretBytes, t = Date.now()) {
    let c = Math.floor(t / 1000 / 30); const msg = new Uint8Array(8);
    for (let i = 7; i >= 0; i--) { msg[i] = c & 255; c = Math.floor(c / 256); }
    const h = await hmac("SHA-1", secretBytes, msg), o = h[19] & 15;
    const n = ((h[o] & 127) << 24) | (h[o + 1] << 16) | (h[o + 2] << 8) | h[o + 3];
    return String(n % 1000000).padStart(6, "0");
  }
  async function derive(seed, username) {
    const s = enc.encode(seed);
    const d = await hmac("SHA-256", s, enc.encode("password:" + username));
    const password = [0, 1, 2, 3].map((i) => WORDS[d[i] % WORDS.length]).join("-") + "-" + (1000 + ((d[4] << 8) | d[5]) % 9000);
    const sec = (await hmac("SHA-256", s, enc.encode("totp:" + username))).slice(0, 20);
    return { password, secret: b32(sec), secretBytes: sec };
  }

  const app = document.getElementById("app");
  const seedIn = el("input", { type: "password", id: "seed", placeholder: "Paste UBF_DEMO_SEED from Render › Environment", autocomplete: "off", spellcheck: "false" });
  const out = el("div");
  let timer = 0;
  async function run() {
    clearInterval(timer);
    const seed = seedIn.value.trim();
    if (seed.length < 20) { out.replaceChildren(el("p", { class: "muted" }, "Paste the seed (20+ characters) to see the logins.")); return; }
    const rows = await Promise.all(USERS.map(async ([u, role]) => ({ u, role, ...(await derive(seed, u)) })));
    const codeEls = [];
    const copy = (txt, what) => navigator.clipboard.writeText(txt).then(() => toast(what + " copied."));
    out.replaceChildren(el("div", { class: "table-wrap" }, el("table", { class: "data" },
      el("thead", null, el("tr", null, ["Username", "Password", "Code now", "Authenticator setup key"].map((h) => el("th", null, h)))),
      el("tbody", null, rows.map((r) => {
        const code = el("b", { class: "mono otp-now" }, "······"); codeEls.push([code, r.secretBytes]);
        return el("tr", null,
          el("td", null, el("span", { class: "ref" }, r.u), el("span", { class: "sub" }, r.role)),
          el("td", null, el("button", { class: "btn btn-ghost btn-small", type: "button", onclick: () => copy(r.password, "Password") }, r.password)),
          el("td", null, code),
          el("td", null, el("button", { class: "btn btn-ghost btn-small mono", type: "button", onclick: () => copy(r.secret, "Setup key") }, r.secret)));
      })))),
      el("p", { class: "hint" }, "Codes change every 30 seconds. Click a password or key to copy it. To use a phone instead: Google or Microsoft Authenticator › + › Enter a setup key › time-based."));
    const tick = async () => { for (const [e, s] of codeEls) e.textContent = await totp(s); };
    tick(); timer = setInterval(tick, 2000);
  }
  seedIn.addEventListener("input", run);
  app.replaceChildren(el("section", { class: "panel stack" },
    el("div", { class: "notice info" }, el("b", null, "Private helper. "), "Everything is calculated in this browser. The seed is not sent anywhere and nothing is saved. Close the tab when you are done."),
    el("div", { class: "field" }, el("label", { for: "seed" }, "Demo seed (UBF_DEMO_SEED)"), seedIn), out));
  run();
  window.UBFDemoLogins = { derive, totp };   // used by the automated parity test
})();
