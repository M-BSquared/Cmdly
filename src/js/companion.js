"use strict";
window.Cmdly = window.Cmdly || {};

/*
  Cmdly.companion — the companion computer at the top of the window.

  One card per companion computer: its name and address, a status pill
  (Online with the round trip, Checking, Offline, Cannot ping, or Not set).
  Pressing the card of an SSH computer connects and opens a terminal on it;
  a computer that is only pinged has nothing to open. A right-click on an
  SSH computer's card asks its computer to shut down or reboot (one command
  over its saved connection, the page never composes the line); sudo's
  password question is answered by the backend, with the connection's saved
  login password — and asked for here, once, when there is none saved.
  Every companion is watched at the same time. A saved SSH connection can
  be shown here too (its dialog has the switch; see setWatched).

  Online is decided here, from pings this computer sends through
  POST /api/local/ping at each companion's interval: online while the last
  reply is younger than its timeout; before the first reply, checking until
  the timeout has passed; offline after that. A probe that could not be made
  at all (no ping program) is an error, not a verdict on the companion.

  Probes run while the window is visible; a hidden window stops asking and
  starts over when it is shown again.
*/
Cmdly.companion = (function () {
  const store = () => Cmdly.store;
  const L = () => Cmdly.launch;

  const PING = "ping";
  const SSH = "ssh";
  const INTERVAL_STEPS = [1, 2, 3, 5, 10];
  const TIMEOUT_STEPS = [3, 4, 6, 10, 15, 20, 30];
  const DEFAULT_INTERVAL_S = 2;
  const DEFAULT_TIMEOUT_S = 6;

  const LOOK = {
    unset: { level: "off", text: "Not set" },
    checking: { level: "warning", text: "Checking" },
    online: { level: "healthy", text: "Online" },
    offline: { level: "critical", text: "Offline" },
    error: { level: "warning", text: "Cannot ping" },
  };

  // ---- pure rules -------------------------------------------------------------

  function timeoutFor(interval) {
    return TIMEOUT_STEPS.find((t) => t > interval) || TIMEOUT_STEPS[TIMEOUT_STEPS.length - 1];
  }

  function intervalFor(timeout) {
    const fit = INTERVAL_STEPS.filter((i) => i < timeout);
    return fit.length ? fit[fit.length - 1] : INTERVAL_STEPS[0];
  }

  /** "unset" | "checking" | "online" | "offline" | "error". */
  function stateOf(s) {
    const o = s || {};
    if (!o.host) return "unset";
    const now = Number(o.now);
    const timeout = Number(o.timeoutMs);
    if (o.lastOkAt != null && now - o.lastOkAt <= timeout) return "online";
    if (o.error) return "error";
    if (o.lastOkAt == null && now - o.startedAt < timeout) return "checking";
    return "offline";
  }

  /** How long one probe waits for its echo: the interval, within 1 to 5 s. */
  function probeWaitMs(intervalS) {
    return Math.min(5000, Math.max(1000, Number(intervalS) * 1000 || 2000));
  }

  function formatRtt(ms) {
    const n = Number(ms);
    if (!isFinite(n)) return "";
    return n < 10 ? `${n.toFixed(1)} ms` : `${Math.round(n)} ms`;
  }

  /** A companion as a shelf entry, so its terminal goes through the button code. */
  function entryOf(companion) {
    if (!companion || companion.type !== SSH || !companion.connection) return null;
    return {
      id: L().COMPANION_PREFIX + companion.id,
      label: companion.name || companion.connection,
      target: L().TARGET_SSH,
      connection: companion.connection,
      mode: L().MODE_TERMINAL,
    };
  }

  /** Whether the power menu (right-click) can reach this companion: only a
   *  computer with a saved SSH connection can be asked anything. */
  function canPower(companion) {
    return !!companion && companion.type === SSH && !!companion.connection;
  }

  // ---- the probes ---------------------------------------------------------------
  // Every companion is pinged on its own: one probe each, started when it
  // appears, started over when its address or timing changes, dropped when it
  // goes.

  const probes = new Map();   // companion id -> its probe
  let el = null;
  let lastKey = "";
  let dialogOpen = false;

  function list() { return store().state.config.companions || []; }

  /** What decides whether a companion's probe has to start over. */
  function sigOf(c) { return c.host + "|" + c.interval_s + "|" + c.timeout_s; }

  function stateFor(c) {
    const pr = probes.get(c.id);
    return stateOf({
      host: c.host,
      startedAt: pr ? pr.startedAt : 0,
      lastOkAt: pr ? pr.lastOkAt : null,
      error: pr ? pr.error : "",
      now: Date.now(),
      timeoutMs: c.timeout_s * 1000,
    });
  }

  /** Whether this companion answers right now. */
  function isOnline(c) { return !!c && stateFor(c) === "online"; }

  /** The first companion, or the one the older configs named: what the page calls "the" companion. */
  function active() {
    const cfg = store().state.config;
    return list().find((c) => c.id === cfg.active_companion) || list()[0] || null;
  }

  function online() { return isOnline(active()); }

  /**
   * Whether the shelf's filter keeps a button. A local one always; an SSH one
   * unless every computer shown above for its connection is offline. Nothing
   * is pinged for the filter's sake: a connection that is not shown above is
   * not known to be down, so its buttons stay.
   */
  function reachableAnywhere(entry) {
    if (L().coerceTarget(entry) !== L().TARGET_SSH) return true;
    const conns = store().state.connections;
    const watched = list().filter((c) => L().reachable(entry, c, true, conns));
    return !watched.length || watched.some((c) => stateFor(c) !== "offline");
  }

  function stopProbe(pr) {
    pr.gen += 1;
    if (pr.timer !== null) { clearTimeout(pr.timer); pr.timer = null; }
    if (pr.paintTimer !== null) { clearTimeout(pr.paintTimer); pr.paintTimer = null; }
  }

  function stop() { probes.forEach(stopProbe); }

  function startProbe(c) {
    const pr = {
      sig: sigOf(c), gen: 0, timer: null, paintTimer: null,
      startedAt: Date.now(), lastOkAt: null, rtt: null, error: "",
    };
    probes.set(c.id, pr);
    if (document.hidden) return;
    const gen = pr.gen;
    const live = () => gen === pr.gen;
    const tick = () => {
      pr.timer = null;
      if (!live()) return;
      const began = Date.now();
      Cmdly.api.post("/api/local/ping", { host: c.host, wait_ms: probeWaitMs(c.interval_s) })
        .then((res) => {
          if (!live()) return;
          if (res && res.ok) {
            pr.error = "";
            if (res.reachable) {
              pr.lastOkAt = Date.now();
              pr.rtt = res.rtt_ms == null ? null : res.rtt_ms;
            }
          } else {
            pr.error = (res && res.error) || "The ping failed.";
          }
        })
        .catch((error) => { if (live()) pr.error = error.message; })
        .then(() => {
          if (!live()) return;
          paint();
          pr.timer = setTimeout(tick, Math.max(0, c.interval_s * 1000 - (Date.now() - began)));
        });
    };
    tick();
  }

  /** Make the probes match the companions: new ones start, changed ones start over, gone ones stop. */
  function sync(force) {
    const ids = new Set(list().map((c) => c.id));
    probes.forEach((pr, id) => {
      if (!ids.has(id)) { stopProbe(pr); probes.delete(id); }
    });
    list().forEach((c) => {
      const pr = probes.get(c.id);
      if (pr && pr.sig === sigOf(c) && !force) return;
      if (pr) stopProbe(pr);
      startProbe(c);
    });
    paint();
  }

  // ---- the cards -------------------------------------------------------------------

  function card(c) {
    const ui = Cmdly.ui;
    const pr = c ? probes.get(c.id) : null;
    const state = c ? stateFor(c) : "unset";
    const look = LOOK[state];
    const box = document.createElement("div");
    box.className = "comp-card";
    box.dataset.state = state;
    if (c) box.dataset.id = c.id;

    const main = document.createElement("button");
    main.type = "button";
    main.className = "comp-main";
    // The bar of an SSH computer opens a terminal on it; one that is only
    // pinged has nothing to open (its settings button edits it).
    const entry = entryOf(c);
    main.title = !c ? "Set up the computer to watch"
      : entry ? `Connect to ${entry.connection} and open a terminal` : "Only pinged: nothing to open";
    main.classList.toggle("is-static", !!c && !entry);
    main.addEventListener("click", () => {
      if (!c) { openDialog(null); return; }
      if (!entry) return;
      if (store().isLive(L().sessionName(entry))) L().openTerminal(entry);
      else L().connectAndOpen(entry, box);
    });

    const iconEl = document.createElement("span");
    iconEl.className = "comp-icon";
    iconEl.appendChild(ui.icon(c && c.type === SSH ? "server" : "cpu", 16));
    main.appendChild(iconEl);

    const text = document.createElement("span");
    text.className = "comp-text";
    const name = document.createElement("span");
    name.className = "comp-name";
    name.textContent = c ? (c.name || c.connection || "Companion computer") : "Companion computer";
    const host = document.createElement("span");
    host.className = "comp-host";
    host.textContent = c ? c.host : "Press to set one up";
    text.append(name, host);
    main.appendChild(text);

    const bar = document.createElement("div");
    bar.className = "comp-bar";
    bar.appendChild(main);

    const pill = document.createElement("span");
    pill.className = "comp-pill";
    pill.dataset.level = look.level;
    pill.appendChild(ui.statusDot(look.level));
    const word = document.createElement("span");
    word.textContent = look.text;
    pill.appendChild(word);
    if (state === "online") {
      const rtt = document.createElement("span");
      rtt.className = "comp-rtt";
      rtt.textContent = pr && pr.rtt != null ? formatRtt(pr.rtt) : "";
      pill.appendChild(rtt);
    }
    pill.title = state === "error" ? (pr ? pr.error : "")
      : c ? `Pinged every ${c.interval_s} s, offline after ${c.timeout_s} s without a reply` : "";
    bar.appendChild(pill);
    box.appendChild(bar);

    const tools = document.createElement("div");
    tools.className = "comp-tools";
    if (c) {
      tools.appendChild(ui.iconButton("settings-2", {
        ariaLabel: `Edit ${c.name || c.host}`,
        title: "Edit",
        onClick: () => openDialog(c),
      }));
    }
    box.appendChild(tools);
    if (canPower(c)) {
      box.addEventListener("contextmenu", (e) => {
        e.preventDefault();
        openPowerMenu(c, e);
      });
    }
    return box;
  }

  // ---- the power menu (right-click) --------------------------------------------

  /**
   * The dropdown a right-click on a companion card opens: shut the computer
   * down, or reboot it. Each is asked for first (a computer that goes down
   * can only be woken at the machine), then run as one command over the
   * companion's saved connection (POST /api/ssh/power — the command itself
   * is the backend's, launcher.POWER_ACTIONS, so the page never sends a
   * shell line of its own).
   */
  function openPowerMenu(c, at) {
    const ui = Cmdly.ui;
    const menu = ui.menu({
      role: "menu",
      ariaLabel: `Power options for ${c.name || c.connection}`,
      render: (surface) => {
        const rows = [
          ui.menuItem({
            icon: "power", label: "Shut down",
            onSelect: () => { menu.close(); powerAction(c, "shutdown"); },
          }),
          ui.menuItem({
            icon: "rotate-cw", label: "Reboot",
            onSelect: () => { menu.close(); powerAction(c, "reboot"); },
          }),
        ];
        rows.forEach((row) => surface.appendChild(row));
        ui.refreshIcons();
        return rows;
      },
    });
    menu.open({ x: at.clientX, y: at.clientY });
  }

  /** Ask, then send one power action to the companion's computer. */
  function powerAction(c, action) {
    const who = c.name || c.connection;
    const reboot = action === "reboot";
    const word = reboot ? "Reboot" : "Shut down";
    Cmdly.dialogs.confirm({
      title: `${word} ${who}?`,
      text: reboot ? `Reboot ${who} now? It answers again once it is back.`
        : `Shut down ${who} now?\n\nIt can only be turned back on at the computer itself.`,
      confirm: word,
      danger: true,
    }).then((yes) => {
      if (yes) sendPowerAction(c, action);
    });
  }

  /**
   * One power action over the companion's saved connection. A reply that
   * says what it needs — the login was refused, sudo asked for a password the
   * connection has none saved to give — asks for it once and tries again:
   * the same ask-once rule the launch buttons follow.
   */
  function sendPowerAction(c, action, retried) {
    const who = c.name || c.connection;
    const reboot = action === "reboot";
    const word = reboot ? "Reboot" : "Shut down";
    Cmdly.api.post("/api/ssh/power", { name: c.connection, action })
      .catch(Cmdly.api.replyOf)
      .then((res) => {
        if (res && res.ok) {
          store().emit("status", { text: `${who} is ${reboot ? "rebooting" : "shutting down"}`, kind: "ok" });
        } else if (!retried && res && res.needs) {
          Cmdly.connections.prompt(res).then((saved) => {
            if (saved) sendPowerAction(c, action, true);
          });
        } else {
          Cmdly.ui.toast({
            level: "critical",
            title: `${word} failed`,
            message: (res && (res.stderr || res.error)) || "The computer did not answer.",
          });
        }
      });
  }

  function paint() {
    if (!el) return;
    const ui = Cmdly.ui;
    // The shelf's filter hides the computers that are offline as well; they
    // are still pinged, so one that comes back is shown again.
    const hideOffline = !!(store().state.config.ui || {}).reachable_only;
    const cs = hideOffline ? list().filter((c) => stateFor(c) !== "offline") : list();
    const states = cs.map((c) => stateFor(c));
    // Only the round trips change from one ping to the next: when nothing
    // else did, those numbers are updated in place instead of the cards
    // being built again (a hover or an open menu stays as it is).
    const key = JSON.stringify([hideOffline, cs, states, cs.map((c) => {
      const e = entryOf(c);
      return e && [store().isLive(L().sessionName(e)), L().isOpening(e)];
    })]);
    if (key === lastKey && el.firstChild) {
      cs.forEach((c) => {
        const pr = probes.get(c.id);
        const rttEl = el.querySelector(`.comp-card[data-id="${c.id}"] .comp-rtt`);
        if (rttEl && pr && pr.rtt != null) rttEl.textContent = formatRtt(pr.rtt);
      });
      schedule();
      return;
    }
    lastKey = key;
    ui.clear(el);
    if (!list().length) el.appendChild(card(null));
    cs.forEach((c) => el.appendChild(card(c)));
    ui.refreshIcons();
    const summary = states.join("|");
    if (summary !== shownSummary) {
      shownSummary = summary;
      store().emit("companion", states);
    }
    schedule();
  }

  let paintTimer = null;
  let shownSummary = "";

  /** Online and checking both end on their own when nothing answers. */
  function schedule() {
    if (paintTimer !== null) { clearTimeout(paintTimer); paintTimer = null; }
    let due = null;
    list().forEach((c) => {
      const pr = probes.get(c.id);
      const state = stateFor(c);
      let at = null;
      if (pr && state === "online") at = pr.lastOkAt + c.timeout_s * 1000;
      else if (pr && state === "checking") at = pr.startedAt + c.timeout_s * 1000;
      if (at !== null && (due === null || at < due)) due = at;
    });
    if (due !== null) paintTimer = setTimeout(paint, Math.max(0, due - Date.now()) + 50);
  }

  // ---- watching a connection ------------------------------------------------------

  /** Whether a saved connection is shown in the main window. */
  function watching(connection) {
    return list().some((c) => c.type === SSH && c.connection === connection);
  }

  /** Show a saved SSH connection in the main window, or stop showing it. */
  function setWatched(connection, on) {
    const cs = list().slice();
    const has = cs.some((c) => c.type === SSH && c.connection === connection);
    if (on && !has) {
      const conn = store().connection(connection);
      if (!conn) return Promise.resolve();
      cs.push({
        id: L().newId("c"), name: connection, host: conn.host, type: SSH, connection,
        interval_s: DEFAULT_INTERVAL_S, timeout_s: DEFAULT_TIMEOUT_S,
      });
    } else if (!on && has) {
      cs.filter((c) => c.type === SSH && c.connection === connection).forEach((c) => {
        const entry = entryOf(c);
        if (entry && store().isLive(L().sessionName(entry))) L().closeSession(entry);
      });
      cs.splice(0, cs.length, ...cs.filter((c) => !(c.type === SSH && c.connection === connection)));
    } else {
      return Promise.resolve();
    }
    return store().save({ companions: cs });
  }

  // ---- the dialog -------------------------------------------------------------------

  /** Add (`existing` null) or edit one companion computer. */
  function openDialog(existing) {
    if (dialogOpen) return;
    const ui = Cmdly.ui;
    const st = store().state;
    const connections = st.connections;
    const draft = existing ? Object.assign({}, existing) : {
      id: L().newId("c"), name: "", host: "", type: PING, connection: "",
      interval_s: DEFAULT_INTERVAL_S, timeout_s: DEFAULT_TIMEOUT_S,
    };
    let mode = draft.type === SSH ? SSH : PING;
    const body = document.createElement("div");
    body.className = "comp-form";

    const kind = ui.segment({
      ariaLabel: "How the companion is reached",
      value: mode,
      options: [
        { value: PING, label: "Ping", icon: "activity", title: "Only ping an IP address or host name" },
        { value: SSH, label: "SSH", icon: "server", title: "A saved SSH connection: ping its host, open a terminal on it" },
      ],
      onChange: (next) => { mode = next; paintMode(); },
    });
    body.appendChild(ui.field({
      label: "Reached by", control: kind.el,
      info: "Ping only watches whether the computer answers. SSH also puts a " +
            "terminal button beside the status, which opens a shell on it.",
    }));

    const nameField = ui.field({
      label: "Name",
      control: ui.input({ value: draft.name, placeholder: "Companion computer", ariaLabel: "Name",
        autocomplete: false, onInput: (v) => { draft.name = v; } }),
    });
    body.appendChild(nameField);
    const hostInput = ui.input({ value: draft.host, placeholder: "192.168.2.10", mono: true,
      ariaLabel: "IP address", autocomplete: false, spellcheck: false,
      onInput: (v) => { draft.host = v.trim(); paintSave(); } });
    const hostField = ui.field({ label: "IP address or host name", control: hostInput });
    body.appendChild(hostField);

    const NEW = "__new__";
    const connOptions = connections.map((c) => ({
      value: c.name, label: c.username ? `${c.name} (${c.username}@${c.host})` : c.name,
    }));
    connOptions.push({ value: NEW, label: "New connection…" });
    const connSel = ui.select({
      ariaLabel: "SSH connection",
      options: connOptions,
      value: draft.connection && connections.some((c) => c.name === draft.connection)
        ? draft.connection : (connections.length ? connections[0].name : NEW),
      onChange: () => paintMode(),
    });
    const connField = ui.field({ label: "SSH connection", control: connSel });
    body.appendChild(connField);
    const newWrap = document.createElement("div");
    newWrap.className = "inset-group";
    body.appendChild(newWrap);
    let newForm = null;

    const seconds = (list) => list.map((n) => ({ value: n, label: `${n} s` }));
    const intervalSlider = ui.slider({
      steps: seconds(INTERVAL_STEPS), value: draft.interval_s, ariaLabel: "Ping every",
      onInput: (v) => {
        draft.interval_s = v;
        if (draft.timeout_s <= v) { draft.timeout_s = timeoutFor(v); timeoutSlider.setValue(draft.timeout_s); }
      },
    });
    const timeoutSlider = ui.slider({
      steps: seconds(TIMEOUT_STEPS), value: draft.timeout_s, ariaLabel: "Offline after",
      onInput: (v) => {
        draft.timeout_s = v;
        if (draft.interval_s >= v) { draft.interval_s = intervalFor(v); intervalSlider.setValue(draft.interval_s); }
      },
    });
    body.appendChild(ui.field({ label: "Ping every", control: intervalSlider.el,
      info: "How often this computer sends the companion one ping." }));
    body.appendChild(ui.field({ label: "Offline after", control: timeoutSlider.el,
      info: "How long without a single reply before the companion counts as " +
            "offline. Always longer than the interval, so one late reply is " +
            "not a lost companion." }));
    const msg = ui.message({ className: "dialog-msg" });
    body.appendChild(msg.el);

    function isSsh() { return mode === SSH; }
    function pickedNew() { return isSsh() && connSel.value === NEW; }
    function pingHost() {
      if (!isSsh()) return String(draft.host || "").trim();
      if (pickedNew()) return newForm ? String(newForm.value().host || "").trim() : "";
      const c = connections.find((x) => x.name === connSel.value);
      return c ? String(c.host || "").trim() : "";
    }
    function paintMode() {
      hostField.hidden = isSsh();
      // Over SSH the companion is called what its connection is called.
      nameField.hidden = isSsh();
      connField.hidden = !isSsh();
      ui.clear(newWrap);
      newForm = null;
      newWrap.hidden = !pickedNew();
      if (pickedNew()) {
        newForm = Cmdly.connections.form(null, { onInput: paintSave });
        newWrap.appendChild(newForm.el);
        ui.refreshIcons();
      }
      paintSave();
    }

    const saveBtn = ui.button({
      variant: "primary", icon: "check", label: existing ? "Save" : "Add",
      onClick: () => {
        const finish = (connection) => {
          const companion = Object.assign({}, draft, {
            type: isSsh() ? SSH : PING,
            connection: isSsh() ? connection : "",
            host: pingHost() || (connection && (store().connection(connection) || {}).host) || "",
          });
          if (isSsh()) companion.name = connection;
          const list = (st.config.companions || []).slice();
          const at = list.findIndex((c) => c.id === companion.id);
          if (at >= 0) list[at] = companion;
          else list.push(companion);
          store().save({ companions: list, active_companion: companion.id })
            .then(() => dialog.close())
            .catch((error) => { ui.setBusy(saveBtn, false); msg.show(error.message, "err"); });
        };
        ui.setBusy(saveBtn, true);
        if (!pickedNew()) { finish(isSsh() ? connSel.value : ""); return; }
        store().saveConnection(newForm.body()).then((saved) => finish(saved.name)).catch((error) => {
          ui.setBusy(saveBtn, false);
          msg.show(error.message, "err");
        });
      },
    });
    const removeBtn = existing ? ui.button({
      variant: "danger", icon: "trash-2", label: "Remove",
      title: "Stop watching this computer. Its SSH connection stays saved.",
      onClick: () => {
        const entry = entryOf(existing);
        if (entry && store().isLive(L().sessionName(entry))) L().closeSession(entry);
        const list = (st.config.companions || []).filter((c) => c.id !== existing.id);
        store().save({ companions: list }).then(() => dialog.close());
      },
    }) : null;

    function paintSave() {
      let problem = L().hostError(pingHost());
      if (pickedNew() && newForm) problem = newForm.error(connections.map((c) => c.name)) || problem;
      if (!pingHost() && !pickedNew()) problem = isSsh() ? "Pick a connection." : "Enter an IP address or host name.";
      saveBtn.disabled = !!problem;
      saveBtn.title = problem;
      if (!isSsh() && draft.host && L().hostError(draft.host)) msg.show(L().hostError(draft.host), "warn");
      else msg.hide();
    }
    paintMode();

    dialogOpen = true;
    const dialog = ui.modal({
      title: existing ? "Companion computer" : "Add a companion computer",
      body,
      actions: [removeBtn, saveBtn],
      onClose: () => { dialogOpen = false; },
    });
    dialog.open();
  }

  // ---- wiring -------------------------------------------------------------------------

  function mount(container) {
    el = container;
    el.classList.add("companion");
    store().on("config", () => sync(false));
    store().on("live", paint);
    store().on("errors", paint);
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) stop();
      else sync(true);
    });
    sync(true);
  }

  return {
    mount, online, active, isOnline, reachableAnywhere, watching, setWatched,
    openDialog, entryOf, canPower, restart: () => sync(true),
    stateOf, probeWaitMs, timeoutFor, intervalFor, formatRtt,
    INTERVAL_STEPS, TIMEOUT_STEPS,
  };
})();
