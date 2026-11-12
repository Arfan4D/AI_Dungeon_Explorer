"""Generates assets/icon.ico (the explorer face) - pure Python, no Pillow needed.

    python tools/make_icon.py
"""
import math
import os
import struct
import zlib

SIZES = [32, 64, 128]
SUPER = 4          # supersampling for smooth edges


def shade(u, v):
    """Colour (r, g, b, a) at normalised position (u, v) in [0, 1]."""
    dx, dy = u - 0.5, v - 0.5
    # rounded-square backdrop
    rad = 0.2
    qx, qy = abs(dx) - (0.5 - rad), abs(dy) - (0.5 - rad)
    sdf = math.hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0) - rad
    if sdf > 0:
        return (0, 0, 0, 0)
    t = v
    color = (int(24 + 24 * t), int(18 + 12 * t), int(44 + 36 * t), 255)
    d = math.hypot(dx, dy - 0.02)
    if d < 0.335:                                    # outline
        color = (10, 60, 56, 255)
    if d < 0.30:                                     # body
        color = (60, 220, 200, 255)
    if math.hypot(dx + 0.10, dy + 0.11) < 0.07:      # shine
        color = (170, 255, 245, 255)
    for ex in (-0.095, 0.095):                       # eyes
        if math.hypot(dx - ex, dy - 0.0) < 0.045:
            color = (10, 30, 30, 255)
    if math.hypot(dx, dy - 0.155) < 0.055:           # key held by the explorer
        color = (255, 214, 64, 255)
    return color


def make_png(size):
    raw = bytearray()
    for y in range(size):
        raw.append(0)
        for x in range(size):
            acc = [0.0, 0.0, 0.0, 0.0]
            for sy in range(SUPER):
                for sx in range(SUPER):
                    r, g, b, a = shade((x + (sx + 0.5) / SUPER) / size, (y + (sy + 0.5) / SUPER) / size)
                    acc[0] += r * a
                    acc[1] += g * a
                    acc[2] += b * a
                    acc[3] += a
            n = SUPER * SUPER
            a = acc[3] / n
            if acc[3] > 0:
                raw += bytes([int(acc[0] / acc[3]), int(acc[1] / acc[3]), int(acc[2] / acc[3]), int(a)])
            else:
                raw += bytes([0, 0, 0, 0])

    def chunk(tag, data):
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))


def main():
    images = [(s, make_png(s)) for s in SIZES]
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries, blobs = b"", b""
    for size, png in images:
        entries += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(png), offset + len(blobs))
        blobs += png
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "icon.ico")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "wb") as fh:
        fh.write(header + entries + blobs)
    print("wrote", out)


if __name__ == "__main__":
    main()
