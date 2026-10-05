# Cmdly 🚀

**Cmdly** ist eine elegante, plattformübergreifende Desktop-Applikation (macOS, Linux, Windows) für das One-Press-Starten und Überwachen von lokalen Terminal- und Remote-SSH-Befehlen. 

Sie basiert auf dem Konzept und Design des beliebten **Schwalby**-Plugins (bekannt aus Flug- und Ground-Station-Workflows für Begleitcomputer und Missionsprogramme) und wurde als eigenständige native Desktop-App mit **PySide6 (Qt for Python)** und **Paramiko** neu implementiert.

---

## ✨ Features & Funktionen

### 1. Companion Computer Bar (Begleitcomputer-Überwachung)
* **Status-Strip oben:** Schlanke Leiste mit CPU-Icon, Name, Host/IP, Echtzeit-Statusdot und Latenzanzeige (z.B. `Online · 4.2 ms`).
* **Zustandsabhängige Rahmenfarbe:** 
  * 🟢 **Online** (grün) – Antwort innerhalb des eingestellten Timeouts erhalten
  * 🔴 **Offline** (rot) – Keine Antwort vor Timeout
  * 🟡 **Checking / Cannot ping** (gelb/orange) – Verbindung wird geprüft oder Ping-Fehler
  * ⚪ **Not set** (neutral) – Noch kein Host konfiguriert
* **Direktes SSH-Terminal:** Sobald der Begleitcomputer online ist und eine SSH-Verbindung zugewiesen ist, erscheint rechts ein Pfeil (`>`), der direkt eine interaktive SSH-Shell auf dem Companion öffnet.
* **Konfigurations-Dialog:**
  * Verbindungsart: **Ping** (nur IP/Hostname anpingen) oder **SSH** (Verbindung über gespeicherte SSH-Credentials + Host-Ping)
  * Intervall-Slider: 1 s, 2 s, 3 s, 5 s, 10 s
  * Timeout-Slider: 3 s, 4 s, 6 s, 10 s, 15 s, 20 s, 30 s (stellt sicher, dass Timeout immer > Intervall ist)
  * Speichern, Zurücksetzen ("Clear") und Abbrechen

### 2. Shelf (Befehlsleiste)
* **Bis zu 12 Start-Buttons** für Missionsskripte, Server, Video-Pipelines, Logs oder System-Tools.
* Jeder Button führt den Befehl entweder **Lokal** auf diesem Computer oder remote via **SSH** aus.
* **Zwei Ausführungs-Modi:**
  * 💻 **Terminal (Standard):** Führt `cd -- <Ordner> && <Befehl>` in einer eigenen interaktiven PTY-Shell aus.
    * Zeigt einen pulsierenden grünen Dot (`●`), während das Programm läuft.
    * Pfeil (`>`): Öffnet das interaktive Terminal-Fenster zum Mitlesen und Eingeben.
    * **Stoppen:** Während das Programm läuft, verwandelt sich der Stift in einen roten Stop-Button (`■`), der `Ctrl-C` (`\x03`) sendet und die Session sauber beendet.
    * **Restart on Press (Optional):** Erneuter Klick auf einen bereits laufenden Button sendet automatisch `Ctrl-C`, wartet 1 Sekunde und startet den Befehl im selben Terminal neu.
  * ⚙️ **Background (Hintergrund):** Einmaliges Ausführen ohne Terminalfenster (lokal als Hintergrund-Prozess, über SSH via `nohup`). Fehler oder Ausgaben werden in einem ausklappbaren Vorschaufenster angezeigt.
* **Fehler-Indikator:** Schlägt ein Start fehl, erscheint ein Warn-Dreieck mit Tooltip, der den genauen Fehlergrund nennt.

### 3. Editor View
* Live-Befehlsvorschau (Command Preview): Zeigt exakt, was ausgeführt wird (z.B. `cd ~/mission && ./start.sh &` oder `ssh corvus@192.168.2.10 'cd /opt/flight && python main.py'`).
* **Segmented Control [Local | SSH]** für die Zielauswahl.
* **SSH-Verwaltung:** Auswahl gespeicherter Verbindungen oder "New connection…" mit Feldern für Name, Host, Port (22), Benutzer, Passwort und Private-Key-Datei.
* Schalter für "Run in a terminal" und "Restart on press".
* Speichern, Löschen (bei bestehenden Buttons) und Abbrechen.

### 4. Interaktives Terminal-Fenster
* Vollständige Tab-Unterstützung für alle aktiven lokalen und SSH-Sessions.
* **Echte ANSI-Farbunterstützung** (Rot, Grün, Gelb, Blau, Bold, etc.).
* Interaktive Eingabezeile mit "Send", Schnell-Button für "Ctrl+C", "Clear" und "Disconnect".
* Echte PTY-Unterstützung auf macOS und Linux (`pty.openpty`), native Windows-Shell-Unterstützung.

### 5. Persistenz
* Alle Einstellungen (Buttons, Begleitcomputer, SSH-Verbindungen) werden sauber und atomar in `~/.cmdly/config.json` gespeichert.

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
.venv/bin/python3 -m unittest discover tests
```

---

## 📁 Projektstruktur

```
Cmdly/
├── app/
│   ├── config.py              # Konfigurationsmanager (~/.cmdly/config.json)
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
│       ├── icons.py           # Vektor-SVG-Icons (CPU, Server, Play, Stop, etc.)
│       ├── styles.py          # Dunkles Theme & CSS-Variablen
│       ├── widgets/
│       │   ├── companion_bar.py    # Der Companion-Status-Strip
│       │   ├── segmented_control.py# [Local | SSH] Segmented Control
│       │   ├── toggle_switch.py    # Moderner Toggle-Schalter
│       │   ├── shelf_row.py        # Einzelne Button-Zeile
│       │   └── terminal_widget.py  # ANSI-Terminal-Widget
│       ├── dialogs/
│       │   ├── companion_dialog.py # Dialog für Begleitcomputer
│       │   └── terminal_window.py  # Tabbed Terminalfenster
│       ├── views/
│       │   ├── shelf_view.py       # Shelf-Ansicht
│       │   └── editor_view.py      # Button-Editor
│       └── main_window.py          # Hauptfenster
├── tests/
│   ├── test_cmdly.py          # Unit-Tests für Modelle & Konfiguration
│   └── test_ui_and_sessions.py# Integrationstests für UI & PTY-Sessions
├── requirements.txt           # PySide6 & Paramiko
├── run.py                     # Startskript
├── run.sh                     # Ausführbares Shell-Startskript
└── README.md
```
