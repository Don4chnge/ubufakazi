/* Public web reporting form (same pipeline as the Telegram bot). */
"use strict";

(() => {
  const { el, api, toast, size, sha256, download } = UBF;
  const app = document.getElementById("app");
  let meta = null;
  const picked = [];          // {file, hash}

  document.getElementById("quickExit").addEventListener("click", () => {
    try { document.querySelectorAll("form").forEach((f) => f.reset()); picked.length = 0; sessionStorage.clear(); } catch (_) { /* ignore */ }
    location.replace("https://www.google.com/search?q=weather+today");
  });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && e.shiftKey) document.getElementById("quickExit").click(); });

  async function boot() {
    try { meta = await api("GET", "/api/public/meta"); } catch (e) { app.replaceChildren(el("div", { class: "notice" }, "The reporting service is not available right now. " + e.message)); return; }
    form();
  }

  function field(id, label, input, hint) {
    return el("div", { class: "field" }, el("label", { for: id }, label), input, hint ? el("p", { class: "hint" }, hint) : null);
  }
  const opt = (v, t, sel) => el("option", { value: v, selected: sel ? true : null }, t);

  function form() {
    const cat = el("select", { id: "category", name: "category", required: true }, opt("", "Choose…", true), Object.entries(meta.categories).map(([k, v]) => opt(k, v)));
    const safety = el("div", { class: "notice warn", hidden: true },
      el("div", null, el("b", null, "Are you safe right now? "), "If not, please call 10111 or the GBV Command Centre on 0800 428 428 first. You can leave this page instantly with Quick exit (or Shift + Esc).",
        el("label", { class: "check" }, el("input", { type: "checkbox", name: "unsafe", value: "yes", id: "unsafe" }), "I am not safe / not sure (officers will treat this report as sensitive)")));
    const prov = el("select", { id: "province", name: "province", required: true }, opt("", "Choose…", true), meta.provinces.map((p) => opt(p, p)));
    const dl = el("datalist", { id: "towns" });
    const town = el("input", { type: "text", id: "town", name: "town", list: "towns", maxlength: "80", autocomplete: "address-level2" });
    const when = el("input", { type: "text", id: "when", name: "incident_when", maxlength: "80", placeholder: "e.g. 12 October 2026, or yesterday" });
    const desc = el("textarea", { id: "desc", name: "description", rows: "5", required: true, minlength: "10", maxlength: "8000", placeholder: "What happened, in your own words. Please don't include your ID number." });
    const lang = el("select", { id: "lang", name: "language" }, Object.entries(meta.languages).map(([k, v]) => opt(k, v, k === "en")));
    const name = el("input", { type: "text", id: "cname", name: "complainant_name", maxlength: "120", autocomplete: "name" });
    const amount = el("input", { type: "text", id: "amount", name: "amount_paid", maxlength: "40", placeholder: "e.g. R3 500" });
    const amountField = field("amount", "How much did you pay in total? (optional)", amount);
    const paste = el("textarea", { id: "paste", name: "pasted_text", rows: "5", placeholder: "Optional: paste the other person's messages here, or add the WhatsApp chat export (.txt) above." });
    const fileInput = el("input", { type: "file", id: "files", multiple: true, class: "sr-only",
      accept: ".txt,.pdf,.jpg,.jpeg,.png,.webp,.gif,.mp3,.ogg,.oga,.opus,.wav,.m4a,.mp4,.mov,.webm,text/plain,application/pdf,image/*,audio/*,video/*" });
    const list = el("ul", { class: "files" });
    const drop = el("label", { class: "drop", for: "files" }, UBF.icon(["M12 16V4M7 9l5-5 5 5", "M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3"]), el("b", null, "Drop files here or tap to choose"),
      el("span", { class: "muted small" }, `Screenshots, proof of payment, chat exports, voice notes, videos · up to ${meta.limits.max_files} files, ${meta.limits.max_file_mb} MB each`));
    const consent = el("input", { type: "checkbox", id: "consent", name: "consent", value: "yes", required: true });
    const msg = el("p", { class: "err-msg", role: "alert" });
    const submit = el("button", { class: "btn btn-primary", type: "submit" }, "Submit report");

    prov.addEventListener("change", () => { dl.replaceChildren(...(meta.towns[prov.value] || []).map((t) => el("option", { value: t }))); });
    cat.addEventListener("change", () => {
      safety.hidden = !["abuse", "threats"].includes(cat.value);
      amountField.hidden = !["scam", "banking_fraud"].includes(cat.value);
    });
    amountField.hidden = true;

    const addFiles = async (files) => {
      for (const f of files) {
        if (picked.length >= meta.limits.max_files) { toast(`At most ${meta.limits.max_files} files.`, true); break; }
        if (f.size > meta.limits.max_file_mb * 1048576) { toast(`${f.name} is larger than ${meta.limits.max_file_mb} MB.`, true); continue; }
        const item = { file: f, hash: null };
        picked.push(item);
        const hashEl = el("span", { class: "hash" }, "fingerprinting…");
        const li = el("li", null, el("span", { class: "n" }, f.name), el("span", { class: "muted small mono" }, size(f.size)), hashEl,
          el("button", { class: "btn btn-ghost btn-small", type: "button", onclick: () => { picked.splice(picked.indexOf(item), 1); li.remove(); } }, "Remove"));
        list.appendChild(li);
        item.hash = await sha256(f);
        hashEl.textContent = item.hash.slice(0, 12) + "…";
        hashEl.title = "SHA-256 calculated in your browser: " + item.hash;
      }
    };
    fileInput.addEventListener("change", () => { addFiles([...fileInput.files]); fileInput.value = ""; });
    ["dragover", "dragenter"].forEach((t) => drop.addEventListener(t, (e) => { e.preventDefault(); drop.classList.add("over"); }));
    ["dragleave", "drop"].forEach((t) => drop.addEventListener(t, () => drop.classList.remove("over")));
    drop.addEventListener("drop", (e) => { e.preventDefault(); addFiles([...e.dataTransfer.files]); });

    const f = el("form", { class: "form-grid", novalidate: true },
      el("fieldset", null, el("legend", null, el("span", { class: "n" }, "1"), "What happened"), field("category", "Type of incident", cat), safety),
      el("fieldset", null, el("legend", null, el("span", { class: "n" }, "2"), "Where and when"),
        el("div", { class: "grid3" }, field("province", "Province", prov), field("town", "Town or area", town, "Decides which demo station receives it."), field("when", "When did it happen?", when)), dl,
        el("p", { class: "hint" }, "We never ask for your GPS location or ID number.")),
      el("fieldset", null, el("legend", null, el("span", { class: "n" }, "3"), "In your own words"), field("desc", "Describe what happened", desc),
        el("div", { class: "grid3" }, field("lang", "Statement language", lang), field("cname", "Name for the statement (optional)", name, "You can also add it at the station."), amountField)),
      el("fieldset", null, el("legend", null, el("span", { class: "n" }, "4"), "Evidence"), fileInput, drop, list, field("paste", "Pasted messages (optional)", paste),
        el("p", { class: "hint" }, "Each file gets a SHA-256 fingerprint in your browser now and again on the server when it arrives, so you can see they match.")),
      el("fieldset", null, el("legend", null, el("span", { class: "n" }, "5"), "Consent"), el("p", { class: "small" }, meta.consent.text),
        el("label", { class: "check" }, consent, "I understand and agree. I am using demo or test data.")),
      msg, el("div", null, submit));

    f.addEventListener("submit", async (e) => {
      e.preventDefault(); msg.textContent = "";
      if (!cat.value) return (msg.textContent = "Please choose the type of incident.");
      if (!prov.value) return (msg.textContent = "Please choose a province.");
      if (desc.value.trim().length < 10) return (msg.textContent = "Please describe what happened (at least a sentence).");
      if (/\b\d{13}\b/.test(desc.value)) return (msg.textContent = "It looks like you typed an ID number. Please remove it: it isn't needed here.");
      if (!consent.checked) return (msg.textContent = "Please read and accept the consent notice.");
      const fd = new FormData(f);
      fd.delete("files");
      picked.forEach((p) => fd.append("files", p.file, p.file.name));
      submit.disabled = true; submit.textContent = "Submitting…";
      try {
        const out = await api("POST", "/api/public/reports", fd);
        receipt(out);
      } catch (ex) { msg.textContent = ex.message; } finally { submit.disabled = false; submit.textContent = "Submit report"; }
    });
    app.replaceChildren(f);
  }

  function warningPanel(body) {
    const out = el("div");
    const btn = el("button", { class: "btn btn-primary", type: "button", onclick: async () => {
      btn.disabled = true;
      try {
        const w = await api("POST", "/api/public/warning", body);
        const P = UBFShare.PRESETS, key = w.category === "banking_fraud" ? "banking" : (P[w.scam_type] ? w.scam_type : "other");
        UBFShare.tool(out, { title: w.scam_type_label || P[key].label, where: w.province, flags: w.red_flags.length ? w.red_flags : P[key].flags, rule: P[key].rule, optional: w.optional });
        btn.remove();
      } catch (e) { toast(e.message, true); btn.disabled = false; }
    } }, "Create a scam warning");
    return el("section", { class: "panel" }, el("div", { class: "kicker" }, "Warn your community"), el("h3", null, "Share a warning, not your details"),
      el("p", { class: "muted" }, "Make a ready-to-post warning for WhatsApp, Facebook, X or Instagram from this report. Your name, bank details, case reference and evidence are never included."),
      btn, out);
  }

  function receipt(out) {
    const browserHash = new Map(picked.map((p) => [p.file.name, p.hash]));
    const packBtn = el("button", { class: "btn btn-primary", disabled: true }, "Preparing your case pack…");
    const keyText = `Reference: ${out.reference}\nReceipt key: ${out.receipt_key}`;
    const stack = el("div", { class: "stack" },
      el("section", { class: "receipt" }, el("div", { class: "kicker" }, "Report submitted"),
        el("div", { class: "grid2" }, el("div", null, el("div", { class: "muted small" }, "Reference"), el("div", { class: "big" }, out.reference)),
          el("div", null, el("div", { class: "muted small" }, "Private receipt key"), el("div", { class: "big" }, out.receipt_key))),
        el("p", { class: "small" }, "Save both now: the key is shown only once. Together they let you track this report and download your case pack. Keep the key private."),
        el("div", { class: "row-btns" },
          el("button", { class: "btn btn-ghost btn-small", onclick: () => navigator.clipboard.writeText(keyText).then(() => toast("Copied.")) }, "Copy reference and key"),
          el("button", { class: "btn btn-ghost btn-small", onclick: () => download(new Blob([keyText + "\n\nTrack at: " + location.origin + "/track\n"], { type: "text/plain" }), `Ubufakazi-${out.reference}-receipt.txt`) }, "Save as file"))),
      el("section", { class: "panel" }, el("h3", null, "What happens next"),
        el("ol", { class: "steps-v" },
          el("li", { class: "done" }, "Your files were fingerprinted (SHA-256) on arrival."),
          el("li", { id: "stepPack" }, "Ubufakazi prepares your fraud dispute statement for the bank and your case pack (a few seconds)."),
          el("li", null, "If the account you paid is at a bank connected to Ubufakazi, that bank gets a fraud alert automatically (in this demo: Ubuntu Trust Bank, a fictional bank). Track this report to see the bank's decision."),
          el("li", null, "Call your bank's fraud line now and send them the statement in your case pack: the faster the bank acts, the more likely the money can be frozen."),
          el("li", null, `A police-ready copy is also kept for ${out.station} (a fictional demo station), if you choose to report there too.`)),
        packBtn),
      out.evidence.length || out.rejected.length ? el("section", { class: "panel" }, el("h3", null, "Evidence received"),
        el("div", { class: "table-wrap" }, el("table", { class: "data" },
          el("thead", null, el("tr", null, ["File", "Size", "Server SHA-256", "Matches your browser?"].map((h) => el("th", null, h)))),
          el("tbody", null, out.evidence.map((e) => {
            const bh = browserHash.get(e.name);
            return el("tr", null, el("td", null, e.name), el("td", { class: "num" }, size(e.size)), el("td", { class: "hash" }, e.sha256),
              el("td", null, bh ? (bh === e.sha256 ? el("span", { class: "verify-ok" }, "✓ identical") : el("span", { class: "verify-bad" }, "✗ different")) : el("span", { class: "muted" }, "pasted text")));
          })))),
        out.rejected.map((r) => el("div", { class: "notice" }, el("b", null, r.name + ": "), r.reason))) : null);
    app.replaceChildren(stack);
    window.scrollTo(0, 0);

    const body = { reference: out.reference, key: out.receipt_key };
    let tries = 0;
    const poll = async () => {
      tries++;
      try {
        const t = await api("POST", "/api/public/track", body);
        if (t.processing_status === "ready") {
          packBtn.disabled = false; packBtn.textContent = "Download my case pack (PDF)";
          packBtn.onclick = async () => { try { download(await api("POST", "/api/public/pack", body, { blob: true }), `Ubufakazi-${out.reference}.pdf`); } catch (e) { toast(e.message, true); } };
          stack.append(warningPanel(body));
          const sp = document.getElementById("stepPack"); if (sp) sp.classList.add("done");
          return;
        }
        if (t.processing_status === "error") { packBtn.textContent = "Could not prepare the pack automatically. Your report is safe."; return; }
      } catch (_) { /* try again */ }
      if (tries > 8) packBtn.textContent = "Reading your evidence (voice notes and screenshots can take a minute or two)…";
      if (tries < 140) setTimeout(poll, tries < 20 ? 1500 : 3000);
      else { packBtn.textContent = "Still preparing. Open the Track page later with your reference and key.";
             stack.append(el("p", null, el("a", { class: "btn btn-ghost", href: "/track" }, "Open the Track page"))); }
    };
    setTimeout(poll, 800);
  }

  boot();
})();
