"use strict";
window.Cmdly = window.Cmdly || {};

/*
  Cmdly.theme — which palette is on <html>.

  A theme is the data-theme attribute (css/themes.css). "auto" is not a
  palette but a rule: green while the system is in dark mode, light while it
  is light, followed live. What is actually applied is mirrored into
  localStorage ("cmdly.theme") so a terminal window of its own paints in it
  before its first frame (popout.html), and follows it from there (the
  storage event, js/popout-page.js).
*/
Cmdly.theme = (function () {
  const KEY = "cmdly.theme";
  const THEMES = [
    { id: "auto", label: "Automatic", desc: "Green in dark mode, light in light mode",
      swatch: ["#0E1013", "#5CCB7A", "#F2F3F6", "#1C1F25"] },
    { id: "green", label: "Green", desc: "Graphite and the icon's neon green",
      swatch: ["#0E1013", "#1A1E24", "#5CCB7A"] },
    { id: "blue", label: "Blue", desc: "Graphite and blue", swatch: ["#0E1013", "#1A1E24", "#3B9EFF"] },
    { id: "orange", label: "Orange", desc: "Graphite and amber", swatch: ["#0E1013", "#1A1E24", "#F58A2B"] },
    { id: "pink", label: "Pink", desc: "Graphite and magenta", swatch: ["#0E1013", "#1A1E24", "#F0509B"] },
    { id: "light", label: "Light", desc: "White and graphite", swatch: ["#F2F3F6", "#FFFFFF", "#1C1F25"] },
    { id: "light-orange", label: "Light orange", desc: "White and burnt orange",
      swatch: ["#F2F3F6", "#FFFFFF", "#CE5E00"] },
  ];
  const DARK = new Set(["green", "blue", "orange", "pink"]);

  let chosen = "blue";
  let media = null;

  function systemDark() {
    try {
      return !!(window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches);
    } catch (_e) {
      return true;
    }
  }

  /** The palette a choice resolves to right now. */
  function resolve(id) {
    if (id === "auto") return systemDark() ? "green" : "light";
    return THEMES.some((t) => t.id === id) ? id : "green";
  }

  function paint() {
    const applied = resolve(chosen);
    const root = document.documentElement;
    const before = root.getAttribute("data-theme");
    if (applied === "light") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", applied);
    root.classList.toggle("theme-dark", DARK.has(applied));
    try { localStorage.setItem(KEY, applied); } catch (_e) { /* windows of their own stay default */ }
    if (before !== root.getAttribute("data-theme")) {
      window.dispatchEvent(new CustomEvent("cmdly:themechange", { detail: { theme: applied } }));
    }
  }

  /** Apply a choice from the settings (an id of THEMES). */
  function set(id) {
    chosen = THEMES.some((t) => t.id === id) ? id : "blue";
    if (!media && window.matchMedia) {
      media = window.matchMedia("(prefers-color-scheme: dark)");
      const onChange = () => { if (chosen === "auto") paint(); };
      if (typeof media.addEventListener === "function") media.addEventListener("change", onChange);
      else if (typeof media.addListener === "function") media.addListener(onChange);
    }
    paint();
  }

  /** Whether the applied palette is a dark one. */
  function isDark() { return DARK.has(resolve(chosen)); }

  return { THEMES, set, resolve, isDark, current: () => chosen, KEY };
})();
