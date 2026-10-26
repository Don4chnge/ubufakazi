/* DemoBank fraud-review simulation. Fictional bank; shows only what a bank needs: no victim names or statements. */
"use strict";

(() => {
  const { el, api, toast, money, date } = UBF;
  const root = document.getElementById("root");
  let me = null, data = null, selected = null;

  async function boot() {
    me = await UBF.session();
    if (!me || !["admin", "bank_reviewer"].includes(me.role)) {
      if (me) { root.replaceChildren(el("div", { class: "public" }, el("div", { class: "notice" }, "This account cannot open the bank simulation. ", el("a", { href: "/police" }, "Open the police console")))); return; }
      UBF.loginForm(root, { title: "DemoBank fraud review", subtitle: "Fictional bank simulation. Reviewers see accounts at their own bank only, never victims' details.",
        onDone: (m) => { me = m; start(); } });
      return;
    }
    start();
  }

  async function start() {
    const who = document.getElementById("who");
    who.replaceChildren(el("b", null, me.display_name), el("span", null, me.role === "admin" ? "Admin view" : "DemoBank reviewer"));
    who.hidden = false;
    const lo = document.getElementById("logout"); lo.hidden = false; lo.onclick = UBF.logout;
    await load();
  }

  async function load() {
    try { data = await api("GET", "/api/bank/alerts"); } catch (e) { toast(e.message, true); return; }
    render();
  }

  function render() {
    const items = data.items;
    const high = items.filter((i) => i.priority === "high").length;
    const total = items.reduce((s, i) => s + i.total_reported, 0);
    const detail = el("div", { id: "detail" }, el("section", { class: "panel" }, el("h3", null, "Select an account"), el("p", { class: "muted" }, "Choose an alert to see the pattern of reports against it.")));
    const rows = items.map((a) => {
      const tr = el("tr", { class: "alert-row" + (selected === a.id ? " sel" : ""), tabindex: "0", onclick: () => pick(a.id, tr), onkeydown: (e) => { if (e.key === "Enter") pick(a.id, tr); } },
        el("td", null, el("span", { class: "mono" }, a.account), el("span", { class: "sub" }, a.bank_stated)),
        el("td", { class: "num" }, String(a.reports)), el("td", { class: "num" }, money(a.total_reported)),
        el("td", null, date(a.last_reported), el("span", { class: "sub" }, "first " + date(a.first_reported))),
        el("td", null, el("span", { class: "prio prio-" + a.priority }, a.priority)),
        el("td", null, el("span", { class: "st" }, a.status_label)));
      return tr;
    });
    root.replaceChildren(el("main", { class: "main" },
      el("div", { class: "page-head" }, el("div", null, el("div", { class: "kicker" }, data.bank), el("h1", null, "Accounts reported in scams"),
        el("p", null, "Receiving accounts named in Ubufakazi reports, ranked by how many separate reports name them."))),
      el("div", { class: "notice warn" }, el("b", null, "Simulation. "), data.notice + " Accounts are masked; a bank would match them in its own systems."),
      el("div", { class: "tiles" }, tile(items.length, "Accounts flagged"), tile(high, "High priority (5+ reports)", true), tile(money(total), "Total reported paid in"),
        tile(items.filter((i) => i.status === "new").length, "Not yet reviewed")),
      el("div", { class: "bank-grid" },
        items.length ? el("div", { class: "table-wrap" }, el("table", { class: "data" },
          el("thead", null, el("tr", null, ["Account", "Reports", "Reported paid", "Last report", "Priority", "Review status"].map((h) => el("th", { scope: "col" }, h)))),
          el("tbody", null, rows))) : el("div", { class: "empty" }, "No accounts flagged."),
        detail)));
    if (selected) pick(selected);
  }

  function tile(v, label, alert) { return el("div", { class: "tile" + (alert ? " alert" : "") }, el("b", null, String(v)), el("span", null, label)); }

  async function pick(id, tr) {
    selected = id;
    document.querySelectorAll(".alert-row").forEach((r) => r.classList.remove("sel"));
    if (tr) tr.classList.add("sel");
    let a;
    try { a = await api("GET", "/api/bank/alerts/" + id); } catch (e) { toast(e.message, true); return; }
    const max = Math.max(...a.reports_list.map((r) => r.amount || 0), 1);
    const act = (status, label, cls) => el("button", { class: "btn btn-small " + (cls || "btn-ghost"), disabled: a.status === status ? true : null, onclick: async () => {
      try { await api("POST", `/api/bank/alerts/${id}/status`, { status }); toast("Recorded (simulation only, no account was touched)."); await load(); }
      catch (e) { toast(e.message, true); } } }, label);
    document.getElementById("detail").replaceChildren(el("section", { class: "panel" },
      el("div", { class: "kicker" }, "Receiving account · " + a.bank_stated),
      el("div", { class: "acct" }, a.account),
      el("p", { class: "muted", style: null }, `${a.reports} separate reports · ${money(a.total_reported)} · ${a.provinces} province${a.provinces === 1 ? "" : "s"} · ${a.scam_types.join(", ") || "type not stated"}`),
      a.corroborated_links ? el("div", { class: "notice info" }, `${a.corroborated_links} pairs of these reports are also linked by other signals (same phone numbers, websites or message templates). This suggests organised use of the account, possibly by a money mule.`) : null,
      el("h3", null, "Reports over time"),
      el("div", { class: "bars" }, a.reports_list.map((r) => {
        const fill = el("div", { class: "fill" }); fill.style.width = Math.max(3, (r.amount || 0) / max * 100) + "%";
        return el("div", { class: "bar" }, el("span", { class: "mono" }, date(r.date)), el("div", { class: "track", title: r.scam_type + ", " + r.province }, fill), el("span", { class: "amt" }, money(r.amount)));
      })),
      el("p", { class: "hint" }, "No complainant names, references, statements or contact details are shared with the bank."),
      el("h3", null, "Review (simulated)"),
      el("p", null, el("span", { class: "st" }, a.status_label)),
      el("div", { class: "sim-actions" }, act("under_review", "Start review"), act("escalated", "Escalate to fraud team", "btn-danger"), act("reviewed", "Mark reviewed"), act("new", "Reset")),
      el("p", { class: "hint" }, "These buttons only change this demo's record and are written to the audit log. They do not freeze, block or contact any account.")));
  }

  boot();
})();
