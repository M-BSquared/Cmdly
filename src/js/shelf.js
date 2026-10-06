"use strict";
window.Cmdly = window.Cmdly || {};

/*
  Cmdly.shelf — the buttons, and the form that edits one.

  Two views, never both: the SHELF (the buttons plus Add) and the EDITOR (one
  button's fields). Editing is a view rather than an expanding row because a
  form beside a list of buttons in a narrow window reads as neither.

  A row: the launch button (label, and where it runs as an icon at its far
  end), then a warning triangle when its last press failed (the reason in its
  popover), a green dot while it runs, the arrow into its terminal, and the
  pencil, which is a stop button while its program runs. Removing a button is
  the last thing in its editor: a trash can beside the launch button would be
  one mis-click from killing a running program.

  Long explanations are never printed under a field: they are behind the (i)
  beside its caption, so a form reads as a form.
*/
Cmdly.shelf = (function () {
  const store = () => Cmdly.store;
  const L = () => Cmdly.launch;
  const MAX_BUTTONS = 24;
  const NEW = "__new__";

  let viewEl = null;
  let editing = null;      // the draft being edited, or null on the shelf
  let dragId = null;
  // Rows already on screen: only a row that is new comes in with the entry
  // animation, so a repaint (a ping, a session going up) never makes the
  // whole list flicker.
  const shown = new Set();

  const HINTS = {
    local: {
      folderPlaceholder: "~/mission",
      folder: "Entered before the program starts. Leave it empty to start in your home folder.",
      program: "Run by your own login shell on this computer, so pipelines and " +
               "arguments work as typed. It runs as you.",
      terminal: "On: the program runs in a terminal of this button's own. Pressing " +
                "the button again runs it again in that same terminal; the arrow " +
                "beside the button shows the window. Stop it with Ctrl-C, the " +
                "window's power button, or the stop button that replaces the pencil " +
                "while it runs.\n\nOff: it starts in the background with nothing to " +
                "watch. Either way it is stopped when Cmdly quits.",
    },
    ssh: {
      folderPlaceholder: "/home/pi/mission",
      folder: "Entered before the program starts. Leave it empty to start in the account's home folder.",
      program: "Run by the remote login shell, so pipelines and arguments work as " +
               "typed. It runs as the connection's user.",
      terminal: "On: the program runs in an SSH session of this button's own. " +
                "Pressing the button again runs it again in that same terminal; the " +
                "arrow beside the button shows the window. The session lasts as long " +
                "as Cmdly does.\n\nOff: it is started with nohup and detached, so it " +
                "keeps running after Cmdly quits, with nothing to watch or stop from here.",
    },
  };

  function buttons() { return store().state.config.buttons || []; }

  function saveButtons(list) { return store().save({ buttons: list }); }

  // ---- the shelf ----------------------------------------------------------------

  function visibleButtons() {
    const st = store().state;
    if (!st.config.ui || !st.config.ui.reachable_only) return buttons();
    return buttons().filter((b) => Cmdly.companion.reachableAnywhere(b));
  }

  function render() {
    if (!viewEl || editing) return;
    const ui = Cmdly.ui;
    const all = buttons();
    const shown = visibleButtons();
    const scrollTop = viewEl.scrollTop;
    ui.clear(viewEl);
    viewEl.dataset.view = "shelf";

    const head = document.createElement("div");
    head.className = "section-head";
    const title = document.createElement("h2");
    title.className = "section-title";
    title.textContent = "Commands";
    head.appendChild(title);
    const count = document.createElement("span");
    count.className = "section-count";
    count.textContent = shown.length === all.length ? `${all.length}` : `${shown.length} of ${all.length}`;
    head.appendChild(count);
    const spacer = document.createElement("span");
    spacer.className = "spacer";
    head.appendChild(spacer);
    const filterOn = !!(store().state.config.ui || {}).reachable_only;
    const filter = ui.iconButton(filterOn ? "filter-x" : "filter", {
      className: "icon-btn" + (filterOn ? " active" : ""),
      title: filterOn ? "Hiding SSH buttons whose computer above is offline. Click to show all"
        : "Hide SSH buttons whose computer above is offline",
      ariaLabel: "Hide buttons that cannot be reached",
      onClick: () => store().setUi({ reachable_only: !filterOn }),
    });
    const slot = document.getElementById("status-filter");
    if (slot) slot.replaceChildren(filter); else head.appendChild(filter);
    head.appendChild(ui.button({
      variant: "primary", size: "sm", icon: "plus", label: "Add",
      className: "add-btn",
      disabled: all.length >= MAX_BUTTONS,
      title: all.length >= MAX_BUTTONS ? `A shelf holds up to ${MAX_BUTTONS} buttons` : "Add a button",
      onClick: () => addButton(),
    }));
    viewEl.appendChild(head);

    if (!all.length) {
      viewEl.appendChild(emptyState("rocket", "No buttons yet",
        "Add one for each program you start again and again, on this computer or on another over SSH.",
        ui.button({ variant: "primary", icon: "plus", label: "Add a button", onClick: () => addButton() })));
    } else if (!shown.length) {
      viewEl.appendChild(emptyState("filter", "Nothing can run right now",
        "Every button runs over SSH on a computer shown above that is offline.",
        ui.button({ variant: "secondary", label: "Show all", onClick: () => store().setUi({ reachable_only: false }) })));
    } else {
      const list = document.createElement("div");
      list.className = "shelf";
      list.setAttribute("role", "list");
      shown.forEach((entry) => list.appendChild(row(entry)));
      viewEl.appendChild(list);
    }

    const missing = missingConnections();
    if (missing.length) {
      const note = document.createElement("div");
      note.className = "shelf-note";
      note.appendChild(ui.icon("circle-alert", 14));
      const text = document.createElement("span");
      text.textContent = `Not set up on this computer: ${missing.map((n) => `“${n}”`).join(", ")}. ` +
        "Press a button that uses one to enter its address and login once.";
      note.appendChild(text);
      viewEl.appendChild(note);
    }
    ui.refreshIcons();
    viewEl.scrollTop = scrollTop;
  }

  function emptyState(iconName, heading, text, action) {
    const ui = Cmdly.ui;
    const box = document.createElement("div");
    box.className = "empty-state";
    const art = document.createElement("div");
    art.className = "empty-art";
    art.appendChild(ui.icon(iconName, 26));
    const h = document.createElement("div");
    h.className = "empty-title";
    h.textContent = heading;
    const p = document.createElement("div");
    p.className = "empty-text";
    p.textContent = text;
    box.append(art, h, p);
    if (action) box.appendChild(action);
    return box;
  }

  /** SSH connections the shelf names that this computer has not saved. */
  function missingConnections() {
    const st = store().state;
    if (!st.connectionsLoaded) return [];
    const known = new Set(st.connections.map((c) => c.name));
    const out = [];
    buttons().forEach((b) => {
      if (L().coerceTarget(b) !== L().TARGET_SSH) return;
      const name = String(b.connection || "").trim();
      if (name && !known.has(name) && out.indexOf(name) < 0) out.push(name);
    });
    return out;
  }

  function row(entry) {
    const ui = Cmdly.ui;
    const session = L().sessionName(entry);
    const running = store().isLive(session);
    const stopping = L().isClosing(entry);
    const failure = L().errorOf(entry);
    const terminal = L().coerceMode(entry) === L().MODE_TERMINAL;
    const local = L().isLocal(entry);

    const el = document.createElement("div");
    el.className = "shelf-row";
    el.setAttribute("role", "listitem");
    el.dataset.id = entry.id;
    if (!shown.has(entry.id)) {
      el.classList.add("is-new");
      shown.add(entry.id);
    }
    el.classList.toggle("is-running", running);
    el.classList.toggle("is-failed", !!failure);

    const preview = L().previewLine(entry) || entry.command;
    // The bar holds two controls: the label starts the command, the arrow
    // beside the where-icon starts it and shows its terminal.
    const bar = document.createElement("div");
    bar.className = "launch";
    const launchBtn = document.createElement("button");
    launchBtn.type = "button";
    launchBtn.className = "launch-main";
    launchBtn.title = running
      ? `${L().restarts(entry) ? "Stop it with Ctrl-C and start it again" : "Run it again"} in its terminal.\n${preview}`
      : preview;
    launchBtn.setAttribute("aria-label", running
      ? `${L().restarts(entry) ? "Restart" : "Run again"}: ${entry.label}` : `Launch ${entry.label}`);
    const label = document.createElement("span");
    label.className = "launch-label";
    label.textContent = entry.label;
    const whereIcon = document.createElement("span");
    whereIcon.className = "launch-where";
    whereIcon.title = (local ? "Runs on this computer" : `Runs on ${entry.connection || "an SSH connection"} over SSH`)
      + (terminal ? ", in a terminal" : ", in the background");
    whereIcon.appendChild(ui.icon(local ? "laptop" : "server", 14));
    launchBtn.append(label, whereIcon);
    launchBtn.addEventListener("click", () => L().launch(entry, bar));
    bar.appendChild(launchBtn);
    if (terminal) {
      const goBtn = ui.iconButton("chevron-right", {
        className: "icon-btn launch-go",
        ariaLabel: running ? `Show the terminal of ${entry.label}` : `Launch ${entry.label} and show its terminal`,
        title: running ? "Show its terminal" : "Start it and show its terminal",
        onClick: () => L().launchAndOpen(entry, bar),
      });
      bar.appendChild(goBtn);
    }
    el.appendChild(bar);

    const tools = document.createElement("div");
    tools.className = "row-tools";
    if (failure) {
      tools.appendChild(ui.infoHint({
        icon: "triangle-alert", size: 15, className: "row-error",
        title: `${entry.label} did not run`, text: failure,
        ariaLabel: `Why ${entry.label} did not run`,
      }));
    }
    if (running) {
      const dot = document.createElement("span");
      dot.className = "run-dot";
      dot.title = "Running";
      tools.appendChild(dot);
    }
    if (running || stopping) {
      const stopBtn = ui.iconButton("square", {
        className: "icon-btn row-stop",
        ariaLabel: `Stop ${entry.label}`,
        title: stopping ? "Stopping" : "Stop it with Ctrl-C and close its terminal",
        onClick: () => L().stop(entry),
      });
      if (stopping) ui.setBusy(stopBtn, true);
      tools.appendChild(stopBtn);
    } else {
      tools.appendChild(ui.iconButton("pencil", {
        ariaLabel: `Edit ${entry.label}`, title: "Edit",
        onClick: () => edit(Object.assign({}, entry), false),
      }));
    }
    el.appendChild(tools);
    wireDrag(el, entry);
    return el;
  }

  /** Reorder by dragging a row by its free space (not its buttons). */
  function wireDrag(el, entry) {
    el.draggable = true;
    el.addEventListener("dragstart", (e) => {
      if (e.target !== el) { e.preventDefault(); return; }
      dragId = entry.id;
      el.classList.add("is-dragging");
      try { e.dataTransfer.effectAllowed = "move"; e.dataTransfer.setData("text/plain", entry.id); } catch (_e) {}
    });
    el.addEventListener("dragend", () => {
      dragId = null;
      el.classList.remove("is-dragging");
      document.querySelectorAll(".shelf-row.drop-before, .shelf-row.drop-after")
        .forEach((r) => r.classList.remove("drop-before", "drop-after"));
    });
    el.addEventListener("dragover", (e) => {
      if (!dragId || dragId === entry.id) return;
      e.preventDefault();
      const box = el.getBoundingClientRect();
      const after = e.clientY > box.top + box.height / 2;
      el.classList.toggle("drop-after", after);
      el.classList.toggle("drop-before", !after);
    });
    el.addEventListener("dragleave", () => el.classList.remove("drop-before", "drop-after"));
    el.addEventListener("drop", (e) => {
      if (!dragId || dragId === entry.id) return;
      e.preventDefault();
      const after = el.classList.contains("drop-after");
      const list = buttons().slice();
      const from = list.findIndex((b) => b.id === dragId);
      if (from < 0) return;
      const [moved] = list.splice(from, 1);
      let to = list.findIndex((b) => b.id === entry.id);
      if (after) to += 1;
      list.splice(to, 0, moved);
      saveButtons(list);
    });
  }

  function addButton() {
    const all = buttons();
    const last = all.length ? all[all.length - 1] : null;
    const conns = store().state.connections;
    // A new button starts where the last one runs: a shelf is usually
    // several programs on the same computer.
    edit({
      id: L().newId("b"),
      label: "",
      target: last ? last.target : L().TARGET_LOCAL,
      connection: (last && last.connection) || (conns.length ? conns[0].name : ""),
      directory: last ? last.directory : "",
      command: "",
      mode: L().MODE_TERMINAL,
      restart: false,
    }, true);
  }

  // ---- the editor ---------------------------------------------------------------

  function setInfo(fieldEl, title, text) {
    const btn = fieldEl.querySelector(".ui-info");
    if (btn && btn.cmdlyPopover) btn.cmdlyPopover.setContent({ title, text });
  }

  function setHint(fieldEl, text) {
    let hint = fieldEl.querySelector(".field-hint");
    if (!hint && text) {
      hint = document.createElement("span");
      hint.className = "field-hint";
      fieldEl.appendChild(hint);
    }
    if (!hint) return;
    hint.textContent = text || "";
    hint.hidden = !text;
  }

  /**
   * One button's form. `draft` is a COPY: nothing reaches the shelf until
   * Save, so Cancel really cancels. `isNew`: Save appends rather than replaces.
   */
  function edit(draft, isNew) {
    const ui = Cmdly.ui;
    editing = draft;
    draft.target = L().coerceTarget(draft);
    let wantedMode = L().coerceMode(draft);
    ui.clear(viewEl);
    viewEl.dataset.view = "editor";
    viewEl.scrollTop = 0;
    const st = store().state;
    const conns = st.connections;

    const head = document.createElement("div");
    head.className = "section-head editor-head";
    head.appendChild(ui.iconButton("chevron-left", {
      className: "icon-btn back-btn", title: "Back to the buttons", ariaLabel: "Back",
      onClick: () => close(),
    }));
    const title = document.createElement("h2");
    title.className = "section-title";
    title.textContent = isNew ? "New button" : "Edit button";
    head.appendChild(title);
    viewEl.appendChild(head);

    const form = document.createElement("div");
    form.className = "editor";

    // -- what it is
    const group1 = group("Button");
    group1.appendChild(ui.field({
      label: "Label",
      control: ui.input({ value: draft.label, placeholder: "Start mission", ariaLabel: "Label",
        autocomplete: false, onInput: (v) => { draft.label = v; } }),
      info: "What the button says. Left empty, it shows the command itself.",
    }));
    const where = ui.segment({
      ariaLabel: "Where it runs",
      value: draft.target,
      options: L().TARGETS,
      onChange: (next) => { draft.target = next; paintTarget(); paintPreview(); },
    });
    group1.appendChild(ui.field({ label: "Runs on", control: where.el }));

    const sshBox = document.createElement("div");
    sshBox.className = "ssh-box";
    const connOptions = conns.map((c) => ({
      value: c.name, label: c.username ? `${c.name} (${c.username}@${c.host})` : c.name,
    }));
    const named = String(draft.connection || "").trim();
    if (named && !conns.some((c) => c.name === named)) {
      connOptions.unshift({ value: named, label: `${named} (not set up on this computer)` });
    }
    connOptions.push({ value: NEW, label: "New connection…" });
    const connSel = ui.select({
      ariaLabel: "SSH connection",
      options: connOptions,
      value: (conns.length || named) ? named || conns[0].name : NEW,
      onChange: () => { renderNew(); paintPreview(); },
    });
    sshBox.appendChild(ui.field({
      label: "Connection", control: connSel,
      info: "A saved SSH connection, or a new one typed in below. Cmdly's " +
            "backend keeps the password; the button only stores the connection's name.",
    }));
    const newWrap = document.createElement("div");
    newWrap.className = "inset-group";
    sshBox.appendChild(newWrap);
    group1.appendChild(sshBox);
    form.appendChild(group1);

    let newForm = null;
    function pickedNew() { return draft.target === L().TARGET_SSH && connSel.value === NEW; }
    function renderNew() {
      ui.clear(newWrap);
      newForm = null;
      newWrap.hidden = !pickedNew();
      if (!pickedNew()) return;
      newForm = Cmdly.connections.form(null, { onInput: paintPreview });
      newWrap.appendChild(newForm.el);
      ui.refreshIcons();
    }
    function targetName() {
      if (draft.target !== L().TARGET_SSH) return "";
      if (!pickedNew()) return connSel.value || "";
      const v = newForm ? newForm.value() : {};
      return String(v.name || "").trim() || L().derivedName(v);
    }

    // -- what it runs
    const group2 = group("Command");
    const dirInput = ui.input({ value: draft.directory, mono: true, ariaLabel: "Folder",
      autocomplete: false, spellcheck: false,
      onInput: (v) => { draft.directory = v.trim(); paintPreview(); } });
    const dirField = ui.field({ label: "Folder", control: dirInput, info: " " });
    group2.appendChild(dirField);
    const cmdInput = ui.input({ value: draft.command, placeholder: "./start.sh", mono: true,
      ariaLabel: "Command", autocomplete: false, spellcheck: false,
      onInput: (v) => { draft.command = v.trim(); paintPreview(); } });
    const cmdField = ui.field({ label: "Command", control: cmdInput, info: " " });
    group2.appendChild(cmdField);
    const preview = document.createElement("div");
    preview.className = "preview";
    const previewText = document.createElement("code");
    preview.appendChild(ui.icon("terminal", 13));
    preview.appendChild(previewText);
    group2.appendChild(preview);
    form.appendChild(group2);

    // -- how it runs
    const group3 = group("Behaviour");
    const switchOpts = {
      value: wantedMode === L().MODE_TERMINAL,
      ariaLabel: "Run in a terminal",
      onChange: (on) => {
        wantedMode = on ? L().MODE_TERMINAL : L().MODE_BACKGROUND;
        draft.mode = wantedMode;
        paintRestart();
        paintPreview();
      },
    };
    const termSwitch = ui.toggle(switchOpts);
    const termField = ui.field({ label: "Run in a terminal", control: termSwitch.el,
      className: "field-switch", info: " " });
    group3.appendChild(termField);
    const restartField = ui.field({
      label: "Restart on press",
      control: ui.toggle({ value: draft.restart === true, ariaLabel: "Restart on press",
        onChange: (on) => { draft.restart = on; } }).el,
      className: "field-switch",
      info: "On: pressing the button while its program still runs sends Ctrl-C, " +
            "waits a second, and starts it again in the same terminal.\n\nOff: the " +
            "line is typed into the terminal as it is, so a program still in the " +
            "foreground gets it as input.",
    });
    group3.appendChild(restartField);
    form.appendChild(group3);

    const msg = ui.message({ className: "dialog-msg" });
    form.appendChild(msg.el);
    viewEl.appendChild(form);

    // -- the bar at the bottom: always in reach, however long the form
    const bar = document.createElement("div");
    bar.className = "editor-bar";
    const deleteBtn = isNew ? null : ui.button({
      variant: "danger", icon: "trash-2", label: "Delete", title: "Remove this button",
      onClick: () => remove(draft),
    });
    const cancelBtn = ui.button({ variant: "ghost", label: "Cancel", onClick: () => close() });
    const saveBtn = ui.button({
      variant: "primary", icon: "check", label: "Save",
      onClick: () => save(),
    });
    if (deleteBtn) bar.appendChild(deleteBtn);
    const grow = document.createElement("span");
    grow.className = "spacer";
    bar.append(grow, cancelBtn, saveBtn);
    viewEl.appendChild(bar);

    function localTerminalReason() {
      const local = st.local;
      if (!local || local.terminal !== false) return "";
      return local.reason || "A terminal on this computer is not available here.";
    }
    function paintRestart() { restartField.hidden = draft.mode === L().MODE_BACKGROUND; }
    function paintTarget() {
      const local = draft.target !== L().TARGET_SSH;
      const words = local ? HINTS.local : HINTS.ssh;
      sshBox.hidden = local;
      renderNew();
      dirInput.placeholder = words.folderPlaceholder;
      setInfo(dirField, "Folder", words.folder);
      setInfo(cmdField, "Command", words.program);
      setInfo(termField, "Run in a terminal", words.terminal);
      const noTerminal = local ? localTerminalReason() : "";
      draft.mode = noTerminal ? L().MODE_BACKGROUND : wantedMode;
      switchOpts.disabled = !!noTerminal;
      termSwitch.setValue(draft.mode !== L().MODE_BACKGROUND);
      setHint(termField, noTerminal);
      paintRestart();
    }
    function paintPreview() {
      const line = L().previewLine(Object.assign({}, draft, { connection: targetName() }));
      previewText.textContent = line || "Type a command to see what runs.";
      preview.classList.toggle("is-empty", !line);
      let problem = "";
      if (pickedNew() && newForm) problem = newForm.error(conns.map((c) => c.name));
      else if (draft.target === L().TARGET_SSH && !targetName()) problem = "Pick a connection to run it on.";
      saveBtn.disabled = !line || !!problem;
      saveBtn.title = problem || (line ? "" : "Type a command first.");
      if (problem && problem.indexOf("already saved") >= 0) msg.show(problem, "warn");
      else msg.hide();
    }
    paintTarget();
    paintPreview();

    function commit() {
      const entry = Object.assign({}, draft, { label: String(draft.label || "").trim() || draft.command });
      const before = isNew ? null : buttons().find((b) => b.id === entry.id);
      (before ? leaveSession(before, entry) : Promise.resolve(true)).then((go) => {
        if (!go) return;
        const list = isNew ? buttons().concat([entry])
          : buttons().map((b) => (b.id === entry.id ? entry : b));
        ui.setBusy(saveBtn, true);
        saveButtons(list).then(() => close()).catch(() => ui.setBusy(saveBtn, false));
      });
    }
    function save() {
      if (draft.target === L().TARGET_SSH && !pickedNew()) draft.connection = connSel.value || "";
      if (draft.target !== L().TARGET_SSH) draft.connection = "";
      if (!pickedNew()) { commit(); return; }
      ui.setBusy(saveBtn, true);
      store().saveConnection(newForm.body()).then((saved) => {
        draft.connection = saved.name;
        ui.setBusy(saveBtn, false);
        commit();
      }).catch((error) => {
        ui.setBusy(saveBtn, false);
        msg.show(error.message, "err");
      });
    }

    ui.refreshIcons();
    setTimeout(() => { if (isNew) cmdInput.focus(); }, 0);
  }

  function group(title) {
    const g = document.createElement("section");
    g.className = "group";
    const h = document.createElement("div");
    h.className = "group-title";
    h.textContent = title;
    g.appendChild(h);
    return g;
  }

  /**
   * A button moved elsewhere or into the background must leave the session it
   * has open; that stops what runs there, so ask first. Resolves whether to go on.
   */
  function leaveSession(before, after) {
    if (!store().isLive(L().sessionName(before))) return Promise.resolve(true);
    const moved = before.target !== after.target
      || (after.target === L().TARGET_SSH && before.connection !== after.connection);
    const detached = L().coerceMode(before) !== L().MODE_BACKGROUND
      && L().coerceMode(after) === L().MODE_BACKGROUND;
    if (!moved && !detached) return Promise.resolve(true);
    return Cmdly.dialogs.confirm({
      title: `“${before.label}” is running`,
      text: "Saving this closes its terminal session, which stops what it runs.",
      confirm: "Save and stop", danger: true,
    }).then((go) => {
      if (go) L().closeSession(before);
      return go;
    });
  }

  function remove(entry) {
    const running = store().isLive(L().sessionName(entry));
    Cmdly.dialogs.confirm({
      title: `Delete “${entry.label}”?`,
      text: running ? "Its terminal session is closed, which stops what it runs." : "The button is removed from the shelf.",
      confirm: "Delete", danger: true,
    }).then((go) => {
      if (!go) return;
      if (running) L().closeSession(entry);
      L().clearError(entry);
      saveButtons(buttons().filter((b) => b.id !== entry.id)).then(() => close());
    });
  }

  function close() {
    editing = null;
    render();
  }

  function mount(container) {
    viewEl = container;
    ["config", "live", "errors", "connections", "companion"].forEach((name) => {
      store().on(name, () => { if (!editing) render(); });
    });
    render();
  }

  return { mount, render, edit, isEditing: () => !!editing, MAX_BUTTONS };
})();
