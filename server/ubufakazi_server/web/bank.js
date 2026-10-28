/* Ubuntu Trust Bank fraud operations (a FICTIONAL bank). Alerts arrive from Ubufakazi over a signed API; every
   decision here is sent back to Ubufakazi. The bank never sees victims' names, statements or report references. */
"use strict";

(() => {
  const { el, api, toast, money, date, dateTime } = UBF;
  const root = document.getElementById("root");
  let me = null, data = null, selected = null, view = "alerts";
  const ACTION_LABEL = { investigate: "Start investigation", freeze: "Block account (freeze)", release: "Unblock account", close: "Close case" };
  const ACTION_CLASS = { freeze: "btn-danger", investigate: "btn-primary" };

  async function boot() {
    me = await UBF.session();
    if (!me || !["admin", "bank_reviewer"].includes(me.role)) {
      if (me) { root.replaceChildren(el("div", { class: "public" }, el("div", { class: "notice" }, "This account cannot open the bank console. ", el("a", { href: "/fraud-desk" }, "Open the branch fraud desk")))); return; }
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
    const tabs = el("div", { class: "bank-tabs", role: "tablist" },
      el("button", { role: "tab", "aria-selected": view === "alerts" ? "true" : "false", onclick: () => { view = "alerts"; render(); } }, "Fraud alerts from Ubufakazi"),
      el("button", { role: "tab", "aria-selected": view === "pay" ? "true" : "false", onclick: () => { view = "pay"; render(); } }, "Customer payment check"));
    if (view === "pay") { root.replaceChildren(el("main", { class: "main" }, tabs, payView())); return; }
    root.replaceChildren(el("main", { class: "main" }, tabs,
      el("div", { class: "page-head" }, el("div", null, el("div", { class: "kicker" }, data.bank + " · fraud operations"), el("h1", null, "Fraud alerts from Ubufakazi"),
        el("p", null, "Scam victims report to Ubufakazi, which routes each report to the fraud desk of the branch for their area and links reports into syndicates. When their reports say they paid into an account held at this bank, Ubufakazi sends this alert so the fraud team can block the account before the money moves on. Each decision is reported back to the branch fraud desk and the victim.")),
        el("a", { class: "plan-pill", href: "/banks#plans", title: "Ubufakazi subscription plans for banks" }, el("span", null, "Subscription"), el("b", null, "Bank plan · demo"))),
      el("ol", { class: "how-strip" },
        el("li", null, el("b", null, "1"), "Victims report scams via Ubufakazi"),
        el("li", null, el("b", null, "2"), "Reports naming the same account are linked"),
        el("li", null, el("b", null, "3"), "Signed alert arrives here (no victim names)"),
        el("li", null, el("b", null, "4"), "You block the account and escalate to SAPS")),
      el("div", { class: "notice warn" }, el("b", null, "Fictional bank. "), data.notice),
      el("div", { class: "tiles" }, tile(items.length, "Alerts received"), tile(open, "Open (new or investigating)", true), tile(frozen, "Accounts frozen"), tile(money(total), "Reported paid into our accounts")),
      el("div", { class: "bank-grid" },
        items.length ? el("div", { class: "table-wrap" }, el("table", { class: "data" },
          el("thead", null, el("tr", null, ["Account", "Reports", "Reported paid", "Last report", "Priority", "Case status"].map((h) => el("th", { scope: "col" }, h)))),
          el("tbody", null, rows))) : el("div", { class: "empty" }, data.syncing ? "Receiving alerts from Ubufakazi… this page refreshes in a few seconds." : "No alerts yet. They appear when Ubufakazi processes a report naming an Ubuntu Trust Bank account."),
        detail)));
    if (selected) pick(selected);
    if (data.syncing) setTimeout(load, 5000);
  }


  // ------------------------------------------------------------------ customer payment check (beneficiary check)
  const SAMPLES = [["Fake-job syndicate account", "1047228359"], ["OTP-fraud mule account", "6230441802"], ["Account nobody reported", "4105529930"]];
  function payView() {
    const num = el("input", { id: "pnum", inputmode: "numeric", autocomplete: "off", placeholder: "e.g. 1047228359", maxlength: "16" });
    const amt = el("input", { id: "pamt", inputmode: "decimal", autocomplete: "off", placeholder: "R 0.00" });
    const who = el("input", { id: "pname", autocomplete: "off", placeholder: "e.g. Mzansi Retail HR" });
    const screen = el("div", { class: "phone-screen" });
    const form = el("form", { class: "pay-form", onsubmit: async (ev) => {
      ev.preventDefault();
      const btn = form.querySelector("button[type=submit]"); btn.disabled = true; btn.textContent = "Checking with Ubufakazi…";
      try {
        const r = await api("POST", "/api/utb/payment-check", { account_number: num.value, amount: amt.value.replace(/[^0-9.]/g, "") || null });
        showResult(r, who.value || "this beneficiary", amt.value);
      } catch (e) { toast(e.message, true); }
      btn.disabled = false; btn.textContent = "Continue";
    } },
      el("label", { for: "pname" }, "Beneficiary name"), who,
      el("label", { for: "pnum" }, "Account number"), num,
      el("label", { for: "pamt" }, "Amount"), amt,
      el("button", { class: "btn btn-primary", type: "submit" }, "Continue"),
      el("div", { class: "chips" }, el("span", null, "Try:"), SAMPLES.map(([l, n]) => el("button", { type: "button", class: "chip", onclick: () => { num.value = n; if (!amt.value) amt.value = "1850"; } }, l))));
    function showResult(r, name, amount) {
      const tone = { high: "stop", warning: "warn", caution: "warn", clear: "ok" }[r.risk];
      const title = { high: "Stop. This looks like a scam.", warning: "Warning: check before you pay", caution: "Check before you pay", clear: "No scam reports found" }[r.risk];
      screen.replaceChildren(el("div", { class: "pay-result " + tone },
        el("div", { class: "pr-icon", "aria-hidden": "true" }, tone === "ok" ? "✓" : "!"),
        el("h3", null, title),
        el("p", { class: "pr-head" }, r.headline),
        el("p", null, r.advice),
        r.risk !== "clear" ? el("ul", { class: "pr-facts" },
          el("li", null, el("b", null, String(r.reports)), " scam report" + (r.reports === 1 ? "" : "s")),
          el("li", null, el("b", null, String(r.provinces)), " province" + (r.provinces === 1 ? "" : "s")),
          el("li", null, el("b", null, String(r.jurisdictions)), " branch region" + (r.jurisdictions === 1 ? "" : "s")),
          r.frozen_by_its_bank ? el("li", null, el("b", null, "Frozen"), " by its bank") : null) : null,
        el("div", { class: "pr-btns" },
          r.risk === "clear" ? el("button", { class: "btn btn-primary", onclick: () => { toast(`Demo: payment of ${amount || "the amount"} to ${name} would continue.`); reset(); } }, "Pay now")
            : [el("button", { class: "btn btn-primary", onclick: () => { toast("Payment cancelled. Well done: the customer kept their money."); reset(); } }, "Cancel payment"),
               el("button", { class: "btn btn-ghost btn-small", onclick: () => { toast("Demo: the bank would ask the customer to confirm and log the override.", true); reset(); } }, "I know this person, pay anyway")]),
        el("p", { class: "pr-foot" }, `Checked with Ubufakazi · ${r.check_id} · signed request · ${r.quota_left_this_hour} checks left this hour`)));
    }
    function reset() { screen.replaceChildren(form); }
    reset();
    return el("div", { class: "pay-grid" },
      el("div", { class: "phone" }, el("div", { class: "phone-top" }, el("b", null, "Ubuntu Trust Bank"), el("span", null, "Fictional bank app · demo")),
        el("h3", { class: "phone-h" }, "Pay a new beneficiary"), screen),
      el("section", { class: "panel" },
        el("div", { class: "kicker" }, "Stop the next victim"),
        el("h2", null, "Checked before the money leaves"),
        el("p", { class: "muted" }, "When a customer adds a new beneficiary, this bank asks Ubufakazi whether the account is named in scam reports, and warns the customer before they pay."),
        el("h3", null, "How the check is protected"),
        el("ul", { class: "checks" },
          el("li", null, el("b", null, "Subscribed banks only: "), "every request is signed with this bank's own key; requests older than 5 minutes, or reused, are refused."),
          el("li", null, el("b", null, "Cannot frame an innocent account: "), "“Stop” needs several victims in at least two branch regions, or the account frozen by its own bank. One report only ever says “check before you pay”."),
          el("li", null, el("b", null, "Nothing to mine: "), "the answer is a risk level and counts. No victims, references, branches, amounts or chats."),
          el("li", null, el("b", null, "Abuse is visible: "), "hourly quota per bank, unusual lookup volumes raise a security alert, and every check is written to the tamper-evident audit log (without the account number).")),
        el("p", { class: "hint" }, "Fictional bank and synthetic data. A real bank would run this check inside its own app.")));
  }

  function recommend(a) {
    if (a.status === "frozen") return el("div", { class: "notice ok-note" }, el("b", null, "Account blocked. "), "Ubufakazi, the branch fraud desk and the victim have been told.");
    if (!a.account_detail || !a.actions.length) return null;
    const many = a.reports >= 3;
    return el("div", { class: "notice " + (many ? "" : "warn") }, el("b", null, many ? "Recommendation: block this account. " : "Recommendation: investigate. "),
      many ? `${a.reports} separate victims in ${a.provinces.length} province${a.provinces.length === 1 ? "" : "s"} say they paid into this account. It is likely being used as a mule account. Check your own records, then block it while the funds can still be stopped.`
           : `${a.reports} report${a.reports === 1 ? "" : "s"} name this account so far. Check your records; Ubufakazi will update this alert if more victims report it.`);
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
      recommend(a),
      el("h3", null, "Fraud report from Ubufakazi"),
      el("dl", { class: "facts" },
        el("dt", null, "Separate reports"), el("dd", null, String(a.reports)),
        el("dt", null, "Reported paid in"), el("dd", null, money(a.total_reported)),
        el("dt", null, "Provinces"), el("dd", null, a.provinces.join(", ") || "-"),
        el("dt", null, "Scam types"), el("dd", null, a.scam_types.join(", ") || "Not stated")),
      a.corroborated_links ? el("div", { class: "notice info" }, `${a.corroborated_links} pairs of these reports are also linked by other signals (same phone numbers, websites or message templates), which suggests organised use of the account, possibly by a money mule.`) : null,
      el("h3", null, "Payments reported into this account"),
      el("div", { class: "bars" }, a.timeline.map((r) => {
        const fill = el("div", { class: "fill" }); fill.style.width = Math.max(3, (r.amount || 0) / max * 100) + "%";
        return el("div", { class: "bar" }, el("span", { class: "mono" }, date(r.date)), el("div", { class: "track" }, fill), el("span", { class: "amt" }, money(r.amount)));
      })),
      el("p", { class: "hint" }, "Ubufakazi never sends victims' names, phone numbers, statements or report references."),
      a.actions.length ? [el("h3", null, "Decision"), el("div", { class: "sim-actions" }, a.actions.map(btn)),
        el("p", { class: "hint" }, "Each decision is applied in this fictional bank's records and sent back to Ubufakazi over the signed API, where the branch fraud desk and the victim can see it.")] : null,
      el("h3", null, "Case history"),
      el("ol", { class: "steps-v" }, a.events.map((e) => el("li", { class: "done" }, el("b", null, e.action.replace(/[._]/g, " ")), el("div", { class: "muted small" }, `${dateTime(e.at)} · ${e.by}${e.note ? " · " + e.note : ""}`))))));
  }

  boot();
})();
