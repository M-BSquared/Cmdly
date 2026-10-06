# Cmdly — Agent Context

Read this first. It describes what Cmdly is, how it is put together, and the
rules a change has to keep.

## Product

Cmdly is a desktop app (macOS, Linux) with a shelf of one-press buttons that
start programs on this computer or on a companion computer over SSH, in a
real terminal or in the background. It is the standalone form of the
Schwalby / SSH Launcher plugin of Corvus GCS and follows Corvus' structure:
a Python backend plus a web frontend in a PySide6/QtWebEngine window.

## Architecture

- `cmdly/app.py` starts the backend on a thread and shows `src/` in a
  QtWebEngine window. It owns the native windows: the main window (macOS:
  unified title bar via Qt's expanded client area, vibrancy via
  `native_window.MacBlur`) and a frameless window per terminal (`popout.html`).
- `cmdly/server.py` is a `ThreadingHTTPServer` on 127.0.0.1 only. Routes are
  registered with `@route` (`cmdly/routing.py`); extra route groups are mixins
  in `cmdly/routes/`. Every request must name the server as
  `localhost`/`127.0.0.1` in its Host header; every POST and the WebSocket
  upgrade must come from that origin.
- Terminals: `ssh_bridge.SshBridge` holds every session by name (SSH and the
  local PTY shell from `local_shell.py` alike). Output goes to the page over
  one WebSocket per terminal (`/api/ssh/ws`), SSE + POSTs as fallback.
- `config.py` owns `~/.cmdly/config.json` (0600, atomic writes). The page
  never receives a password: `Config.public()` is what it gets.
- `launcher.py` holds the pure rules (buttons, companions, connections).
  `src/js/launch.js` and `src/js/companion.js` keep the few the page needs
  while a form is typed in; keep both sides in step.

## Frontend rules

- Every colour, radius, blur, shadow and spacing is a token in
  `src/css/themes.css`. Surfaces use the one glass material (`--glass`,
  `--glass-thin`, `--glass-thick`, `--hairline`, `--sheen`, `--blur`);
  do not invent a new translucency.
- Spacing is the 4 px grid (`--space-*`). Gutters 16 px, 12 px between cards.
- Controls come from `Cmdly.ui` (`src/js/ui.js`, shared with Corvus). Long
  explanations go behind an info icon (`ui.field({info})`, `ui.infoHint`),
  never as paragraphs under a field.
- The window is a column of bands that never overlap: title bar, companion
  card, the scrolling view, the status line. Anything that can grow scrolls.
- Questions are `Cmdly.dialogs.confirm`, never `window.confirm`.
- Terminal windows are Corvus' (`float-window.js`, `term-window.js`,
  `popout*.js`, `ssh-term.js`); change them in Corvus first, then here.

## Versions and packaging

- `VERSION` is the only version; nothing else may contain a version literal.
- Python dependencies live only in `pyproject.toml` `[dependency-groups]`.
- PySide6 (LGPL), never PyQt6.
- `./build.sh` dispatches per host. AppImages are built on the oldest Ubuntu
  the PySide6 wheels install on (x86_64: 22.04, aarch64: 24.04), with the
  appimagetool from github.com/AppImage/appimagetool.

## Tests

- `python -m pytest` (tests get their own `CMDLY_HOME`, see `tests/conftest.py`).
- `node tests/test_frontend_*.js` (no browser, no test runner).
- `ruff check cmdly tests tools`.
