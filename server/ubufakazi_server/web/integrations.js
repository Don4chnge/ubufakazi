/* Public status page: what is genuinely connected right now. */
"use strict";

(async () => {
  const { el, api } = UBF;
  const app = document.getElementById("app");
  let i;
  try { i = await api("GET", "/api/integrations"); } catch (e) { app.replaceChildren(el("div", { class: "notice" }, e.message)); return; }
  const row = (name, on, note) => el("div", { class: "integ" }, el("span", { class: "dot " + (on ? "on" : "off") }), el("div", null, el("b", null, name), el("div", { class: "muted" }, note)));
  app.replaceChildren(el("section", { class: "panel" },
    row("Web reporting form", true, "Available at /report."),
    row("Telegram bot", i.telegram.running, i.telegram.note + (i.telegram.running ? " Open Telegram and search for @" + i.telegram.username + "." : "")),
    row("WhatsApp", i.whatsapp.configured, i.whatsapp.note),
    row("AI reading of images, voice notes and scans", i.ai_media_reading.configured, i.ai_media_reading.note),
    row("Trusted timestamps (RFC 3161)", i.trusted_timestamps.configured, i.trusted_timestamps.note),
    row("SAPS systems", i.saps.connected, i.saps.note),
    row("Banks", i.banks.connected, i.banks.note)),
    el("p", { class: "foot-note" }, "Ubufakazi 2.0 is a HackSecure 2026 prototype by Team CyberThreat. All stations, banks and earlier reports are fictional."));
})();
