"""Tests for the GitHub-release update check (cmdly/update_check.py) and its
``/api/update*`` endpoints in cmdly/server.py.

Three things drive the coverage here:

* **Nothing may reach the network.** Every test stubs ``urlopen`` or the
  checker itself, and every cache lives under ``tmp_path``.
* **No repository, no check.** :data:`cmdly.update_check.REPO` is empty until
  Cmdly is published; the checker must then ask nothing, store nothing and
  report no error.
* **False positives are the real failure mode.** An update notice for a
  version that does not exist, or one that keeps re-appearing after it was
  dismissed, is worse than no notice — so the version comparison, the
  draft/prerelease filter, and the "skipped" path are pinned hard.

Handler-level helpers construct a ``Handler`` via ``object.__new__`` and stub
``_send_json``, so no socket is opened.
"""
from __future__ import annotations

import json
import types
import urllib.error
from typing import Any

import pytest

from cmdly import update_check
from cmdly.config import Config
from cmdly.update_check import (
    UpdateChecker,
    _pick_latest,
    configured_repo,
    is_newer,
    parse_version,
    releases_page_url,
)
from cmdly.version import get_version

REPO = "example-owner/cmdly"
RELEASES_PAGE = releases_page_url(REPO)


# ---------------------------------------------------------------------------
# Version parsing / comparison
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("2000.09.27", (2000, 9, 27)),
    ("v2000.09.27", (2000, 9, 27)),
    ("  v2000.10.02  ", (2000, 10, 2)),
    ("1.16", (1, 16)),
    ("", None),
    (None, None),
    ("nightly", None),
    ("v2000.09.27-rc1", None),
    ("0.0.0-unknown", None),
    ("2000.09.x", None),
])
def test_parse_version(text: Any, expected: tuple | None) -> None:
    assert parse_version(text) == expected


@pytest.mark.parametrize("candidate,current,expected", [
    ("2000.10.02", "2000.09.29", True),
    ("2001.01.01", "2000.12.31", True),
    ("2000.09.30", "2000.09.29", True),
    # Equal is not newer: a machine on the current release must stay quiet.
    ("2000.09.29", "2000.09.29", False),
    ("2000.09.27", "2000.09.29", False),
    ("1999.12.31", "2000.01.01", False),
    # Zero padding is cosmetic; the comparison is on integers.
    ("2000.9.30", "2000.09.29", True),
    # Unparsable on either side means "no update", never a guess.
    ("nightly", "2000.09.29", False),
    ("2000.10.02", "0.0.0-unknown", False),
    ("", "2000.09.29", False),
])
def test_is_newer(candidate: str, current: str, expected: bool) -> None:
    assert is_newer(candidate, current) is expected


def test_the_running_version_parses() -> None:
    """The version the app actually reports must parse, or nothing ever works."""
    assert parse_version(get_version()) is not None


# ---------------------------------------------------------------------------
# The repository setting
# ---------------------------------------------------------------------------

def test_the_repository_is_not_set_yet() -> None:
    """Placeholder until Cmdly is published: the check is off by construction."""
    assert update_check.REPO == ""
    assert configured_repo() == ""


@pytest.mark.parametrize("repo,expected", [
    ("example-owner/cmdly", "example-owner/cmdly"),
    ("  example-owner/cmdly  ", "example-owner/cmdly"),
    ("", ""),
    (None, ""),
    ("cmdly", ""),
    ("a/b/c", ""),
    ("owner/..", ""),
    ("https://evil.example/x", ""),
    ("owner/name?x=1", ""),
    ("-owner/name", ""),
])
def test_configured_repo_accepts_only_owner_slash_name(repo: Any, expected: str) -> None:
    assert configured_repo(repo if repo is not None else "") == expected


def test_without_a_repository_nothing_is_fetched_or_stored(tmp_path, no_network) -> None:
    calls = no_network(error=AssertionError("no repository, no request"))
    checker = UpdateChecker(state_dir=str(tmp_path), repo="")

    status = checker.check()
    forced = checker.check(force=True)

    assert calls == []
    assert not (tmp_path / "update.json").exists(), "and no cache file appears"
    for s in (status, forced):
        assert s["configured"] is False
        assert s["update_available"] is False
        assert s["error"] == "", "an unset repository is not a failure"
        assert s["url"] == ""
        assert s["current"] == get_version()


def test_the_default_checker_follows_the_module_constant(tmp_path, no_network, monkeypatch) -> None:
    no_network([_release("v2000.10.02")])
    checker = UpdateChecker(state_dir=str(tmp_path))
    assert checker.check()["configured"] is False

    monkeypatch.setattr(update_check, "REPO", REPO)
    status = checker.check()
    assert status["configured"] is True
    assert status["latest"] == "2000.10.02"


def test_a_cache_stored_for_another_repository_is_ignored(tmp_path, no_network) -> None:
    calls = no_network([_release("v2000.10.02")])
    (tmp_path / "update.json").write_text(json.dumps({
        "repo": "someone-else/thing", "checked_at": 9e12,
        "latest": {"tag": "v2999.01.01", "version": "2999.01.01"}, "error": "",
    }))
    checker = UpdateChecker(state_dir=str(tmp_path), repo=REPO)

    assert checker.cached_status()["latest"] == ""
    assert checker.check()["latest"] == "2000.10.02"
    assert len(calls) == 1


# ---------------------------------------------------------------------------
# Release payload reduction
# ---------------------------------------------------------------------------

def _release(tag: str, **kw: Any) -> dict[str, Any]:
    base = {
        "tag_name": tag,
        "name": f"Cmdly {tag}",
        "draft": False,
        "prerelease": False,
        "published_at": "2026-10-02T09:00:00Z",
        "body": "notes",
        "assets": [],
    }
    base.update(kw)
    return base


def test_pick_latest_takes_the_newest_stable_release() -> None:
    latest = _pick_latest([
        _release("v2000.09.27"),
        _release("v2000.10.02"),
        _release("v2000.09.30"),
    ], REPO)
    assert latest is not None
    assert latest["version"] == "2000.10.02"


def test_pick_latest_ignores_the_order_github_returned() -> None:
    latest = _pick_latest([_release("v2000.09.01"), _release("v2000.11.09")], REPO)
    assert latest["version"] == "2000.11.09"


def test_pick_latest_skips_drafts_and_prereleases() -> None:
    latest = _pick_latest([
        _release("v2001.01.01", draft=True),
        _release("v2000.12.01", prerelease=True),
        _release("v2000.10.02"),
    ], REPO)
    assert latest["version"] == "2000.10.02"


def test_pick_latest_skips_unparsable_tags() -> None:
    latest = _pick_latest([_release("nightly"), _release("v2000.10.02")], REPO)
    assert latest["version"] == "2000.10.02"


def test_pick_latest_keeps_calver_zero_padding() -> None:
    """"2000.09.07", not "2000.9.7" — the dismissal match is a string compare."""
    latest = _pick_latest([_release("v2000.09.07")], REPO)
    assert latest["version"] == "2000.09.07"


def test_pick_latest_returns_none_for_junk() -> None:
    assert _pick_latest(None, REPO) is None
    assert _pick_latest({"message": "rate limited"}, REPO) is None
    assert _pick_latest([], REPO) is None
    assert _pick_latest(["not a dict", 7], REPO) is None


def test_release_url_is_derived_not_taken_from_the_payload() -> None:
    latest = _pick_latest([_release(
        "v2000.10.02",
        html_url="https://evil.example/pwn",
        url="https://evil.example/pwn",
    )], REPO)
    assert latest["url"] == f"https://github.com/{REPO}/releases/tag/v2000.10.02"
    assert "evil.example" not in json.dumps(latest)


def test_notes_are_truncated() -> None:
    latest = _pick_latest([_release(
        "v2000.10.02", body="x" * (update_check.MAX_NOTES_CHARS + 500))], REPO)
    assert len(latest["notes"]) == update_check.MAX_NOTES_CHARS


def test_assets_are_coerced_not_trusted() -> None:
    latest = _pick_latest([_release("v2000.10.02", assets=[
        {"name": "app.dmg", "size": "12"},
        "not a dict",
        {"name": None, "size": None},
        {"name": "odd", "size": "huge"},
    ])], REPO)
    assert latest["assets"] == [
        {"name": "app.dmg", "size": 12},
        {"name": "", "size": 0},
        {"name": "odd", "size": 0},
    ]


# ---------------------------------------------------------------------------
# UpdateChecker: cache + offline behaviour
# ---------------------------------------------------------------------------

class _FakeResponse:
    def __init__(self, payload: Any) -> None:
        self._body = json.dumps(payload).encode("utf-8")

    def read(self, size: int | None = None) -> bytes:
        return self._body if size is None else self._body[:size]

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *_args: Any) -> bool:
        return False


@pytest.fixture
def no_network(monkeypatch: pytest.MonkeyPatch):
    """Make every urlopen a controlled fake; fail loudly on an unstubbed call."""
    calls: list[str] = []

    def _install(payload: Any = None, error: Exception | None = None):
        def fake_urlopen(request, timeout=None):  # noqa: ANN001
            calls.append(getattr(request, "full_url", str(request)))
            if error is not None:
                raise error
            return _FakeResponse(payload)
        monkeypatch.setattr("cmdly.update_check.urllib.request.urlopen", fake_urlopen)
        return calls

    _install(error=AssertionError("unstubbed network access"))
    return _install


def _checker(tmp_path) -> UpdateChecker:
    return UpdateChecker(state_dir=str(tmp_path), repo=REPO)


def test_check_fetches_stores_and_reports(tmp_path, no_network) -> None:
    calls = no_network([_release("v2000.10.02")])

    status = _checker(tmp_path).check()

    assert calls == [f"https://api.github.com/repos/{REPO}/releases?per_page=10"]
    assert status["configured"] is True
    assert status["latest"] == "2000.10.02"
    assert status["error"] == ""
    assert status["current"] == get_version()
    assert (tmp_path / "update.json").is_file()


def test_check_reuses_the_cache_instead_of_refetching(tmp_path, no_network) -> None:
    calls = no_network([_release("v2000.10.02")])
    checker = _checker(tmp_path)

    checker.check()
    checker.check()
    checker.check()

    assert len(calls) == 1, "a fresh cache must not be re-fetched"


def test_refresh_forces_a_fetch(tmp_path, no_network) -> None:
    calls = no_network([_release("v2000.10.02")])
    checker = _checker(tmp_path)

    checker.check()
    checker.check(force=True)

    assert len(calls) == 2


def test_stale_cache_is_refetched(tmp_path, no_network) -> None:
    calls = no_network([_release("v2000.10.02")])
    checker = _checker(tmp_path)

    checker.check()
    cached = json.loads((tmp_path / "update.json").read_text())
    cached["checked_at"] -= update_check.CHECK_INTERVAL_S + 1
    (tmp_path / "update.json").write_text(json.dumps(cached))

    checker.check()
    assert len(calls) == 2


def test_a_cache_from_the_future_is_refetched(tmp_path, no_network) -> None:
    """A clock that moved backwards must not pin the check as fresh forever."""
    import time
    calls = no_network([_release("v2000.10.02")])

    (tmp_path / "update.json").write_text(json.dumps({
        "repo": REPO, "checked_at": time.time() + 10_000, "latest": None, "error": "",
    }))
    _checker(tmp_path).check()
    assert len(calls) == 1


def test_offline_check_never_raises_and_keeps_the_cached_release(tmp_path, no_network) -> None:
    no_network([_release("v2000.10.02")])
    checker = _checker(tmp_path)
    assert checker.check()["latest"] == "2000.10.02"

    no_network(error=urllib.error.URLError("no route to host"))
    status = checker.check(force=True)

    assert status["latest"] == "2000.10.02", "the last known release survives"
    assert status["error"], "and the failure is reported, not hidden"


def test_a_failed_check_backs_off_instead_of_retrying_every_call(tmp_path, no_network) -> None:
    calls = no_network(error=urllib.error.URLError("offline"))
    checker = _checker(tmp_path)

    checker.check()
    checker.check()
    checker.check()

    assert len(calls) == 1, "a failed attempt is cached too, so it backs off"


def test_a_failed_check_retries_sooner_than_a_successful_one(tmp_path, no_network) -> None:
    calls = no_network(error=urllib.error.URLError("offline"))
    checker = _checker(tmp_path)
    checker.check()

    cached = json.loads((tmp_path / "update.json").read_text())
    cached["checked_at"] -= update_check.RETRY_INTERVAL_S + 1
    (tmp_path / "update.json").write_text(json.dumps(cached))

    checker.check()
    assert len(calls) == 2


def test_an_oversized_payload_is_refused(tmp_path, monkeypatch) -> None:
    class _Huge:
        def read(self, size=None):  # noqa: ANN001
            return b"x" * (update_check.MAX_PAYLOAD_BYTES + 1)

        def __enter__(self): return self
        def __exit__(self, *_a): return False

    monkeypatch.setattr("cmdly.update_check.urllib.request.urlopen",
                        lambda *a, **k: _Huge())
    latest, error = _checker(tmp_path).fetch()
    assert latest is None
    assert error


def test_a_corrupt_cache_file_is_survivable(tmp_path, no_network) -> None:
    (tmp_path / "update.json").write_text("{ not json")
    no_network([_release("v2000.10.02")])
    assert _checker(tmp_path).check()["latest"] == "2000.10.02"


def test_cached_status_touches_no_network(tmp_path, no_network) -> None:
    calls = no_network(error=AssertionError("cached_status must not fetch"))
    status = _checker(tmp_path).cached_status()
    assert calls == []
    assert status["update_available"] is False
    assert status["url"] == RELEASES_PAGE


# ---------------------------------------------------------------------------
# The cache file is not a source of URLs
# ---------------------------------------------------------------------------

def test_a_tampered_cache_cannot_name_its_own_release_page(tmp_path) -> None:
    """The URL is rebuilt from the tag on the way OUT, not only on the way in.

    ``POST /api/update/open`` passes that string to the system browser, which
    would make ~/.cmdly/update.json a place to plant a link.
    """
    (tmp_path / "update.json").write_text(json.dumps({
        "repo": REPO,
        "checked_at": 1,
        "latest": {
            "tag": "v2000.10.02",
            "version": "2000.10.02",
            "name": "Update",
            "url": "https://evil.example/pwn",
        },
        "error": "",
    }))
    status = _checker(tmp_path).cached_status()
    assert status["url"] == f"https://github.com/{REPO}/releases/tag/v2000.10.02"
    assert "evil.example" not in json.dumps(status)


def test_a_cache_with_a_junk_tag_falls_back_to_the_releases_index(tmp_path) -> None:
    for tag in ("../../../etc", "v1 onmouseover=x", "javascript:alert(1)", ""):
        (tmp_path / "update.json").write_text(json.dumps({
            "repo": REPO,
            "checked_at": 1,
            "latest": {"tag": tag, "version": "2000.10.02", "name": "x"},
            "error": "",
        }))
        assert _checker(tmp_path).cached_status()["url"] == RELEASES_PAGE, tag


def test_no_cache_at_all_still_points_at_the_releases_page(tmp_path) -> None:
    assert _checker(tmp_path).cached_status()["url"] == RELEASES_PAGE


# ---------------------------------------------------------------------------
# open_url
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("url", [
    "file:///etc/passwd", "javascript:alert(1)", "ssh://host", "", "x-system-settings:",
])
def test_open_url_refuses_anything_but_the_web(url: str, monkeypatch) -> None:
    monkeypatch.setattr("webbrowser.open", lambda *_a, **_k: pytest.fail("opened " + url))
    assert update_check.open_url(url, platform="darwin") is False


# ---------------------------------------------------------------------------
# Config: the updates section
# ---------------------------------------------------------------------------

def _config(tmp_path, data: dict[str, Any] | None = None) -> Config:
    path = tmp_path / "config.json"
    if data is not None:
        path.write_text(json.dumps(data))
    return Config(str(path))


def test_a_new_config_checks_and_has_skipped_nothing(tmp_path) -> None:
    assert _config(tmp_path).updates == {"check": True, "skipped": ""}


def test_config_keeps_a_valid_updates_section(tmp_path) -> None:
    cfg = _config(tmp_path, {"updates": {"check": False, "skipped": "v2000.10.02"}})
    assert cfg.updates == {"check": False, "skipped": "2000.10.02"}


def test_config_rejects_a_non_boolean_check(tmp_path) -> None:
    """A hand-edited "false" must read as "not set", never as an accidental off."""
    assert _config(tmp_path, {"updates": {"check": "false"}}).updates["check"] is True


def test_config_drops_a_skipped_value_that_is_not_a_version(tmp_path) -> None:
    """Otherwise a junk value could silence updates permanently."""
    assert _config(tmp_path, {"updates": {"skipped": "everything"}}).updates["skipped"] == ""


def test_config_updates_section_round_trips(tmp_path) -> None:
    cfg = _config(tmp_path)
    cfg.update({"updates": {"check": False, "skipped": "2000.10.02"}})
    assert Config(cfg.path).updates == {"check": False, "skipped": "2000.10.02"}


def test_config_update_merges_the_updates_section_key_by_key(tmp_path) -> None:
    cfg = _config(tmp_path, {"updates": {"check": False}})
    cfg.update({"updates": {"skipped": "2000.10.02"}})
    assert cfg.updates == {"check": False, "skipped": "2000.10.02"}


# ---------------------------------------------------------------------------
# HTTP endpoints
# ---------------------------------------------------------------------------

pytest.importorskip("paramiko")

from cmdly import server  # noqa: E402
from cmdly.server import Handler  # noqa: E402


class _StubChecker:
    """Records how it was called; returns a fixed status."""

    def __init__(self, status: dict[str, Any] | None = None) -> None:
        self.status = status or {
            "configured": True, "current": "2000.09.29", "latest": "2000.10.02",
            "update_available": True, "name": "n",
            "url": f"https://github.com/{REPO}/releases/tag/v2000.10.02",
            "published": "", "notes": "", "assets": [], "checked_at": 1, "error": "",
        }
        self.check_calls: list[bool] = []
        self.cached_calls = 0

    def check(self, force: bool = False) -> dict[str, Any]:
        self.check_calls.append(force)
        return dict(self.status)

    def cached_status(self) -> dict[str, Any]:
        self.cached_calls += 1
        return dict(self.status)


def _handler(tmp_path, *, updates: Any = None, config: dict[str, Any] | None = None,
             path: str = "/api/update"):
    handler = object.__new__(Handler)
    handler.server = types.SimpleNamespace(
        config=_config(tmp_path, config), updates=updates or _StubChecker())
    handler.path = path
    responses: list[tuple[dict, int]] = []
    handler._send_json = lambda data, status=200: responses.append((data, status))  # type: ignore[method-assign]
    return handler, responses


def test_api_update_reports_an_available_update(tmp_path) -> None:
    checker = _StubChecker()
    handler, responses = _handler(tmp_path, updates=checker)

    handler._api_update()

    payload, status = responses[0]
    assert status == 200
    assert payload["update_available"] is True
    assert payload["latest"] == "2000.10.02"
    assert payload["enabled"] is True
    assert payload["skipped"] == ""
    assert checker.check_calls == [False], "no refresh unless asked"


def test_api_update_honours_the_refresh_query(tmp_path) -> None:
    checker = _StubChecker()
    handler, _ = _handler(tmp_path, updates=checker, path="/api/update?refresh=1")
    handler._api_update()
    assert checker.check_calls == [True]


def test_api_update_without_a_repository_is_quiet(tmp_path, no_network) -> None:
    """The real checker with REPO unset: no request, no error, no update."""
    calls = no_network(error=AssertionError("no repository, no request"))
    handler, responses = _handler(
        tmp_path, updates=UpdateChecker(state_dir=str(tmp_path / "state")),
        path="/api/update?refresh=1")

    handler._api_update()

    payload, status = responses[0]
    assert status == 200
    assert calls == []
    assert payload["configured"] is False
    assert payload["update_available"] is False
    assert payload["error"] == ""


def test_api_update_off_never_touches_the_network(tmp_path) -> None:
    checker = _StubChecker()
    handler, responses = _handler(tmp_path, updates=checker,
                                  config={"updates": {"check": False}})

    handler._api_update()

    payload, _ = responses[0]
    assert payload["enabled"] is False
    assert payload["update_available"] is False, "a disabled check can raise no dialog"
    assert checker.check_calls == [], "and reaches for nothing"
    assert checker.cached_calls == 1


def test_api_update_echoes_the_skipped_version(tmp_path) -> None:
    handler, responses = _handler(tmp_path, config={"updates": {"skipped": "2000.10.02"}})
    handler._api_update()
    assert responses[0][0]["skipped"] == "2000.10.02"


def test_api_update_never_500s_on_a_broken_checker(tmp_path) -> None:
    class _Broken:
        def check(self, force: bool = False):
            raise RuntimeError("boom")

    handler, responses = _handler(tmp_path, updates=_Broken())
    handler._api_update()
    payload, status = responses[0]
    assert status == 200
    assert payload["update_available"] is False


def test_api_update_skip_persists_the_version(tmp_path) -> None:
    handler, responses = _handler(tmp_path)

    handler._api_update_skip({"version": "2000.10.02"})

    payload, status = responses[0]
    assert status == 200 and payload["ok"] is True
    assert payload["skipped"] == "2000.10.02"
    assert Config(str(tmp_path / "config.json")).updates["skipped"] == "2000.10.02"


def test_api_update_skip_leaves_the_check_switch_alone(tmp_path) -> None:
    """Dismissing a version must not also turn the check on or off."""
    handler, _ = _handler(tmp_path, config={"updates": {"check": False}})
    handler._api_update_skip({"version": "2000.10.02"})
    assert Config(str(tmp_path / "config.json")).updates == {
        "check": False, "skipped": "2000.10.02"}


def test_api_update_skip_with_an_empty_version_clears_the_dismissal(tmp_path) -> None:
    handler, responses = _handler(tmp_path, config={"updates": {"skipped": "2000.10.02"}})
    handler._api_update_skip({"version": ""})
    assert responses[0][0]["skipped"] == ""
    assert Config(str(tmp_path / "config.json")).updates["skipped"] == ""


def test_api_update_skip_ignores_a_junk_version(tmp_path) -> None:
    handler, responses = _handler(tmp_path)
    handler._api_update_skip({"version": "../../etc/passwd"})
    assert responses[0][0]["skipped"] == ""


def test_api_update_open_uses_the_derived_url_not_the_payload(tmp_path, monkeypatch) -> None:
    opened: list[str] = []
    monkeypatch.setattr(server, "open_url", lambda url: opened.append(url) or True)
    handler, responses = _handler(tmp_path)

    handler._api_update_open({"url": "https://evil.example/pwn"})

    assert opened == [f"https://github.com/{REPO}/releases/tag/v2000.10.02"]
    assert responses[0][0]["ok"] is True


def test_api_update_open_reports_when_no_browser_opens(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(server, "open_url", lambda url: False)
    handler, responses = _handler(tmp_path)
    handler._api_update_open({})

    payload, status = responses[0]
    assert status == 200
    assert payload["ok"] is False
    assert payload["url"], "the URL is still returned so the UI can offer a copy"


def test_api_update_open_without_a_repository_opens_nothing(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(server, "open_url", lambda url: pytest.fail("opened " + url))
    handler, responses = _handler(
        tmp_path, updates=UpdateChecker(state_dir=str(tmp_path / "state")))
    handler._api_update_open({})
    assert responses[0][1] == 404


def test_api_update_open_refuses_a_non_web_url(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(server, "open_url", lambda url: pytest.fail("opened " + url))
    stub = _StubChecker()
    stub.status["url"] = "file:///Applications/Calculator.app"
    handler, responses = _handler(tmp_path, updates=stub)
    handler._api_update_open({})
    assert responses[0][1] == 404


def test_update_routes_are_registered() -> None:
    assert server._ROUTES["GET"].get("/api/update") == "_api_update"
    assert server._ROUTES["POST"].get("/api/update/skip") == "_api_update_skip"
    assert server._ROUTES["POST"].get("/api/update/open") == "_api_update_open"


def test_no_version_literal_in_the_update_module() -> None:
    """The single-source-of-truth rule: the version comes from cmdly.version.

    Checked over the AST rather than the raw text so the CalVer *examples* in
    the docstrings are not mistaken for a second place the version lives.
    """
    import ast
    import pathlib
    import re

    path = pathlib.Path(update_check.__file__)
    tree = ast.parse(path.read_text())
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef))
        and node.body and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    }
    calver = re.compile(r"\b\d{4}\.\d{1,2}\.\d{1,3}\b")
    offenders = [
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        and id(node) not in docstrings and calver.search(node.value)
    ]
    assert not offenders, f"version literal(s) in code: {offenders}"
    assert "get_version" in path.read_text()
