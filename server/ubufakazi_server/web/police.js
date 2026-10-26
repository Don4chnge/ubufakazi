/* Ubufakazi 2.0 police console. Every request is checked on the server (session, two-factor, CSRF, station). */
"use strict";

(() => {
  const { el, icon, api, toast, money, date, dateTime, size, download } = UBF;
  const root = document.getElementById("root");
  const I = {
    queue: ["M4 6h16M4 12h16M4 18h10"],
    intel: ["M5 7a2 2 0 1 0 0-.01M19 5a2 2 0 1 0 0-.01M12 19a2 2 0 1 0 0-.01M7 7l3.5 10M17.2 6.2L13 17M7 6.5h10"],
    audit: ["M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z", "M9 12l2 2 4-4"],
    plug: ["M9 3v5M15 3v5M7 8h10v3a5 5 0 0 1-10 0zM12 16v5"],
    back: ["M15 6l-6 6 6 6"],
    pdf: ["M7 3h7l5 5v13H7z", "M14 3v5h5", "M10 14h6M10 17h4"],
    dl: ["M12 4v11M7 10l5 5 5-5M5 20h14"],
    check: ["M5 12l4 4 10-10"],
    redo: ["M4 12a8 8 0 1 0 2.4-5.7L4 8.5", "M4 4v4.5h4.5"],
  };
  let me = null, meta = null;
  const state = { filters: { q: "", status: "", category: "", station: "", linked: false, sort: "newest", page: 1 } };

  // ------------------------------------------------------------------ boot
  async function boot() {
    me = await UBF.session();
    if (!me || !["admin", "officer"].includes(me.role)) {
      if (me) { root.replaceChildren(el("div", { class: "public" }, el("div", { class: "notice" }, "This account cannot use the police console. ", el("a", { href: "/bank-demo" }, "Open the bank demo")))); showWho(); return; }
      UBF.loginForm(root, { title: "Police console", subtitle: "Signed-in officers see reports for their own station only. Two-factor code required.",
        onDone: (m) => { me = m; start(); } });
      return;
    }
    start();
  }

  function showWho() {
    const who = document.getElementById("who");
    who.replaceChildren(el("b", null, me.display_name), el("span", null, me.role === "admin" ? "All stations (admin)" : me.stations.map((s) => s.name.replace("Demo Station · ", "")).join(", ")));
    who.hidden = false;
    const lo = document.getElementById("logout");
    lo.hidden = false; lo.onclick = UBF.logout;
  }

  async function start() {
    showWho();
    try { meta = await api("GET", "/api/police/overview"); } catch (e) { toast(e.message, true); return; }
    window.addEventListener("hashchange", route);
    route();
  }

  // ------------------------------------------------------------------ shell + routing
  function shell(active, content) {
    const nav = (id, label, ic, hash) => el("button", { "aria-current": active === id ? "page" : null, onclick: () => { location.hash = hash; } }, icon(ic), label);
    root.replaceChildren(el("div", { class: "shell" },
      el("nav", { class: "rail", "aria-label": "Console" },
        nav("queue", "Report queue", I.queue, "#/queue"),
        nav("intel", "Intelligence", I.intel, "#/intel"),
        me.role === "admin" ? nav("audit", "Audit log", I.audit, "#/audit") : null,
        el("div", { class: "sep" }),
        nav("integ", "Integrations", I.plug, "#/integrations"),
        el("div", { class: "foot" }, "Fictional demo stations. Leads are investigative, not findings of guilt.")),
      el("main", { class: "main", id: "main" }, content)));
    window.scrollTo(0, 0);
  }

  function route() {
    const h = location.hash || "#/queue";
    const m = h.match(/^#\/report\/([A-Z0-9-]{6,24})(?:\/(\w+))?/);
    if (m) return showReport(m[1], m[2] || "overview");
    if (h.startsWith("#/intel")) return showIntel();
    if (h.startsWith("#/audit") && me.role === "admin") return showAudit();
    if (h.startsWith("#/integrations")) return showIntegrations();
    return showQueue();
  }

  // ------------------------------------------------------------------ queue
  async function showQueue() {
    const s = meta.stats;
    const tiles = el("div", { class: "tiles" },
      tile(s.awaiting, "Awaiting review", true), tile(s.by_status.under_review.count, "Under review"),
      tile(s.linked_reports, "Reports with possible connections", true), tile(money(s.reported_loss), "Reported losses", false, spark(s.per_day)));
    const f = state.filters;
    const q = el("input", { type: "search", id: "f-q", placeholder: "Reference, words, or an identifier (account, phone, website)", value: f.q });
    const sel = (id, label, opts, val) => el("div", { class: "field" }, el("label", { for: id }, label),
      el("select", { id }, opts.map(([v, t]) => el("option", { value: v, selected: v === val ? true : null }, t))));
    const stOpts = [["", "All statuses"], ["open", "All open"], ...Object.entries(meta.statuses)];
    const catOpts = [["", "All categories"], ...Object.entries(meta.categories)];
    const stnOpts = [["", meta.stations.length > 1 ? "All my stations" : meta.stations[0]?.name || "Station"], ...meta.stations.map((x) => [x.code, x.name.replace("Demo Station · ", "")])];
    const sortOpts = [["newest", "Newest first"], ["oldest", "Oldest first"], ["amount", "Largest loss"]];
    const linked = el("input", { type: "checkbox", id: "f-linked", checked: f.linked ? true : null });
    const filters = el("form", { class: "filters", role: "search" },
      el("div", { class: "field q" }, el("label", { for: "f-q" }, "Search"), q),
      sel("f-status", "Status", stOpts, f.status), sel("f-cat", "Category", catOpts, f.category),
      sel("f-stn", "Station", stnOpts, f.station), sel("f-sort", "Sort", sortOpts, f.sort),
      el("label", { class: "check" }, linked, "Only linked"));
    const list = el("div", null, el("div", { class: "empty" }, "Loading…"));
    const read = () => {
      Object.assign(f, { q: q.value, status: filters.querySelector("#f-status").value, category: filters.querySelector("#f-cat").value,
        station: filters.querySelector("#f-stn").value, sort: filters.querySelector("#f-sort").value, linked: linked.checked, page: 1 });
      load();
    };
    filters.addEventListener("change", read);
    filters.addEventListener("submit", (e) => { e.preventDefault(); read(); });
    let t; q.addEventListener("input", () => { clearTimeout(t); t = setTimeout(read, 350); });

    shell("queue", [
      el("div", { class: "page-head" }, el("div", null, el("div", { class: "kicker" }, me.role === "admin" ? "All demo stations" : me.stations.map((x) => x.name).join(" · ")),
        el("h1", null, "Report queue"), el("p", null, "Reports submitted through Telegram and the web, prepared for your review."))),
      tiles, filters, list]);

    async function load() {
      const p = new URLSearchParams({ q: f.q, status: f.status, category: f.category, station: f.station, sort: f.sort, page: f.page, page_size: 25, linked: f.linked ? 1 : 0 });
      let data;
      try { data = await api("GET", "/api/police/reports?" + p); } catch (e) { list.replaceChildren(el("div", { class: "empty" }, e.message)); return; }
      if (!data.items.length) { list.replaceChildren(el("div", { class: "empty" }, "No reports match these filters.")); return; }
      const rows = data.items.map((r) => {
        const tr = el("tr", { tabindex: "0", onclick: () => { location.hash = "#/report/" + r.reference; },
                              onkeydown: (e) => { if (e.key === "Enter") location.hash = "#/report/" + r.reference; } },
          el("td", null, el("span", { class: "ref" }, r.reference), r.is_seed ? el("span", { class: "tag" }, "synthetic") : null,
            r.sensitive ? el("span", { class: "tag sens" }, "sensitive") : null, el("span", { class: "sub" }, dateTime(r.created_at) + " · " + r.source)),
          el("td", null, r.scam_type_label || r.category_label, el("span", { class: "sub" }, r.complainant_name || "Name not given")),
          el("td", null, r.town || "-", el("span", { class: "sub" }, r.station.replace("Demo Station · ", ""))),
          el("td", { class: "num" }, r.amount_paid ? money(r.amount_paid) : "-"),
          el("td", null, r.leads ? el("span", { class: "lead-badge" + (r.corroborated ? "" : " single") }, `${r.leads} lead${r.leads > 1 ? "s" : ""}`) : el("span", { class: "muted small" }, "none")),
          el("td", null, el("span", { class: "st st-" + r.status }, r.status_label), r.processing_status !== "ready" ? el("span", { class: "sub" }, "processing: " + r.processing_status) : null),
          el("td", { class: "num" }, String(r.evidence_count)));
        return tr;
      });
      const pages = Math.max(1, Math.ceil(data.total / data.page_size));
      list.replaceChildren(
        el("div", { class: "table-wrap" }, el("table", { class: "data" },
          el("thead", null, el("tr", null, ["Reference", "Type / complainant", "Area / station", "Paid", "Leads", "Status", "Files"].map((h) => el("th", { scope: "col" }, h)))),
          el("tbody", null, rows))),
        el("div", { class: "pager" }, el("span", null, `${data.total} report${data.total === 1 ? "" : "s"} · page ${data.page} of ${pages}`),
          el("span", null,
            el("button", { class: "btn btn-ghost btn-small", disabled: data.page <= 1 ? true : null, onclick: () => { f.page--; load(); } }, "Previous"), " ",
            el("button", { class: "btn btn-ghost btn-small", disabled: data.page >= pages ? true : null, onclick: () => { f.page++; load(); } }, "Next"))));
    }
    load();
  }

  function tile(value, label, alert, extra) {
    return el("div", { class: "tile" + (alert ? " alert" : "") }, el("b", null, String(value)), el("span", null, label), extra || null);
  }

  function spark(perDay) {
    if (!perDay || perDay.length < 2) return null;
    const vals = perDay.map((d) => d[1]), max = Math.max(...vals, 1), W = 200, H = 26;
    const pts = vals.map((v, i) => [i * W / (vals.length - 1), H - 2 - v / max * (H - 4)]);
    const d = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join("");
    return el("svg:svg", { class: "spark", viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: "none", "aria-hidden": "true" },
      el("svg:path", { class: "area", d: d + `L${W} ${H}L0 ${H}Z` }), el("svg:path", { d }));
  }

  // ------------------------------------------------------------------ report detail
  async function showReport(ref, tab) {
    shell("queue", el("div", { class: "empty" }, "Loading report…"));
    let r;
    try { r = await api("GET", "/api/police/reports/" + encodeURIComponent(ref)); }
    catch (e) { shell("queue", [backBtn(), el("div", { class: "empty" }, e.status === 404 ? "Report not found, or it belongs to another station." : e.message)]); return; }

    const statusSel = el("select", { id: "st-sel", "aria-label": "New status" }, Object.entries(meta.statuses).map(([k, v]) => el("option", { value: k, selected: k === r.status ? true : null }, v)));
    const statusNote = el("input", { type: "text", id: "st-note", placeholder: "Note for the record (optional)", maxlength: "1000" });
    const statusBtn = el("button", { class: "btn btn-primary btn-small", onclick: async () => {
      try { await api("POST", `/api/police/reports/${r.reference}/status`, { status: statusSel.value, note: statusNote.value }); toast("Status updated and recorded in the audit log."); refreshMeta(); showReport(ref, tab); }
      catch (e) { toast(e.message, true); } } }, "Update status");

    const packBtn = el("button", { class: "btn btn-ghost btn-small", onclick: async () => {
      packBtn.disabled = true;
      try { download(await api("GET", `/api/police/reports/${r.reference}/pack`, undefined, { blob: true }), `Ubufakazi-${r.reference}-POLICE.pdf`); toast("Police case pack downloaded (recorded in the audit log)."); }
      catch (e) { toast(e.message, true); } finally { packBtn.disabled = false; } } }, icon(I.pdf), "Police case pack");
    const reBtn = r.is_seed ? null : el("button", { class: "btn btn-ghost btn-small", onclick: async () => {
      try { await api("POST", `/api/police/reports/${r.reference}/reprocess`, {}); toast("Re-processing started. Originals are not changed."); setTimeout(() => showReport(ref, tab), 1500); }
      catch (e) { toast(e.message, true); } } }, icon(I.redo), "Re-run processing");

    const tabs = [["overview", "Overview"], ["statement", "Statement"], ["evidence", "Evidence & custody", r.evidence.length],
                  ["timeline", "Timeline", r.timeline.length], ["leads", "Leads & graph", r.leads.length], ["notes", "Notes", r.notes.length], ["audit", "Audit trail"]];
    const tabBar = el("div", { class: "tabs", role: "tablist" }, tabs.map(([id, label, n]) =>
      el("button", { role: "tab", "aria-selected": id === tab ? "true" : "false", onclick: () => { location.hash = `#/report/${r.reference}/${id}`; } },
        label, n !== undefined ? el("span", { class: "count" }, String(n)) : null)));
    const body = el("div", { role: "tabpanel" });

    shell("queue", [
      backBtn(),
      r.sensitive ? el("div", { class: "notice" }, el("b", null, "Sensitive report. "), "Contact the complainant only through safe channels. They may share a device with the other person. Emergency: 10111 · GBV Command Centre 0800 428 428.") : null,
      el("div", { class: "case-head" },
        el("div", null, el("div", { class: "kicker" }, r.station + (r.is_seed ? " · synthetic record" : "")),
          el("h1", null, r.reference),
          el("div", { class: "meta-line" }, el("span", { class: "st st-" + r.status }, r.status_label), el("span", null, r.scam_type_label || r.category_label),
            el("span", null, [r.town, r.province].filter(Boolean).join(", ") || "-"), el("span", null, "Received " + dateTime(r.created_at) + " via " + r.source),
            r.amount_paid ? el("span", null, "Paid " + money(r.amount_paid)) : null)),
        el("div", { class: "actions" }, packBtn, reBtn)),
      el("div", { class: "status-box" }, statusSel, statusNote, statusBtn),
      tabBar, body]);

    ({ overview, statement, evidence, timeline, leads, notes, audit }[tab] || overview)(r, body);
  }

  function backBtn() { return el("button", { class: "back", onclick: () => { location.hash = "#/queue"; } }, icon(I.back), "Back to queue"); }

  async function refreshMeta() { try { meta = await api("GET", "/api/police/overview"); } catch (_) { /* keep old */ } }

  function overview(r, body) {
    const f = r.facts || {};
    const ids = r.identifiers || [];
    const kindLabel = { account: "Receiving account", phone: "Phone", email: "Email", domain: "Website", social: "Social profile", username: "@username", payment_ref: "Payment ref" };
    const srcLabel = (s) => s === "chat" ? "chat" : s === "description" ? "complainant" : s === "seed" ? "synthetic" : s.startsWith("evidence:") ? "file" : s;
    const groups = {};
    ids.forEach((i) => { (groups[i.kind] = groups[i.kind] || []).push(i); });
    const facts = el("dl", { class: "facts" },
      Object.entries(groups).map(([k, arr]) => [el("dt", null, kindLabel[k] || k),
        el("dd", null, arr.map((i) => el("span", { class: "chip" }, i.display + (i.bank ? " · " + i.bank : ""), el("span", { class: "src" }, srcLabel(i.source)))))]),
      f.suspect_alias ? [el("dt", null, "Name used"), el("dd", null, el("span", { class: "chip" }, f.suspect_alias))] : null,
      f.total_paid ? [el("dt", null, "Payments"), el("dd", null, (f.payments || [f.total_paid]).map((p) => el("span", { class: "chip" }, money(p))), el("b", null, " = " + money(f.total_paid)))] : null,
      f.total_requested ? [el("dt", null, "Requested"), el("dd", null, money(f.total_requested))] : null);
    const answers = Object.entries(r.answers || {}).filter(([, v]) => v);
    body.replaceChildren(el("div", { class: "cols" },
      el("div", null,
        el("section", { class: "panel" }, el("h3", null, "The complainant's account"), el("div", { class: "quote" }, r.description),
          answers.length ? el("dl", { class: "facts" }, answers.map(([k, v]) => [el("dt", null, k.replace(/_/g, " ")), el("dd", null, String(v))])) : null,
          el("p", { class: "hint" }, `When (as stated): ${r.incident_when || "not given"} · Statement language: ${r.language}` + (r.location ? ` · Approximate location (${r.location.precision}): ${r.location.lat}, ${r.location.lon}` : ""))),
        el("section", { class: "panel" }, el("h3", null, "Extracted facts ", el("span", { class: "tag" }, "unverified")),
          ids.length || f.total_paid ? facts : el("p", { class: "muted" }, "Nothing extracted automatically."),
          el("p", { class: "hint" }, f.method || ""))),
      el("div", null,
        el("section", { class: "panel" }, el("h3", null, "Processing"),
          el("p", null, el("span", { class: "st" }, r.processing_status)),
          r.processing_note ? el("div", { class: "notice warn" }, r.processing_note) : el("p", { class: "muted small" }, "All evidence processed with the documented rules."),
          r.consent ? el("p", { class: "hint" }, `Consent ${r.consent.version} given ${dateTime(r.consent.given_at)}.`) : null),
        el("section", { class: "panel" }, el("h3", null, "Possible connections"),
          r.leads.length ? [el("p", null, el("b", { class: "mono" }, String(r.leads.length)), ` other report${r.leads.length > 1 ? "s" : ""} share signals with this one (${r.leads.filter((l) => l.strength === "corroborated").length} corroborated, ${r.leads.filter((l) => !l.visible).length} at other stations).`),
            el("button", { class: "btn btn-ghost btn-small", onclick: () => { location.hash = `#/report/${r.reference}/leads`; } }, "Open leads & graph")]
            : el("p", { class: "muted" }, "No possible connections found.")),
        el("section", { class: "panel" }, el("h3", null, "Status history"),
          el("ul", { class: "steps-v" }, r.history.map((h) => el("li", { class: "done" }, el("b", null, h.to_label), el("div", { class: "muted small" }, `${dateTime(h.at)} · ${h.by}${h.note ? " · " + h.note : ""}`))))))));
  }

  function statement(r, body) {
    const langs = { en: "English", zu: "isiZulu", xh: "isiXhosa", af: "Afrikaans", st: "Sesotho" };
    const avail = Object.keys(r.statements || {});
    let cur = avail.includes(r.language) ? r.language : avail[0];
    const box = el("div", { class: "statement" });
    const sw = el("div", { class: "lang-switch", role: "group", "aria-label": "Statement language" });
    const paint = () => {
      box.textContent = (r.statements || {})[cur] || "Not prepared yet.";
      sw.replaceChildren(...avail.map((l) => el("button", { "aria-pressed": l === cur ? "true" : "false", onclick: () => { cur = l; paint(); } }, langs[l] + (l === r.language ? " (chosen)" : ""))));
    };
    paint();
    body.replaceChildren(el("div", { class: "cols" },
      el("section", { class: "panel" }, el("h3", null, "Draft statement"), el("p", { class: "hint" }, "Prepared automatically from the report. The complainant must read, correct and sign it at the station."), sw, box,
        el("div", { class: "row-btns" }, el("button", { class: "btn btn-ghost btn-small", onclick: () => { navigator.clipboard.writeText(box.textContent).then(() => toast("Copied.")); } }, "Copy text"))),
      r.bank_report ? el("section", { class: "panel" }, el("h3", null, "Draft bank fraud report"), el("p", { class: "hint" }, "For the complainant to send to their own bank. Ubufakazi does not contact banks."),
        el("div", { class: "quote mono small" }, r.bank_report)) : el("section", { class: "panel" }, el("h3", null, "Bank report"), el("p", { class: "muted" }, "Not applicable to this report."))));
  }

  function evidence(r, body) {
    if (!r.evidence.length) { body.replaceChildren(el("div", { class: "empty" }, r.is_seed ? "Synthetic seed record: no evidence files." : "No files were attached.")); return; }
    body.replaceChildren(el("div", { class: "notice info" }, "Originals are stored exactly as received and never modified. Their SHA-256 was calculated by the server on arrival. Use Verify to re-hash the stored file now. Every download and verification is written to the audit log."),
      el("div", { class: "stack" }, ...r.evidence.map((e) => evCard(r, e))));
  }

  function evCard(r, e) {
    const thumb = el("div", { class: "thumb" }, e.type);
    const result = el("div", { "aria-live": "polite" });
    const verify = el("button", { class: "btn btn-ghost btn-small", onclick: async () => {
      verify.disabled = true;
      try {
        const v = await api("POST", `/api/police/evidence/${e.id}/verify`, {});
        result.replaceChildren(v.match ? el("div", { class: "verify-ok" }, "✓ Unchanged since receipt (" + dateTime(v.checked_at) + ")")
          : el("div", { class: "verify-bad" }, "✗ MISMATCH: stored file differs from the hash recorded at receipt. Do not rely on it; escalate."));
      } catch (ex) { toast(ex.message, true); } finally { verify.disabled = false; }
    } }, icon(I.check), "Verify");
    const dl = el("button", { class: "btn btn-ghost btn-small", onclick: async () => {
      try { download(await api("GET", `/api/police/evidence/${e.id}/download`, undefined, { blob: true }), `${r.reference}-${e.id}-${e.name}`); }
      catch (ex) { toast(ex.message, true); } } }, icon(I.dl), "Original");
    if (e.previewable) {
      const show = el("button", { class: "btn btn-ghost btn-small", onclick: async () => {
        try { const b = await api("GET", `/api/police/evidence/${e.id}/download?inline=1`, undefined, { blob: true });
              thumb.replaceChildren(el("img", { src: URL.createObjectURL(b), alt: "Preview of " + e.name })); show.remove(); }
        catch (ex) { toast(ex.message, true); } } }, "Preview");
      thumb.replaceChildren(show);
    }
    const ders = e.derivatives.map((d) => el("details", { class: "deriv" },
      el("summary", null, d.kind, d.ai_generated ? el("span", { class: "tag ai" }, "AI-generated · unverified") : null, " · ", el("span", { class: "muted" }, d.method), " · ", d.note),
      d.content ? el("pre", null, d.content + (d.truncated ? "\n[…truncated in this view]" : "")) : null));
    return el("article", { class: "ev" }, thumb,
      el("div", null, el("div", { class: "name" }, e.name),
        el("div", { class: "row" }, el("span", null, e.type.toUpperCase() + " · " + size(e.size)), el("span", null, "received " + dateTime(e.received_at) + " (server clock)"), el("span", null, "via " + e.channel),
          e.declared_mime ? el("span", null, "declared " + e.declared_mime) : null),
        el("div", { class: "hash", title: "SHA-256" }, e.sha256), result, ders),
      el("div", { class: "btns" }, verify, dl));
  }

  function timeline(r, body) {
    if (!r.timeline.length) { body.replaceChildren(el("div", { class: "empty" }, "No timeline yet.")); return; }
    const src = { chat: "from chat", complainant: "complainant", system: "Ubufakazi" };
    body.replaceChildren(el("section", { class: "panel" }, el("h3", null, "Timeline"), el("p", { class: "hint" }, "Events from the chat are extracted automatically and must be checked against the original messages."),
      el("ol", { class: "tl" }, r.timeline.map((e) => el("li", { class: "k-" + e.kind },
        el("div", { class: "when" }, e.when || "-"),
        el("div", { class: "what" }, e.what, el("span", { class: "src-tag" }, src[e.source] || e.source), e.quote ? el("q", null, e.quote) : null))))));
  }

  async function leads(r, body) {
    const gbox = el("div", { class: "graph-box" }, el("div", { class: "empty" }, "Building graph…"));
    const summary = el("div", { class: "graph-summary" });
    const list = r.leads.length ? r.leads.map((L) => el("article", { class: `lead ${L.strength}${L.visible ? "" : " restricted"}` },
      el("div", { class: "lead-top" },
        L.visible ? el("button", { class: "back", onclick: () => { location.hash = "#/report/" + L.reference + "/leads"; } }, el("span", { class: "ref" }, L.reference))
                  : el("span", null, el("b", null, "Restricted report"), " ", el("span", { class: "muted small" }, "· request access through your station commander")),
        el("span", { class: "lead-badge" + (L.strength === "corroborated" ? "" : " single") }, L.strength === "corroborated" ? "Corroborated lead" : "Single-signal lead")),
      el("div", { class: "muted small" }, L.station + (L.visible ? ` · ${date(L.date)} · ${money(L.amount_paid)} · ${L.status_label}` : "")),
      el("ul", null, L.signals.map((s) => el("li", null, s.reason, ...(s.conflicts || []).map((c) => el("div", { class: "conflict" }, "Conflict: " + c)))))))
      : [el("div", { class: "empty" }, "No possible connections.")];
    body.replaceChildren(
      el("div", { class: "notice info" }, el("b", null, "How to read this. "), "A lead means another report shares an identifier or message template with this one. One kind of shared signal = single lead; two or more kinds = corroborated. Shared accounts can belong to money mules, so a lead is a reason to investigate, never proof of who is responsible."),
      el("section", { class: "panel" }, el("h3", null, "Investigation graph"), summary, gbox,
        el("p", { class: "hint" }, "Drag nodes, scroll to zoom, double-click a report from your station to open it. Reports at other stations stay restricted.")),
      el("section", { class: "panel" }, el("h3", null, `Leads (${r.leads.length})`), list));
    try {
      const g = await api("GET", `/api/police/reports/${r.reference}/graph`);
      const s = g.summary;
      summary.replaceChildren(el("span", null, el("b", null, String(s.reports)), " reports linked"), el("span", null, el("b", null, String(s.visible)), " visible to you"),
        el("span", null, el("b", null, String(s.restricted)), " restricted"), el("span", null, el("b", null, String(s.stations)), " stations"),
        el("span", null, el("b", null, money(s.visible_amount)), " reported loss (visible)"), ...(g.truncated ? [el("span", null, "(showing the closest 60)")] : []));
      if (s.reports < 2) { gbox.replaceChildren(el("div", { class: "empty" }, "This report has no possible connections yet.")); return; }
      requestAnimationFrame(() => UBFGraph.render(gbox, g, { onOpen: (ref) => { location.hash = "#/report/" + ref + "/leads"; } }));
    } catch (e) { gbox.replaceChildren(el("div", { class: "empty" }, e.message)); }
  }

  function notes(r, body) {
    const ta = el("textarea", { id: "note-body", rows: "3", maxlength: "4000", placeholder: "Add a case note (visible to officers at this station)" });
    const add = el("button", { class: "btn btn-primary btn-small", onclick: async () => {
      if (!ta.value.trim()) return;
      try { await api("POST", `/api/police/reports/${r.reference}/notes`, { body: ta.value }); toast("Note added."); showReport(r.reference, "notes"); }
      catch (e) { toast(e.message, true); } } }, "Add note");
    body.replaceChildren(el("section", { class: "panel" }, el("h3", null, "Case notes"),
      r.notes.length ? r.notes.map((n) => el("div", { class: "note" }, el("div", { class: "by" }, `${n.by} · ${dateTime(n.at)}`), el("div", { class: "quote" }, n.body))) : el("p", { class: "muted" }, "No notes yet."),
      el("div", { class: "field" }, el("label", { for: "note-body" }, "New note"), ta), el("div", { class: "row-btns" }, add)));
  }

  async function audit(r, body) {
    body.replaceChildren(el("div", { class: "empty" }, "Loading…"));
    try {
      const [rows, chain] = await Promise.all([api("GET", `/api/police/reports/${r.reference}/audit`), api("GET", "/api/police/audit/verify")]);
      body.replaceChildren(
        el("div", { class: chain.intact ? "notice info" : "notice" }, chain.intact ? `Audit chain verified: ${chain.checked} events, every hash links to the one before.` : `AUDIT CHAIN BROKEN at event #${chain.broken_at}. Escalate.`),
        el("div", { class: "table-wrap" }, el("table", { class: "data" },
          el("thead", null, el("tr", null, ["#", "When", "Action", "Actor", "Target", "Event hash"].map((h) => el("th", null, h)))),
          el("tbody", null, rows.map((a) => el("tr", { class: "audit-row" }, el("td", { class: "num" }, String(a.id)), el("td", null, dateTime(a.at)), el("td", null, a.action),
            el("td", null, a.actor), el("td", { class: "mono small" }, a.target), el("td", { class: "hash" }, a.hash.slice(0, 24) + "…")))))));
    } catch (e) { body.replaceChildren(el("div", { class: "empty" }, e.message)); }
  }

  // ------------------------------------------------------------------ intelligence
  async function showIntel() {
    shell("intel", el("div", { class: "empty" }, "Loading…"));
    let cl;
    try { cl = await api("GET", "/api/police/intel/clusters"); } catch (e) { shell("intel", el("div", { class: "empty" }, e.message)); return; }
    const kindLabel = { account: "acc", phone: "tel", domain: "web", social: "social", email: "email", username: "user", payment_ref: "ref" };
    shell("intel", [
      el("div", { class: "page-head" }, el("div", null, el("div", { class: "kicker" }, "Scam intelligence"), el("h1", null, "Possible networks"),
        el("p", null, "Groups of reports linked by shared accounts, numbers, websites or message templates. Each group includes at least one report from your station."))),
      el("div", { class: "notice info" }, "Investigative leads only. Numbers and accounts can be recycled, spoofed or belong to money mules. Reports held by other stations are counted but not shown."),
      el("div", { class: "clusters" }, cl.length ? cl.map((c) => el("button", { class: "cluster", onclick: () => { location.hash = "#/report/" + c.anchor + "/leads"; } },
        el("div", { class: "lead-top" }, el("span", { class: "big" }, String(c.size)), el("span", { class: "muted small" }, `${c.stations} station${c.stations > 1 ? "s" : ""} · ${c.provinces.length} province${c.provinces.length > 1 ? "s" : ""}`)),
        el("div", null, el("b", null, c.scam_type || "Mixed"), el("span", { class: "muted" }, ` · ${date(c.first)} → ${date(c.last)}`)),
        el("div", { class: "muted small" }, `${c.visible} visible to you · ${c.restricted} restricted · ${money(c.visible_amount)} reported loss (visible)`),
        el("div", { class: "chips" }, c.shared.map((s) => el("span", { class: "chip" }, `${kindLabel[s.kind] || s.kind} ${s.display}`, el("span", { class: "src" }, `×${s.reports}`))))))
        : el("div", { class: "empty" }, "No linked reports yet."))]);
  }

  // ------------------------------------------------------------------ audit (admin)
  async function showAudit() {
    shell("audit", el("div", { class: "empty" }, "Loading…"));
    let a;
    try { a = await api("GET", "/api/admin/audit?limit=200"); } catch (e) { shell("audit", el("div", { class: "empty" }, e.message)); return; }
    shell("audit", [
      el("div", { class: "page-head" }, el("div", null, el("div", { class: "kicker" }, "Administrator"), el("h1", null, "Audit log"),
        el("p", null, "Append-only and hash-chained: each event's hash covers the previous one, so editing or deleting history is detectable. It is evidence of tampering, not prevention of it."))),
      el("div", { class: a.verify.intact ? "notice info" : "notice" }, a.verify.intact ? `Chain intact · ${a.verify.checked} events checked · head ${a.verify.head.slice(0, 16)}…` : `CHAIN BROKEN at event #${a.verify.broken_at}`),
      el("div", { class: "table-wrap" }, el("table", { class: "data" },
        el("thead", null, el("tr", null, ["#", "When", "Action", "Actor", "Target", "IP", "Hash"].map((h) => el("th", null, h)))),
        el("tbody", null, a.events.map((e) => el("tr", { class: "audit-row", onclick: () => { if (e.target.startsWith("report:")) location.hash = "#/report/" + e.target.slice(7); } },
          el("td", { class: "num" }, String(e.id)), el("td", null, dateTime(e.at)), el("td", null, e.action), el("td", null, e.actor), el("td", { class: "mono small" }, e.target),
          el("td", { class: "mono small" }, e.ip || "-"), el("td", { class: "hash" }, e.hash.slice(0, 16) + "…"))))))]);
  }

  // ------------------------------------------------------------------ integrations
  async function showIntegrations() {
    shell("integ", el("div", { class: "empty" }, "Loading…"));
    const i = await api("GET", "/api/integrations");
    shell("integ", [el("div", { class: "page-head" }, el("div", null, el("div", { class: "kicker" }, "System"), el("h1", null, "Integrations"),
      el("p", null, "What is connected right now. Nothing here is simulated as connected."))), integList(i)]);
  }

  window.UBFIntegList = integList;
  function integList(i) {
    const row = (name, on, note) => el("div", { class: "integ" }, el("span", { class: "dot " + (on ? "on" : "off") }), el("div", null, el("b", null, name), el("div", { class: "muted" }, note)));
    return el("section", { class: "panel" },
      row("Telegram bot", i.telegram.running, i.telegram.note),
      row("WhatsApp", i.whatsapp.configured, i.whatsapp.note),
      row("AI reading of images, voice notes and scans", i.ai_media_reading.configured, i.ai_media_reading.note),
      row("Trusted timestamps (RFC 3161)", i.trusted_timestamps.configured, i.trusted_timestamps.note),
      row("SAPS systems", i.saps.connected, i.saps.note),
      row("Banks", i.banks.connected, i.banks.note),
      row("Database", true, i.database === "sqlite" ? "SQLite (local demo). Set DATABASE_URL for Postgres/Supabase." : "PostgreSQL"));
  }

  boot();
})();
