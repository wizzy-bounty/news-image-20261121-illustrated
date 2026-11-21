#!/usr/bin/env python3
"""THE WORLD IN ONE DAY - an illustrated one-page broadsheet summing up the
world news of Saturday 21 November 2026. Pure stdlib: own rasteriser, own
world map, own pictorial illustrations, baked glyph data (fontdata.py).
Writes /output/entry.png (1024x1024 PNG), deterministic."""
import os, sys, zlib, base64, struct, math

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fontdata import FONTS

SS = 2                      # supersample factor
W = H = 1024                # final size
CW = CH = W * SS            # canvas size

# ---------------------------------------------------------------- fonts
_fontcache = {}
def font(name):
    if name in _fontcache:
        return _fontcache[name]
    d = FONTS[name]
    blob = zlib.decompress(base64.b85decode(d["blob"]))
    _fontcache[name] = (d["ascent"], d["descent"], d["glyphs"], blob)
    return _fontcache[name]

def text_w(s, name):
    asc, desc, glyphs, blob = font(name)
    return sum(glyphs.get(ch, glyphs["?"])[2] for ch in s) / SS

def wrap(s, name, maxw):
    words = s.split()
    lines, cur = [], ""
    for wd in words:
        t = (cur + " " + wd).strip()
        if text_w(t, name) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines

# ---------------------------------------------------------------- canvas
class Canvas:
    def __init__(self):
        self.px = bytearray(CW * CH * 4)

    def _span(self, x0, x1, y, rgb):
        if y < 0 or y >= CH or x1 < 0 or x0 >= CW:
            return
        x0 = max(0, x0); x1 = min(CW - 1, x1)
        if x1 < x0:
            return
        i = (y * CW + x0) * 4
        n = x1 - x0 + 1
        self.px[i:i + n * 4] = bytes((rgb[0], rgb[1], rgb[2], 0)) * n

    def rect(self, x, y, w, h, rgb):
        X, Y = int(x * SS), int(y * SS)
        X1, Y1 = int((x + w) * SS) - 1, int((y + h) * SS) - 1
        for yy in range(Y, Y1 + 1):
            self._span(X, X1, yy, rgb)

    def vgrad(self, x, y, w, h, top, bot):
        Y, Y1 = int(y * SS), int((y + h) * SS)
        for yy in range(Y, Y1):
            t = (yy - Y) / max(1, Y1 - Y)
            c = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3))
            self._span(int(x * SS), int((x + w) * SS) - 1, yy, c)

    def blend_px(self, x, y, rgb, a):
        if 0 <= x < CW and 0 <= y < CH and a > 0:
            i = (y * CW + x) * 4
            if a >= 255:
                self.px[i:i + 3] = bytes(rgb)
            else:
                ia = 255 - a
                self.px[i] = (self.px[i] * ia + rgb[0] * a) // 255
                self.px[i + 1] = (self.px[i + 1] * ia + rgb[1] * a) // 255
                self.px[i + 2] = (self.px[i + 2] * ia + rgb[2] * a) // 255

    def disc(self, cx, cy, r, rgb, a=255):
        CX, CY, R = int(cx * SS), int(cy * SS), int(r * SS)
        for yy in range(CY - R, CY + R + 1):
            dx = int(math.sqrt(max(0, R * R - (yy - CY) ** 2)))
            if a >= 255:
                self._span(CX - dx, CX + dx, yy, rgb)
            else:
                for xx in range(CX - dx, CX + dx + 1):
                    self.blend_px(xx, yy, rgb, a)

    def ring(self, cx, cy, r, rgb, wdt=1.6):
        CX, CY, R = int(cx * SS), int(cy * SS), r * SS
        steps = max(24, int(2 * math.pi * R))
        for i in range(steps):
            t = 2 * math.pi * i / steps
            self.disc(cx + r * math.cos(t), cy + r * math.sin(t), wdt / 2, rgb)

    def line(self, x0, y0, x1, y1, rgb, wdt=1.4, a=255):
        n = int(max(abs(x1 - x0), abs(y1 - y0)) * SS) + 1
        for i in range(n + 1):
            t = i / n
            self.disc(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, wdt / 2, rgb, a)

    def polyline(self, pts, rgb, wdt=1.4, a=255, close=False):
        p = pts + [pts[0]] if close else pts
        for i in range(len(p) - 1):
            self.line(p[i][0], p[i][1], p[i + 1][0], p[i + 1][1], rgb, wdt, a)

    def poly(self, pts, rgb):
        P = [(x * SS, y * SS) for x, y in pts]
        ys = [p[1] for p in P]
        y0, y1 = max(0, int(min(ys))), min(CH - 1, int(max(ys)))
        n = len(P)
        for yy in range(y0, y1 + 1):
            xs = []
            for i in range(n):
                xa, ya = P[i]
                xb, yb = P[(i + 1) % n]
                if (ya <= yy < yb) or (yb <= yy < ya):
                    xs.append(xa + (xb - xa) * (yy - ya) / (yb - ya))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                self._span(int(xs[i]), int(xs[i + 1]), yy, rgb)

    def text(self, x, y, s, name, rgb, align="l"):
        asc, desc, glyphs, blob = font(name)
        w = sum(glyphs.get(ch, glyphs["?"])[2] for ch in s)
        if align == "c":
            pen = int(x * SS - w / 2)
        elif align == "r":
            pen = int(x * SS - w)
        else:
            pen = int(x * SS)
        base = int(y * SS)
        for ch in s:
            gw, gh, adv, xo, yo, off = glyphs.get(ch, glyphs["?"])
            if gw and gh:
                for gy in range(gh):
                    yy = base + yo + gy
                    if yy < 0 or yy >= CH:
                        continue
                    row = blob[off + gy * gw: off + (gy + 1) * gw]
                    xx0 = pen + xo
                    for gx, av in enumerate(row):
                        if av:
                            self.blend_px(xx0 + gx, yy, rgb, av)
            pen += adv
        return w / SS

    def text_block(self, x, y, lines, name, rgb, lh, align="l"):
        asc, desc, _, _ = font(name)
        step = lh
        for i, ln in enumerate(lines):
            self.text(x, y + i * step, ln, name, rgb, align)
        return y + len(lines) * step

    def downscale(self):
        out = bytearray(W * H * 3)
        px = self.px
        for y in range(H):
            r0 = (2 * y) * CW * 4
            r1 = (2 * y + 1) * CW * 4
            o = y * W * 3
            for x in range(W):
                i0 = r0 + 8 * x
                i1 = r1 + 8 * x
                o3 = o + 3 * x
                out[o3] = (px[i0] + px[i0 + 4] + px[i1] + px[i1 + 4]) >> 2
                out[o3 + 1] = (px[i0 + 1] + px[i0 + 5] + px[i1 + 1] + px[i1 + 5]) >> 2
                out[o3 + 2] = (px[i0 + 2] + px[i0 + 6] + px[i1 + 2] + px[i1 + 6]) >> 2
        return out

def save_png(rgb, path):
    raw = bytearray()
    stride = W * 3
    for y in range(H):
        raw.append(0)
        raw += rgb[y * stride:(y + 1) * stride]
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return len(png)

# ---------------------------------------------------------------- palette
PAPER = (247, 242, 231)
PAPER2 = (240, 233, 214)
INK = (26, 32, 44)
GREY = (96, 102, 112)
RED = (178, 30, 42)
DARKRED = (128, 20, 30)
NAVY = (23, 54, 93)
SKY = (146, 190, 224)
GOLD = (217, 154, 22)
TEAL = (14, 122, 109)
WHITE = (255, 255, 255)
BLACK = (10, 12, 18)

REGION = {
    "EUROPE": (36, 86, 166),
    "ASIA-PACIFIC": (14, 122, 109),
    "NORTH AMERICA": (178, 30, 42),
    "MIDDLE EAST": (194, 106, 27),
    "AFRICA": (122, 79, 163),
    "LATIN AMERICA": (209, 73, 91),
    "OCEANIA": (43, 127, 184),
    "GLOBAL": (90, 96, 108),
}

# ---------------------------------------------------------------- icons
def icon(c, kind, x, y, s, col):
    """Small pictograms, drawn with primitives. (x,y) = top-left, s = box."""
    u = s / 24.0
    cx, cy = x + s / 2, y + s / 2
    if kind == "coin":
        c.disc(cx, cy, 10 * u, GOLD)
        c.ring(cx, cy, 10 * u, col, 1.6)
        c.text(cx, cy - 8 * u, "€", "bold_card", col, "c")
    elif kind == "aid":
        c.poly([(x + 3 * u, y + 14 * u), (x + 21 * u, y + 14 * u), (x + 19 * u, y + 21 * u), (x + 5 * u, y + 21 * u)], col)
        c.line(x + 12 * u, y + 3 * u, x + 12 * u, y + 14 * u, col, 2.6)
        c.line(x + 7 * u, y + 9 * u, x + 12 * u, y + 14 * u, col, 2.4)
        c.line(x + 17 * u, y + 9 * u, x + 12 * u, y + 14 * u, col, 2.4)
    elif kind == "rugby":
        c.poly([(x + 4 * u, y + 12 * u), (x + 9 * u, y + 5 * u), (x + 19 * u, y + 5 * u), (x + 20 * u, y + 12 * u),
                (x + 19 * u, y + 19 * u), (x + 9 * u, y + 19 * u), (x + 4 * u, y + 19 * u)], col)
        for i in range(3):
            c.line(x + (10 + i * 2.4) * u, y + 10 * u, x + (10 + i * 2.4) * u, y + 14 * u, WHITE, 1.1)
    elif kind == "chart":
        c.line(x + 3 * u, y + 21 * u, x + 21 * u, y + 21 * u, col, 1.8)
        for i, hh in enumerate((7, 12, 9, 15)):
            c.rect(x + (4.5 + i * 4.4) * u, y + (21 - hh) * u, 3 * u, hh * u, col)
    elif kind == "chip":
        c.rect(x + 6 * u, y + 6 * u, 12 * u, 12 * u, col)
        c.rect(x + 9.5 * u, y + 9.5 * u, 5 * u, 5 * u, PAPER)
        for i in range(3):
            for xx in (3, 21):
                c.line(x + xx * u, y + (8 + i * 4) * u, x + (xx + (3 if xx == 3 else -3)) * u, y + (8 + i * 4) * u, col, 1.6)
            c.line(x + (8 + i * 4) * u, y + 3 * u, x + (8 + i * 4) * u, y + 6 * u, col, 1.6)
            c.line(x + (8 + i * 4) * u, y + 18 * u, x + (8 + i * 4) * u, y + 21 * u, col, 1.6)
    elif kind == "rocket":
        c.poly([(cx, y + 2 * u), (x + 17 * u, y + 10 * u), (x + 15 * u, y + 17 * u), (x + 9 * u, y + 17 * u), (x + 7 * u, y + 10 * u)], col)
        c.disc(cx, y + 9 * u, 2.4 * u, PAPER)
        c.poly([(x + 9 * u, y + 17 * u), (cx, y + 23 * u), (x + 15 * u, y + 17 * u)], GOLD)
    elif kind == "factory":
        c.rect(x + 3 * u, y + 13 * u, 18 * u, 8 * u, col)
        c.poly([(x + 5 * u, y + 5 * u), (x + 9 * u, y + 5 * u), (x + 9 * u, y + 13 * u), (x + 5 * u, y + 13 * u)], col)
        c.poly([(x + 13 * u, y + 3 * u), (x + 17 * u, y + 3 * u), (x + 17 * u, y + 13 * u), (x + 13 * u, y + 13 * u)], col)
        c.disc(x + 7 * u, y + 3 * u, 2 * u, GREY)
        c.disc(x + 15 * u, y + 1.6 * u, 2.4 * u, GREY)
    elif kind == "fire":
        c.poly([(cx, y + 2 * u), (x + 17 * u, y + 12 * u), (x + 15 * u, y + 20 * u), (x + 9 * u, y + 20 * u), (x + 7 * u, y + 12 * u)], RED)
        c.poly([(cx, y + 10 * u), (x + 14 * u, y + 15 * u), (x + 13 * u, y + 20 * u), (x + 11 * u, y + 20 * u), (x + 10 * u, y + 15 * u)], GOLD)
    elif kind == "shield":
        c.poly([(cx, y + 2 * u), (x + 20 * u, y + 5 * u), (x + 20 * u, y + 13 * u), (cx, y + 22 * u), (x + 4 * u, y + 13 * u), (x + 4 * u, y + 5 * u)], col)
        c.polyline([(x + 8.5 * u, y + 11 * u), (x + 11 * u, y + 14 * u), (x + 16 * u, y + 8 * u)], WHITE, 2.0)
    elif kind == "lock":
        c.rect(x + 5 * u, y + 11 * u, 14 * u, 10 * u, col)
        c.ring(cx, y + 11 * u, 5.4 * u, col, 2.2)
        c.disc(cx, y + 16 * u, 1.8 * u, PAPER)
    elif kind == "gavel":
        c.line(x + 6 * u, y + 18 * u, x + 18 * u, y + 6 * u, col, 3.0)
        c.rect(x + 13 * u, y + 2 * u, 8 * u, 5 * u, col)
        c.line(x + 3 * u, y + 21.5 * u, x + 12 * u, y + 21.5 * u, col, 2.2)
    elif kind == "scale":
        c.line(cx, y + 4 * u, cx, y + 19 * u, col, 2.0)
        c.line(x + 5 * u, y + 6 * u, x + 19 * u, y + 6 * u, col, 2.0)
        for xx in (5, 19):
            c.polyline([(x + xx * u, y + 6 * u), (x + (xx - 2.6) * u, y + 12 * u), (x + (xx + 2.6) * u, y + 12 * u)], col, 1.3)
            c.line(x + (xx - 3) * u, y + 12 * u, x + (xx + 3) * u, y + 12 * u, col, 1.8)
        c.line(x + 8 * u, y + 21 * u, x + 16 * u, y + 21 * u, col, 2.2)
    elif kind == "syringe":
        c.line(x + 5 * u, y + 19 * u, x + 15 * u, y + 9 * u, col, 3.2)
        c.line(x + 15 * u, y + 9 * u, x + 20 * u, y + 4 * u, col, 2.4)
        c.line(x + 17 * u, y + 2 * u, x + 22 * u, y + 7 * u, col, 2.0)
        c.line(x + 5 * u, y + 19 * u, x + 2 * u, y + 22 * u, col, 1.6)
    elif kind == "flag":
        c.line(x + 6 * u, y + 3 * u, x + 6 * u, y + 21 * u, col, 2.0)
        c.poly([(x + 6 * u, y + 3 * u), (x + 20 * u, y + 5 * u), (x + 6 * u, y + 10 * u)], col)
    elif kind == "train":
        c.rect(x + 4 * u, y + 6 * u, 16 * u, 10 * u, col)
        c.rect(x + 6.4 * u, y + 8.4 * u, 4.6 * u, 3.6 * u, PAPER)
        c.rect(x + 13 * u, y + 8.4 * u, 4.6 * u, 3.6 * u, PAPER)
        c.disc(x + 8 * u, y + 19 * u, 1.8 * u, col)
        c.disc(x + 16 * u, y + 19 * u, 1.8 * u, col)
        c.line(x + 3 * u, y + 22 * u, x + 21 * u, y + 22 * u, col, 1.6)
    elif kind == "hockey":
        c.line(x + 7 * u, y + 3 * u, x + 7 * u, y + 17 * u, col, 2.4)
        c.line(x + 7 * u, y + 17 * u, x + 15 * u, y + 17 * u, col, 2.4)
        c.line(x + 17 * u, y + 3 * u, x + 17 * u, y + 17 * u, col, 2.4)
        c.line(x + 17 * u, y + 17 * u, x + 9 * u, y + 17 * u, col, 2.4)
        c.disc(cx, y + 20.4 * u, 1.7 * u, col)
    elif kind == "shuttle":
        for dx in (-5, 0, 5):
            c.line(cx + dx * u, y + 3 * u, cx, y + 13 * u, col, 1.5)
        c.line(x + 6 * u, y + 3 * u, x + 18 * u, y + 3 * u, col, 1.5)
        c.poly([(x + 8 * u, y + 13 * u), (x + 16 * u, y + 13 * u), (x + 15 * u, y + 20 * u), (x + 9 * u, y + 20 * u)], col)
    elif kind == "ship":
        c.poly([(x + 3 * u, y + 16 * u), (x + 21 * u, y + 16 * u), (x + 18 * u, y + 21 * u), (x + 6 * u, y + 21 * u)], col)
        c.rect(x + 9 * u, y + 11 * u, 7 * u, 5 * u, col)
        c.line(x + 12.5 * u, y + 4 * u, x + 12.5 * u, y + 11 * u, col, 1.8)
    elif kind == "oil":
        c.poly([(cx, y + 3 * u), (x + 17 * u, y + 13 * u), (x + 15.4 * u, y + 19 * u), (x + 8.6 * u, y + 19 * u), (x + 7 * u, y + 13 * u)], col)
        c.disc(x + 10.6 * u, y + 15.6 * u, 1.7 * u, PAPER)
    elif kind == "crown":
        c.poly([(x + 3 * u, y + 18 * u), (x + 3 * u, y + 9 * u), (x + 8 * u, y + 13 * u), (cx, y + 6 * u), (x + 16 * u, y + 13 * u), (x + 21 * u, y + 9 * u), (x + 21 * u, y + 18 * u)], GOLD)
        c.rect(x + 3 * u, y + 18 * u, 18 * u, 2.6 * u, col)
    elif kind == "coal":
        c.poly([(x + 4 * u, y + 18 * u), (x + 8 * u, y + 8 * u), (x + 16 * u, y + 6 * u), (x + 21 * u, y + 14 * u), (x + 19 * u, y + 18 * u)], col)
        c.line(x + 9 * u, y + 12 * u, x + 13 * u, y + 10 * u, PAPER, 1.4)
    elif kind == "cross":
        c.rect(cx - 2.4 * u, y + 4 * u, 4.8 * u, 16 * u, RED)
        c.rect(cx - 8 * u, y + 9.6 * u, 16 * u, 4.8 * u, RED)
    elif kind == "ball":
        c.disc(cx, cy, 9.6 * u, col)
        c.ring(cx, cy, 9.6 * u, INK, 1.2)
        c.poly([(cx, cy - 3 * u), (x + 15 * u, cy + 1 * u), (x + 13.4 * u, cy + 5 * u), (x + 10.6 * u, cy + 5 * u), (x + 9 * u, cy + 1 * u)], PAPER)
    elif kind == "car":
        c.poly([(x + 3 * u, y + 15 * u), (x + 6 * u, y + 9 * u), (x + 18 * u, y + 9 * u), (x + 21 * u, y + 15 * u), (x + 21 * u, y + 18 * u), (x + 3 * u, y + 18 * u)], col)
        c.disc(x + 7.4 * u, y + 18.4 * u, 2.2 * u, INK)
        c.disc(x + 16.6 * u, y + 18.4 * u, 2.2 * u, INK)
    elif kind == "paw":
        c.disc(cx, y + 15.4 * u, 5 * u, col)
        for dx, dy in ((-7.4, 7.4), (-2.6, 4.6), (2.6, 4.6), (7.4, 7.4)):
            c.disc(cx + dx * u, y + dy * u, 2 * u, col)
    else:  # dot
        c.disc(cx, cy, 6 * u, col)

# ---------------------------------------------------------------- hero art
def hero_lead(c, x, y, w, h):
    """Missiles + drone down over a border landscape, dusk sky."""
    c.vgrad(x, y, w, h, (38, 52, 96), (214, 116, 66))
    # distant hills + ground
    c.poly([(x, y + h * 0.68), (x + w * 0.25, y + h * 0.58), (x + w * 0.5, y + h * 0.66),
            (x + w * 0.78, y + h * 0.56), (x + w, y + h * 0.64), (x + w, y + h), (x, y + h)], (58, 74, 52))
    c.rect(x, y + h * 0.8, w, h * 0.2, (40, 56, 38))
    # houses
    for hx, hs in ((0.08, 1.0), (0.3, 0.7), (0.62, 0.85), (0.85, 0.65)):
        bx, by = x + w * hx, y + h * 0.8
        c.rect(bx, by, 26 * hs, 15 * hs, (24, 26, 34))
        c.poly([(bx - 3 * hs, by), (bx + 13 * hs, by - 10 * hs), (bx + 29 * hs, by)], (14, 15, 22))
        c.rect(bx + 9 * hs, by + 5 * hs, 6 * hs, 6 * hs, GOLD)
    # smoke trails (dashed arcs) + two missiles
    def trail(x0, y0, x1, y1, bend):
        pts = []
        for i in range(25):
            t = i / 24
            xx = x0 + (x1 - x0) * t
            yy = y0 + (y1 - y0) * t - bend * math.sin(math.pi * t)
            pts.append((xx, yy))
        for i in range(0, 24, 2):
            c.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], (235, 230, 220), 2.2, 200)
        return pts[-1]
    ex, ey = trail(x + w * 0.06, y + h * 0.10, x + w * 0.52, y + h * 0.52, 26)
    # missile 1 at trail end, angled down-right
    mx, my = ex, ey
    c.poly([(mx, my), (mx + 34, my + 15), (mx + 30, my + 22), (mx - 4, my + 8)], (226, 228, 232))
    c.poly([(mx - 4, my + 8), (mx - 14, my + 2), (mx - 8, my - 6)], (190, 60, 50))
    c.poly([(mx + 2, my + 18), (mx - 8, my + 26), (mx + 8, my + 24)], (190, 60, 50))
    c.poly([(mx + 30, my + 22), (mx + 44, my + 30), (mx + 34, my + 15)], (240, 160, 60))
    ex2, ey2 = trail(x + w * 0.3, y + h * 0.04, x + w * 0.8, y + h * 0.44, 18)
    c.poly([(ex2, ey2), (ex2 + 26, ey2 + 11), (ex2 + 22, ey2 + 17), (ex2 - 3, ey2 + 6)], (210, 212, 216))
    c.poly([(ex2 + 22, ey2 + 17), (ex2 + 33, ey2 + 23), (ex2 + 26, ey2 + 11)], (240, 160, 60))
    # explosion starbursts where they came down
    for bx, by, bs in ((0.55, 0.78, 15), (0.83, 0.7, 11)):
        cx0, cy0 = x + w * bx, y + h * by
        for k in range(8):
            t = 2 * math.pi * k / 8
            c.line(cx0, cy0, cx0 + bs * math.cos(t), cy0 + bs * math.sin(t), (255, 176, 66), 2.6)
        c.disc(cx0, cy0, 4.5, (255, 214, 110))
        c.disc(cx0, cy0 - 12, 6, (90, 88, 88), 150)
        c.disc(cx0 + 6, cy0 - 20, 8, (90, 88, 88), 110)
    # jet drone silhouette (top right)
    dx, dy = x + w * 0.78, y + h * 0.14
    c.poly([(dx, dy), (dx + 44, dy + 6), (dx + 58, dy + 16), (dx + 40, dy + 15), (dx + 30, dy + 24),
            (dx + 24, dy + 14), (dx + 4, dy + 12)], (20, 22, 30))
    c.poly([(dx + 6, dy + 1), (dx - 8, dy - 8), (dx + 2, dy - 10), (dx + 16, dy - 2)], (20, 22, 30))
    c.text(x + 8, y + 6, "ILLUSTRATION: THE NIGHT SKY OVER SOUTH-EAST POLAND", "sans_mini", (240, 236, 220))

def hero_cop(c, x, y, w, h):
    """Climate summit: globe, thermometer, factory, protest placards."""
    c.vgrad(x, y, w, h, (16, 66, 84), (64, 138, 128))
    # globe
    gx, gy, gr = x + w * 0.30, y + h * 0.52, h * 0.34
    c.disc(gx, gy, gr, (52, 116, 178))
    c.poly([(gx - gr * 0.7, gy - gr * 0.5), (gx - gr * 0.2, gy - gr * 0.75), (gx + gr * 0.1, gy - gr * 0.45),
            (gx - gr * 0.15, gy - gr * 0.15), (gx - gr * 0.62, gy - gr * 0.1)], (74, 160, 92))
    c.poly([(gx + gr * 0.25, gy + gr * 0.1), (gx + gr * 0.65, gy - gr * 0.05), (gx + gr * 0.8, gy + gr * 0.35),
            (gx + gr * 0.4, gy + gr * 0.55), (gx + gr * 0.15, gy + gr * 0.3)], (74, 160, 92))
    c.poly([(gx - gr * 0.55, gy + gr * 0.35), (gx - gr * 0.2, gy + gr * 0.25), (gx - gr * 0.05, gy + gr * 0.6),
            (gx - gr * 0.4, gy + gr * 0.75)], (196, 164, 92))
    c.ring(gx, gy, gr, (220, 240, 250), 1.6)
    # thermometer
    tx = x + w * 0.60
    c.rect(tx, y + h * 0.14, 11, h * 0.52, (232, 236, 238))
    c.rect(tx + 2, y + h * 0.30, 7, h * 0.36, RED)
    c.disc(tx + 5.5, y + h * 0.72, 10, RED)
    c.disc(tx + 5.5, y + h * 0.72, 5.5, (240, 120, 110))
    for i in range(4):
        c.line(tx + 11, y + h * (0.2 + i * 0.11), tx + 17, y + h * (0.2 + i * 0.11), WHITE, 1.4)
    # factory silhouette
    fy = y + h * 0.86
    c.rect(x + w * 0.68, fy - 26, w * 0.3, 26, (18, 30, 40))
    c.poly([(x + w * 0.70, fy - 26), (x + w * 0.73, fy - 48), (x + w * 0.765, fy - 48), (x + w * 0.78, fy - 26)], (18, 30, 40))
    c.poly([(x + w * 0.84, fy - 26), (x + w * 0.865, fy - 56), (x + w * 0.895, fy - 56), (x + w * 0.91, fy - 26)], (18, 30, 40))
    c.disc(x + w * 0.75, fy - 56, 7, (200, 204, 208), 130)
    c.disc(x + w * 0.885, fy - 66, 9, (200, 204, 208), 110)
    # placards
    for i, word in enumerate(("NO", "DEAL", "YET")):
        px0 = x + w * (0.06 + i * 0.13)
        py0 = y + h * 0.60
        ph = max(13, h * 0.16)
        c.rect(px0, py0, w * 0.115, ph, (244, 240, 228))
        c.text(px0 + w * 0.057, py0 + 1, word, "sans_mini", DARKRED, "c")
        c.line(px0 + w * 0.057, py0 + ph, px0 + w * 0.057, py0 + ph + 5, (60, 44, 30), 2.0)

def hero_markets(c, x, y, w, h):
    """Falling chart over a night skyline."""
    c.vgrad(x, y, w, h, (12, 18, 38), (30, 40, 74))
    for gx in range(1, 8):
        c.line(x + w * gx / 8, y + 6, x + w * gx / 8, y + h - 4, (52, 66, 104), 0.8)
    for gy in range(1, 4):
        c.line(x + 6, y + h * gy / 4, x + w - 6, y + h * gy / 4, (52, 66, 104), 0.8)
    # candlesticks
    vals = [(0.30, 0.42), (0.36, 0.46), (0.33, 0.40), (0.44, 0.55), (0.50, 0.60), (0.56, 0.68), (0.63, 0.78)]
    for i, (a, b) in enumerate(vals):
        cx0 = x + w * (0.08 + i * 0.115)
        col = (224, 72, 72) if i > 0 else (70, 190, 120)
        c.line(cx0 + 5, y + h * (a - 0.07), cx0 + 5, y + h * (b + 0.05), col, 1.6)
        c.rect(cx0, y + h * a, 10, h * (b - a), col)
    # plunge line + arrow
    pts = [(x + w * 0.06, y + h * 0.30), (x + w * 0.3, y + h * 0.38), (x + w * 0.5, y + h * 0.52),
           (x + w * 0.72, y + h * 0.66), (x + w * 0.93, y + h * 0.82)]
    c.polyline(pts, (255, 92, 92), 3.0)
    ax, ay = pts[-1]
    c.poly([(ax, ay), (ax - 16, ay - 3), (ax - 4, ay - 13)], (255, 92, 92))
    # skyline
    hs = [0.16, 0.26, 0.2, 0.32, 0.22, 0.28, 0.18]
    bx = x + 4
    for i, hh in enumerate(hs):
        bw = w * 0.125
        c.rect(bx, y + h * (1 - hh), bw - 4, h * hh, (8, 11, 22))
        for r in range(3):
            for cc in range(2):
                if (i * 7 + r * 3 + cc) % 3:
                    c.rect(bx + 5 + cc * 12, y + h * (1 - hh) + 6 + r * 11, 5, 6, (250, 205, 110))
        bx += bw
    c.text(x + w - 8, y + 6, "S&P 500  -3.7%", "bold_banner", (255, 120, 120), "r")

def hero_cyclone(c, x, y, w, h):
    """Cyclone spiral over sea and palms."""
    c.vgrad(x, y, w, h, (24, 62, 96), (96, 150, 180))
    cx0, cy0 = x + w * 0.42, y + h * 0.44
    for k, rr in enumerate((44, 34, 25, 16)):
        steps = 60
        prev = None
        for i in range(steps):
            t = i / steps * math.pi * 1.55 + k * 0.9
            xx = cx0 + rr * math.cos(t) * 1.25
            yy = cy0 + rr * math.sin(t) * 0.72
            if prev:
                c.line(prev[0], prev[1], xx, yy, (238, 244, 248), 3.4 - k * 0.5, 235)
            prev = (xx, yy)
    c.disc(cx0, cy0, 6, (16, 44, 74))
    # sea waves
    for r in range(3):
        yy = y + h * (0.74 + r * 0.09)
        for xx in range(int(x + 4), int(x + w - 14), 26):
            c.polyline([(xx, yy), (xx + 6, yy - 3.4), (xx + 13, yy), (xx + 19, yy - 3.4), (xx + 25, yy)], (210, 232, 244), 1.7)
    # bent palm
    px0, py0 = x + w * 0.86, y + h * 0.92
    c.polyline([(px0, py0), (px0 - 4, py0 - 26), (px0 - 13, py0 - 42)], (70, 52, 34), 3.4)
    for dx, dy in ((-26, -50), (-12, -56), (4, -54), (16, -46), (-20, -40)):
        c.polyline([(px0 - 13, py0 - 42), (px0 - 13 + dx, py0 - 42 + dy + 14)], (34, 110, 62), 2.6)
    c.text(x + 8, y + 5, "CYCLONE XAVIER - COOK ISLANDS", "sans_mini", (238, 244, 248))

# ---------------------------------------------------------------- world map
LAND = (108, 148, 96)
LAND_D = (86, 124, 78)
SEA = (172, 205, 228)

EURASIA = [(-9, 37), (-9, 43), (-2, 44), (-1, 46), (-5, 48), (-2, 50), (2, 51), (7, 54),
           (8, 57), (5, 58), (6, 61), (11, 65), (18, 69), (30, 70), (45, 68), (60, 69),
           (75, 72), (90, 75), (105, 77), (120, 73), (135, 71), (150, 70), (165, 69),
           (178, 65), (178, 62), (162, 60), (156, 52), (150, 45), (142, 50), (140, 42),
           (135, 40), (130, 42), (127, 40), (122, 38), (121, 32), (120, 28), (118, 24),
           (112, 22), (108, 18), (106, 9), (103, 2), (100, 7), (98, 12), (95, 16),
           (92, 15), (89, 22), (86, 20), (80, 13), (77, 8), (75, 12), (72, 19),
           (68, 23), (61, 25), (57, 26), (52, 28), (50, 29), (48, 30), (44, 29),
           (43, 33), (42, 37), (39, 36), (36, 36), (33, 36), (30, 36), (27, 37),
           (23, 36), (19, 40), (15, 38), (12, 42), (10, 44), (7, 44), (3, 42),
           (0, 39), (-2, 37)]
UK = [(-5, 50), (-3, 51), (-2, 53), (-4, 55), (-3, 57), (-5, 58), (-7, 57), (-8, 54), (-6, 51)]
NAMERICA = [(-165, 68), (-150, 70), (-135, 69), (-125, 71), (-115, 72), (-105, 74),
            (-95, 78), (-88, 70), (-84, 66), (-80, 70), (-78, 62), (-70, 58), (-60, 52),
            (-64, 48), (-68, 44), (-70, 41), (-73, 38), (-75, 35), (-79, 33), (-81, 30),
            (-80, 25), (-82, 23), (-87, 21), (-90, 20), (-97, 16), (-95, 15), (-90, 14),
            (-86, 12), (-83, 9), (-78, 8), (-83, 10), (-90, 13), (-95, 16), (-100, 18),
            (-105, 22), (-110, 24), (-114, 29), (-120, 34), (-124, 40), (-124, 46),
            (-130, 54), (-145, 60), (-158, 58), (-165, 60)]
GREENLAND = [(-45, 60), (-32, 68), (-22, 70), (-20, 76), (-30, 82), (-50, 80), (-58, 72), (-55, 64)]
SAMERICA = [(-79, 9), (-72, 11), (-64, 10), (-55, 6), (-50, 0), (-44, -3), (-35, -8),
            (-39, -13), (-40, -20), (-48, -26), (-52, -33), (-58, -39), (-62, -41),
            (-65, -45), (-67, -50), (-68, -54), (-71, -54), (-73, -46), (-73, -37),
            (-71, -30), (-70, -20), (-75, -15), (-79, -8), (-81, -4), (-80, 1), (-77, 4)]
AFRICA = [(-6, 35), (0, 36), (10, 37), (20, 32), (30, 31), (34, 28), (35, 24), (38, 20),
          (43, 12), (48, 11), (51, 12), (44, 0), (40, -6), (40, -15), (36, -22),
          (33, -27), (28, -33), (20, 35 * -1), (17, -32), (15, -27), (13, -18),
          (12, -10), (9, -2), (9, 4), (-8, 4), (-13, 8), (-17, 12), (-17, 20),
          (-16, 27), (-10, 31)]
JAPAN = [(130, 31), (133, 34), (137, 35), (140, 36), (140, 39), (141, 42), (142, 44),
         (140, 45), (138, 40), (135, 34), (131, 32)]
INDONESIA = [(95, 5), (102, 0), (107, -6), (114, -7), (119, -9), (125, -10), (131, -4),
             (136, -2), (141, -3), (141, -8), (131, -9), (120, -11), (110, -10), (100, -3), (95, 2)]
AUSTRALIA = [(113, -22), (114, -28), (115, -34), (118, -35), (124, -33), (129, -32),
             (132, -32), (135, -35), (138, -35), (140, -38), (145, -38), (147, -38),
             (150, -37), (153, -31), (153, -27), (151, -24), (146, -19), (143, -15),
             (142, -11), (142, -14), (139, -17), (136, -15), (135, -12), (132, -11),
             (130, -13), (126, -14), (122, -17), (118, -20), (114, -21)]
NEWZEALAND = [(167, -45), (171, -43), (174, -41), (176, -38), (174, -37), (172, -40),
              (169, -43), (166, -46)]
MADAGASCAR = [(44, -16), (47, -15), (50, -16), (50, -20), (47, -24), (45, -25), (43, -22), (43, -18)]

def draw_map(c, x, y, w, h):
    c.rect(x, y, w, h, SEA)
    def proj(lon, lat):
        return (x + (lon + 180) / 360 * w, y + (80 - lat) / 130 * h)
    for shape in (EURASIA, UK, NAMERICA, GREENLAND, SAMERICA, AFRICA, JAPAN, INDONESIA, AUSTRALIA, NEWZEALAND, MADAGASCAR):
        c.poly([proj(lon, lat) for lon, lat in shape], LAND)
    markers = [
        (19, 52, "1", "POLAND: MISSILES DOWN"),
        (12.5, 55.7, "2", "COPENHAGEN PLOT"),
        (2.3, 48.9, "3", "PARIS: ZECLER VERDICT"),
        (30.5, 50.4, "4", "KYIV: FUNERALS HELD"),
        (46.7, 24.6, "5", "RIYADH: INTERCEPTED"),
        (42.9, 14.8, "6", "HODEIDAH: UN WARNING"),
        (92, 21.5, "7", "ROHINGYA: JOY AT ICJ"),
        (85.1, 20, "8", "ODISHA: RELIEF"),
        (114.2, 22.3, "9", "HK: SEN + SATWIK"),
        (-115.1, 36.2, "10", "LAS VEGAS GP"),
        (-58.4, -34.6, "11", "BUENOS AIRES: TESLA"),
        (174.8, -41.3, "12", "WELLINGTON TEST"),
    ]
    pts = []
    for lon, lat, num, _ in markers:
        mx, my = proj(lon, lat)
        pts.append((mx, my, num))
        c.disc(mx, my, 9.5, RED)
        c.ring(mx, my, 9.5, WHITE, 1.3)
        c.text(mx, my - 7.5, num, "bold_card", WHITE, "c")
    return markers

# ---------------------------------------------------------------- layout
def build():
    c = Canvas()
    c.rect(0, 0, W, H, PAPER)
    M = 24  # margin

    # masthead
    c.text(W / 2, 8, "THE DAY'S NEWS, IN ONE PAGE - EVERY STORY HAPPENED OR WAS FIRST REPORTED TODAY",
           "sans_mini", GREY, "c")
    c.text(W / 2, 24, "THE WORLD IN ONE DAY", "serif_title", INK, "c")
    c.line(M, 88, W - M, 88, INK, 2.2)
    # date banner
    c.rect(M, 94, W - 2 * M, 38, RED)
    c.text(M + 14, 101, "SATURDAY 21 NOVEMBER 2026", "bold_date", WHITE)
    c.text(W - M - 14, 104, "ONE DAY - THE WHOLE WORLD", "bold_banner", (255, 214, 150), "r")

    # numbers strip
    stats = [
        ("€7.9bn", "PAID BY THE EU\nTO UKRAINE"),
        ("$120bn", "ADAPTATION ASK\nAT COP31"),
        ("-3.7%", "S&P 500 FRIDAY\nCORRECTION"),
        ("235", "MONTHS: GUPTA\nSENTENCE, NY"),
        ("306", "RUNS: INDIA A\nWIN MARGIN"),
        ("62", "CHEETAHS NOW\nIN INDIA"),
        ("310", "PARTNERS IN AP\nMEDIA PACT"),
        ("1.8°C", "OCTOBER HEAT\nABOVE PRE-IND."),
    ]
    sy, sh = 140, 58
    sw = (W - 2 * M - 7 * 6) / 8
    for i, (num, lab) in enumerate(stats):
        bx = M + i * (sw + 6)
        c.rect(bx, sy, sw, sh, PAPER2)
        c.rect(bx, sy, sw, 4, GOLD if i % 2 == 0 else NAVY)
        c.text(bx + sw / 2, sy + 8, num, "bold_stat", INK, "c")
        for j, ln in enumerate(lab.split("\n")):
            c.text(bx + sw / 2, sy + 36 + j * 11, ln, "sans_mini", GREY, "c")
    c.line(M, 206, W - M, 206, INK, 1.2)

    # ---- heroes
    hy = 214
    # lead (left)
    lx, lw = M, 540
    c.rect(lx, hy, lw, 258, WHITE)
    c.rect(lx, hy, lw, 4, RED)
    hero_lead(c, lx + 6, hy + 10, lw - 12, 96)
    ly = hy + 110
    c.text(lx + 12, ly, "EUROPE - CONFLICT", "sans_mini", RED)
    head = wrap("RUSSIAN MISSILES AND A JET DRONE COME DOWN IN POLAND", "bold_hero", lw - 24)
    ly = c.text_block(lx + 12, ly + 13, head, "bold_hero", INK, 24)
    body = wrap("Two Kh-101 cruise missiles and a jet drone fell in the south-east during a mass "
                "strike on Ukraine. NATO chief Rutte visits Warsaw as Poland seeks allied "
                "troops and AWACS cover.", "sans_body", lw - 24)
    ly = c.text_block(lx + 12, ly + 2, body, "sans_body", INK, 19)
    chips = [("8 DEAD", DARKRED), ("28 INJURED", DARKRED), ("RUTTE IN WARSAW", NAVY), ("PM TUSK: 'PROVOCATION'", NAVY)]
    cx0 = lx + 12
    for label, col in chips:
        wch = text_w(label, "sans_small") + 16
        c.rect(cx0, 449, wch, 19, col)
        c.text(cx0 + wch / 2, 452, label, "sans_small", WHITE, "c")
        cx0 += wch + 8

    # right column heroes
    rx, rw = 576, 424
    # COP31
    c.rect(rx, hy, rw, 132, WHITE)
    c.rect(rx, hy, rw, 4, TEAL)
    hero_cop(c, rx + 6, hy + 8, rw - 12, 50)
    c.text(rx + 12, hy + 62, "CLIMATE - ANTALYA", "sans_mini", TEAL)
    c.text(rx + 12, hy + 74, "COP31 TALKS IN OVERTIME", "bold_hero", INK)
    cb = wrap("No deal by Friday's close; third draft promised today. Fossil fuels "
              "and the $120bn goal dropped.", "sans_body", rw - 24)
    c.text_block(rx + 12, hy + 94, cb, "sans_body", INK, 19)
    # markets
    my = hy + 138
    c.rect(rx, my, rw, 130, WHITE)
    c.rect(rx, my, rw, 4, NAVY)
    hero_markets(c, rx + 6, my + 8, rw - 12, 66)
    c.text(rx + 12, my + 79, "MARKETS - NEW YORK", "sans_mini", NAVY)
    c.text(rx + 12, my + 91, "WALL ST IN CORRECTION", "bold_hero", INK)
    mb = wrap("Dow -949 pts; Nasdaq -5.28%, negative for the year.", "sans_body", rw - 24)
    c.text_block(rx + 12, my + 113, mb, "sans_body", INK, 19)

    # ---- map band
    by = 484
    c.text(M, by, "WHERE IT HAPPENED", "bold_banner", NAVY)
    c.text(W - M, by + 2, "12 STORIES ON THE MAP", "sans_small", GREY, "r")
    markers = draw_map(c, M, by + 22, 640, 150)
    c.text(680, by + 26, "ON THE MAP", "bold_banner", NAVY)
    for i, (_, _, num, label) in enumerate(markers):
        xx0 = 680 + (i // 6) * 172
        yy = by + 50 + (i % 6) * 19
        c.disc(xx0 + 6, yy + 5.5, 5.5, RED)
        c.text(xx0 + 6, yy + 1.6, num, "sans_mini", WHITE, "c")
        c.text(xx0 + 16, yy + 0.5, label, "sans_mini", INK)

    # ---- story cards
    cards = [
        ("EUROPE", "coin", "EU PAYS UKRAINE €7.9BN", "Biggest tranche; €1bn arms too"),
        ("EUROPE", "flag", "UK-EU SEAL SUMMIT DEALS", "Food, carbon and youth pacts"),
        ("EUROPE", "rugby", "RUGBY: SIX BIG FIXTURES", "England v NZ tops the bill"),
        ("ASIA-PACIFIC", "chart", "NSE NOW WORLD No.5", "India's exchange passes Nasdaq"),
        ("ASIA-PACIFIC", "syringe", "H5N1 VACCINE UNVEILED", "India's first bird-flu jab"),
        ("ASIA-PACIFIC", "flag", "NEPAL PM TO VISIT INDIA", "Shah in Delhi, 22-23 Nov"),
        ("ASIA-PACIFIC", "hockey", "INDIA WOMEN WIN 4-1", "Hockey opener vs Malaysia"),
        ("ASIA-PACIFIC", "ball", "INDIA A WIN BY 306 RUNS", "Nepal all out for 26"),
        ("NORTH AMERICA", "chip", "NVIDIA FALLS 14%", "Chip index down 10.7% in rout"),
        ("NORTH AMERICA", "rocket", "ANTHROPIC SLIDES -9.1%", "A day after record IPO debut"),
        ("NORTH AMERICA", "factory", "TRUMP THREATENS AI TAX", "On data centres built abroad"),
        ("NORTH AMERICA", "fire", "PALISADES ARSON VERDICT", "Guilty on two counts, LA jury"),
        ("NORTH AMERICA", "shield", "NEW US CYBER CHIEF", "Davies in after outage week"),
        ("NORTH AMERICA", "lock", "BANKS CONFIRM BREACH", "JPMorgan, Visa, Mastercard"),
        ("MIDDLE EAST", "oil", "TRUMP DEMANDS IRAN DEAL", "Decision deferred to new year"),
        ("MIDDLE EAST", "ship", "US HUNTS IRAN EVASION", "Treasury targets front firms"),
        ("AFRICA", "scale", "KENYA JUDGES SCORED", "Backlog near 580,000 cases"),
        ("LATIN AMERICA", "crown", "MISS UNIVERSE: SAN JUAN", "Costume show, 116 delegates"),
        ("OCEANIA", "coal", "COAL MINE GROWS 32%", "NSW law backs Mount Pleasant"),
        ("OCEANIA", "cyclone", "XAVIER LASHES COOK IS.", "Record Nov storm, 220 km/h"),
    ]
    gy = 668
    colw = (W - 2 * M - 3 * 10) / 4
    per_col = 5
    for idx, (reg, ic, head_t, sub) in enumerate(cards):
        col_i = idx // per_col
        row_i = idx % per_col
        xx = M + col_i * (colw + 10)
        yy = gy + row_i * 66
        col = REGION[reg]
        c.rect(xx, yy, colw, 62, WHITE)
        c.rect(xx, yy, 4, 62, col)
        if ic == "cyclone":
            # spiral pictogram
            cx0, cy0 = xx + 23, yy + 31
            for k, rr in enumerate((12, 8, 4.5)):
                prev = None
                for i2 in range(26):
                    t = i2 / 25 * math.pi * 1.5 + k * 1.1
                    px_ = cx0 + rr * math.cos(t) * 1.2
                    py_ = cy0 + rr * math.sin(t) * 0.75
                    if prev:
                        c.line(prev[0], prev[1], px_, py_, REGION["OCEANIA"], 1.7)
                    prev = (px_, py_)
        else:
            icon(c, ic, xx + 8, yy + 18, 30, col)
        c.text(xx + 46, yy + 5, reg, "sans_mini", col)
        hl = wrap(head_t, "bold_card", colw - 54)
        c.text_block(xx + 46, yy + 16, hl[:2], "bold_card", INK, 16.5)
        c.text(xx + 46, yy + 49, sub, "sans_mini", GREY)

    # footer
    c.line(M, 1002, W - M, 1002, INK, 1.2)
    c.text(W / 2, 1007, "All stories happened or were first reported on Saturday 21 November 2026. "
                        "Sources include AP, Reuters, WSJ, Le Monde, The Times and ESPNcricinfo.",
           "sans_mini", GREY, "c")
    return c

def main():
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(outdir, exist_ok=True)
    c = build()
    rgb = c.downscale()
    n = save_png(rgb, os.path.join(outdir, "entry.png"))
    print("wrote entry.png:", n, "bytes")

if __name__ == "__main__":
    main()
