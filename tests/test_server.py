"""The HTTP backend (cmdly/server.py), over a real socket."""
from __future__ import annotations

import http.client
import json
import sys
import time

import pytest

from cmdly import launcher
from cmdly import server as server_module
from cmdly.config import Config
from cmdly.server import CmdlyServer, serve_in_thread


@pytest.fixture
def server(tmp_path):
    srv = CmdlyServer(("127.0.0.1", 0), Config(str(tmp_path / "config.json")))
    serve_in_thread(srv)
    yield srv
    srv.stop()


def request(srv, method, path, body=None, host=None, origin=None, raw=None):
    conn = http.client.HTTPConnection("127.0.0.1", srv.port, timeout=10)
    headers = {"Host": host or f"localhost:{srv.port}"}
    if origin:
        headers["Origin"] = origin
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    if data is not None:
        headers["Content-Type"] = "application/json"
    conn.request(method, path, body=data, headers=headers)
    res = conn.getresponse()
    payload = res.read()
    conn.close()
    try:
        return res.status, json.loads(payload)
    except ValueError:
        return res.status, payload


def test_the_page_and_the_icon_are_served(server):
    status, body = request(server, "GET", "/")
    assert status == 200 and b"<title>Cmdly</title>" in body
    status, body = request(server, "GET", "/assets/icon.png")
    assert status == 200 and body[:4] == b"\x89PNG"


@pytest.mark.parametrize("path", ["/../cmdly/config.py", "/%2e%2e/cmdly/server.py", "/assets/../VERSION"])
def test_nothing_outside_the_web_folder_is_served(server, path):
    status, _ = request(server, "GET", path)
    assert status == 404


def test_a_request_naming_another_host_is_refused(server):
    status, _ = request(server, "GET", "/api/version", host="evil.example:80")
    assert status == 403


def test_a_post_from_another_site_is_refused(server):
    status, _ = request(server, "POST", "/api/config", {"ui": {}}, origin="https://evil.example")
    assert status == 403
    status, _ = request(server, "POST", "/api/config", {"ui": {}}, origin="null")
    assert status == 403


def test_a_post_from_the_app_is_accepted(server):
    status, body = request(server, "POST", "/api/config", {"ui": {"theme": "blue"}},
                           origin=f"http://localhost:{server.port}")
    assert status == 200 and body["config"]["ui"]["theme"] == "blue"


def test_a_body_that_is_not_json_is_refused(server):
    status, body = request(server, "POST", "/api/config", raw=b"{nope")
    assert status == 400 and body["ok"] is False


def test_connections_round_trip_without_the_password(server):
    status, body = request(server, "POST", "/api/ssh/connections",
                           {"host": "10.0.0.2", "username": "pi", "password": "secret"})
    assert status == 200 and body["connection"]["name"] == "pi@10.0.0.2"
    status, body = request(server, "GET", "/api/ssh/connections")
    assert "secret" not in json.dumps(body)
    assert body["connections"][0]["has_password"] is True
    status, body = request(server, "POST", "/api/ssh/connections/remove", {"name": "pi@10.0.0.2"})
    assert body["connections"] == []


def test_a_connect_to_a_connection_this_computer_lacks_says_what_it_needs(server):
    status, body = request(server, "POST", "/api/ssh/connect", {"name": "cmdly/b1", "from": "pi"})
    assert status == 400
    assert body["needs"] == "connection" and body["connection"] == "pi"


def test_a_background_run_without_the_connection_says_what_it_needs(server):
    status, body = request(server, "POST", "/api/ssh/run", {"name": "pi", "command": "x"})
    assert status == 400 and body["needs"] == "connection"


def test_the_power_menu_names_its_actions_and_needs_the_connection(server):
    status, body = request(server, "POST", "/api/ssh/power", {"name": "pi", "action": "explode"})
    assert status == 400 and body["ok"] is False
    status, body = request(server, "POST", "/api/ssh/power", {"name": "pi", "action": "shutdown"})
    assert status == 400 and body["needs"] == "connection" and body["connection"] == "pi"


def _save_connection(server, **fields) -> str:
    status, body = request(server, "POST", "/api/ssh/connections",
                           {"host": "10.0.0.2", "username": "pi", **fields})
    assert status == 200 and body["ok"] is True
    return body["connection"]["name"]


def _power_run_result(**result) -> dict:
    return {"ok": False, "exit_status": None, "stdout": "", "stderr": "",
            "error": "did not run", "auth_failed": False, **result}


def test_the_power_action_types_the_saved_login_password_into_sudo(server, monkeypatch):
    """sudo -S reads its password from the command's input, so a computer
    whose sudo asks for one is shut down all the same."""
    name = _save_connection(server, password="raspberry")
    sent = {}

    def run_command(**kwargs):
        sent.update(kwargs)
        return _power_run_result(ok=True, exit_status=0, error="")

    monkeypatch.setattr(server_module, "run_command", run_command)
    status, body = request(server, "POST", "/api/ssh/power", {"name": name, "action": "shutdown"})
    assert status == 200 and body["ok"] is True
    assert sent["command"] == launcher.POWER_ACTIONS["shutdown"]
    assert sent["stdin"] == "raspberry\n"


def test_the_power_action_without_a_saved_password_closes_sudos_input(server, monkeypatch):
    """A key login has no password to give sudo: sudo sees EOF instead of a
    wait until the timeout, and the reply says what the page should ask for."""
    name = _save_connection(server, key_path="~/.ssh/id_ed25519")
    sent = {}

    def run_command(**kwargs):
        sent.update(kwargs)
        return _power_run_result(exit_status=1, stderr="sudo: no password was provided\n",
                                  error="command exited with status 1")

    monkeypatch.setattr(server_module, "run_command", run_command)
    status, body = request(server, "POST", "/api/ssh/power", {"name": name, "action": "reboot"})
    assert status == 200 and body["ok"] is False
    assert sent["stdin"] == ""
    assert body["needs"] == "sudo-password" and body["connection"] == name
    assert "login password" in body["stderr"]


def test_the_power_action_names_which_password_sudo_did_not_accept(server, monkeypatch):
    """The saved login password reached sudo and was refused: not a question
    the page can answer with a save — the reply says which password failed."""
    name = _save_connection(server, password="raspberry")
    monkeypatch.setattr(server_module, "run_command",
                        lambda **kwargs: _power_run_result(
                            exit_status=1, stderr="sudo: 1 incorrect password attempt\n",
                            error="command exited with status 1"))
    status, body = request(server, "POST", "/api/ssh/power", {"name": name, "action": "shutdown"})
    assert status == 200 and body["ok"] is False
    assert "needs" not in body
    assert "sudo did not accept the connection's saved login password" in body["stderr"]


def test_the_power_action_with_a_refused_login_says_what_it_needs(server, monkeypatch):
    name = _save_connection(server, password="raspberry")
    monkeypatch.setattr(server_module, "run_command",
                        lambda **kwargs: _power_run_result(auth_failed=True))
    status, body = request(server, "POST", "/api/ssh/power", {"name": name, "action": "shutdown"})
    assert status == 200 and body["ok"] is False
    assert body["needs"] == "credentials" and body["connection"] == name


@pytest.mark.skipif(sys.platform == "win32", reason="a pseudo-terminal is POSIX only")
def test_a_local_terminal_session_from_connect_to_disconnect(server):
    status, body = request(server, "POST", "/api/local/connect", {"name": "cmdly/t"})
    assert body["connected"] is True
    _, body = request(server, "GET", "/api/ssh/sessions")
    assert any(s["name"] == "cmdly/t" and s["connected"] for s in body["sessions"])
    _, body = request(server, "POST", "/api/ssh/send", {"name": "cmdly/t", "data": "echo cmdly-$((40+2))\n"})
    assert body["ok"] is True
    session = server.ssh.get_session("cmdly/t")
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and "cmdly-42" not in "".join(session._replay):
        time.sleep(0.05)
    assert "cmdly-42" in "".join(session._replay)
    _, body = request(server, "POST", "/api/ssh/resize", {"name": "cmdly/t", "cols": 100, "rows": 30})
    assert body["ok"] is True
    _, body = request(server, "POST", "/api/ssh/disconnect", {"name": "cmdly/t"})
    assert body["ok"] is True
    _, body = request(server, "GET", "/api/ssh/sessions")
    assert body["sessions"] == []


def test_a_background_program_that_fails_at_once_says_so(server):
    _, body = request(server, "POST", "/api/local/run", {"command": "echo nope; exit 3"})
    assert body["exited"] is True and body["code"] == 3 and "nope" in body["output"]


@pytest.mark.skipif(sys.platform == "win32", reason="a pseudo-terminal is POSIX only")
def test_the_output_route_returns_a_sessions_terminal_so_far(server):
    """The once-and-done read of a client with no stream (an agent over MCP):
    the scrollback as one snapshot, its tail bounded."""
    _, body = request(server, "POST", "/api/local/connect", {"name": "cmdly/t"})
    assert body["connected"] is True
    _, body = request(server, "POST", "/api/ssh/send", {"name": "cmdly/t", "data": "echo cmdly-$((40+2))\n"})
    session = server.ssh.get_session("cmdly/t")
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and "cmdly-42" not in session.snapshot():
        time.sleep(0.05)
    _, body = request(server, "GET", "/api/ssh/output?name=cmdly/t")
    assert body["connected"] is True and "cmdly-42" in body["output"]
    _, body = request(server, "GET", "/api/ssh/output?name=cmdly/t&tail=5")
    assert len(body["output"]) == 5
    status, body = request(server, "GET", "/api/ssh/output?name=cmdly/nope")
    assert status == 404 and body["ok"] is False
    request(server, "POST", "/api/ssh/disconnect", {"name": "cmdly/t"})


def test_the_local_power_route_runs_the_backends_own_line(server, monkeypatch):
    sent = {}

    def run(command, directory=""):
        sent["command"] = command
        return {"ok": False, "exited": True, "code": 1, "output": "shutdown: you must be root"}

    monkeypatch.setattr(server.local, "run", run)
    status, body = request(server, "POST", "/api/local/power", {"action": "explode"})
    assert status == 400 and body["ok"] is False
    status, body = request(server, "POST", "/api/local/power", {"action": "shutdown"})
    assert status == 200 and body["ok"] is False and "you must be root" in body["output"]
    assert sent["command"] == launcher.local_power_line("shutdown")


@pytest.mark.parametrize("payload", [{"name": "x", "cols": 0, "rows": 5}, {"name": "x", "cols": True, "rows": 5},
                                     {"cols": 80, "rows": 24}])
def test_resize_refuses_a_bad_size(server, payload):
    status, _ = request(server, "POST", "/api/ssh/resize", payload)
    assert status == 400


def test_an_unknown_route_is_404(server):
    status, _ = request(server, "POST", "/api/nope", {})
    assert status == 404
