"""The MCP server (cmdly/mcp.py): the protocol over fake stdio, the tools
against a real backend on a real socket.

The JSON-RPC plumbing is driven line by line; the tools run against a
CmdlyServer with the agent's own port given (no discovery), except where the
discovery itself is the point — it has its seams.
"""
from __future__ import annotations

import json
import os
import sys
import time

import pytest

from cmdly import mcp
from cmdly.config import Config
from cmdly.mcp import CmdlyClient, handle_message, serve
from cmdly.server import CmdlyServer, serve_in_thread

TOOLS = {t["name"] for t in mcp.TOOLS}


@pytest.fixture
def server(tmp_path):
    srv = CmdlyServer(("127.0.0.1", 0), Config(str(tmp_path / "config.json")))
    serve_in_thread(srv)
    yield srv
    srv.stop()


@pytest.fixture
def client(server):
    return CmdlyClient(port=server.port)


def call(client, name, arguments=None):
    """One tools/call, answered; ``(text, is_error)`` of the tool result."""
    reply = handle_message({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                            "params": {"name": name, "arguments": arguments or {}}}, client)
    assert reply["id"] == 1 and "result" in reply
    return reply["result"]["content"][0]["text"], reply["result"]["isError"]


def allow(server):
    server.config.update({"agent": {"terminal_control": True}})


# ---------------------------------------------------------------------------
# the protocol
# ---------------------------------------------------------------------------


def test_initialize_answers_the_client_in_its_own_protocol_version(client):
    reply = handle_message({"jsonrpc": "2.0", "id": 7, "method": "initialize",
                            "params": {"protocolVersion": "2025-03-26"}}, client)
    result = reply["result"]
    assert reply["id"] == 7
    assert result["protocolVersion"] == "2025-03-26"
    assert result["serverInfo"]["name"] == "cmdly"
    assert result["capabilities"]["tools"]["listChanged"] is False
    reply = handle_message({"jsonrpc": "2.0", "id": 8, "method": "initialize", "params": {}}, client)
    assert reply["result"]["protocolVersion"] == mcp.PROTOCOL_VERSION


def test_the_protocol_answers_only_what_it_knows(client):
    assert handle_message({"jsonrpc": "2.0", "id": 1, "method": "ping"}, client)["result"] == {}
    reply = handle_message({"jsonrpc": "2.0", "id": 2, "method": "prompts/list"}, client)
    assert reply["error"]["code"] == -32601
    reply = handle_message({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                           "params": {"name": "nope"}}, client)
    assert reply["error"]["code"] == -32602
    # A notification wants no answer, whatever it names.
    assert handle_message({"jsonrpc": "2.0", "method": "notifications/initialized"}, client) is None
    assert handle_message({"jsonrpc": "2.0", "method": "made/up"}, client) is None


def test_the_loop_answers_one_message_per_line(client):
    """serve() is the stdio loop: every line a message, every reply one."""
    out = []
    lines = [
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}),
        "not json at all",
        json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "no/such"}),
    ]
    serve(lines, out.append, client)
    assert len(out) == 3  # the notification is not answered
    assert out[0]["id"] == 1 and out[0]["result"] == {}
    assert out[1]["error"]["code"] == -32700
    assert out[2]["id"] == 2 and out[2]["error"]["code"] == -32601


def test_the_tools_are_listed_with_a_schema_and_the_permission_state(server, client):
    reply = handle_message({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, client)
    tools = {t["name"]: t for t in reply["result"]["tools"]}
    assert tools.keys() == TOOLS
    assert tools["add_button"]["inputSchema"]["type"] == "object"
    # While the switch is off a gated tool says so, so the agent learns what
    # to ask for instead of trying.
    assert "has not allowed" in tools["run_in_terminal"]["description"]
    allow(server)
    reply = handle_message({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, client)
    tools = {t["name"]: t for t in reply["result"]["tools"]}
    assert "has turned on" in tools["run_in_terminal"]["description"]
    assert "has not allowed" not in tools["add_button"]["description"]


# ---------------------------------------------------------------------------
# finding the backend
# ---------------------------------------------------------------------------


def test_the_port_is_read_from_the_instance_locks_record(server, monkeypatch):
    monkeypatch.setattr(mcp.CmdlyClient, "_candidate_ports",
                        lambda self: [server.port])
    assert CmdlyClient().port() == server.port


def test_without_a_backend_the_tools_say_that_instead_of_failing(server, monkeypatch):
    monkeypatch.setattr(mcp.CmdlyClient, "_candidate_ports", lambda self: [])
    text, is_error = call(CmdlyClient(), "status")
    assert is_error and "Cmdly is not running" in text


# ---------------------------------------------------------------------------
# buttons: always allowed
# ---------------------------------------------------------------------------


def test_an_agent_can_add_list_and_remove_buttons(client):
    text, is_error = call(client, "add_button", {"label": "Logs", "command": "journalctl -f"})
    assert not is_error and "Logs" in text and "journalctl -f" in text
    text, _ = call(client, "list_buttons")
    assert "Logs" in text and "System info" in text
    text, is_error = call(client, "remove_button", {"label": "Logs"})
    assert not is_error and "Logs" in text
    text, _ = call(client, "list_buttons")
    assert "Logs" not in text and "System info" in text


def test_an_ssh_button_names_one_of_the_saved_connections(client):
    text, is_error = call(client, "add_button", {"command": "ls", "target": "ssh"})
    assert is_error and "connection" in text
    text, is_error = call(client, "add_button",
                         {"command": "ls", "target": "ssh", "connection": "pi"})
    assert is_error and "no saved connection" in text


def test_a_button_without_a_command_is_refused(client):
    text, is_error = call(client, "add_button", {"label": "Nothing"})
    assert is_error and "command" in text


def test_an_agent_can_update_one_field_of_a_button(client):
    text, is_error = call(client, "update_button",
                         {"id": "b_welcome", "command": "uname -r", "mode": "background"})
    assert not is_error and "uname -r" in text and "Changed: command, mode" in text
    text, _ = call(client, "list_buttons")
    line = [line for line in text.splitlines() if line.startswith("b_welcome")][0]
    assert "System info" in line and "background" in line   # only what was asked changed
    text, is_error = call(client, "update_button", {"id": "b_welcome", "command": " "})
    assert is_error and "without a command" in text
    text, is_error = call(client, "update_button", {"id": "b_nope", "command": "x"})
    assert is_error and "No such button" in text
    text, is_error = call(client, "update_button",
                         {"id": "b_welcome", "target": "ssh", "connection": "pi"})
    assert is_error and "no saved connection" in text


def test_the_computers_are_listed_with_what_uses_them(server, client):
    text, is_error = call(client, "list_computers")
    assert not is_error
    assert "No companion computers are set up." in text
    assert "No SSH connections are saved." in text
    client.post("/api/ssh/connections",
                {"name": "pi", "host": "10.0.0.2", "username": "pi", "password": "raspberry"})
    client.post("/api/config", {"companions": [
        {"id": "c1", "name": "Pi", "host": "10.0.0.2", "type": "ssh", "connection": "pi"}]})
    call(client, "add_button", {"label": "On the Pi", "command": "ls", "target": "ssh",
                                "connection": "pi"})
    text, _ = call(client, "list_computers")
    assert "c1 “Pi”" in text and "10.0.0.2" in text and "connection pi" in text
    assert "pi → pi@10.0.0.2:22" in text and "password" in text and "1 button" in text


def test_the_shelf_is_not_filled_past_its_own_bound(server, client):
    for i in range(24):
        call(client, "add_button", {"command": f"echo {i}"})
    text, is_error = call(client, "add_button", {"command": "echo one too many"})
    assert is_error and "full" in text


# ---------------------------------------------------------------------------
# terminals and power: the person's switch
# ---------------------------------------------------------------------------


def test_without_the_switch_the_terminal_tools_are_refused(server, client):
    for name, args in (("list_terminals", {}), ("run_command", {"command": "x"}),
                       ("power", {"action": "reboot"}), ("press_button", {"label": "x"}),
                       ("ping", {"host": "127.0.0.1"})):
        text, is_error = call(client, name, args)
        assert is_error, name
        assert "Settings → Agent" in text, name


@pytest.mark.skipif(sys.platform == "win32", reason="a pseudo-terminal is POSIX only")
def test_with_the_switch_a_command_runs_in_a_terminal_and_is_read_back(server, client):
    allow(server)
    text, is_error = call(client, "run_in_terminal",
                         {"command": "echo agent-$((40+2))", "wait_s": 6})
    assert not is_error
    assert "agent-42" in text
    # The completion never reaches the agent: the pty's echo of the typed line
    # shows the marker's *text*, but the printf's output — the escape byte —
    # is where the returned text ends.
    assert "\x1b[2K\r__CMDLY_DONE_" not in text
    # The session is one of the page's, under the agent's prefix, and closes.
    text, _ = call(client, "list_terminals")
    assert "agent/main" in text
    text, _ = call(client, "close_terminal", {"name": "main"})
    assert "closed" in text.lower()
    text, is_error = call(client, "read_terminal", {"name": "agent/main"})
    assert is_error and "no terminal" in text


@pytest.mark.skipif(sys.platform == "win32", reason="a pseudo-terminal is POSIX only")
def test_a_terminal_command_is_waited_for_not_merely_waited_out(server, client):
    """A command that finishes after a moment returns with its output — the
    wait looks for the completion, not the clock."""
    allow(server)
    text, is_error = call(client, "run_in_terminal",
                         {"command": "sleep 1 && echo slow-42", "wait_s": 6})
    assert not is_error and "slow-42" in text
    # One that outruns the wait says so instead of pretending it is done.
    text, is_error = call(client, "run_in_terminal",
                         {"command": "sleep 3", "name": "slow", "wait_s": 1})
    assert not is_error and "may still be running" in text
    call(client, "close_terminal", {"name": "slow"})


def test_with_the_switch_a_background_command_runs_here(server, client):
    allow(server)
    text, is_error = call(client, "run_command", {"command": "echo nope; exit 3"})
    assert not is_error
    assert "exit code 3" in text and "nope" in text


def test_power_reaches_the_backends_line_not_the_callers(server, client, monkeypatch):
    allow(server)
    sent = {}

    def run(command, directory=""):
        sent["command"] = command
        return {"ok": True, "exited": True, "code": 0, "output": ""}

    monkeypatch.setattr(server.local, "run", run)
    text, is_error = call(client, "power", {"action": "shutdown"})
    assert not is_error and "shutting down" in text
    assert sent["command"] == mcp.launcher.local_power_line("shutdown")
    text, is_error = call(client, "power", {"action": "explode"})
    assert is_error and "shutdown" in text
    text, is_error = call(client, "power", {"action": "reboot"})
    assert not is_error and "rebooting" in text


def test_power_says_why_a_computer_refused_it(server, client, monkeypatch):
    allow(server)

    def run(command, directory=""):
        return {"ok": False, "exited": True, "code": 1, "output": "shutdown: you must be root"}

    monkeypatch.setattr(server.local, "run", run)
    text, is_error = call(client, "power", {"action": "shutdown"})
    assert is_error and "you must be root" in text


@pytest.mark.skipif(sys.platform == "win32", reason="a pseudo-terminal is POSIX only")
def test_with_the_switch_pressing_a_button_runs_what_the_person_configured(server, client):
    """A press is a press: the line goes into the button's own session, opened
    when it has none — the same shelf row shows it running."""
    allow(server)
    text, is_error = call(client, "press_button", {"id": "b_welcome"})
    assert not is_error and "Pressed" in text and "cmdly/b_welcome" in text
    session = server.ssh.get_session("cmdly/b_welcome")
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and "load average" not in session.snapshot():
        time.sleep(0.05)
    assert "load average" in session.snapshot()   # it really ran the button's command
    text, _ = call(client, "close_terminal", {"name": "cmdly/b_welcome"})
    assert "closed" in text.lower()


def test_pressing_a_background_button_runs_it_once(server, client):
    allow(server)
    call(client, "add_button", {"label": "Press bg", "command": "echo pressed", "mode": "background"})
    text, is_error = call(client, "press_button", {"label": "Press bg"})
    assert not is_error and "Pressed" in text and "pressed" in text
    call(client, "remove_button", {"label": "Press bg"})


def test_ping_says_whether_a_computer_answers(server, client, monkeypatch):
    allow(server)

    class FakePinger:
        available = True

        def ping(self, raw_host, wait_s=2.0):
            if str(raw_host) == "10.0.0.2":
                return {"ok": True, "host": "10.0.0.2", "reachable": True, "rtt_ms": 4.2}
            return {"ok": True, "host": str(raw_host), "reachable": False, "rtt_ms": None}

        def shutdown(self):
            pass

    monkeypatch.setattr(server, "pinger", FakePinger())
    text, is_error = call(client, "ping", {"host": "10.0.0.2"})
    assert not is_error and "10.0.0.2 is up (4.2 ms)" in text
    text, is_error = call(client, "ping", {"host": "10.9.9.9", "wait_ms": 500})
    assert not is_error and "did not answer" in text
    text, is_error = call(client, "ping", {"host": "-bad-"})
    assert is_error and "not an IP address" in text


# ---------------------------------------------------------------------------
# what an agent app should run, and whether it answers
# ---------------------------------------------------------------------------


def test_an_appimage_speaks_with_itself_as_the_mcp_server():
    spec = mcp.mcp_command(env={"APPIMAGE": "/opt/Cmdly.AppImage"})
    assert spec == {"command": ["/opt/Cmdly.AppImage", "mcp"], "env": {}}


def test_a_macos_app_launches_through_its_own_launcher(monkeypatch):
    monkeypatch.setattr(mcp.sys, "platform", "darwin")
    spec = mcp.mcp_command(
        env={}, executable="/x/Cmdly.app/Contents/Frameworks/Python.framework/Versions/3.12/Python")
    assert spec == {"command": ["/x/Cmdly.app/Contents/MacOS/cmdly", "mcp"], "env": {}}


def test_a_checkout_names_its_python_and_its_root():
    spec = mcp.mcp_command(env={}, executable="/usr/bin/python3")
    assert spec["command"][1:] == ["-m", "cmdly", "mcp"]
    assert spec["env"]["PYTHONPATH"] == os.path.dirname(os.path.dirname(mcp.__file__))


def test_the_mcp_server_answers_a_handshake(server, client):
    """The Settings' test button: the very command an agent app would run,
    started once, answered — and nothing left running."""
    spec = client.get("/api/agent/mcp")
    assert spec["command"][-3:] == ["-m", "cmdly", "mcp"]
    assert spec["env"]["PYTHONPATH"]
    result = client.post("/api/agent/mcp/test", {})
    assert result["ok"] is True, result["error"]
    assert result["version"] == mcp.get_version()
    assert {"add_button", "press_button", "power"} <= set(result["tools"])


def test_status_tells_the_agent_where_things_stand(server, client):
    text, is_error = call(client, "status")
    assert not is_error
    assert "does not allow" in text and "Buttons: 1" in text
    allow(server)
    text, _ = call(client, "status")
    assert "ALLOWS" in text
