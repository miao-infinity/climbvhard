#!/usr/bin/env python3
"""Rasterize the CRUX mark to PNG. Pure stdlib: no PIL, no rsvg.

Mirrors the inline SVG in index.html:
  512x512, rounded rect r=96 fill #16130F, an X of two round-capped
  strokes width 58 from 156,156->356,356 and 356,156->156,356 in #E5484D.
"""
import math, struct, zlib, sys

BG = (0x16, 0x13, 0x0F)
FG = (0xE5, 0x48, 0x4D)
S = 512.0          # design-space size
RADIUS = 96.0
STROKE = 58.0
A, B = 156.0, 356.0
SS = 4             # supersample factor per axis


def sd_round_rect(px, py, half, r):
    qx = abs(px - half) - (half - r)
    qy = abs(py - half) - (half - r)
    return math.hypot(max(qx, 0.0), max(qy, 0.0)) + min(max(qx, qy), 0.0) - r


def sd_segment(px, py, ax, ay, bx, by):
    pax, pay = px - ax, py - ay
    bax, bay = bx - ax, by - ay
    denom = bax * bax + bay * bay
    h = max(0.0, min(1.0, (pax * bax + pay * bay) / denom))
    return math.hypot(pax - bax * h, pay - bay * h)


def sample(px, py, full_bleed):
    """Return (r,g,b,a) at design-space point."""
    inside_bg = True if full_bleed else sd_round_rect(px, py, S / 2.0, RADIUS) <= 0.0
    if not inside_bg:
        return (0, 0, 0, 0)
    d = min(sd_segment(px, py, A, A, B, B), sd_segment(px, py, B, A, A, B))
    if d <= STROKE / 2.0:
        return (FG[0], FG[1], FG[2], 255)
    return (BG[0], BG[1], BG[2], 255)


def render(size, full_bleed):
    scale = S / size
    rows = []
    for y in range(size):
        row = bytearray()
        for x in range(size):
            ar = ag = ab = aa = 0
            for sy in range(SS):
                for sx in range(SS):
                    px = (x + (sx + 0.5) / SS) * scale
                    py = (y + (sy + 0.5) / SS) * scale
                    r, g, b, a = sample(px, py, full_bleed)
                    # accumulate premultiplied to avoid edge fringing
                    ar += r * a; ag += g * a; ab += b * a; aa += a
            n = SS * SS
            aa_avg = aa / n
            if aa_avg <= 0:
                row += b"\x00\x00\x00\x00"
            else:
                row += bytes((
                    round(ar / aa), round(ag / aa), round(ab / aa), round(aa_avg),
                ))
        rows.append(bytes(row))
    return rows


def write_png(path, size, rows):
    raw = b"".join(b"\x00" + r for r in rows)

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", zlib.compress(raw, 9))
           + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


TARGETS = [
    ("icon-192.png", 192, False),
    ("icon-512.png", 512, False),
    ("icon-maskable-512.png", 512, True),
    ("icon-180.png", 180, True),   # apple-touch-icon: opaque, iOS masks it itself
]

if __name__ == "__main__":
    out = sys.argv[1].rstrip("/")
    for name, size, full in TARGETS:
        n = write_png(out + "/" + name, size, render(size, full))
        print("%-24s %4dpx  %6d bytes  %s" % (name, size, n, "full-bleed" if full else "rounded"))
