/* Scam fingerprint network: force-directed layout in plain SVG (no libraries).
   Click a node to select it (neighbours stay lit, details go to onSelect). Double-click a report to open it.
   Filters hide signal types. Reports at other stations are drawn as restricted stubs with no details. */
"use strict";

const UBFGraph = (() => {
  const { el } = UBF;
  const KIND = { account: "Bank account", phone: "Phone number", domain: "Website", social: "Social profile",
                 email: "Email", username: "@username", payment_ref: "Payment reference", report: "Report" };
  const GROUP = (t) => t === "account" ? "account" : t === "phone" ? "phone" : t === "report" ? "report" : "web";

  function render(box, data, { onOpen, onSelect } = {}) {
    box.replaceChildren();
    const W = box.clientWidth || 800, H = box.clientHeight || 560;
    const nodes = data.nodes.map((n, i) => ({ ...n, x: W / 2 + Math.cos(i * 2.4) * (60 + i * 7), y: H / 2 + Math.sin(i * 2.4) * (60 + i * 7), vx: 0, vy: 0 }));
    const byId = new Map(nodes.map((n) => [n.id, n]));
    const links = data.edges.map((e) => ({ ...e, s: byId.get(e.source), t: byId.get(e.target) })).filter((l) => l.s && l.t);
    const nbr = new Map(nodes.map((n) => [n.id, new Set()]));
    links.forEach((l) => { nbr.get(l.s.id).add(l.t.id); nbr.get(l.t.id).add(l.s.id); });
    const focus = nodes.find((n) => n.focus);
    if (focus) { focus.x = W / 2; focus.y = H / 2; }
    const hidden = new Set();
    let selected = null;

    const svg = el("svg:svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Network of reports linked by shared identifiers" });
    const view = el("svg:g"), gl = el("svg:g"), gn = el("svg:g");
    view.append(gl, gn); svg.appendChild(view);
    const tip = el("div", { class: "graph-tip", hidden: true });

    for (const l of links) { l.line = el("svg:line", { class: "g-link " + l.kind }); gl.appendChild(l.line); }
    for (const n of nodes) {
      const g = el("svg:g", { class: "g-node", tabindex: "0", role: "button", "aria-label": label(n) });
      if (n.type === "report") {
        n.r = n.focus ? 16 : 10 + Math.min(7, Math.sqrt((n.amount || 0) / 2500));
        g.appendChild(el("svg:circle", { r: n.r, class: n.focus ? "r-focus" : n.visible ? "r-vis" : "r-hidden" }));
        const t = el("svg:text", { y: n.r + 14, "text-anchor": "middle" }); t.textContent = n.visible ? n.label.replace("UBF-26-", "") : "restricted"; g.appendChild(t);
      } else {
        n.r = 7 + Math.min(9, n.count * 1.2);
        g.appendChild(el("svg:rect", { x: -n.r, y: -n.r, width: n.r * 2, height: n.r * 2, rx: n.type === "account" ? 3 : n.r, class: "i-" + n.type, transform: n.type === "account" ? "rotate(45)" : null }));
        const t = el("svg:text", { y: -n.r - 7, "text-anchor": "middle" }); t.textContent = n.label.length > 24 ? n.label.slice(0, 23) + "…" : n.label; g.appendChild(t);
      }
      n.g = g; gn.appendChild(g);
      g.addEventListener("pointerenter", (e) => showTip(n, e));
      g.addEventListener("pointerleave", () => { tip.hidden = true; });
      g.addEventListener("click", (e) => { if (!n.moved) select(n); e.stopPropagation(); });
      g.addEventListener("dblclick", () => open(n));
      g.addEventListener("keydown", (e) => { if (e.key === "Enter") { select(n); } if (e.key === "o") open(n); });
      drag(g, n);
    }
    box.append(svg, tip, legend());
    svg.addEventListener("click", () => select(null));

    function label(n) { return n.type === "report" ? (n.visible ? `Report ${n.label}` : `Restricted report at ${n.station}`) : `${KIND[n.type] || n.type} ${n.label}`; }
    function open(n) { if (n.type === "report" && n.visible && !n.focus && onOpen) onOpen(n.label); }
    function select(n) {
      selected = n;
      const lit = n ? new Set([n.id, ...nbr.get(n.id)]) : null;
      nodes.forEach((m) => { m.g.classList.toggle("dim", !!lit && !lit.has(m.id)); m.g.classList.toggle("sel", n === m); });
      links.forEach((l) => l.line.classList.toggle("dim", !!lit && !(l.s.id === n.id || l.t.id === n.id)));
      if (onSelect) onSelect(n, n ? [...nbr.get(n.id)].map((id) => byId.get(id)) : [], links.filter((l) => n && (l.s === n || l.t === n)));
    }
    function showTip(n, e) {
      tip.replaceChildren();
      if (n.type === "report") {
        if (n.visible) tip.append(el("b", null, n.label), el("div", null, n.station), el("div", null, `${n.scam_type || "-"} · ${UBF.money(n.amount)}`), el("div", { class: "muted" }, `${UBF.date(n.date)} · ${n.status}`));
        else tip.append(el("b", null, "Restricted report"), el("div", null, `Held by ${n.station}`), el("div", { class: "muted small" }, "Details are visible only to that branch."));
      } else tip.append(el("b", null, KIND[n.type] || n.type), el("div", { class: "mono" }, n.label), el("div", { class: "muted" }, `Appears in ${n.count} reports`));
      const r = box.getBoundingClientRect();
      tip.style.left = Math.min(e.clientX - r.left + 14, r.width - 270) + "px";
      tip.style.top = (e.clientY - r.top + 10) + "px";
      tip.hidden = false;
    }
    function applyFilters() {
      const off = (n) => (n.type === "report" ? (!n.visible && hidden.has("restricted")) : hidden.has(GROUP(n.type)));
      nodes.forEach((n) => { n.off = off(n) && !n.focus; n.g.style.display = n.off ? "none" : ""; });
      links.forEach((l) => { const o = l.s.off || l.t.off || (l.kind === "script" && hidden.has("script")); l.line.style.display = o ? "none" : ""; });
    }

    // ---- simulation
    let alpha = 1;
    function step() {
      const k = alpha;
      for (let i = 0; i < nodes.length; i++) {
        const a = nodes[i];
        for (let j = i + 1; j < nodes.length; j++) {
          const b = nodes[j];
          let dx = b.x - a.x, dy = b.y - a.y; const d2 = dx * dx + dy * dy || 0.01;
          const d = Math.sqrt(d2), min = a.r + b.r + 22;
          const f = (5600 / d2 + (d < min ? (min - d) * 0.5 : 0)) * k;
          dx /= d; dy /= d; a.vx -= dx * f; a.vy -= dy * f; b.vx += dx * f; b.vy += dy * f;
        }
      }
      for (const l of links) {
        const dx = l.t.x - l.s.x, dy = l.t.y - l.s.y, d = Math.sqrt(dx * dx + dy * dy) || 1;
        const rest = l.kind === "script" ? 170 : 95, f = (d - rest) * (l.kind === "script" ? 0.008 : 0.03) * k;
        l.s.vx += dx / d * f; l.s.vy += dy / d * f; l.t.vx -= dx / d * f; l.t.vy -= dy / d * f;
      }
      for (const n of nodes) {
        n.vx += (W / 2 - n.x) * 0.002 * k; n.vy += (H / 2 - n.y) * 0.002 * k;
        if (n.fixed || n.focus) { n.vx = 0; n.vy = 0; continue; }
        n.vx *= 0.6; n.vy *= 0.6; n.x += n.vx; n.y += n.vy;
      }
      alpha *= 0.972;
    }
    function tick() { step(); draw(); if (alpha > 0.02) requestAnimationFrame(tick); else fit(); }
    function draw() {
      for (const l of links) { l.line.setAttribute("x1", l.s.x); l.line.setAttribute("y1", l.s.y); l.line.setAttribute("x2", l.t.x); l.line.setAttribute("y2", l.t.y); }
      for (const n of nodes) n.g.setAttribute("transform", `translate(${n.x.toFixed(1)},${n.y.toFixed(1)})`);
    }
    let scale = 1, tx = 0, ty = 0;
    const apply = () => view.setAttribute("transform", `translate(${tx},${ty}) scale(${scale})`);
    function fit() {
      let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
      for (const n of nodes) { x0 = Math.min(x0, n.x - n.r - 50); x1 = Math.max(x1, n.x + n.r + 50); y0 = Math.min(y0, n.y - n.r - 28); y1 = Math.max(y1, n.y + n.r + 28); }
      const sc = Math.min(1.7, W / (x1 - x0), (H - 50) / (y1 - y0));
      scale = sc; tx = W / 2 - (x0 + x1) / 2 * sc; ty = (H - 50) / 2 - (y0 + y1) / 2 * sc; apply();
    }
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) { while (alpha > 0.02) step(); draw(); requestAnimationFrame(fit); } else requestAnimationFrame(tick);

    svg.addEventListener("wheel", (e) => {
      e.preventDefault();
      const r = svg.getBoundingClientRect(), mx = (e.clientX - r.left) * W / r.width, my = (e.clientY - r.top) * H / r.height;
      const ns = Math.min(3, Math.max(0.35, scale * (e.deltaY < 0 ? 1.12 : 0.89)));
      tx = mx - (mx - tx) * ns / scale; ty = my - (my - ty) * ns / scale; scale = ns; apply();
    }, { passive: false });
    let pan = null;
    svg.addEventListener("pointerdown", (e) => { if (e.target === svg) { pan = { x: e.clientX, y: e.clientY, tx, ty }; svg.setPointerCapture(e.pointerId); } });
    svg.addEventListener("pointermove", (e) => { if (pan) { const r = svg.getBoundingClientRect(); tx = pan.tx + (e.clientX - pan.x) * W / r.width; ty = pan.ty + (e.clientY - pan.y) * H / r.height; apply(); } });
    svg.addEventListener("pointerup", () => { pan = null; });

    function drag(g, n) {
      let start = null;
      g.addEventListener("pointerdown", (e) => { e.stopPropagation(); g.setPointerCapture(e.pointerId); start = { x: e.clientX, y: e.clientY, nx: n.x, ny: n.y }; n.moved = false; });
      g.addEventListener("pointermove", (e) => {
        if (!start) return;
        const r = svg.getBoundingClientRect(), dx = e.clientX - start.x, dy = e.clientY - start.y;
        if (Math.abs(dx) + Math.abs(dy) > 4) { n.moved = true; n.fixed = true; }
        n.x = start.nx + dx * W / r.width / scale; n.y = start.ny + dy * H / r.height / scale; draw();
      });
      g.addEventListener("pointerup", () => { start = null; setTimeout(() => { n.moved = false; }, 0); });
    }
    function legend() {
      const dot = (c) => { const i = el("i"); i.style.background = c; return i; };
      return el("div", { class: "graph-legend" },
        el("span", null, dot("#2EE6D6"), "your branch's report"), el("span", null, dot("#3A4756"), "restricted report"),
        el("span", null, dot("#FF5D6C"), "bank account"), el("span", null, dot("#FBBF24"), "phone"),
        el("span", null, dot("#A78BFA"), "website / other"), el("span", null, "- - - similar message template"));
    }

    return {
      setFilter(group, on) { if (on) hidden.delete(group); else hidden.add(group); applyFilters(); },
      select(id) { select(id ? byId.get(id) : null); },
      fit,
    };
  }

  /** Filter chip row for a graph controller. */
  function filterBar(ctrl) {
    const chip = (group, text, color) => {
      const b = el("button", { type: "button", "aria-pressed": "true" }, el("i"), text);
      b.firstChild.style.background = color;
      b.addEventListener("click", () => { const on = b.getAttribute("aria-pressed") !== "true"; b.setAttribute("aria-pressed", on ? "true" : "false"); ctrl.setFilter(group, on); });
      return b;
    };
    return el("div", { class: "graph-filters", role: "group", "aria-label": "Show or hide signal types" },
      chip("account", "Bank accounts", "#FF5D6C"), chip("phone", "Phone numbers", "#FBBF24"), chip("web", "Websites & other", "#A78BFA"),
      chip("script", "Message templates", "#A78BFA"), chip("restricted", "Restricted reports", "#3A4756"));
  }

  return { render, filterBar, KIND };
})();
