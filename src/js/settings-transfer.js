"use strict";
window.Cmdly = window.Cmdly || {};

/*
  Cmdly.settingsTransfer — Export and Import on the Data page of the settings.

  One file carries the setup, or the parts of it the person picks: the
  buttons, the companion computers, the saved SSH connections and the
  appearance. The backend puts in the config (POST /api/settings/export, see
  cmdly/settings_bundle.py); this page adds what it keeps in localStorage
  that is a setting, listed in BROWSER_KEYS.

  The backend writes the file, because the desktop window (QtWebEngine)
  drops a browser download; that is also what keeps the passwords, when they
  go in, off the HTTP responses. Import reads the file here, shows what it
  holds, and posts it back with the parts chosen. The browser half is applied
  once the backend has taken the rest, and the store then reloads the
  settings, which repaints the shelf and the companion and applies the
  appearance again (js/app.js).
*/
Cmdly.settingsTransfer = (function () {
  /* Every localStorage key that is a setting, with the part of an import it
     belongs to. A key ending in "." is a prefix. Keys that are not settings
     sit in NOT_SETTINGS, so the test suite can tell a key that was forgotten
     here from one that was left out on purpose. */
  const BROWSER_KEYS = [];
  // cmdly.theme is the palette applied right now, mirrored for terminal
  // windows of their own (js/theme.js); cmdly.frostedTerminals mirrors
  // ui.frosted_terminals the same way (js/term-window.js). Both are written
  // again on every start from the config, which is what travels.
  const NOT_SETTINGS = ["cmdly.theme", "cmdly.frostedTerminals"];

  /* The parts an export or import is chosen by. The ids match SECTIONS in
     cmdly/settings_bundle.py. */
  const SECTIONS = [
    { id: "buttons", label: "Buttons",
      hint: "Every button on the shelf: its command, folder, where it runs and how." },
    { id: "companions", label: "Companion computers",
      hint: "The companion computers, how each is checked, and which one is shown." },
    { id: "connections", label: "SSH connections",
      hint: "The saved SSH connections the buttons and companions use." },
    { id: "appearance", label: "Appearance",
      hint: "Theme, the frosted window and how terminal windows open and look." },
  ];

  // ---- browser half ------------------------------------------------------

  /** The part a localStorage key belongs to, or "" when it is not a setting. */
  function sectionOfKey(key) {
    const k = String(key || "");
    const hit = BROWSER_KEYS.find((e) =>
      e.key.endsWith(".") ? k.startsWith(e.key) : k === e.key);
    return hit ? hit.section : "";
  }

  function storageKeys(storage) {
    const keys = [];
    for (let i = 0; i < storage.length; i += 1) {
      const k = storage.key(i);
      if (k) keys.push(k);
    }
    return keys;
  }

  /** Every setting this page keeps in *storage*, as {key: string}; only those
   *  of *sections* when it is given. */
  function collectBrowser(storage, sections) {
    const out = {};
    const only = sections ? new Set(sections) : null;
    try {
      storageKeys(storage).forEach((k) => {
        const section = sectionOfKey(k);
        if (!section || (only && !only.has(section))) return;
        const v = storage.getItem(k);
        if (typeof v === "string") out[k] = v;
      });
    } catch (_e) { /* storage unavailable: the backend half still exports */ }
    return out;
  }

  /**
   * Make the chosen parts of *storage* what *browser* says.
   *
   * A key of a chosen part that the file does not have is removed, so it
   * falls back to its default the way it had on the computer that wrote the
   * file. Parts not chosen are not touched.
   */
  function applyBrowser(storage, browser, sections) {
    const chosen = new Set(sections || []);
    const incoming = browser && typeof browser === "object" ? browser : {};
    try {
      storageKeys(storage).forEach((k) => {
        if (chosen.has(sectionOfKey(k)) && !Object.prototype.hasOwnProperty.call(incoming, k)) {
          storage.removeItem(k);
        }
      });
      Object.keys(incoming).forEach((k) => {
        if (chosen.has(sectionOfKey(k)) && typeof incoming[k] === "string") {
          storage.setItem(k, incoming[k]);
        }
      });
    } catch (_e) { /* storage unavailable: the backend half is already applied */ }
  }

  function localStore() {
    try { return window.localStorage; } catch (_e) { return null; }
  }

  // ---- what a file carries -----------------------------------------------

  function isObject(v) { return !!v && typeof v === "object" && !Array.isArray(v); }

  /* The keys the first Cmdly export wrote for each part, the PySide build's
     spellings included. Mirrors _LEGACY_KEYS in cmdly/settings_bundle.py. */
  const LEGACY_KEYS = {
    buttons: ["buttons"],
    companions: ["companions", "companion", "active_companion"],
    connections: ["connections"],
    appearance: ["ui", "theme"],
  };

  /** Whether *data* is a setup the first Cmdly export wrote. Pure. */
  function isLegacy(data) {
    return isObject(data) && !("kind" in data) &&
      Object.keys(LEGACY_KEYS).some((s) => LEGACY_KEYS[s].some((k) => k in data));
  }

  /** The parts *bundle* carries, in the order of SECTIONS. Pure. */
  function sectionsInFile(bundle) {
    const all = SECTIONS.map((s) => s.id);
    if (isLegacy(bundle)) {
      return all.filter((id) => LEGACY_KEYS[id].some((k) => k in bundle));
    }
    if (!bundle || !Array.isArray(bundle.sections)) return [];
    return all.filter((id) => bundle.sections.indexOf(id) !== -1);
  }

  function listOf(v) { return Array.isArray(v) ? v : []; }

  /**
   * What each part of *bundle* holds, as a phrase for the import dialog
   * ("3 buttons"), or "" for a part with nothing to count. Pure.
   */
  function describeParts(bundle) {
    const cfg = isLegacy(bundle) ? bundle : (isObject(bundle && bundle.config) ? bundle.config : {});
    const count = (n, one, many) => (n === 1 ? `1 ${one}` : `${n} ${many}`);
    const companions = listOf(cfg.companions).length || (isObject(cfg.companion) ? 1 : 0);
    const ui = isObject(cfg.ui) ? cfg.ui : {};
    const theme = ui.theme || cfg.theme;
    return {
      buttons: count(listOf(cfg.buttons).length, "button", "buttons"),
      companions: count(companions, "companion computer", "companion computers"),
      connections: count(listOf(cfg.connections).length, "connection", "connections"),
      appearance: typeof theme === "string" && theme ? `Theme: ${theme}` : "",
    };
  }

  /** The parsed file, or an Error a person can act on. Pure. */
  function parseBundle(text) {
    let data;
    try { data = JSON.parse(String(text || "")); } catch (_e) {
      throw new Error("This is not a Cmdly settings file.");
    }
    if (isLegacy(data)) return data;
    if (!isObject(data) || data.kind !== "cmdly-settings" || !isObject(data.config)) {
      throw new Error("This is not a Cmdly settings file.");
    }
    return data;
  }

  function describeSource(bundle, fileName) {
    const parts = [];
    const version = isLegacy(bundle) ? bundle.cmdly : bundle.version;
    if (typeof version === "string" && version) parts.push(`Cmdly ${version}`);
    if (bundle.exported_at) {
      const when = new Date(bundle.exported_at);
      if (!isNaN(when.getTime())) parts.push(`exported ${when.toLocaleString()}`);
    }
    return parts.length ? `${fileName}, from ${parts.join(", ")}.` : `${fileName}.`;
  }

  // ---- the part picker both dialogs share -------------------------------

  /**
   * One switch per part. spec.unavailable is {part id: hint} for parts that
   * cannot be chosen, spec.hints {part id: text} replaces a part's own hint,
   * spec.onChange runs after any switch moves.
   * Returns {el, head, chosen(), setAll(on)}.
   */
  function partsPicker(spec) {
    const ui = Cmdly.ui;
    const unavailable = spec.unavailable || {};
    const hints = spec.hints || {};
    const toggles = new Map();

    const el = document.createElement("div");
    el.className = "settings-transfer-parts";

    function changed() {
      if (typeof spec.onChange === "function") spec.onChange();
    }

    SECTIONS.forEach((s) => {
      const off = unavailable[s.id];
      const t = ui.toggle({
        value: !off,
        disabled: !!off,
        ariaLabel: s.label,
        onChange: () => changed(),
      });
      toggles.set(s.id, t);
      el.appendChild(ui.field({
        label: s.label,
        control: t.el,
        className: "field-switch",
        hint: off || hints[s.id] || s.hint,
      }));
    });

    function setAll(on) {
      toggles.forEach((t, id) => { if (!unavailable[id]) t.setValue(on); });
      changed();
    }

    const head = document.createElement("div");
    head.className = "settings-transfer-head";
    head.appendChild(ui.label(spec.caption || "Parts"));
    head.appendChild(ui.actions([
      ui.button({ variant: "ghost", size: "sm", label: "All", onClick: () => setAll(true) }),
      ui.button({ variant: "ghost", size: "sm", label: "None", onClick: () => setAll(false) }),
    ]));

    function chosen() {
      return SECTIONS.map((s) => s.id).filter((id) => !unavailable[id] && toggles.get(id).getValue());
    }

    return { el, head, chosen, setAll };
  }

  function text(className, content) {
    const p = document.createElement("div");
    p.className = className;
    p.textContent = content;
    return p;
  }

  // ---- export ------------------------------------------------------------

  async function openExport() {
    const ui = Cmdly.ui;
    const target = await Cmdly.api.get("/api/settings/export/target").catch(() => ({}));

    const nameInput = ui.input({
      id: "settingsExportName",
      ariaLabel: "File name",
      value: (target && target.filename) || "",
      placeholder: "cmdly-settings.json",
      mono: true,
      autocomplete: false,
    });
    const dirInput = ui.input({
      id: "settingsExportDir",
      ariaLabel: "Folder",
      value: (target && target.dir) || "",
      placeholder: "~/Downloads",
      mono: true,
      autocomplete: false,
      spellcheck: false,
    });
    const secrets = ui.toggle({ ariaLabel: "Include passwords" });

    const body = document.createElement("div");
    body.className = "settings-transfer";
    body.appendChild(text("confirm-text", "Choose what goes into the file. Everything is " +
      "switched on, which is the whole setup: a backup, or the start on the next computer."));

    const picker = partsPicker({ caption: "What goes into the file", onChange: () => refresh() });
    body.appendChild(picker.head);
    body.appendChild(picker.el);

    body.appendChild(ui.field({ label: "File name", control: nameInput }));
    body.appendChild(ui.field({
      label: "Folder",
      control: dirInput,
      hint: "Created if it does not exist.",
    }));
    body.appendChild(ui.field({
      label: "Include passwords",
      control: secrets.el,
      className: "field-switch",
      hint: "The SSH passwords, in plain text. Off, the file names each connection " +
            "without its password, and the other computer asks on the first press. " +
            "Leave off for a file you pass on.",
    }));
    const msg = ui.message({ className: "dialog-msg" });
    body.appendChild(msg.el);

    const cancelBtn = ui.button({ variant: "secondary", label: "Cancel", onClick: () => dialog.close() });
    const saveBtn = ui.button({ variant: "primary", icon: "download", label: "Save", onClick: save });
    const dialog = ui.modal({ title: "Export settings", size: "lg", body, actions: [cancelBtn, saveBtn] });
    dialog.open();
    refresh();

    function refresh() {
      saveBtn.disabled = !picker.chosen().length;
    }

    async function save() {
      msg.hide();
      const sections = picker.chosen();
      if (!sections.length) return;
      ui.setBusy(saveBtn, true);
      try {
        const store = localStore();
        const res = await Cmdly.api.post("/api/settings/export", {
          filename: nameInput.value.trim(),
          dir: dirInput.value.trim(),
          include_secrets: secrets.getValue(),
          browser: store ? collectBrowser(store, sections) : {},
          sections,
        });
        dialog.close();
        ui.toast({ level: "info", title: "Settings exported", message: res.path });
      } catch (err) {
        msg.show((err && err.message) || "Export failed.", "err");
        ui.setBusy(saveBtn, false);
      }
    }
  }

  // ---- import ------------------------------------------------------------

  /** Ask for a settings file and open the import dialog for it. */
  function pickFile() {
    const input = document.createElement("input");
    input.type = "file";
    input.setAttribute("accept", ".json,application/json");
    input.hidden = true;
    document.body.appendChild(input);
    input.addEventListener("change", () => {
      input.remove();
      const file = input.files && input.files[0];
      if (!file) return;
      readFileText(file).then((content) => {
        openImport(parseBundle(content), file.name || "The file");
      }).catch((err) => {
        Cmdly.ui.toast({ level: "critical", message: (err && err.message) || "Could not read the settings file." });
      });
    });
    input.click();
  }

  function readFileText(file) {
    if (typeof file.text === "function") return file.text();
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ""));
      reader.onerror = () => reject(new Error("Could not read the settings file."));
      reader.readAsText(file);
    });
  }

  /** The import dialog for a parsed *bundle*. */
  function openImport(bundle, fileName) {
    const ui = Cmdly.ui;
    const present = new Set(sectionsInFile(bundle));
    const unavailable = {};
    SECTIONS.forEach((s) => { if (!present.has(s.id)) unavailable[s.id] = "Not in this file."; });
    const counts = describeParts(bundle);
    const hints = {};
    SECTIONS.forEach((s) => { if (counts[s.id]) hints[s.id] = `${counts[s.id]}. ${s.hint}`; });

    const body = document.createElement("div");
    body.className = "settings-transfer";
    body.appendChild(text("confirm-text", describeSource(bundle, fileName)));
    body.appendChild(text("confirm-text", bundle.secrets === true
      ? "The file carries passwords, and they replace the ones stored here."
      : "The file carries no passwords. The ones stored here are kept wherever " +
        "the connection (name, host and user) is still the same."));

    const picker = partsPicker({
      caption: "What to take from the file",
      unavailable,
      hints,
      onChange: () => refresh(),
    });
    body.appendChild(picker.head);
    body.appendChild(picker.el);

    const warn = ui.message({ className: "dialog-msg" });
    warn.show("The parts switched on replace the ones here. Programs that are " +
              "running keep running.", "warn");
    body.appendChild(warn.el);
    const msg = ui.message({ className: "dialog-msg" });
    body.appendChild(msg.el);

    const cancelBtn = ui.button({ variant: "secondary", label: "Cancel", onClick: () => dialog.close() });
    const importBtn = ui.button({ variant: "primary", icon: "upload", label: "Import", onClick: run });
    const dialog = ui.modal({ title: "Import settings", size: "lg", body, actions: [cancelBtn, importBtn] });
    dialog.open();
    refresh();

    function refresh() {
      importBtn.disabled = !picker.chosen().length;
    }

    async function run() {
      msg.hide();
      const sections = picker.chosen();
      if (!sections.length) return;
      ui.setBusy(importBtn, true);
      let res;
      try {
        res = await Cmdly.api.post("/api/settings/import", { bundle, sections });
      } catch (err) {
        msg.show((err && err.message) || "Import failed.", "err");
        ui.setBusy(importBtn, false);
        return;
      }
      const store = localStore();
      if (store) applyBrowser(store, bundle.browser, sections);
      dialog.close();
      await Cmdly.store.load().catch(() => {});
      showResult(res || {});
    }
  }

  /** What the import did, as a toast. Pure apart from the toast. */
  function resultText(res) {
    const n = res.counts || {};
    const taken = new Set(res.sections || []);
    const parts = [];
    if (taken.has("buttons")) parts.push(`${n.buttons} button${n.buttons === 1 ? "" : "s"}`);
    if (taken.has("companions")) parts.push(`${n.companions} companion${n.companions === 1 ? "" : "s"}`);
    if (taken.has("connections")) parts.push(`${n.connections} connection${n.connections === 1 ? "" : "s"}`);
    if (taken.has("appearance")) parts.push("the appearance");
    const lines = [parts.length ? `Now here: ${parts.join(", ")}.` : "Settings imported."];
    (res.warnings || []).forEach((w) => lines.push(w));
    return lines.join(" ");
  }

  function showResult(res) {
    Cmdly.ui.toast({
      level: (res.warnings || []).length ? "warning" : "info",
      title: "Settings imported",
      message: resultText(res),
    });
  }

  return {
    openExport,
    openImport,
    pickFile,
    BROWSER_KEYS,
    NOT_SETTINGS,
    SECTIONS,
    // Exported for the test suite.
    sectionOfKey,
    collectBrowser,
    applyBrowser,
    parseBundle,
    isLegacy,
    sectionsInFile,
    describeParts,
    resultText,
  };
})();
