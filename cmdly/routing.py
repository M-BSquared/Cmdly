"""The route table the HTTP handler dispatches on.

Its own module so the route mixins (``cmdly/routes/``) can register their
handlers without importing :mod:`cmdly.server`, which imports them.
"""
from __future__ import annotations

from collections.abc import Callable

# method -> path -> handler name
_ROUTES: dict[str, dict[str, str]] = {"GET": {}, "POST": {}}


def route(method: str, path: str) -> Callable:
    def register(fn: Callable) -> Callable:
        _ROUTES[method][path] = fn.__name__
        return fn
    return register
