/* Syndicate jurisdiction board: a schematic map of South Africa's nine provinces (NOT to scale, NOT SAPS boundaries).
   Each province tile shows its demo stations as dots; for a selected syndicate, tiles heat up by victims, involved
   stations light up, the suggested lead station gets a ring, and flows run from each province to the mule accounts. */
"use strict";

const UBFBoard = (() => {
  const { el } = UBF;
  // schematic tile layout, roughly where each province sits
  const TILES = {
    "Limpopo": { x: 360, y: 8, w: 236, h: 110, ab: "LP" },
    "North West": { x: 158, y: 126, w: 194, h: 108, ab: "NW" },
    "Gauteng": { x: 360, y: 126, w: 122, h: 100, ab: "GP" },
    "Mpumalanga": { x: 490, y: 126, w: 150, h: 124, ab: "MP" },
    "Northern Cape": { x: 8, y: 242, w: 252, h: 128, ab: "NC" },
    "Free State": { x: 268, y: 242, w: 206, h: 114, ab: "FS" },
    "KwaZulu-Natal": { x: 482, y: 258, w: 158, h: 138, ab: "KZN" },
    "Western Cape": { x: 8, y: 378, w: 252, h: 130, ab: "WC" },
    "Eastern Cape": { x: 268, y: 364, w: 206, h: 144, ab: "EC" },
  };
  const W = 1000, H = 520, AX = 690;

  function heat(n, max) {
    if (!n) return 0;
    return Math.min(4, 1 + Math.floor((n / Math.max(1, max)) * 3.999));
  }

  function map(data, syn) {
    const svg = el("svg:svg", { viewBox: `0 0 ${W} ${H}`, class: "jmap", role: "img",
      "aria-label": syn ? `Schematic map of the provinces and stations involved in ${syn.code}` : "Schematic map of reports by province" });
    const gFlow = el("svg:g"), gTile = el("svg:g"), gAcc = el("svg:g");
    svg.append(gFlow, gTile, gAcc);
    const perProv = {};
    if (syn) syn.provinces.forEach((p) => { perProv[p.province] = p.victims; });
    else data.provinces.forEach((p) => { perProv[p.province] = p.reports; });
    const max = Math.max(1, ...Object.values(perProv));
    const involved = new Set(syn ? syn.jurisdictions.map((j) => j.code) : []);
    const jByCode = Object.fromEntries((syn ? syn.jurisdictions : []).map((j) => [j.code, j]));
    const centre = {};

    data.provinces.forEach((p) => {
      const t = TILES[p.province];
      if (!t) return;
      const n = perProv[p.province] || 0;
      const g = el("svg:g", { class: "jtile h" + heat(n, max) + (syn && !n ? " dim" : "") });
      g.append(el("svg:rect", { x: t.x, y: t.y, width: t.w, height: t.h, rx: 12 }));
      g.append(el("svg:text", { x: t.x + 12, y: t.y + 24, class: "jab" }, t.ab));
      g.append(el("svg:text", { x: t.x + 12, y: t.y + 40, class: "jname" }, p.province));
      g.append(el("svg:text", { x: t.x + t.w - 12, y: t.y + 30, class: "jnum", "text-anchor": "end" }, n ? String(n) : "–"));
      if (t.w >= 140) g.append(el("svg:text", { x: t.x + t.w - 12, y: t.y + 44, class: "jname", "text-anchor": "end" }, syn ? (n === 1 ? "victim" : "victims") : (n === 1 ? "report" : "reports")));
      // station dots: one per demo station (jurisdiction)
      const k = p.stations.length, gap = Math.min(40, (t.w - 24) / Math.max(1, k));
      p.stations.forEach((s, i) => {
        const cx = t.x + 18 + gap * i + gap / 2 - 6, cy = t.y + t.h - 26;
        const on = involved.has(s.code), lead = syn && syn.lead.code === s.code;
        const dot = el("svg:g", { class: "jst" + (on ? " on" : "") + (lead ? " lead" : "") + (s.own ? " own" : "") });
        dot.append(el("svg:title", null, `${s.name}: ${s.towns.join(", ")}` + (on ? ` · ${jByCode[s.code].victims} victim(s) in this syndicate` : "")));
        if (lead) dot.append(el("svg:circle", { cx, cy, r: 12, class: "ring" }));
        dot.append(el("svg:circle", { cx, cy, r: on ? 7 : 5 }));
        dot.append(el("svg:text", { x: cx, y: cy + 20, "text-anchor": "middle", class: "jcode" }, s.code));
        g.append(dot);
      });
      gTile.append(g);
      centre[p.province] = { x: t.x + t.w / 2, y: t.y + t.h / 2 - 8 };
    });

    if (syn && syn.mules.length) {
      const mules = syn.mules.slice(0, 5), step = Math.min(96, (H - 40) / mules.length);
      const y0 = H / 2 - (step * (mules.length - 1)) / 2;
      gAcc.append(el("svg:text", { x: AX, y: y0 - 44, class: "jhead" }, "MULE ACCOUNTS"));
      mules.forEach((m, i) => {
        const y = y0 + i * step;
        m.provinces.forEach((pr) => {
          const c = centre[pr];
          if (!c) return;
          const d = `M${c.x},${c.y} C${(c.x + AX) / 2 + 40},${c.y} ${AX - 80},${y} ${AX},${y}`;
          gFlow.append(el("svg:path", { d, class: "jflow" + (m.bank_status === "frozen" ? " frozen" : "") }));
        });
        const st = m.bank_status === "frozen" ? "frozen" : m.bank_connected ? "sent" : "manual";
        const chip = el("svg:g", { class: "jacc " + st });
        chip.append(el("svg:rect", { x: AX, y: y - 30, width: 300, height: 60, rx: 10 }));
        chip.append(el("svg:text", { x: AX + 14, y: y - 8, class: "jaccno" }, m.account));
        chip.append(el("svg:text", { x: AX + 14, y: y + 12, class: "jname" }, `${m.bank || "Bank not stated"} · ${m.reports} report${m.reports === 1 ? "" : "s"}`));
        chip.append(el("svg:text", { x: AX + 288, y: y - 8, class: "jtag", "text-anchor": "end" },
          st === "frozen" ? "FROZEN" : st === "sent" ? (m.bank_status ? m.bank_status.toUpperCase() : "ALERT SENT") : "SEND MANUALLY"));
        gAcc.append(chip);
      });
    }
    svg.append(el("svg:text", { x: 14, y: H - 4, class: "jfoot" }, "Schematic, not to scale. Fictional demo stations; not SAPS precinct boundaries."));
    return svg;
  }

  return { map };
})();
