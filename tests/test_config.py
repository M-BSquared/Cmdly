"""Cmdly's settings file (cmdly/config.py): migration, writes, passwords."""
from __future__ import annotations

import json
import os
import stat

import pytest

from cmdly.config import Config, ConfigError, migrate


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def test_a_first_run_writes_a_starter_shelf(tmp_path):
    cfg = Config(str(tmp_path / "config.json"))
    assert [b["label"] for b in cfg.snapshot()["buttons"]] == ["System info"]
    assert (tmp_path / "config.json").exists()


def test_the_file_is_readable_by_its_owner_only(tmp_path):
    Config(str(tmp_path / "config.json"))
    mode = stat.S_IMODE(os.stat(tmp_path / "config.json").st_mode)
    assert mode == 0o600


def test_the_widget_builds_config_is_migrated(tmp_path):
    path = tmp_path / "config.json"
    write(path, {
        "theme": "blue", "opacity": 0.9,
        "buttons": [{"label": "Go", "command": "go", "target": "ssh", "connection": "pi"}],
        "companions": [{"id": "c1", "name": "Pi", "host": "10.0.0.2", "type": "ssh", "connection": "pi"}],
        "active_companion": "Pi",
        "connections": [{"name": "pi", "host": "10.0.0.2", "username": "pi", "password": "pw"}],
        "window_width": 600, "window_height": 800,
    })
    data = Config(str(path)).snapshot()
    assert data["ui"]["theme"] == "blue"
    assert data["active_companion"] == "c1"
    assert data["window"] == {"width": 600, "height": 800}
    assert data["connections"][0]["password"] == "pw"


def test_an_unreadable_file_is_kept_aside_not_overwritten(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{ broken")
    Config(str(path))
    assert (tmp_path / "config.json.broken").read_text() == "{ broken"


def test_public_never_carries_a_password(tmp_path):
    path = tmp_path / "config.json"
    write(path, {"connections": [{"name": "pi", "host": "h", "password": "pw"}]})
    pub = Config(str(path)).public()
    assert "pw" not in json.dumps(pub)
    assert "password" not in pub["connections"][0]
    assert pub["connections"][0]["has_password"] is True


def test_update_merges_ui_and_normalizes(tmp_path):
    cfg = Config(str(tmp_path / "config.json"))
    out = cfg.update({"ui": {"theme": "pink", "bogus": 1}})
    assert out["ui"]["theme"] == "pink"
    assert "bogus" not in out["ui"]
    assert out["ui"]["frosted_terminals"] is True
    out = cfg.update({"ui": {"theme": "no-such-theme"}})
    assert out["ui"]["theme"] == "blue"


def test_update_refuses_a_wrong_shape(tmp_path):
    cfg = Config(str(tmp_path / "config.json"))
    with pytest.raises(ConfigError):
        cfg.update({"buttons": "x"})


def test_a_save_without_a_password_keeps_the_stored_one(tmp_path):
    cfg = Config(str(tmp_path / "config.json"))
    cfg.upsert_connection({"name": "pi", "host": "10.0.0.2", "username": "pi", "password": "pw"})
    cfg.upsert_connection({"name": "pi", "host": "10.0.0.3", "username": "pi"})
    assert cfg.connection("pi")["password"] == "pw"
    assert cfg.connection("pi")["host"] == "10.0.0.3"


def test_a_rename_follows_into_buttons_and_companions(tmp_path):
    cfg = Config(str(tmp_path / "config.json"))
    cfg.upsert_connection({"name": "pi", "host": "10.0.0.2", "username": "pi"})
    cfg.update({"buttons": [{"command": "x", "target": "ssh", "connection": "pi"}],
                "companions": [{"host": "10.0.0.2", "type": "ssh", "connection": "pi"}]})
    cfg.upsert_connection({"name": "pi4", "original_name": "pi", "host": "10.0.0.2", "username": "pi"})
    data = cfg.snapshot()
    assert data["buttons"][0]["connection"] == "pi4"
    assert data["companions"][0]["connection"] == "pi4"


def test_a_rename_onto_another_connection_is_refused(tmp_path):
    cfg = Config(str(tmp_path / "config.json"))
    cfg.upsert_connection({"name": "a", "host": "h1"})
    cfg.upsert_connection({"name": "b", "host": "h2"})
    with pytest.raises(ConfigError):
        cfg.upsert_connection({"name": "b", "original_name": "a", "host": "h1"})


def test_a_bad_host_or_port_is_refused(tmp_path):
    cfg = Config(str(tmp_path / "config.json"))
    with pytest.raises(ConfigError):
        cfg.upsert_connection({"name": "x", "host": "-oProxyCommand=evil"})
    with pytest.raises(ConfigError):
        cfg.upsert_connection({"name": "x", "host": "h", "port": 70000})


def test_window_size_is_bounded(tmp_path):
    cfg = Config(str(tmp_path / "config.json"))
    cfg.set_window(10, 10)
    assert cfg.window is None
    cfg.set_window(700, 900)
    assert cfg.window == {"width": 700, "height": 900}


def test_migrate_tolerates_anything():
    for junk in (None, [], "x", {"buttons": "x", "companions": 5, "ui": []}):
        data = migrate(junk)
        assert data["buttons"] == [] and data["companions"] == []


def test_deleting_a_connection_takes_its_shown_computer_with_it(tmp_path):
    cfg = Config(str(tmp_path / "config.json"))
    cfg.upsert_connection({"name": "pi", "host": "10.0.0.2", "username": "pi"})
    cfg.upsert_connection({"name": "nas", "host": "10.0.0.3", "username": "root"})
    cfg.update({"companions": [
        {"id": "c1", "name": "pi", "host": "10.0.0.2", "type": "ssh", "connection": "pi"},
        {"id": "c2", "name": "nas", "host": "10.0.0.3", "type": "ssh", "connection": "nas"},
        {"id": "c3", "name": "router", "host": "10.0.0.1", "type": "ping"},
    ], "active_companion": "c1"})
    cfg.remove_connection("pi")
    data = cfg.snapshot()
    assert [c["id"] for c in data["companions"]] == ["c2", "c3"]
    assert data["active_companion"] == "c2"


def test_editing_a_connection_reaches_buttons_and_computers(tmp_path):
    cfg = Config(str(tmp_path / "config.json"))
    cfg.upsert_connection({"name": "pi", "host": "10.0.0.2", "username": "pi"})
    cfg.update({
        "buttons": [{"id": "b1", "label": "Go", "command": "go", "target": "ssh", "connection": "pi"}],
        "companions": [{"id": "c1", "name": "pi", "host": "10.0.0.2", "type": "ssh", "connection": "pi"}],
    })
    cfg.upsert_connection({"name": "rover", "original_name": "pi", "host": "10.0.0.9", "username": "pi"})
    data = cfg.snapshot()
    assert data["buttons"][0]["connection"] == "rover"
    companion = data["companions"][0]
    assert (companion["connection"], companion["name"], companion["host"]) == ("rover", "rover", "10.0.0.9")
