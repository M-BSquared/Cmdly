#!/usr/bin/env bash
# Build the Linux AppImage in a container, from any host with Docker
# (Docker Desktop, OrbStack, or Docker on Linux).
#
#   tools/appimage-in-docker.sh [x86_64|aarch64]     # default: x86_64
#
# The image is the oldest Ubuntu the PySide6 wheels install on for that
# architecture, because an AppImage runs only on systems whose glibc is at
# least as new as the one it was built against:
#
#   x86_64   ubuntu:22.04  (PySide6 wheels: manylinux_2_34; 22.04 has 2.35)
#   aarch64  ubuntu:24.04  (PySide6 wheels: manylinux_2_39; 24.04 has 2.39)
#
# The checkout is mounted read-only and copied inside, so nothing the build
# writes (venv, build/) lands in the working copy except dist/.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARCH="${1:-x86_64}"
case "$ARCH" in
    x86_64)  PLATFORM=linux/amd64; IMAGE=ubuntu:22.04 ;;
    aarch64) PLATFORM=linux/arm64; IMAGE=ubuntu:24.04 ;;
    *) echo "usage: $0 [x86_64|aarch64]" >&2; exit 2 ;;
esac

command -v docker >/dev/null 2>&1 || { echo "ERROR: docker not found" >&2; exit 1; }
mkdir -p "$REPO_DIR/dist"

echo ">>> Building the $ARCH AppImage in $IMAGE ($PLATFORM) ..."
docker run --rm --platform "$PLATFORM" \
    -v "$REPO_DIR:/src:ro" -v "$REPO_DIR/dist:/out" \
    -e DEBIAN_FRONTEND=noninteractive \
    "$IMAGE" bash -euo pipefail -c '
        apt-get update -qq
        apt-get install -y -qq --no-install-recommends \
            ca-certificates wget rsync file squashfs-tools software-properties-common gpg-agent >/dev/null
        if ! command -v python3.12 >/dev/null 2>&1; then
            add-apt-repository -y ppa:deadsnakes/ppa >/dev/null
            apt-get update -qq
        fi
        apt-get install -y -qq --no-install-recommends python3.12 python3.12-venv python3.12-dev >/dev/null
        # LINUX_BUILD_PACKAGES: the system libraries build-appimage.sh bundles.
        # Names differ between releases (t64), so each is tried on its own.
        for pkg in libsnappy1v5 libminizip1 libminizip1t64 libwebp7 libwebpmux3 libwebpdemux2 \
                   libsharpyuv0 libopus0 liblcms2-2 libxkbfile1 libxcb-cursor0 libxcb-icccm4 \
                   libxcb-image0 libxcb-keysyms1 libxcb-render-util0 libxcb-util1; do
            apt-get install -y -qq --no-install-recommends "$pkg" >/dev/null 2>&1 || true
        done
        ln -sf "$(command -v python3.12)" /usr/local/bin/python3
        rsync -a --exclude .venv --exclude build --exclude dist --exclude .git /src/ /work/
        cd /work
        ./build-appimage.sh
        cp -a dist/*.AppImage dist/*.lock /out/ 2>/dev/null || true
    '
OUT="$(ls -1t "$REPO_DIR"/dist/*-"$ARCH".AppImage 2>/dev/null | head -1)"
[ -n "$OUT" ] || { echo "ERROR: no $ARCH AppImage was produced" >&2; exit 1; }
echo ">>> Done: $OUT"
