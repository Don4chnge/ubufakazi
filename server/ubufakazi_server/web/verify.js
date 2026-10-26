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

  input.addEventListener("change", run);
  expected.addEventListener("input", run);
  app.replaceChildren(el("section", { class: "panel stack" },
    el("div", { class: "field" }, el("label", { for: "vf" }, "File(s) to check"), input),
    el("div", { class: "field" }, el("label", { for: "vh" }, "Expected fingerprint(s)"), expected),
    out,
    el("p", { class: "hint" }, "A matching fingerprint shows the file is bit-for-bit the same as when Ubufakazi received it. It does not prove what the file shows is true, and it is not a trusted third-party timestamp.")));
})();
