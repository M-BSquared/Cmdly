"use strict";
/*
  Vendor bundles that are not needed to open the app.

  xterm and its fit addon (~300 KB) are only needed once a terminal is shown,
  so they are fetched the first time one is, not on every launch.

  * Once per bundle, however many callers ask at once: the promise is cached
    under its src.
  * A failed load is not cached, so the next caller retries.
  * `terminalReady()` stays synchronous and never starts a load, for code that
    only wants to clean up.
*/
window.Cmdly = window.Cmdly || {};
Cmdly.lazy = (function () {
  /** src -> Promise, resolved when that bundle has run. */
  const pending = new Map();

  function script(src) {
    if (pending.has(src)) return pending.get(src);
    const promise = new Promise((resolve, reject) => {
      if (typeof document === "undefined") {
        reject(new Error("no document"));
        return;
      }
      const el = document.createElement("script");
      el.src = src;
      // Injected scripts run in the order they were added: xterm, then its addon.
      el.async = false;
      el.addEventListener("load", () => resolve());
      el.addEventListener("error", () => {
        pending.delete(src);
        el.remove();
        reject(new Error(`could not load ${src}`));
      });
      document.head.appendChild(el);
    });
    pending.set(src, promise);
    return promise;
  }

  /** Is xterm (and its fit addon) here already? Synchronous. */
  function terminalReady() {
    return typeof window !== "undefined"
      && typeof window.Terminal === "function"
      && !!(window.FitAddon && window.FitAddon.FitAddon);
  }

  /** xterm + the fit addon, in that order: the addon needs the base. */
  function terminal() {
    if (terminalReady()) return Promise.resolve(window.Terminal);
    return script("vendor/xterm.js")
      .then(() => script("vendor/xterm-addon-fit.js"))
      .then(() => window.Terminal);
  }

  return { script, terminal, terminalReady };
})();
