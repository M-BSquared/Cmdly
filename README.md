<p align="center">
  <img src="assets/icon.png" width="112" alt="Cmdly">
</p>

<h1 align="center">Cmdly</h1>

<p align="center">
  <strong>Ein Klick statt fünf Terminals.</strong><br>
  Buttons für die Programme, die du immer wieder startest:<br>
  auf diesem Rechner oder per SSH auf einem anderen.
</p>

<p align="center">
  <a href="https://github.com/M-BSquared/Cmdly/actions/workflows/build.yml"><img src="https://github.com/M-BSquared/Cmdly/actions/workflows/build.yml/badge.svg" alt="Build"></a>
  <img src="https://img.shields.io/badge/macOS-arm64%20%7C%20x86__64-1C1F25?logo=apple&logoColor=white" alt="macOS">
  <img src="https://img.shields.io/badge/Linux-AppImage-1C1F25?logo=linux&logoColor=white" alt="Linux">
  <img src="https://img.shields.io/badge/Python-3.12%2B-3B9EFF?logo=python&logoColor=white" alt="Python 3.12+">
  <img src="https://img.shields.io/badge/Qt-PySide6-41CD52?logo=qt&logoColor=white" alt="PySide6">
</p>

<p align="center">
  <img src="docs/images/hero.png" alt="Cmdly: das Hauptfenster mit zwei Begleitcomputern und fünf Buttons, daneben ein Terminal-Fenster mit einem laufenden Mission Planner">
</p>

---

## Warum Cmdly?

Wer mit einem Begleitcomputer arbeitet (einer Drohne, einem Roboter, einem
Raspberry Pi im Feld), startet jeden Tag dieselben Befehle: SSH-Login, in den
Ordner wechseln, Bridge starten, Kamera-Stream starten, Logs holen. Cmdly
macht aus jedem dieser Befehle einen Button.

- **Ein Klick** startet einen Befehl in einem echten Terminal oder still im Hintergrund.
- **Lokal oder per SSH**, mit gespeicherten Verbindungen, Passwort oder Schlüsseldatei.
- **Auf einen Blick**, ob deine Rechner erreichbar sind: jeder wird gepingt, mit Latenz.
- **Echte Terminals** in eigenen Fenstern: Ctrl-C, `top`, `vim`, Passwortabfragen.

Cmdly ist die eigenständige Version des SSH-Launcher-Plugins aus
[Corvus GCS](https://github.com/M-BSquared/CorvusGCS).

## Funktionen

<table>
<tr>
<td width="50%" valign="top">

### Buttons für deine Befehle

Label, Ziel (lokal oder SSH), Ordner und Befehl, mit Live-Vorschau der Zeile,
die tatsächlich ausgeführt wird. Sortieren per Drag & Drop.

- **Terminal-Modus:** eine eigene Shell pro Button. Erneutes Drücken führt
  den Befehl dort erneut aus, auf Wunsch mit Ctrl-C davor.
- **Hintergrund-Modus:** lokal als Kindprozess, per SSH mit `nohup`.
- **Der Pfeil** im Button startet den Befehl und öffnet sofort sein Terminal.
- Läuft etwas, zeigt die Zeile einen grünen Punkt und einen Stopp-Button.

</td>
<td width="50%" valign="top">
<img src="docs/images/editor.png" alt="Der Editor eines Buttons">
</td>
</tr>
<tr>
<td width="50%" valign="top">
<img src="docs/images/settings.png" alt="Die Einstellungen mit der Theme-Auswahl">
</td>
<td width="50%" valign="top">

### Rechner im Blick

Oben im Fenster steht jeder Begleitcomputer als eigene Karte mit Status
(Online mit Latenz, Checking, Offline). Ein Klick auf die Karte einer
SSH-Verbindung öffnet direkt eine Shell darauf.

- Jede gespeicherte SSH-Verbindung lässt sich mit einem Schalter oben anzeigen.
- Reine Ping-Rechner (Router, Funkstrecke) gehen auch.
- **Filter:** blendet aus, was gerade offline ist, Buttons und Karten.
- Gepingt wird nur, was oben angezeigt wird.

</td>
</tr>
</table>

### Sieht aus wie zu Hause

<p align="center">
  <img src="docs/images/themes.png" alt="Cmdly in den Themes Blau, Grün und Hell-Orange">
</p>

Sieben Themes (Automatisch, Blau, Grün, Orange, Pink, Hell, Hell-Orange). Unter
macOS scheint der Desktop weichgezeichnet durch das Fenster (Vibrancy), die
Titelleiste ist Teil des Fensters, Terminals sind aus Milchglas.

### Und außerdem

- **Terminal-Fenster** wie in Corvus: rahmenlos, frei platzierbar, über Cmdly
  anheftbar, zurück ins Hauptfenster ziehbar. Der Verlauf bleibt beim erneuten
  Öffnen erhalten.
- **Sichere Verbindungen:** Passwörter bleiben im Backend
  (`~/.cmdly/config.json`, nur für dich lesbar) und erreichen die Oberfläche nie.
  Änderst du eine Verbindung, ziehen alle Buttons und Karten mit.
- **Import/Export** des ganzen Setups, Passwörter optional.
- **Update-Hinweis**, sobald ein neues Release erscheint.

## Installation

Fertige Builds für macOS (`.dmg`) und Linux (`.AppImage`) liegen unter
[**Releases**](https://github.com/M-BSquared/Cmdly/releases).

Oder direkt aus dem Quellcode (Python ≥ 3.12):

```bash
git clone https://github.com/M-BSquared/Cmdly.git
cd Cmdly
./run.sh
```

Der erste Start legt `.venv` an und installiert die Abhängigkeiten aus
`pyproject.toml`; danach startet Cmdly ohne Netzwerk. Unter Linux trägt
`./run.sh --desktop-entry` den Checkout ins App-Menü ein.

## In drei Schritten

1. **Verbindung anlegen:** Settings → SSH → *Add a connection*. Mit *Test*
   prüfst du den Login, mit *Show in the main window* erscheint der Rechner oben.
2. **Button anlegen:** *Add* im Hauptfenster, Ziel und Befehl eintragen.
3. **Drücken.** Mit dem Pfeil im Button öffnet sich gleich das Terminal dazu.

<details>
<summary><strong>Selbst bauen</strong></summary>

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
  1.9.1, `CMDLY_APPIMAGETOOL_VERSION=continuous` für den neuesten Build) mit
  statischer Runtime, also ohne `libfuse2` auf dem Zielsystem.
- Ein AppImage läuft nur mit mindestens der glibc des Build-Systems. Die
  PySide6-Wheels setzen glibc 2.34 (x86_64) bzw. 2.39 (aarch64) voraus, daher
  wird x86_64 auf Ubuntu 22.04 und aarch64 auf Ubuntu 24.04 gebaut;
  `tools/appimage-in-docker.sh` macht genau das.
- `tools/qt_bundle.py` entfernt alle Qt-Module, die Cmdly nicht lädt
  (etwa ein Drittel von PySide6), und bricht ab, wenn danach eine Bibliothek
  fehlen würde.

</details>

<details>
<summary><strong>Aufbau</strong></summary>

Ein Python-Backend (`ThreadingHTTPServer`, nur auf 127.0.0.1) und eine
Web-Oberfläche in einem PySide6/QtWebEngine-Fenster, wie in Corvus GCS.
Terminals laufen über eine WebSocket pro Fenster und xterm.js.

```
cmdly/          Python: Backend (server.py), Qt-Fenster (app.py),
                SSH-Bridge, lokale PTY-Shell, WebSocket, Ping, Config
  routes/       zusätzliche API-Routen (Import/Export)
src/            Web-Oberfläche
  css/          themes.css (alle Tokens) → components.css → base/app/windows.css
  js/           ui.js (Komponenten), store/launch/shelf/companion/settings …
  vendor/       xterm.js, Lucide, Schriften (offline)
assets/         App-Icon
docs/images/    die Bilder dieser README
tools/          make_icon.py, readme_shots.py (README-Bilder und Social Preview),
                qt_bundle.py, appimage-in-docker.sh
tests/          pytest (tests/test_*.py) und Node (tests/test_frontend_*.js)
```

</details>

<details>
<summary><strong>Entwickeln und testen</strong></summary>

```bash
.venv/bin/python -m pytest
for f in tests/test_frontend_*.js; do node "$f"; done
.venv/bin/ruff check cmdly tests tools
```

Die Bilder dieser README erzeugt `tools/readme_shots.py`: Es startet Cmdly mit
einem erfundenen Demo-Setup in einem temporären `CMDLY_HOME`, lässt Chromium
jedes Fenster in doppelter Auflösung zeichnen und legt es mit Schatten und
Milchglas auf ein generiertes Hintergrundbild. Es nimmt nichts vom Bildschirm
auf und zeigt keine eigenen Rechner oder Buttons.

```bash
.venv/bin/python tools/readme_shots.py            # alle Bilder
.venv/bin/python tools/readme_shots.py hero       # nur einzelne
```

Die Einstellungen liegen in `~/.cmdly/config.json`; die Konfiguration der
alten PySide-Widget-Version wird beim ersten Start übernommen.

</details>
