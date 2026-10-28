/* Security page: live self-checks from this server (aggregates only) plus a check of the headers this page was served with. */
"use strict";
(async () => {
  const { el } = UBF;
  const box = document.getElementById("live");
  if (!box) return;
  const card = (ok, title, value, note) => el("div", { class: "sec-card " + (ok === true ? "ok" : ok === false ? "bad" : "info") },
    el("span", { class: "sec-dot", "aria-hidden": "true" }), el("b", null, title), el("strong", null, value), el("small", null, note));
  let d, h;
  try {
    const r = await fetch("/api/public/security", { credentials: "same-origin" });
    d = await r.json();
    h = (await fetch("/security", { credentials: "same-origin" })).headers;
  } catch (_) { box.replaceChildren(el("p", { class: "muted" }, "Live checks are unavailable right now.")); return; }
  const scan = d.dependency_scan || {}, tests = d.tests || {};
  const hdr = ["content-security-policy", "x-frame-options", "x-content-type-options", "referrer-policy", "permissions-policy"]
    .filter((k) => h.get(k)).length + (h.get("strict-transport-security") ? 1 : 0);
  box.replaceChildren(
    card(d.audit_chain.intact, "Audit log chain", d.audit_chain.intact ? "Intact" : "BROKEN", `${d.audit_chain.events.toLocaleString("en-ZA")} events re-verified just now (SHA-256 hash chain)`),
    card(scan.known_vulnerabilities === 0, "Dependency scan", scan.known_vulnerabilities === 0 ? "0 known vulnerabilities" : (scan.known_vulnerabilities ?? "?") + " found",
      `pip-audit over ${scan.packages || "?"} pinned packages · ${scan.scanned_at ? new Date(scan.scanned_at).toLocaleDateString("en-ZA") : ""} · `, ),
    card(tests.failed === 0, "Automated security & function tests", `${tests.passed ?? "?"} passing`, `${tests.failed ?? "?"} failing · run ${tests.run_at ? new Date(tests.run_at).toLocaleString("en-ZA") : ""}`),
    card(hdr >= 5, "Security headers on this page", `${hdr} of 6 present`, "CSP, frame, sniffing, referrer, permissions" + (d.https_only ? ", HSTS" : "")),
    card(d.timestamps.configured, "Independent timestamps (RFC 3161)", d.timestamps.configured ? "Active" : "Off", d.timestamps.note),
    card(true, "AI usage cap (LLM10)", `${d.ai.last_hour}/${d.ai.max_per_hour} this hour`, `${d.ai.max_per_day} per day max · ${d.ai.metadata_stripped} photos stripped of metadata since restart`),
    card(null, "Sealed documents issued", String(d.seals_issued), "Each case pack can be checked on Verify"),
    card(null, "Beneficiary checks answered", String(d.beneficiary_checks), `${d.subscribed_banks} subscribed bank(s) · signed, single-use, rate-limited`));
  const sb = box.querySelectorAll(".sec-card")[1].querySelector("small");
  sb.append(el("a", { href: "/app/sbom.json", download: "ubufakazi-sbom.cdx.json" }, "Download SBOM"));
})();
