/* When this page is served by the Ubufakazi 2.0 server, point the landing page at the real system.
   On static hosting (no server) nothing changes and the in-browser MVP keeps working. */
"use strict";
(function () {
  var band = document.getElementById("v2");
  if (!band || !window.fetch) return;
  fetch("/api/health", { headers: { Accept: "application/json" } })
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (d) {
      if (!(d && d.ok && d.version && d.version.indexOf("2.") === 0)) return;
      band.hidden = false;
      var cta = document.querySelector(".h-cta");
      if (cta) {
        cta.setAttribute("href", "/report");
        for (var i = 0; i < cta.childNodes.length; i++) {
          if (cta.childNodes[i].nodeType === 3 && cta.childNodes[i].textContent.trim()) { cta.childNodes[i].textContent = "Report an incident "; break; }
        }
      }
      var sub = document.querySelector(".h-sub");
      if (sub) { sub.setAttribute("href", "/track"); sub.removeAttribute("target"); sub.textContent = "or track a report you already made"; }
      var nav = document.querySelector(".h-nav a[href='#report']");
      if (nav) nav.textContent = "Offline case builder";
    })
    .catch(function () { /* static hosting: nothing to change */ });
})();
