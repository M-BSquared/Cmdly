#!/usr/bin/env bash
# Build Cmdly as a Linux AppImage (x86_64 or aarch64).
#
# Bundles a relocatable CPython (venv --copies + host stdlib + libpython) and
# the PySide6/QtWebEngine wheels, then packs them with appimagetool. No conda on
# the build host; only stdlib python3 -m venv + pip are used.
#
# Version is read exclusively from the repo-root VERSION file — never hardcoded.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION="$(cat "$REPO_DIR/VERSION")"
ARCH="$(uname -m)"
BUILD_DIR="$REPO_DIR/build"
APPDIR="$BUILD_DIR/AppDir"
# Artifacts go to dist/, which is gitignored — not to the repo root.
# Two finished .dmg files (600 MB between them) were sitting in the
# checkout from builds two weeks old, because this is where they landed.
OUTPUT="$REPO_DIR/dist/Cmdly-${VERSION}-${ARCH}.AppImage"

# ---- preflight --------------------------------------------------------------
echo "=== Cmdly — AppImage build ==="
echo "Repo:    $REPO_DIR"
echo "Version: $VERSION  (read from VERSION)"
echo "AppDir:  $APPDIR"
echo "Output:  $OUTPUT"
echo ""

command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 not found" >&2; exit 1; }

PY_MAJOR="$(python3 -c 'import sys; print(sys.version_info.major)')"
PY_MINOR="$(python3 -c 'import sys; print(sys.version_info.minor)')"
# 3.12 is the floor pyproject.toml declares and the version CI tests.
# This used to accept 3.10, so the shipped AppImage could be built on an
# interpreter older than anything the suite had ever run against.
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 12 ]; }; then
    echo "ERROR: Python >= 3.12 required, found $PY_MAJOR.$PY_MINOR" >&2
    exit 1
fi
PY_MM="${PY_MAJOR}.${PY_MINOR}"

case "$ARCH" in
    x86_64|aarch64) ;;
    *) echo "ERROR: AppImages are built for x86_64 or aarch64; host arch is $ARCH" >&2; exit 1 ;;
esac

# Everything the AppDir is assembled from, checked before anything is built.
# A missing LICENSE.md used to stop the build at its `cp`, long after the
# interpreter had been downloaded and the wheels installed, with no hint of
# which step wanted it. Name the file, in the first second.
MISSING=""
for required in \
    VERSION pyproject.toml \
    cmdly src assets assets/icon.png assets/icon-256.png tools/qt_bundle.py
do
    [ -e "$REPO_DIR/$required" ] || MISSING="$MISSING  $required"
done
if [ -n "$MISSING" ]; then
    echo "ERROR: the AppImage is assembled from files that are not in the repo:" >&2
    for m in $MISSING; do echo "         $m" >&2; done
    echo "       Restore them (git checkout -- <path>) and run this again." >&2
    exit 1
fi

if command -v wget >/dev/null 2>&1; then
    DOWNLOADER=wget
elif command -v curl >/dev/null 2>&1; then
    DOWNLOADER=curl
else
    echo "ERROR: wget or curl required" >&2
    exit 1
fi
download() {  # <url> <dest>
    local url="$1" dest="$2"
    if [ "$DOWNLOADER" = wget ]; then wget -q -O "$dest" "$url"
    else curl -fsSL -o "$dest" "$url"; fi
}

# host interpreter layout (detected, never assumed)
PY_STDLIB="$(python3 -c 'import sysconfig; print(sysconfig.get_path("stdlib"))')"
PY_LIBDIR="$(python3 -c 'import sysconfig; print(sysconfig.get_config_var("LIBDIR"))')"

# ---- cleanup trap: keep $OUTPUT + cached appimagetool, drop $APPDIR on failure
SUCCESS=0
cleanup() {
    if [ "${SUCCESS:-0}" -ne 1 ]; then
        rm -rf "$APPDIR" 2>/dev/null || true
    fi
}
trap cleanup EXIT
trap 'cleanup; exit 130' INT
trap 'cleanup; exit 143' TERM

# ---- fresh AppDir -----------------------------------------------------------
echo ">>> Preparing AppDir ..."
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr"
rm -f "$OUTPUT"

# ---- 1. relocatable venv (--copies the interpreter binary) ------------------
echo ">>> Creating venv (python$PY_MM) in AppDir/usr ..."
python3 -m venv --copies "$APPDIR/usr"

# ---- 2. fix portability: copy host stdlib + lib-dynload + libpython ---------
# pyvenv.cfg `home =` points at the build host and breaks on another machine.
# PYTHONHOME (set in AppRun) repoints the interpreter at AppDir/usr; to make
# that resolve we copy the host stdlib (with lib-dynload) under the venv's
# lib/pythonX.Y and the shared libpython next to it. The venv's own
# site-packages is preserved: the host stdlib dir has no site-packages subdir,
# and rsync below excludes dist-packages to avoid leaking system debs.
echo ">>> Bundling stdlib + lib-dynload from $PY_STDLIB ..."
rsync -a --exclude 'dist-packages' "$PY_STDLIB/" "$APPDIR/usr/lib/python$PY_MM/"

echo ">>> Bundling libpython${PY_MM}.so.1.0 from $PY_LIBDIR ..."
if [ -f "$PY_LIBDIR/libpython${PY_MM}.so.1.0" ]; then
    cp -a "$PY_LIBDIR/libpython${PY_MM}.so.1.0" "$APPDIR/usr/lib/"
else
    # Static-libpython builds (e.g. Debian/Ubuntu) embed it in the executable;
    # the .so is still bundled when present so --enable-shared hosts work too.
    echo "WARNING: libpython${PY_MM}.so.1.0 not found at $PY_LIBDIR (host likely static-libpython)"
fi

# ---- 3. pip-install deps (pyproject.toml's `app` group) ---------------------
PIP_LOG="$BUILD_DIR/pip-install.log"
mkdir -p "$BUILD_DIR"
: > "$PIP_LOG"
echo ">>> Upgrading pip ..."
if ! "$APPDIR/usr/bin/python3" -m pip install --upgrade pip >>"$PIP_LOG" 2>&1; then
    echo "ERROR: pip self-upgrade failed; log: $PIP_LOG" >&2
    exit 1
fi
# pyproject.toml's `app` group, not a hand-written list: this script used to
# install the runtime packages with NO version floors, so the Linux artifact
# could be built against a package older than the floor the code needs and
# nothing would catch it until a user hit it.
#
# Which source, in order: $CMDLY_REQUIREMENTS, then requirements.lock if the
# repo has one, then the `app` group. The lock is what makes a release
# rebuildable — the group states floors, so installing from it in six months
# resolves to whatever is newest then. Every build writes the set it actually
# installed to dist/*.lock; promoting one to requirements.lock at tag time
# pins the next rebuild to it.
REQUIREMENTS="${CMDLY_REQUIREMENTS:-}"
if [ -z "$REQUIREMENTS" ] && [ -f "$REPO_DIR/requirements.lock" ]; then
    REQUIREMENTS="$REPO_DIR/requirements.lock"
fi
if [ -n "$REQUIREMENTS" ]; then
    if [ ! -f "$REQUIREMENTS" ]; then
        echo "ERROR: missing $REQUIREMENTS" >&2
        exit 1
    fi
    DEPS_ARGS=(-r "$REQUIREMENTS")
    DEPS_LABEL="$(basename "$REQUIREMENTS")"
else
    DEPS_ARGS=(--group "$REPO_DIR/pyproject.toml:app")
    DEPS_LABEL="pyproject.toml [app]"
fi
LOCK_OUT="$REPO_DIR/dist/Cmdly-${VERSION}-${ARCH}.lock"
echo ">>> Installing runtime deps from $DEPS_LABEL ..."
if ! "$APPDIR/usr/bin/python3" -m pip install \
        "${DEPS_ARGS[@]}" >>"$PIP_LOG" 2>&1; then
    echo "ERROR: dependency install failed; log: $PIP_LOG" >&2
    exit 1
fi
echo "    (deps install log: $PIP_LOG)"
# What went into THIS AppImage, exactly. Ships beside the artifact so a
# rebuild can be told to resolve to the same versions:
#   cp dist/Cmdly-<version>-<arch>.lock requirements.lock
mkdir -p "$REPO_DIR/dist"
{
    echo "# Cmdly $VERSION — Linux $ARCH, python $PY_MM"
    echo "# The resolved runtime set this artifact was built from."
    echo "# Install with: pip install -r <this file>"
    "$APPDIR/usr/bin/python3" -m pip freeze --all --exclude-editable
} > "$LOCK_OUT" 2>>"$PIP_LOG" || {
    echo "WARNING: could not write $LOCK_OUT" >&2
    rm -f "$LOCK_OUT"
}
if [ -f "$LOCK_OUT" ]; then echo "    (resolved set: $LOCK_OUT)"; fi

# ---- 3b. Qt: the modules Cmdly loads ---------------------------------------
# The PySide6 wheels carry every Qt module, the Designer/Assistant/Linguist
# tools and the files for building bindings. tools/qt_bundle.py takes out what
# nothing in Cmdly loads, read from the binaries' own DT_NEEDED entries, and
# fails the build if anything left would miss a library it links.
echo ">>> Trimming PySide6 to the Qt modules Cmdly loads ..."
python3 "$REPO_DIR/tools/qt_bundle.py" prune "$APPDIR/usr/lib/python$PY_MM/site-packages"

# ---- 3c. the system libraries Qt links that a desktop may not have ---------
# The PySide6 wheels carry Qt itself, but QtWebEngine links a handful of
# libraries from the system: codecs and compression (snappy, minizip, webp,
# opus, lcms2) and the xcb utility libraries the X11 platform plugin needs.
# Many desktops have some of them and few have all: Ubuntu without a browser
# of its own has no libsnappy, and libxcb-cursor is missing almost everywhere.
# So they travel in usr/lib (AppRun puts it on LD_LIBRARY_PATH). What every
# desktop has by definition (glibc, X11 and Wayland themselves, OpenGL/EGL,
# fontconfig, dbus, NSS) stays the system's; bundling those breaks more than
# it fixes.
BUNDLED_SYSTEM_LIBS="
libsnappy.so.1 libminizip.so.1 libwebp.so.7 libwebpmux.so.3 libwebpdemux.so.2
libsharpyuv.so.0 libopus.so.0 liblcms2.so.2 libxkbfile.so.1
libxcb-cursor.so.0 libxcb-icccm.so.4 libxcb-image.so.0 libxcb-keysyms.so.1
libxcb-render-util.so.0 libxcb-util.so.1
"
echo ">>> Bundling the system libraries QtWebEngine links ..."
MISSING_LIBS=""
for soname in $BUNDLED_SYSTEM_LIBS; do
    # No early exit in awk: under pipefail, ldconfig's SIGPIPE would end the build.
    path="$(ldconfig -p | awk -v n="$soname" '$1 == n && $0 ~ /=>/ && !found {print $NF; found = 1}')"
    if [ -z "$path" ]; then
        # libsharpyuv only exists where libwebp was split (Ubuntu 24.04+).
        [ "$soname" = "libsharpyuv.so.0" ] && continue
        MISSING_LIBS="$MISSING_LIBS $soname"
        continue
    fi
    cp -L "$path" "$APPDIR/usr/lib/$soname"
    echo "    $soname <- $path"
done
if [ -n "$MISSING_LIBS" ]; then
    echo "ERROR: these libraries have to be on the build host to be bundled:" >&2
    for m in $MISSING_LIBS; do echo "         $m" >&2; done
    echo "       On Ubuntu: tools/appimage-in-docker.sh installs them (see LINUX_BUILD_PACKAGES there)." >&2
    exit 1
fi

# Everything Qt and the interpreter link, resolved as it will be at run time.
# What is still missing must be on the allow list of libraries a desktop
# provides (or optional plugins whose absence Qt survives); anything else is
# an AppImage that would not start on some machine, which is a build error.
echo ">>> Checking every bundled library resolves ..."
SITE_QT="$APPDIR/usr/lib/python$PY_MM/site-packages/PySide6/Qt"
SYSTEM_PROVIDED='^lib(wayland-(client|cursor|egl)|X(11|11-xcb|ext|fixes|i|render|randr|cursor|damage|composite|tst|au|dmcp)|xcb|xcb-(shape|render|shm|sync|xfixes|xkb|randr|glx|present|dri3|xinerama|xinput)|SM|ICE|GL|EGL|GLX|OpenGL|gbm|drm|fontconfig|freetype|dbus-1|glib-2\.0|gobject-2\.0|gio-2\.0|gthread-2\.0|gmodule-2\.0|nss3|nssutil3|nspr4|smime3|plc4|plds4|asound|expat|z|xkbcommon|xkbcommon-x11|xshmfence|udev|cups|gtk-3|gdk-3|gdk_pixbuf-2\.0|pango-1\.0|pangocairo-1\.0|pangoft2-1\.0|harfbuzz|fribidi|thai|epoxy|png16|jpeg|cairo|cairo-gobject|atk-1\.0|readline|tinfo|ncursesw|Qt6EglFsKmsGbmSupport)\.so'
UNRESOLVED="$(
    find "$SITE_QT" "$APPDIR/usr/lib" -maxdepth 6 -type f \( -name '*.so*' -o -name QtWebEngineProcess \) 2>/dev/null \
    | while IFS= read -r f; do
        LD_LIBRARY_PATH="$SITE_QT/lib:$APPDIR/usr/lib" ldd "$f" 2>/dev/null | awk '/not found/ {print $1}'
    done | sort -u | grep -Ev "$SYSTEM_PROVIDED" || true
)"
if [ -n "$UNRESOLVED" ]; then
    echo "ERROR: bundled binaries link libraries that are neither bundled nor provided by a desktop:" >&2
    printf '         %s\n' $UNRESOLVED >&2
    echo "       Add them to BUNDLED_SYSTEM_LIBS (and install them on the build host)." >&2
    exit 1
fi
echo "    ok"

# ---- 4. copy app code into AppDir root -------------------------------------
# cmdly/version.py does parent.parent/VERSION; cmdly/server.py does
# parent.parent/src — so VERSION, cmdly/, src/, assets/ are siblings.
echo ">>> Copying application code ..."
rsync -a --exclude '__pycache__' "$REPO_DIR/cmdly/" "$APPDIR/cmdly/"
rsync -a --exclude '__pycache__' "$REPO_DIR/src/" "$APPDIR/src/"
rsync -a --exclude 'icon.jpeg' "$REPO_DIR/assets/" "$APPDIR/assets/"
cp -a "$REPO_DIR/VERSION" "$APPDIR/VERSION"
if [ -f "$REPO_DIR/LICENSE.md" ]; then cp -a "$REPO_DIR/LICENSE.md" "$APPDIR/LICENSE.md"; fi

# ---- 5. generate AppRun (no version literal; pythonX.Y resolved at runtime) --
echo ">>> Generating AppRun + desktop entry ..."
cat > "$APPDIR/AppRun" <<'APPRUN_EOF'
#!/usr/bin/env bash
set -euo pipefail

# AppImage type-2 sets $APPDIR to the mount point; fall back to the script dir
# so AppRun is also runnable directly from an extracted squashfs-root.
if [ -z "${APPDIR:-}" ]; then
    APPDIR="$(cd "$(dirname "$0")" && pwd)"
fi
cd "$APPDIR"

# Resolve the bundled pythonX.Y directory at runtime (X.Y was fixed at build).
shopt -s nullglob
PY_BASE=""
for d in "$APPDIR/usr/lib"/python3.*/; do PY_BASE="$d"; break; done
shopt -u nullglob
if [ -z "$PY_BASE" ] || [ ! -d "$PY_BASE" ]; then
    echo "cmdly: bundled python3.x not found under $APPDIR/usr/lib" >&2
    exit 1
fi
PY_SITE="${PY_BASE}site-packages"

# PYTHONHOME overrides the stale pyvenv.cfg `home =` so the bundled interpreter
# finds its stdlib under $APPDIR/usr/lib/pythonX.Y regardless of mount path.
# PYTHONPATH re-adds the venv site-packages because PYTHONHOME bypasses venv
# site-discovery, and AppDir root so `import cmdly` resolves.
export PYTHONHOME="$APPDIR/usr"
export PYTHONPATH="$APPDIR:$PY_SITE"

# Qt6 is bundled inside the PySide6 wheel (site-packages/PySide6/Qt/). Point the
# Qt plugin/resource loaders and the dynamic linker at it so the bundled Qt is
# used despite the random /tmp/.mount_<XXXX> AppImage mount path.
PYSIDE6_QT="$PY_SITE/PySide6/Qt"
export QT_PLUGIN_PATH="$PYSIDE6_QT/plugins"
export QT_QPA_PLATFORM_PLUGIN_PATH="$PYSIDE6_QT/plugins"
export QTWEBENGINE_RESOURCES_PATH="$PYSIDE6_QT/resources"
if [ -d "$PYSIDE6_QT/resources/qtwebengine_dictionaries" ]; then
    export QTWEBENGINE_DICTIONARIES_PATH="$PYSIDE6_QT/resources/qtwebengine_dictionaries"
fi
export LD_LIBRARY_PATH="$PYSIDE6_QT/lib:$APPDIR/usr/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

# AppImage cannot use the Chromium setuid sandbox; append the disabling flags.
# app.py uses os.environ.setdefault, so its own Vulkan/swiftshader flags stay.
export QTWEBENGINE_CHROMIUM_FLAGS="${QTWEBENGINE_CHROMIUM_FLAGS:-} --no-sandbox --disable-gpu-sandbox --disable-setuid-sandbox --disable-dev-shm-usage"

# Ensure a writable HOME for Qt/Chromium profile+cache when none is set/unwritable.
if [ -z "${HOME:-}" ] || [ ! -w "${HOME:-}" ]; then
    export HOME="${XDG_CACHE_HOME:-${TMPDIR:-/tmp}}/cmdly"
    mkdir -p "$HOME" 2>/dev/null || true
fi

# exec replaces the shell so SIGINT/SIGTERM reach python directly, letting
# cmdly/app.py's signal handlers tear down cleanly (no zombies, no leaked sockets).
exec "$APPDIR/usr/bin/python3" "$APPDIR/cmdly/app.py" "$@"
APPRUN_EOF
chmod 0755 "$APPDIR/AppRun"

# ---- 6. desktop entry (no version literal) ---------------------------------
# StartupWMClass is how a dock ties the running window to this entry; it is
# the id cmdly/app.py gives the window inside an AppImage (desktop_id).
cat > "$APPDIR/cmdly.desktop" <<'DESKTOP_EOF'
[Desktop Entry]
Name=Cmdly
Comment=One-press buttons that start programs, here or over SSH
Exec=cmdly
Icon=cmdly
StartupWMClass=cmdly
Type=Application
Categories=Utility;Development;
Keywords=ssh;terminal;launcher;command;
Terminal=false
DESKTOP_EOF

# ---- 7. icon: a square 256x256 PNG ------------------------------------------
# An integrator files the icon under hicolor/<W>x<H>/apps from its real size,
# so it has to be exactly 256x256; checked, because a wrong size fails
# silently later.
ICON="$APPDIR/cmdly.png"
# Rendered once by tools/make_icon.py, so this needs no image tool.
cp -a "$REPO_DIR/assets/icon-256.png" "$ICON"
ICON_SIZE="$(python3 -c 'import struct, sys; d = open(sys.argv[1], "rb").read(24); print("%dx%d" % struct.unpack(">II", d[16:24]))' "$ICON")"
if [ "$ICON_SIZE" != "256x256" ]; then
    echo "ERROR: the AppImage icon is $ICON_SIZE, not 256x256" >&2
    exit 1
fi
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp -a "$ICON" "$APPDIR/usr/share/icons/hicolor/256x256/apps/cmdly.png"
ln -sf cmdly.png "$APPDIR/.DirIcon"

# ---- 8. obtain appimagetool -------------------------------------------------
# The current appimagetool lives in github.com/AppImage/appimagetool (the old
# AppImageKit "continuous" build is abandoned). Its AppImages embed the static
# type2-runtime, so the result needs no libfuse2 on the target machine. Pinned
# to a release so a rebuild packs the same way; $CMDLY_APPIMAGETOOL_VERSION=
# continuous follows the newest build instead.
APPIMAGETOOL_VERSION="${CMDLY_APPIMAGETOOL_VERSION:-1.9.1}"
APPIMAGETOOL="$BUILD_DIR/appimagetool-${APPIMAGETOOL_VERSION}-${ARCH}.AppImage"
APPIMAGETOOL_URL="https://github.com/AppImage/appimagetool/releases/download/${APPIMAGETOOL_VERSION}/appimagetool-${ARCH}.AppImage"
if [ -x "$APPIMAGETOOL" ] && [ "$APPIMAGETOOL_VERSION" != "continuous" ]; then
    echo ">>> Using cached appimagetool $APPIMAGETOOL_VERSION"
else
    echo ">>> Downloading appimagetool $APPIMAGETOOL_VERSION ($ARCH) ..."
    download "$APPIMAGETOOL_URL" "$APPIMAGETOOL"
    chmod +x "$APPIMAGETOOL"
fi

# ---- 9. pack ----------------------------------------------------------------
# Three execution tiers. On a normal laptop the direct run works (FUSE mounts
# the appimagetool AppImage). Sandboxes without FUSE fall back to
# APPIMAGE_EXTRACT_AND_RUN=1. Sandboxes where binfmt_misc routes AppImage exec
# through a broken appimagelauncher interpreter need the third tier: manually
# unsquashfs the appimagetool AppImage and run its AppRun directly (a plain
# ELF, not intercepted by binfmt).
AIM_LOG="$BUILD_DIR/appimagetool.log"
: > "$AIM_LOG"

run_appimagetool_extracted() {  # <tool_appimage> <args...>
    local tool="$1"; shift
    local workdir="$BUILD_DIR/appimagetool-extracted"
    local sqfs="$BUILD_DIR/appimagetool.squashfs"
    rm -rf "$workdir" "$sqfs"
    # Find the embedded squashfs 4.0 superblock and slice the file from there.
    local result
    result="$(python3 - "$tool" "$sqfs" <<'PY' || true
import struct, re, sys
data = open(sys.argv[1], 'rb').read()
for m in re.finditer(b'hsqs', data):
    off = m.start()
    if off + 56 > len(data):
        continue
    sb = data[off:off + 56]
    s_major, s_minor = struct.unpack('<HH', sb[28:32])
    block_size = struct.unpack('<I', sb[12:16])[0]
    block_log = struct.unpack('<H', sb[22:24])[0]
    compression = struct.unpack('<H', sb[20:22])[0]
    bytes_used = struct.unpack('<Q', sb[40:48])[0]
    if (s_major == 4 and s_minor == 0 and block_size == (1 << block_log)
            and compression in (1, 2, 3, 4, 5, 6)
            and 0 < bytes_used <= len(data) - off):
        open(sys.argv[2], 'wb').write(data[off:])
        print("OK %d" % off)
        sys.exit(0)
print("FAIL")
sys.exit(1)
PY
)"
    case "$result" in
        OK\ *) ;;
        *) echo "ERROR: no valid squashfs superblock in $tool ($result)" >&2; return 1 ;;
    esac
    unsquashfs -force -d "$workdir" "$sqfs" || return 1
    [ -x "$workdir/AppRun" ] || { echo "ERROR: extracted AppRun missing" >&2; return 1; }
    ARCH="$ARCH" "$workdir/AppRun" "$@"
}

echo ">>> Packaging AppImage ..."
if ! ARCH="$ARCH" "$APPIMAGETOOL" "$APPDIR" "$OUTPUT" >>"$AIM_LOG" 2>&1; then
    echo ">>> Direct run failed; retrying with APPIMAGE_EXTRACT_AND_RUN=1 ..."
    if ! APPIMAGE_EXTRACT_AND_RUN=1 ARCH="$ARCH" "$APPIMAGETOOL" "$APPDIR" "$OUTPUT" >>"$AIM_LOG" 2>&1; then
        if command -v unsquashfs >/dev/null 2>&1; then
            echo ">>> Extract-and-run failed; manually unsquashfs-ing appimagetool (bypasses FUSE + binfmt) ..."
            if ! run_appimagetool_extracted "$APPIMAGETOOL" "$APPDIR" "$OUTPUT" >>"$AIM_LOG" 2>&1; then
                echo "ERROR: appimagetool failed; log: $AIM_LOG" >&2
                tail -n 20 "$AIM_LOG" >&2 || true
                exit 1
            fi
        else
            echo "ERROR: appimagetool failed and unsquashfs is not available; log: $AIM_LOG" >&2
            tail -n 20 "$AIM_LOG" >&2 || true
            exit 1
        fi
    fi
fi

SUCCESS=1
echo ""
echo ">>> Built: $OUTPUT"
echo "    (appimagetool log: $AIM_LOG)"
