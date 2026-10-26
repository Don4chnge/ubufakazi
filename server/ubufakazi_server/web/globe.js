/* Dotted 3D globe centred on South Africa (canvas 2D, orthographic projection, no libraries).
   Arcs connect the demo stations whose fictional reports share the same scammer account in the seed data.
   Drag to rotate. Pauses when off-screen; draws a single still frame for reduced-motion users. */
"use strict";

const UBFGlobe = (() => {
  const RAD = Math.PI / 180;
  const CITIES = {
    mthatha: [-31.59, 28.78], joburg: [-26.2, 28.05], durban: [-29.86, 31.02], capetown: [-33.92, 18.42],
    polokwane: [-23.9, 29.45], gqeberha: [-33.96, 25.6], bloem: [-29.12, 26.21], mbombela: [-25.47, 30.97],
    kimberley: [-28.74, 24.77], mahikeng: [-25.86, 25.64], pretoria: [-25.75, 28.19],
  };
  // Seed syndicate (job-fee scam): reports in Gauteng, KwaZulu-Natal, Limpopo, Western Cape and Eastern Cape
  const ARCS = [["mthatha", "joburg"], ["mthatha", "durban"], ["mthatha", "capetown"], ["mthatha", "polokwane"],
                ["joburg", "capetown"], ["durban", "polokwane"], ["gqeberha", "bloem"], ["mbombela", "joburg"]];

  function start(canvas) {
    const ctx = canvas.getContext("2d");
    const land = window.UBF_LAND || [];
    const pts = [];
    for (let i = 0; i < land.length; i += 2) pts.push([land[i] / 10 * RAD, land[i + 1] / 10 * RAD]);
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let W = 0, H = 0, R = 0, cx = 0, cy = 0, dpr = 1;
    let lon0 = 24 * RAD, lat0 = -24 * RAD, t0 = performance.now(), dragging = null, userLon = 0, userLat = 0, visible = true, raf = 0;

    function resize() {
      const r = canvas.getBoundingClientRect();
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      W = r.width; H = r.height;
      canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      R = Math.min(W, H) * 0.43; cx = W / 2; cy = H / 2 + H * 0.01;
    }

    function project(lat, lon, rLon, rLat, lift = 1) {
      // rotate so (rLat, rLon) faces the viewer
      const x0 = Math.cos(lat) * Math.sin(lon - rLon);
      const y0 = Math.sin(lat);
      const z0 = Math.cos(lat) * Math.cos(lon - rLon);
      const y = y0 * Math.cos(rLat) - z0 * Math.sin(rLat);
      const z = y0 * Math.sin(rLat) + z0 * Math.cos(rLat);
      return [cx + x0 * R * lift, cy - y * R * lift, z];
    }

    function frame(now) {
      const t = (now - t0) / 1000;
      const rLon = lon0 + (reduce ? 0 : Math.sin(t * 0.08) * 0.45) + userLon;
      const rLat = lat0 + userLat;
      ctx.clearRect(0, 0, W, H);

      // atmosphere
      let g = ctx.createRadialGradient(cx, cy, R * 0.7, cx, cy, R * 1.45);
      g.addColorStop(0, "rgba(46,230,214,0.16)"); g.addColorStop(0.45, "rgba(56,189,248,0.07)"); g.addColorStop(1, "rgba(3,8,18,0)");
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(cx, cy, R * 1.45, 0, Math.PI * 2); ctx.fill();
      // sphere body
      g = ctx.createRadialGradient(cx - R * 0.35, cy - R * 0.4, R * 0.1, cx, cy, R);
      g.addColorStop(0, "#0E2747"); g.addColorStop(0.7, "#071630"); g.addColorStop(1, "#040C1C");
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2); ctx.fill();

      // graticule
      ctx.lineWidth = 0.6; ctx.strokeStyle = "rgba(120,190,255,0.10)";
      for (let la = -60; la <= 60; la += 30) { ctx.beginPath(); let first = true;
        for (let lo = -180; lo <= 180; lo += 4) { const p = project(la * RAD, lo * RAD, rLon, rLat); if (p[2] < 0) { first = true; continue; } if (first) { ctx.moveTo(p[0], p[1]); first = false; } else ctx.lineTo(p[0], p[1]); }
        ctx.stroke(); }
      for (let lo = -180; lo < 180; lo += 30) { ctx.beginPath(); let first = true;
        for (let la = -90; la <= 90; la += 4) { const p = project(la * RAD, lo * RAD, rLon, rLat); if (p[2] < 0) { first = true; continue; } if (first) { ctx.moveTo(p[0], p[1]); first = false; } else ctx.lineTo(p[0], p[1]); }
        ctx.stroke(); }

      // land dots
      const dot = Math.max(1, R / 210);
      for (const [la, lo] of pts) {
        const p = project(la, lo, rLon, rLat);
        if (p[2] <= 0.02) continue;
        const a = 0.25 + p[2] * 0.75;
        ctx.fillStyle = `rgba(${90 + p[2] * 70 | 0},${200 + p[2] * 40 | 0},${230},${a})`;
        ctx.fillRect(p[0] - dot / 2, p[1] - dot / 2, dot * 1.35, dot * 1.35);
      }

      // rim light
      g = ctx.createLinearGradient(cx - R, cy - R, cx + R, cy + R);
      g.addColorStop(0, "rgba(46,230,214,0.55)"); g.addColorStop(0.5, "rgba(56,189,248,0.12)"); g.addColorStop(1, "rgba(46,230,214,0.35)");
      ctx.strokeStyle = g; ctx.lineWidth = 1.4; ctx.beginPath(); ctx.arc(cx, cy, R, 0, Math.PI * 2); ctx.stroke();

      // arcs + travelling pulses
      for (let i = 0; i < ARCS.length; i++) {
        const [a, b] = ARCS[i], A = CITIES[a], B = CITIES[b];
        const steps = 40, pathPts = [];
        for (let s = 0; s <= steps; s++) {
          const f = s / steps;
          const la = (A[0] + (B[0] - A[0]) * f) * RAD, lo = (A[1] + (B[1] - A[1]) * f) * RAD;
          const lift = 1 + Math.sin(f * Math.PI) * 0.16;
          pathPts.push(project(la, lo, rLon, rLat, lift));
        }
        if (pathPts[steps >> 1][2] < 0) continue;
        ctx.beginPath();
        pathPts.forEach((p, k) => k ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
        ctx.strokeStyle = i < 4 ? "rgba(255,93,108,0.75)" : "rgba(46,230,214,0.55)";
        ctx.lineWidth = i < 4 ? 1.6 : 1.1; ctx.shadowColor = i < 4 ? "rgba(255,93,108,0.9)" : "rgba(46,230,214,0.9)"; ctx.shadowBlur = 8;
        ctx.stroke(); ctx.shadowBlur = 0;
        if (!reduce) {
          const f = ((t * 0.32 + i * 0.37) % 1), p = pathPts[Math.round(f * steps)];
          ctx.fillStyle = "#ffffff"; ctx.beginPath(); ctx.arc(p[0], p[1], 2.1, 0, Math.PI * 2); ctx.fill();
        }
      }
      // city nodes
      for (const [name, [la, lo]] of Object.entries(CITIES)) {
        const p = project(la * RAD, lo * RAD, rLon, rLat, 1.003);
        if (p[2] < 0.05) continue;
        const hub = name === "mthatha";
        const pulse = reduce ? 0 : (Math.sin(t * 2.2 + la) + 1) / 2;
        ctx.fillStyle = hub ? "rgba(255,93,108,0.25)" : "rgba(46,230,214,0.22)";
        ctx.beginPath(); ctx.arc(p[0], p[1], (hub ? 11 : 6.5) + pulse * 5, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = hub ? "#FF5D6C" : "#2EE6D6"; ctx.shadowColor = ctx.fillStyle; ctx.shadowBlur = 12;
        ctx.beginPath(); ctx.arc(p[0], p[1], hub ? 4 : 2.8, 0, Math.PI * 2); ctx.fill(); ctx.shadowBlur = 0;
      }

      // orbit ring (decorative)
      ctx.save(); ctx.translate(cx, cy); ctx.rotate(-0.32);
      ctx.strokeStyle = "rgba(46,230,214,0.22)"; ctx.lineWidth = 1; ctx.setLineDash([2, 6]);
      ctx.beginPath(); ctx.ellipse(0, 0, R * 1.32, R * 0.42, 0, 0, Math.PI * 2); ctx.stroke(); ctx.setLineDash([]);
      if (!reduce) { const ang = t * 0.5; ctx.fillStyle = "#2EE6D6"; ctx.shadowColor = "#2EE6D6"; ctx.shadowBlur = 14;
        ctx.beginPath(); ctx.arc(Math.cos(ang) * R * 1.32, Math.sin(ang) * R * 0.42, 3, 0, Math.PI * 2); ctx.fill(); ctx.shadowBlur = 0; }
      ctx.restore();

      if (!reduce && visible && !document.hidden) raf = requestAnimationFrame(frame);
    }

    function kick() { cancelAnimationFrame(raf); raf = requestAnimationFrame(frame); }
    resize();
    window.addEventListener("resize", () => { resize(); kick(); });
    document.addEventListener("visibilitychange", () => { if (!document.hidden) kick(); });
    if ("IntersectionObserver" in window) new IntersectionObserver((e) => { visible = e[0].isIntersecting; if (visible) kick(); }).observe(canvas);
    canvas.addEventListener("pointerdown", (e) => { dragging = { x: e.clientX, y: e.clientY, lon: userLon, lat: userLat }; canvas.setPointerCapture(e.pointerId); });
    canvas.addEventListener("pointermove", (e) => {
      if (!dragging) return;
      userLon = dragging.lon - (e.clientX - dragging.x) * 0.006;
      userLat = Math.max(-0.9, Math.min(0.9, dragging.lat + (e.clientY - dragging.y) * 0.006));
      if (reduce) kick();
    });
    canvas.addEventListener("pointerup", () => { dragging = null; });
    kick();
  }
  return { start };
})();
