/* Ubufakazi landing screen: a fingerprint drawn in code, scanned top to bottom.
 * The scan pauses while the landing screen is off-screen, and shows a still,
 * finished scan for people who prefer reduced motion. */
(function () {
  'use strict';
  var cv = document.querySelector('canvas.h-bg');
  if (!cv || !cv.getContext) return;
  var ctx = cv.getContext('2d');
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var W = 0, H = 0, dpr = 1, geo = null, base = null, bright = null, raf = 0, t0 = performance.now(), visible = true;
  var PERIOD = 8200, SCAN = 6200;

  function rng(seed) { return function () { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; }; }

  function build() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    W = cv.clientWidth; H = cv.clientHeight;
    if (!W || !H) return false;
    cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
    var phone = W < 610;
    var ph = Math.min(H * (phone ? 0.7 : 0.84), W * (phone ? 1.25 : 0.6), 1100);
    var pw = ph * 0.74;
    var cx = W * 0.5, cy = H * (phone ? 0.6 : 0.585);
    var R = rng(20261020);
    var spacing = Math.max(4.6, ph / 118);
    var N = Math.floor((ph * 0.62) / spacing);
    var p1 = R() * 6.28, p2 = R() * 6.28, p3 = R() * 6.28, p4 = R() * 6.28;

    function ring(i, th) {
      var f = i / N, r = i * spacing;
      var d = 0.055 * Math.sin(3 * th + p1 + i * 0.045) + 0.035 * Math.sin(5 * th + p2 - i * 0.03) +
              0.02 * Math.sin(9 * th + p3 + i * 0.09) + 0.012 * Math.sin(15 * th + p4);
      var x = cx + r * 0.82 * Math.cos(th) * (1 + d) + i * 0.32 * spacing * 0.18;
      var sy = Math.sin(th);
      var squash = sy < 0 ? 1 - 0.32 * Math.max(0, f - 0.45) : 1 + 0.18 * f;
      var y = cy - ph * 0.06 + r * 1.08 * sy * (1 + d) * squash;
      return [x, y];
    }
    function draw(o, pts) {
      if (pts.length < 2) return;
      o.beginPath(); o.moveTo(pts[0][0], pts[0][1]);
      for (var j = 1; j < pts.length; j++) o.lineTo(pts[j][0], pts[j][1]);
      o.stroke();
    }
    function makeLayer(color, width) {
      var c = document.createElement('canvas');
      c.width = cv.width; c.height = cv.height;
      var o = c.getContext('2d');
      o.scale(dpr, dpr);
      o.strokeStyle = color; o.lineWidth = width; o.lineCap = 'round'; o.lineJoin = 'round';
      var G = rng(77);
      for (var i = 1; i <= N; i++) {
        var steps = 260, seg = [];
        for (var k = 0; k <= steps; k++) {
          var th = (k / steps) * Math.PI * 2;
          if (G() < 0.012 && seg.length > 4) { draw(o, seg); seg = []; k += 3 + Math.floor(G() * 5); continue; }
          seg.push(ring(i, th));
        }
        draw(o, seg);
      }
      // fade out to the shape of a fingertip
      o.globalCompositeOperation = 'destination-in';
      var fy = cy - ph * 0.04;
      var g = o.createRadialGradient(cx, fy, ph * 0.08, cx, fy, ph * 0.52);
      g.addColorStop(0, 'rgba(0,0,0,1)'); g.addColorStop(0.62, 'rgba(0,0,0,0.85)'); g.addColorStop(1, 'rgba(0,0,0,0)');
      o.save(); o.translate(cx, fy); o.scale(pw / ph, 1); o.translate(-cx, -fy);
      o.fillStyle = g; o.beginPath(); o.arc(cx, fy, ph * 0.52, 0, Math.PI * 2); o.fill(); o.restore();
      o.globalCompositeOperation = 'source-over';
      return c;
    }

    base = makeLayer('rgba(222, 232, 240, 1)', spacing * 0.36);
    bright = makeLayer('rgba(92, 242, 214, 1)', spacing * 0.42);

    var M = rng(4242), minutiae = [];
    while (minutiae.length < 14) {
      var i = Math.floor(N * (0.18 + M() * 0.6)), th = M() * Math.PI * 2;
      var pt = ring(i, th);
      var dx = (pt[0] - cx) / (pw * 0.46), dy = (pt[1] - (cy - ph * 0.04)) / (ph * 0.46);
      if (dx * dx + dy * dy > 0.7) continue;
      minutiae.push({ x: pt[0], y: pt[1], outer: Math.abs(pt[0] - cx) > pw * 0.3 && pt[1] > cy - ph * 0.12,
        id: 'M-' + String(minutiae.length + 1).padStart(2, '0'), type: M() < 0.5 ? 'END' : 'SPLIT' });
    }
    minutiae.sort(function (a, b) { return a.y - b.y; });
    geo = { cx: cx, cy: cy, ph: ph, pw: pw, top: cy - ph / 2, bottom: cy + ph / 2, minutiae: minutiae, phone: phone };
    return true;
  }

  function mono(size, weight) { return (weight || 400) + ' ' + size + 'px "IBM Plex Mono", ui-monospace, Consolas, monospace'; }

  function frame(now) {
    raf = 0;
    var g = geo;
    if (!g) return;
    var t = reduce ? PERIOD - 1 : (now - t0) % PERIOD;
    var p = Math.min(1, t / SCAN);
    var ease = p < 0.5 ? 2 * p * p : 1 - Math.pow(-2 * p + 2, 2) / 2;
    var scanY = g.top + (g.bottom - g.top) * ease;
    var hold = t > SCAN;
    var fade = t > PERIOD - 500 ? (PERIOD - t) / 500 : 1;

    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, cv.width, cv.height);
    ctx.globalAlpha = 0.13; ctx.drawImage(base, 0, 0);
    ctx.save(); ctx.beginPath(); ctx.rect(0, 0, cv.width, scanY * dpr); ctx.clip();
    ctx.globalAlpha = 0.16 * fade; ctx.drawImage(bright, 0, 0);
    ctx.restore();
    if (!hold && !reduce) {
      var band = Math.max(26, g.ph * 0.05);
      ctx.save(); ctx.beginPath(); ctx.rect(0, (scanY - band) * dpr, cv.width, band * dpr); ctx.clip();
      ctx.globalAlpha = 0.85; ctx.drawImage(bright, 0, 0);
      ctx.restore();
    }
    ctx.globalAlpha = 1;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    if (!hold && !reduce) {
      var half = g.pw * 0.62;
      var lg = ctx.createLinearGradient(g.cx - half, 0, g.cx + half, 0);
      lg.addColorStop(0, 'rgba(92,242,214,0)'); lg.addColorStop(0.5, 'rgba(92,242,214,0.9)'); lg.addColorStop(1, 'rgba(92,242,214,0)');
      ctx.fillStyle = lg; ctx.fillRect(g.cx - half, scanY - 0.75, half * 2, 1.5);
      ctx.fillStyle = 'rgba(92,242,214,0.06)'; ctx.fillRect(g.cx - half, scanY - 18, half * 2, 18);
    }

    var found = 0;
    ctx.lineWidth = 1.2;
    for (var i = 0; i < g.minutiae.length; i++) {
      var m = g.minutiae[i];
      if (m.y > scanY) continue;
      found++;
      if (g.phone) continue;
      var age = Math.min(1, (scanY - m.y) / 60);
      ctx.globalAlpha = (0.25 + 0.4 * age) * fade;
      ctx.strokeStyle = '#5CF2D6';
      ctx.beginPath(); ctx.arc(m.x, m.y, 5.5, 0, Math.PI * 2); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(m.x + 6, m.y - 6); ctx.lineTo(m.x + 16, m.y - 16); ctx.stroke();
      if (m.outer) {
        ctx.fillStyle = 'rgba(220,240,236,0.9)'; ctx.font = mono(9.5, 500);
        ctx.fillText(m.id + ' ' + m.type, m.x + 19, m.y - 18);
      }
    }
    ctx.globalAlpha = 1;

    if (!g.phone && W >= 900) {
      var rx = g.cx + g.pw * 0.5 + 26, lx = g.cx - g.pw * 0.5 - 26, ry = g.cy - g.ph * 0.3;
      var right = [
        ['SCAN', hold ? 'COMPLETE' : (Math.round(p * 100) + '%')],
        ['MINUTIAE', String(found).padStart(2, '0') + ' / ' + g.minutiae.length],
        ['STATUS', hold ? 'MATCH FOUND' : 'COMPARING'],
        ['LINKED', hold ? '6 REPORTS · R84 000' : '…'],
      ];
      var left = [['CASE', 'UBF-61D4FFB0'], ['EVIDENCE', '3 FILES LOCKED'], ['SHA-256', 'a1c0e538…a082d670'], ['LOCKED', '12 OCT 2026 09:41']];
      for (var r = 0; r < 4; r++) {
        var y = ry + r * 22, alert = hold && r >= 2;
        ctx.textAlign = 'left'; ctx.font = mono(11, 400);
        ctx.fillStyle = 'rgba(147,163,180,0.85)'; ctx.fillText(right[r][0], rx, y);
        ctx.fillStyle = alert ? 'rgba(255,143,114,' + (0.95 * fade) + ')' : 'rgba(230,237,245,0.85)';
        ctx.font = mono(11, alert ? 500 : 400); ctx.fillText(right[r][1], rx + 74, y);
        ctx.font = mono(11, 400); ctx.textAlign = 'right';
        ctx.fillStyle = 'rgba(230,237,245,0.8)'; ctx.fillText(left[r][1], lx, y);
        ctx.fillStyle = 'rgba(147,163,180,0.85)'; ctx.fillText(left[r][0], lx - ctx.measureText(left[r][1]).width - 12, y);
      }
      ctx.textAlign = 'left';
      ctx.strokeStyle = 'rgba(147,163,180,0.35)'; ctx.lineWidth = 1;
      var bx = g.pw * 0.5 + 8, by = g.ph * 0.5, c = 18;
      [[-1, -1], [1, -1], [-1, 1], [1, 1]].forEach(function (s) {
        var x0 = g.cx + s[0] * bx, y0 = g.cy - g.ph * 0.04 + s[1] * by;
        ctx.beginPath(); ctx.moveTo(x0, y0 - s[1] * c); ctx.lineTo(x0, y0); ctx.lineTo(x0 - s[0] * c, y0); ctx.stroke();
      });
    }
    if (!reduce && visible) raf = requestAnimationFrame(frame);
  }

  function start() {
    if (raf) cancelAnimationFrame(raf);
    raf = 0;
    if (build()) raf = requestAnimationFrame(frame);
  }

  var timer = 0;
  window.addEventListener('resize', function () { clearTimeout(timer); timer = setTimeout(start, 150); });
  if ('IntersectionObserver' in window) {
    new IntersectionObserver(function (entries) {
      visible = entries[0].isIntersecting;
      if (visible && !raf && geo && !reduce) raf = requestAnimationFrame(frame);
    }).observe(cv);
  }
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(start); else start();
})();
