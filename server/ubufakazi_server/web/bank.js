/* Ubuntu Trust Bank fraud operations (a FICTIONAL bank). Alerts arrive from Ubufakazi over a signed API; every
   decision here is sent back to Ubufakazi. The bank never sees victims' names, statements or report references. */
"use strict";

(() => {
  const { el, api, toast, money, date, dateTime } = UBF;
  const root = document.getElementById("root");
  let me = null, data = null, selected = null;
  const ACTION_LABEL = { investigate: "Start investigation", freeze: "Freeze account", release: "Lift freeze", close: "Close case" };
  const ACTION_CLASS = { freeze: "btn-danger", investigate: "btn-primary" };

  async function boot() {
    me = await UBF.session();
    if (!me || !["admin", "bank_reviewer"].includes(me.role)) {
      if (me) { root.replaceChildren(el("div", { class: "public" }, el("div", { class: "notice" }, "This account cannot open the bank console. ", el("a", { href: "/police" }, "Open the police console")))); return; }
      UBF.loginForm(root, { title: "Ubuntu Trust Bank · Fraud operations", subtitle: "Fictional bank. Fraud analysts see alerts about accounts held at this bank, never victims' details.",
        onDone: (m) => { me = m; start(); } });
      return;
    }
    start();
  }

  async function start() {
    const who = document.getElementById("who");
    who.replaceChildren(el("b", null, me.display_name), el("span", null, me.role === "admin" ? "Admin view" : "Fraud operations"));
    who.hidden = false;
    const lo = document.getElementById("logout"); lo.hidden = false; lo.onclick = UBF.logout;
    await load();
  }

  async function load() {
    try { data = await api("GET", "/api/utb/cases"); } catch (e) { toast(e.message, true); return; }
    render();
  }

  function tile(v, label, alert) { return el("div", { class: "tile" + (alert ? " alert" : "") }, el("b", null, String(v)), el("span", null, label)); }

  function render() {
    const items = data.items;
    const open = items.filter((i) => ["received", "investigating"].includes(i.status)).length;
    const frozen = items.filter((i) => i.status === "frozen").length;
    const total = items.filter((i) => i.matched).reduce((s, i) => s + i.total_reported, 0);
    const detail = el("div", { id: "detail" }, el("section", { class: "panel" }, el("h3", null, "Select a case"), el("p", { class: "muted" }, "Choose an alert to see the reports against the account and act on it.")));
    const rows = items.map((a) => {
      const tr = el("tr", { class: "alert-row" + (selected === a.id ? " sel" : ""), tabindex: "0", onclick: () => pick(a.id, tr), onkeydown: (e) => { if (e.key === "Enter") pick(a.id, tr); } },
        el("td", null, el("span", { class: "mono" }, a.account), el("span", { class: "sub" }, a.case_ref)),
        el("td", { class: "num" }, String(a.reports)), el("td", { class: "num" }, money(a.total_reported)),
        el("td", null, date(a.last_report), el("span", { class: "sub" }, "first " + date(a.first_report))),
        el("td", null, el("span", { class: "prio prio-" + a.priority }, a.priority)),
        el("td", null, el("span", { class: "st st-utb-" + a.status }, a.status_label)));
      return tr;
    });
    root.replaceChildren(el("main", { class: "main" },
      el("div", { class: "page-head" }, el("div", null, el("div", { class: "kicker" }, data.bank + " · fraud operations"), el("h1", null, "Fraud alerts from Ubufakazi"),
        el("p", null, "Accounts at this bank named in scam reports. Alerts arrive over Ubufakazi's signed API; each decision is reported back."))),
      el("div", { class: "notice warn" }, el("b", null, "Fictional bank. "), data.notice),
      el("div", { class: "tiles" }, tile(items.length, "Alerts received"), tile(open, "Open (new or investigating)", true), tile(frozen, "Accounts frozen"), tile(money(total), "Reported paid into our accounts")),
      el("div", { class: "bank-grid" },
        items.length ? el("div", { class: "table-wrap" }, el("table", { class: "data" },
          el("thead", null, el("tr", null, ["Account", "Reports", "Reported paid", "Last report", "Priority", "Case status"].map((h) => el("th", { scope: "col" }, h)))),
          el("tbody", null, rows))) : el("div", { class: "empty" }, "No alerts yet. They appear when Ubufakazi processes a report naming an Ubuntu Trust Bank account."),
        detail)));
    if (selected) pick(selected);
  }

  async function pick(id, tr) {
    selected = id;
    document.querySelectorAll(".alert-row").forEach((r) => r.classList.remove("sel"));
    if (tr) tr.classList.add("sel");
    let a;
    try { a = await api("GET", "/api/utb/cases/" + id); } catch (e) { toast(e.message, true); return; }
    const max = Math.max(...a.timeline.map((r) => r.amount || 0), 1);
    const btn = (action) => el("button", { class: "btn btn-small " + (ACTION_CLASS[action] || "btn-ghost"), onclick: async (ev) => {
      ev.currentTarget.disabled = true;
      try { const r = await api("POST", `/api/utb/cases/${id}/action`, { action }); toast(r.status_label + ". Ubufakazi has been notified."); await load(); }
      catch (e) { toast(e.message, true); } } }, ACTION_LABEL[action]);
    const ad = a.account_detail;
    document.getElementById("detail").replaceChildren(el("section", { class: "panel" },
      el("div", { class: "kicker" }, a.case_ref + " · " + a.status_label),
      el("div", { class: "acct" }, a.account),
      ad ? el("dl", { class: "facts" },
        el("dt", null, "Customer"), el("dd", null, ad.customer_ref + " · " + ad.product),
        el("dt", null, "Balance"), el("dd", null, money(ad.balance)),
        el("dt", null, "Account status"), el("dd", null, el("span", { class: "st st-utb-acct-" + ad.status }, ad.status === "frozen" ? "Frozen" : "Active")))
        : el("div", { class: "notice info" }, "No Ubuntu Trust Bank account has this number. Ubufakazi was told automatically."),
      el("p", { class: "muted" }, `${a.reports} separate report${a.reports === 1 ? "" : "s"} · ${money(a.total_reported)} · ${a.provinces.length} province${a.provinces.length === 1 ? "" : "s"} · ${a.scam_types.join(", ") || "type not stated"}`),
      a.corroborated_links ? el("div", { class: "notice info" }, `${a.corroborated_links} pairs of these reports are also linked by other signals (same phone numbers, websites or message templates), which suggests organised use of the account, possibly by a money mule.`) : null,
      el("h3", null, "Payments reported into this account"),
      el("div", { class: "bars" }, a.timeline.map((r) => {
        const fill = el("div", { class: "fill" }); fill.style.width = Math.max(3, (r.amount || 0) / max * 100) + "%";
        return el("div", { class: "bar" }, el("span", { class: "mono" }, date(r.date)), el("div", { class: "track" }, fill), el("span", { class: "amt" }, money(r.amount)));
      })),
      el("p", { class: "hint" }, "Ubufakazi never sends victims' names, phone numbers, statements or report references."),
      a.actions.length ? [el("h3", null, "Decision"), el("div", { class: "sim-actions" }, a.actions.map(btn)),
        el("p", { class: "hint" }, "Each decision is applied in this fictional bank's records and sent back to Ubufakazi over the signed API, where the investigating officer and the victim can see it.")] : null,
      el("h3", null, "Case history"),
      el("ol", { class: "steps-v" }, a.events.map((e) => el("li", { class: "done" }, el("b", null, e.action.replace(/[._]/g, " ")), el("div", { class: "muted small" }, `${dateTime(e.at)} · ${e.by}${e.note ? " · " + e.note : ""}`))))));
  }

  boot();
})();
