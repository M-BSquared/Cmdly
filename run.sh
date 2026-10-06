#!/usr/bin/env bash
# Cmdly — run the desktop app from source.
#
#   ./run.sh [PORT]
#   ./run.sh --desktop-entry      # Linux: add this checkout to the app launcher
#
# The first run creates .venv from a Python >= 3.12 and installs the `dev`
# group from pyproject.toml into it. Later runs re-install only when
# pyproject.toml has changed, so a relaunch needs no network.
#
# $CMDLY_PYTHON picks the interpreter the venv is created from.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$REPO_DIR/.venv"
PY="$VENV/bin/python"
STAMP="$VENV/.cmdly-deps"

ENTRY="${XDG_DATA_HOME:-$HOME/.local/share}/applications/cmdly-dev.desktop"
if [ "${1:-}" = "--desktop-entry" ]; then
    if [ "$(uname -s)" != "Linux" ]; then
        echo "ERROR: --desktop-entry is for Linux desktops" >&2
        exit 1
    fi
    mkdir -p "$(dirname "$ENTRY")"
    printf '%s\n' \
        "[Desktop Entry]" \
        "Type=Application" \
        "Name=Cmdly (dev)" \
        "Comment=Cmdly from the checkout in $REPO_DIR" \
        "Exec=\"$REPO_DIR/run.sh\"" \
        "Icon=$REPO_DIR/assets/icon.png" \
        "StartupWMClass=cmdly-dev" \
        "Categories=Utility;Development;" \
        "Terminal=false" > "$ENTRY"
    echo ">>> Desktop entry: $ENTRY"
    exit 0
fi

py_ok() { "$1" -c 'import sys; sys.exit(sys.version_info < (3, 12))' >/dev/null 2>&1; }

if [ ! -x "$PY" ]; then
    BASE="${CMDLY_PYTHON:-}"
    if [ -z "$BASE" ]; then
        for cand in python3.13 python3.12 python3.14 python3; do
            path="$(command -v "$cand" 2>/dev/null || true)"
            if [ -n "$path" ] && py_ok "$path"; then BASE="$path"; break; fi
        done
    fi
    if [ -z "$BASE" ] || ! py_ok "$BASE"; then
        echo "ERROR: Cmdly needs Python >= 3.12; none found on PATH." >&2
        echo "       Install one, or point at it: CMDLY_PYTHON=/path/to/python3 ./run.sh" >&2
        exit 1
    fi
    echo ">>> Creating .venv with $BASE ..."
    "$BASE" -m venv "$VENV"
fi

WANT="$("$PY" -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' \
        "$REPO_DIR/pyproject.toml")"
HAVE="$(cat "$STAMP" 2>/dev/null || true)"
if [ "$WANT" != "$HAVE" ]; then
    echo ">>> Installing dependencies (pyproject.toml, group dev) ..."
    # pip >= 25.1 reads [dependency-groups].
    if "$PY" -m pip install --quiet --upgrade pip \
        && "$PY" -m pip install --quiet --group "$REPO_DIR/pyproject.toml:dev"; then
        echo "$WANT" > "$STAMP"
    elif [ -n "$HAVE" ]; then
        echo "WARNING: dependency update failed (offline?); starting with what is installed" >&2
    else
        echo "ERROR: dependency install failed; see the pip output above" >&2
        exit 1
    fi
fi

# exec, so SIGINT/SIGTERM reach cmdly/app.py's own handlers.
exec "$PY" "$REPO_DIR/cmdly/app.py" "$@"
