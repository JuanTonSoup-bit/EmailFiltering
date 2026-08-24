"""Generate the extension's PNG icons.

    python make_icons.py

Writes icon16/32/48/128.png next to this file.

Why generate rather than commit a binary blob: the icons are then
reproducible and reviewable - you can read the shape out of the code instead
of taking a checked-in PNG on faith. It also avoids a Pillow dependency;
this writes PNG bytes directly with zlib, which is all the format needs for
a plain RGBA image.

The mark is a shield with a check cut out of it, rendered 4x and downsampled
for antialiasing.
"""

from __future__ import annotations

import pathlib
import struct
import zlib

# Categorical slot 1 blue - the same hue the dashboard uses for its accent.
SHIELD = (57, 135, 229)
CHECK = (255, 255, 255)

SS = 4  # supersampling factor


def _shield_contains(x: float, y: float) -> bool:
    """Is (x, y) inside the shield? x in [-1, 1], y in [0, 1] top to bottom."""
    if not (0.0 <= y <= 1.0):
        return False
    # Full width at the shoulders, tapering to a point at the bottom.
    half = 0.78 * (1.0 - y**2.4)
    if abs(x) > half:
        return False
    # Round off the top corners so it reads as a shield, not a tombstone.
    if y < 0.16:
        corner = (abs(x) - 0.52) / 0.26
        if corner > 0:
            dy = (0.16 - y) / 0.16
            if corner * corner + dy * dy > 1.0:
                return False
    return True


def _segment_distance(px, py, ax, ay, bx, by) -> float:
    """Distance from point to line segment ab."""
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return ((px - ax) ** 2 + (py - ay) ** 2) ** 0.5
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
    cx, cy = ax + t * dx, ay + t * dy
    return ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5


def _check_contains(x: float, y: float, thickness: float) -> bool:
    """The check mark: a short down-stroke into a long up-stroke."""
    short = _segment_distance(x, y, -0.30, 0.46, -0.08, 0.64)
    long_ = _segment_distance(x, y, -0.08, 0.64, 0.34, 0.26)
    return min(short, long_) <= thickness


def render(size: int) -> bytes:
    """Render one icon as raw RGBA rows."""
    thickness = 0.10 if size >= 48 else 0.13  # keep the check visible at 16px
    rows = []
    for py in range(size):
        row = bytearray()
        for px in range(size):
            r = g = b = a = 0
            hits = 0
            for sy in range(SS):
                for sx in range(SS):
                    # Sample at subpixel centres, mapped into shield space.
                    fx = (px + (sx + 0.5) / SS) / size
                    fy = (py + (sy + 0.5) / SS) / size
                    x = (fx - 0.5) * 2.0
                    y = (fy - 0.04) / 0.92
                    if not _shield_contains(x, y):
                        continue
                    hits += 1
                    color = CHECK if _check_contains(x, y, thickness) else SHIELD
                    r += color[0]
                    g += color[1]
                    b += color[2]
            total = SS * SS
            if hits:
                r, g, b = r // hits, g // hits, b // hits
                a = (255 * hits) // total
            row += bytes((r, g, b, a))
        rows.append(bytes(row))
    return b"".join(b"\x00" + row for row in rows)


def write_png(path: pathlib.Path, size: int) -> None:
    raw = render(size)

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(
            ">I", zlib.crc32(body) & 0xFFFFFFFF
        )

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9))
    png += chunk(b"IEND", b"")
    path.write_bytes(png)
    print(f"  {path.name:<14} {size}x{size}  {len(png):>6} bytes")


def main() -> None:
    here = pathlib.Path(__file__).parent
    print("Writing icons:")
    for size in (16, 32, 48, 128):
        write_png(here / f"icon{size}.png", size)


if __name__ == "__main__":
    main()
