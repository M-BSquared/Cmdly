"""Settings export and import: the bundle format and its two endpoints.

Covers ``cmdly/settings_bundle.py`` (sections, redaction, parsing, the merge
that keeps stored passwords) and ``POST /api/settings/export`` /
``POST /api/settings/import`` on a handler with its responses captured.
"""
from __future__ import annotations

import json
import os
import sys
from types import SimpleNamespace
from typing import Any

import pytest

from cmdly import config as config_mod
from cmdly import settings_bundle
from cmdly.config import Config
from cmdly.routes.settings import safe_filename
from cmdly.server import Handler


def _setup() -> dict[str, Any]:
    """A whole config with one of everything, a password among it."""
    cfg = config_mod.migrate({
        "buttons": [
            {"id": "b1", "label": "Flight", "target": "ssh", "connection": "pi",
             "directory": "/opt/flight", "command": "python main.py"},
            {"id": "b2", "label": "Logs", "target": "local", "command": "tail -f x.log"},
        ],
        "companions": [{"id": "c1", "name": "Pi", "host": "10.0.0.2", "type": "ssh",
                        "connection": "pi"}],
        "active_companion": "c1",
        "connections": [{"name": "pi", "host": "10.0.0.2", "port": 22,
                         "username": "pi", "password": "ssh-secret"}],
        "ui": {"theme": "orange", "frosted_window": False},
    })
    cfg["window"] = {"width": 900, "height": 700}
    return cfg


def _secrets_in(text: str) -> bool:
    return "ssh-secret" in text


# ---------------------------------------------------------------------------
# settings_bundle
# ---------------------------------------------------------------------------

def test_every_config_key_belongs_to_exactly_one_section():
    """A new config key without a section would silently never be exported."""
    for key in config_mod.migrate({}):
        owners = [s for s, keys in settings_bundle.SECTIONS.items() if key in keys]
        if key in settings_bundle.EXCLUDED_KEYS:
            assert owners == [], key
        else:
            assert len(owners) == 1, f"{key} is in {owners or 'no section'}"


def test_build_leaves_the_passwords_out_by_default():
    bundle = settings_bundle.build(_setup())
    assert not _secrets_in(json.dumps(bundle))
    assert bundle["secrets"] is False
    assert bundle["kind"] == settings_bundle.KIND
    # The connection itself travels, only the password is gone.
    assert bundle["config"]["connections"][0]["host"] == "10.0.0.2"


def test_build_carries_the_passwords_when_asked():
    bundle = settings_bundle.build(_setup(), include_secrets=True)
    assert _secrets_in(json.dumps(bundle))
    assert bundle["secrets"] is True


def test_build_never_carries_the_window_size():
    assert "window" not in settings_bundle.build(_setup())["config"]


def test_build_does_not_mutate_the_config_it_redacts():
    config = _setup()
    settings_bundle.build(config)
    assert config["connections"][0]["password"] == "ssh-secret"


def test_build_carries_only_the_chosen_sections():
    bundle = settings_bundle.build(_setup(), sections=["appearance", "buttons"])
    assert bundle["sections"] == ["buttons", "appearance"]
    assert set(bundle["config"]) == {"buttons", "ui", "updates"}


def test_build_keeps_only_cmdly_string_entries_from_the_browser():
    bundle = settings_bundle.build({}, browser={"cmdly.x": "1", "other.key": "x", "cmdly.bad": 3})
    assert bundle["browser"] == {"cmdly.x": "1"}


@pytest.mark.parametrize("data", [None, [], {"kind": "other"}, {"kind": "cmdly-settings"},
                                  {"unrelated": 1}])
def test_parse_rejects_what_is_not_a_bundle(data):
    with pytest.raises(ValueError):
        settings_bundle.parse(data)


def test_parse_refuses_a_newer_format():
    bundle = settings_bundle.build({})
    bundle["format"] = settings_bundle.FORMAT + 1
    with pytest.raises(ValueError, match="newer"):
        settings_bundle.parse(bundle)


def test_parse_refuses_a_file_that_does_not_say_what_it_carries():
    bundle = settings_bundle.build({})
    del bundle["sections"]
    with pytest.raises(ValueError, match="which settings"):
        settings_bundle.parse(bundle)


def test_parse_round_trips_a_built_bundle():
    bundle = settings_bundle.build(_setup(), browser={"cmdly.x": "{}"})
    parsed = settings_bundle.parse(json.loads(json.dumps(bundle)))
    assert parsed["sections"] == list(settings_bundle.SECTIONS)
    assert parsed["browser"] == {"cmdly.x": "{}"}
    assert parsed["config"]["ui"]["theme"] == "orange"


def test_parse_ignores_config_keys_of_sections_the_file_does_not_carry():
    bundle = settings_bundle.build(_setup(), sections=["appearance"])
    bundle["config"]["buttons"] = [{"command": "rm -rf ~"}]
    bundle["config"]["window"] = {"width": 500, "height": 600}
    assert set(settings_bundle.parse(bundle)["config"]) == {"ui", "updates"}


def test_parse_reads_a_setup_from_the_first_cmdly_export():
    legacy = {"cmdly": "2026.10.05", "buttons": _setup()["buttons"],
              "connections": [{"name": "pi", "host": "10.0.0.2", "username": "pi"}]}
    parsed = settings_bundle.parse(legacy)
    assert parsed["sections"] == ["buttons", "connections"]
    assert parsed["version"] == "2026.10.05"
    assert parsed["secrets"] is False
    assert "password" not in parsed["config"]["connections"][0]


def test_parse_reads_the_pyside_builds_spellings():
    parsed = settings_bundle.parse({"theme": "green",
                                    "companion": {"name": "Pi", "host": "10.0.0.9"}})
    assert parsed["sections"] == ["companions", "appearance"]
    assert parsed["config"]["ui"]["theme"] == "green"
    assert parsed["config"]["companions"][0]["host"] == "10.0.0.9"


def test_merge_leaves_sections_not_chosen_alone():
    current = _setup()
    imported = dict(current, buttons=[], ui={"theme": "pink"})
    out = settings_bundle.merge(current, imported, {"appearance"}, secrets=True)
    assert out["ui"]["theme"] == "pink"
    assert [b["id"] for b in out["buttons"]] == ["b1", "b2"]


def test_merge_resets_a_key_the_file_leaves_out():
    current = _setup()
    imported = {k: v for k, v in current.items() if k != "ui"}
    out = settings_bundle.merge(current, imported, {"appearance"}, secrets=True)
    assert out["ui"] == config_mod.DEFAULT_UI


def test_merge_keeps_the_window_size_of_this_computer():
    current = _setup()
    imported = dict(current, window={"width": 1200, "height": 900})
    out = settings_bundle.merge(current, imported, set(settings_bundle.SECTIONS), secrets=True)
    assert out["window"] == {"width": 900, "height": 700}


def test_merge_keeps_stored_passwords_for_unchanged_connections():
    current = _setup()
    imported = settings_bundle.redact(current)
    out = settings_bundle.merge(current, imported, set(settings_bundle.SECTIONS), secrets=False)
    assert out["connections"][0]["password"] == "ssh-secret"


def test_merge_never_hands_a_stored_password_to_another_host():
    current = _setup()
    imported = settings_bundle.redact(current)
    imported["connections"][0]["host"] = "10.9.9.9"
    out = settings_bundle.merge(current, imported, set(settings_bundle.SECTIONS), secrets=False)
    assert out["connections"][0]["password"] == ""


def test_merge_never_hands_a_stored_password_to_another_user():
    current = _setup()
    imported = settings_bundle.redact(current)
    imported["connections"][0]["username"] = "root"
    out = settings_bundle.merge(current, imported, set(settings_bundle.SECTIONS), secrets=False)
    assert out["connections"][0]["password"] == ""


def test_merge_with_secrets_takes_the_file_as_it_is():
    current = _setup()
    imported = settings_bundle.redact(current)
    out = settings_bundle.merge(current, imported, set(settings_bundle.SECTIONS), secrets=True)
    assert out["connections"][0]["password"] == ""


def test_merge_points_an_ssh_companion_at_its_connections_host():
    current = _setup()
    imported = {"connections": [{"name": "pi", "host": "10.0.0.77", "username": "pi"}]}
    out = settings_bundle.merge(current, imported, {"connections"}, secrets=False)
    assert out["companions"][0]["host"] == "10.0.0.77"


def test_merge_normalizes_what_the_file_says():
    current = _setup()
    imported = {"buttons": [{"label": "no command"}, "junk", {"command": "ls"}],
                "ui": {"theme": "neon", "vibrancy": "yes"}}
    out = settings_bundle.merge(current, imported, {"buttons", "appearance"}, secrets=True)
    assert [b["command"] for b in out["buttons"]] == ["ls"]
    assert out["ui"]["theme"] == config_mod.DEFAULT_THEME
    # "vibrancy" is the older Cmdly's name for the frosted window.
    assert out["ui"]["frosted_window"] is True


def test_missing_connections_names_what_the_buttons_use_but_nobody_saved():
    cfg = _setup()
    cfg["connections"] = []
    assert settings_bundle.missing_connections(cfg) == ["pi"]
    assert settings_bundle.missing_connections(_setup()) == []


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def _handler(tmp_path, data: dict[str, Any] | None = None):
    path = str(tmp_path / "config.json")
    if data is not None:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
    handler = object.__new__(Handler)
    handler.server = SimpleNamespace(config=Config(path))
    responses: list[tuple[dict, int]] = []
    handler._send_json = lambda body, status=200: responses.append((body, status))  # type: ignore[method-assign]
    return handler, responses


def _export(handler, responses, tmp_path, **payload: Any) -> dict[str, Any]:
    body = {"dir": str(tmp_path / "out"), "filename": "setup.json"}
    body.update(payload)
    handler._api_settings_export(body)
    data, status = responses[-1]
    assert status == 200, data
    return data


def _written(tmp_path) -> dict[str, Any]:
    return json.loads((tmp_path / "out" / "setup.json").read_text(encoding="utf-8"))


def test_export_writes_the_file_and_never_echoes_a_password(tmp_path):
    handler, responses = _handler(tmp_path, _setup())
    data = _export(handler, responses, tmp_path, include_secrets=True,
                   browser={"cmdly.x": "1"})
    assert not _secrets_in(json.dumps(data))
    assert data["path"] == str(tmp_path / "out" / "setup.json")
    written = _written(tmp_path)
    assert written["kind"] == "cmdly-settings"
    assert written["browser"] == {"cmdly.x": "1"}
    assert _secrets_in(json.dumps(written))


def test_export_without_passwords_writes_none(tmp_path):
    handler, responses = _handler(tmp_path, _setup())
    _export(handler, responses, tmp_path)
    assert not _secrets_in((tmp_path / "out" / "setup.json").read_text(encoding="utf-8"))


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_export_file_is_owner_only(tmp_path):
    handler, responses = _handler(tmp_path, _setup())
    _export(handler, responses, tmp_path, include_secrets=True)
    assert os.stat(tmp_path / "out" / "setup.json").st_mode & 0o077 == 0


def test_export_writes_only_the_chosen_sections(tmp_path):
    handler, responses = _handler(tmp_path, _setup())
    data = _export(handler, responses, tmp_path, sections=["buttons"])
    assert data["sections"] == ["buttons"]
    assert set(_written(tmp_path)["config"]) == {"buttons"}


@pytest.mark.parametrize("payload", [
    {"include_secrets": "yes"},
    {"sections": []},
    {"sections": "buttons"},
    {"browser": []},
])
def test_export_refuses_bad_input_without_writing(tmp_path, payload):
    handler, responses = _handler(tmp_path, _setup())
    handler._api_settings_export({"dir": str(tmp_path / "out"), **payload})
    assert responses[-1][1] == 400
    assert not (tmp_path / "out").exists()


def test_export_keeps_the_file_inside_the_chosen_folder(tmp_path):
    handler, responses = _handler(tmp_path, _setup())
    data = _export(handler, responses, tmp_path, filename="../../escape")
    assert data["path"] == str(tmp_path / "out" / "escape.json")


def test_safe_filename():
    assert safe_filename("a/b/c.json", "x.json") == "c.json"
    assert safe_filename("..", "x.json") == "x.json"
    assert safe_filename(42, "x.json") == "x.json"
    assert safe_filename("setup", "x.json") == "setup.json"


def test_export_target_names_a_folder_and_a_file(tmp_path):
    handler, responses = _handler(tmp_path, _setup())
    handler._api_settings_export_target()
    data, _status = responses[-1]
    assert os.path.isdir(data["dir"])
    assert data["filename"].startswith("cmdly-settings_") and data["filename"].endswith(".json")


def test_import_round_trips_an_export_onto_a_fresh_computer(tmp_path):
    source_dir = tmp_path / "a"
    source_dir.mkdir()
    source, responses = _handler(source_dir, _setup())
    _export(source, responses, tmp_path, include_secrets=True)
    bundle = _written(tmp_path)

    target_dir = tmp_path / "b"
    target_dir.mkdir()
    target, responses = _handler(target_dir)
    target._api_settings_import({"bundle": bundle})
    data, status = responses[-1]
    assert status == 200, data
    assert not _secrets_in(json.dumps(data))
    assert data["counts"] == {"buttons": 2, "companions": 1, "connections": 1}

    got = target.app.config.snapshot()
    want = source.app.config.snapshot()
    for key in settings_bundle.SECTIONS["buttons"] + settings_bundle.SECTIONS["companions"] \
            + settings_bundle.SECTIONS["connections"] + settings_bundle.SECTIONS["appearance"]:
        assert got[key] == want[key], key
    on_disk = json.loads((target_dir / "config.json").read_text(encoding="utf-8"))
    assert on_disk["connections"][0]["password"] == "ssh-secret"
    assert on_disk["ui"]["theme"] == "orange"


def test_import_only_touches_the_chosen_sections(tmp_path):
    handler, responses = _handler(tmp_path, config_mod.migrate({
        "buttons": [{"id": "mine", "command": "ls"}],
    }))
    handler._api_settings_import({"bundle": settings_bundle.build(_setup()),
                                  "sections": ["appearance"]})
    assert responses[-1][1] == 200
    cfg = handler.app.config.snapshot()
    assert cfg["ui"]["theme"] == "orange"
    assert [b["id"] for b in cfg["buttons"]] == ["mine"]
    assert cfg["connections"] == []


def test_a_partial_file_never_resets_the_sections_it_does_not_carry(tmp_path):
    handler, responses = _handler(tmp_path, _setup())
    bundle = settings_bundle.build(config_mod.migrate({"ui": {"theme": "pink"}}),
                                   sections=["appearance"])
    handler._api_settings_import({"bundle": bundle})
    data, status = responses[-1]
    assert status == 200, data
    assert data["sections"] == ["appearance"]
    cfg = handler.app.config.snapshot()
    assert cfg["ui"]["theme"] == "pink"
    assert len(cfg["buttons"]) == 2
    assert cfg["connections"][0]["password"] == "ssh-secret"


def test_import_without_passwords_keeps_the_stored_ones(tmp_path):
    handler, responses = _handler(tmp_path, _setup())
    handler._api_settings_import({"bundle": settings_bundle.build(_setup())})
    assert responses[-1][1] == 200
    assert handler.app.config.connection("pi")["password"] == "ssh-secret"


def test_import_says_which_connections_are_missing(tmp_path):
    handler, responses = _handler(tmp_path, config_mod.migrate({}))
    handler._api_settings_import({"bundle": settings_bundle.build(_setup(), sections=["buttons"])})
    data, status = responses[-1]
    assert status == 200
    assert data["missing_connections"] == ["pi"]
    assert any('"pi"' in w for w in data["warnings"])


def test_import_of_only_sections_the_file_lacks_is_refused(tmp_path):
    handler, responses = _handler(tmp_path, _setup())
    before = (tmp_path / "config.json").read_text(encoding="utf-8")
    bundle = settings_bundle.build(_setup(), sections=["appearance"])
    handler._api_settings_import({"bundle": bundle, "sections": ["connections"]})
    assert responses[-1][1] == 400
    assert (tmp_path / "config.json").read_text(encoding="utf-8") == before


@pytest.mark.parametrize("payload", [
    {"bundle": {"kind": "something-else"}},
    {"bundle": settings_bundle.build({}), "sections": "buttons"},
    {"bundle": settings_bundle.build({}), "sections": []},
])
def test_import_rejects_bad_input_without_writing(tmp_path, payload):
    handler, responses = _handler(tmp_path, _setup())
    before = (tmp_path / "config.json").read_text(encoding="utf-8")
    handler._api_settings_import(payload)
    assert responses[-1][1] == 400
    assert (tmp_path / "config.json").read_text(encoding="utf-8") == before


def test_import_never_answers_with_a_password(tmp_path):
    handler, responses = _handler(tmp_path)
    handler._api_settings_import({"bundle": settings_bundle.build(_setup(), include_secrets=True)})
    data, status = responses[-1]
    assert status == 200
    assert not _secrets_in(json.dumps(data))
    assert data["config"]["connections"][0]["has_password"] is True
