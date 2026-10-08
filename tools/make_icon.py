#!/usr/bin/env python3
"""Cut the app icon out of its artwork: ``assets/icon.jpeg`` -> ``assets/icon.png``
(1024 px) and ``assets/icon-256.png`` (the Linux launcher size).

The artwork is a JPEG, so the "transparent" checkerboard around the rounded
square is painted into it. This finds the dark tile (everything darker than
the checkerboard's lightest grey), crops to it, masks it with the rounded
square the macOS icon grid uses and centres it on a transparent 1024 px canvas
with the grid's margin, so the dock, the file manager and a Linux launcher all show the
tile alone, the same size as every other app icon beside it.

Run it again whenever the artwork changes; the build scripts read the PNG.

    .venv/bin/python tools/make_icon.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "assets" / "icon.jpeg"
TARGET = ROOT / "assets" / "icon.png"
# The Linux launcher icon: hicolor/256x256 wants exactly that size, and the
# AppImage build then needs no image tool of its own.
TARGET_256 = ROOT / "assets" / "icon-256.png"

CANVAS = 1024
# The macOS icon grid: an 824 px tile on a 1024 px canvas, corner radius
# about 22.5 % of the tile.
TILE = 824
RADIUS = 0.225
# The tile is near black, the checkerboard never darker than light grey.
DARK = 110


def main() -> int:
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPainterPath

    _app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
    src = QImage(str(SOURCE))
    if src.isNull():
        print(f"cannot read {SOURCE}", file=sys.stderr)
        return 1
    w, h = src.width(), src.height()
    xs, ys = [], []
    # Every fourth pixel is plenty to find a tile two thousand pixels wide.
    for y in range(0, h, 4):
        for x in range(0, w, 4):
            if QColor(src.pixel(x, y)).lightness() < DARK:
                xs.append(x)
                ys.append(y)
    if not xs:
        print("no dark tile found in the artwork", file=sys.stderr)
        return 1
    # A few pixels in from the found edge: the outermost ring is the tile's
    # own anti-aliased border blended into the checkerboard.
    inset = 6
    left, top = min(xs) + inset, min(ys) + inset
    side = min(max(xs) - min(xs), max(ys) - min(ys)) - 2 * inset
    tile = src.copy(left, top, side, side).scaled(
        TILE, TILE, Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation)

    out = QImage(CANVAS, CANVAS, QImage.Format.Format_ARGB32_Premultiplied)
    out.fill(Qt.GlobalColor.transparent)
    painter = QPainter(out)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    offset = (CANVAS - TILE) / 2
    path = QPainterPath()
    path.addRoundedRect(QRectF(offset, offset, TILE, TILE), TILE * RADIUS, TILE * RADIUS)
    painter.setClipPath(path)
    painter.drawImage(int(offset), int(offset), tile)
    painter.end()
    if not out.save(str(TARGET), "PNG"):
        print(f"cannot write {TARGET}", file=sys.stderr)
        return 1
    small = out.scaled(256, 256, Qt.AspectRatioMode.KeepAspectRatio,
                       Qt.TransformationMode.SmoothTransformation)
    if not small.save(str(TARGET_256), "PNG"):
        print(f"cannot write {TARGET_256}", file=sys.stderr)
        return 1
    print(f"{TARGET.relative_to(ROOT)}: {CANVAS}x{CANVAS}, tile {TILE} px "
          f"(cut from {side} px at {left},{top})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
