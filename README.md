# Cmdly 🚀

**Cmdly** ist eine elegante, plattformübergreifende Desktop-Applikation (macOS, Linux, Windows) für das One-Press-Starten und Überwachen von lokalen Terminal- und Remote-SSH-Befehlen. 

Sie basiert auf dem Konzept des beliebten **Schwalby**-Launchers und wurde als eigenständige native Desktop-App mit **PySide6 (Qt for Python)**, **Paramiko** und einem hochmodernen **Tesla-inspirierten Dark Smoked Frosted Glass Design** neu entwickelt.

---

## ✨ Features & Funktionen

### 1. Tesla Smoked Frosted Glass UI
* **High-Tech Obsidian & Smoked Glass Look:** Dunkle transluzente Oberflächen (`rgba(9, 10, 14, 0.95)` und `rgba(18, 21, 28, 0.75)`), feine Hairline-Konturen (`rgba(255, 255, 255, 0.09)`) und tiefe Drop-Shadows.
* **Akzentfarben:** Electric Cyan (`#38bdf8`) für Interaktion und aktive Elemente, Tesla Red (`#e82127`) für Stopp-Befehle und Unterbrechungen, Emerald Neon (`#10b981`) für Online- und Connected-Status.
* **Flüssige Widgets:** HUD-Capsule Segmented Controls, Tesla Touchscreen-Slider mit leuchtender Cyan-Führung und haptischen Tick-Notches, minimalistische Kapsel-Switches.

### 2. Companion Computer Bar & In-App Modal Overlay
* **Status-Strip oben:** Schlanke Telemetrie-Leiste mit Chip-Icon, Name, Host/IP, Echtzeit-Statusdot und Latenzanzeige (z.B. `ONLINE · 4.2 ms`).
* **Zustandsabhängige Rahmenfarbe:** 
  * 🟢 **ONLINE** (Emerald Neon) – Begleitcomputer erreichbar
  * 🔴 **OFFLINE** (Tesla Red) – Keine Antwort vor Timeout
  * 🟡 **CHECKING / ERROR** (Amber) – Verbindung wird geprüft oder Ping-Fehler
  * ⚪ **NOT SET** (Muted) – Noch kein Host konfiguriert
* **In-App Modal Overlay:** Die Konfiguration des Begleitcomputers öffnet sich als elegantes In-App-Modal (Dark Frosted Glass mit abgedunkeltem Hintergrund), ohne ein zweites Betriebssystem-Fenster zu erzwingen.
  * Umschaltung: **Ping** (ICMP/TCP-Ping) oder **SSH** (gespeicherte SSH-Credentials)
  * Stepped Sliders: **Ping Interval** (1s, 2s, 3s, 5s, 10s) und **Offline Timeout** (3s bis 30s) mit dynamischer Kopplung
  * Speichern, Zurücksetzen ("Clear") und Abbrechen

### 3. Shelf (Befehlsleiste)
* **Bis zu 12 Start-Buttons** für Missionsskripte, Server, Video-Pipelines, Logs oder System-Tools.
* Jeder Button führt den Befehl entweder **Lokal** auf diesem Computer oder remote via **SSH** aus.
* **Zwei Ausführungs-Modi:**
  * 💻 **Terminal (Standard):** Führt `cd -- <Ordner> && <Befehl>` in einer eigenen interaktiven PTY-Shell aus.
    * Zeigt einen pulsierenden grünen Dot (`●`), während das Programm läuft.
    * Pfeil (`>`): Öffnet das floating Terminal-Fenster zum Mitlesen und Eingeben.
    * **Stoppen:** Während das Programm läuft, verwandelt sich das Aktionssymbol in ein rotes Stop-Symbol (`■`), das `Ctrl-C` (`\x03`) sendet und die Session beendet.
    * **Restart on Press (Optional):** Erneuter Klick auf einen bereits laufenden Button sendet automatisch `Ctrl-C`, wartet 1 Sekunde und startet den Befehl im selben Terminal neu.
  * ⚙️ **Background (Hintergrund):** Einmaliges Ausführen ohne Terminalfenster (lokal als Hintergrund-Prozess, über SSH via `nohup`). Fehler oder Ausgaben werden in der Konsole angezeigt.

### 4. Dedicated Floating Terminal Console
* Eigenständiges, rahmenloses Floating-Fenster im smoked obsidian Design.
* **Custom Glass Header:**
  * `[>_]` Terminal-Icon, Befehlsname (z.B. `ls`) und Host/Ziel
  * `● CONNECTED` / `DISCONNECTED` Status-Pill
  * Fenster-Steuerung: Pin (`📌`), Maximize/Restore (`🗖`), Restart/Interrupt (`↻`), Schließen (`✕`)
* **Echte ANSI-Farbunterstützung** (Cyan, Grün, Gelb, Rot, Bold, etc.).
* Interaktive Befehlseingabe mit Schnelltasten für Enter, Ctrl+C und Clear.
* Echte PTY-Unterstützung auf macOS und Linux (`pty.openpty`), native Windows-Shell-Unterstützung.

### 5. Button Editor View
* Live-Befehlsvorschau (Command Preview): Zeigt exakt, was ausgeführt wird (z.B. `cd ~/mission && ./start.sh &` oder `ssh corvus@192.168.2.10 'cd /opt/flight && python main.py'`).
* **Segmented Control [Local | SSH]** für die Zielauswahl.
* **SSH-Verwaltung:** Auswahl gespeicherter Verbindungen oder "New connection…" mit Feldern für Host, Port (22), Benutzer, Passwort und Private-Key-Datei.
* Schalter für "Run in an interactive terminal" und "Restart on press".

### 6. Persistenz
* Alle Einstellungen (Buttons, Begleitcomputer, SSH-Verbindungen) werden atomar in `~/.cmdly/config.json` gesichert.

---

## 🚀 Installation & Start

### Voraussetzungen
* Python 3.10+ (empfohlen: 3.11, 3.12 oder 3.13)

### Schnellstart

```bash
# 1. Repository klonen oder in das Verzeichnis wechseln:
cd /Users/maximilian/Developer/Cmdly

# 2. Virtuelle Umgebung aktivieren (falls noch nicht aktiv):
source .venv/bin/activate

# 3. Abhängigkeiten installieren:
pip install -r requirements.txt

# 4. Cmdly starten:
./run.sh
# oder
python3 run.py
```

---

## 🧪 Tests ausführen

Das Projekt verfügt über eine vollständige Test-Suite:

```bash
### 6. Settings Modal & Multi-Theme System
* **Unten-Links Settings-Button (⚙️):** Ein Klick auf "Settings" öffnet das In-App Modal Overlay für Einstellungen.
* **5 Integrierte Themes mit Live-Umschaltung:**
  * 🌌 **Tesla Cyber (Dark Smoked):** Obsidian Glas, Electric Cyan Akzente (`#38bdf8`), Tesla Red Stopp.
  * 🌃 **Midnight Obsidian (Deep Indigo):** Tiefblaue Nacht-Ästhetik mit Indigo-Neon (`#818cf8`).
  * 🛸 **Corvus Flight Deck (Charcoal):** Klassisches Schwalby Titanium-Design mit Aviation Amber (`#f59e0b`).
  * 🍏 **Apple Smoked Glass:** macOS Sonoma/Sequoia Smoked Glass mit Apple Blue (`#0a84ff`).
  * ☀️ **Light Frosted (Clear Day):** Helles, transparentes Frosted Glass mit Slate Blue (`#0071e3`).
* **Transluzentes Styling:** Nutzt `Qt.WA_TranslucentBackground` mit transluzenten Smoked-Glass-Oberflächen.
* **Persistenz:** Das gewählte Theme wird automatisch in `~/.cmdly/config.json` gesichert.

---

## 🚀 Installation & Start

### Voraussetzungen
* Python 3.10+ (empfohlen: 3.11, 3.12 oder 3.13)

### Schnellstart

```bash
# 1. Repository klonen oder in das Verzeichnis wechseln:
cd /Users/maximilian/Developer/Cmdly

# 2. Virtuelle Umgebung aktivieren (falls noch nicht aktiv):
source .venv/bin/activate

# 3. Abhängigkeiten installieren:
pip install -r requirements.txt

# 4. Cmdly starten:
./run.sh
# oder
python3 run.py
```

---

## 🧪 Tests ausführen

Das Projekt verfügt über eine vollständige Test-Suite (15 Tests):

```bash
.venv/bin/python3 -m unittest discover tests
```

---

## 📁 Projektstruktur

```
Cmdly/
├── app/
│   ├── config.py              # Konfigurationsmanager (~/.cmdly/config.json & Theme-Speicherung)
│   ├── models.py              # Datenmodelle & Shell-Quoting-Logik
│   ├── main.py                # Qt-Anwendungs-Einstiegspunkt
│   ├── network/
│   │   ├── ping_service.py    # Asynchroner Companion-Pinger & RTT-Messung
│   │   └── ssh_manager.py     # SSH-Verbindungen & Detached-Execution
│   ├── sessions/
│   │   ├── base_session.py    # Basisklasse für Terminal-Sessions
│   │   ├── local_session.py   # Lokale interaktive PTY-Shell
│   │   ├── ssh_session.py     # Interaktive Paramiko-SSH-Shell
│   │   └── session_manager.py # Session-Lifecycle & Event-Routing
│   └── ui/
│       ├── icons.py           # Vektor-SVG-Icons (CPU, Settings, Server, Play, Stop, etc.)
│       ├── styles.py          # Multi-Theme-Engine & SF Pro Typografie-System
│       ├── widgets/
│       │   ├── companion_bar.py    # Companion-Telemetrie-Status-Strip
│       │   ├── companion_modal.py  # In-App Begleitcomputer-Modal
│       │   ├── settings_modal.py   # In-App Settings & Theme-Auswahl-Modal
│       │   ├── modal_overlay.py    # Frosted Glass Modal-Backdrop
│       │   ├── ticked_slider.py    # HUD-Touchscreen-Slider mit Ticks
│       │   ├── segmented_control.py# Capsule Segmented Control
│       │   ├── toggle_switch.py    # Minimalistischer Capsule-Switch
│       │   ├── shelf_row.py        # Taktile Frosted Glass Button-Zeile
│       │   └── terminal_widget.py  # ANSI-Terminal-Widget
│       ├── dialogs/
│       │   └── terminal_window.py  # Dedicated Floating Terminal Window
│       ├── views/
│       │   ├── shelf_view.py       # Shelf-Ansicht (resizable mit Top-Alignment)
│       │   └── editor_view.py      # Scrollbarer Button-Editor
│       └── main_window.py          # Hauptfenster mit Bottom-Bar (Settings & Status)
├── tests/
│   ├── test_cmdly.py          # Unit-Tests für Modelle & Konfiguration
│   └── test_ui_and_sessions.py# Integrationstests für UI, Themes & PTY-Sessions
├── requirements.txt           # PySide6 & Paramiko
├── run.py                     # Startskript
├── run.sh                     # Ausführbares Shell-Startskript
└── README.md
```
