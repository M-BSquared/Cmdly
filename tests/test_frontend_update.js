"use strict";

/**
 * Frontend tests for the update notice (Cmdly.update).
 *
 * Stub the browser globals the module touches, require the real source
 * (ui.js first, for the modal it builds its dialog from), and assert on the
 * rendered DOM and the requests it makes. No browser, no test runner.
 *
 * What matters here is when the dialog is NOT raised — while no repository
 * is set, over a version that was dismissed, or because there is no internet.
 *
 * Run:
 *   node tests/test_frontend_update.js
 */

const assert = require("node:assert/strict");

// ---------------------------------------------------------------------------
// Browser-ish globals
// ---------------------------------------------------------------------------
global.window = global;
global.Cmdly = {};

window.addEventListener = () => {};
window.removeEventListener = () => {};
window.dispatchEvent = () => {};

// setTimeout is captured, never auto-fired: init() schedules the background
// check and the tests decide when it runs.
const timeouts = [];
window.setTimeout = (cb, ms) => { timeouts.push({ cb, ms }); return timeouts.length; };
window.clearTimeout = () => {};
function runTimeouts() {
  const pending = timeouts.splice(0, timeouts.length);
  pending.forEach((t) => t.cb());
}

// ---------------------------------------------------------------------------
// Minimal DOM stub: just enough for Cmdly.ui's modal, buttons and rows.
// ---------------------------------------------------------------------------
function makeEl(tag) {
  const e = {
    tagName: String(tag || "div").toUpperCase(),
    className: "",
    textContent: "",
    children: [],
    dataset: {},
    style: {
      _props: {},
      setProperty(k, v) { this._props[k] = String(v); },
      getPropertyValue(k) { return this._props[k] || ""; },
      removeProperty(k) { delete this._props[k]; },
    },
    type: "",
    hidden: false,
    disabled: false,
    value: "",
    readOnly: false,
    id: "",
    _attrs: {},
    _listeners: {},
    _isEl: true,
  };
  e.classList = {
    add(c) { const s = e.className.split(/\s+/).filter(Boolean); if (!s.includes(c)) s.push(c); e.className = s.join(" "); },
    remove(c) { e.className = e.className.split(/\s+/).filter((x) => x !== c).join(" "); },
    toggle(c, force) {
      const has = e.classList.contains(c);
      const next = force === undefined ? !has : !!force;
      if (next) e.classList.add(c); else e.classList.remove(c);
      return next;
    },
    contains(c) { return e.className.split(/\s+/).includes(c); },
  };
  e.appendChild = (c) => { c.parentNode = e; e.children.push(c); return c; };
  e.append = (...cs) => cs.forEach((c) => e.appendChild(c));
  e.removeChild = (c) => {
    const i = e.children.indexOf(c);
    if (i >= 0) e.children.splice(i, 1);
    c.parentNode = null;
    return c;
  };
  e.setAttribute = (k, v) => { e._attrs[k] = String(v); if (k === "class") e.className = String(v); };
  e.getAttribute = (k) => (k in e._attrs ? e._attrs[k] : null);
  e.addEventListener = (type, cb) => { (e._listeners[type] = e._listeners[type] || []).push(cb); };
  e.removeEventListener = () => {};
  e.select = () => {};
  e.focus = () => {};
  e.querySelector = (sel) => querySel(e.children, sel)[0] || null;
  e.querySelectorAll = (sel) => querySel(e.children, sel);
  return e;
}

function querySel(children, sel) {
  const out = [];
  const first = String(sel).split(",")[0].trim();
  const wantTag = first && first[0] !== ".";
  const classes = first ? first.split(".").filter(Boolean) : [];
  function walk(list) {
    for (const c of list) {
      if (!c || !c._isEl) continue;
      const ok = wantTag
        ? c.tagName === first.toUpperCase()
        : classes.every((cl) => c.className.split(/\s+/).includes(cl));
      if (ok) out.push(c);
      if (c.children) walk(c.children);
    }
  }
  walk(children);
  return out;
}

// documentFragment behaves as a plain container: the module appends it into
// the modal body, and the stub's appendChild keeps it as one node — so the
// assertions walk through it exactly as they would a real subtree.
const body = makeEl("body");
global.document = {
  body,
  createElement: makeEl,
  createDocumentFragment: () => makeEl("fragment"),
  createTextNode: (t) => ({ nodeType: 3, textContent: String(t), _isText: true }),
  getElementById: () => null,
  querySelectorAll: () => [],
  addEventListener: () => {},
  removeEventListener: () => {},
  execCommand: () => true,
};

// Node defines `navigator` as a getter-only global, so it is replaced rather
// than assigned. Left without a clipboard API by default, which exercises the
// execCommand fallback — the path QtWebEngine takes without clipboard
// permission. A test that wants the modern API sets navigator.clipboard.
Object.defineProperty(global, "navigator", {
  value: {}, writable: true, configurable: true,
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function flush() { return new Promise((r) => setImmediate(r)); }

function findByClass(root, cls) { return root.querySelectorAll("." + cls); }

function textOf(el) {
  if (!el) return "";
  let out = String(el.textContent || "");
  (el.children || []).forEach((c) => { out += textOf(c); });
  return out;
}

function buttonByLabel(root, text) {
  return findByClass(root, "btn").filter((b) => textOf(b).includes(text))[0];
}

function fire(el, type, detail) {
  const listeners = (el && el._listeners && el._listeners[type]) || [];
  const event = Object.assign({ preventDefault() {}, stopPropagation() {} }, detail || {});
  listeners.forEach((cb) => cb(event));
}

/** The mounted modal overlay, or null when no dialog is open. */
function openDialog() {
  return findByClass(body, "modal-overlay")[0] || null;
}

function clearBody() { body.children.length = 0; }

const NEWER = {
  configured: true,
  enabled: true,
  skipped: "",
  current: "2000.09.29",
  latest: "2000.10.02",
  update_available: true,
  name: "Cmdly v2000.10.02",
  url: "https://github.com/example-owner/cmdly/releases/tag/v2000.10.02",
  published: "2026-10-02T09:00:00Z",
  notes: "* Faster shelf\n* Fixed a thing",
  assets: [],
  checked_at: 1,
  error: "",
};

const CURRENT = Object.assign({}, NEWER, {
  latest: "2000.09.29", update_available: false, notes: "",
});

/* What the backend answers while cmdly/update_check.py has no REPO. */
const UNCONFIGURED = {
  configured: false, enabled: true, skipped: "",
  current: "2000.09.29", latest: "", update_available: false,
  name: "", url: "", published: "", notes: "", assets: [], checked_at: 0, error: "",
};

/**
 * Fake Cmdly.api: one response for GET /api/update, one for the open POST.
 * Records every request so the tests can assert what was (and was not) asked.
 */
function makeFakeApi(status) {
  const requests = [];
  const posts = [];
  let response = status;
  let openResponse = { ok: true, url: NEWER.url };

  const settle = (r) => (r instanceof Error ? Promise.reject(r) : Promise.resolve(r));

  Cmdly.api = {
    get(path) {
      requests.push({ url: path });
      return settle(response);
    },
    post(path, body) {
      posts.push({ url: path, payload: body });
      if (path === "/api/update/open") return settle(openResponse);
      return Promise.resolve({ ok: true });
    },
  };

  return {
    requests, posts,
    setResponse(r) { response = r; },
    setOpenResponse(r) { openResponse = r; },
  };
}

// ---------------------------------------------------------------------------
// Load the module under test. ui.js first — it defines Cmdly.ui, the
// component layer the dialog is built from (same order as index.html).
// ---------------------------------------------------------------------------
require("../src/js/ui.js");
require("../src/js/update.js");

// ===========================================================================
// Tests
// ===========================================================================

async function testDialogShownForNewerVersion() {
  clearBody();
  const fake = makeFakeApi(NEWER);

  await Cmdly.update.check();
  await flush();

  const dialog = openDialog();
  assert.ok(dialog, "a newer release raises the dialog");
  const text = textOf(dialog);
  assert.ok(text.includes("2000.09.29"), "the installed version is shown");
  assert.ok(text.includes("2000.10.02"), "the available version is shown");
  assert.ok(text.includes("Faster shelf"), "the release notes are shown");
  assert.ok(text.includes(NEWER.url), "the release URL is readable, not only linked");

  // The automatic path uses the backend's cache, so a reload costs no request
  // to GitHub.
  assert.equal(fake.requests[0].url, "/api/update", "automatic check does not force a refresh");

  Cmdly.update.close();
  assert.equal(openDialog(), null, "close() unmounts the dialog");
}

async function testNothingWithoutARepository() {
  clearBody();
  makeFakeApi(UNCONFIGURED);
  Cmdly.update.note(null);

  const status = await Cmdly.update.check();
  await flush();
  assert.equal(openDialog(), null, "no repository, no dialog");
  assert.equal(status.configured, false);
  assert.equal(Cmdly.update.available(), null, "and no marker");

  // Even a stray update_available from an unconfigured backend stays silent.
  makeFakeApi(Object.assign({}, NEWER, { configured: false }));
  await Cmdly.update.check();
  await Cmdly.update.check({ manual: true, refresh: true });
  await flush();
  assert.equal(openDialog(), null, "configured: false always wins");
  assert.equal(Cmdly.update.available(), null);
}

async function testNoDialogWhenUpToDate() {
  clearBody();
  makeFakeApi(CURRENT);

  const status = await Cmdly.update.check();
  await flush();

  assert.equal(openDialog(), null, "no dialog when the running version is current");
  assert.equal(status.update_available, false);
}

async function testSkippedVersionIsSilent() {
  clearBody();
  makeFakeApi(Object.assign({}, NEWER, { skipped: "2000.10.02" }));

  await Cmdly.update.check();
  await flush();
  assert.equal(openDialog(), null, "a dismissed version never prompts again");

  // …but an explicit "Check now" still shows it, otherwise there is no way
  // back to a release skipped earlier.
  await Cmdly.update.check({ manual: true, refresh: true });
  await flush();
  assert.ok(openDialog(), "a manual check overrides the dismissal");
  Cmdly.update.close();
}

async function testDisabledCheckNeverPrompts() {
  clearBody();
  makeFakeApi(Object.assign({}, NEWER, { enabled: false, update_available: false }));

  await Cmdly.update.check();
  await flush();
  assert.equal(openDialog(), null, "the switched-off check raises nothing");
}

async function testOfflineCheckIsSilent() {
  clearBody();
  makeFakeApi(new Error("Cmdly's backend is not answering."));

  const status = await Cmdly.update.check();
  await flush();

  assert.equal(status, null, "an unreachable backend resolves to null, never throws");
  assert.equal(openDialog(), null, "and shows nothing");

  // A manual check is allowed to fail loudly — someone asked.
  await assert.rejects(() => Cmdly.update.check({ manual: true }),
    "a manual check surfaces the error");
}

async function testSkipButtonPersistsTheVersion() {
  clearBody();
  const fake = makeFakeApi(NEWER);

  await Cmdly.update.check();
  await flush();
  fire(buttonByLabel(openDialog(), "Skip this version"), "click");
  await flush();

  assert.deepEqual(fake.posts[0], {
    url: "/api/update/skip", payload: { version: "2000.10.02" },
  }, "the dismissal is persisted for the exact version shown");
  assert.equal(openDialog(), null, "and the dialog closes");
}

async function testLaterButtonPersistsNothing() {
  clearBody();
  const fake = makeFakeApi(NEWER);

  await Cmdly.update.check();
  await flush();
  fire(buttonByLabel(openDialog(), "Later"), "click");
  await flush();

  assert.equal(fake.posts.length, 0, "\"Later\" writes no config");
  assert.equal(openDialog(), null, "but does close the dialog");
}

async function testOpenReleasePageGoesThroughTheBackend() {
  clearBody();
  const fake = makeFakeApi(NEWER);

  await Cmdly.update.check();
  await flush();
  fire(buttonByLabel(openDialog(), "Open release"), "click");
  await flush();

  const opened = fake.posts.filter((r) => r.url === "/api/update/open");
  assert.equal(opened.length, 1, "the release page is opened server-side");
  // No URL in the request: the backend derives it, so the button can never be
  // turned into a redirect out of the app.
  assert.deepEqual(opened[0].payload, {}, "the request carries no URL");
  Cmdly.update.close();
}

async function testNoBrowserFallsBackToCopy() {
  clearBody();
  const fake = makeFakeApi(NEWER);
  fake.setOpenResponse({ ok: false, error: "no browser available", url: NEWER.url });

  await Cmdly.update.check();
  await flush();
  const dialog = openDialog();
  fire(buttonByLabel(dialog, "Open release"), "click");
  await flush();
  await flush();

  const msg = findByClass(dialog, "update-msg")[0];
  assert.ok(msg, "the dialog carries a status line");
  assert.ok(/clipboard/i.test(textOf(msg)),
    `no browser falls back to the clipboard, got: ${textOf(msg)}`);
  Cmdly.update.close();
}

async function testInitDefersTheCheck() {
  clearBody();
  const fake = makeFakeApi(NEWER);

  Cmdly.update.init();
  assert.equal(fake.requests.length, 0, "init() fires no request of its own");
  assert.ok(timeouts.length >= 1, "it schedules the check instead");
  assert.ok(timeouts[timeouts.length - 1].ms >= 1000,
    "and leaves the UI time to settle first");

  runTimeouts();
  await flush();
  assert.equal(fake.requests[0].url, "/api/update", "the scheduled check then runs");
  Cmdly.update.close();
}

async function testMarkerFollowsTheStatus() {
  clearBody();
  const fake = makeFakeApi(CURRENT);
  Cmdly.update.note(null);
  const seen = [];
  const off = Cmdly.update.onChange((v) => seen.push(v));

  await Cmdly.update.check();
  assert.equal(Cmdly.update.available(), null, "no marker while current");

  fake.setResponse(NEWER);
  await Cmdly.update.check();
  await flush();
  assert.equal(Cmdly.update.available(), "2000.10.02", "a newer release sets the marker");
  Cmdly.update.close();

  fake.setResponse(Object.assign({}, NEWER, { skipped: "2000.10.02" }));
  await Cmdly.update.check();
  assert.equal(Cmdly.update.available(), null, "a skipped version carries no marker");

  fake.setResponse(Object.assign({}, NEWER, { enabled: false }));
  await Cmdly.update.check();
  assert.equal(Cmdly.update.available(), null, "a switched off check carries no marker");

  // Offline keeps whatever the last good answer said.
  fake.setResponse(NEWER);
  await Cmdly.update.check();
  Cmdly.update.close();
  fake.setResponse(new Error("Cmdly's backend is not answering."));
  await Cmdly.update.check();
  assert.equal(Cmdly.update.available(), "2000.10.02", "a failed check leaves the marker alone");

  off();
  assert.deepEqual(seen.filter((v, i) => i === 0 || v !== seen[i - 1]), seen,
    "listeners hear changes only, never repeats");
  assert.deepEqual(seen[0], null, "onChange reports the current value straight away");
  Cmdly.update.note(null);
}

async function testSkipButtonClearsTheMarker() {
  clearBody();
  makeFakeApi(NEWER);

  await Cmdly.update.check();
  await flush();
  assert.equal(Cmdly.update.available(), "2000.10.02");
  fire(buttonByLabel(openDialog(), "Skip this version"), "click");
  await flush();
  assert.equal(Cmdly.update.available(), null, "skipping clears the marker at once");
}

// ---------------------------------------------------------------------------

async function main() {
  const tests = [
    testDialogShownForNewerVersion,
    testNothingWithoutARepository,
    testNoDialogWhenUpToDate,
    testSkippedVersionIsSilent,
    testDisabledCheckNeverPrompts,
    testOfflineCheckIsSilent,
    testSkipButtonPersistsTheVersion,
    testLaterButtonPersistsNothing,
    testOpenReleasePageGoesThroughTheBackend,
    testNoBrowserFallsBackToCopy,
    testInitDefersTheCheck,
    testMarkerFollowsTheStatus,
    testSkipButtonClearsTheMarker,
  ];
  for (const t of tests) {
    await t();
    console.log(`  ok  ${t.name}`);
  }
  console.log(`\n${tests.length} update-notice assertions passed`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
