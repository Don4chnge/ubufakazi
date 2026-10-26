/* Home page: globe, live aggregate stats (synthetic demo data), example warning card. */
"use strict";
(async () => {
  const c = document.getElementById("globe");
  if (c && typeof UBFGlobe !== "undefined") UBFGlobe.start(c);
  const card = document.getElementById("sampleCard");
  if (card) {
    const p = UBFShare.PRESETS.job;
    UBFShare.render(card, { title: p.label, where: "Eastern Cape", flags: p.flags.slice(0, 4), rule: p.rule, example: true });
  }
  try {
    const s = await UBF.api("GET", "/api/public/stats");
    const set = (id, v) => { const e = document.getElementById(id); if (e) e.textContent = Number(v).toLocaleString("en-ZA"); };
    set("statLinked", s.linked_reports); set("sReports", s.reports); set("sEvidence", s.evidence_files);
    set("sNetworks", s.networks); set("sStations", s.stations);
  } catch (_) { /* stats are optional decoration; keep the dashes */ }
})();
