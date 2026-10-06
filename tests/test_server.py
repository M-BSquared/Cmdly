"""The HTTP backend (cmdly/server.py), over a real socket."""
from __future__ import annotations

import http.client
import json
import sys
import time

import pytest

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


@pytest.mark.parametrize("payload", [{"name": "x", "cols": 0, "rows": 5}, {"name": "x", "cols": True, "rows": 5},
                                     {"cols": 80, "rows": 24}])
def test_resize_refuses_a_bad_size(server, payload):
    status, _ = request(server, "POST", "/api/ssh/resize", payload)
    assert status == 400


def test_an_unknown_route_is_404(server):
    status, _ = request(server, "POST", "/api/nope", {})
    assert status == 404
