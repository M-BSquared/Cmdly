"use strict";
window.Cmdly = window.Cmdly || {};

/*
  Cmdly.app — boot.

  Reads the settings, applies the appearance (theme, vibrancy, how terminal
  windows open and look), mounts the companion card and the shelf, and
  keeps the status line under them. Every later change to the settings comes
  back through the store's "config" event and is applied again here.
*/
Cmdly.app = (function () {
  const store = () => Cmdly.store;
  let statusTimer = null;

  function applyUi() {
    const ui = store().state.config.ui || {};
    Cmdly.theme.set(ui.theme || "blue");
    Cmdly.native.setVibrancy(ui.vibrancy !== false);
    if (Cmdly.termWindows) Cmdly.termWindows.setFrosted(ui.frosted_terminals !== false);
    if (Cmdly.popouts) Cmdly.popouts.setInApp(!!ui.terminals_in_app);
  }

  function wireStatus() {
    const text = document.getElementById("status-text");
    const output = document.getElementById("status-output");
    store().on("status", (s) => {
      if (statusTimer) clearTimeout(statusTimer);
      text.textContent = s && s.text ? s.text : "";
      text.dataset.kind = (s && s.kind) || "";
      text.title = text.textContent;
      text.classList.remove("is-fading");
      // A confirmation is a moment, not a state: it fades after a while.
      if (s && s.text) statusTimer = setTimeout(() => text.classList.add("is-fading"), 6000);
    });
    store().on("output", (body) => {
      output.textContent = body || "";
      output.hidden = !body;
    });
  }

  function boot() {
    Cmdly.native.init();
    Cmdly.native.wireTitlebar(document.getElementById("titlebar"));
    document.getElementById("btn-settings").addEventListener("click", () => Cmdly.settings.open());
    // Cmd/Ctrl + , opens the settings, as in every Mac app.
    document.addEventListener("keydown", (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === ",") { e.preventDefault(); Cmdly.settings.open(); }
    });
    if (Cmdly.ui.watchSelects) Cmdly.ui.watchSelects();
    wireStatus();
    store().on("config", applyUi);
    Cmdly.companion.mount(document.getElementById("companion"));
    Cmdly.shelf.mount(document.getElementById("view"));
    store().startPolling();
    store().load().catch((error) => {
      Cmdly.ui.toast({ level: "critical", title: "Cmdly could not start", message: error.message });
    });
    // A newer release puts a dot on the settings button; the dialog itself
    // comes a few seconds after boot, in the background (Cmdly.update).
    if (Cmdly.update) {
      const settingsBtn = document.getElementById("btn-settings");
      Cmdly.update.onChange((version) => {
        settingsBtn.classList.toggle("has-update", !!version);
        settingsBtn.title = version ? `Settings · Cmdly ${version} is available` : "Settings";
      });
      Cmdly.update.init();
    }
    Cmdly.ui.refreshIcons();
    document.documentElement.classList.add("is-ready");
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();

  return { applyUi };
})();
