#!/usr/bin/env python3
"""A simple mountain-peak line mark. Emits SVG (header/favicon) and PWA PNGs.
Same geometry drives both. Pure stdlib (no rasteriser on the box)."""
import math, struct, zlib, sys

BG    = '#16130F'
CHALK = '#F1EDE6'
S = 512.0
SS = 4

# A two-peak ridge, second peak higher. Points read left->right.
RIDGE = [(84, 384), (196, 214), (262, 288), (344, 158), (432, 384)]
STROKE = 30  # full width

def mark(include_bg):
    p = []
    if include_bg:
        p.append(('rrect', 0, 0, 512, 512, 112, BG))
    p.append(('polyline', RIDGE, STROKE, CHALK))
    return p

# ---------- SVG ----------
def svg_body(prims):
    out = []
    for pr in prims:
        if pr[0] == 'rrect':
            _, x, y, w, h, r, c = pr
            out.append('<rect x="%g" y="%g" width="%g" height="%g" rx="%g" fill="%s"/>' % (x, y, w, h, r, c))
        elif pr[0] == 'polyline':
            _, pts, w, c = pr
            d = 'M' + ' L'.join('%g %g' % (px, py) for px, py in pts)
            out.append('<path d="%s" fill="none" stroke="%s" stroke-width="%g" '
                       'stroke-linecap="round" stroke-linejoin="round"/>' % (d, c, w))
    return ''.join(out)

def svg(include_bg):
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">'
            + svg_body(mark(include_bg)) + '</svg>')

# ---------- raster ----------
def hexrgb(h):
    h = h.lstrip('#'); return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

def seg_dist(px, py, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    wx, wy = px - ax, py - ay
    d = vx * vx + vy * vy
    t = 0 if d == 0 else max(0, min(1, (wx * vx + wy * vy) / d))
    return math.hypot(px - (ax + vx * t), py - (ay + vy * t))

def inside(pr, x, y):
    if pr[0] == 'rrect':
        _, rx, ry, w, h, r, _c = pr
        qx = abs(x - (rx + w / 2)) - (w / 2 - r)
        qy = abs(y - (ry + h / 2)) - (h / 2 - r)
        return math.hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0) - r <= 0
    if pr[0] == 'polyline':
        _, pts, w, _c = pr
        hw = w / 2.0
        for i in range(len(pts) - 1):
            if seg_dist(x, y, pts[i][0], pts[i][1], pts[i+1][0], pts[i+1][1]) <= hw:
                return True
        return False
    return False

def color_at(prims, x, y):
    col = None
    for pr in prims:
        if inside(pr, x, y):
            col = pr[-1]
    return col

def render(size, prims):
    scale = S / size
    rows = []
    for py in range(size):
        row = bytearray()
        for px in range(size):
            ar = ag = ab = aa = 0
            for sy in range(SS):
                for sx in range(SS):
                    c = color_at(prims, (px + (sx + .5) / SS) * scale, (py + (sy + .5) / SS) * scale)
                    if c is not None:
                        r, g, b = hexrgb(c); ar += r; ag += g; ab += b; aa += 255
            n = SS * SS; cov = aa / n
            if cov <= 0:
                row += b'\x00\x00\x00\x00'
            else:
                k = aa / 255.0
                row += bytes((round(ar / k), round(ag / k), round(ab / k), round(cov)))
        rows.append(bytes(row))
    return rows

def write_png(path, size, rows):
    raw = b''.join(b'\x00' + r for r in rows)
    def chunk(tag, data):
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)
    png = (b'\x89PNG\r\n\x1a\n'
           + chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 6, 0, 0, 0))
           + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))
    open(path, 'wb').write(png)

if __name__ == '__main__':
    out = sys.argv[1].rstrip('/') if len(sys.argv) > 1 else '.'
    for name, size in [('icon-192.png', 192), ('icon-512.png', 512),
                       ('icon-maskable-512.png', 512), ('icon-180.png', 180)]:
        write_png(out + '/' + name, size, render(size, mark(True)))
        print('wrote', name)
    open(out + '/mark.svg', 'w').write(svg(False))
    print('SVG_MARK:' + svg(False))
