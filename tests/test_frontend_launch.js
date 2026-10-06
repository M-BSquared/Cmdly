"use strict";

/**
 * Frontend tests for the shelf's pure rules: Cmdly.launch (what a button
 * runs, how a connection is checked) and Cmdly.companion (when the companion
 * counts as online). Loaded from the real sources with only `window` stubbed.
 *
 * Run:
 *   node tests/test_frontend_launch.js
 */

const assert = require("node:assert/strict");
const path = require("node:path");

global.window = global;
global.Cmdly = {};
window.addEventListener = () => {};
global.document = { addEventListener: () => {}, hidden: false };

require(path.join(__dirname, "..", "src", "js", "launch.js"));
require(path.join(__dirname, "..", "src", "js", "companion.js"));
const L = Cmdly.launch;
const C = Cmdly.companion;

let passed = 0;
function test(name, fn) {
  fn();
  passed += 1;
  console.log("  ok  " + name);
}

test("terminalLine quotes the folder and keeps ~", () => {
  assert.equal(L.terminalLine({ command: "ls" }), "ls");
  assert.equal(L.terminalLine({ directory: "~/my dir", command: "ls" }), "cd -- ~/'my dir' && ls");
  assert.equal(L.terminalLine({ directory: "/opt/it's", command: "ls" }), "cd -- '/opt/it'\\''s' && ls");
  assert.equal(L.terminalLine({ directory: "/x", command: "  " }), "");
});

test("previewLine shows where and how it runs", () => {
  assert.equal(L.previewLine({ target: "local", command: "go" }), "go");
  assert.equal(L.previewLine({ target: "local", mode: "background", command: "go", directory: "/a" }), "cd /a && go &");
  assert.equal(L.previewLine({ target: "ssh", connection: "pi", mode: "background", command: "go" }), "ssh pi 'nohup go &'");
});

test("an old SSH launcher entry runs over SSH, detached as it was", () => {
  assert.equal(L.coerceTarget({ connection: "pi" }), "ssh");
  assert.equal(L.coerceTarget({}), "local");
  assert.equal(L.coerceMode({ detach: true }), "background");
  assert.equal(L.coerceMode({ mode: "terminal", detach: true }), "terminal");
});

test("only a terminal button restarts", () => {
  assert.equal(L.restarts({ restart: true }), true);
  assert.equal(L.restarts({ restart: true, mode: "background" }), false);
  assert.equal(L.restarts({ restart: "yes" }), false);
});

test("sessions are keyed by the button's id", () => {
  assert.equal(L.sessionName({ id: "b1" }), "cmdly/b1");
});

test("a typed-in connection is checked before it is saved", () => {
  assert.match(L.connectionError({}, []), /host/);
  assert.match(L.connectionError({ host: "-x" }, []), /not an IP/);
  assert.match(L.connectionError({ host: "h", port: "70000" }, []), /port/);
  assert.match(L.connectionError({ host: "h", username: "pi" }, ["pi@h"]), /already saved/);
  assert.equal(L.connectionError({ host: "h", username: "pi" }, []), "");
});

test("an empty password field is left out, so the stored one is kept", () => {
  const body = L.connectionBody({ host: " h ", username: "pi", port: "", password: "" });
  assert.deepEqual(body, { name: "pi@h", host: "h", port: 22, username: "pi", key_path: "" });
  assert.equal(L.connectionBody({ host: "h", password: " p " }).password, " p ");
});

test("background summaries", () => {
  assert.deepEqual(L.localSummary({ exited: true, ok: false, code: 2, output: "boom\nmore" }),
    { text: "boom", kind: "err" });
  assert.equal(L.localSummary({ ok: true, pid: 7 }).kind, "ok");
  assert.equal(L.sshSummary({ ok: true, stdout: "123\n" }).text, "Running in the background (pid 123)");
  assert.equal(L.sshSummary({ ok: false, error: "nope" }).kind, "err");
});

test("the reachable filter", () => {
  const comp = { host: "10.0.0.2", connection: "pi" };
  const conns = [{ name: "other", host: "10.0.0.2" }];
  assert.equal(L.reachable({ target: "local" }, null, false, []), true);
  assert.equal(L.reachable({ target: "ssh", connection: "pi" }, comp, false, conns), false);
  assert.equal(L.reachable({ target: "ssh", connection: "other" }, comp, true, conns), true);
  assert.equal(L.reachable({ target: "ssh", connection: "x" }, comp, true, conns), false);
});

test("companion state over time", () => {
  const base = { host: "h", startedAt: 0, timeoutMs: 6000 };
  assert.equal(C.stateOf({}), "unset");
  assert.equal(C.stateOf({ ...base, now: 1000, lastOkAt: null }), "checking");
  assert.equal(C.stateOf({ ...base, now: 7000, lastOkAt: null }), "offline");
  assert.equal(C.stateOf({ ...base, now: 7000, lastOkAt: 2000 }), "online");
  assert.equal(C.stateOf({ ...base, now: 9000, lastOkAt: 2000 }), "offline");
  assert.equal(C.stateOf({ ...base, now: 1000, error: "no ping" }), "error");
  assert.equal(C.stateOf({ ...base, now: 3000, lastOkAt: 2000, error: "x" }), "online");
});

test("probe waits and slider couplings", () => {
  assert.equal(C.probeWaitMs(0.2), 1000);
  assert.equal(C.probeWaitMs(3), 3000);
  assert.equal(C.probeWaitMs(30), 5000);
  assert.equal(C.timeoutFor(5), 6);
  assert.equal(C.intervalFor(4), 3);
  assert.equal(C.formatRtt(3.456), "3.5 ms");
  assert.equal(C.formatRtt(42.4), "42 ms");
});

test("a companion gets a terminal only over SSH", () => {
  assert.equal(C.entryOf({ id: "c1", type: "ping", host: "h" }), null);
  const e = C.entryOf({ id: "c1", type: "ssh", connection: "pi", host: "h" });
  assert.equal(L.sessionName(e), "cmdly/companion-c1");
  assert.equal(e.connection, "pi");
});

console.log(`\n${passed} launch/companion assertions passed`);
