#!/usr/bin/env python3
"""Cmdly, the desktop app.

Starts the backend (:mod:`cmdly.server`) on a thread of its own and shows its
page in a PySide6 QtWebEngine window: no browser, one process, one clean
shutdown that closes every terminal session and ends every program Cmdly
started on this computer.

On macOS the title bar is folded into the page (the page's header sits
under the traffic lights) and the desktop shows through the frosted window,
blurred behind by the system (:class:`cmdly.native_window.MacBlur`). On Linux
the same frost is a window Qt paints translucent itself (the page's own
tint, src/css/themes.css), with KWin's blur behind it where the window
manager honours the hint (:class:`cmdly.native_window.X11Effects`).
A terminal
opens in a window of its own by default, frameless and drawn by its page, the
same frame as in Corvus GCS, which can go anywhere and be pinned above Cmdly.

Usage:
    python3 cmdly/app.py [PORT]
"""
from __future__ import annotations

import atexit
import json
import logging
import os
import re
import signal
import sys
import threading
import time
from urllib.parse import parse_qs, urlsplit

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

APP_NAME = "Cmdly"


def chromium_flags(platform: str = sys.platform) -> list[str]:
    """QtWebEngine's Chromium switches for this platform.

    ``--ignore-gpu-blocklist`` keeps the GPU on blocklisted but working
    drivers (a lot of VMs and older laptops); SwiftShader is the software
    fallback when there is no usable GPU at all. On Linux the GPU sandbox is
    what keeps the GPU process from coming up in containers and on odd
    drivers. An operator's own ``QTWEBENGINE_CHROMIUM_FLAGS`` wins outright.
    """
    flags = ["--ignore-gpu-blocklist", "--enable-unsafe-swiftshader"]
    if platform.startswith("linux"):
        flags += ["--disable-gpu-sandbox"]
    return flags


os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", " ".join(chromium_flags()))


def qpa_platform(env, platform: str = sys.platform) -> str:
    """The Qt platform to ask for, or ``""`` to leave Qt its own choice.

    On a Wayland desktop with XWayland beside it, X11 first: a Wayland
    client may not place its own windows or keep one above others, which the
    terminal windows need. Wayland stays the fallback in the same value.
    """
    if not platform.startswith("linux") or env.get("QT_QPA_PLATFORM"):
        return ""
    wayland = bool(env.get("WAYLAND_DISPLAY")) or env.get("XDG_SESSION_TYPE", "").lower() == "wayland"
    return "xcb;wayland" if wayland and env.get("DISPLAY") else ""


_QPA = qpa_platform(os.environ)
if _QPA:
    from cmdly.child_env import QPA_DEFAULT_ENV

    os.environ["QT_QPA_PLATFORM"] = _QPA
    os.environ[QPA_DEFAULT_ENV] = _QPA

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
                    datefmt="%H:%M:%S")
logger = logging.getLogger("cmdly.app")

from cmdly.config import Config  # noqa: E402
from cmdly.instance_lock import ALLOW_MULTI_ENV, InstanceLock, allow_multi, describe_peer  # noqa: E402
from cmdly.native_window import MacBlur, mac_blur, win32_windows, x11_effects  # noqa: E402
from cmdly.paths import cmdly_path  # noqa: E402
from cmdly.qt_plugins import visible_plugin_dir  # noqa: E402
from cmdly.server import DEFAULT_PORT, create_server, serve_in_thread  # noqa: E402
from cmdly.version import get_version  # noqa: E402

ICON_PATH = os.path.join(REPO_ROOT, "assets", "icon.png")

# ---------------------------------------------------------------------------
# Rules, pure so they are tested without Qt
# ---------------------------------------------------------------------------

POPOUT_MIN_W = 360
POPOUT_MIN_H = 220
#: A new terminal window: landscape, whatever shape the frame it replaces had.
POPOUT_DEFAULT = (780, 500)
MAIN_MIN_W = 300
MAIN_MIN_H = 520
MAIN_DEFAULT = (560, 760)
#: What the blur behind the main window is tinted with in a light theme
#: (RGBA, 0-1): the frosted look, with the desktop showing through faintly.
MAIN_LIGHT_TINT = (0.90, 0.90, 0.92, 0.35)

_POPOUT_KEY_RE = re.compile(r"^term:[A-Za-z0-9_./@:-]{1,96}$")


def parse_port_arg(argv: list[str], default: int) -> tuple[int, str]:
    """The optional PORT argument: ``(port, error)``."""
    if len(argv) <= 1:
        return default, ""
    raw = argv[1]
    try:
        port = int(raw)
    except (TypeError, ValueError):
        return default, f"invalid port {raw!r}"
    if not 1 <= port <= 65535:
        return default, f"port {port} is out of range (1-65535)"
    return port, ""


def popout_url_allowed(url: str, port: int) -> bool:
    """A window the page opened may show this backend's pages, nothing else."""
    if url in ("", "about:blank"):
        return True
    try:
        parts = urlsplit(url)
        url_port = parts.port
    except ValueError:
        return False
    return (parts.scheme == "http" and (parts.hostname or "") in ("localhost", "127.0.0.1")
            and url_port == port)


def popout_key_valid(key: str) -> bool:
    return isinstance(key, str) and bool(_POPOUT_KEY_RE.match(key))


def popout_key(url: str) -> str:
    """The key a popout.html address names, or ``""``."""
    try:
        values = parse_qs(urlsplit(url).query).get("key") or [""]
    except ValueError:
        return ""
    return values[0] if popout_key_valid(values[0]) else ""


def external_url(url: str) -> bool:
    try:
        return urlsplit(url).scheme in ("http", "https")
    except ValueError:
        return False


def stays_on_top(pinned: bool, app_active: bool) -> bool:
    """A pinned terminal is above Cmdly's windows, not above other programs'."""
    return bool(pinned) and bool(app_active)


def window_support(platform_name: str, os_platform: str = sys.platform,
                   composited: bool = False) -> dict:
    """What the windows can do on this Qt platform (the page reads it first).

    ``place``/``pin``: not on Wayland, where the compositor places windows.
    ``frost``: the desktop can show through a window, tinted by the page —
    the main window's frost (src/css/themes.css) and a terminal window's
    frosted glass alike. On macOS the system blurs the desktop behind the
    window (NSVisualEffectView); on Linux the page's own tint is the frost,
    with KWin's blur behind it where the window manager honours the hint.
    ``unified``: macOS, which can fold the title bar into the content.

    On Linux, *composited* says a compositor runs (a see-through window is
    black without one); macOS needs neither asked.
    """
    name = str(platform_name or "").lower()
    wayland = name.startswith("wayland")
    cocoa = name == "cocoa"
    linux = os_platform.startswith("linux")
    plat = "mac" if os_platform == "darwin" else ("windows" if os_platform == "win32" else "linux")
    return {"place": not wayland, "pin": not wayland,
            "frost": cocoa or (linux and composited),
            "unified": cocoa, "platform": plat}


def popout_geometry(rect: tuple[int, int, int, int],
                    available: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """A window's rect, kept on the screen it is on and no larger than it."""
    x, y, w, h = rect
    ax, ay, aw, ah = available
    w = max(min(w, aw), min(POPOUT_MIN_W, aw))
    h = max(min(h, ah), min(POPOUT_MIN_H, ah))
    x = min(max(x, ax), ax + aw - w)
    y = min(max(y, ay), ay + ah - h)
    return x, y, w, h


def native_support_js(support: dict) -> str:
    return "\n;window.cmdlyNativeSupport = Object.freeze(" + json.dumps(support) + ");\n"


# Runs in every page before its own scripts: connects it to the Qt object it
# may ask things of. A plain browser has no `qt` and nothing happens.
NATIVE_BOOTSTRAP_JS = """
;(function () {
  if (typeof qt === "undefined" || !qt.webChannelTransport || typeof QWebChannel !== "function") return;
  new QWebChannel(qt.webChannelTransport, function (channel) {
    window.cmdlyNative = channel.objects.cmdlyNative || null;
    window.dispatchEvent(new CustomEvent("cmdly:native-ready"));
  });
})();
"""


def webengine_profile_dir(multi: bool) -> str:
    """QtWebEngine's cache and storage; one per instance, as Chromium locks it."""
    return cmdly_path("webengine", f"instance-{os.getpid()}" if multi else "default")


def set_windows_app_id(app_id: str) -> bool:
    """Windows: group the window under Cmdly's own taskbar icon, not Python's."""
    if os.name != "nt":
        return False
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:  # noqa: BLE001 - a taskbar icon is never worth a failed launch
        return False
    return True


def desktop_id(env=None) -> str:
    """The name a Linux desktop matches the window to its launcher entry by."""
    env = os.environ if env is None else env
    return "cmdly" if env.get("APPIMAGE") else "cmdly-dev"


def qt_argv(argv: list[str], app_id: str, platform: str = sys.platform) -> list[str]:
    """On Linux ``-name`` sets the X11 WM_CLASS, which Qt otherwise takes from argv[0]."""
    if not platform.startswith("linux"):
        return list(argv)
    return [*argv, "-name", app_id]


def use_visible_qt_plugins() -> None:
    """Load Qt's plugins through links when macOS has flagged them hidden."""
    from PySide6.QtCore import QCoreApplication, QLibraryInfo

    try:
        links = visible_plugin_dir(QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath))
    except OSError:
        logger.warning("Qt's plugins are flagged hidden and could not be linked", exc_info=True)
        return
    if links:
        QCoreApplication.addLibraryPath(links)


def report_startup_failure(text: str, detail: str) -> None:
    """Why this launch stopped, in a window: a packaged app has no console."""
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox

        use_visible_qt_plugins()
        app = QApplication.instance() or QApplication(sys.argv)
        app.setApplicationName(APP_NAME)
        box = QMessageBox()
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle(APP_NAME)
        box.setText(text)
        box.setInformativeText(detail)
        box.exec()
    except Exception:  # noqa: BLE001 - the log line is the fallback
        logger.debug("could not show the startup dialog", exc_info=True)


# ---------------------------------------------------------------------------
# The app
# ---------------------------------------------------------------------------


def main() -> int:  # noqa: C901 - one function owns the Qt objects and their lifetimes
    from PySide6.QtCore import QFile, QIODevice, QObject, QPoint, QRect, QSize, Qt, QTimer, QUrl, Slot
    from PySide6.QtGui import QGuiApplication, QIcon
    from PySide6.QtWebChannel import QWebChannel
    from PySide6.QtWebEngineCore import (
        QWebEngineDownloadRequest, QWebEnginePage, QWebEngineProfile, QWebEngineScript, QWebEngineSettings,
    )
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow

    port, port_error = parse_port_arg(sys.argv, DEFAULT_PORT)
    if port_error:
        logger.error("%s\nusage: cmdly [PORT]", port_error)
        report_startup_failure("Cmdly could not start.", f"{port_error}\n\nusage: cmdly [PORT]")
        return 2

    lock = InstanceLock()
    first = lock.acquire(port=None)
    if not first and not allow_multi():
        peer = describe_peer(lock.peer())
        logger.error("Cmdly is %s.", peer)
        report_startup_failure("Cmdly is already running.",
                               f"{peer}\n\nBring its window forward, or set {ALLOW_MULTI_ENV}=1 to run a second one.")
        return 1
    atexit.register(lock.release)

    config = Config()
    try:
        server = create_server(port, config)
    except OSError as exc:
        logger.error("could not start the backend: %s", exc)
        report_startup_failure("Cmdly could not start.", f"No free local port: {exc}")
        lock.release()
        return 1
    serve_in_thread(server)
    port = server.port
    lock.write_port(port)
    logger.info("backend on http://localhost:%d/ (config %s)", port, config.path)

    set_windows_app_id(f"cmdly.app.{get_version()}")
    use_visible_qt_plugins()
    app_id = desktop_id()
    QGuiApplication.setDesktopFileName(app_id)
    app = QApplication(qt_argv(sys.argv, app_id))
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(get_version())
    if os.path.exists(ICON_PATH):
        app.setWindowIcon(QIcon(ICON_PATH))

    platform_name = QGuiApplication.platformName()
    x11 = x11_effects(platform_name)
    # On Linux a see-through window is only real where something composites:
    # always on Wayland, on X11 only with a manager running (X11Effects
    # asks). The desktop then shows through the page's own frost, and KWin
    # adds the blur behind it where it runs.
    support = window_support(platform_name,
                             composited=bool(x11 and x11.composited())
                             or platform_name.startswith("wayland"))
    win = win32_windows()
    mac: MacBlur | None = mac_blur() if support["frost"] else None
    if mac is None and support["unified"]:
        # macOS promised the frost and the unified title bar, and AppKit
        # would not load after all: a plain window there. Everywhere else
        # mac is None by design, and the support stands.
        support.update(frost=False, unified=False)

    # ---- the main window -------------------------------------------------------
    class MainWindow(QMainWindow):
        def closeEvent(self, event):  # noqa: N802 - Qt's name
            # A terminal window has no parent on macOS (see PopoutWindow), so
            # it does not go with this one by itself.
            for holder in list(popout_windows.values()):
                holder.close()
            super().closeEvent(event)

    window = MainWindow()
    window.setWindowTitle(APP_NAME)
    window.setMinimumSize(MAIN_MIN_W, MAIN_MIN_H)
    saved = config.window
    window.resize(*(saved["width"], saved["height"]) if saved else MAIN_DEFAULT)
    if support["frost"]:
        # See-through, so what is behind the window shows where the page is:
        # the system's blur on macOS, the page's own frost on Linux.
        window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    if support["unified"]:
        # The page runs up under the traffic lights and draws the title bar
        # itself. Qt 6.9 calls this ExpandedClientAreaHint; PySide still names
        # the bit by its older name, MaximizeUsingFullscreenGeometryHint.
        window.setWindowFlags(window.windowFlags()
                              | Qt.WindowType.MaximizeUsingFullscreenGeometryHint
                              | Qt.WindowType.NoTitleBarBackgroundHint)
        # Qt keeps a widget's contents out of that area by default (safe
        # area margins); the page wants it, and keeps clear of the traffic
        # lights itself.
        window.setAttribute(Qt.WidgetAttribute.WA_ContentsMarginsRespectsSafeArea, False)
    main_state = {"blur": 0, "unified": False}

    def configure_view(view) -> None:
        settings = view.settings()
        try:
            # Copying a terminal's selection: QtWebEngine refuses
            # navigator.clipboard.writeText without this. Writing only.
            settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanAccessClipboard, True)
            settings.setAttribute(QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled, True)
        except Exception:  # noqa: BLE001 - conveniences
            logger.debug("could not set a web setting", exc_info=True)

    # ---- terminal windows of their own --------------------------------------------
    popout_windows: dict = {}   # key -> window
    popout_last: dict = {}      # key -> where it was when closed, for this run
    popout_pinned: dict = {}    # key -> whether its pin was on, for this run

    def set_on_top(holder, on: bool) -> None:
        flags = holder.windowFlags()
        flags = flags | Qt.WindowType.WindowStaysOnTopHint if on else flags & ~Qt.WindowType.WindowStaysOnTopHint
        holder.overrideWindowFlags(flags)
        handle = holder.windowHandle()
        if handle is not None:
            handle.setFlags(flags)

    def app_active() -> bool:
        return QGuiApplication.applicationState() == Qt.ApplicationState.ApplicationActive

    def step_back(holder) -> None:
        if win is not None:
            try:
                win.step_back(int(holder.winId()))
            except Exception:  # noqa: BLE001 - the order is cosmetic
                logger.debug("could not step a window back", exc_info=True)
        elif QGuiApplication.platformName() == "xcb":
            holder.lower()

    def apply_pin(holder) -> None:
        if not support["pin"]:
            return
        active = app_active()
        want = stays_on_top(holder.pinned, active)
        if want != bool(holder.windowFlags() & Qt.WindowType.WindowStaysOnTopHint):
            set_on_top(holder, want)
            if not want and not active:
                step_back(holder)

    def pin(holder, on: bool) -> None:
        holder.pinned = bool(on) and support["pin"]
        if holder.key:
            popout_pinned[holder.key] = holder.pinned
        apply_pin(holder)

    def on_app_state(_state) -> None:
        for holder in list(popout_windows.values()):
            try:
                apply_pin(holder)
            except RuntimeError:
                pass

    app.applicationStateChanged.connect(on_app_state)

    from PySide6.QtWidgets import QVBoxLayout, QWidget

    class PopoutWindow(QWidget):
        """A terminal's own window: frameless, see-through, drawn by its page."""

        def __init__(self):
            # On macOS it is a window of its own, not a child of the main one:
            # a child with the blur of its own (MacBlur) turns the main
            # window's blur black for as long as it exists. What the parent
            # gave elsewhere (it closes with the main window, it stays
            # above it) is done by MainWindow.closeEvent and the pin.
            super().__init__(None if mac is not None else window,
                             Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
            self.key = ""
            self.normal = None
            self.pinned = False
            self.blur = 0

        def unfrost(self) -> None:
            if self.blur:
                try:
                    if mac is not None:
                        mac.clear(self.blur)
                    elif x11 is not None:
                        x11.set_blur(int(self.winId()), False)
                except Exception:  # noqa: BLE001 - the window goes either way
                    logger.debug("could not take a window's blur away", exc_info=True)
            self.blur = 0

        def closeEvent(self, event):  # noqa: N802 - Qt's name
            if self.key:
                popout_last[self.key] = QRect(self.normal or self.geometry())
            self.unfrost()
            super().closeEvent(event)

    def screen_area_at(point) -> tuple[int, int, int, int]:
        screen = QGuiApplication.screenAt(point) or window.screen() or QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        return area.x(), area.y(), area.width(), area.height()

    def settle(holder) -> None:
        g = holder.geometry()
        now = (g.x(), g.y(), g.width(), g.height())
        fitted = popout_geometry(now, screen_area_at(g.center()))
        if fitted != now:
            holder.setGeometry(*fitted)

    def over_app(point) -> bool:
        if not window.isVisible() or window.isMinimized():
            return False
        return QRect(web.mapToGlobal(QPoint(0, 0)), web.size()).contains(point)

    def place_popout(holder, rect) -> None:
        holder.setGeometry(*popout_geometry((rect.x(), rect.y(), rect.width(), rect.height()),
                                            screen_area_at(rect.center())))

    class PopoutBridge(QObject):
        """What a terminal's own window may ask of its window, and nothing else."""

        def __init__(self, holder):
            super().__init__(holder)
            self._holder = holder
            self._start = None
            self._grab = None

        @Slot()
        def dragStart(self) -> None:  # noqa: N802 - the page's name
            self._start = self._holder.geometry()
            self._grab = None
            if win is not None:
                try:
                    hwnd = int(self._holder.winId())
                    cx, cy = win.cursor()
                    ox, oy = win.origin(hwnd)
                    self._grab = (hwnd, cx - ox, cy - oy)
                except Exception:  # noqa: BLE001 - Qt's move is the fallback
                    logger.debug("native drag unavailable", exc_info=True)

        @Slot(int, int)
        def dragTo(self, dx: int, dy: int) -> None:  # noqa: N802
            if self._start is None or self._holder.normal is not None:
                return
            if self._grab is not None:
                hwnd, gx, gy = self._grab
                try:
                    cx, cy = win.cursor()
                    win.move(hwnd, cx - gx, cy - gy)
                    return
                except Exception:  # noqa: BLE001
                    self._grab = None
            self._holder.move(self._start.x() + dx, self._start.y() + dy)

        @Slot(result=bool)
        def systemMove(self) -> bool:  # noqa: N802
            handle = self._holder.windowHandle()
            return bool(handle is not None and self._holder.normal is None and handle.startSystemMove())

        @Slot(result=bool)
        def systemResize(self) -> bool:  # noqa: N802
            handle = self._holder.windowHandle()
            return bool(handle is not None and handle.startSystemResize(Qt.Edge.RightEdge | Qt.Edge.BottomEdge))

        @Slot(int, int)
        def resizeTo(self, dw: int, dh: int) -> None:  # noqa: N802
            if self._start is not None:
                self._holder.normal = None
                self._holder.resize(max(POPOUT_MIN_W, self._start.width() + dw),
                                    max(POPOUT_MIN_H, self._start.height() + dh))

        @Slot(int, int, result=str)
        def dragEnd(self, x: int, y: int) -> str:  # noqa: N802
            """End a gesture; say whether it was let go of over the app, and where."""
            self._start = None
            self._grab = None
            if self._holder.normal is not None or not support["place"]:
                return json.dumps({"inside": False})
            released = self._holder.mapToGlobal(QPoint(x, y))
            settle(self._holder)
            if not over_app(released):
                return json.dumps({"inside": False})
            origin = web.mapFromGlobal(self._holder.pos())
            return json.dumps({"inside": True, "left": origin.x(), "top": origin.y(),
                               "width": self._holder.width(), "height": self._holder.height()})

        @Slot(result=bool)
        def toggleMaximize(self) -> bool:  # noqa: N802
            holder = self._holder
            if not support["place"]:
                if holder.isMaximized():
                    holder.normal = None
                    holder.showNormal()
                    return False
                holder.normal = holder.geometry()
                holder.showMaximized()
                return True
            if holder.normal is not None:
                holder.setGeometry(holder.normal)
                holder.normal = None
                return False
            holder.normal = holder.geometry()
            holder.setGeometry(*screen_area_at(holder.geometry().center()))
            return True

        @Slot(bool, result=bool)
        def setPinned(self, on: bool) -> bool:  # noqa: N802
            pin(self._holder, bool(on))
            return self._holder.pinned

        @Slot(result=bool)
        def isPinned(self) -> bool:  # noqa: N802
            return self._holder.pinned

        @Slot(bool, bool, float, result=bool)
        def setFrosted(self, on: bool, dark: bool, radius: float) -> bool:  # noqa: N802
            holder = self._holder
            if not on or not support["frost"]:
                holder.unfrost()
                return False
            if mac is not None:
                try:
                    holder.blur = mac.frost(int(holder.winId()), holder.blur, bool(dark), float(radius),
                                            holder.width(), holder.height())
                except Exception:  # noqa: BLE001 - a solid terminal is the fallback
                    logger.debug("could not blur behind a window", exc_info=True)
                    return False
                return True
            # Linux: the window is translucent, so the frost is the page's own
            # tint (the frosted-terminals class); KWin, where it runs, adds
            # the blur behind it.
            if x11 is not None and x11.blur_supported():
                try:
                    x11.set_blur(int(holder.winId()), True)
                    holder.blur = 1
                except Exception:  # noqa: BLE001 - frosted without blur is fine
                    logger.debug("could not blur behind a window", exc_info=True)
            return True

        @Slot()
        def raiseWindow(self) -> None:  # noqa: N802
            self._holder.show()
            self._holder.raise_()
            self._holder.activateWindow()

        @Slot()
        def closeWindow(self) -> None:  # noqa: N802
            self._holder.close()

    class PopoutPage(QWebEnginePage):
        """A terminal window's page: Cmdly's own pages only, never the web."""

        def __init__(self, page_profile, parent, holder):
            super().__init__(page_profile, parent)
            self.holder = holder

        def acceptNavigationRequest(self, url, nav_type, is_main_frame):  # noqa: N802
            text = url.toString()
            if popout_url_allowed(text, port):
                key = popout_key(text) if is_main_frame else ""
                if key and key not in popout_windows:
                    popout_windows[key] = self.holder
                    self.holder.key = key
                    if popout_pinned.get(key):
                        pin(self.holder, True)
                    self.holder.destroyed.connect(lambda *_: popout_windows.pop(key, None))
                return True
            if is_main_frame:
                if external_url(text):
                    from PySide6.QtGui import QDesktopServices
                    QDesktopServices.openUrl(QUrl(text))
                QTimer.singleShot(0, self.holder.close)
            return False

        def createWindow(self, _type):  # noqa: N802
            return open_popout(self.profile())

    def show_popout(holder) -> None:
        if not holder.isVisible():
            holder.show()
            holder.raise_()

    def open_popout(page_profile):
        holder = PopoutWindow()
        holder.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        holder.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        holder.setWindowTitle(APP_NAME)
        holder.setMinimumSize(POPOUT_MIN_W, POPOUT_MIN_H)
        holder.resize(*POPOUT_DEFAULT)
        box = QVBoxLayout(holder)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(0)
        view = QWebEngineView(holder)
        page = PopoutPage(page_profile, view, holder)
        page.setBackgroundColor(Qt.GlobalColor.transparent)
        channel = QWebChannel(page)
        channel.registerObject("cmdlyNative", PopoutBridge(holder))
        page.setWebChannel(channel)
        view.setPage(page)
        configure_view(view)
        box.addWidget(view)
        page.titleChanged.connect(holder.setWindowTitle)
        page.windowCloseRequested.connect(holder.close)
        page.geometryChangeRequested.connect(lambda rect: place_popout(holder, rect))
        # Shown once its page has drawn, so it never flashes up empty.
        page.loadFinished.connect(lambda ok: show_popout(holder) if ok else holder.close())
        return page

    def window_for(key: str, query: str):
        holder = popout_windows.get(key)
        if holder is not None:
            return holder, False
        url = f"http://localhost:{port}/popout.html?{query}"
        if not popout_url_allowed(url, port) or popout_key(url) != key:
            return None, False
        page = open_popout(web.page().profile())
        holder = page.holder
        holder.key = key
        if popout_pinned.get(key):
            pin(holder, True)
        popout_windows[key] = holder
        holder.destroyed.connect(lambda *_: popout_windows.pop(key, None))
        page.setUrl(QUrl(url))
        return holder, True

    # ---- what the main page may ask ---------------------------------------------------
    class MainBridge(QObject):
        """Terminal windows for the page's frames, and its own window: move,
        zoom, the frosted window. Coordinates are the page's own CSS pixels."""

        def __init__(self, parent=None):
            super().__init__(parent)
            self._grabs: dict = {}

        def _rect(self, left: int, top: int, width: int, height: int):
            return QRect(web.mapToGlobal(QPoint(left, top)),
                         QSize(max(POPOUT_MIN_W, width), max(POPOUT_MIN_H, height)))

        @Slot(str, str, int, int, int, int)
        def openWindow(self, key, query, left, top, width, height) -> None:  # noqa: N802
            if not popout_key_valid(key) or len(query) > 4096:
                return
            holder, made = window_for(key, query)
            if holder is None:
                return
            if not made:
                if holder.isVisible():
                    holder.raise_()
                    holder.activateWindow()
                return
            rect = popout_last.get(key)
            if rect is None:
                rect = QRect(web.mapToGlobal(QPoint(left, top)), QSize(*POPOUT_DEFAULT))
            holder.setGeometry(*popout_geometry((rect.x(), rect.y(), rect.width(), rect.height()),
                                                screen_area_at(rect.center())))

        @Slot(str, str, int, int, int, int)
        def detachWindow(self, key, query, left, top, width, height) -> None:  # noqa: N802
            if not popout_key_valid(key) or len(query) > 4096:
                return
            holder, _ = window_for(key, query)
            if holder is None:
                return
            holder.setGeometry(self._rect(left, top, width, height))
            self._grabs.pop(key, None)
            if win is not None:
                try:
                    hwnd = int(holder.winId())
                    cx, cy = win.cursor()
                    ox, oy = win.origin(hwnd)
                    self._grabs[key] = (hwnd, cx - ox, cy - oy)
                except Exception:  # noqa: BLE001
                    logger.debug("native drag unavailable", exc_info=True)

        @Slot(str, int, int)
        def moveWindow(self, key, left, top) -> None:  # noqa: N802
            holder = popout_windows.get(key)
            if holder is None:
                return
            grab = self._grabs.get(key)
            if grab is not None:
                hwnd, gx, gy = grab
                try:
                    cx, cy = win.cursor()
                    win.move(hwnd, cx - gx, cy - gy)
                    return
                except Exception:  # noqa: BLE001
                    self._grabs.pop(key, None)
            holder.move(web.mapToGlobal(QPoint(left, top)))

        @Slot(str)
        def settleWindow(self, key) -> None:  # noqa: N802
            self._grabs.pop(key, None)
            holder = popout_windows.get(key)
            if holder is not None:
                settle(holder)

        @Slot(str)
        def closeWindow(self, key) -> None:  # noqa: N802
            self._grabs.pop(key, None)
            holder = popout_windows.get(key)
            if holder is not None:
                holder.close()

        @Slot()
        def startMove(self) -> None:  # noqa: N802
            """The page's header was grabbed: the window system moves the window."""
            handle = window.windowHandle()
            if handle is not None:
                handle.startSystemMove()

        @Slot()
        def toggleZoom(self) -> None:  # noqa: N802
            """A double-click on the header: zoom, as a title bar does."""
            if window.isMaximized():
                window.showNormal()
            else:
                window.showMaximized()

        @Slot(bool, bool, result=bool)
        def setFrosted(self, on: bool, dark: bool) -> bool:  # noqa: N802
            """The main window frosted or solid: the desktop shows through,
            blurred behind where the system can. Answers whether it can;
            the page paints its frost only when it says so."""
            if not support["frost"]:
                return False
            if not on:
                if main_state["blur"]:
                    try:
                        if mac is not None:
                            mac.clear(main_state["blur"])
                        elif x11 is not None:
                            x11.set_blur(int(window.winId()), False)
                    except Exception:  # noqa: BLE001
                        logger.debug("could not take the window's frost away", exc_info=True)
                    main_state["blur"] = 0
                return False
            if mac is not None:
                try:
                    main_state["blur"] = mac.frost(int(window.winId()), main_state["blur"], bool(dark), 0.0,
                                                   window.width(), window.height(), material=MacBlur._POPOVER,
                                                   tint=None if dark else MAIN_LIGHT_TINT)
                except Exception:  # noqa: BLE001 - a solid window is the fallback
                    logger.debug("could not frost the window", exc_info=True)
                    return False
                return True
            # Linux: the window is translucent and the frost is the page's own;
            # KWin, asked through the X11 property, blurs behind it.
            if x11 is not None and x11.blur_supported():
                try:
                    x11.set_blur(int(window.winId()), True)
                    main_state["blur"] = 1
                except Exception:  # noqa: BLE001 - frosted without the blur
                    logger.debug("could not add a blur behind the window", exc_info=True)
            return True

        @Slot(bool, result=bool)
        def setPinned(self, on: bool) -> bool:  # noqa: N802
            """Keep the main window above other programs', or stop. A pinned
            terminal is kept above Cmdly's windows only while Cmdly is in
            front (stays_on_top); this is the app itself, so the pin is the
            window system's own always-on-top, for as long as it is on."""
            if not support["pin"]:
                return False
            set_on_top(window, bool(on))
            return bool(on)

    class MainPage(QWebEnginePage):
        """The app's page: window.open gets a terminal window; links leave for the browser."""

        def createWindow(self, _type):  # noqa: N802
            return open_popout(self.profile())

        def acceptNavigationRequest(self, url, nav_type, is_main_frame):  # noqa: N802
            text = url.toString()
            if not is_main_frame or popout_url_allowed(text, port) or text.startswith("blob:") \
                    or text.startswith("data:"):
                return True
            if external_url(text):
                from PySide6.QtGui import QDesktopServices
                QDesktopServices.openUrl(QUrl(text))
            return False

        def javaScriptConsoleMessage(self, level, message, line, source):  # noqa: N802
            if level == QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel:
                logger.warning("page: %s (%s:%s)", message, source.rsplit("/", 1)[-1], line)

    def native_script():
        source = QFile(":/qtwebchannel/qwebchannel.js")
        if not source.open(QIODevice.OpenModeFlag.ReadOnly):
            logger.warning("qwebchannel.js not found; terminals stay inside the window")
            return None
        script = QWebEngineScript()
        script.setName("cmdly-native")
        script.setSourceCode(bytes(source.readAll()).decode("utf-8")
                             + native_support_js(support) + NATIVE_BOOTSTRAP_JS)
        script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
        script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        script.setRunsOnSubFrames(False)
        return script

    profile_dir = webengine_profile_dir(not first)
    os.makedirs(profile_dir, exist_ok=True)
    profile = QWebEngineProfile("cmdly", window)
    profile.setPersistentStoragePath(profile_dir)
    profile.setCachePath(os.path.join(profile_dir, "cache"))

    def on_download(request: QWebEngineDownloadRequest) -> None:
        """A setup exported from Settings: ask where it goes, like a Save dialog."""
        name = request.suggestedFileName() or "cmdly-setup.json"
        start = os.path.join(os.path.expanduser("~"), "Downloads", name)
        path, _ = QFileDialog.getSaveFileName(window, "Export Cmdly setup", start, "JSON (*.json)")
        if not path:
            request.cancel()
            return
        request.setDownloadDirectory(os.path.dirname(path))
        request.setDownloadFileName(os.path.basename(path))
        request.accept()

    profile.downloadRequested.connect(on_download)

    web = QWebEngineView()
    page = MainPage(profile, web)
    if support["frost"]:
        page.setBackgroundColor(Qt.GlobalColor.transparent)
    web.setPage(page)
    configure_view(web)
    script = native_script()
    if script is not None:
        profile.scripts().insert(script)
        channel = QWebChannel(page)
        channel.registerObject("cmdlyNative", MainBridge(web))
        page.setWebChannel(channel)
    web.setUrl(QUrl(f"http://localhost:{port}/"))
    if support["unified"]:
        web.setAttribute(Qt.WidgetAttribute.WA_ContentsMarginsRespectsSafeArea, False)
    window.setCentralWidget(web)

    # ---- window size, remembered ----------------------------------------------------
    resize_timer = QTimer()
    resize_timer.setSingleShot(True)
    resize_timer.setInterval(600)
    resize_timer.timeout.connect(lambda: (not window.isMaximized() and not window.isFullScreen()
                                          and config.set_window(window.width(), window.height())))
    original_resize = window.resizeEvent

    def on_resize(event) -> None:
        original_resize(event)
        resize_timer.start()

    window.resizeEvent = on_resize

    # ---- shutdown ----------------------------------------------------------------------
    shutdown_lock = threading.Lock()
    done = threading.Event()

    def shutdown() -> None:
        with shutdown_lock:
            if done.is_set():
                return
            done.set()
        logger.info("shutting down: closing sessions, ending programs")
        server.stop()

        def watchdog() -> None:
            # QtWebEngine's helpers can hold interpreter teardown; never hang on quit.
            time.sleep(2.0)
            if threading.main_thread().is_alive():
                logger.warning("clean exit timed out; forcing it")
                os._exit(0)

        threading.Thread(target=watchdog, name="exit-watchdog", daemon=True).start()
        try:
            web.page().deleteLater()
        except Exception:  # noqa: BLE001
            pass

    app.aboutToQuit.connect(shutdown)
    atexit.register(shutdown)
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    signal.signal(signal.SIGTERM, lambda *_: app.quit())
    # Python only sees a signal between bytecodes; this keeps it ticking.
    tick = QTimer()
    tick.start(400)
    tick.timeout.connect(lambda: None)

    window.show()
    if support["unified"] and mac is not None:
        try:
            main_state["unified"] = mac.unify(int(window.winId()))
        except Exception:  # noqa: BLE001 - the system title bar is the fallback
            logger.debug("could not unify the title bar", exc_info=True)
    logger.info("Cmdly %s ready", get_version())
    ret = app.exec()
    shutdown()
    return ret


if __name__ == "__main__":
    sys.exit(main())
