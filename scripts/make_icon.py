"""Generate a Windows .ico from the canonical assets/hdm.png."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path


def _write_png(path: Path, size: int = 256) -> None:
    """Minimal PNG writer (blue tile + white HDM text via simple rects)."""
    width = height = size
    rows = []
    bg = (44, 82, 130)
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            # rounded rect margin
            margin = size // 16
            if margin <= x < width - margin and margin <= y < height - margin:
                # simple "HDM" block letters in center band
                cx, cy = width // 2, height // 2
                in_band = abs(y - cy) < size // 5
                in_h = abs(x - (cx - size // 5)) < size // 28 and in_band
                in_d = abs(x - (cx + size // 8)) < size // 28 and in_band
                in_m = cx - size // 12 < x < cx + size // 12 and in_band
                if in_h or in_d or (in_m and (x < cx or x > cx + size // 40)):
                    row.extend((255, 255, 255))
                else:
                    row.extend(bg)
            else:
                row.extend(bg)
        rows.append(bytes(row))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    raw = b"".join(rows)
    compressed = zlib.compress(raw, 9)
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", ihdr)
    png += chunk(b"IDAT", compressed)
    png += chunk(b"IEND", b"")
    path.write_bytes(png)


def _write_ico(path: Path, png_path: Path, *, size: int = 48) -> None:
    """Single-size ICO embedding a PNG (Windows Vista+)."""
    png = png_path.read_bytes()
    header = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack("<BBBBHHII", size, size, 0, 0, 1, 32, len(png), 22)
    path.write_bytes(header + entry + png)


def _png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"Not a PNG file: {path}")
    if data[12:16] != b"IHDR":
        raise ValueError(f"Missing PNG IHDR chunk: {path}")
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    assets = root / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    png = assets / "hdm.png"
    ico = assets / "hdm.ico"

    if not png.is_file():
        _write_png(png, size=256)
        print(f"Created placeholder {png}")

    width, height = _png_size(png)
    if width != height:
        raise ValueError(f"Icon PNG must be square, got {width}x{height}: {png}")

    # ICO stores 256 as 0 in the width/height directory bytes.
    ico_size = 0 if width >= 256 else width
    _write_ico(ico, png, size=ico_size)
    print(f"Wrote {ico} from {png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
