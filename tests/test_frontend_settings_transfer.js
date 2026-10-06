"use strict";

/**
 * Settings export and import, the browser half (Cmdly.settingsTransfer).
 *
 * Asserted on the pure seams: which localStorage keys are settings and which
 * part they belong to, collecting and applying them, reading a file (the
 * first Cmdly export's included), and what the import dialog says a file
 * holds. Plus the guard that matters most over time: a module that starts
 * keeping a new setting in localStorage has to register it in BROWSER_KEYS
 * (or say it is not a setting), or an export would quietly leave it behind.
 *
 * Run:
 *   node tests/test_frontend_settings_transfer.js
 */

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

global.window = global;
global.Cmdly = {};

require("./../src/js/settings-transfer.js");

const T = Cmdly.settingsTransfer;

/** A Storage with the parts of the Web Storage API the module uses. */
function fakeStorage(entries) {
  const map = new Map(Object.entries(entries || {}));
  return {
    get length() { return map.size; },
    key(i) { return Array.from(map.keys())[i] ?? null; },
    getItem(k) { return map.has(k) ? map.get(k) : null; },
    setItem(k, v) { map.set(k, String(v)); },
    removeItem(k) { map.delete(k); },
    dump() { return Object.fromEntries(map); },
  };
}

// ---------------------------------------------------------------------------

function testMirrorsAreNotSettings() {
  T.NOT_SETTINGS.forEach((k) => assert.equal(T.sectionOfKey(k), ""));
  assert.equal(T.sectionOfKey("somebody.else"), "");
}

function testCollectTakesOnlySettings() {
  const store = fakeStorage({ "cmdly.theme": "green", "unrelated": "1" });
  assert.deepEqual(T.collectBrowser(store), {});
}

function testApplyNeverTouchesWhatIsNotASetting() {
  const store = fakeStorage({ "cmdly.theme": "green" });
  T.applyBrowser(store, { "cmdly.theme": "pink", "evil": "y" }, ["appearance", "buttons"]);
  assert.deepEqual(store.dump(), { "cmdly.theme": "green" });
}

function testStorageThatThrowsIsSurvived() {
  const broken = { get length() { throw new Error("denied"); } };
  T.applyBrowser(broken, { "cmdly.x": "{}" }, ["appearance"]);
  assert.deepEqual(T.collectBrowser(broken), {});
}

function testParseRejectsWhatIsNotASettingsFile() {
  assert.throws(() => T.parseBundle("not json"), /not a Cmdly settings file/);
  assert.throws(() => T.parseBundle('{"kind":"x","config":{}}'), /not a Cmdly settings file/);
  assert.throws(() => T.parseBundle('{"kind":"cmdly-settings"}'), /not a Cmdly settings file/);
  assert.throws(() => T.parseBundle('{"unrelated":1}'), /not a Cmdly settings file/);
  const ok = T.parseBundle('{"kind":"cmdly-settings","format":1,"sections":[],"config":{}}');
  assert.equal(ok.format, 1);
}

function testAFileCarriesWhatItSays() {
  const bundle = { kind: "cmdly-settings", sections: ["appearance", "buttons", "bogus"], config: {} };
  assert.deepEqual(T.sectionsInFile(bundle), ["buttons", "appearance"]);
  assert.deepEqual(T.sectionsInFile({ kind: "cmdly-settings", config: {} }), []);
}

function testTheFirstCmdlyExportIsRead() {
  const legacy = T.parseBundle(JSON.stringify({
    cmdly: "2026.10.05", buttons: [{ command: "ls" }], theme: "tesla_dark",
  }));
  assert.ok(T.isLegacy(legacy));
  assert.deepEqual(T.sectionsInFile(legacy), ["buttons", "appearance"]);
  const pyside = { companion: { host: "10.0.0.2" } };
  assert.deepEqual(T.sectionsInFile(pyside), ["companions"]);
  assert.equal(T.describeParts(pyside).companions, "1 companion computer");
}

function testDescribePartsCounts() {
  const parts = T.describeParts({
    kind: "cmdly-settings",
    config: {
      buttons: [{}, {}, {}], companions: [{}], connections: [],
      ui: { theme: "orange" },
    },
  });
  assert.equal(parts.buttons, "3 buttons");
  assert.equal(parts.companions, "1 companion computer");
  assert.equal(parts.connections, "0 connections");
  assert.equal(parts.appearance, "Theme: orange");
  assert.equal(T.describeParts(null).appearance, "");
}

function testResultTextNamesOnlyWhatWasTaken() {
  const text = T.resultText({
    sections: ["buttons", "appearance"],
    counts: { buttons: 1, companions: 4, connections: 2 },
    warnings: ['No saved SSH connection named "pi".'],
  });
  assert.match(text, /1 button,/);
  assert.match(text, /the appearance/);
  assert.doesNotMatch(text, /companion/);
  assert.match(text, /"pi"/);
  assert.equal(T.resultText({}), "Settings imported.");
}

function testSectionsMatchTheBackend() {
  const py = fs.readFileSync(path.join(__dirname, "..", "cmdly", "settings_bundle.py"), "utf8");
  const start = py.indexOf("SECTIONS: dict");
  const block = py.slice(start, py.indexOf("EXCLUDED_KEYS", start));
  const backend = Array.from(block.matchAll(/^\s+"([a-z]+)": \(/gm)).map((m) => m[1]).sort();
  assert.ok(backend.length, "the scan found no section; the pattern is broken");
  assert.deepEqual(T.SECTIONS.map((s) => s.id).sort(), backend);
  T.BROWSER_KEYS.forEach((e) => assert.ok(backend.includes(e.section), e.key));
}

function testEveryStoredKeyIsAccountedFor() {
  // A key a module keeps in localStorage is either exported or deliberately
  // not a setting. Anything else is a setting an export would lose.
  const root = path.join(__dirname, "..", "src");
  const sources = fs.readdirSync(path.join(root, "js")).filter((f) => f.endsWith(".js"))
    .map((f) => fs.readFileSync(path.join(root, "js", f), "utf8"));
  fs.readdirSync(root).filter((f) => f.endsWith(".html"))
    .forEach((f) => sources.push(fs.readFileSync(path.join(root, f), "utf8")));
  const found = new Set();
  const patterns = [
    /KEY(?:_PREFIX)?\s*=\s*"(cmdly\.[^"]+)"/g,
    /localStorage\.(?:getItem|setItem|removeItem)\(\s*"(cmdly\.[^"]+)"/g,
  ];
  sources.forEach((src) => patterns.forEach((re) => {
    for (const m of src.matchAll(re)) found.add(m[1]);
  }));
  assert.ok(found.has("cmdly.theme"), "the scan found nothing; the pattern is broken");
  const known = new Set(T.BROWSER_KEYS.map((e) => e.key).concat(T.NOT_SETTINGS));
  const missing = Array.from(found).filter((k) => !known.has(k));
  assert.deepEqual(missing, [],
    "add these to BROWSER_KEYS or NOT_SETTINGS in src/js/settings-transfer.js");
}

function testHintsUseNoDashes() {
  const texts = [];
  T.SECTIONS.forEach((s) => texts.push(s.label, s.hint));
  texts.forEach((t) => assert.ok(!/[–—]| - /.test(t), t));
}

const tests = [
  testMirrorsAreNotSettings,
  testCollectTakesOnlySettings,
  testApplyNeverTouchesWhatIsNotASetting,
  testStorageThatThrowsIsSurvived,
  testParseRejectsWhatIsNotASettingsFile,
  testAFileCarriesWhatItSays,
  testTheFirstCmdlyExportIsRead,
  testDescribePartsCounts,
  testResultTextNamesOnlyWhatWasTaken,
  testSectionsMatchTheBackend,
  testEveryStoredKeyIsAccountedFor,
  testHintsUseNoDashes,
];

let failed = 0;
for (const t of tests) {
  try {
    t();
    console.log(`  ok  ${t.name}`);
  } catch (err) {
    failed += 1;
    console.log(`FAIL ${t.name}\n${err.stack || err}`);
  }
}
if (failed) {
  console.log(`${failed} of ${tests.length} failed`);
  process.exit(1);
}
console.log(`\n${tests.length} settings-transfer assertions passed`);
