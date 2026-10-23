"use strict";

/**
 * Frontend test for the store's agent sessions: a terminal an AI agent opens
 * over MCP (js/store.js) comes up under the agent/ prefix and is shown to the
 * person as a terminal window, so nothing an agent types happens off screen.
 *
 * Loaded from the real sources with `window`, `document`, the api and the
 * terminal windows stubbed. The tests run one after the other: they share the
 * store's live state.
 *
 * Run:
 *   node tests/test_frontend_store.js
 */

const assert = require("node:assert/strict");
const path = require("node:path");

global.window = global;
global.Cmdly = {};
window.addEventListener = () => {};
global.document = { addEventListener: () => {}, hidden: false };

// store.js takes the api as it loads (as the page loads it after api.js);
// the stub is one object whose answers each test replaces.
Cmdly.api = { get: () => Promise.reject(new Error("no sessions yet")) };

require(path.join(__dirname, "..", "src", "js", "store.js"));
require(path.join(__dirname, "..", "src", "js", "launch.js"));
const store = Cmdly.store;

let passed = 0;
let chain = Promise.resolve();
function test(name, fn) {
  chain = chain.then(fn).then(() => {
    passed += 1;
    console.log("  ok  " + name);
  }, (e) => {
    console.error(`${name}\n${(e && e.stack) || e}`);
    process.exitCode = 1;
  });
}

/** One /api/ssh/sessions answer behind the api stub. */
function sessionsApi(rows) {
  Cmdly.api.get = (p) => {
    if (p === "/api/ssh/sessions") return Promise.resolve({ sessions: rows });
    return Promise.reject(new Error("not asked: " + p));
  };
}

test("a session an agent opened is shown as a terminal window", () => {
  const opened = [];
  Cmdly.termWindows = { open: (s) => { opened.push(s); return true; } };
  sessionsApi([{ name: "agent/main", host: "this computer", port: 0, username: "me", connected: true }]);
  return store.refreshLive().then(() => {
    assert.equal(opened.length, 1);
    assert.deepEqual(opened[0], {
      name: "agent/main", title: "Agent: main",
      host: "this computer", port: 0, username: "",
    });
  });
});

test("a session of a button's own never opens a window from the poll", () => {
  const opened = [];
  Cmdly.termWindows = { open: (s) => { opened.push(s); return true; } };
  sessionsApi([{ name: "cmdly/b_welcome", host: "this computer", port: 0, username: "me", connected: true }]);
  return store.refreshLive().then(() => {
    assert.equal(opened.length, 0);
  });
});

test("an agent session over SSH names its host in the window", () => {
  const opened = [];
  Cmdly.termWindows = { open: (s) => { opened.push(s); return true; } };
  sessionsApi([{ name: "agent/deploy", host: "10.0.0.2", port: 2222, username: "pi", connected: true }]);
  return store.refreshLive().then(() => {
    assert.deepEqual(opened[0], {
      name: "agent/deploy", title: "Agent: deploy",
      host: "10.0.0.2", port: 2222, username: "pi",
    });
  });
});

test("a window the person closed is not forced back on the next poll", () => {
  const opened = [];
  Cmdly.termWindows = { open: (s) => { opened.push(s); return true; } };
  sessionsApi([{ name: "agent/main", host: "this computer", port: 0, username: "me", connected: true }]);
  return store.refreshLive().then(() => {
    assert.equal(opened.length, 1);
    return store.refreshLive();
  }).then(() => {
    assert.equal(opened.length, 1);  // still up, already shown
  });
});

test("an unreachable backend means no sessions and no windows", () => {
  const opened = [];
  Cmdly.termWindows = { open: (s) => { opened.push(s); return true; } };
  Cmdly.api.get = () => Promise.reject(new Error("down"));
  return store.refreshLive().then(() => {
    assert.equal(opened.length, 0);
    assert.equal(Object.keys(store.state.live).length, 0);
  });
});

test("a config an agent changed is pulled in, an unchanged one is not", () => {
  store.state.config = { buttons: [], companions: [], connections: [] };
  const toasts = [];
  Cmdly.ui = { toast: (o) => toasts.push(o) };
  let events = 0;
  const off = store.on("config", () => { events += 1; });
  Cmdly.api.get = (p) => {
    if (p === "/api/config") {
      return Promise.resolve({ config: { buttons: [{ id: "b1" }], connections: [] } });
    }
    return Promise.reject(new Error("not asked: " + p));
  };
  return store.refreshConfig().then(() => {
    assert.equal(store.state.config.buttons.length, 1);   // the agent's button
    assert.equal(events, 1);                               // and the shelf heard
    assert.equal(toasts.length, 1);                        // and the person was told
    assert.equal(toasts[0].title, "Shelf changed");
    return store.refreshConfig();
  }).then(() => {
    assert.equal(events, 1);   // the same config again: no repaint, no noise
    assert.equal(toasts.length, 1);
    off();
  });
});

test("a save on its way out holds the refresh back: its answer wins", () => {
  Cmdly.ui = { toast: () => {} };
  store.state.config = { buttons: [] };
  const post = new Promise((resolve) => {
    setTimeout(() => resolve({ ok: true, config: { buttons: [], connections: [] } }), 20);
  });
  Cmdly.api.post = () => post;
  Cmdly.api.get = (p) => {
    if (p === "/api/config") {
      return Promise.resolve({ config: { buttons: [{ id: "agent" }], connections: [] } });
    }
    return Promise.reject(new Error("not asked: " + p));
  };
  const saved = store.save({ buttons: [{ id: "draft" }] });
  return store.refreshConfig().then(() => {
    // The refresh ran while the save was out: it stood back.
    assert.equal(store.state.config.buttons[0].id, "draft");
    return saved;
  }).then(() => {
    assert.equal(store.state.config.buttons.length, 0);   // the save's answer
  });
});

chain.then(() => {
  console.log(`\n${passed} tests passed`);
});
