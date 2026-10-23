"use strict";

/**
 * Frontend tests for the agent setup guide's snippet builders (js/settings.js):
 * the OpenCode and Codex config blocks, built from the command that
 * GET /api/agent/mcp returns for the installation Cmdly runs from. Pure
 * string builders, so only `window` is stubbed.
 *
 * Run:
 *   node tests/test_frontend_settings_agent.js
 */

const assert = require("node:assert/strict");
const path = require("node:path");

global.window = global;
global.Cmdly = {};
window.addEventListener = () => {};

require(path.join(__dirname, "..", "src", "js", "settings.js"));
const S = Cmdly.settings;

let passed = 0;
function test(name, fn) {
  fn();
  passed += 1;
  console.log("  ok  " + name);
}

const VENV = { command: ["/home/pi/Cmdly/.venv/bin/python", "-m", "cmdly", "mcp"],
               env: { PYTHONPATH: "/home/pi/Cmdly" } };
const APPIMAGE = { command: ["/opt/Cmdly.AppImage", "mcp"], env: {} };

test("the OpenCode block names the command and the folder", () => {
  const s = S.opencodeSnippet(VENV);
  const block = JSON.parse(s.text);   // JSON, whatever file it goes into
  assert.equal(block.mcp.servers.cmdly.type, "local");
  assert.deepEqual(block.mcp.servers.cmdly.command, VENV.command);
  assert.deepEqual(block.mcp.servers.cmdly.environment, VENV.env);
  assert.equal(
    s.cli,
    "opencode mcp add cmdly --env PYTHONPATH=/home/pi/Cmdly --global -- " +
    "/home/pi/Cmdly/.venv/bin/python -m cmdly mcp");
});

test("an AppImage install carries its Python with it, so no environment", () => {
  const s = S.opencodeSnippet(APPIMAGE);
  const block = JSON.parse(s.text).mcp.servers.cmdly;
  assert.deepEqual(block.command, APPIMAGE.command);
  assert.deepEqual(block.environment, {});
  assert.equal(s.cli, "opencode mcp add cmdly --global -- /opt/Cmdly.AppImage mcp");
});

test("the Codex block is a TOML table", () => {
  const s = S.codexSnippet(VENV);
  const lines = s.text.split("\n");
  assert.equal(lines[0], "[mcp_servers.cmdly]");
  assert.ok(lines.includes('command = "/home/pi/Cmdly/.venv/bin/python"'));
  assert.ok(lines.includes('args = ["-m", "cmdly", "mcp"]'));
  assert.ok(lines.includes('env = { "PYTHONPATH" = "/home/pi/Cmdly" }'));
});

test("the Codex block of an AppImage leaves the env line out", () => {
  assert.equal(
    S.codexSnippet(APPIMAGE).text,
    '[mcp_servers.cmdly]\ncommand = "/opt/Cmdly.AppImage"\nargs = ["mcp"]');
});

test("a path with a space stays one argument in the CLI line", () => {
  const s = S.opencodeSnippet({ command: ["/opt/My Cmdly/App Image", "mcp"], env: {} });
  assert.ok(s.cli.indexOf("'/opt/My Cmdly/App Image' mcp") !== -1);
});

console.log(`\n${passed} tests passed`);
