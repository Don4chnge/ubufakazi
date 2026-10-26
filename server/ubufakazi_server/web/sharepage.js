/* /share: build a scam warning from your own report (reference + key) or from scratch. */
"use strict";

(() => {
  const { el, api } = UBF;
  const app = document.getElementById("app");
  const P = UBFShare.PRESETS;
  const PROVINCES = ["Eastern Cape", "Free State", "Gauteng", "KwaZulu-Natal", "Limpopo", "Mpumalanga", "North West", "Northern Cape", "Western Cape"];

  function presetFor(w) {
    if (w.category === "banking_fraud") return "banking";
    return P[w.scam_type] ? w.scam_type : "other";
  }

  function fromReport(out) {
    const ref = el("input", { type: "text", id: "ref", placeholder: "UBF-26-XXXXXX", maxlength: "24", autocomplete: "off", spellcheck: "false" });
    const key = el("input", { type: "password", id: "key", placeholder: "XXXX-XXXX-XXXX", maxlength: "24", autocomplete: "off" });
    const msg = el("p", { class: "err-msg", role: "alert" });
    const f = el("form", { class: "panel stack" },
      el("p", { class: "muted" }, "Use the reference and receipt key from when you reported. We only use them to read the scam type and the tricks used."),
      el("div", { class: "grid2" }, el("div", { class: "field" }, el("label", { for: "ref" }, "Reference"), ref), el("div", { class: "field" }, el("label", { for: "key" }, "Receipt key"), key)),
      msg, el("div", null, el("button", { class: "btn btn-primary", type: "submit" }, "Create my warning")));
    f.addEventListener("submit", async (e) => {
      e.preventDefault(); msg.textContent = "";
      try {
        const w = await api("POST", "/api/public/warning", { reference: ref.value.trim().toUpperCase(), key: key.value.trim().toUpperCase() });
        const p = P[presetFor(w)];
        UBFShare.tool(out, { title: w.scam_type_label || p.label, where: w.province, flags: w.red_flags.length ? w.red_flags : p.flags, rule: p.rule, optional: w.optional });
        out.scrollIntoView({ behavior: "smooth", block: "start" });
      } catch (ex) { msg.textContent = ex.message; }
    });
    return f;
  }

  function quick(out) {
    const type = el("select", { id: "qtype" }, Object.entries(P).map(([k, v]) => el("option", { value: k }, v.label)));
    const prov = el("select", { id: "qprov" }, el("option", { value: "" }, "Don't say"), PROVINCES.map((p) => el("option", { value: p }, p)));
    const flagsBox = el("div", { class: "stack" });
    const paint = () => {
      const p = P[type.value];
      flagsBox.replaceChildren(...p.flags.map((f) => el("label", { class: "check" }, el("input", { type: "checkbox", checked: true, value: f, onchange: build }), f)));
      build();
    };
    function build() {
      const p = P[type.value];
      const flags = [...flagsBox.querySelectorAll("input:checked")].map((i) => i.value);
      UBFShare.tool(out, { title: p.label, where: prov.value, flags: flags.length ? flags : [p.rule], rule: p.rule, optional: {} });
    }
    type.addEventListener("change", paint);
    prov.addEventListener("change", build);
    setTimeout(paint, 0);
    return el("div", { class: "panel stack" },
      el("p", { class: "muted" }, "No report needed. Pick the kind of scam and the warning signs you saw."),
      el("div", { class: "grid2" }, el("div", { class: "field" }, el("label", { for: "qtype" }, "Type of scam"), type), el("div", { class: "field" }, el("label", { for: "qprov" }, "Province (optional)"), prov)),
      el("div", { class: "field" }, el("span", { class: "label" }, "Warning signs to include"), flagsBox));
  }

  const out = el("div", { id: "shareOut" });
  const tabsHost = el("div");
  const tabs = el("div", { class: "subtabs", role: "tablist" });
  const show = (which) => {
    [...tabs.children].forEach((b) => b.setAttribute("aria-selected", b.dataset.t === which ? "true" : "false"));
    out.replaceChildren();
    tabsHost.replaceChildren(which === "report" ? fromReport(out) : quick(out));
  };
  tabs.append(el("button", { role: "tab", dataset: { t: "quick" }, onclick: () => show("quick") }, "Quick warning"),
              el("button", { role: "tab", dataset: { t: "report" }, onclick: () => show("report") }, "From my report"));
  app.replaceChildren(tabs, tabsHost, el("div", { class: "spacer-16" }), out);
  show("quick");
})();
