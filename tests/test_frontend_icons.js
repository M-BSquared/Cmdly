"use strict";

/**
 * Frontend test for the vendored icon bundle: src/vendor/lucide.min.js is a
 * subset (tools/build_lucide.mjs), so every icon name the sources spell must
 * be in it. A name that is missing shows as a blank glyph and a page error at
 * runtime; this catches it here, with the name to add to the tool's list.
 *
 * Run:
 *   node tests/test_frontend_icons.js
 */

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

global.window = global;

require(path.join(__dirname, "..", "src", "vendor", "lucide.min.js"));
const bundled = window.lucide.icons;

const SRC = path.join(__dirname, "..", "src");
const files = [
  ...fs.readdirSync(path.join(SRC, "js")).filter((f) => f.endsWith(".js")).map((f) => path.join(SRC, "js", f)),
  ...fs.readdirSync(SRC).filter((f) => f.endsWith(".html")).map((f) => path.join(SRC, f)),
];

// How the sources name an icon: as the icon itself, as an icon: property, or
// as either side of a conditional the call picks one of.
const CALLERS = [
  /(?:ui\.icon|iconButton|emptyState)\(\s*"([a-z0-9-]+)"/g,
  /(?:ui\.icon|iconButton)\([^)]*\?\s*"([a-z0-9-]+)"\s*:\s*"([a-z0-9-]+)"/g,
  /data-lucide="([a-z0-9-]+)"/g,
  /icon:\s*"([a-z0-9-]+)"/g,
  /icon:\s*[^,}]*\?\s*"([a-z0-9-]+)"\s*:\s*"([a-z0-9-]+)"/g,
];
const used = new Set();
files.forEach((file) => {
  // Doc comments name icons as placeholders (<i data-lucide="name">); only
  // code counts.
  const text = fs.readFileSync(file, "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, " ")
    .replace(/^\s*\/\/.*$/gm, " ");
  CALLERS.forEach((re) => {
    let m;
    while ((m = re.exec(text))) {
      if (/^[a-z0-9]+(-[a-z0-9]+)*$/.test(m[1])) used.add(m[1]);
      if (m[2] && /^[a-z0-9]+(-[a-z0-9]+)*$/.test(m[2])) used.add(m[2]);
    }
  });
});

// lucide's own transform: "settings-2" is the export "Settings2".
const pascal = (name) => name.split("-").map((w) => w[0].toUpperCase() + w.slice(1)).join("");

let passed = 0;
function test(name, fn) {
  fn();
  passed += 1;
  console.log("  ok  " + name);
}

test("every icon the sources name is in the bundled set", () => {
  assert.ok(used.size >= 30, `the collector found suspiciously few icon names (${used.size})`);
  const missing = [...used].filter((name) => !bundled[pascal(name)]);
  assert.deepEqual(missing, [],
    "add them in tools/build_lucide.mjs and rebuild src/vendor/lucide.min.js");
});

console.log(`${passed} icon-bundle assertion${passed === 1 ? "" : "s"} passed`);
