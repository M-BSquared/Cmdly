"""Native window effects the desktop wrapper needs beyond what Qt offers.

Windows: placing a pop out window in the operating system's own
pixels (:class:`Win32Windows`). macOS: blurring the desktop behind a window
(:class:`MacBlur`): a frosted terminal of its own, and the main window's
frost, whose title bar :meth:`MacBlur.unify` also folds into the page.
X11: what a see-through window needs from the display server
(:class:`X11Effects`): whether anything composites, and KWin's blur behind
a window. Each loads only on its own platform and answers
None elsewhere, so cmdly/app.py can ask without branching on the platform.
"""
from __future__ import annotations

import logging
import sys

logger = logging.getLogger("cmdly.app")


class Win32Windows:
    """The Win32 calls a frameless window needs to follow the pointer on Windows.

    Qt's coordinates on Windows are logical pixels, and with screens at
    different scales (a laptop at 150 % beside a monitor at 100 %) they are
    not one continuous plane: each screen keeps its physical origin and is
    shrunk from there, so there are gaps and overlaps between them. A window
    moved through ``QWidget.move`` while the pointer crosses from one screen
    to the other lands in a gap, is placed by the scale of the screen it came
    from, and jumps back and forth. Windows' own pixels have no gaps. So the
    drag is done in them: where the pointer is (``GetCursorPos``), where the
    window is (``GetWindowRect``), and ``SetWindowPos``; Windows then tells Qt
    the window changed screens, and Qt rescales it as it would for the
    system's own drag.
    """

    _SWP_NOSIZE = 0x0001
    _SWP_NOZORDER = 0x0004
    _SWP_NOACTIVATE = 0x0010

    def __init__(self) -> None:
        import ctypes
        from ctypes import wintypes

        self._ct = ctypes
        self._wt = wintypes
        # A private handle, so setting argtypes here changes nothing for any
        # other user of ctypes.windll.user32.
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
        user32.GetCursorPos.restype = wintypes.BOOL
        user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        user32.GetWindowRect.restype = wintypes.BOOL
        user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                        ctypes.c_int, ctypes.c_int, wintypes.UINT]
        user32.SetWindowPos.restype = wintypes.BOOL
        self._user32 = user32

    def cursor(self) -> tuple[int, int]:
        pt = self._wt.POINT()
        if not self._user32.GetCursorPos(self._ct.byref(pt)):
            raise OSError(self._ct.get_last_error(), "GetCursorPos failed")
        return pt.x, pt.y

    def origin(self, hwnd: int) -> tuple[int, int]:
        rect = self._wt.RECT()
        if not self._user32.GetWindowRect(hwnd, self._ct.byref(rect)):
            raise OSError(self._ct.get_last_error(), "GetWindowRect failed")
        return rect.left, rect.top

    def move(self, hwnd: int, x: int, y: int) -> None:
        flags = self._SWP_NOSIZE | self._SWP_NOZORDER | self._SWP_NOACTIVATE
        if not self._user32.SetWindowPos(hwnd, None, int(x), int(y), 0, 0, flags):
            raise OSError(self._ct.get_last_error(), "SetWindowPos failed")


def win32_windows(platform: str = sys.platform) -> Win32Windows | None:
    """:class:`Win32Windows` on Windows, None elsewhere or when it cannot load."""
    if platform != "win32":
        return None
    try:
        return Win32Windows()
    except Exception:  # noqa: BLE001 - Qt's own moves are the fallback
        logger.debug("Win32 window calls unavailable", exc_info=True)
        return None


class MacBlur:
    """The desktop behind a see-through window, blurred by macOS.

    A terminal's window of its own is frosted glass unless Settings asks for
    solid ones (src/js/popout-page.js), and the page cannot do that alone: CSS
    ``backdrop-filter`` only sees the page, and behind the page is the
    desktop. macOS blurs it with an ``NSVisualEffectView`` behind the window's
    content. Qt's view *is* the content view and draws in its own layer, so a
    subview of it would cover the page; the effect view goes one level up,
    into the window's frame view, below the content view. It follows the
    window's size by itself, and its layer is rounded like the page's frame,
    so the blur has the frame's corners rather than the window's square ones.

    ctypes over the Objective-C runtime rather than PyObjC: a dozen messages
    to AppKit are not worth a dependency. Every call is made on the Qt main
    thread, which is AppKit's.
    """

    _BEHIND_WINDOW = 0       # NSVisualEffectBlendingModeBehindWindow
    _ALWAYS_ACTIVE = 1       # NSVisualEffectStateActive: not grey behind another app
    _POPOVER = 6             # the material that lets the most colour through
    _SIZABLE = 2 | 16        # NSViewWidthSizable | NSViewHeightSizable
    _BELOW = -1              # NSWindowBelow
    _UNDER_WINDOW = 21       # NSVisualEffectMaterialUnderWindowBackground
    _SIDEBAR = 7             # NSVisualEffectMaterialSidebar
    _TITLE_HIDDEN = 1        # NSWindowTitleHidden

    def __init__(self) -> None:
        import ctypes
        import ctypes.util

        objc_path = ctypes.util.find_library("objc")
        appkit_path = ctypes.util.find_library("AppKit")
        if not objc_path or not appkit_path:
            raise OSError("no Objective-C runtime or AppKit")
        ctypes.CDLL(appkit_path)
        objc = ctypes.CDLL(objc_path)
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.objc_getClass.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.sel_registerName.argtypes = [ctypes.c_char_p]
        if not objc.objc_getClass(b"NSVisualEffectView"):
            raise OSError("AppKit has no NSVisualEffectView")

        class Rect(ctypes.Structure):
            _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double),
                        ("w", ctypes.c_double), ("h", ctypes.c_double)]

        self._ct = ctypes
        self._objc = objc
        self._rect = Rect
        self._msg_send = ctypes.cast(objc.objc_msgSend, ctypes.c_void_p).value
        self._prototypes: dict = {}

    def _send(self, target: int, selector: str, restype=None, argtypes=(), *args):
        """``[target selector:args…]``, with the C signature spelled out."""
        c = self._ct
        key = (restype, tuple(argtypes))
        fn = self._prototypes.get(key)
        if fn is None:
            fn = c.CFUNCTYPE(restype, c.c_void_p, c.c_void_p, *argtypes)(self._msg_send)
            self._prototypes[key] = fn
        return fn(target, self._objc.sel_registerName(selector.encode()), *args)

    def _obj(self, target: int, selector: str) -> int:
        return int(self._send(target, selector, self._ct.c_void_p) or 0)

    def frost(self, view_id: int, effect: int, dark: bool, radius: float,
              width: int, height: int, material: int | None = None,
              tint: tuple[float, float, float, float] | None = None) -> int:
        """Blur the desktop behind the window whose content view is *view_id*.

        *effect* is what an earlier call returned, or 0: it is updated in
        place while it is still behind this window, and replaced when Qt has
        made the window anew. *dark* picks the blur's own tint to match the
        theme, *radius* is the page frame's corner radius and *width* by
        *height* the window's size, all in points. *tint* is an optional
        (red, green, blue, alpha) laid over the blur by the blur view itself:
        a light, see-through colour drawn by the page comes out white in a
        translucent Qt window, a native one does not. Returns the effect view,
        retained, for the next call or for :meth:`clear`.
        """
        c = self._ct
        window = self._obj(view_id, "window")
        content = self._obj(window, "contentView") if window else 0
        frame = self._obj(content, "superview") if content else 0
        if not frame:
            raise OSError("the view is not in a window with a frame view")
        # Let go of a view behind a window that is gone only once its
        # replacement exists: the caller keeps what it had if this raises.
        # The blur only shows through a window that is not opaque; Qt's
        # translucent attribute does not always leave it so.
        self._send(window, "setOpaque:", None, (c.c_bool,), False)
        clear = self._send(self._objc.objc_getClass(b"NSColor"), "clearColor", c.c_void_p)
        self._send(window, "setBackgroundColor:", None, (c.c_void_p,), clear)
        stale = effect if effect and self._obj(effect, "superview") != frame else 0
        if stale:
            effect = 0
        if not effect:
            cls = self._objc.objc_getClass(b"NSVisualEffectView")
            effect = self._obj(cls, "alloc")
            effect = int(self._send(effect, "initWithFrame:", c.c_void_p, (self._rect,),
                                    self._rect(0.0, 0.0, float(width), float(height))) or 0)
            if not effect:
                raise OSError("could not make an NSVisualEffectView")
            self._send(effect, "setAutoresizingMask:", None, (c.c_ulong,), self._SIZABLE)
            self._send(effect, "setBlendingMode:", None, (c.c_long,), self._BEHIND_WINDOW)
            self._send(effect, "setState:", None, (c.c_long,), self._ALWAYS_ACTIVE)
            self._send(effect, "setWantsLayer:", None, (c.c_bool,), True)
            self._send(frame, "addSubview:positioned:relativeTo:", None,
                       (c.c_void_p, c.c_long, c.c_void_p), effect, self._BELOW, content)
        if stale:
            self.clear(stale)
        self._send(effect, "setMaterial:", None, (c.c_long,),
                   self._POPOVER if material is None else int(material))
        name = b"NSAppearanceNameDarkAqua" if dark else b"NSAppearanceNameAqua"
        text = self._send(self._objc.objc_getClass(b"NSString"), "stringWithUTF8String:",
                          c.c_void_p, (c.c_char_p,), name)
        appearance = self._send(self._objc.objc_getClass(b"NSAppearance"), "appearanceNamed:",
                                c.c_void_p, (c.c_void_p,), text)
        self._send(effect, "setAppearance:", None, (c.c_void_p,), appearance)
        layer = self._obj(effect, "layer")
        if layer:
            self._send(layer, "setCornerRadius:", None, (c.c_double,), max(0.0, float(radius)))
            self._send(layer, "setMasksToBounds:", None, (c.c_bool,), True)
        # The effect view draws its material itself and ignores a background
        # colour on its layer: the tint is a plain view on top of it.
        tint_view = self._obj(self._obj(effect, "subviews"), "firstObject")
        if not tint_view:
            tint_view = self._obj(self._obj(self._objc.objc_getClass(b"NSView"), "alloc"), "init")
            self._send(tint_view, "setFrame:", None, (self._rect,),
                       self._rect(0.0, 0.0, float(width), float(height)))
            self._send(tint_view, "setAutoresizingMask:", None, (c.c_ulong,), self._SIZABLE)
            self._send(tint_view, "setWantsLayer:", None, (c.c_bool,), True)
            self._send(effect, "addSubview:", None, (c.c_void_p,), tint_view)
        tint_layer = self._obj(tint_view, "layer")
        cg = 0
        if tint:
            color = self._send(self._objc.objc_getClass(b"NSColor"),
                               "colorWithSRGBRed:green:blue:alpha:", c.c_void_p,
                               (c.c_double,) * 4, *[float(v) for v in tint])
            cg = self._obj(color, "CGColor") if color else 0
        if tint_layer:
            self._send(tint_layer, "setBackgroundColor:", None, (c.c_void_p,), cg)
        # The window's shadow is traced from what it draws, and it now draws
        # the blur as well.
        self._send(window, "invalidateShadow")
        return effect

    def unify(self, view_id: int) -> bool:
        """Finish folding the title bar into the content: no title drawn.

        The traffic lights stay; the bar behind them is transparent, so the
        page's own header sits under them and the frost reaches the top
        edge, as the system's own windows do. The window's title is kept
        (Mission Control and the Window menu read it) but not drawn. Returns
        whether it was done.
        """
        c = self._ct
        window = self._obj(view_id, "window")
        if not window:
            return False
        # The content view already runs the full height (Qt's
        # ExpandedClientAreaHint, set on the window in cmdly/app.py): changing
        # the style mask here, behind Qt's back, left Qt's view where it was.
        self._send(window, "setTitlebarAppearsTransparent:", None, (c.c_bool,), True)
        self._send(window, "setTitleVisibility:", None, (c.c_long,), self._TITLE_HIDDEN)
        # A window you can drag by its page would fight the page's own drags
        # (text selection, the shelf's reordering): the header asks for a move
        # itself (QWindow.startSystemMove).
        self._send(window, "setMovableByWindowBackground:", None, (c.c_bool,), False)
        return True

    def clear(self, effect: int) -> None:
        """Take the blur away, and let go of the view :meth:`frost` returned."""
        if not effect:
            return
        self._send(effect, "removeFromSuperview")
        self._send(effect, "release")


def mac_blur(platform: str = sys.platform) -> MacBlur | None:
    """:class:`MacBlur` on macOS, None elsewhere or when AppKit will not load."""
    if platform != "darwin":
        return None
    try:
        return MacBlur()
    except Exception:  # noqa: BLE001 - a solid terminal is the fallback
        logger.debug("macOS window blur unavailable", exc_info=True)
        return None


class X11Effects:
    """X11: what a see-through window needs from the display server.

    A window Qt paints with translucency is only real where something
    composites the screen; without a compositor (Xfce with compositing off,
    an old Xorg) the alpha channel is dropped and the window comes up black.
    :meth:`composited` asks whether one runs, through the selection the
    compositing manager owns (``_NET_WM_CM_S<screen>``, the spec's own way
    of saying it is there — the same thing KWindowSystem asks).

    :meth:`blur_supported` asks whether the window manager blurs the desktop
    behind a window that asks for it: KWin's, announced like every hint it
    honours, in the root window's ``_NET_SUPPORTED`` list.
    :meth:`set_blur` asks: the property ``_KDE_NET_WM_BLUR_BEHIND_REGION``
    on the window, empty, which KWin reads as "the whole window" (and
    follows a window's size by itself, so no resize is ever answered). A
    window Qt has made anew simply carries no property and is not blurred
    until asked again.

    ctypes over libX11 rather than python-xlib: a dozen calls are not worth
    a dependency. Every call is made on the Qt main thread, on a connection
    of our own — Qt's xcb plugin never sees it.
    """

    _XA_ATOM = 4        # the X server's own atom type
    _XA_CARDINAL = 6    # an array of cardinals
    _PROP_REPLACE = 0   # PropModeReplace

    def __init__(self) -> None:
        import ctypes
        import ctypes.util

        x11_path = ctypes.util.find_library("X11") or "libX11.so.6"
        # A private handle, so setting argtypes here changes nothing for any
        # other user of libX11.
        x11 = ctypes.CDLL(x11_path)
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x11.XDefaultScreen.restype = ctypes.c_int
        x11.XDefaultScreen.argtypes = [ctypes.c_void_p]
        x11.XDefaultRootWindow.restype = ctypes.c_ulong
        x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        x11.XInternAtom.restype = ctypes.c_ulong
        x11.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
        x11.XGetSelectionOwner.restype = ctypes.c_ulong
        x11.XGetSelectionOwner.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        x11.XGetWindowProperty.restype = ctypes.c_int
        x11.XGetWindowProperty.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_long, ctypes.c_long, ctypes.c_int,
            ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_void_p),
        ]
        x11.XChangeProperty.restype = ctypes.c_int
        x11.XChangeProperty.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong,
                                        ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int]
        x11.XDeleteProperty.restype = ctypes.c_int
        x11.XDeleteProperty.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong]
        x11.XFree.restype = ctypes.c_int
        x11.XFree.argtypes = [ctypes.c_void_p]
        display = x11.XOpenDisplay(None)
        if not display:
            raise OSError("no X display")
        self._ct = ctypes
        self._x11 = x11
        self._display = display
        # An X error would end the process by default (a stale window id is
        # enough); this handler logs and carries on. It is per connection:
        # Qt's xcb plugin, whose errors Qt handles, is not ours.
        self._error_handler = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)(
            self._on_x_error)
        x11.XSetErrorHandler.argtypes = [ctypes.c_void_p]
        x11.XSetErrorHandler.restype = ctypes.c_void_p
        x11.XSetErrorHandler(self._error_handler)
        self._root = x11.XDefaultRootWindow(display)

        def atom(name: str, only_existing: bool = False) -> int:
            return int(x11.XInternAtom(display, name.encode(), only_existing))

        self._cm = atom(f"_NET_WM_CM_S{x11.XDefaultScreen(display)}", True)
        self._supported = atom("_NET_SUPPORTED", True)
        self._blur = atom("_KDE_NET_WM_BLUR_BEHIND_REGION", True)

    @staticmethod
    def _on_x_error(_display, _event) -> int:
        logger.debug("an X11 window call failed")
        return 0

    def composited(self) -> bool:
        """Whether a compositing manager runs; without one, a see-through
        window is not real."""
        return bool(self._cm and self._x11.XGetSelectionOwner(self._display, self._cm))

    def blur_supported(self) -> bool:
        """Whether the window manager blurs the desktop behind a window that
        asks for it (KWin, which announces the hint in _NET_SUPPORTED)."""
        if not self._blur or not self._supported:
            return False
        c = self._ct
        kind, fmt, items, after, data = (c.c_ulong(), c.c_int(), c.c_ulong(),
                                         c.c_ulong(), c.c_void_p())
        found = self._x11.XGetWindowProperty(self._display, self._root, self._supported,
                                             0, 4096, False, self._XA_ATOM,
                                             c.byref(kind), c.byref(fmt), c.byref(items),
                                             c.byref(after), c.byref(data))
        if found or fmt.value != 32 or not data.value:
            if data.value:
                self._x11.XFree(data)
            return False
        try:
            atoms = c.cast(data, c.POINTER(c.c_ulong))
            return any(atoms[i] == self._blur for i in range(items.value))
        finally:
            self._x11.XFree(data)

    def set_blur(self, window_id: int, on: bool) -> None:
        """Ask the window manager to blur the desktop behind the window, or
        stop asking."""
        if not self._blur:
            return
        if on:
            self._x11.XChangeProperty(self._display, window_id, self._blur,
                                      self._XA_CARDINAL, 32, self._PROP_REPLACE, None, 0)
        else:
            self._x11.XDeleteProperty(self._display, window_id, self._blur)


def x11_effects(platform_name: str, os_platform: str = sys.platform) -> X11Effects | None:
    """:class:`X11Effects` under X11, None elsewhere or without a display."""
    if os_platform != "linux" or not str(platform_name or "").lower().startswith("xcb"):
        return None
    try:
        return X11Effects()
    except Exception:  # noqa: BLE001 - a solid window is the fallback
        logger.debug("X11 window effects unavailable", exc_info=True)
        return None
