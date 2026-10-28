/* Ubufakazi 2.0 bank fraud desk console (code and API keep the old "police"/"station" names). Every request is checked on the server (session, two-factor, CSRF, branch). */
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
    home: ["M4 11l8-7 8 7v9H4z", "M10 20v-6h4v6"],
    files: ["M6 3h8l4 4v14H6z", "M14 3v4h4", "M9 12h6M9 16h4"],
    net: ["M12 5a2 2 0 1 0 0 .01M5 18a2 2 0 1 0 0 .01M19 18a2 2 0 1 0 0 .01M11 7l-5 9M13 7l5 9M7 18h10"],
    side: ["M4 5h16v14H4z", "M9 5v14"],
    board: ["M3 6l6-2 6 2 6-2v14l-6 2-6-2-6 2z", "M9 4v14M15 6v14"],
    shield: ["M12 3l8 3v6c0 5-3.5 8.3-8 9.8C7.5 20.3 4 17 4 12V6z", "M12 8v5M12 16h.01"],
  };
  const COLLAPSE_KEY = "ubf-rail-collapsed";
  let collapsed = false;
  try { collapsed = localStorage.getItem(COLLAPSE_KEY) === "1"; } catch (_) { /* storage unavailable */ }
  let me = null, meta = null;
  const state = { filters: { q: "", status: "", category: "", station: "", linked: false, sort: "newest", page: 1 } };

  // ------------------------------------------------------------------ boot
  async function boot() {
    me = await UBF.session();
    if (!me || !["admin", "officer"].includes(me.role)) {
      if (me) { root.replaceChildren(el("div", { class: "public" }, el("div", { class: "notice" }, "This account cannot use the fraud desk console. ", el("a", { href: "/bank" }, "Open Ubuntu Trust Bank")))); showWho(); return; }
      UBF.loginForm(root, { title: "Bank fraud desk", subtitle: "Ubuntu Trust Bank (fictional). Signed-in investigators see reports for their own branch only. Two-factor code required.",
        onDone: (m) => { me = m; start(); } });
      const panel = root.querySelector(".login");
      if (panel) panel.appendChild(el("p", { class: "hint" }, "Demo team: ", el("a", { href: "/demo-logins?next=" + encodeURIComponent(location.pathname + location.hash) }, "sign in with the demo-logins helper"),
        location.hash.startsWith("#/handover/") ? " (you will come straight back to this handover)." : "."));
      return;
    }
    start();
  }

  function showWho() {
    const who = document.getElementById("who");
    who.replaceChildren(el("b", null, me.display_name), el("span", null, me.role === "admin" ? "All branches · head office" : me.stations.map((s) => s.name.replace("UTB · ", "")).join(", ")));
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
    const nav = (id, label, ic, hash) => el("button", { "aria-current": active === id ? "page" : null, title: label, onclick: () => { location.hash = hash; } }, icon(ic), el("span", { class: "label-txt" }, label));
    const shellEl = el("div", { class: "shell" + (collapsed ? " collapsed" : "") },
      el("nav", { class: "rail", "aria-label": "Console" },
        nav("overview", "Overview", I.home, "#/overview"),
        nav("board", "Syndicate board", I.board, "#/board"),
        nav("queue", "Case queue", I.queue, "#/queue"),
        nav("evidence", "Evidence", I.files, "#/evidence"),
        nav("network", "Scam network", I.net, "#/network"),
        me.role === "admin" ? nav("audit", "Audit log", I.audit, "#/audit") : null,
        me.role === "admin" ? nav("security", "Security alerts", I.shield, "#/security") : null,
        el("div", { class: "sep" }),
        nav("integ", "Integrations", I.plug, "#/integrations"),
        el("button", { class: "collapse-btn", title: "Collapse sidebar", "aria-label": "Collapse or expand the sidebar", onclick: () => {
          collapsed = !collapsed; shellEl.classList.toggle("collapsed", collapsed);
          try { localStorage.setItem(COLLAPSE_KEY, collapsed ? "1" : "0"); } catch (_) { /* ignore */ }
        } }, icon(I.side), el("span", { class: "label-txt" }, "Collapse")),
        el("div", { class: "foot" }, "Fictional bank and branches. Leads are investigative, not findings of guilt.")),
      el("main", { class: "main", id: "main" }, content));
    root.replaceChildren(shellEl);
    window.scrollTo(0, 0);
  }

  function route() {
    const h = location.hash || "#/overview";
    const ho = h.match(/^#\/handover\/([A-Z0-9-]{6,24})\/([a-f0-9]{24})$/);
    if (ho) return showHandover(ho[1], ho[2]);
    const m = h.match(/^#\/report\/([A-Z0-9-]{6,24})(?:\/(\w+))?/);
    if (m) return showReport(m[1], m[2] || "overview");
    const n = h.match(/^#\/network(?:\/([A-Z0-9-]{6,24}))?/);
    if (n) return showNetwork(n[1]);
    if (h.startsWith("#/intel")) return showNetwork();
    const b = h.match(/^#\/board(?:\/(SYN-[A-Z0-9]+))?/);
    if (b) return showBoard(b[1]);
    if (h.startsWith("#/queue")) return showQueue();
    if (h.startsWith("#/evidence")) return showEvidence();
    if (h.startsWith("#/audit") && me.role === "admin") return showAudit();
    if (h.startsWith("#/security") && me.role === "admin") return showSecurity();
    if (h.startsWith("#/integrations")) return showIntegrations();
    return showOverview();
  }

  // ------------------------------------------------------------------ overview
  async function showOverview() {
    shell("overview", el("div", { class: "empty" }, "Loading…"));
    await refreshMeta();
    const s = meta.stats;
    let recent = { items: [] }, cl = [];
    try { [recent, cl] = await Promise.all([api("GET", "/api/police/reports?page_size=6&sort=newest"), api("GET", "/api/police/intel/clusters")]); } catch (e) { toast(e.message, true); }
    const maxS = Math.max(1, ...Object.values(s.by_status).map((x) => x.count));
    const maxC = Math.max(1, ...Object.values(s.by_category).map((x) => x.count));
    const bars = (obj, max, filterKey) => el("div", { class: "bars-h" }, Object.entries(obj).filter(([, v]) => v.count || filterKey === "status").map(([k, v]) => {
      const fill = el("div", { class: "fill" }); fill.style.width = (v.count / max * 100) + "%";
      return el("div", { class: "bar-h" }, el("span", null, v.label), el("div", { class: "track" }, fill), el("b", null, String(v.count)));
    }));
    const stationTxt = me.role === "admin" ? "UTB head office · all branches" : me.stations.map((x) => x.name).join(" · ");
    shell("overview", [
      el("div", { class: "page-head" }, el("div", null, el("div", { class: "kicker" }, stationTxt),
        el("h1", null, `Good ${new Date().getHours() < 12 ? "morning" : new Date().getHours() < 18 ? "afternoon" : "evening"}, ${me.display_name.replace(/^Demo /, "")}`),
        el("p", null, "Your fraud desk overview. Counts include only reports your branch may see. All data in this demo is synthetic.")),
        el("div", { class: "row-btns" }, el("a", { class: "btn btn-primary", href: "#/board" }, "Syndicate board"), el("a", { class: "btn btn-ghost", href: "#/queue" }, "Open case queue"))),
      el("div", { class: "tiles" },
        tile(s.total, "Total cases", false), tile(s.awaiting, "Awaiting review", true),
        tile(s.linked_reports, "Cases with possible connections", true), tile(money(s.reported_loss), "Reported losses", false, spark(s.per_day))),
      el("div", { class: "grid-2" },
        el("section", { class: "panel" }, el("h3", null, "Case status"), bars(s.by_status, maxS, "status")),
        el("section", { class: "panel" }, el("h3", null, "By category"), bars(s.by_category, maxC))),
      el("div", { class: "spacer-16" }),
      el("div", { class: "grid-2" },
        el("section", { class: "panel" }, el("div", { class: "lead-top" }, el("h3", null, "Recent cases"), el("a", { href: "#/queue", class: "small" }, "View all →")),
          recent.items.length ? el("ul", { class: "list-plain" }, recent.items.map((r) => el("li", null,
            el("span", null, el("a", { href: "#/report/" + r.reference, class: "ref" }, r.reference), el("span", { class: "sub" }, `${r.scam_type_label || r.category_label} · ${r.town || "-"}`)),
            el("span", null, el("span", { class: "st st-" + r.status }, r.status_label), r.leads ? el("span", { class: "sub" }, `${r.leads} lead${r.leads > 1 ? "s" : ""}`) : null))))
            : el("p", { class: "muted" }, "No cases yet.")),
        el("section", { class: "panel" }, el("div", { class: "lead-top" }, el("h3", null, "Possible scam networks"), el("a", { href: "#/network", class: "small" }, "Explore →")),
          cl.length ? el("ul", { class: "list-plain" }, cl.slice(0, 5).map((c) => el("li", null,
            el("span", null, el("a", { href: "#/network/" + c.anchor }, `${c.size} linked reports`), el("span", { class: "sub" }, `${c.scam_type || "Mixed"} · ${c.stations} branch${c.stations > 1 ? "es" : ""} · ${c.restricted} restricted`)),
            el("span", { class: "lead-badge" }, money(c.visible_amount)))))
            : el("p", { class: "muted" }, "No linked reports yet."))),
    ]);
  }



  // ------------------------------------------------------------------ security alert centre (admin)
  async function showSecurity() {
    shell("security", el("div", { class: "empty" }, "Loading…"));
    let d;
    try { d = await api("GET", "/api/admin/security"); } catch (e) { shell("security", el("div", { class: "notice" }, e.message)); return; }
    const c = d.counts || {}, u = d.ai_usage || {};
    const sevTag = (s) => el("span", { class: "sev sev-" + s }, s);
    shell("security", [
      el("div", { class: "page-head" }, el("div", null, el("div", { class: "kicker" }, "Admin · OWASP A09:2025 security logging & alerting"),
        el("h1", null, "Security alerts"),
        el("p", null, "Alerts are derived from the hash-chained audit log, so they cannot be quietly deleted. Last 7 days."))),
      el("div", { class: "tiles tiles-5" },
        tile(d.audit_chain.intact ? "Intact" : "BROKEN", `Audit chain · ${d.audit_chain.checked} events verified`, !d.audit_chain.intact),
        tile((c.critical || 0) + (c.high || 0), "High / critical alerts", true),
        tile(c.medium || 0, "Medium alerts"),
        tile(`${u.last_hour || 0}/${u.max_per_hour || "-"}`, "AI reads this hour (cap)"),
        tile(u.metadata_stripped || 0, "Photos stripped of metadata before AI")),
      el("section", { class: "panel" }, el("h3", null, "Alerts"),
        d.alerts.length ? el("div", { class: "table-wrap" }, el("table", { class: "data" },
          el("thead", null, el("tr", null, ["Severity", "What happened", "Who / where", "When"].map((h) => el("th", { scope: "col" }, h)))),
          el("tbody", null, d.alerts.map((a) => el("tr", { class: "audit-row", onclick: () => { if (a.target.startsWith("report:")) location.hash = "#/report/" + a.target.slice(7); } },
            el("td", null, sevTag(a.severity)), el("td", null, el("b", null, a.title), el("span", { class: "sub" }, a.rule)),
            el("td", null, el("span", { class: "mono" }, a.actor), a.target ? el("span", { class: "sub" }, a.target) : null),
            el("td", null, dateTime(a.at)))))))
          : el("p", { class: "muted" }, "No security alerts in the last 7 days.")),
      el("section", { class: "panel" }, el("h3", null, "What raises an alert"), el("ul", { class: "checks" },
        el("li", null, "5+ failed sign-ins or two-factor codes for one user from one address within 10 minutes (password guessing); locked accounts"),
        el("li", null, "Bank API calls with an unknown bank, a bad or reused signature; beneficiary-check quota reached; unusual lookup volumes"),
        el("li", null, "Possible prompt injection found in submitted evidence (OWASP LLM01)"),
        el("li", null, "25+ evidence files or case packs opened by one user within 10 minutes (bulk access)"),
        el("li", null, "Any break in the audit log's hash chain (history changed): critical"))),
    ]);
  }

  // ------------------------------------------------------------------ syndicate jurisdiction board
  function leadWhy(syn) {
    const rest = Math.max(0, ...syn.jurisdictions.filter((j) => j.code !== syn.lead.code).map((j) => j.victims));
    return syn.lead.victims > rest
      ? `This branch holds the most victims (${syn.lead.victims}); first report there ${date(syn.lead.first)}.`
      : `Victims are spread evenly (${syn.lead.victims} per branch at most), so the branch with the earliest report (${date(syn.lead.first)}) leads.`;
  }

  async function showBoard(code) {
    shell("board", el("div", { class: "empty" }, "Loading…"));
    let d;
    try { d = await api("GET", "/api/police/intel/board"); } catch (e) { shell("board", el("div", { class: "notice" }, e.message)); return; }
    const syn = d.syndicates.find((x) => x.code === code) || d.syndicates[0] || null;
    const t = d.totals, plural = (n, w) => `${n} ${w}${n === 1 ? "" : "s"}`;
    const who = me.role === "admin" ? "UTB head office · national fraud view (demo)" : me.stations.map((x) => x.name).join(" · ");
    const list = el("div", { class: "syn-list", role: "list" }, d.syndicates.map((x) => el("button", {
      class: "syn-item" + (syn && x.code === syn.code ? " active" : ""), role: "listitem", onclick: () => { location.hash = "#/board/" + x.code; } },
      el("span", { class: "syn-code" }, x.code), el("b", null, x.label),
      el("span", { class: "sub" }, `${plural(x.victims, "victim")} · ${x.stations} branch${x.stations === 1 ? "" : "es"} · ${plural(x.provinces.length, "province")}`),
      x.total_amount !== null ? el("span", { class: "syn-amt" }, money(x.total_amount)) : el("span", { class: "syn-amt" }, `${x.your_victims} at your branch`))));
    const content = [
      el("div", { class: "page-head" }, el("div", null, el("div", { class: "kicker" }, who), el("h1", null, "Syndicate board"),
        el("p", null, "One syndicate, many branches. When reports at different branches share a mule account, phone number, website or message script, Ubufakazi joins them into one syndicate, so the bank can freeze the accounts while the money is still there and escalate one strong case to SAPS instead of many small ones."))),
      el("div", { class: "tiles tiles-5" },
        tile(t.syndicates, "Syndicates detected", true), tile(t.victims, "Victims linked"),
        tile(t.stations, "Branch regions involved"), tile(`${t.provinces}/9`, "Provinces affected"),
        t.amount !== null ? tile(money(t.amount), "Linked losses", true) : tile(d.syndicates.reduce((a, x) => a + x.your_victims, 0), "Linked victims at your branch", true)),
    ];
    if (!syn) {
      content.push(el("section", { class: "panel" }, el("p", { class: "muted" }, "No syndicates detected yet: no group of three or more linked reports.")));
    } else {
      const docketsTxt = `${plural(syn.stations, "separate fraud case")} at ${syn.stations} branch${syn.stations === 1 ? "" : "es"} in ${plural(syn.provinces.length, "province")}`;
      const others = syn.jurisdictions.filter((j) => j.code !== syn.lead.code).map((j) => j.code);
      const mulesTxt = syn.mules.map((m) => m.account).join(", ");
      const jt = el("table", { class: "data jtable" }, el("thead", null, el("tr", null, ["Province", "Branch (region)", "Where victims were scammed", "Victims", "Reported loss"].map((h, i) => el("th", { scope: "col", class: i > 2 ? "num" : null }, h)))),
        el("tbody", null, syn.jurisdictions.map((j) => el("tr", { class: (j.code === syn.lead.code ? "lead-row" : "") + (j.visible ? "" : " restricted"), tabindex: j.references.length ? "0" : null,
          onclick: j.references.length ? () => { location.hash = "#/report/" + j.references[j.references.length - 1]; } : null },
          el("td", null, j.province), el("td", null, el("b", null, j.station.replace("UTB · ", "")), el("span", { class: "sub" }, j.code + (j.code === syn.lead.code ? " · suggested lead" : "") + (j.own ? " · your branch" : ""))),
          el("td", null, j.visible ? j.towns.join(", ") : el("span", { class: "muted" }, "Restricted: another branch's region")),
          el("td", { class: "num" }, String(j.victims)), el("td", { class: "num" }, j.amount !== null ? money(j.amount) : "–")))));
      const mt = el("table", { class: "data" }, el("thead", null, el("tr", null, ["Mule account", "Bank", "Reports", "Payers warned", "Bank decision"].map((h, i) => el("th", { scope: "col", class: i === 2 || i === 3 ? "num" : null }, h)))),
        el("tbody", null, syn.mules.map((m) => el("tr", null, el("td", { class: "mono" }, m.account), el("td", null, m.bank || "Not stated", el("span", { class: "sub" }, plural(m.provinces.length, "province"))),
          el("td", { class: "num" }, String(m.reports)), el("td", { class: "num" }, String(m.warned || 0)),
          el("td", null, m.bank_status === "frozen" ? el("span", { class: "st st-frozen" }, "Frozen") : m.bank_connected
            ? el("span", { class: "st st-under_review" }, m.bank_status ? m.bank_status.replace(/_/g, " ") : "Alert sent")
            : el("span", { class: "st st-more_info_required" }, "Not connected: send manually"),
            m.bank_note ? el("span", { class: "sub" }, m.bank_note) : null)))));
      content.push(el("div", { class: "syn-grid" },
        el("aside", null, el("h3", { class: "side-h" }, "Detected syndicates"), list),
        el("div", null,
          el("section", { class: "panel syn-panel" },
            el("div", { class: "lead-top" }, el("div", null, el("div", { class: "kicker" }, `${syn.code} · ${date(syn.first)} – ${date(syn.last)}`),
              el("h2", null, syn.label), el("p", { class: "muted" }, "Linked by " + [syn.mules.length && plural(syn.mules.length, "receiving account"), syn.phones && plural(syn.phones, "phone number"), syn.websites && plural(syn.websites, "website"), syn.scripted && "a repeated message script"].filter(Boolean).join(", ").replace(/, ([^,]*)$/, " and $1") + ".")),
              syn.anchor ? el("a", { class: "btn btn-ghost btn-small", href: "#/network/" + syn.anchor }, "Open network graph") : null),
            el("div", { class: "versus" },
              el("div", { class: "vs-a" }, el("span", null, "Without Ubufakazi"), el("b", null, docketsTxt), el("small", null, "Each looks like a small, separate case.")),
              el("div", { class: "vs-b" }, el("span", null, "With Ubufakazi"), el("b", null, `1 linked investigation · ${plural(syn.victims, "victim")}`),
                el("small", null, syn.total_amount !== null ? `${money(syn.total_amount)} reported lost in total` : `${money(syn.your_amount)} reported at your branch`))),
            el("div", { class: "jmap-wrap" }, UBFBoard.map(d, syn))),
          el("section", { class: "panel" }, el("h3", null, "Branches holding pieces of this syndicate"), el("div", { class: "table-wrap" }, jt)),
          el("div", { class: "grid-2" },
            el("section", { class: "panel" }, el("h3", null, "Recommended actions"), el("ol", { class: "actions" },
              el("li", null, el("b", null, `${syn.lead.station.replace("UTB · ", "")} (${syn.lead.code}) leads. `), leadWhy(syn)),
              others.length ? el("li", null, el("b", null, "Merge the other branches' cases into one investigation: "), others.join(", ") + ".") : null,
              el("li", null, el("b", null, "Freeze the money trail: "), `block ${mulesTxt || "the receiving accounts"} (or alert the bank that holds them) while funds can still be stopped.`),
              syn.warned ? el("li", null, el("b", null, "Next victims already protected: "), `${syn.warned} customer${syn.warned === 1 ? " was" : "s were"} warned before paying into these accounts.`) : null,
              el("li", null, el("b", null, "Use the evidence as is: "), "every file is SHA-256 fingerprinted and independently timestamped; the sealed case pack goes with the bank's escalation to SAPS."))),
            el("section", { class: "panel" }, el("h3", null, "Mule accounts and bank decisions"), el("div", { class: "table-wrap" }, mt))))));
    }
    const nat = el("table", { class: "data" }, el("thead", null, el("tr", null, ["Province", "Branches", "Towns covered", "Reports", "Linked to a syndicate"].map((h, i) => el("th", { scope: "col", class: i > 0 ? "num" : null }, h)))),
      el("tbody", null, d.provinces.map((p) => el("tr", { class: "nat-row" },
        el("td", null, el("b", null, p.province), el("span", { class: "sub" }, p.stations.map((s) => `${s.code}: ${s.towns.join(", ")}`).join(" · "))),
        el("td", { class: "num" }, String(p.station_count)), el("td", { class: "num" }, String(p.towns)),
        el("td", { class: "num" }, String(p.reports)), el("td", { class: "num" }, String(p.linked))))));
    content.push(el("section", { class: "panel" }, el("h3", null, "Branches and regions in every province"),
      el("p", { class: "muted" }, "Each report goes to the fraud desk of the branch whose region covers the town where the victim was scammed. Counts include every report, so a branch can see how busy each region is."),
      el("div", { class: "table-wrap" }, nat)),
      el("p", { class: "foot-note" }, d.note));
    shell("board", content);
  }

  // ------------------------------------------------------------------ evidence inventory
  async function showEvidence() {
    const q = el("input", { type: "search", id: "ev-q", placeholder: "File name, SHA-256 or case reference" });
    const type = el("select", { id: "ev-type" }, [["", "All types"], ["image", "Images"], ["document", "PDF documents"], ["text", "Text / chat exports"], ["audio", "Audio"], ["video", "Video"]].map(([v, t]) => el("option", { value: v }, t)));
    const list = el("div", null, el("div", { class: "empty" }, "Loading…"));
    let page = 1;
    const load = async () => {
      let d;
      try { d = await api("GET", "/api/police/evidence?" + new URLSearchParams({ q: q.value, type: type.value, page, page_size: 30 })); }
      catch (e) { list.replaceChildren(el("div", { class: "empty" }, e.message)); return; }
      if (!d.items.length) { list.replaceChildren(el("div", { class: "empty" }, "No evidence files match. Seed records are synthetic and have no files: submit a report on /report to see evidence here.")); return; }
      const pages = Math.max(1, Math.ceil(d.total / d.page_size));
      list.replaceChildren(el("div", { class: "table-wrap" }, el("table", { class: "data" },
        el("thead", null, el("tr", null, ["File", "Case", "Type / size", "Received (server clock)", "SHA-256", "Processing"].map((h) => el("th", null, h)))),
        el("tbody", null, d.items.map((e) => el("tr", { tabindex: "0", onclick: () => { location.hash = `#/report/${e.reference}/evidence`; } },
          el("td", null, e.name, el("span", { class: "sub" }, "via " + e.channel)), el("td", null, el("span", { class: "ref" }, e.reference), el("span", { class: "sub" }, e.station.replace("UTB · ", ""))),
          el("td", null, e.type.toUpperCase(), el("span", { class: "sub" }, size(e.size))), el("td", null, dateTime(e.received_at)),
          el("td", { class: "hash" }, e.sha256.slice(0, 20) + "…"), el("td", null, e.processed.map((k) => el("span", { class: "tag" + (k === "not-processed" ? "" : " ok") }, k)))))))),
        el("div", { class: "pager" }, el("span", null, `${d.total} file${d.total === 1 ? "" : "s"} · page ${d.page} of ${pages}`),
          el("span", null, el("button", { class: "btn btn-ghost btn-small", disabled: d.page <= 1 ? true : null, onclick: () => { page--; load(); } }, "Previous"), " ",
            el("button", { class: "btn btn-ghost btn-small", disabled: d.page >= pages ? true : null, onclick: () => { page++; load(); } }, "Next"))));
    };
    let t; q.addEventListener("input", () => { clearTimeout(t); t = setTimeout(() => { page = 1; load(); }, 300); });
    type.addEventListener("change", () => { page = 1; load(); });
    shell("evidence", [
      el("div", { class: "page-head" }, el("div", null, el("div", { class: "kicker" }, "Evidence inventory"), el("h1", null, "Evidence & chain of custody"),
        el("p", null, "Every original file your branch holds, with the fingerprint recorded when it arrived. Open a file's case to verify it, preview it or download the original (each action is audited)."))),
      el("div", { class: "filters" }, el("div", { class: "field q" }, el("label", { for: "ev-q" }, "Search"), q), el("div", { class: "field" }, el("label", { for: "ev-type" }, "Type"), type)),
      list]);
    load();
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
    const stnOpts = [["", meta.stations.length > 1 ? "All my branches" : meta.stations[0]?.name || "Branch"], ...meta.stations.map((x) => [x.code, x.name.replace("UTB · ", "")])];
    const sortOpts = [["newest", "Newest first"], ["oldest", "Oldest first"], ["amount", "Largest loss"]];
    const linked = el("input", { type: "checkbox", id: "f-linked", checked: f.linked ? true : null });
    const filters = el("form", { class: "filters", role: "search" },
      el("div", { class: "field q" }, el("label", { for: "f-q" }, "Search"), q),
      sel("f-status", "Status", stOpts, f.status), sel("f-cat", "Category", catOpts, f.category),
      sel("f-stn", "Branch", stnOpts, f.station), sel("f-sort", "Sort", sortOpts, f.sort),
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
      el("div", { class: "page-head" }, el("div", null, el("div", { class: "kicker" }, me.role === "admin" ? "UTB head office · all branches" : me.stations.map((x) => x.name).join(" · ")),
        el("h1", null, "Report queue"), el("p", null, "Reports submitted through Telegram, WhatsApp and the web, prepared for your review."))),
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
          el("td", null, r.town || "-", el("span", { class: "sub" }, r.station.replace("UTB · ", ""))),
          el("td", { class: "num" }, r.amount_paid ? money(r.amount_paid) : "-"),
          el("td", null, r.leads ? el("span", { class: "lead-badge" + (r.corroborated ? "" : " single") }, `${r.leads} lead${r.leads > 1 ? "s" : ""}`) : el("span", { class: "muted small" }, "none")),
          el("td", null, el("span", { class: "st st-" + r.status }, r.status_label), r.processing_status !== "ready" ? el("span", { class: "sub" }, "processing: " + r.processing_status) : null),
          el("td", { class: "num" }, String(r.evidence_count)));
        return tr;
      });
      const pages = Math.max(1, Math.ceil(data.total / data.page_size));
      list.replaceChildren(
        el("div", { class: "table-wrap" }, el("table", { class: "data" },
          el("thead", null, el("tr", null, ["Reference", "Type / complainant", "Area / branch", "Paid", "Leads", "Status", "Files"].map((h) => el("th", { scope: "col" }, h)))),
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
    catch (e) { shell("queue", [backBtn(), el("div", { class: "empty" }, e.status === 404 ? "Report not found, or it belongs to another branch." : e.message)]); return; }

    const statusSel = el("select", { id: "st-sel", "aria-label": "New status" }, Object.entries(meta.statuses).filter(([k]) => k !== "registered_at_station" || k === r.status).map(([k, v]) => el("option", { value: k, selected: k === r.status ? true : null }, v)));
    const statusNote = el("input", { type: "text", id: "st-note", placeholder: "Note for the record (optional)", maxlength: "1000" });
    const statusBtn = el("button", { class: "btn btn-primary btn-small", onclick: async () => {
      try { await api("POST", `/api/police/reports/${r.reference}/status`, { status: statusSel.value, note: statusNote.value }); toast("Status updated and recorded in the audit log."); refreshMeta(); showReport(ref, tab); }
      catch (e) { toast(e.message, true); } } }, "Update status");

    const packBtn = el("button", { class: "btn btn-ghost btn-small", onclick: async () => {
      packBtn.disabled = true;
      try { download(await api("GET", `/api/police/reports/${r.reference}/pack`, undefined, { blob: true }), `Ubufakazi-${r.reference}-FRAUD-DESK.pdf`); toast("Fraud desk case pack downloaded (recorded in the audit log)."); }
      catch (e) { toast(e.message, true); } finally { packBtn.disabled = false; } } }, icon(I.pdf), "Fraud desk case pack");
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
    const srcLabel = (s) => s === "chat" ? "chat" : s === "description" ? "complainant" : s === "seed" ? "synthetic" : s.startsWith("evidence:") ? "file"
      : s.startsWith("ai:") ? "AI-read · unverified" : s.startsWith("flagged:") ? "⚠ injection flagged" : s;
    const groups = {};
    ids.forEach((i) => { (groups[i.kind] = groups[i.kind] || []).push(i); });
    const facts = el("dl", { class: "facts" },
      Object.entries(groups).map(([k, arr]) => [el("dt", null, kindLabel[k] || k),
        el("dd", null, arr.map((i) => el("span", { class: "chip" }, i.display + (i.bank ? " · " + i.bank : ""), el("span", { class: "src" }, srcLabel(i.source)))))]),
      f.suspect_alias ? [el("dt", null, "Name used"), el("dd", null, el("span", { class: "chip" }, f.suspect_alias))] : null,
      f.total_paid ? [el("dt", null, "Payments"), el("dd", null, (f.payments || [f.total_paid]).map((p) => el("span", { class: "chip" }, money(p))), el("b", null, " = " + money(f.total_paid)))] : null,
      f.total_requested ? [el("dt", null, "Requested"), el("dd", null, money(f.total_requested))] : null);
    const answers = Object.entries(r.answers || {}).filter(([, v]) => v);
    const sec = f.security || {};
    const inj = sec.prompt_injection || [];
    const aiPanel = inj.length ? el("section", { class: "panel ai-alert" },
        el("h3", null, "⚠ Possible prompt injection in the evidence"),
        el("p", null, "Text in this report looks written to steer an AI reader. Details from the affected file(s) are kept as leads for you, but they cannot send a bank alert or count in the bank beneficiary check on their own."),
        el("ul", { class: "inj-list" }, inj.map((x) => el("li", null, el("b", null, x.label), el("span", { class: "sub" }, `${x.file} · read by ${x.read_by}`), el("q", null, x.snippet)))),
        el("p", { class: "hint" }, "OWASP LLM01 (prompt injection) · LLM06 (excessive agency). Check the original file before relying on any detail."))
      : sec.untrusted_identifiers ? el("div", { class: "notice info" }, el("b", null, "AI-read details: "), `${sec.untrusted_identifiers} detail${sec.untrusted_identifiers === 1 ? " was" : "s were"} read only by the AI. They are shown as unverified and need confirmation before a bank is alerted.`) : null;
    const editPanel = (sec.edit_signs || []).length ? el("div", { class: "notice warn" }, el("b", null, "Payment slip may be edited: "),
      `${sec.edit_signs.join("; ")} show${sec.edit_signs.length === 1 ? "s" : ""} signs of editing in the file's metadata. Not proof: confirm the payment with the bank. Details are under Evidence → integrity-signals.`) : null;
    body.replaceChildren(...[aiPanel, editPanel].filter(Boolean), el("div", { class: "cols" },
      el("div", null,
        el("section", { class: "panel" }, el("h3", null, "The complainant's account"), el("div", { class: "quote" }, r.description),
          answers.length ? el("dl", { class: "facts" }, answers.map(([k, v]) => [el("dt", null, k.replace(/_/g, " ")), el("dd", null, String(v))])) : null,
          el("p", { class: "hint" }, `When (as stated): ${r.incident_when || "not given"} · Statement language: ${r.language}` + (r.location ? ` · Approximate location (${r.location.precision}): ${r.location.lat}, ${r.location.lon}` : ""))),
        el("section", { class: "panel" }, el("h3", null, "Extracted facts ", el("span", { class: "tag" }, "unverified")),
          ids.length || f.total_paid ? facts : el("p", { class: "muted" }, "Nothing extracted automatically."),
          el("p", { class: "hint" }, f.method || ""))),
      el("div", null,
        stationPanel(r),
        r.bank_responses && r.bank_responses.length ? el("section", { class: "panel" }, el("h3", null, "Bank response"),
          r.bank_responses.map((b) => el("div", { class: "bank-resp" }, el("div", null, el("span", { class: "mono" }, b.account), " · ", b.bank, " ", el("span", { class: "tag" }, "fictional bank")),
            el("p", null, el("span", { class: "st st-bank-" + b.status }, b.status_label)), b.note ? el("p", { class: "muted small" }, b.note) : null,
            el("p", { class: "hint" }, `Bank case ${b.case_ref || "-"} · ${dateTime(b.at)} · received over the signed bank API`)))) : null,
        el("section", { class: "panel" }, el("h3", null, "Processing"),
          el("p", null, el("span", { class: "st" }, r.processing_status)),
          r.processing_note ? el("div", { class: "notice warn" }, r.processing_note) : el("p", { class: "muted small" }, "All evidence processed with the documented rules."),
          r.consent ? el("p", { class: "hint" }, `Consent ${r.consent.version} given ${dateTime(r.consent.given_at)}.`) : null),
        el("section", { class: "panel" }, el("h3", null, "Possible connections"),
          r.leads.length ? [el("p", null, el("b", { class: "mono" }, String(r.leads.length)), ` other report${r.leads.length > 1 ? "s" : ""} share signals with this one (${r.leads.filter((l) => l.strength === "corroborated").length} corroborated, ${r.leads.filter((l) => !l.visible).length} at other branches).`),
            el("button", { class: "btn btn-ghost btn-small", onclick: () => { location.hash = `#/report/${r.reference}/leads`; } }, "Open leads & graph")]
            : el("p", { class: "muted" }, "No possible connections found.")),
        el("section", { class: "panel" }, el("h3", null, "Status history"),
          el("ul", { class: "steps-v" }, r.history.map((h) => el("li", { class: "done" }, el("b", null, h.to_label), el("div", { class: "muted small" }, `${dateTime(h.at)} · ${h.by}${h.note ? " · " + h.note : ""}`))))))));
  }

  function stationPanel(r) {
    const h = r.handover;
    const input = el("input", { type: "text", id: "cas-in", placeholder: "CAS 123/10/2026", maxlength: "40", autocomplete: "off", spellcheck: "false" });
    const err = el("p", { class: "err", role: "alert" });
    const save = el("button", { class: "btn btn-primary btn-small", onclick: async () => {
      err.textContent = ""; save.disabled = true;
      try { const v = await api("POST", `/api/police/reports/${r.reference}/cas`, { cas_number: input.value });
            toast(v.cas_number + " recorded. Status: " + v.status_label + "."); refreshMeta(); showReport(r.reference, "overview"); }
      catch (e) { err.textContent = e.message; } finally { save.disabled = false; } } }, "Record SAPS escalation");
    const form = el("div", { class: "stack" },
      el("div", { class: "field" }, el("label", { for: "cas-in" }, h && h.cas_number ? "Correct the CAS number" : "CAS number SAPS issued when the bank escalated"), input),
      err, el("div", { class: "row-btns" }, save),
      el("p", { class: "hint" }, "When the bank escalates this case to SAPS, type the CAS number exactly as SAPS issued it. Ubufakazi never creates CAS numbers and cannot check them with SAPS; it is shown as “entered by the bank”. The bank and branches are fictional."));
    return el("section", { class: "panel" }, el("h3", null, "Escalation to SAPS"),
      h ? el("dl", { class: "facts" },
        el("dt", null, "Handled by"), el("dd", null, h.station + (h.moved ? ` (moved from ${h.from_station})` : "")),
        el("dt", null, "Accepted by"), el("dd", null, `${h.accepted_by} · ${dateTime(h.accepted_at)}`),
        h.cas_number ? [el("dt", null, "CAS number"), el("dd", null, el("b", { class: "mono" }, h.cas_number), el("span", { class: "tag" }, "entered by the bank"),
          el("div", { class: "muted small" }, `${h.cas_recorded_by} · ${dateTime(h.cas_recorded_at)} · not verified with SAPS`))] : null)
        : el("p", { class: "muted" }, "Not yet escalated to SAPS. If the complainant visits a branch, scanning the QR code on their case pack opens the handover screen."),
      form);
  }

  // ------------------------------------------------------------------ station handover (QR on the complainant's case pack)
  async function showHandover(ref, token) {
    shell("queue", el("div", { class: "empty" }, "Checking the handover code…"));
    let h;
    try { h = await api("GET", `/api/police/handover/${ref}/${token}`); }
    catch (e) { shell("queue", [backBtn(), el("div", { class: "empty" }, e.message)]); return; }
    const sel = el("select", { id: "ho-st", "aria-label": "Accept at branch" }, h.my_stations.map((st) =>
      el("option", { value: String(st.id), selected: st.id === h.routed_station_id ? true : null }, st.name)));
    const btn = el("button", { class: "btn btn-primary", onclick: async () => {
      btn.disabled = true;
      try { await api("POST", `/api/police/handover/${ref}/${token}/accept`, { station_id: Number(sel.value) });
            toast("Case accepted at your branch. Recorded in the audit log."); refreshMeta(); location.hash = `#/report/${ref}/overview`; }
      catch (e) { toast(e.message, true); btn.disabled = false; } } }, "Accept case at this branch");
    shell("queue", [
      el("div", { class: "page-head" }, el("div", null, el("div", { class: "kicker" }, "Branch handover"),
        el("h1", null, h.reference),
        el("p", null, "The customer is showing you their Ubufakazi case pack. Check that this is their report, then accept it at your branch's fraud desk."))),
      el("div", { class: "cols" },
        el("section", { class: "panel" }, el("h3", null, "Check with the complainant"),
          el("dl", { class: "facts" },
            el("dt", null, "Name on statement"), el("dd", null, h.complainant_name || "(not given; ask for it)"),
            el("dt", null, "What happened"), el("dd", null, h.category_label),
            el("dt", null, "Area"), el("dd", null, [h.town, h.province].filter(Boolean).join(", ") || "-"),
            el("dt", null, "Reported"), el("dd", null, dateTime(h.received)),
            el("dt", null, "Evidence files"), el("dd", null, String(h.evidence_count)),
            el("dt", null, "Routed to"), el("dd", null, h.routed_station)),
          h.handover ? el("div", { class: "notice info" }, `Already accepted at ${h.handover.station} by ${h.handover.accepted_by} (${dateTime(h.handover.accepted_at)}).`) : null),
        el("section", { class: "panel" }, el("h3", null, "Accept the case"),
          el("div", { class: "field" }, el("label", { for: "ho-st" }, "Your branch"), sel),
          el("div", { class: "row-btns" }, btn),
          el("p", { class: "hint" }, "If the customer came to a different branch than the one Ubufakazi suggested, the case moves to yours and the move is written to the audit log. When the bank escalates the case to SAPS, record the CAS number on the report."),
          h.can_open ? el("a", { class: "btn btn-ghost btn-small", href: `#/report/${h.reference}/overview` }, "Open the report") : null))]);
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
      el("section", { class: "panel" }, el("h3", null, "Draft statement"), el("p", { class: "hint" }, "Prepared automatically from the report. The complainant must read, correct and sign it in front of a SAPS officer when the bank escalates."), sw, box,
        el("div", { class: "row-btns" }, el("button", { class: "btn btn-ghost btn-small", onclick: () => { navigator.clipboard.writeText(box.textContent).then(() => toast("Copied.")); } }, "Copy text"))),
      r.bank_report ? el("section", { class: "panel" }, el("h3", null, "Draft bank fraud report"), el("p", { class: "hint" }, "For the complainant to send to their own bank. Ubufakazi does not contact banks."),
        el("div", { class: "quote mono small" }, r.bank_report)) : el("section", { class: "panel" }, el("h3", null, "Bank report"), el("p", { class: "muted" }, "Not applicable to this report."))));
  }

  function evidence(r, body) {
    if (!r.evidence.length) { body.replaceChildren(el("div", { class: "empty" }, r.is_seed ? "Synthetic seed record: no evidence files." : "No files were attached.")); return; }
    body.replaceChildren(el("div", { class: "notice info" }, "Originals are stored exactly as received and never modified. Their SHA-256 was calculated by the server on arrival and, when configured, timestamped by an independent authority (RFC 3161). Use Verify to re-hash the stored file now. Every download and verification is written to the audit log."),
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
          : el("div", { class: "verify-bad" }, "✗ MISMATCH: stored file differs from the hash recorded at receipt. Do not rely on it; escalate."),
          v.timestamp_note ? el("div", { class: v.timestamp_ok ? "verify-ok" : "verify-bad" }, (v.timestamp_ok ? "✓ " : "✗ ") + v.timestamp_note) : null);
      } catch (ex) { toast(ex.message, true); } finally { verify.disabled = false; }
    } }, icon(I.check), "Verify");
    const dl = el("button", { class: "btn btn-ghost btn-small", onclick: async () => {
      try { download(await api("GET", `/api/police/evidence/${e.id}/download`, undefined, { blob: true }), `${r.reference}-${e.id}-${e.name}`); }
      catch (ex) { toast(ex.message, true); } } }, icon(I.dl), "Original");
    const tsr = e.timestamp ? el("button", { class: "btn btn-ghost btn-small", title: "RFC 3161 token for independent checking (openssl ts -verify)", onclick: async () => {
      try { download(await api("GET", `/api/police/evidence/${e.id}/timestamp`, undefined, { blob: true }), `${r.reference}-${e.id}.tsr`); }
      catch (ex) { toast(ex.message, true); } } }, icon(I.dl), "Timestamp token") : null;
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
        el("div", { class: "row" }, el("span", null, e.type.toUpperCase() + " · " + size(e.size)), el("span", null, "received " + dateTime(e.received_at) + " (server clock)"),
          e.timestamp ? el("span", { class: "ts-ok", title: "RFC 3161 trusted timestamp by " + e.timestamp.tsa }, "✓ trusted timestamp " + dateTime(e.timestamp.gen_time)) : null, el("span", null, "via " + e.channel),
          e.declared_mime ? el("span", null, "declared " + e.declared_mime) : null),
        el("div", { class: "hash", title: "SHA-256" }, e.sha256), result, ders),
      el("div", { class: "btns" }, verify, dl, tsr));
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
    const list = r.leads.length ? r.leads.map((L) => el("article", { class: `lead ${L.strength}${L.visible ? "" : " restricted"}` },
      el("div", { class: "lead-top" },
        L.visible ? el("a", { class: "ref", href: "#/report/" + L.reference + "/leads" }, L.reference)
                  : el("span", null, el("b", null, "Restricted report"), " ", el("span", { class: "muted small" }, "· request access through your branch fraud manager")),
        el("span", { class: "lead-badge" + (L.strength === "corroborated" ? "" : " single") }, L.strength === "corroborated" ? "Corroborated lead" : "Single-signal lead")),
      el("div", { class: "muted small" }, L.station + (L.visible ? ` · ${date(L.date)} · ${money(L.amount_paid)} · ${L.status_label}` : "")),
      el("ul", null, L.signals.map((s) => el("li", null, s.reason, ...(s.conflicts || []).map((c) => el("div", { class: "conflict" }, "Conflict: " + c)))))))
      : [el("div", { class: "empty" }, "No possible connections.")];
    const work = el("div");
    body.replaceChildren(
      el("div", { class: "notice info" }, el("b", null, "How to read this. "), "A lead means another report shares an identifier or message template with this one. One kind of shared signal = single lead; two or more kinds = corroborated. Shared accounts can belong to money mules, so a lead is a reason to investigate, never proof of who is responsible."),
      el("section", { class: "panel" }, el("h3", null, "Investigation graph"), work),
      el("section", { class: "panel" }, el("h3", null, `Leads (${r.leads.length})`), list));
    graphWorkspace(work, r.reference, { onOpen: (ref) => { location.hash = "#/report/" + ref + "/leads"; } });
  }

  function notes(r, body) {
    const ta = el("textarea", { id: "note-body", rows: "3", maxlength: "4000", placeholder: "Add a case note (visible to investigators at this branch)" });
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

  // ------------------------------------------------------------------ scam network
  function nodePanel(panel, n, nbrs, edges) {
    const put = (...k) => panel.replaceChildren(...k.filter((x) => x !== null && x !== undefined && x !== false));
    if (!n) { put(el("div", { class: "kicker" }, "Details"), el("p", { class: "muted" }, "Select a node to see what it is and why it is connected. Double-click a report from your branch to open it."),
      el("p", { class: "hint" }, "A connection means a shared signal, not proof. Accounts can belong to money mules and numbers can be spoofed.")); return; }
    if (n.type === "report") {
      const sigs = nbrs.filter((x) => x.type !== "report").map((x) => `${UBFGraph.KIND[x.type]}: ${x.label}`);
      const scripts = edges.filter((e) => e.kind === "script").length;
      put(el("div", { class: "kicker" }, n.visible ? "Report" : "Restricted report"),
        el("h4", null, n.visible ? n.label : "Held by " + n.station),
        n.visible ? el("dl", { class: "facts" }, el("dt", null, "Branch"), el("dd", null, n.station), el("dt", null, "Type"), el("dd", null, n.scam_type || "-"),
          el("dt", null, "Paid"), el("dd", null, money(n.amount)), el("dt", null, "Date"), el("dd", null, date(n.date)), el("dt", null, "Status"), el("dd", null, n.status))
          : el("p", { class: "muted small" }, "You can see that this report exists and how it connects, but not its details. Request access through your branch fraud manager."),
        el("h4", null, "Connected by"),
        sigs.length || scripts ? el("ul", null, sigs.map((x) => el("li", null, x)), scripts ? el("li", null, `Similar message template (${scripts} report${scripts > 1 ? "s" : ""})`) : null) : el("p", { class: "muted small" }, "No visible signals."),
        n.visible && !n.focus ? el("a", { class: "btn btn-primary btn-small", href: "#/report/" + n.label }, "Open case") : null,
        n.visible ? el("a", { class: "btn btn-ghost btn-small", href: "#/report/" + n.label + "/leads" }, "Leads for this case") : null);
    } else {
      const reps = nbrs.filter((x) => x.type === "report");
      const vis = reps.filter((x) => x.visible), res = reps.length - vis.length;
      put(el("div", { class: "kicker" }, UBFGraph.KIND[n.type] || n.type), el("h4", { class: "mono" }, n.label),
        el("p", { class: "muted small" }, `Appears in ${reps.length} reports${res ? ` (${res} at other branches)` : ""}. Compared by a keyed hash: the raw value is shown only because a report you may see contains it.`),
        el("ul", null, vis.map((r) => el("li", null, el("a", { href: "#/report/" + r.label }, r.label), ` · ${money(r.amount)}`)), res ? el("li", { class: "muted" }, `${res} restricted report${res > 1 ? "s" : ""}`) : null),
        n.type === "account" ? el("p", { class: "hint" }, "A shared receiving account is the strongest signal, but the holder may be a money mule rather than the organiser.") : null);
    }
  }

  async function graphWorkspace(container, reference, { onOpen } = {}) {
    const gbox = el("div", { class: "graph-box" }, el("div", { class: "empty" }, "Building graph…"));
    const panel = el("aside", { class: "node-panel", "aria-live": "polite" });
    const summary = el("div", { class: "graph-summary" });
    const filters = el("div");
    container.replaceChildren(summary, filters, el("div", { class: "graph-layout" }, gbox, panel),
      el("p", { class: "hint" }, "Drag nodes, scroll to zoom, click to see details. Reports at other branches stay restricted."));
    nodePanel(panel, null);
    try {
      const g = await api("GET", `/api/police/reports/${reference}/graph`);
      const s = g.summary;
      summary.replaceChildren(el("span", null, el("b", null, String(s.reports)), " reports linked"), el("span", null, el("b", null, String(s.visible)), " visible to you"),
        el("span", null, el("b", null, String(s.restricted)), " restricted"), el("span", null, el("b", null, String(s.stations)), " branches"),
        el("span", null, el("b", null, money(s.visible_amount)), " reported loss (visible)"), ...(g.truncated ? [el("span", null, "(showing the closest 60)")] : []));
      if (s.reports < 2) { gbox.replaceChildren(el("div", { class: "empty" }, "This report has no possible connections yet.")); return; }
      requestAnimationFrame(() => {
        const ctrl = UBFGraph.render(gbox, g, { onOpen: onOpen || ((ref) => { location.hash = "#/report/" + ref; }), onSelect: (n, nb, ed) => nodePanel(panel, n, nb, ed) });
        filters.replaceChildren(UBFGraph.filterBar(ctrl));
      });
    } catch (e) { gbox.replaceChildren(el("div", { class: "empty" }, e.message)); }
  }

  async function showNetwork(anchor) {
    shell("network", el("div", { class: "empty" }, "Loading…"));
    let cl;
    try { cl = await api("GET", "/api/police/intel/clusters"); } catch (e) { shell("network", el("div", { class: "empty" }, e.message)); return; }
    const kindLabel = { account: "acc", phone: "tel", domain: "web", social: "social", email: "email", username: "user", payment_ref: "ref" };
    const current = anchor || (cl[0] && cl[0].anchor);
    const work = el("section", { class: "panel" });
    shell("network", [
      el("div", { class: "page-head" }, el("div", null, el("div", { class: "kicker" }, "Scam fingerprint network"), el("h1", null, "Possible scam networks"),
        el("p", null, "Groups of reports linked by shared bank accounts, phone numbers, websites or message templates. Each group includes at least one report from your branch."))),
      el("div", { class: "notice info" }, el("b", null, "Investigative leads only. "), "Solid red lines: shared bank account. Amber: shared phone. Violet: website or other identifier. Dashed violet: similar message template. A grey dashed ring is a report at another branch (restricted)."),
      el("div", { class: "spacer-16" }),
      cl.length ? el("div", { class: "clusters" }, cl.map((c) => el("button", { class: "cluster" + (c.anchor === current ? " active" : ""), onclick: () => { location.hash = "#/network/" + c.anchor; } },
        el("div", { class: "lead-top" }, el("span", { class: "big" }, String(c.size)), el("span", { class: "muted small" }, `${c.stations} branch${c.stations > 1 ? "es" : ""} · ${c.provinces.length} province${c.provinces.length > 1 ? "s" : ""}`)),
        el("div", null, el("b", null, c.scam_type || "Mixed"), el("span", { class: "muted" }, ` · ${date(c.first)} → ${date(c.last)}`)),
        el("div", { class: "muted small" }, `${c.visible} visible to you · ${c.restricted} restricted · ${money(c.visible_amount)} reported loss (visible)`),
        el("div", { class: "chips" }, c.shared.map((s) => el("span", { class: "chip" }, `${kindLabel[s.kind] || s.kind} ${s.display}`, el("span", { class: "src" }, `×${s.reports}`)))))))
        : el("div", { class: "empty" }, "No linked reports yet."),
      el("div", { class: "spacer-16" }),
      current ? work : null]);
    if (current) {
      work.append(el("div", { class: "lead-top" }, el("h3", null, "Network around " + current), el("a", { class: "btn btn-ghost btn-small", href: "#/report/" + current }, "Open anchor case")), el("div"));
      graphWorkspace(work.lastChild, current);
    }
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
      el("p", { class: "legend" }, el("span", { class: "dot on" }), " Working now  ", el("span", { class: "dot off" }), " Not connected. For SAPS and real banks this is deliberate: Ubufakazi never pretends to be linked to them."),
      row("Telegram bot", i.telegram.running, i.telegram.note),
      row("WhatsApp", i.whatsapp.running, i.whatsapp.note),
      row("AI reading of images, voice notes and scans", i.ai_media_reading.configured, i.ai_media_reading.note),
      row("Trusted timestamps (RFC 3161)", i.trusted_timestamps.configured, i.trusted_timestamps.note),
      row("Branch handover (QR) + SAPS escalation (CAS number)", i.station_handover.working, i.station_handover.note),
      row("Bank link: Ubuntu Trust Bank (fictional)", i.bank_link.connected, i.bank_link.note),
      row("SAPS systems", i.saps.connected, i.saps.note),
      row("Real banks", i.banks.connected, i.banks.note),
      row("Database", true, i.database === "sqlite" ? "SQLite (local demo). Set DATABASE_URL for Postgres/Supabase." : "PostgreSQL"));
  }

  boot();
})();
