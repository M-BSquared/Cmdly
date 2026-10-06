#!/usr/bin/env python3
"""Make the README's pictures: ``docs/images/*.png``.

Cmdly is started for real (its backend on a free port, its page in a
QtWebEngine view) on a made-up setup in a temporary ``CMDLY_HOME``, so the
pictures never show anyone's own buttons, hosts or prompt. Each window is
rendered on its own and laid onto a generated wallpaper, the way macOS shows
it: the frosted glass is the wallpaper behind the window, blurred, under the
page; rounded corners, the traffic lights and a soft shadow are drawn here.

Nothing is taken from the screen, so the pictures are the same on every run
and on every machine that can run Cmdly.

    .venv/bin/python tools/readme_shots.py            # every picture
    .venv/bin/python tools/readme_shots.py hero       # only some of them

Pictures: hero, themes, editor, settings, and social (the 1280 x 640
social preview, uploaded by hand under the repository's Settings > General).
"""
from __future__ import annotations

import base64
import json
import os
import socket
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "images"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Rendered at twice the size, as on a Retina screen.
SCALE = 2
MAIN_SIZE = (440, 640)
TERM_SIZE = (720, 430)
WINDOW_RADIUS = 14

# Who the pictures are about: a drone's ground station and its companion.
DEMO_CONFIG = {
    "buttons": [
        {"id": "b_bridge", "label": "Autopilot bridge", "target": "ssh", "connection": "jetson",
         "directory": "~/ros2_ws", "command": "ros2 launch mavros apm.launch", "mode": "terminal",
         "restart": True},
        {"id": "b_camera", "label": "Camera stream", "target": "ssh", "connection": "jetson",
         "directory": "~", "command": "./stream.sh --port 5600", "mode": "background"},
        {"id": "b_planner", "label": "Mission planner", "target": "local", "directory": "~/ops",
         "command": "./mission-planner --vehicle 1", "mode": "terminal"},
        {"id": "b_logs", "label": "Sync flight logs", "target": "local", "directory": "~/ops",
         "command": "rsync -av jetson:~/logs/ ./logs/", "mode": "background"},
        {"id": "b_info", "label": "System info", "target": "local", "directory": "~",
         "command": "uname -a && uptime", "mode": "terminal"},
    ],
    "companions": [
        {"id": "c_jetson", "name": "jetson", "host": "127.0.0.1", "type": "ssh", "connection": "jetson",
         "interval_s": 1, "timeout_s": 3},
        {"id": "c_router", "name": "Field router", "host": "localhost", "type": "ping",
         "interval_s": 1, "timeout_s": 3},
    ],
    "active_companion": "c_jetson",
    "connections": [
        {"name": "jetson", "host": "127.0.0.1", "port": 22, "username": "pilot", "password": "demo"},
    ],
    "ui": {"theme": "blue", "vibrancy": True, "frosted_terminals": True},
    "window": {"width": MAIN_SIZE[0], "height": MAIN_SIZE[1]},
    "updates": {"check": False, "skipped": ""},
}

# What the terminal in the pictures shows: a mission planner starting up.
PLANNER = r"""#!/bin/sh
g='\033[32m'; c='\033[36m'; y='\033[33m'; d='\033[2m'; b='\033[1m'; r='\033[0m'
printf "${b}Mission planner${r} ${d}v2.4.1${r}\n\n"
sleep 0.05
printf "${d}[09:41:02]${r} ${c}link${r}    connecting to udp://127.0.0.1:14550\n"
printf "${d}[09:41:02]${r} ${g}link${r}    heartbeat from vehicle 1 ${d}(ArduCopter 4.5.7)${r}\n"
printf "${d}[09:41:03]${r} ${c}params${r}  1 284 / 1 284 loaded\n"
printf "${d}[09:41:03]${r} ${c}gps${r}     3D fix, 17 satellites, hdop 0.6\n"
printf "${d}[09:41:04]${r} ${y}battery${r} 16.4 V, 98 %%\n"
printf "${d}[09:41:04]${r} ${c}mission${r} survey_north.plan, 42 waypoints, 3.8 km\n"
printf "${d}[09:41:05]${r} ${g}ready${r}   pre-arm checks passed\n\n"
printf "${g}>${r} waiting for operator ${d}(arm, upload, start)${r}\n"
"""

PROMPT = "pilot@ground ~/ops $ "


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class DevTools:
    """Just enough of the Chrome DevTools protocol to take a page's picture.

    QtWebEngine serves it on ``QTWEBENGINE_REMOTE_DEBUGGING``. Chromium draws
    the picture itself, at the scale asked for, whatever screen (if any) the
    view is on.
    """

    def __init__(self, port: int) -> None:
        self.port = port

    def targets(self) -> list[dict]:
        from urllib.request import urlopen
        with urlopen(f"http://127.0.0.1:{self.port}/json", timeout=5) as r:
            return json.loads(r.read())

    def call_all(self, ws_url: str, calls: list[tuple[str, dict]]) -> list[dict]:
        """Send each (method, params) in turn on one connection; their results."""
        import struct
        from urllib.parse import urlsplit

        parts = urlsplit(ws_url)
        sock = socket.create_connection((parts.hostname, parts.port), timeout=30)
        key = base64.b64encode(os.urandom(16)).decode()
        sock.sendall((f"GET {parts.path} HTTP/1.1\r\nHost: {parts.hostname}:{parts.port}\r\n"
                      f"Upgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
                      "Sec-WebSocket-Version: 13\r\n\r\n").encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            buf += sock.recv(4096)
        buf = buf.split(b"\r\n\r\n", 1)[1]

        def read_exact(n: int) -> bytes:
            nonlocal buf
            while len(buf) < n:
                chunk = sock.recv(1 << 20)
                if not chunk:
                    raise OSError("DevTools closed the connection")
                buf += chunk
            out, buf = buf[:n], buf[n:]
            return out

        def read_message() -> str:
            parts_: list[bytes] = []
            while True:
                b0, b1 = read_exact(2)
                n = b1 & 0x7F
                if n == 126:
                    n = struct.unpack("!H", read_exact(2))[0]
                elif n == 127:
                    n = struct.unpack("!Q", read_exact(8))[0]
                parts_.append(read_exact(n))
                if b0 & 0x80:
                    return b"".join(parts_).decode()

        def send(text: str) -> None:
            data = text.encode()
            mask = os.urandom(4)
            n = len(data)
            head = struct.pack("!BB", 0x81, 0x80 | n) if n < 126 else (
                struct.pack("!BBH", 0x81, 0x80 | 126, n) if n < 1 << 16 else struct.pack("!BBQ", 0x81, 0x80 | 127, n))
            sock.sendall(head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

        results = []
        for i, (method, params) in enumerate(calls, 1):
            send(json.dumps({"id": i, "method": method, "params": params}))
            while True:
                msg = json.loads(read_message())
                if msg.get("id") == i:
                    if "error" in msg:
                        raise RuntimeError(f"{method}: {msg['error']}")
                    results.append(msg.get("result", {}))
                    break
        sock.close()
        return results


def prepare_home() -> Path:
    """A ``CMDLY_HOME`` with the demo setup, and the planner script beside it."""
    home = Path(tempfile.mkdtemp(prefix="cmdly-shots-"))
    (home / "config.json").write_text(json.dumps(DEMO_CONFIG))
    ops = home / "ops"
    ops.mkdir()
    script = ops / "mission-planner"
    script.write_text(PLANNER)
    script.chmod(0o755)
    return home


def main(argv: list[str]) -> int:
    wanted = set(argv[1:]) or {"hero", "themes", "editor", "settings", "social"}
    home = prepare_home()
    os.environ["CMDLY_HOME"] = str(home)
    # A plain shell, so the terminal shows the demo prompt and not the
    # prompt (and whatever else) of the shell this is run from.
    os.environ["SHELL"] = "/bin/sh"
    os.environ["ENV"] = ""
    devtools = DevTools(free_port())
    os.environ["QTWEBENGINE_REMOTE_DEBUGGING"] = str(devtools.port)

    from PySide6.QtCore import QEventLoop, QPointF, QRectF, QSize, Qt, QTimer, QUrl
    from PySide6.QtGui import (
        QBrush, QColor, QGuiApplication, QImage, QLinearGradient, QPainter, QPainterPath, QRadialGradient,
    )
    from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWidgets import QApplication

    from cmdly.config import Config
    from cmdly.server import create_server, serve_in_thread

    QGuiApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv[:1])  # noqa: F841 - must live as long as the views
    config = Config()
    server = create_server(free_port(), config)
    serve_in_thread(server)
    base = f"http://localhost:{server.port}"
    profile = QWebEngineProfile()  # off the record: nothing is kept

    def wait(ms: int) -> None:
        loop = QEventLoop()
        QTimer.singleShot(ms, loop.quit)
        loop.exec()

    # ---- pictures, painted ------------------------------------------------------

    def wallpaper(w: int, h: int) -> QImage:
        """A dark, colourful backdrop, as a desktop picture would be."""
        img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        ground = QLinearGradient(0, 0, w, h)
        ground.setColorAt(0, QColor("#0B1430"))
        ground.setColorAt(1, QColor("#120A26"))
        p.fillRect(img.rect(), ground)
        for cx, cy, r, color in ((0.18, 0.25, 0.55, "#2F6BFF"), (0.85, 0.15, 0.45, "#B04BFF"),
                                 (0.70, 0.90, 0.60, "#00B3A4"), (0.10, 0.95, 0.40, "#FF7A45"),
                                 (0.50, 0.50, 0.35, "#3B9EFF")):
            g = QRadialGradient(QPointF(cx * w, cy * h), r * max(w, h))
            col = QColor(color)
            col.setAlphaF(0.75)
            g.setColorAt(0, col)
            col.setAlphaF(0.0)
            g.setColorAt(1, col)
            p.fillRect(img.rect(), QBrush(g))
        p.end()
        return img

    def blurred(img: QImage, factor: int = 24) -> QImage:
        """A heavy blur: down, and back up, twice."""
        out = img
        for _ in range(2):
            small = out.scaled(max(1, out.width() // factor), max(1, out.height() // factor),
                               Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
            out = small.scaled(img.width(), img.height(), Qt.AspectRatioMode.IgnoreAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
        return out

    def data_url(img: QImage) -> str:
        from PySide6.QtCore import QBuffer, QIODevice
        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        img.save(buf, "PNG")
        return "data:image/png;base64," + base64.b64encode(bytes(buf.data())).decode()

    def shadow(p: QPainter, rect: QRectF, radius: float) -> None:
        """A soft shadow under a window: rings of falling alpha."""
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        steps = 28 * SCALE
        for i in range(steps, 0, -1):
            alpha = 0.03 * (1 - i / steps)
            p.setBrush(QColor(0, 0, 0, int(255 * alpha)))
            grow = i * 1.0
            r = rect.adjusted(-grow, -grow + 10 * SCALE, grow, grow + 10 * SCALE)
            p.drawRoundedRect(r, radius + grow, radius + grow)
        p.restore()

    def place(p: QPainter, shot: QImage, x: float, y: float, lights: bool) -> None:
        """A window at (x, y) in canvas pixels: shadow, the shot, rim, traffic lights."""
        rect = QRectF(x, y, shot.width(), shot.height())
        radius = WINDOW_RADIUS * SCALE
        shadow(p, rect, radius)
        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        p.save()
        p.setClipPath(path)
        p.drawImage(QPointF(x, y), shot)
        p.restore()
        p.setPen(QColor(255, 255, 255, 40))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)
        if lights:
            p.setPen(QColor(0, 0, 0, 40))
            for i, color in enumerate(("#FF5F57", "#FEBC2E", "#28C840")):
                p.setBrush(QColor(color))
                p.drawEllipse(QPointF(x + (20 + 20 * i) * SCALE, y + 17 * SCALE), 6 * SCALE, 6 * SCALE)

    # ---- pages, rendered --------------------------------------------------------------

    views: list = []

    def render(path: str, size: tuple[int, int], behind: QImage, setup_js: str = "",
               settle_ms: int = 1800, classes: str = "") -> QImage:
        """Cmdly's page *path* at *size*, frosted over *behind* (canvas pixels)."""
        view = QWebEngineView()
        views.append(view)
        page = QWebEnginePage(profile, view)
        view.setPage(page)
        view.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        view.resize(QSize(*size))
        view.show()
        loop = QEventLoop()
        page.loadFinished.connect(lambda _ok: loop.quit())
        tag = f"shot={len(views)}"
        url = base + path + ("&" if "?" in path else "?") + tag
        page.setUrl(QUrl(url))
        loop.exec()
        # The page as the desktop app shows it on macOS, with the blurred
        # desktop as its ground instead of the window system's blur.
        crop = data_url(blurred(behind).scaled(size[0], size[1], Qt.AspectRatioMode.IgnoreAspectRatio,
                                               Qt.TransformationMode.SmoothTransformation))
        js = f"""
          (function () {{
            const root = document.documentElement;
            root.classList.add({", ".join(json.dumps(c) for c in classes.split())});
            if (!document.getElementById("shot-ground")) {{
              const style = document.createElement("style");
              style.id = "shot-ground";
              style.textContent = 'html {{ background: url({crop}) 0 0 / 100% 100% no-repeat !important; }}';
              document.head.appendChild(style);
            }}
            if (!window.shotSetUp) {{
              window.shotSetUp = true;
              {setup_js}
            }}
          }})();
        """
        page.runJavaScript(js)
        wait(settle_ms)
        page.runJavaScript(js)   # the classes again, should the page have redrawn its root
        wait(300)
        img = capture(url, size)
        view.hide()
        return img

    def capture(url: str, size: tuple[int, int]) -> QImage:
        """The page at *url*, drawn by Chromium at SCALE times its CSS size."""
        result: dict = {}

        # Off this thread: DevTools answers through Qt's event loop.
        def work() -> None:
            try:
                target = next(t for t in devtools.targets() if t.get("url") == url)
                result["shot"] = devtools.call_all(target["webSocketDebuggerUrl"], [
                    ("Emulation.setDeviceMetricsOverride",
                     {"width": size[0], "height": size[1], "deviceScaleFactor": SCALE, "mobile": False}),
                    ("Page.captureScreenshot", {"format": "png"}),
                ])[1]["data"]
            except Exception as exc:  # noqa: BLE001 - reported below
                result["error"] = exc

        import threading
        worker = threading.Thread(target=work, daemon=True)
        worker.start()
        while worker.is_alive():   # Chromium draws on this (Qt's) thread
            wait(50)
        if "error" in result:
            raise result["error"]
        return QImage.fromData(base64.b64decode(result["shot"]), "PNG")

    def render_main(behind: QImage, theme: str = "blue", setup_js: str = "", settle_ms: int = 4000) -> QImage:
        config.update({"ui": dict(config.snapshot()["ui"], theme=theme)})
        # In a light theme macOS lays its light material and Cmdly's veil
        # (cmdly/app.py, MAIN_LIGHT_VEIL) over the blur: about this much white.
        if theme.startswith("light"):
            setup_js += """
              const veil = document.createElement("style");
              veil.textContent = "body { background: rgb(240 241 245 / 0.72) !important; }";
              document.head.appendChild(veil);
            """
        js = f"""
          Cmdly.native.setVibrancy = function () {{}};
          document.documentElement.classList.add("vibrant");
          {setup_js}
        """
        return render("/", MAIN_SIZE, behind, js, settle_ms,
                      "vibrant unified-titlebar platform-mac desktop-app")

    def render_terminal(behind: QImage) -> QImage:
        query = ("kind=terminal&name=cmdly%2Fb_planner&title=Mission+planner&host=this+computer"
                 "&key=term%3Acmdly%2Fb_planner")
        # The bar's window buttons come from the desktop app's bridge, which a
        # page rendered here has not: the same buttons, in the same order.
        tools = """
          const tools = document.querySelector('.term-win-tools');
          const power = tools && tools.firstChild;
          if (tools) {
            ['pin', 'maximize-2'].forEach((n) => tools.insertBefore(Cmdly.ui.iconButton(n, { size: 13 }), power));
            tools.appendChild(Cmdly.ui.iconButton('x', { size: 13 }));
            Cmdly.ui.refreshIcons();
          }
        """
        return render("/popout.html?" + query, TERM_SIZE, behind, tools, 2500,
                      "native-window frosted-terminals platform-mac")

    def start_planner() -> None:
        """The planner's terminal, running, for the main window's row and the terminal picture."""
        name = "cmdly/b_planner"
        server.ssh.connect_local(name, str(home / "ops"))
        time.sleep(0.8)
        server.ssh.send(name, f"PS1='{PROMPT}'; clear\n")
        time.sleep(0.4)
        server.ssh.send(name, "./mission-planner --vehicle 1\n")
        time.sleep(0.8)

    def canvas(w: int, h: int) -> QImage:
        return wallpaper(w * SCALE, h * SCALE)

    def crop_of(bg: QImage, x: int, y: int, size: tuple[int, int]) -> QImage:
        return bg.copy(x * SCALE, y * SCALE, size[0] * SCALE, size[1] * SCALE)

    def save(img: QImage, name: str) -> None:
        OUT.mkdir(parents=True, exist_ok=True)
        path = OUT / f"{name}.png"
        img.save(str(path), "PNG")
        print(f"  {path.relative_to(ROOT)}  {img.width()}x{img.height()}")

    # ---- the pictures ----------------------------------------------------------------

    start_planner()
    print("Pictures:")

    if "hero" in wanted:
        w, h = 1320, 800
        bg = canvas(w, h)
        mx, my = 110, 70
        tx, ty = 510, 300
        main_shot = render_main(crop_of(bg, mx, my, MAIN_SIZE))
        term_shot = render_terminal(crop_of(bg, tx, ty, TERM_SIZE))
        out = QImage(bg)
        p = QPainter(out)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        place(p, main_shot, mx * SCALE, my * SCALE, lights=True)
        place(p, term_shot, tx * SCALE, ty * SCALE, lights=False)
        p.end()
        save(out, "hero")

    if "themes" in wanted:
        gap, pad = 40, 50
        w = pad * 2 + MAIN_SIZE[0] * 3 + gap * 2
        h = pad * 2 + MAIN_SIZE[1]
        bg = canvas(w, h)
        out = QImage(bg)
        p = QPainter(out)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        for i, theme in enumerate(("blue", "green", "light-orange")):
            x = pad + i * (MAIN_SIZE[0] + gap)
            shot = render_main(crop_of(bg, x, pad, MAIN_SIZE), theme)
            place(p, shot, x * SCALE, pad * SCALE, lights=True)
        p.end()
        save(out, "themes")

    if "editor" in wanted:
        w, h = MAIN_SIZE[0] + 100, MAIN_SIZE[1] + 100
        bg = canvas(w, h)
        click_edit = """
          setTimeout(() => {
            const row = [...document.querySelectorAll('.shelf-row')]
              .find((r) => r.textContent.includes('Autopilot bridge'));
            const btn = row && row.querySelector('.row-tools button[title="Edit"]');
            if (btn) btn.click();
          }, 1500);
        """
        shot = render_main(crop_of(bg, 50, 50, MAIN_SIZE), "blue", click_edit)
        out = QImage(bg)
        p = QPainter(out)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        place(p, shot, 50 * SCALE, 50 * SCALE, lights=True)
        p.end()
        save(out, "editor")

    if "settings" in wanted:
        w, h = MAIN_SIZE[0] + 100, MAIN_SIZE[1] + 100
        bg = canvas(w, h)
        shot = render_main(crop_of(bg, 50, 50, MAIN_SIZE), "blue",
                           "setTimeout(() => Cmdly.settings.open(), 1500);")
        out = QImage(bg)
        p = QPainter(out)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        place(p, shot, 50 * SCALE, 50 * SCALE, lights=True)
        p.end()
        save(out, "settings")

    if "social" in wanted:
        # GitHub's social preview: 1280 x 640, the name and what it does on
        # the left, the window on the right, cut off by the bottom edge.
        from PySide6.QtGui import QFont
        w, h = 1280, 640
        bg = canvas(w, h)
        mx, my = 760, 70
        shot = render_main(crop_of(bg, mx, my, MAIN_SIZE))
        out = QImage(bg)
        p = QPainter(out)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        place(p, shot, mx * SCALE, my * SCALE, lights=True)
        icon = QImage(str(ROOT / "assets" / "icon.png"))
        p.drawImage(QRectF(80 * SCALE, 150 * SCALE, 128 * SCALE, 128 * SCALE), icon)
        p.setPen(QColor("#FFFFFF"))
        title = QFont("SF Pro Display")
        title.setPixelSize(96 * SCALE)
        title.setWeight(QFont.Weight.Bold)
        p.setFont(title)
        p.drawText(QRectF(96 * SCALE, 290 * SCALE, 640 * SCALE, 120 * SCALE),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "Cmdly")
        body = QFont("SF Pro Text")
        body.setPixelSize(30 * SCALE)
        p.setFont(body)
        p.setPen(QColor(255, 255, 255, 220))
        p.drawText(QRectF(100 * SCALE, 410 * SCALE, 620 * SCALE, 120 * SCALE),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
                   "One-press buttons for the programs you start again and again, here or over SSH.")
        p.end()
        save(out.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation),
             "social-preview")

    server.stop()
    # Pages before their profile, or QtWebEngine complains on the way out.
    from PySide6.QtCore import QCoreApplication, QEvent
    for v in views:
        v.page().deleteLater()
        v.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    del views[:]
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
