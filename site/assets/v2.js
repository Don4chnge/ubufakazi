/* When this MVP page is opened on the Ubufakazi 2.0 server (at /mvp), show a banner linking back to the full system.
   On static hosting (Netlify) there is no server, so nothing changes and the offline MVP works alone. */
"use strict";
(function () {
  var band = document.getElementById("v2");
  if (!band || !window.fetch) return;
  fetch("/api/health", { headers: { Accept: "application/json" } })
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (d) { if (d && d.ok && d.version && d.version.indexOf("2.") === 0) band.hidden = false; })
    .catch(function () { /* static hosting: nothing to show */ });
})();
