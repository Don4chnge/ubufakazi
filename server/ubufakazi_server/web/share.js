/* Social-media scam warnings. Renders a 1080x1350 card (good for WhatsApp Status, Instagram, Facebook, X) and a text version.
   Privacy rules: never includes the victim's name, case reference, receipt key, bank account numbers or evidence.
   Optional items (website, partly hidden number) appear only when the user ticks them. */
"use strict";

const UBFShare = (() => {
  const { el, toast, download } = UBF;
  const SITE = location.origin;

  const PRESETS = {
    job: { label: "Fake job offer", rule: "Real employers never ask you to pay to get a job.",
      flags: ["Asked for a 'registration', 'uniform' or 'training' fee", "Offered a job you never applied for, or after a very short chat", "Pressured you to pay today or lose the position", "Asked you to pay into a personal bank account"] },
    parcel: { label: "Fake courier / parcel fee", rule: "Check deliveries only on the courier's official website or app.",
      flags: ["Message about a parcel you were not expecting", "Asked for a customs or clearance fee by link", "Threatened to return or destroy the parcel", "Link to a website that is not the courier's official site"] },
    sars: { label: "Fake SARS refund", rule: "SARS does not send refund links. Use eFiling or the SARS MobiApp.",
      flags: ["Promised a tax refund by SMS, WhatsApp or email", "Link asking for your banking details or login", "Deadline to 'claim' within hours"] },
    investment: { label: "Investment / crypto scam", rule: "Guaranteed high returns are a warning sign. Check the FSCA register first.",
      flags: ["Promised guaranteed or very fast returns", "Asked you to recruit others or pay to withdraw", "Account manager on WhatsApp or Telegram only", "Could not withdraw your money"] },
    marketplace: { label: "Online seller / marketplace scam", rule: "Pay only through the platform, or on collection after you see the item.",
      flags: ["Price far below normal", "Asked for full payment or a deposit before delivery", "Refused to meet or show the item", "Sent a fake proof of payment"] },
    romance: { label: "Romance scam", rule: "Never send money to someone you have only met online.",
      flags: ["Relationship moved fast, but they never meet or video-call", "Sudden emergency that needs money", "Asked for gift cards, crypto or transfers"] },
    banking: { label: "Bank impersonation / OTP scam", rule: "Your bank will never ask for your OTP, PIN or password.",
      flags: ["Caller or message claiming to be your bank's fraud team", "Asked for an OTP, PIN or password", "Asked you to move money to a 'safe' account", "Link to a fake banking website"] },
    other: { label: "Scam warning", rule: "If someone pressures you to pay quickly, stop and check first.",
      flags: ["Asked for money upfront", "Pressured you to act quickly", "Stopped responding after payment"] },
  };

  function wrap(ctx, text, maxW) {
    const words = String(text).split(/\s+/), lines = [];
    let line = "";
    for (const w of words) {
      const test = line ? line + " " + w : w;
      if (ctx.measureText(test).width > maxW && line) { lines.push(line); line = w; } else line = test;
    }
    if (line) lines.push(line);
    return lines;
  }

  async function render(canvas, d) {
    try { await Promise.all(["700 60px 'Space Grotesk'", "500 30px Inter", "600 30px Inter"].map((f) => document.fonts.load(f))); } catch (_) { /* fallback fonts */ }
    const c = canvas.getContext("2d"), W = 1080, H = 1350;
    canvas.width = W; canvas.height = H;
    // background
    let g = c.createLinearGradient(0, 0, W, H); g.addColorStop(0, "#04101F"); g.addColorStop(1, "#020610");
    c.fillStyle = g; c.fillRect(0, 0, W, H);
    g = c.createRadialGradient(W * 0.85, 120, 20, W * 0.85, 120, 700); g.addColorStop(0, "rgba(255,93,108,0.28)"); g.addColorStop(1, "rgba(255,93,108,0)");
    c.fillStyle = g; c.fillRect(0, 0, W, H);
    g = c.createRadialGradient(80, H - 80, 20, 80, H - 80, 700); g.addColorStop(0, "rgba(46,230,214,0.18)"); g.addColorStop(1, "rgba(46,230,214,0)");
    c.fillStyle = g; c.fillRect(0, 0, W, H);
    c.strokeStyle = "rgba(120,190,255,0.06)"; c.lineWidth = 1;
    for (let x = 0; x < W; x += 54) { c.beginPath(); c.moveTo(x, 0); c.lineTo(x, H); c.stroke(); }
    for (let y = 0; y < H; y += 54) { c.beginPath(); c.moveTo(0, y); c.lineTo(W, y); c.stroke(); }
    // header
    c.strokeStyle = "#2EE6D6"; c.lineWidth = 4; c.lineJoin = "round"; c.lineCap = "round";
    c.beginPath(); c.moveTo(90, 76); c.lineTo(122, 89); c.lineTo(122, 116); c.quadraticCurveTo(120, 140, 90, 152); c.quadraticCurveTo(60, 140, 58, 116); c.lineTo(58, 89); c.closePath(); c.stroke();
    c.fillStyle = "#EEF5FF"; c.font = "700 38px 'Space Grotesk', sans-serif"; c.fillText("UBUFAKAZI", 146, 112);
    c.fillStyle = "#8FA6C4"; c.font = "500 24px Inter, sans-serif"; c.fillText("Community scam warning", 146, 146);
    // badge
    c.fillStyle = "rgba(255,93,108,0.16)"; roundRect(c, 60, 210, 360, 64, 32); c.fill();
    c.strokeStyle = "rgba(255,93,108,0.75)"; c.lineWidth = 2; roundRect(c, 60, 210, 360, 64, 32); c.stroke();
    c.fillStyle = "#FF8B96"; c.font = "700 30px 'Space Grotesk', sans-serif"; c.fillText("⚠  SCAM ALERT", 92, 252);
    // title
    c.fillStyle = "#FFFFFF"; c.font = "700 76px 'Space Grotesk', sans-serif";
    let y = 380;
    for (const line of wrap(c, d.title, W - 120).slice(0, 2)) { c.fillText(line, 60, y); y += 84; }
    c.fillStyle = "#8FA6C4"; c.font = "500 30px Inter, sans-serif";
    c.fillText(d.where ? `Reported in ${d.where}` : "Reported by the community", 60, y + 4); y += 70;
    // flags
    c.fillStyle = "#2EE6D6"; c.font = "600 26px Inter, sans-serif"; c.fillText("RED FLAGS", 60, y); y += 44;
    c.font = "500 33px Inter, sans-serif";
    for (const f of d.flags.slice(0, 5)) {
      const lines = wrap(c, f, W - 190);
      c.fillStyle = "#FF5D6C"; c.beginPath(); c.arc(78, y - 11, 9, 0, Math.PI * 2); c.fill();
      c.fillStyle = "#E3ECFA";
      for (const l of lines.slice(0, 2)) { c.fillText(l, 108, y); y += 44; }
      y += 12;
      if (y > 1010) break;
    }
    // optional extras
    const extras = [];
    for (const w of d.websites || []) extras.push(["Website used (do not open):", w.replace(/\./g, "[.]")]);
    for (const p of d.phones || []) extras.push(["Number used (partly hidden):", p]);
    for (const [k, v] of extras.slice(0, 2)) {
      if (y > 1040) break;
      c.fillStyle = "#8FA6C4"; c.font = "500 26px Inter, sans-serif"; c.fillText(k, 60, y + 6);
      c.fillStyle = "#FBBF24"; c.font = "500 30px 'JetBrains Mono', monospace"; c.fillText(v, 60, y + 46); y += 92;
    }
    // rule box
    const ry = Math.max(y + 10, 1060);
    c.fillStyle = "rgba(46,230,214,0.10)"; roundRect(c, 60, ry, W - 120, 120, 22); c.fill();
    c.strokeStyle = "rgba(46,230,214,0.5)"; c.lineWidth = 2; roundRect(c, 60, ry, W - 120, 120, 22); c.stroke();
    c.fillStyle = "#FFFFFF"; c.font = "600 31px Inter, sans-serif";
    const ruleLines = wrap(c, d.rule, W - 180).slice(0, 2);
    let ly = ruleLines.length === 1 ? ry + 71 : ry + 52; for (const l of ruleLines) { c.fillText(l, 90, ly); ly += 40; }
    // footer
    c.fillStyle = "#8FA6C4"; c.font = "500 24px Inter, sans-serif";
    c.fillText("In danger? Call 10111  ·  Report scams at " + SITE.replace(/^https?:\/\//, ""), 60, H - 62);
    c.fillStyle = "#5E7594"; c.font = "500 20px Inter, sans-serif";
    c.fillText(d.example ? "EXAMPLE  ·  no personal details included" : "Shared via Ubufakazi  ·  no personal details included", 60, H - 28);
  }

  function roundRect(c, x, y, w, h, r) { c.beginPath(); c.moveTo(x + r, y); c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r); c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath(); }

  function text(d) {
    const lines = [`⚠️ SCAM ALERT: ${d.title}`, d.where ? `Reported in ${d.where}.` : "", "", "Red flags:"];
    d.flags.forEach((f) => lines.push(`• ${f}`));
    (d.websites || []).forEach((w) => lines.push(`Website used (do not open): ${w.replace(/\./g, "[.]")}`));
    (d.phones || []).forEach((p) => lines.push(`Number used (partly hidden): ${p}`));
    lines.push("", d.rule, "", `If you've been scammed, report it and keep your evidence safe: ${SITE}/report`, "In danger? Call 10111.");
    return lines.filter((l, i, a) => !(l === "" && a[i - 1] === "")).join("\n");
  }

  /** Build the full share tool inside `root`. data: {title, where, flags, rule, optional: {websites, phones_masked}} */
  function tool(root, data) {
    const opt = data.optional || {};
    const state = { web: false, phone: false };
    const canvas = el("canvas", { width: "1080", height: "1350", "aria-label": "Scam warning image preview" });
    const ta = el("textarea", { rows: "11", class: "share-text", readonly: true, "aria-label": "Warning text" });
    const current = () => ({ ...data, websites: state.web ? opt.websites || [] : [], phones: state.phone ? opt.phones_masked || [] : [] });
    const refresh = () => { const d = current(); ta.value = text(d); render(canvas, d); };
    const box = (key, label, items) => items && items.length ? el("label", { class: "check" },
      el("input", { type: "checkbox", onchange: (e) => { state[key] = e.target.checked; refresh(); } }), label + ": " + items.join(", ")) : null;
    const pngBlob = () => new Promise((res) => canvas.toBlob(res, "image/png"));
    const enc = encodeURIComponent;
    const shareBtns = el("div", { class: "share-btns" },
      el("button", { class: "btn btn-primary", type: "button", onclick: async () => download(await pngBlob(), "ubufakazi-scam-warning.png") }, "Download image"),
      el("button", { class: "btn btn-ghost", type: "button", onclick: () => navigator.clipboard.writeText(ta.value).then(() => toast("Warning text copied.")) }, "Copy text"),
      el("a", { class: "btn btn-ghost", target: "_blank", rel: "noopener", href: "#", onclick: (e) => { e.currentTarget.href = "https://wa.me/?text=" + enc(ta.value); } }, "WhatsApp"),
      el("a", { class: "btn btn-ghost", target: "_blank", rel: "noopener", href: "#", onclick: (e) => { e.currentTarget.href = "https://x.com/intent/post?text=" + enc(ta.value.slice(0, 260)); } }, "X (Twitter)"),
      el("a", { class: "btn btn-ghost", target: "_blank", rel: "noopener", href: "https://www.facebook.com/sharer/sharer.php?u=" + enc(SITE + "/share") }, "Facebook"),
      navigator.canShare ? el("button", { class: "btn btn-ghost", type: "button", onclick: async () => {
        try {
          const file = new File([await pngBlob()], "ubufakazi-scam-warning.png", { type: "image/png" });
          if (navigator.canShare({ files: [file] })) await navigator.share({ files: [file], text: ta.value });
          else await navigator.share({ text: ta.value });
        } catch (_) { /* user cancelled */ }
      } }, "Share…") : null);
    root.replaceChildren(el("div", { class: "share-grid" },
      el("div", { class: "stack" },
        el("section", { class: "panel" }, el("h3", null, "What will be shared"),
          el("p", { class: "muted small" }, "Only the scam type, the tricks used and safety advice. Never your name, case reference, bank details or evidence."),
          (opt.websites || []).length || (opt.phones_masked || []).length ? el("div", { class: "stack" },
            el("p", { class: "hint" }, "Optional (off by default). Only add these if you are sure. Numbers can be spoofed and websites can be hacked:"),
            box("web", "Include the website", opt.websites), box("phone", "Include the number, partly hidden", opt.phones_masked)) : null),
        el("section", { class: "panel" }, el("h3", null, "Post it"), shareBtns,
          el("p", { class: "hint" }, "Facebook can't take pre-filled text: copy the text first, then paste it into your post. For Instagram, download the image."),
          el("div", { class: "field" }, el("label", null, "Warning text"), ta))),
      el("div", { class: "share-preview" }, canvas)));
    refresh();
  }

  return { PRESETS, render, text, tool };
})();
