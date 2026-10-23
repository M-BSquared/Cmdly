"use strict";
window.Cmdly = window.Cmdly || {};

/*
  Cmdly.connections — the SSH connection form, wherever one is typed in.

  Three places need it: a button's editor ("New connection…"), the companion
  computer dialog, and Settings > Connections. Plus one more nobody opens on
  purpose: a press whose connection this computer does not have, or whose
  login was refused, asks for it once (prompt), saves it under the name the
  button already carries, and the press goes on.

  The form is built only while it is in use: a password field that is merely
  hidden is still a password field in the page. A stored password never comes
  to the page at all; an edit that leaves the field empty keeps it.
*/
Cmdly.connections = (function () {
  const L = () => Cmdly.launch;

  const FIELDS = [
    { key: "name", label: "Name", placeholder: "companion-01",
      info: "The name this connection is saved under, and what buttons show. " +
            "Left empty, it is saved as user@host." },
    { key: "host", label: "Host", placeholder: "192.168.2.10", mono: true },
    { key: "port", label: "Port", type: "number", mono: true, placeholder: "22", half: true },
    { key: "username", label: "User", placeholder: "pi", half: true },
    { key: "password", label: "Password", type: "password", mono: true,
      info: "Optional when a key file is set. Kept by Cmdly's backend in " +
            "~/.cmdly/config.json (readable only by you) and never shown again." },
    { key: "key_path", label: "Key file", mono: true, placeholder: "~/.ssh/id_ed25519",
      info: "A private key to log in with instead of a password. The SSH agent " +
            "and the keys in ~/.ssh are not tried when this or a password is set." },
  ];

  function blank() {
    return { name: "", host: "", port: "22", username: "", password: "", key_path: "" };
  }

  /**
   * The form. `initial` fills it (a saved connection: its password stays
   * with the backend, so the field says so instead). Returns
   * {el, value(), error(taken), focus()}.
   */
  function form(initial, opts) {
    const ui = Cmdly.ui;
    const o = opts || {};
    const value = Object.assign(blank(), initial || {}, { password: "" });
    value.port = String(value.port || "22");
    const el = document.createElement("div");
    el.className = "conn-form";
    const inputs = {};
    let row = null;
    FIELDS.forEach((f) => {
      if (o.lockName && f.key === "name") return;
      const control = ui.input({
        type: f.type || "text",
        value: value[f.key],
        placeholder: f.key === "password" && initial && initial.has_password
          ? "Saved. Type to replace it" : (f.placeholder || ""),
        mono: f.mono,
        ariaLabel: f.label,
        autocomplete: false,
        spellcheck: false,
        onInput: (v) => { value[f.key] = v; if (typeof o.onInput === "function") o.onInput(); },
      });
      if (f.key === "port") { control.min = 1; control.max = 65535; }
      inputs[f.key] = control;
      const field = ui.field({ label: f.label, control, info: f.info });
      if (f.half) {
        if (!row) {
          row = document.createElement("div");
          row.className = "field-row";
          el.appendChild(row);
        }
        row.appendChild(field);
        field.classList.add("field-inline");
      } else {
        row = null;
        el.appendChild(field);
      }
    });
    return {
      el,
      value: () => Object.assign({}, value),
      error: (taken) => L().connectionError(value, taken),
      body: () => L().connectionBody(value),
      focus: () => {
        const first = inputs.host && !value.host ? inputs.host : (inputs.name || inputs.host);
        if (first) first.focus();
      },
    };
  }

  /** Try a connection's login (saved, or the form as typed). */
  function test(body, btn, message) {
    const ui = Cmdly.ui;
    ui.setBusy(btn, true);
    message.show("Connecting…", "");
    return Cmdly.api.post("/api/ssh/connections/test", body).catch(Cmdly.api.replyOf).then((res) => {
      ui.setBusy(btn, false);
      if (res && res.ok) message.show("Logged in. The connection works.", "ok");
      else message.show((res && res.error) || "The login failed.", "err");
      return !!(res && res.ok);
    });
  }

  /**
   * Buttons, computers above and pings follow an edited connection by
   * themselves (cmdly/config.py). A terminal that is already open does not:
   * it is logged in as before, until it is stopped and started again.
   */
  function warnOpenSessions(before, typed, name) {
    if (!before) return;
    const changed = ["host", "username", "key_path"].some((k) => String(before[k] || "") !== String(typed[k] || ""))
      || String(before.port || 22) !== String(typed.port || 22) || !!typed.password;
    if (!changed) return;
    const store = Cmdly.store;
    const entries = store.state.config.buttons.filter((b) => b.connection === name);
    const live = entries.some((b) => store.isLive(L().sessionName(b)));
    if (live) {
      Cmdly.ui.toast({
        level: "info", title: "Connection saved",
        message: "Terminals that are already open keep the old login. Stop and start them again to use the new one.",
      });
    }
  }

  /**
   * A dialog for one connection: new (no `conn`) or a saved one. Resolves the
   * saved connection's name, or "" when it was cancelled or deleted.
   */
  function edit(conn, opts) {
    const ui = Cmdly.ui;
    const o = opts || {};
    const store = Cmdly.store;
    const existing = conn ? conn.name : "";
    return new Promise((resolve) => {
      let result = "";
      const body = document.createElement("div");
      body.className = "conn-dialog";
      if (o.intro) {
        const intro = document.createElement("p");
        intro.className = "dialog-intro";
        intro.textContent = o.intro;
        body.appendChild(intro);
      }
      const f = form(conn, { onInput: paint, lockName: !!o.lockName });
      // Whether the main window shows this connection as a computer it pings.
      const watchedBefore = !!existing && Cmdly.companion.watching(existing);
      let watch = watchedBefore;
      if (!o.lockName) {
        const watchToggle = ui.toggle({
          value: watch, ariaLabel: "Show in the main window",
          onChange: (on) => { watch = !!on; },
        });
        body.appendChild(ui.field({
          label: "Show in the main window", control: watchToggle.el, className: "field-switch",
          info: "Adds this connection to the computers at the top of the main " +
                "window. Each one is pinged on its own, and shows whether it is online.",
        }));
      }
      body.appendChild(f.el);
      const msg = ui.message({ className: "dialog-msg" });
      body.appendChild(msg.el);

      const taken = () => store.state.connections.map((c) => c.name).filter((n) => n !== existing);
      const payload = () => {
        const b = f.body();
        if (o.lockName) b.name = existing || o.name;
        if (existing) b.original_name = existing;
        return b;
      };

      const saveBtn = ui.button({
        variant: "primary", icon: "check", label: "Save",
        onClick: () => {
          ui.setBusy(saveBtn, true);
          const before = conn ? Object.assign({}, conn) : null;
          const typed = f.value();
          store.saveConnection(payload()).then((saved) => {
            result = saved.name;
            warnOpenSessions(before, typed, saved.name);
            return o.lockName || watch === watchedBefore ? null : Cmdly.companion.setWatched(saved.name, watch);
          }).then(() => {
            dialog.close();
          }).catch((error) => {
            ui.setBusy(saveBtn, false);
            msg.show(error.message, "err");
          });
        },
      });
      const testBtn = ui.button({
        variant: "secondary", icon: "plug-zap", label: "Test",
        title: "Log in once to check the address, user and password",
        onClick: () => test(payload(), testBtn, msg),
      });
      const deleteBtn = existing && !o.lockName ? ui.button({
        variant: "danger", icon: "trash-2", label: "Delete",
        onClick: () => {
          const users = store.state.config.buttons.filter((b) => b.connection === existing).length;
          Cmdly.dialogs.confirm({
            title: `Delete “${existing}”?`,
            text: users ? `${users} button${users > 1 ? "s use" : " uses"} it, and will ask for its address and login on the next press.`
              : "The saved address and login are removed.",
            confirm: "Delete", danger: true,
          }).then((go) => {
            if (!go) return;
            store.removeConnection(existing).then(() => dialog.close())
              .catch((error) => msg.show(error.message, "err"));
          });
        },
      }) : null;

      function paint() {
        const problem = f.error(taken());
        saveBtn.disabled = !!problem;
        saveBtn.title = problem;
        testBtn.disabled = !!L().hostError(f.value().host) || !String(f.value().username || "").trim();
      }
      paint();

      const dialog = ui.modal({
        title: o.title || (existing ? `Connection “${existing}”` : "New SSH connection"),
        size: "md",
        body,
        actions: [deleteBtn, testBtn, saveBtn],
        onClose: () => resolve(result),
      });
      dialog.open();
      setTimeout(() => f.focus(), 0);
    });
  }

  /**
   * A press could not run for want of a connection (or its login): ask for
   * it, save it under the name the button carries. Resolves whether it was
   * saved. The power menu asks too, when sudo wants a password the
   * connection has none saved to give (`needs` "sudo-password").
   */
  function prompt(reply) {
    const r = reply || {};
    const name = String(r.connection || "").trim();
    if (!name) return Promise.resolve(false);
    const known = Cmdly.store.connection(name);
    const intro = r.needs === "credentials"
      ? `The login to “${name}” was refused. Check the user and password, or set a key file.`
      : r.needs === "sudo-password"
        ? `sudo on “${name}” asked for a password. Save the connection's login password ` +
          "and Cmdly types it into sudo itself whenever it shuts that computer down or reboots it."
        : `This computer has no connection named “${name}” yet. Enter its address and login once; ` +
          "every button that uses it works from then on.";
    return edit(known || { name }, {
      title: r.needs === "credentials" ? "Log in again"
        : r.needs === "sudo-password" ? "Save sudo's password" : "Set up the connection",
      intro, lockName: true, name,
    }).then((saved) => !!saved);
  }

  return { form, edit, prompt, test, blank, FIELDS };
})();
