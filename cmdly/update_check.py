"""Update check against the Cmdly GitHub releases page.

Nobody should have to watch a repository to learn that a newer build exists.
This module compares the running version against the newest published
release of :data:`REPO` and hands the answer to the page, which raises a
dialog once per version.

Which repository
----------------
:data:`REPO` names the public repository whose releases are checked — the
whole switch. While it is empty (a private fork, say) the checker is inert:
:meth:`UpdateChecker.check` reaches for nothing, writes no cache, reports
``configured: False`` with no error, and so the page shows neither a dialog
nor a failure.

Offline contract
----------------
* Nothing here runs at import or at startup. The check happens only when the
  page asks for it, on a background fetch nothing in the UI waits for.
* Every answer is cached to ``<state_dir>/update.json``, so a launch with no
  internet reports the last known result instead of going quiet, and a
  repeated launch does not hammer GitHub — a fresh network check is made at
  most once per :data:`CHECK_INTERVAL_S` (sooner after a failure, since a
  failed check knows nothing).
* A failed check is never an error anyone sees uninvited. It returns the
  cached release together with a message Settings can show on request.

Only the release *list* is trusted from the network. The page URL the dialog
offers is BUILT from the tag, never read out of the payload, so a tampered
cache file can at worst name a different tag in the same repository rather
than send anyone to another site.
"""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlsplit

from .child_env import child_env
from .paths import cmdly_home
from .version import get_version

logger = logging.getLogger("cmdly.update")

# "owner/name" of the GitHub repository whose releases are checked. The
# whole switch: an empty REPO (a private fork, say) turns the update check
# off entirely.
REPO = "M-BSquared/Cmdly"

UPDATE_FILE = "update.json"
FETCH_TIMEOUT_S = 6.0
# Nobody is waiting on this request, but a hung socket must not hold a handler
# thread or a huge body exhaust memory. A release list is a few dozen KB.
MAX_PAYLOAD_BYTES = 2 * 1024 * 1024
# How stale a successful check may be before the next request re-fetches.
CHECK_INTERVAL_S = 6 * 3600.0
# After a failure: the usual case is "no internet right now", so retry often
# enough that a returning connection is noticed, rarely enough that an
# offline session is not retrying on every page load.
RETRY_INTERVAL_S = 900.0
# Release notes are shown in a dialog, not a document viewer.
MAX_NOTES_CHARS = 4000

_TAG_RE = re.compile(r"^v?(\d+(?:\.\d+)*)$")
# GitHub's own rules for owner and repository names, close enough that
# nothing outside them can end up interpolated into a URL.
_REPO_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9._-]{1,100}$")


def default_state_dir() -> str:
    """Where the cached check result lives (``~/.cmdly``)."""
    return cmdly_home()


def configured_repo(repo: str | None = None) -> str:
    """*repo* (default :data:`REPO`) when it is a usable ``owner/name``, else ``""``."""
    value = (REPO if repo is None else repo or "").strip()
    return value if _REPO_RE.match(value) and ".." not in value else ""


def releases_api_url(repo: str) -> str:
    return f"https://api.github.com/repos/{repo}/releases?per_page=10"


def releases_page_url(repo: str) -> str:
    return f"https://github.com/{repo}/releases"


def parse_version(text: Any) -> tuple[int, ...] | None:
    """Parse ``2026.10.06`` / ``v2026.10.06`` into a comparable tuple.

    Returns ``None`` for anything that is not a plain dotted number — a
    release named ``nightly`` or a ``0.0.0-unknown`` fallback version must
    never be compared, because a wrong comparison here announces an update
    that does not exist.
    """
    match = _TAG_RE.match(str(text or "").strip())
    if match is None:
        return None
    return tuple(int(part) for part in match.group(1).split("."))


def is_newer(candidate: Any, current: Any) -> bool:
    """True when *candidate* is a strictly newer version than *current*.

    Unparsable on either side means "no update": CalVer components are
    zero-padded strings, so the comparison is done on integer tuples and
    shorter tuples sort first (``2026.10`` < ``2026.10.01``).
    """
    left = parse_version(candidate)
    right = parse_version(current)
    if left is None or right is None:
        return False
    return left > right


def open_url(url: str, platform: str = sys.platform) -> bool:
    """Open a web page in the system browser; whether a browser was started.

    http and https only: on every desktop the URL opener is a launcher for far
    more schemes than those, and the scheme decides which program runs.

    Linux goes through ``xdg-open`` with :func:`cmdly.child_env.child_env`,
    not through :mod:`webbrowser`, which starts its commands with this
    process' environment and no way to give it another. It is not waited for:
    some browsers keep ``xdg-open`` until their window closes.
    """
    try:
        if urlsplit(url).scheme not in ("http", "https"):
            return False
    except ValueError:
        return False
    if platform.startswith("linux"):
        try:
            subprocess.Popen(
                ["xdg-open", url], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, close_fds=True, start_new_session=True,
                env=child_env(),
            )
            return True
        except OSError as exc:
            logger.info("xdg-open could not open %s: %s", url, exc)
    try:
        import webbrowser
        return bool(webbrowser.open(url))
    except Exception:  # noqa: BLE001 - no browser is an answer, not an error
        logger.info("could not open %s in a browser", url, exc_info=True)
        return False


def _request(url: str) -> urllib.request.Request:
    return urllib.request.Request(url, headers={
        "User-Agent": f"Cmdly/{get_version()}",
        "Accept": "application/vnd.github+json",
    })


def _release_page(repo: str, tag: str) -> str:
    """The release page for *tag*, or the releases index for an odd tag."""
    if not repo:
        return ""
    if _TAG_RE.match(tag or ""):
        return f"{releases_page_url(repo)}/tag/{tag}"
    return releases_page_url(repo)


def _pick_latest(payload: Any, repo: str) -> dict[str, Any] | None:
    """Reduce the GitHub release payload to the newest stable release.

    Untrusted input: every field is coerced, drafts and prereleases are
    dropped, and the winner is chosen by comparing parsed version tuples
    rather than trusting the order GitHub returned.
    """
    if not isinstance(payload, list):
        return None
    best: dict[str, Any] | None = None
    best_version: tuple[int, ...] | None = None
    for item in payload:
        if not isinstance(item, dict) or item.get("draft") or item.get("prerelease"):
            continue
        tag = str(item.get("tag_name") or "")
        version = parse_version(tag)
        if version is None:
            continue
        if best_version is not None and version <= best_version:
            continue
        notes = str(item.get("body") or "").strip()
        assets = []
        for asset in item.get("assets") or []:
            if not isinstance(asset, dict):
                continue
            try:
                size = int(asset.get("size") or 0)
            except (TypeError, ValueError):
                size = 0
            assets.append({"name": str(asset.get("name") or ""), "size": size})
        best_version = version
        best = {
            "tag": tag,
            # The tag's own text minus the "v", so the UI never has to strip
            # it and the zero padding CalVer writes ("2026.10.06") survives —
            # rebuilding the string from the parsed ints would lose it, and
            # the dismissed-version match is a string compare.
            "version": tag.lstrip("v"),
            "name": str(item.get("name") or tag),
            "published": str(item.get("published_at") or ""),
            "notes": notes[:MAX_NOTES_CHARS],
            "assets": assets,
            "url": _release_page(repo, tag),
        }
    return best


class UpdateChecker:
    """Cached "is there a newer release?" answer, backed by one JSON file.

    Thread-safe: HTTP handler threads share one instance, and a check that is
    already in flight is not started a second time.

    *repo* defaults to :data:`REPO`, read at each call so the tests (and a
    later setting) can change it without a new checker.
    """

    def __init__(self, state_dir: str | None = None, repo: str | None = None) -> None:
        self.dir = state_dir or default_state_dir()
        self._repo = repo
        self._lock = threading.Lock()

    @property
    def repo(self) -> str:
        """The usable ``owner/name`` this checker asks, or ``""`` when none is set."""
        return configured_repo(self._repo)

    # ------------------------------------------------------------------
    # Cache
    # ------------------------------------------------------------------

    def _cache_path(self) -> str:
        return os.path.join(self.dir, UPDATE_FILE)

    def load_cached(self) -> dict[str, Any]:
        """The last stored check result; ``{}`` when there is no usable cache.

        A result stored for another repository is no result at all: it would
        otherwise announce that repository's release under this one's name.
        """
        try:
            with open(self._cache_path(), encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return {}
        if not isinstance(data, dict) or data.get("repo") != self.repo:
            return {}
        return data

    def _store_cached(self, data: dict[str, Any]) -> None:
        try:
            os.makedirs(self.dir, exist_ok=True)
            path = self._cache_path()
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as handle:
                json.dump(data, handle)
            os.replace(tmp, path)
        except OSError:
            logger.debug("could not cache the update check", exc_info=True)

    # ------------------------------------------------------------------
    # Network
    # ------------------------------------------------------------------

    def fetch(self) -> tuple[dict[str, Any] | None, str]:
        """Fetch the release list. Returns ``(latest_release, error)``.

        Never raises: offline, this call fails on every launch, and that is a
        normal state, not a fault. Without a repository it asks nothing.
        """
        repo = self.repo
        if not repo:
            return None, ""
        try:
            with urllib.request.urlopen(_request(releases_api_url(repo)),
                                        timeout=FETCH_TIMEOUT_S) as resp:
                raw = resp.read(MAX_PAYLOAD_BYTES + 1)
            if len(raw) > MAX_PAYLOAD_BYTES:
                return None, "the release list was unexpectedly large"
            payload = json.loads(raw.decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            logger.info("update check failed: %s", exc)
            return None, f"could not reach the release server ({exc})"
        return _pick_latest(payload, repo), ""

    def _is_stale(self, cached: dict[str, Any], now: float) -> bool:
        checked_at = cached.get("checked_at")
        if not isinstance(checked_at, (int, float)):
            return True
        # A clock that moved backwards (or a cache copied from another
        # machine) must not pin the check as "fresh" forever.
        if checked_at > now:
            return True
        interval = CHECK_INTERVAL_S if cached.get("latest") else RETRY_INTERVAL_S
        return (now - checked_at) >= interval

    def check(self, force: bool = False) -> dict[str, Any]:
        """Return the update status as the API serves it.

        ``force`` always goes to the network (Settings' "Check now").
        Otherwise the cached answer is reused until it goes stale, so opening
        the app repeatedly costs nothing and works offline. Without a
        repository nothing is fetched or stored, whatever ``force`` says.
        """
        repo = self.repo
        if not repo:
            return self._status(get_version(), "", None, "", None)
        now = time.time()
        with self._lock:
            cached = self.load_cached()
            error = str(cached.get("error") or "")
            latest = cached.get("latest") if isinstance(cached.get("latest"), dict) else None
            checked_at = cached.get("checked_at")
            if force or self._is_stale(cached, now):
                fetched, error = self.fetch()
                if fetched is not None:
                    latest = fetched
                checked_at = now
                # The failed attempt is stored too, so an offline session backs
                # off instead of re-trying the timeout on every page load.
                self._store_cached({
                    "repo": repo,
                    "checked_at": now,
                    "latest": latest,
                    "error": error,
                })
        return self._status(get_version(), repo, latest, error, checked_at)

    def cached_status(self) -> dict[str, Any]:
        """The stored answer with no network access at all."""
        repo = self.repo
        if not repo:
            return self._status(get_version(), "", None, "", None)
        cached = self.load_cached()
        latest = cached.get("latest") if isinstance(cached.get("latest"), dict) else None
        return self._status(get_version(), repo, latest,
                            str(cached.get("error") or ""), cached.get("checked_at"))

    @staticmethod
    def _status(current: str, repo: str, latest: dict[str, Any] | None,
                error: str, checked_at: Any) -> dict[str, Any]:
        release = dict(latest) if latest else {}
        return {
            "configured": bool(repo),
            "current": current,
            "latest": release.get("version", ""),
            "update_available": bool(repo) and is_newer(release.get("version"), current),
            "name": release.get("name", ""),
            # Rebuilt from the tag on the way out, never read back from the
            # stored object. The cache is an ordinary file in ~/.cmdly;
            # anything that can write there could otherwise put its own URL in
            # front of POST /api/update/open, which hands it to the system
            # browser. _release_page validates the tag and falls back to the
            # releases index, so the worst a tampered cache can do is name a
            # different tag in this repository.
            "url": _release_page(repo, str(release.get("tag") or "")),
            "published": release.get("published", ""),
            "notes": release.get("notes", ""),
            "assets": release.get("assets", []),
            "checked_at": checked_at if isinstance(checked_at, (int, float)) else 0,
            "error": error,
        }
