"""The desktop wrapper's rules (cmdly/app.py), without Qt."""
from __future__ import annotations

from cmdly import app


def test_parse_port_arg():
    assert app.parse_port_arg(["cmdly"], 8765) == (8765, "")
    assert app.parse_port_arg(["cmdly", "9000"], 8765) == (9000, "")
    assert app.parse_port_arg(["cmdly", "x"], 8765)[1]
    assert app.parse_port_arg(["cmdly", "70000"], 8765)[1]


def test_a_terminal_window_may_show_only_this_backends_pages():
    assert app.popout_url_allowed("http://localhost:8765/popout.html?key=term:x", 8765)
    assert app.popout_url_allowed("about:blank", 8765)
    assert not app.popout_url_allowed("http://localhost:9999/", 8765)
    assert not app.popout_url_allowed("https://example.com/", 8765)
    assert not app.popout_url_allowed("file:///etc/passwd", 8765)


def test_popout_keys():
    assert app.popout_key("http://localhost:1/popout.html?key=term%3Acmdly%2Fb1") == "term:cmdly/b1"
    assert app.popout_key("http://localhost:1/popout.html?key=video%3Ax") == ""
    assert not app.popout_key_valid("term:" + "x" * 200)


def test_window_support_per_platform():
    mac = app.window_support("cocoa", "darwin")
    assert mac["vibrancy"] and mac["unified"] and mac["place"] and mac["platform"] == "mac"
    wayland = app.window_support("wayland", "linux")
    assert not wayland["place"] and not wayland["pin"] and not wayland["vibrancy"]
    x11 = app.window_support("xcb", "linux")
    assert x11["place"] and x11["pin"] and not x11["frost"] and x11["platform"] == "linux"


def test_a_window_is_kept_on_its_screen():
    assert app.popout_geometry((-500, -500, 600, 400), (0, 25, 1440, 875)) == (0, 25, 600, 400)
    assert app.popout_geometry((100, 100, 5000, 5000), (0, 0, 1000, 800)) == (0, 0, 1000, 800)


def test_pinned_only_while_cmdly_is_in_front():
    assert app.stays_on_top(True, True)
    assert not app.stays_on_top(True, False)
    assert not app.stays_on_top(False, True)


def test_qt_platform_prefers_x11_under_wayland_with_xwayland():
    env = {"WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":0"}
    assert app.qpa_platform(env, "linux") == "xcb;wayland"
    assert app.qpa_platform({"WAYLAND_DISPLAY": "w"}, "linux") == ""
    assert app.qpa_platform({**env, "QT_QPA_PLATFORM": "wayland"}, "linux") == ""
    assert app.qpa_platform(env, "darwin") == ""


def test_desktop_id_and_argv():
    assert app.desktop_id({"APPIMAGE": "/x.AppImage"}) == "cmdly"
    assert app.desktop_id({}) == "cmdly-dev"
    assert app.qt_argv(["a"], "cmdly", "linux") == ["a", "-name", "cmdly"]
    assert app.qt_argv(["a"], "cmdly", "darwin") == ["a"]


def test_chromium_flags():
    assert "--disable-gpu-sandbox" in app.chromium_flags("linux")
    assert "--disable-gpu-sandbox" not in app.chromium_flags("darwin")
