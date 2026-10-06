"use strict";
window.Cmdly = window.Cmdly || {};

/*
  Cmdly.store — what the page knows, in one place.

  The settings (GET /api/config: buttons, companion computers, appearance),
  the saved SSH connections (never with a password: the backend keeps those),
  which terminal sessions are up, and what this computer can do. Every view
  reads from here and repaints on the events it fires; every change goes
  through here, which saves it.

  Events (on(name, fn) -> unsubscribe):
    config       the buttons, companions or appearance changed
    connections  the saved SSH connections changed
    live         a session came up or went away
    local        what this computer can do is known

  Sessions have no push of their own, so which are up is asked every
  LIVE_POLL_MS, and at once after anything that starts or stops one. A session
  that ends inside a terminal window is told here too (sshTerm.onSessionEnded),
  so the row stops showing it as running without waiting for the next poll.
*/
Cmdly.store = (function () {
  const api = Cmdly.api;
  const LIVE_POLL_MS = 3000;

  const state = {
    config: { buttons: [], companions: [], active_companion: "", connections: [], ui: {} },
    connections: [],
    connectionsLoaded: false,
    live: Object.create(null),   // session name -> true
    local: null,                 // GET /api/local/status
    platform: "",
    version: "",
  };
  const listeners = Object.create(null);
  let pollTimer = null;
  let saving = Promise.resolve();

  function on(name, fn) {
    (listeners[name] = listeners[name] || new Set()).add(fn);
    return () => listeners[name].delete(fn);
  }

  function emit(name, detail) {
    (listeners[name] || []).forEach((fn) => {
      try { fn(detail); } catch (e) { console.error(e); }
    });
  }

  // ---- settings -------------------------------------------------------------

  function load() {
    return api.get("/api/config").then((data) => {
      state.config = data.config;
      state.platform = data.platform || "";
      state.version = data.version || "";
      state.local = data.local || null;
      state.connections = data.config.connections || [];
      state.connectionsLoaded = true;
      emit("config");
      emit("connections");
      emit("local");
      refreshLive();
      return state.config;
    });
  }

  /**
   * Save a partial change ({buttons}, {companions, active_companion}, {ui}).
   * Applied here at once, so the page never waits on the disk; the backend's
   * answer (the normalized whole) replaces it when it comes. Saves run one
   * after the other, so an older answer never overwrites a newer change.
   */
  function save(changes) {
    Object.keys(changes).forEach((k) => { state.config[k] = changes[k]; });
    emit("config");
    saving = saving.then(() => api.post("/api/config", changes)).then((res) => {
      if (res && res.config) {
        state.config = res.config;
        emit("config");
      }
      return res;
    });
    return saving.catch((error) => {
      Cmdly.ui.toast({ level: "warning", title: "Not saved", message: error.message });
      saving = Promise.resolve();
      throw error;
    });
  }

  function setUi(patch) {
    return save({ ui: Object.assign({}, state.config.ui, patch) });
  }

  // ---- SSH connections ------------------------------------------------------

  function setConnections(list, config) {
    state.connections = Array.isArray(list) ? list : [];
    state.connectionsLoaded = true;
    if (config) state.config = config;
    emit("connections");
    if (config) emit("config");
  }

  function loadConnections() {
    return api.get("/api/ssh/connections").then((data) => {
      setConnections(data.connections);
      return state.connections;
    });
  }

  /** Save one connection (POST /api/ssh/connections); resolves its public form. */
  function saveConnection(body) {
    return api.post("/api/ssh/connections", body).then((res) => {
      setConnections(res.connections, res.config);
      return res.connection;
    });
  }

  function removeConnection(name) {
    return api.post("/api/ssh/connections/remove", { name }).then((res) => {
      setConnections(res.connections, res.config);
    });
  }

  function connection(name) {
    return state.connections.find((c) => c.name === name) || null;
  }

  // ---- sessions -------------------------------------------------------------

  /** Ask which sessions are up; never rejects (unreachable means none). */
  function refreshLive() {
    return api.get("/api/ssh/sessions").then((data) => {
      const next = Object.create(null);
      ((data && data.sessions) || []).forEach((s) => { if (s && s.connected) next[s.name] = true; });
      setLive(next);
    }).catch(() => setLive(Object.create(null)));
  }

  function setLive(next) {
    const before = Object.keys(state.live).sort().join("\n");
    const after = Object.keys(next).sort().join("\n");
    state.live = next;
    if (before !== after) emit("live");
  }

  function markLive(name, up) {
    const next = Object.assign(Object.create(null), state.live);
    if (up) next[name] = true;
    else delete next[name];
    setLive(next);
  }

  function isLive(name) { return !!state.live[name]; }

  function startPolling() {
    if (pollTimer !== null) return;
    pollTimer = setInterval(() => {
      // A hidden window has no rows to repaint; it catches up when shown.
      if (document.hidden) return;
      refreshLive();
    }, LIVE_POLL_MS);
    document.addEventListener("visibilitychange", () => { if (!document.hidden) refreshLive(); });
    if (Cmdly.sshTerm && typeof Cmdly.sshTerm.onSessionEnded === "function") {
      Cmdly.sshTerm.onSessionEnded((name) => markLive(name, false));
    }
  }

  return {
    state, on, emit, load, save, setUi,
    loadConnections, saveConnection, removeConnection, connection, setConnections,
    refreshLive, markLive, isLive, startPolling, LIVE_POLL_MS,
  };
})();
