<p align="center">
  <img src="assets/icon.png" width="128" alt="Cmdly">
</p>

<h1 align="center">Cmdly</h1>

<p align="center">
  <em>Ein-Klick-Buttons für die Programme, die du immer wieder startest –<br>
  auf diesem Rechner oder per SSH auf einem anderen.</em>
</p>

---

## Was ist Cmdly?

Cmdly ist eine Desktop-App (macOS und Linux) mit einer Leiste aus Start-Buttons.
Jeder Button startet einen Befehl in einem Ordner – lokal oder auf einem
Begleitcomputer per SSH – entweder in einem echten Terminal oder im
Hintergrund. Oben zeigt eine Statusleiste, ob der Begleitcomputer erreichbar
ist (Ping mit Latenz) und öffnet auf Wunsch direkt eine SSH-Shell auf ihm.

Cmdly ist die eigenständige Version des Schwalby-/SSH-Launcher-Plugins aus
[Corvus GCS](https://github.com/M-BSquared/CorvusGCS) und teilt dessen
Architektur: ein Python-Backend und eine Web-Oberfläche in einem
PySide6/QtWebEngine-Fenster, dieselben Terminal-Fenster (xterm.js) und
dieselben UI-Komponenten.

## Funktionen

- **Buttons** (bis zu 24): Label, Ziel (Lokal / SSH), Ordner, Befehl,
  Live-Vorschau des ausgeführten Befehls, Sortieren per Drag & Drop.
  - **Terminal-Modus:** `cd -- <Ordner> && <Befehl>` in einer eigenen Shell
    pro Button (echtes PTY: Ctrl-C, `top`, `vim`, Passwortabfragen).
    Erneutes Drücken führt den Befehl im selben Terminal erneut aus;
    mit *Restart on press* wird vorher Ctrl-C gesendet.
  - **Hintergrund-Modus:** lokal als Kindprozess (endet mit Cmdly), per SSH
    mit `nohup` (läuft weiter, auch wenn Cmdly beendet wird).
  - Läuft ein Programm, wird der Stift zum Stopp-Button (Ctrl-C, dann Session
    schließen). Fehler stehen als Warn-Symbol mit Popover direkt in der Zeile.
- **Terminal-Fenster wie in Corvus:** standardmäßig eigene, rahmenlose
  Fenster (überall platzierbar, über Cmdly anheftbar, maximierbar, zurück ins
  Hauptfenster ziehbar), optional als Rahmen im Hauptfenster. Frosted Glass
  oder deckend; der Verlauf wird beim erneuten Öffnen wiederhergestellt.
- **Begleitcomputer:** mehrere speicherbar, Schnellumschalter, Ping- oder
  SSH-Modus, einstellbares Intervall und Timeout, Filter „nur ausführbare
  Buttons zeigen“.
- **SSH-Verbindungen:** gespeichert mit Passwort oder Schlüsseldatei, „Test“-
  Login, Umbenennen wirkt auf alle Buttons. Passwörter verlassen das Backend
  nie. Fehlt eine Verbindung (z. B. nach einem Import), fragt der erste
  Klick einmal danach.
- **Aussehen:** Automatisch (folgt dem System), Grün, Blau, Orange, Pink,
  Hell, Hell-Orange. Unter macOS mit Vibrancy (der Desktop scheint
  weichgezeichnet durch) und in das Fenster integrierter Titelleiste.
- **Import/Export** des Setups (wählbare Bereiche, Passwörter optional),
  Update-Hinweis bei neuen Releases.

## Starten aus dem Quellcode

Voraussetzung: Python ≥ 3.12.

```bash
./run.sh
```

Der erste Start legt `.venv` an und installiert die Gruppe `dev` aus
`pyproject.toml`; danach startet Cmdly ohne Netzwerk. Unter Linux trägt
`./run.sh --desktop-entry` den Checkout ins App-Menü ein.

Die Einstellungen liegen in `~/.cmdly/config.json` (nur für dich lesbar).
Eine Konfiguration der alten PySide-Widget-Version wird beim ersten Start
automatisch übernommen.

## Bauen

| Plattform | Befehl | Ergebnis |
| --- | --- | --- |
| macOS (arm64/x86_64) | `./build.sh --dmg` | `dist/Cmdly.app`, `dist/Cmdly-<version>-macOS-<arch>.dmg` |
| Linux (x86_64/aarch64) | `./build.sh` | `dist/Cmdly-<version>-<arch>.AppImage` |
| Linux-AppImage von macOS aus | `tools/appimage-in-docker.sh x86_64` | wie oben, gebaut in Docker |

- Die macOS-App bündelt ein relokierbares Framework-Python, Qt und alle
  Abhängigkeiten, ad-hoc signiert. Mit `CODESIGN_IDENTITY="Developer ID
  Application: …"` wird richtig signiert.
- Das AppImage nutzt das aktuelle
  [`appimagetool`](https://github.com/AppImage/appimagetool) (gepinnt auf
  1.9.1, `CMDLY_APPIMAGETOOL_VERSION=continuous` für den neuesten Build)
  mit statischer Runtime, also ohne `libfuse2`-Abhängigkeit auf dem
  Zielsystem.
- Ein AppImage läuft nur auf Systemen mit mindestens der glibc des
  Build-Systems. Weil die PySide6-Wheels glibc 2.34 (x86_64) bzw. 2.39
  (aarch64) voraussetzen, wird x86_64 auf Ubuntu 22.04 und aarch64 auf
  Ubuntu 24.04 gebaut – `tools/appimage-in-docker.sh` macht genau das.
- `tools/qt_bundle.py` entfernt alle Qt-Module, die Cmdly nicht lädt
  (≈ ein Drittel von PySide6), und bricht ab, wenn danach eine Bibliothek
  fehlen würde.

## Struktur

```
cmdly/          Python: Backend (server.py), Qt-Fenster (app.py),
                SSH-Bridge, lokale PTY-Shell, WebSocket, Ping, Config
  routes/       zusätzliche API-Routen (Import/Export)
src/            Web-Oberfläche
  css/          themes.css (alle Tokens) → components.css → base/app/windows.css
  js/           ui.js (Komponenten), store/launch/shelf/companion/settings …
  vendor/       xterm.js, Lucide, Schriften (offline)
assets/         App-Icon
tools/          make_icon.py, qt_bundle.py, appimage-in-docker.sh
tests/          pytest (tests/test_*.py) und Node (tests/test_frontend_*.js)
```

## Tests

```bash
.venv/bin/python -m pytest
for f in tests/test_frontend_*.js; do node "$f"; done
.venv/bin/ruff check cmdly tests tools
```
