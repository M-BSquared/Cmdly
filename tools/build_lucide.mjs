#!/usr/bin/env node
/**
 * Builds src/vendor/lucide.min.js: not the whole icon set (376 KB for the
 * ~40 icons the app uses, ~20 KB here), but exactly those, with the same
 * `window.lucide` the page expects. `createIcons()` walks the document for
 * [data-lucide] and replaces each with the named icon, and an icon the set
 * does not carry says so on the console (the backend logs page errors), so
 * a missing name is caught the moment it is used.
 *
 * Run from the repo root with the two dev-only tools installed:
 *     npm install lucide@<version> esbuild
 *     node tools/build_lucide.mjs
 * The lucide version should stay the one the vendor file was first built
 * from, so the glyphs do not change under an existing layout.
 */
import { build } from "esbuild";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

// The names as the sources spell them (data-lucide); the export is the same
// words in PascalCase ("settings-2" -> "Settings2").
const ICONS = [
  "activity", "app-window", "arrow-up-down", "check", "chevron-left", "chevron-right", "circle-alert",
  "clipboard", "cpu", "download", "filter", "filter-x", "grip-vertical", "hard-drive", "info",
  "key-round", "laptop", "maximize-2", "minimize-2", "palette", "pencil", "pin",
  "plug-zap", "plus", "power", "refresh-cw", "rocket", "rotate-cw", "server",
  "settings", "settings-2", "square", "square-arrow-down-left",
  "square-arrow-out-up-right", "square-terminal", "terminal", "trash-2",
  "triangle-alert", "upload", "x",
];
const pascal = (name) => name.split("-").map((w) => w[0].toUpperCase() + w.slice(1)).join("");
const names = ICONS.map(pascal).join(", ");

const entry = `
import { createIcons, ${names} } from "lucide";
const set = { ${names} };
window.lucide = {
  icons: set,
  createIcons(opts) {
    createIcons(Object.assign({}, opts, { icons: set }));
    if (typeof document === "undefined") return;
    document.querySelectorAll("[data-lucide]").forEach((el) => {
      if (el.tagName === "I") {
        console.error('lucide: "' + el.getAttribute("data-lucide") +
          '" is not in the bundled icon set (tools/build_lucide.mjs)');
      }
    });
  },
};
`;

const here = path.dirname(fileURLToPath(import.meta.url));
const out = path.join(here, "..", "src", "vendor", "lucide.min.js");
const result = await build({
  stdin: { contents: entry, resolveDir: process.cwd(), loader: "js" },
  bundle: true,
  minify: true,
  format: "iife",
  target: ["es2019"],
  write: false,
});
const banner = `/**
 * lucide (ISC License) — the ${ICONS.length} icons Cmdly uses, subset by
 * tools/build_lucide.mjs from the lucide npm package.
 */
`;
const text = result.outputFiles[0].text;
fs.writeFileSync(out, banner + text);
console.log(`wrote ${out} (${(text.length / 1024).toFixed(1)} KB for ${ICONS.length} icons)`);
