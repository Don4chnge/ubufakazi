/* Offline integrity check: SHA-256 is computed in the browser; the file is never uploaded. */
"use strict";

(() => {
  const { el, sha256, size } = UBF;
  const app = document.getElementById("app");
  const input = el("input", { type: "file", id: "vf", multiple: true });
  const expected = el("textarea", { id: "vh", rows: "3", placeholder: "Paste one or more SHA-256 fingerprints from the case pack (64 characters each)", spellcheck: "false" });
  const out = el("div", { "aria-live": "polite" });

  async function run() {
    const want = new Set((expected.value.toLowerCase().match(/[0-9a-f]{64}/g) || []));
    const files = [...input.files];
    if (!files.length) { out.replaceChildren(el("p", { class: "muted" }, "Choose a file to check.")); return; }
    out.replaceChildren(el("p", { class: "muted" }, "Calculating…"));
    const rows = [];
    for (const f of files) {
      const h = await sha256(f);
      const verdict = !want.size ? el("span", { class: "muted" }, "no fingerprint pasted to compare")
        : want.has(h) ? el("span", { class: "verify-ok" }, "✓ Matches: this file is identical to the one fingerprinted")
        : el("span", { class: "verify-bad" }, "✗ No match: this file differs from every pasted fingerprint (or a different file was chosen)");
      rows.push(el("tr", null, el("td", null, f.name, el("span", { class: "sub" }, size(f.size))), el("td", { class: "hash" }, h), el("td", null, verdict)));
    }
    out.replaceChildren(el("div", { class: "table-wrap" }, el("table", { class: "data" },
      el("thead", null, el("tr", null, ["File", "SHA-256 (calculated here)", "Result"].map((t) => el("th", null, t)))), el("tbody", null, rows))));
  }

  // ---------------------------------------------------------------- sealed documents (case packs)
  const sealId = (new URLSearchParams(location.search).get("seal") || "").toUpperCase().replace(/[^A-Z0-9-]/g, "").slice(0, 24);
  const sealOut = el("div", { "aria-live": "polite" });
  const sealFile = el("input", { type: "file", id: "sf", accept: "application/pdf,.pdf" });
  let seal = null;
  const sealCard = (s) => el("dl", { class: "facts" },
    el("dt", null, "Document"), el("dd", null, s.document),
    el("dt", null, "Report"), el("dd", { class: "mono" }, s.reference),
    el("dt", null, "Issued"), el("dd", null, UBF.dateTime(s.issued_at) + " to " + s.issued_to),
    el("dt", null, "Sealed fingerprint"), el("dd", { class: "hash" }, s.sha256),
    el("dt", null, "Independent timestamp"), el("dd", null, s.timestamp ? `${UBF.dateTime(s.timestamp.gen_time)} · ${s.timestamp.tsa}` : "Not available for this document"));
  async function checkSealed() {
    const f = sealFile.files[0];
    if (!f) return;
    sealOut.replaceChildren(el("p", { class: "muted" }, "Calculating the fingerprint on this device…"));
    const h = await sha256(f);
    if (seal) {
      sealOut.replaceChildren(h === seal.sha256
        ? el("div", { class: "seal-verdict ok" }, el("b", null, "✓ AUTHENTIC AND UNCHANGED"), el("span", null, `This is exactly the document sealed as ${seal.seal_id}.`))
        : el("div", { class: "seal-verdict bad" }, el("b", null, "✗ ALTERED OR NOT THIS DOCUMENT"), el("span", null, "This file's fingerprint does not match the seal. It was changed after it was issued, or it is a different file.")),
        el("p", { class: "hint mono" }, "This file: " + h));
      return;
    }
    try {
      const s = await UBF.api("GET", "/api/public/seal-by-hash/" + h);
      sealOut.replaceChildren(el("div", { class: "seal-verdict ok" }, el("b", null, "✓ AUTHENTIC AND UNCHANGED"), el("span", null, `Issued by Ubufakazi as ${s.seal_id}.`)), sealCard(s));
    } catch (_) {
      sealOut.replaceChildren(el("div", { class: "seal-verdict bad" }, el("b", null, "✗ NOT A DOCUMENT UBUFAKAZI ISSUED, OR IT WAS CHANGED"), el("span", null, "No sealed document has this exact fingerprint.")), el("p", { class: "hint mono" }, "This file: " + h));
    }
  }
  sealFile.addEventListener("change", checkSealed);
  const sealPanel = el("section", { class: "panel stack seal-panel" },
    el("div", { class: "kicker" }, sealId ? "Sealed document " + sealId : "Check a sealed document"),
    el("h2", null, "Is this case pack genuine?"),
    el("p", { class: "muted" }, "Every case pack Ubufakazi issues is sealed: its fingerprint and an independent timestamp are recorded when it is issued. Choose the PDF: your browser fingerprints it (the file is not uploaded) and compares it with the seal."),
    el("div", { id: "sealInfo" }),
    el("div", { class: "field" }, el("label", { for: "sf" }, "Case pack PDF"), sealFile), sealOut);
  if (sealId) {
    UBF.api("GET", "/api/public/seal/" + encodeURIComponent(sealId)).then((s) => { seal = s; sealPanel.querySelector("#sealInfo").replaceChildren(sealCard(s)); })
      .catch(() => { sealPanel.querySelector("#sealInfo").replaceChildren(el("div", { class: "seal-verdict bad" }, el("b", null, "✗ UNKNOWN SEAL"), el("span", null, "Ubufakazi never issued a document with this seal. The paper may be forged."))); });
  }

  input.addEventListener("change", run);
  expected.addEventListener("input", run);
  app.replaceChildren(sealPanel, el("h2", { class: "section-title" }, "Check an evidence file"), el("section", { class: "panel stack" },
    el("div", { class: "field" }, el("label", { for: "vf" }, "File(s) to check"), input),
    el("div", { class: "field" }, el("label", { for: "vh" }, "Expected fingerprint(s)"), expected),
    out,
    el("p", { class: "hint" }, "A matching fingerprint shows the file is bit-for-bit the same as when Ubufakazi received it. It does not prove what the file shows is true.")));
})();
