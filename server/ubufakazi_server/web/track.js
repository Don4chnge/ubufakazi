/* Track a report with reference + private receipt key; download the case pack; add more evidence. */
"use strict";

(() => {
  const { el, api, toast, size, dateTime, download } = UBF;
  const app = document.getElementById("app");

  function lookup(prefill) {
    const ref = el("input", { type: "text", id: "ref", placeholder: "UBF-26-XXXXXX", maxlength: "24", autocomplete: "off", spellcheck: "false", value: prefill?.reference || "" });
    const key = el("input", { type: "password", id: "key", placeholder: "XXXX-XXXX-XXXX", maxlength: "24", autocomplete: "off", spellcheck: "false" });
    const msg = el("p", { class: "err-msg", role: "alert" });
    const f = el("form", { class: "panel stack" },
      el("div", { class: "grid2" }, el("div", { class: "field" }, el("label", { for: "ref" }, "Reference"), ref), el("div", { class: "field" }, el("label", { for: "key" }, "Receipt key"), key)),
      msg, el("div", null, el("button", { class: "btn btn-primary", type: "submit" }, "Check status")));
    f.addEventListener("submit", async (e) => {
      e.preventDefault(); msg.textContent = "";
      const body = { reference: ref.value.trim().toUpperCase(), key: key.value.trim().toUpperCase() };
      try { show(body, await api("POST", "/api/public/track", body)); } catch (ex) { msg.textContent = ex.message; }
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

  function show(body, t) {
    const fileInput = el("input", { type: "file", id: "more", multiple: true });
    const addBtn = el("button", { class: "btn btn-ghost btn-small", type: "button", onclick: async () => {
      if (!fileInput.files.length) return toast("Choose one or more files first.", true);
      const fd = new FormData();
      fd.append("reference", body.reference); fd.append("key", body.key);
      [...fileInput.files].forEach((f) => fd.append("files", f, f.name));
      addBtn.disabled = true;
      try {
        const r = await api("POST", "/api/public/evidence", fd);
        toast(`Added ${r.added.length} file(s).` + (r.rejected.length ? ` Not accepted: ${r.rejected.map((x) => x.name).join(", ")}.` : ""), !!r.rejected.length);
        show(body, await api("POST", "/api/public/track", body));
      } catch (e) { toast(e.message, true); } finally { addBtn.disabled = false; }
    } }, "Add files");
    const packBtn = el("button", { class: "btn btn-primary", disabled: t.processing_status !== "ready" ? true : null, onclick: async () => {
      try { download(await api("POST", "/api/public/pack", body, { blob: true }), `Ubufakazi-${t.reference}.pdf`); } catch (e) { toast(e.message, true); }
    } }, t.processing_status === "ready" ? "Download case pack (PDF)" : "Case pack being prepared…");
    app.replaceChildren(el("div", { class: "stack" },
      el("section", { class: "receipt" }, el("div", { class: "kicker" }, t.station + " fraud desk · fictional bank"),
        el("div", { class: "big" }, t.reference), el("p", null, el("span", { class: "st st-" + t.status }, t.status_label), " ",
          el("span", { class: "muted small" }, "Submitted " + dateTime(t.submitted))),
        el("div", { class: "row-btns" }, packBtn, el("button", { class: "btn btn-ghost", onclick: () => lookup() }, "Check another"))),
      el("section", { class: "panel" }, el("h3", null, "Progress"),
        el("ol", { class: "steps-v" }, t.history.map((h) => el("li", { class: "done" }, el("b", null, h.label), el("div", { class: "muted small" }, dateTime(h.at))))),
        (t.bank_responses || []).map((b) => el("div", { class: "notice info" }, el("b", null, b.bank + " (fictional bank): "), b.status_label + ". ", b.note || "")),
        t.registration ? el("div", { class: "notice info" }, el("b", null, "Escalated to SAPS via " + t.registration.station + ": "), el("span", { class: "mono" }, t.registration.cas_number),
          " (the CAS number SAPS issued, entered by the bank's investigator; keep it for any follow-up).") : null,
        el("p", { class: "hint" }, "These are steps inside Ubufakazi's demo workflow. The bank's fraud desk investigates and escalates to SAPS; a SAPS case number exists only once SAPS registers the case. If the branch asks, show the QR code in your case pack.")),
      el("section", { class: "panel" }, el("h3", null, "Your evidence"),
        t.evidence.length ? el("div", { class: "table-wrap" }, el("table", { class: "data" },
          el("thead", null, el("tr", null, ["File", "Size", "Received", "SHA-256"].map((h) => el("th", null, h)))),
          el("tbody", null, t.evidence.map((e) => el("tr", null, el("td", null, e.name), el("td", { class: "num" }, size(e.size)), el("td", null, dateTime(e.received)), el("td", { class: "hash" }, e.sha256))))))
          : el("p", { class: "muted" }, "No files yet."),
        t.status !== "closed" ? el("div", { class: "field" }, el("label", { for: "more" }, "Add more evidence"), fileInput, el("div", null, addBtn)) : null,
        el("p", { class: "hint" }, "Want to check a copy of a file later? Use ", el("a", { href: "/verify" }, "Verify a file"), ": it compares fingerprints on your own device.")),
      t.processing_status === "ready" ? warningPanel(body) : null));
    if (t.processing_status !== "ready") setTimeout(async () => { try { show(body, await api("POST", "/api/public/track", body)); } catch (_) { /* ignore */ } }, 2000);
  }

  lookup();
})();
