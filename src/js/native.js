"use strict";
window.Cmdly = window.Cmdly || {};

/*
  Cmdly.native — the desktop window around the page.

  In the desktop app (cmdly/app.py) the page talks to its window over a
  QWebChannel object, window.cmdlyNative, and learns before its first script
  what the window can do, window.cmdlyNativeSupport:

    place     the app may place its windows (not on Wayland)
    pin       a window can be kept above others (not on Wayland)
    frost     the desktop behind a window can be blurred (macOS)
    vibrancy  the same, for the main window (macOS)
    unified   the title bar is part of the page (macOS): the page draws the
              header under the traffic lights and is the window's drag area

  In a plain browser none of this exists and every function here is a no-op,
  so the page works there too.
*/
Cmdly.native = (function () {
  function support() { return window.cmdlyNativeSupport || {}; }

  function bridge() {
    return (window.cmdlyNative && typeof window.cmdlyNative.startMove === "function")
      ? window.cmdlyNative : null;
  }

  function whenReady(fn) {
    if (bridge()) { fn(bridge()); return; }
    window.addEventListener("cmdly:native-ready", () => { if (bridge()) fn(bridge()); }, { once: true });
  }

  function canVibrancy() { return !!support().vibrancy; }

  function reducedTransparency() {
    try {
      return !!(window.matchMedia && window.matchMedia("(prefers-reduced-transparency: reduce)").matches);
    } catch (_e) {
      return false;
    }
  }

  let wantVibrancy = false;
  let asked = 0;

  /**
   * Vibrancy on or off. The page turns see-through only once the window has
   * said the blur is behind it, and solid before the blur goes: either way
   * round, the desktop never shows through sharp.
   */
  function setVibrancy(on) {
    wantVibrancy = !!on;
    const root = document.documentElement;
    const want = wantVibrancy && canVibrancy() && !reducedTransparency();
    const ticket = ++asked;
    if (!want) root.classList.remove("vibrant");
    whenReady((n) => {
      if (typeof n.setVibrancy !== "function") return;
      n.setVibrancy(want, Cmdly.theme.isDark(), (ok) => {
        if (ticket === asked) root.classList.toggle("vibrant", !!(want && ok));
      });
    });
  }

  /** The header is the window's title bar: drag to move, double-click to zoom. */
  function wireTitlebar(el) {
    if (!el) return;
    const interactive = (t) => t.closest("button, a, input, select, textarea, .ui-select-trigger, [data-no-drag]");
    el.addEventListener("pointerdown", (e) => {
      if (e.button !== 0 || interactive(e.target)) return;
      const n = bridge();
      if (n) { n.startMove(); e.preventDefault(); }
    });
    el.addEventListener("dblclick", (e) => {
      if (interactive(e.target)) return;
      const n = bridge();
      if (n && typeof n.toggleZoom === "function") n.toggleZoom();
    });
  }

  function init() {
    const root = document.documentElement;
    const s = support();
    if (s.platform) root.classList.add("platform-" + s.platform);
    if (s.unified) root.classList.add("unified-titlebar");
    if (window.qt && window.qt.webChannelTransport) root.classList.add("desktop-app");
    window.addEventListener("cmdly:themechange", () => setVibrancy(wantVibrancy));
    try {
      const media = window.matchMedia("(prefers-reduced-transparency: reduce)");
      const again = () => setVibrancy(wantVibrancy);
      if (typeof media.addEventListener === "function") media.addEventListener("change", again);
    } catch (_e) { /* an engine without the query: nothing to follow */ }
  }

  return { init, setVibrancy, wireTitlebar, canVibrancy, support, bridge, whenReady };
})();
