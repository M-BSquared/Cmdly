"""``python -m cmdly`` — the package's command line.

    python -m cmdly mcp    Cmdly's MCP server, on stdin/stdout
                          (see :mod:`cmdly.mcp`)

The desktop app is ``cmdly/app.py`` (or ``run.sh``), deliberately not this:
it pulls in Qt, and the MCP server is at its leanest without it.
"""
from __future__ import annotations

import sys

from .mcp import run


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else list(argv)
    if args[:1] == ["mcp"]:
        return run()
    print("usage: python -m cmdly mcp", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
