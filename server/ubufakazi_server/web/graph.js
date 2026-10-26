/* Investigation graph: a small force-directed layout in plain SVG (no external libraries). */
"use strict";

const UBFGraph = (() => {
  const { el } = UBF;
  const KIND = { account: "Bank account", phone: "Phone number", domain: "Website", social: "Social profile",
                 email: "Email", username: "@username", payment_ref: "Payment reference" };

  function render(box, data, { onOpen } = {}) {
    box.replaceChildren();
    const W = box.clientWidth || 800, H = box.clientHeight || 520;
    const nodes = data.nodes.map((n, i) => ({ ...n, x: W / 2 + Math.cos(i * 2.4) * (60 + i * 6), y: H / 2 + Math.sin(i * 2.4) * (60 + i * 6), vx: 0, vy: 0 }));
    const byId = new Map(nodes.map((n) => [n.id, n]));
    const links = data.edges.map((e) => ({ ...e, s: byId.get(e.source), t: byId.get(e.target) })).filter((l) => l.s && l.t);
    const focus = nodes.find((n) => n.focus);
    if (focus) { focus.x = W / 2; focus.y = H / 2; }

    const svg = el("svg:svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Graph of reports linked by shared identifiers" });
    const view = el("svg:g");
    const gl = el("svg:g"), gn = el("svg:g");
    view.append(gl, gn); svg.appendChild(view);
    const tip = el("div", { class: "graph-tip", hidden: true });

    for (const l of links) {
      l.line = el("svg:line", { class: "g-link " + l.kind });
      gl.appendChild(l.line);
    }
    for (const n of nodes) {
      const g = el("svg:g", { class: "g-node", tabindex: n.type === "report" && n.visible ? "0" : null });
      if (n.type === "report") {
        n.r = n.focus ? 15 : 10 + Math.min(6, Math.sqrt((n.amount || 0) / 2500));
        g.appendChild(el("svg:circle", { r: n.r, class: n.focus ? "r-focus" : n.visible ? "r-vis" : "r-hidden" }));
        const lbl = el("svg:text", { y: n.r + 13, "text-anchor": "middle" });
        lbl.textContent = n.visible ? n.label.replace("UBF-26-", "") : "restricted";
        g.appendChild(lbl);
      } else {
        n.r = 6 + Math.min(8, n.count * 1.2);
        g.appendChild(el("svg:rect", { x: -n.r, y: -n.r, width: n.r * 2, height: n.r * 2, rx: n.type === "account" ? 2 : n.r,
                                        class: "i-" + n.type, transform: n.type === "account" ? "rotate(45)" : null }));
        const lbl = el("svg:text", { y: -n.r - 6, "text-anchor": "middle" });
        lbl.textContent = n.label.length > 26 ? n.label.slice(0, 25) + "…" : n.label;
        g.appendChild(lbl);
      }
      n.g = g; gn.appendChild(g);
      g.addEventListener("pointerenter", (e) => showTip(n, e));
      g.addEventListener("pointerleave", () => { tip.hidden = true; });
      g.addEventListener("dblclick", () => open(n));
      g.addEventListener("keydown", (e) => { if (e.key === "Enter") open(n); });
      drag(g, n);
    }
    box.append(svg, tip, legend());

    function open(n) { if (n.type === "report" && n.visible && !n.focus && onOpen) onOpen(n.label); }

    function showTip(n, e) {
      tip.replaceChildren();
      if (n.type === "report") {
        if (n.visible) tip.append(el("b", null, n.label), el("div", null, `${n.station}`), el("div", null, `${n.scam_type || "-"} · ${UBF.money(n.amount)}`),
                                  el("div", { class: "muted" }, `${UBF.date(n.date)} · ${n.status}`), n.focus ? null : el("div", { class: "muted small" }, "Double-click to open"));
        else tip.append(el("b", null, "Restricted report"), el("div", null, `Held by ${n.station}`),
                        el("div", { class: "muted small" }, "Details are visible only to that station. Request access through your commander."));
      } else {
        tip.append(el("b", null, KIND[n.type] || n.type), el("div", { class: "mono" }, n.label), el("div", { class: "muted" }, `Appears in ${n.count} reports`));
      }
      const r = box.getBoundingClientRect();
      tip.style.left = Math.min(e.clientX - r.left + 14, r.width - 270) + "px";
      tip.style.top = (e.clientY - r.top + 10) + "px";
      tip.hidden = false;
    }

    // ---- simulation
    let alpha = 1;
    function step() {
      const k = alpha;
      for (let i = 0; i < nodes.length; i++) {
        const a = nodes[i];
        for (let j = i + 1; j < nodes.length; j++) {
          const b = nodes[j];
          let dx = b.x - a.x, dy = b.y - a.y, d2 = dx * dx + dy * dy || 0.01;
          const d = Math.sqrt(d2), min = a.r + b.r + 18;
          const f = (5200 / d2 + (d < min ? (min - d) * 0.5 : 0)) * k;
          dx /= d; dy /= d;
          a.vx -= dx * f; a.vy -= dy * f; b.vx += dx * f; b.vy += dy * f;
        }
      }
      for (const l of links) {
        const dx = l.t.x - l.s.x, dy = l.t.y - l.s.y, d = Math.sqrt(dx * dx + dy * dy) || 1;
        const rest = l.kind === "script" ? 170 : 95;
        const f = (d - rest) * (l.kind === "script" ? 0.008 : 0.03) * k;
        l.s.vx += dx / d * f; l.s.vy += dy / d * f; l.t.vx -= dx / d * f; l.t.vy -= dy / d * f;
      }
      for (const n of nodes) {
        n.vx += (W / 2 - n.x) * 0.002 * k; n.vy += (H / 2 - n.y) * 0.002 * k;
        if (n.fixed || n.focus) { n.vx = 0; n.vy = 0; continue; }
        n.vx *= 0.6; n.vy *= 0.6;
        n.x += n.vx; n.y += n.vy;
      }
      alpha *= 0.972;
    }
    function tick() { step(); draw(); if (alpha > 0.02) requestAnimationFrame(tick); else fit(); }
    function fit() {
      let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
      for (const n of nodes) { x0 = Math.min(x0, n.x - n.r - 40); x1 = Math.max(x1, n.x + n.r + 40); y0 = Math.min(y0, n.y - n.r - 24); y1 = Math.max(y1, n.y + n.r + 24); }
      const sc = Math.min(1.7, W / (x1 - x0), (H - 40) / (y1 - y0));
      scale = sc; tx = W / 2 - (x0 + x1) / 2 * sc; ty = (H - 40) / 2 - (y0 + y1) / 2 * sc;
      view.style.transition = "transform .5s ease"; apply();
    }
    function draw() {
      for (const l of links) {
        l.line.setAttribute("x1", l.s.x); l.line.setAttribute("y1", l.s.y);
        l.line.setAttribute("x2", l.t.x); l.line.setAttribute("y2", l.t.y);
      }
      for (const n of nodes) n.g.setAttribute("transform", `translate(${n.x.toFixed(1)},${n.y.toFixed(1)})`);
    }
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) { while (alpha > 0.02) step(); draw(); requestAnimationFrame(fit); } else requestAnimationFrame(tick);

    // ---- pan / zoom
    let scale = 1, tx = 0, ty = 0;
    const apply = () => view.setAttribute("transform", `translate(${tx},${ty}) scale(${scale})`);
    svg.addEventListener("wheel", (e) => {
      e.preventDefault();
      const r = svg.getBoundingClientRect(), mx = (e.clientX - r.left) * W / r.width, my = (e.clientY - r.top) * H / r.height;
      const ns = Math.min(3, Math.max(0.4, scale * (e.deltaY < 0 ? 1.12 : 0.89)));
      tx = mx - (mx - tx) * ns / scale; ty = my - (my - ty) * ns / scale; scale = ns; apply();
    }, { passive: false });
    let pan = null;
    svg.addEventListener("pointerdown", (e) => { if (e.target === svg) { pan = { x: e.clientX, y: e.clientY, tx, ty }; svg.setPointerCapture(e.pointerId); } });
    svg.addEventListener("pointermove", (e) => { if (pan) { const r = svg.getBoundingClientRect(); tx = pan.tx + (e.clientX - pan.x) * W / r.width; ty = pan.ty + (e.clientY - pan.y) * H / r.height; apply(); } });
    svg.addEventListener("pointerup", () => { pan = null; });

    function drag(g, n) {
      let start = null;
      g.addEventListener("pointerdown", (e) => {
        e.stopPropagation(); g.setPointerCapture(e.pointerId);
        start = { x: e.clientX, y: e.clientY, nx: n.x, ny: n.y }; n.fixed = true;
      });
      g.addEventListener("pointermove", (e) => {
        if (!start) return;
        const r = svg.getBoundingClientRect();
        n.x = start.nx + (e.clientX - start.x) * W / r.width / scale; n.y = start.ny + (e.clientY - start.y) * H / r.height / scale;
        draw();
      });
      g.addEventListener("pointerup", () => { start = null; if (alpha < 0.05) { alpha = 0.3; requestAnimationFrame(tick); } });
    }

    function legend() {
      const box = el("div", { class: "graph-legend" });
      const dot = (c) => { const i = el("i"); i.style.background = c; return i; };
      box.append(el("span", null, dot("#5CF2D6"), "your station's report"), el("span", null, dot("#3A4756"), "restricted report"),
                 el("span", null, dot("#FF8F72"), "bank account"), el("span", null, dot("#F5C66B"), "phone"),
                 el("span", null, dot("#B49CFF"), "website / other"), el("span", null, "- - - same message template"));
      return box;
    }
  }
  return { render };
})();
