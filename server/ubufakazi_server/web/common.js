/* Ubufakazi 2.0 shared browser helpers. No secrets live here: all keys stay on the server. */
"use strict";

document.documentElement.classList.add("js");

const UBF = (() => {
  let csrf = "";

  /** Build a DOM element. Children may be strings (always inserted as text, never HTML), nodes, arrays or null. */
  function el(tag, attrs, ...kids) {
    const ns = tag.startsWith("svg:") ? "http://www.w3.org/2000/svg" : null;
    const node = ns ? document.createElementNS(ns, tag.slice(4)) : document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") node.setAttribute("class", v);
      else if (k === "text") node.textContent = v;
      else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
      else if (k === "dataset") Object.assign(node.dataset, v);
      else node.setAttribute(k, v === true ? "" : v);
    }
    const add = (c) => {
      if (c === null || c === undefined || c === false) return;
      if (Array.isArray(c)) c.forEach(add);
      else node.appendChild(c instanceof Node ? c : document.createTextNode(String(c)));
    };
    kids.forEach(add);
    return node;
  }

  function icon(path) {
    const s = el("svg:svg", { viewBox: "0 0 24 24", "aria-hidden": "true" });
    for (const d of [].concat(path)) s.appendChild(el("svg:path", { d }));
    return s;
  }

  async function api(method, url, body, opts = {}) {
    const headers = { Accept: "application/json" };
    if (csrf && method !== "GET") headers["X-CSRF-Token"] = csrf;
    let payload;
    if (body instanceof FormData) payload = body;
    else if (body !== undefined) { headers["Content-Type"] = "application/json"; payload = JSON.stringify(body); }
    const res = await fetch(url, { method, headers, body: payload, credentials: "same-origin" });
    if (opts.blob && res.ok) return res.blob();
    let data = null;
    try { data = await res.json(); } catch (_) { /* not JSON */ }
    if (!res.ok) {
      const msg = (data && (typeof data.detail === "string" ? data.detail : "Please check the form.")) || `Request failed (${res.status})`;
      const err = new Error(msg); err.status = res.status; throw err;
    }
    return data;
  }

  function setCsrf(t) { csrf = t || ""; }

  function toast(msg, isErr) {
    document.querySelectorAll(".toast").forEach((t) => t.remove());
    const t = el("div", { class: "toast" + (isErr ? " err" : ""), role: "status" }, msg);
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 4200);
  }

  const money = (n) => (n === null || n === undefined) ? "-" : "R" + Math.round(n).toLocaleString("en-ZA").replace(/,/g, " ");
  const date = (iso) => iso ? new Date(iso).toLocaleDateString("en-ZA", { day: "numeric", month: "short", year: "numeric" }) : "-";
  const dateTime = (iso) => iso ? new Date(iso).toLocaleString("en-ZA", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "-";
  const size = (n) => n < 1024 ? n + " B" : n < 1048576 ? (n / 1024).toFixed(1) + " KB" : (n / 1048576).toFixed(1) + " MB";

  function download(blob, name) {
    const a = el("a", { href: URL.createObjectURL(blob), download: name });
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  }

  async function sha256(file) {
    const buf = await file.arrayBuffer();
    const h = await crypto.subtle.digest("SHA-256", buf);
    return [...new Uint8Array(h)].map((b) => b.toString(16).padStart(2, "0")).join("");
  }

  /** Sign-in form (password, then a two-factor code). Calls onDone(me). */
  function loginForm(root, { title, subtitle, onDone }) {
    root.replaceChildren();
    const err = el("p", { class: "err", role: "alert" });
    const user = el("input", { type: "text", id: "lg-user", autocomplete: "username", required: true, spellcheck: "false" });
    const pass = el("input", { type: "password", id: "lg-pass", autocomplete: "current-password", required: true });
    const code = el("input", { type: "text", id: "lg-code", class: "otp", inputmode: "numeric", autocomplete: "one-time-code", maxlength: "6", pattern: "[0-9]{6}" });
    const btn = el("button", { class: "btn btn-primary", type: "submit" }, "Sign in");
    const step1 = el("div", { class: "stack" },
      el("div", { class: "field" }, el("label", { for: "lg-user" }, "Username"), user),
      el("div", { class: "field" }, el("label", { for: "lg-pass" }, "Password"), pass));
    const step2 = el("div", { class: "field", hidden: true }, el("label", { for: "lg-code" }, "Two-factor code"), code,
      el("p", { class: "hint" }, "Open your authenticator app (for the demo: python -m ubufakazi_server.totp <username>)."));
    const form = el("form", { novalidate: true }, step1, step2, err, btn);
    let mfa = false;
    form.addEventListener("submit", async (e) => {
      e.preventDefault(); err.textContent = ""; btn.disabled = true;
      try {
        if (!mfa) {
          const r = await api("POST", "/api/auth/login", { username: user.value.trim(), password: pass.value });
          setCsrf(r.csrf);
          if (r.mfa_required) { mfa = true; step1.hidden = true; step2.hidden = false; btn.textContent = "Verify"; code.focus(); }
          else { setCsrf(r.me.csrf); onDone(r.me); }
        } else {
          const r = await api("POST", "/api/auth/mfa", { code: code.value.trim() });
          setCsrf(r.me.csrf); onDone(r.me);
        }
      } catch (ex) {
        err.textContent = ex.message;
        if (ex.status === 401 && mfa && /sign in again/i.test(ex.message)) { mfa = false; step1.hidden = false; step2.hidden = true; btn.textContent = "Sign in"; }
      } finally { btn.disabled = false; }
    });
    root.appendChild(el("div", { class: "login-wrap" }, el("div", { class: "panel login" },
      el("div", { class: "kicker" }, "Restricted · demo"), el("h1", null, title), el("p", { class: "muted" }, subtitle), form)));
    user.focus();
  }

  async function session() {
    try { const me = await api("GET", "/api/auth/me"); setCsrf(me.csrf); return me; } catch (_) { return null; }
  }

  async function logout() {
    try { await api("POST", "/api/auth/logout", {}); } catch (_) { /* already signed out */ }
    setCsrf(""); location.reload();
  }

  // ---- page chrome: mobile menu + reveal-on-scroll (progressive: content is visible without JS)
  function chrome() {
    const btn = document.querySelector(".menu-btn"), nav = document.getElementById("pubnav");
    if (btn && nav) btn.addEventListener("click", () => {
      const open = nav.classList.toggle("open");
      btn.setAttribute("aria-expanded", open ? "true" : "false");
    });
    const items = document.querySelectorAll(".reveal");
    if (!("IntersectionObserver" in window)) { items.forEach((i) => i.classList.add("in")); return; }
    const io = new IntersectionObserver((entries) => entries.forEach((e) => {
      if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
    }), { threshold: 0.12 });
    items.forEach((i) => io.observe(i));
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", chrome); else chrome();

  return { el, icon, api, setCsrf, toast, money, date, dateTime, size, download, sha256, loginForm, session, logout };
})();
