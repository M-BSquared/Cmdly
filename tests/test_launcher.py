"""The shelf's rules (cmdly/launcher.py): what is stored, and what a button runs."""
from __future__ import annotations

import pytest

from cmdly import launcher as L


def test_a_button_without_a_command_is_dropped():
    assert L.coerce_button({"label": "x"}) is None
    assert L.coerce_button({"command": "   "}) is None
    assert L.coerce_button("nope") is None


def test_a_button_is_completed():
    b = L.coerce_button({"command": "./run.sh"})
    assert b["label"] == "./run.sh"
    assert b["target"] == L.TARGET_LOCAL
    assert b["mode"] == L.MODE_TERMINAL
    assert b["restart"] is False
    assert b["id"].startswith("b")


def test_a_button_runs_here_in_a_terminal_unless_it_says_otherwise():
    b = L.coerce_button({"command": "x", "connection": "pi@10.0.0.2", "detach": True})
    assert b["target"] == L.TARGET_LOCAL
    assert b["connection"] == ""
    assert b["mode"] == L.MODE_TERMINAL
    b = L.coerce_button({"command": "x", "target": "ssh", "connection": "pi", "mode": "background"})
    assert b["target"] == L.TARGET_SSH
    assert b["mode"] == L.MODE_BACKGROUND


def test_a_local_button_names_no_connection():
    b = L.coerce_button({"command": "x", "target": "local", "connection": "old"})
    assert b["connection"] == ""


def test_restart_must_be_a_real_true():
    assert L.coerce_button({"command": "x", "restart": "yes"})["restart"] is False
    assert L.coerce_button({"command": "x", "restart": True})["restart"] is True


def test_the_shelf_is_capped_and_ids_are_unique():
    raw = [{"id": "same", "command": f"c{i}"} for i in range(L.MAX_BUTTONS + 5)]
    out = L.normalize_buttons(raw)
    assert len(out) == L.MAX_BUTTONS
    assert len({b["id"] for b in out}) == len(out)


def test_an_unsafe_id_is_replaced():
    assert L.coerce_button({"id": "../x", "command": "c"})["id"] != "../x"


@pytest.mark.parametrize("directory, line", [
    ("", "ls"),
    ("~", "cd -- ~ && ls"),
    ("~/my dir", "cd -- ~/'my dir' && ls"),
    ("/opt/it's", "cd -- '/opt/it'\\''s' && ls"),
    ("-rf", "cd -- '-rf' && ls"),
])
def test_the_terminal_line_quotes_the_folder(directory, line):
    assert L.terminal_line({"directory": directory, "command": "ls"}) == line


def test_a_background_run_over_ssh_is_detached_and_echoes_its_pid():
    line = L.remote_command("/srv/app", "python main.py", True)
    assert line == "cd -- /srv/app && { nohup python main.py >/dev/null 2>&1 & }; echo $!"
    assert L.remote_command("", "uptime", False) == "uptime"


@pytest.mark.parametrize("host, ok", [
    ("192.168.2.10", True), ("companion.local", True), ("fe80::1%en0", True),
    ("", False), ("-f", False), ("a b", False), ("x" * 254, False),
])
def test_host_error(host, ok):
    assert (L.host_error(host) == "") is ok


def test_a_companion_lands_on_slider_stops_with_a_longer_timeout():
    c = L.coerce_companion({"host": "10.0.0.2", "interval_s": 4.2, "timeout_s": 3})
    assert c["interval_s"] == 5
    assert c["timeout_s"] > c["interval_s"]
    assert c["type"] == L.COMPANION_PING


def test_an_ssh_companion_without_a_connection_is_a_ping_one():
    assert L.coerce_companion({"host": "h", "type": "ssh"})["type"] == L.COMPANION_PING
    c = L.coerce_companion({"host": "h", "connection": "pi@h"})
    assert c["type"] == L.COMPANION_SSH


def test_a_companion_with_a_bad_host_is_dropped():
    assert L.coerce_companion({"host": "-x"}) is None


def test_an_older_single_companion_is_read():
    out = L.normalize_companions(None, {"host": "10.0.0.2", "name": "Pi"})
    assert [c["name"] for c in out] == ["Pi"]


def test_pick_active_by_id_or_name_else_the_first():
    cs = L.normalize_companions([{"id": "c1", "host": "a", "name": "A"}, {"id": "c2", "host": "b", "name": "B"}])
    assert L.pick_active(cs, "c2") == "c2"
    assert L.pick_active(cs, "B") == "c2"
    assert L.pick_active(cs, "zz") == "c1"
    assert L.pick_active([], "c1") == ""


def test_a_connection_needs_a_host_and_is_named_user_at_host():
    assert L.coerce_connection({"username": "pi"}) is None
    c = L.coerce_connection({"host": "10.0.0.2", "username": "pi", "port": "abc", "password": " p "})
    assert c["name"] == "pi@10.0.0.2"
    assert c["port"] == 22
    assert c["password"] == " p "


def test_the_page_never_sees_a_password():
    pub = L.public_connection({"name": "n", "host": "h", "password": "secret"})
    assert "password" not in pub
    assert pub["has_password"] is True


def test_reachable():
    comp = {"host": "10.0.0.2", "connection": "pi"}
    conns = [{"name": "other", "host": "10.0.0.2"}, {"name": "far", "host": "10.9.9.9"}]
    assert L.button_reachable({"target": "local"}, None, False, conns)
    assert not L.button_reachable({"target": "ssh", "connection": "pi"}, comp, False, conns)
    assert L.button_reachable({"target": "ssh", "connection": "pi"}, comp, True, conns)
    assert L.button_reachable({"target": "ssh", "connection": "other"}, comp, True, conns)
    assert not L.button_reachable({"target": "ssh", "connection": "far"}, comp, True, conns)


def test_the_power_actions_run_through_sudo_with_the_bare_command_as_the_fallback():
    # sudo first (a companion is usually a user with passwordless sudo), the
    # bare command for a root login; whichever runs takes the computer down.
    assert L.POWER_ACTIONS["shutdown"] == "sudo shutdown -h now || shutdown -h now"
    assert L.POWER_ACTIONS["reboot"] == "sudo reboot || reboot"
    assert set(L.POWER_ACTIONS) == {"shutdown", "reboot"}
