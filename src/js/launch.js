"use strict";
window.Cmdly = window.Cmdly || {};

/*
  Cmdly.launch — what pressing a button does, and the rules it follows.

  Two ways to run one, per button, on this computer or over SSH:

    TERMINAL (the default)  Types `cd -- <folder> && <command>` into a session
      of the button's own, opening one the first time: a login shell here, or
      an SSH shell there. Pressing the button again types the line again into
      the SAME shell, because a key pressed twice means "run it again", not
      "throw this session away". With RESTART on, the second press sends
      Ctrl-C first and types the line a second later. The terminal window
      opens on the ARROW beside the button, never on the button: a launch is
      a launch. While the session is up the row's pencil is a stop button:
      Ctrl-C, then the session closed.

    BACKGROUND  One shot, nothing to watch. Over SSH it runs under nohup and
      outlives Cmdly on that computer; here it is Cmdly's own child and stops
      when Cmdly quits.

  A button stores the NAME of a saved SSH connection, never a password. A
  press whose connection is missing (a shelf imported from another computer)
  or whose login is refused asks for it once (Cmdly.connections.prompt),
  saves it under that name and tries again.

  The pure rules are exported for the tests (tests/frontend/launch.test.js).
*/
Cmdly.launch = (function () {
  const TARGET_LOCAL = "local";
  const TARGET_SSH = "ssh";
  const MODE_TERMINAL = "terminal";
  const MODE_BACKGROUND = "background";
  const CTRL_C = "\x03";
  // How long a shell gets to take the prompt back after Ctrl-C before the
  // line is typed again; typed too soon it lands on the dying program's stdin.
  const RESTART_GRACE_MS = 1000;
  const LOCAL_HOST = "this computer";
  const SESSION_PREFIX = "cmdly/";
  const COMPANION_PREFIX = "companion-";
  const HOST_RE = /^[A-Za-z0-9:](?:[A-Za-z0-9._:%-]*[A-Za-z0-9])?$/;

  const TARGETS = [
    { value: TARGET_LOCAL, label: "Local", icon: "laptop", title: "Run it on this computer" },
    { value: TARGET_SSH, label: "SSH", icon: "server", title: "Run it over an SSH connection" },
  ];

  // ---- pure rules -------------------------------------------------------------

  function str(v) { return String(v == null ? "" : v); }

  function coerceTarget(raw) {
    const r = raw || {};
    if (r.target === TARGET_LOCAL || r.target === TARGET_SSH) return r.target;
    return str(r.connection).trim() ? TARGET_SSH : TARGET_LOCAL;
  }

  function coerceMode(raw) {
    const r = raw || {};
    if (r.mode === MODE_BACKGROUND || r.mode === MODE_TERMINAL) return r.mode;
    if (typeof r.detach === "boolean") return r.detach ? MODE_BACKGROUND : MODE_TERMINAL;
    return MODE_TERMINAL;
  }

  /** Whether a press while the program runs stops it first. Only a terminal can. */
  function restarts(entry) {
    return !!entry && entry.restart === true && coerceMode(entry) === MODE_TERMINAL;
  }

  function newId(prefix) {
    return (prefix || "b") + Date.now().toString(36) + Math.floor(Math.random() * 1e6).toString(36);
  }

  /** The session a button runs in, keyed by its id so a rename keeps it. */
  function sessionName(entry) {
    return SESSION_PREFIX + (entry && entry.id ? entry.id : "");
  }

  function shellFolder(directory) {
    const quote = (text) => "'" + text.replace(/'/g, "'\\''") + "'";
    if (directory === "~") return "~";
    if (directory.indexOf("~/") === 0) {
      const rest = directory.slice(2);
      return rest ? "~/" + quote(rest) : "~/";
    }
    return quote(directory);
  }

  /** The line a button types into its terminal. */
  function terminalLine(entry) {
    const e = entry || {};
    const command = str(e.command).trim();
    if (!command) return "";
    const directory = str(e.directory).trim();
    if (!directory) return command;
    return "cd -- " + shellFolder(directory) + " && " + command;
  }

  /** What a button will run, as a person reads it. Shown, never sent. */
  function previewLine(cfg) {
    const c = cfg || {};
    const command = str(c.command).trim();
    if (!command) return "";
    const directory = str(c.directory).trim();
    const local = coerceTarget(c) === TARGET_LOCAL;
    const background = coerceMode(c) === MODE_BACKGROUND;
    const body = background ? (local ? `${command} &` : `nohup ${command} &`) : command;
    const line = directory ? `cd ${directory} && ${body}` : body;
    if (local) return line;
    const target = str(c.connection).trim();
    return target ? `ssh ${target} '${line}'` : line;
  }

  function sshSummary(res) {
    const r = res || {};
    if (!r.ok) {
      const detail = str(r.stderr || r.error).trim().split("\n")[0];
      return { text: detail || "The command failed.", kind: "err" };
    }
    const pid = str(r.stdout).trim();
    return { text: pid ? `Running in the background (pid ${pid})` : "Running in the background", kind: "ok" };
  }

  function localSummary(res) {
    const r = res || {};
    const first = (text) => str(text).trim().split("\n")[0].trim();
    if (r.exited) {
      if (r.ok) return { text: "Ran and finished", kind: "ok" };
      return { text: first(r.output) || `Ended at once with exit code ${r.code}`, kind: "err" };
    }
    if (!r.ok) return { text: first(r.error) || "The command failed.", kind: "err" };
    return {
      text: r.pid ? `Running in the background (pid ${r.pid}), stops with Cmdly`
        : "Running in the background, stops with Cmdly",
      kind: "ok",
    };
  }

  function derivedName(conn) {
    const c = conn || {};
    const host = str(c.host).trim();
    if (!host) return "";
    const user = str(c.username).trim();
    return user ? `${user}@${host}` : host;
  }

  function hostError(host) {
    const h = str(host).trim();
    if (!h) return "Enter an IP address or host name.";
    if (h.length > 253 || !HOST_RE.test(h)) return "That is not an IP address or host name.";
    return "";
  }

  /** Why a typed-in connection cannot be saved yet, or "". */
  function connectionError(conn, taken) {
    const c = conn || {};
    const problem = hostError(c.host);
    if (problem) return str(c.host).trim() ? problem : "Name the host to connect to.";
    const name = str(c.name).trim() || derivedName(c);
    const port = str(c.port).trim();
    if (port !== "") {
      const n = Number(port);
      if (!isFinite(n) || Math.floor(n) !== n || n < 1 || n > 65535) {
        return "The port has to be a number between 1 and 65535.";
      }
    }
    if ((taken || []).indexOf(name) >= 0) {
      return `“${name}” is already saved. Pick it above, or save this one under another name.`;
    }
    return "";
  }

  /** The body of POST /api/ssh/connections for a typed-in connection. */
  function connectionBody(conn) {
    const c = conn || {};
    const trim = (v) => str(v).trim();
    const body = {
      name: trim(c.name) || derivedName(c),
      host: trim(c.host),
      port: parseInt(trim(c.port), 10) || 22,
      username: trim(c.username),
      key_path: trim(c.key_path),
    };
    // Left out unless typed: an edit that leaves it empty keeps the stored one.
    if (str(c.password) !== "") body.password = str(c.password);
    return body;
  }

  /**
   * Whether a button can run now, for the "reachable only" filter: a local
   * button always, an SSH one while the companion it runs on is online.
   */
  function reachable(entry, companion, online, connections) {
    if (coerceTarget(entry) !== TARGET_SSH) return true;
    if (!companion || !online) return false;
    const name = str(entry.connection);
    if (companion.connection && name === companion.connection) return true;
    const host = str(companion.host).toLowerCase();
    const conn = (connections || []).find((c) => c.name === name);
    return !!(conn && str(conn.host).toLowerCase() === host);
  }

  // ---- what went wrong, and where ---------------------------------------------

  const errors = Object.create(null);   // button id -> why its last press failed
  const closing = Object.create(null);  // session -> its disconnect in flight
  const opening = Object.create(null);  // session -> the arrow's connect in flight

  function store() { return Cmdly.store; }

  function status(text, kind) { store().emit("status", { text, kind }); }

  function setError(entry, text) {
    errors[entry.id] = str(text) || "It failed.";
    store().emit("errors");
  }

  function clearError(entry) {
    if (entry && errors[entry.id]) {
      delete errors[entry.id];
      store().emit("errors");
    }
  }

  function failed(entry, detail) {
    setError(entry, detail);
    Cmdly.ui.toast({ level: "warning", title: entry.label, message: detail });
  }

  function errorOf(entry) { return (entry && errors[entry.id]) || ""; }

  function isLocal(entry) { return coerceTarget(entry) === TARGET_LOCAL; }

  function isClosing(entry) { return !!closing[sessionName(entry)]; }

  function isOpening(entry) { return !!opening[sessionName(entry)]; }

  // ---- running one ----------------------------------------------------------------

  /** A button pressed. Resolves when the press has done what it does. */
  function launch(entry, btn) {
    clearError(entry);
    store().emit("output", "");
    Cmdly.ui.setBusy(btn, true);
    const done = () => Cmdly.ui.setBusy(btn, false);
    const run = coerceMode(entry) === MODE_BACKGROUND ? launchDetached(entry) : launchInTerminal(entry);
    return run.finally(done);
  }

  /**
   * The arrow on a terminal button: start it and show its terminal. One
   * that is already running is only shown, not run a second time.
   */
  function launchAndOpen(entry, btn) {
    if (store().isLive(sessionName(entry))) {
      openTerminal(entry);
      return Promise.resolve(true);
    }
    return launch(entry, btn).then((ok) => {
      if (ok) openTerminal(entry);
      return ok;
    });
  }

  function send(session, data) {
    return Cmdly.api.post("/api/ssh/send", { name: session, data }).catch(Cmdly.api.replyOf);
  }

  /** Ctrl-C into a session, then a moment for its shell to take the prompt back. */
  function interrupt(session) {
    return send(session, CTRL_C).then((res) => {
      if (!(res && res.ok)) return res;
      return new Promise((resolve) => setTimeout(() => resolve(res), RESTART_GRACE_MS));
    });
  }

  /**
   * TERMINAL mode: type the line into the button's own session; open one only
   * when it has none. Send first and connect only when that fails, so a
   * second press runs it again in the same shell.
   */
  function launchInTerminal(entry) {
    const session = sessionName(entry);
    const line = terminalLine(entry);
    const restart = restarts(entry);
    const sendLine = () => send(session, line + "\n");
    const attempt = restart
      ? () => interrupt(session).then((res) => ((res && res.ok) ? sendLine() : res))
      : sendLine;
    // A session being closed must be gone, and one the arrow is opening must
    // be up, before the line is sent, or it lands in the wrong shell.
    const pending = closing[session] || opening[session];
    return (pending ? pending.then(attempt, attempt) : attempt())
      .then((res) => {
        if (res && res.ok) return ran(entry, false, restart);
        return connectSession(entry).then((up) => {
          if (!up) return false;
          return sendLine().then(() => ran(entry, true, false));
        });
      })
      .catch((error) => { failed(entry, error.message); return false; });
  }

  /**
   * Open a button's session: a shell here, or over SSH. A reply that says the
   * connection is missing or refused asks for it once, then tries again.
   */
  function connectSession(entry, retried) {
    const session = sessionName(entry);
    const request = isLocal(entry)
      ? Cmdly.api.post("/api/local/connect", { name: session, directory: "" })
      : Cmdly.api.post("/api/ssh/connect", { name: session, from: entry.connection });
    return request.catch(Cmdly.api.replyOf).then((res) => {
      if (res && res.ok && res.connected) {
        store().markLive(session, true);
        return true;
      }
      if (!retried && !isLocal(entry) && res && res.needs) {
        return Cmdly.connections.prompt(res).then((saved) => {
          if (saved) return connectSession(entry, true);
          failed(entry, res.error || "Could not open the terminal.");
          return false;
        });
      }
      failed(entry, (res && res.error) || "Could not open the terminal.");
      return false;
    });
  }

  /** The arrow on a button with nothing running: connect, and show the terminal. */
  function connectAndOpen(entry, btn) {
    const session = sessionName(entry);
    if (opening[session]) return opening[session];
    clearError(entry);
    Cmdly.ui.setBusy(btn, true);
    const connect = () => connectSession(entry);
    const pending = closing[session];
    const up = (pending ? pending.then(connect, connect) : connect())
      .catch((error) => { failed(entry, error.message); return false; })
      .then((ok) => {
        if (opening[session] === up) delete opening[session];
        Cmdly.ui.setBusy(btn, false);
        if (!ok) return false;
        openTerminal(entry, true);
        status(`${entry.label}: terminal ready. Press the button to start it.`, "ok");
        return true;
      });
    opening[session] = up;
    store().emit("errors");
    return up;
  }

  /** Record a launch; a window left open on a replaced shell is quietly repointed. */
  function ran(entry, reconnected, restarted) {
    const session = sessionName(entry);
    const was = store().isLive(session);
    store().markLive(session, true);
    if (reconnected) openTerminal(entry, true, true);
    let said = `${entry.label} is running`;
    if (restarted && !reconnected) said = `${entry.label} restarted`;
    else if (was && !reconnected) said = `${entry.label} sent again to its terminal`;
    status(said, "ok");
    return true;
  }

  /** BACKGROUND mode: one shot, here or over SSH. */
  function launchDetached(entry, retried) {
    const local = isLocal(entry);
    const request = local
      ? Cmdly.api.post("/api/local/run", { directory: entry.directory, command: entry.command })
      : Cmdly.api.post("/api/ssh/run", {
        name: entry.connection, directory: entry.directory, command: entry.command, detach: true,
      });
    return request.catch(Cmdly.api.replyOf).then((res) => {
      if (!local && !retried && res && res.needs) {
        return Cmdly.connections.prompt(res).then((saved) => (
          saved ? launchDetached(entry, true) : report(res)));
      }
      return report(res);
    });

    function report(res) {
      const r = res || {};
      const summary = local ? localSummary(r) : sshSummary(r);
      if (summary.kind === "err") failed(entry, summary.text);
      else status(`${entry.label}: ${summary.text}`, "ok");
      const body = [r.stdout, r.stderr, r.output].map((p) => str(p).trim()).filter(Boolean).join("\n");
      if (body && !r.ok) store().emit("output", body);
      return !!r.ok;
    }
  }

  /** Close a button's session; `first` is what has to happen before the hang-up. */
  function closeSession(entry, first) {
    const session = sessionName(entry);
    const disconnect = () => Cmdly.api.post("/api/ssh/disconnect", { name: session });
    const done = (first ? first.then(disconnect, disconnect) : disconnect())
      .then(() => true, () => false)
      .then((reached) => {
        if (closing[session] === done) delete closing[session];
        store().markLive(session, false);
        if (Cmdly.termWindows) Cmdly.termWindows.close(session);
        if (Cmdly.popouts) Cmdly.popouts.close("term:" + session);
        store().emit("errors");
        return reached;
      });
    closing[session] = done;
    store().emit("errors");
    return done;
  }

  /** The stop button: Ctrl-C, so the program can shut down, then the session closed. */
  function stop(entry) {
    const session = sessionName(entry);
    if (closing[session]) return closing[session];
    clearError(entry);
    return closeSession(entry, interrupt(session)).then((reached) => {
      if (!reached) {
        failed(entry, "Could not reach Cmdly's backend to stop it.");
        return false;
      }
      status(`${entry.label} stopped`, "ok");
      return true;
    });
  }

  /**
   * Show the terminal a button's program runs in, raising it when it is open.
   * `reattach`: a new shell is behind the name. `existingOnly`: repair an open
   * window, open none.
   */
  function openTerminal(entry, reattach, existingOnly) {
    let where;
    if (isLocal(entry)) {
      where = { host: LOCAL_HOST };
    } else {
      const conn = store().connection(entry.connection) || {};
      where = { host: conn.host, port: conn.port, username: conn.username };
    }
    const shown = Cmdly.termWindows.open(Object.assign({
      name: sessionName(entry),
      title: entry.label,
    }, where), { reattach: !!reattach, existingOnly: !!existingOnly });
    if (!shown && !existingOnly) failed(entry, "Its terminal window could not be opened.");
    return shown;
  }

  return {
    // rules
    TARGETS, TARGET_LOCAL, TARGET_SSH, MODE_TERMINAL, MODE_BACKGROUND, LOCAL_HOST,
    CTRL_C, RESTART_GRACE_MS, SESSION_PREFIX, COMPANION_PREFIX,
    coerceTarget, coerceMode, restarts, newId, sessionName, terminalLine, previewLine,
    sshSummary, localSummary, derivedName, hostError, connectionError, connectionBody, reachable,
    // actions
    launch, launchAndOpen, connectAndOpen, stop, closeSession, openTerminal, connectSession,
    errorOf, clearError, isLocal, isClosing, isOpening,
  };
})();
