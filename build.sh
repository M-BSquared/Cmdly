#!/usr/bin/env bash
# Cmdly — build the distributable artifact for this host.
#
# One entry point for people and CI. Packaging is per platform, so this hands
# over to the platform's script and never pretends to cross-build:
#
#   Linux  x86_64/aarch64  ->  ./build-appimage.sh   ->  dist/Cmdly-<version>-<arch>.AppImage
#   macOS  arm64/x86_64    ->  ./build-macos-app.sh  ->  dist/Cmdly.app
#                                                       (+ dist/Cmdly-<version>-macOS-<arch>.dmg)
#
# Usage:
#   ./build.sh [--dmg] [--no-verify] [--python <path>]
#
# --dmg is macOS-only and dropped on Linux with a note, so one CI invocation
# works on both. The version is read from VERSION, never written here.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION="$(cat "$REPO_DIR/VERSION")"
OS="$(uname -s)"
ARCH="$(uname -m)"

echo "=== Cmdly — build ==="
echo "Version: $VERSION  (read from VERSION)"
echo "Host:    $OS $ARCH"
echo ""

case "$OS" in
    Linux)
        SCRIPT="$REPO_DIR/build-appimage.sh"
        ARTIFACT="$REPO_DIR/dist/Cmdly-${VERSION}-${ARCH}.AppImage"
        ARGS=()
        for arg in "$@"; do
            case "$arg" in
                --dmg) echo ">>> note: --dmg is macOS-only, ignoring on Linux" ;;
                *)     ARGS+=("$arg") ;;
            esac
        done
        ;;
    Darwin)
        SCRIPT="$REPO_DIR/build-macos-app.sh"
        ARTIFACT="${CMDLY_DIST:-$REPO_DIR/dist}/Cmdly.app"
        ARGS=("$@")
        ;;
    *)
        echo "ERROR: unsupported build host '$OS'. Cmdly packages for Linux (AppImage) and macOS (.app)." >&2
        exit 1
        ;;
esac

[ -f "$SCRIPT" ] || { echo "ERROR: $SCRIPT not found" >&2; exit 1; }
echo ">>> Running $(basename "$SCRIPT") ${ARGS[*]:-}"
echo ""
bash "$SCRIPT" ${ARGS[@]+"${ARGS[@]}"}

[ -e "$ARTIFACT" ] || { echo "ERROR: expected artifact missing: $ARTIFACT" >&2; exit 1; }
echo ""
echo ">>> build.sh done — artifact: $ARTIFACT"
