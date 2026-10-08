"use strict";
window.Cmdly = window.Cmdly || {};

/*
  Cmdly.native — the desktop window around the page.

  In the desktop app (cmdly/app.py) the page talks to its window over a
  QWebChannel object, window.cmdlyNative, and learns before its first script
  what the window can do, window.cmdlyNativeSupport:

    place     the app may place its windows (not on Wayland)
    pin       a window can be kept above others (not on Wayland)
    frost     the desktop can show through a window, frosted by the page's
              own tint (themes.css): the main window's frost and a terminal
              window's frosted glass alike. macOS blurs the desktop behind
              the window (NSVisualEffectView); KWin does where it runs
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

  function canFrost() { return !!support().frost; }

  function reducedTransparency() {
    try {
      return !!(window.matchMedia && window.matchMedia("(prefers-reduced-transparency: reduce)").matches);
    } catch (_e) {
      return false;
    }
  }

  let wantFrost = false;
  let asked = 0;

  /**
   * The frosted window on or off. The page turns see-through only once the
   * window has said the desktop can show through, and solid before it asks:
   * either way round, the desktop never shows through sharp.
   */
  function setFrost(on) {
    wantFrost = !!on;
    const root = document.documentElement;
    const want = wantFrost && canFrost() && !reducedTransparency();
    const ticket = ++asked;
    if (!want) root.classList.remove("frosted-window");
    whenReady((n) => {
      if (typeof n.setFrosted !== "function") return;
      n.setFrosted(want, Cmdly.theme.isDark(), (ok) => {
        if (ticket === asked) root.classList.toggle("frosted-window", !!(want && ok));
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

  /**
   * The pin beside the filter in the status line: the window itself kept
   * above other programs', or not. Only where the window system has a pin at
   * all (not on Wayland, not in a plain browser), and unlike a terminal's
   * pin (popout-page.js), which is kept above Cmdly while Cmdly is in
   * front, this one stays above everything as long as it is on.
   */
  function wirePin(slot) {
    if (!slot) return;
    whenReady((n) => {
      if (!support().pin || typeof n.setPinned !== "function") return;
      const btn = Cmdly.ui.iconButton("pin", {
        title: "Keep the Cmdly window above other programs",
        ariaLabel: "Keep the Cmdly window above other programs",
      });
      let pinned = false;
      function paint(on) {
        pinned = !!on;
        btn.classList.toggle("active", pinned);
        btn.setAttribute("aria-pressed", pinned ? "true" : "false");
        btn.title = pinned ? "Kept above other programs. Click to stop"
          : "Keep the Cmdly window above other programs";
      }
      btn.addEventListener("click", () => n.setPinned(!pinned, paint));
      paint(false);
      slot.replaceChildren(btn);
    });
  }

  function init() {
    const root = document.documentElement;
    const s = support();
    if (s.platform) root.classList.add("platform-" + s.platform);
    if (s.unified) root.classList.add("unified-titlebar");
    if (window.qt && window.qt.webChannelTransport) root.classList.add("desktop-app");
    window.addEventListener("cmdly:themechange", () => setFrost(wantFrost));
    try {
      const media = window.matchMedia("(prefers-reduced-transparency: reduce)");
      const again = () => setFrost(wantFrost);
      if (typeof media.addEventListener === "function") media.addEventListener("change", again);
    } catch (_e) { /* an engine without the query: nothing to follow */ }
  }

  return { init, setFrost, wireTitlebar, wirePin, canFrost, support, bridge, whenReady };
})();
