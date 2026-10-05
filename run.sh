#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
if [ -d "$DIR/.venv" ]; then
    "$DIR/.venv/bin/python3" "$DIR/run.py" "$@"
else
    python3 "$DIR/run.py" "$@"
fi
