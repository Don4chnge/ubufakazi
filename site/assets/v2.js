/* Shows the Ubufakazi 2.0 links only when this page is served by the 2.0 server (the static MVP keeps working alone). */
"use strict";
(function () {
  var band = document.getElementById("v2");
  if (!band || !window.fetch) return;
  fetch("/api/health", { headers: { Accept: "application/json" } })
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (d) { if (d && d.ok && d.version && d.version.indexOf("2.") === 0) band.hidden = false; })
    .catch(function () { /* static hosting: no 2.0 server, nothing to show */ });
})();
