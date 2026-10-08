"use strict";
window.Cmdly = window.Cmdly || {};

/*
  Cmdly.settings — the settings sheet.

  Five pages behind one segmented control: Appearance (theme, the frosted window),
  Terminals (frosted or solid, own windows or frames in the app),
  Connections (the saved SSH connections), Data (moving a setup to another
  computer) and About. Every switch applies at once and is saved; there is no
  Save button to forget.
*/
Cmdly.settings = (function () {
  const store = () => Cmdly.store;
  let dialog = null;
  let page = "appearance";

  const PAGES = [
    { value: "appearance", label: "Look", icon: "palette" },
    { value: "terminals", label: "Terminals", icon: "square-terminal" },
    { value: "connections", label: "SSH", icon: "key-round" },
    { value: "data", label: "Data", icon: "hard-drive" },
    { value: "about", label: "About", icon: "info" },
  ];

  function ui() { return Cmdly.ui; }

  function switchRow(label, value, onChange, info, disabled) {
    const t = ui().toggle({ value, ariaLabel: label, disabled, onChange });
    return ui().field({ label, control: t.el, className: "field-switch", info });
  }

  function group(title, children) {
    const g = document.createElement("section");
    g.className = "group";
    if (title) {
      const h = document.createElement("div");
      h.className = "group-title";
      h.textContent = title;
      g.appendChild(h);
    }
    children.filter(Boolean).forEach((c) => g.appendChild(c));
    return g;
  }

  // ---- pages ------------------------------------------------------------------

  function appearance() {
    const st = store().state;
    const uiCfg = st.config.ui || {};
    const wrap = document.createElement("div");
    const cards = ui().optionCards({
      ariaLabel: "Theme",
      columns: 2,
      value: uiCfg.theme || "blue",
      options: Cmdly.theme.THEMES.map((t) => ({ id: t.id, label: t.label, desc: t.desc, swatch: t.swatch })),
      onChange: (id) => { Cmdly.theme.set(id); store().setUi({ theme: id }); },
    });
    wrap.appendChild(group("Theme", [cards.el]));
    const native = Cmdly.native;
    if (native && native.canFrost()) {
      wrap.appendChild(group("Window", [switchRow(
        "Solid window", uiCfg.frosted_window === false,
        (on) => store().setUi({ frosted_window: !on }),
        "By default the desktop shows through the window, tinted like frosted " +
        "glass, and blurred behind it too wherever the system can blur (macOS, " +
        "KDE's KWin on Linux; elsewhere the desktop reads through faintly). On: " +
        "a solid window. The system's own Reduce transparency setting makes it " +
        "solid everywhere.",
      )]));
    }
    return wrap;
  }

  function terminals() {
    const uiCfg = store().state.config.ui || {};
    const nativeWindows = !!(Cmdly.popouts && Cmdly.popouts.native());
    return group("Terminal windows", [
      switchRow("Frosted glass", uiCfg.frosted_terminals !== false,
        (on) => store().setUi({ frosted_terminals: on }),
        "Terminals of frosted glass, with what is behind them showing through, " +
        "or solid. A terminal in a window of its own frosts the desktop behind " +
        "it: blurred where the system can blur (macOS, KDE's KWin on Linux), " +
        "tinted on other Linux desktops — never sharp."),
      nativeWindows ? switchRow("Open inside the Cmdly window", !!uiCfg.terminals_in_app,
        (on) => store().setUi({ terminals_in_app: on }),
        "Off (the default): every terminal opens as a window of its own, which " +
        "can go anywhere, another screen included, and be pinned above Cmdly.\n\n" +
        "On: terminals open as frames floating inside the Cmdly window. Drag one " +
        "past the window's edge and it carries on as a window of its own.") : null,
    ]);
  }

  function connections() {
    const st = store().state;
    const wrap = document.createElement("div");
    const list = document.createElement("div");
    list.className = "list";
    if (!st.connections.length) {
      const none = document.createElement("div");
      none.className = "list-empty";
      none.textContent = "No saved connections yet.";
      list.appendChild(none);
    }
    st.connections.forEach((c) => {
      const row = document.createElement("button");
      row.type = "button";
      row.className = "list-row";
      const icon = document.createElement("span");
      icon.className = "list-icon";
      icon.appendChild(ui().icon("server", 15));
      const text = document.createElement("span");
      text.className = "list-text";
      const name = document.createElement("span");
      name.className = "list-name";
      name.textContent = c.name;
      const sub = document.createElement("span");
      sub.className = "list-sub";
      sub.textContent = `${c.username ? c.username + "@" : ""}${c.host}${c.port && c.port !== 22 ? ":" + c.port : ""}` +
        (c.key_path ? " · key" : c.has_password ? " · password" : "");
      text.append(name, sub);
      const users = st.config.buttons.filter((b) => b.connection === c.name).length;
      const badge = document.createElement("span");
      badge.className = "list-badge";
      badge.textContent = users ? `${users} button${users > 1 ? "s" : ""}` : "";
      const chev = ui().icon("chevron-right", 14);
      chev.classList.add("list-chev");
      row.append(icon, text, badge, chev);
      row.addEventListener("click", () => Cmdly.connections.edit(c).then(repaint));
      list.appendChild(row);
    });
    wrap.appendChild(group("Saved SSH connections", [list]));
    wrap.appendChild(ui().actions([ui().button({
      variant: "secondary", icon: "plus", label: "Add a connection",
      onClick: () => Cmdly.connections.edit(null).then(repaint),
    }), ui().button({
      variant: "secondary", icon: "activity", label: "Ping a computer",
      title: "Show a computer in the main window that is only pinged, without a connection",
      onClick: () => { Cmdly.companion.openDialog(null); },
    })]));
    return wrap;
  }

  function data() {
    const wrap = document.createElement("div");
    const transfer = Cmdly.settingsTransfer;
    wrap.appendChild(group("Move a setup to another computer", [
      ui().actions([
        ui().button({
          variant: "secondary", icon: "download", label: "Export setup…",
          title: "Save the buttons, companions, connections and appearance to a file",
          onClick: () => transfer.openExport(),
        }),
        ui().button({
          variant: "secondary", icon: "upload", label: "Import setup…",
          title: "Take over a setup exported on another computer",
          onClick: () => transfer.pickFile(),
        }),
      ]),
    ]));
    const path = document.createElement("code");
    path.className = "path";
    path.textContent = "~/.cmdly/config.json";
    Cmdly.api.get("/api/about").then((a) => { path.textContent = a.config; }).catch(() => {});
    wrap.appendChild(group("Stored in", [path]));
    return wrap;
  }

  /* The update check, filled into *slot* once GET /api/update has answered
     (from the backend's cache: opening Settings never waits on GitHub).
     Nothing at all while no repository is set — there is nothing to check,
     so there is nothing to switch or to report either. */
  function updates(slot) {
    if (!Cmdly.update) return;
    const msg = ui().message({ className: "dialog-msg" });

    function describe(s) {
      if (s.enabled === false) { msg.hide(); return; }
      if (s.update_available && s.latest) {
        msg.show(`Cmdly ${s.latest} is available` +
          (s.skipped === s.latest ? " (skipped)." : "."), "warn");
      } else if (s.error) {
        msg.show(`The last check failed: ${s.error}`, "err");
      } else if (s.checked_at) {
        msg.show(`Up to date. Last checked ${new Date(s.checked_at * 1000).toLocaleString()}.`, "ok");
      } else {
        msg.hide();
      }
    }

    Cmdly.api.get("/api/update").then((status) => {
      if (!status || status.configured === false || !slot.isConnected) return;
      Cmdly.update.note(status);
      const checkBtn = ui().button({
        variant: "secondary", icon: "refresh-cw", label: "Check now",
        disabled: status.enabled === false,
        onClick: () => {
          ui().setBusy(checkBtn, true);
          Cmdly.update.check({ refresh: true, manual: true })
            .then((s) => { if (s) describe(s); })
            .catch((error) => msg.show(error.message, "err"))
            .finally(() => ui().setBusy(checkBtn, false));
        },
      });
      const toggle = switchRow("Check for updates", status.enabled !== false, (on) => {
        const current = store().state.config.updates || {};
        checkBtn.disabled = !on;
        store().save({ updates: Object.assign({}, current, { check: on }) })
          .then(() => Cmdly.api.get("/api/update"))
          .then((s) => { Cmdly.update.note(s); describe(s); })
          .catch(() => {});
      }, "Looks for a newer Cmdly release on GitHub a few seconds after start " +
         "(at most every few hours) and says so once per release. Updating " +
         "stays manual. Off: Cmdly asks nothing at all.");
      slot.appendChild(group("Updates", [toggle, ui().actions(checkBtn), msg.el]));
      describe(status);
      ui().refreshIcons();
    }).catch(() => {});
  }

  function about() {
    const wrap = document.createElement("div");
    wrap.className = "about";
    const hero = document.createElement("div");
    hero.className = "about-hero";
    const img = document.createElement("img");
    img.src = "assets/icon.png";
    img.alt = "";
    img.className = "about-icon";
    const name = document.createElement("div");
    name.className = "about-name";
    name.textContent = "Cmdly";
    const ver = document.createElement("div");
    ver.className = "about-version";
    ver.textContent = `Version ${store().state.version}`;
    const tag = document.createElement("div");
    tag.className = "about-tag";
    tag.textContent = "One-press buttons for the programs you start again and again, here or over SSH.";
    hero.append(img, name, ver, tag);
    wrap.appendChild(hero);
    const updatesSlot = document.createElement("div");
    wrap.appendChild(updatesSlot);
    updates(updatesSlot);
    const libs = document.createElement("div");
    libs.className = "list";
    wrap.appendChild(group("Built with", [libs]));
    Cmdly.api.get("/api/about").then((a) => {
      ver.textContent = `Version ${a.version} · ${a.os}`;
      (a.libraries || []).forEach((lib) => {
        const row = document.createElement("div");
        row.className = "list-row is-static";
        const text = document.createElement("span");
        text.className = "list-text";
        const n = document.createElement("span");
        n.className = "list-name";
        n.textContent = lib.version ? `${lib.name} ${lib.version}` : lib.name;
        const s = document.createElement("span");
        s.className = "list-sub";
        s.textContent = lib.role;
        text.append(n, s);
        const badge = document.createElement("span");
        badge.className = "list-badge";
        badge.textContent = lib.license;
        row.append(text, badge);
        libs.appendChild(row);
      });
    }).catch(() => {});
    return wrap;
  }

  const BUILDERS = { appearance, terminals, connections, data, about };

  // ---- the sheet ----------------------------------------------------------------

  let bodyEl = null;

  function repaint() {
    if (!bodyEl) return;
    ui().clear(bodyEl);
    bodyEl.appendChild(BUILDERS[page]());
    ui().refreshIcons();
  }

  function open(which) {
    if (dialog) return;
    if (which && BUILDERS[which]) page = which;
    const body = document.createElement("div");
    body.className = "settings";
    const tabs = ui().segment({
      ariaLabel: "Settings page",
      className: "settings-tabs",
      value: page,
      options: PAGES,
      onChange: (next) => { page = next; repaint(); },
    });
    body.appendChild(tabs.el);
    bodyEl = document.createElement("div");
    bodyEl.className = "settings-page";
    body.appendChild(bodyEl);
    repaint();
    const off = [store().on("connections", () => { if (page === "connections") repaint(); })];
    dialog = ui().modal({
      title: "Settings",
      size: "lg",
      body,
      onClose: () => { dialog = null; bodyEl = null; off.forEach((fn) => fn()); },
    });
    dialog.el.classList.add("settings-overlay");
    dialog.open();
  }

  return { open };
})();
