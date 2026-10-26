#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DSPET art generator - "whale girl" character.

Renders a chibi DeepSeek whale-girl into a 16-colour sprite bank (.SPR) made
of raw Windows 3.0 DIB frames (BITMAPINFOHEADER + palette + bits) that the
16-bit app feeds straight to CreateDIBitmap().

Design brief (from the reference art the user supplied):
  - deep blue long hair with a light streak, like the whale-girl illustrations
  - the official DeepSeek whale is a rounded blue body with a white belly and
    a two-lobe fluke, so the tail behind her uses exactly those two blues
  - pale face, big eyes, light-blue sailor dress
  - 16 VGA colours only, 1px black outline, magenta index 0 = transparent key

Palette is the IBM VGA 16-colour set, reordered so index 0 is the key.
"""
import os, sys, struct, zlib, math

W, H = 72, 56
SS = 4  # supersampling factor

# ---- palette: (index, R, G, B) -------------------------------------------
PAL = [
    (0xAA, 0x00, 0xAA),  # 0  magenta   transparent key
    (0x00, 0x00, 0x00),  # 1  black     outline / pupil / eyelash
    (0x00, 0x00, 0xAA),  # 2  blue      hair shadow, tail shadow
    (0x55, 0x55, 0xFF),  # 3  lt blue   hair main, tail main, dress trim
    (0x55, 0xFF, 0xFF),  # 4  lt cyan   hair highlight, dress
    (0xFF, 0xFF, 0xFF),  # 5  white     lace, apron, collar
    (0xFF, 0xD2, 0xAA),  # 6  skin      face, hands  (was grey: it merged
    (0xD8, 0x92, 0x62),  # 7  tan       neck / skin shadow   with white)
    (0xFF, 0x55, 0x55),  # 8  lt red    blush / mouth inside
    (0xFF, 0xFF, 0x55),  # 9  yellow    star ornament
    (0x00, 0xAA, 0xAA),  # 10 cyan      deep water
    (0xFF, 0x55, 0xFF),  # 11 lt magenta
    (0x00, 0xAA, 0x00),  # 12 green
    (0xAA, 0x55, 0x00),  # 13 brown
    (0xAA, 0x00, 0x00),  # 14 red       mouth deep
    (0x55, 0xFF, 0x55),  # 15 lt green
]
KEY, BLACK, BLUE_D, BLUE, CYAN_L, WHITE = 0, 1, 2, 3, 4, 5
SKIN, SKIN_D, RED_L, YELLOW, CYAN_D, RED_D = 6, 7, 8, 9, 10, 14


# ---- tiny software rasteriser (no external deps) --------------------------
def _grid():
    return [0.0] * (W * H)


def cov_ellipse(cx, cy, rx, ry, rot=0.0):
    c = _grid()
    ca, sa = math.cos(rot), math.sin(rot)
    inv = 1.0 / SS
    if rx <= 0 or ry <= 0:
        return c
    # bounding box in screen space: a rotated ellipse fits inside this
    cxx, sxx = abs(ca), abs(sa)
    hw = math.sqrt((rx * cxx) ** 2 + (ry * sxx) ** 2) + 1.0
    hh = math.sqrt((rx * sxx) ** 2 + (ry * cxx) ** 2) + 1.0
    px0 = max(0, int(cx - hw))
    px1 = min(W, int(cx + hw) + 1)
    py0 = max(0, int(cy - hh))
    py1 = min(H, int(cy + hh) + 1)
    if px0 >= px1 or py0 >= py1:
        return c
    for py in range(py0, py1):
        # cheap reject: bounding box in screen space (generous)
        for px in range(px0, px1):
            hit = 0
            for sy in range(SS):
                y = py + (sy + 0.5) * inv - cy
                for sx in range(SS):
                    x = px + (sx + 0.5) * inv - cx
                    u = x * ca + y * sa
                    v = -x * sa + y * ca
                    if (u * u) / (rx * rx) + (v * v) / (ry * ry) <= 1.0:
                        hit += 1
            if hit:
                c[py * W + px] = hit / float(SS * SS)
    return c


def cov_poly(pts):
    c = _grid()
    n = len(pts)
    inv = 1.0 / SS
    px0 = max(0, int(min(p[0] for p in pts)) - 1)
    px1 = min(W, int(max(p[0] for p in pts)) + 2)
    py0 = max(0, int(min(p[1] for p in pts)) - 1)
    py1 = min(H, int(max(p[1] for p in pts)) + 2)
    for py in range(py0, py1):
        for px in range(px0, px1):
            hit = 0
            for sy in range(SS):
                yy = py + (sy + 0.5) * inv
                for sx in range(SS):
                    xx = px + (sx + 0.5) * inv
                    inside = False
                    j = n - 1
                    for i in range(n):
                        xi, yi = pts[i]
                        xj, yj = pts[j]
                        if (yi > yy) != (yj > yy):
                            t = (yy - yi) / (yj - yi)
                            if xx < xi + t * (xj - xi):
                                inside = not inside
                        j = i
                    if inside:
                        hit += 1
            if hit:
                c[py * W + px] = hit / float(SS * SS)
    return c


def cov_capsule(x1, y1, x2, y2, r):
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy) or 1e-6
    nx, ny = -dy / L * r, dx / L * r
    quad = [(x1 + nx, y1 + ny), (x2 + nx, y2 + ny), (x2 - nx, y2 - ny), (x1 - nx, y1 - ny)]
    c = cov_poly(quad)
    for (cx, cy) in ((x1, y1), (x2, y2)):
        d = cov_ellipse(cx, cy, r, r)
        for i in range(W * H):
            if d[i] > c[i]:
                c[i] = d[i]
    return c


def cov_bezier(p0, p1, p2, p3, r, steps=18):
    c = _grid()
    prev = p0
    for k in range(1, steps + 1):
        t = k / float(steps)
        mt = 1 - t
        x = (mt ** 3) * p0[0] + 3 * (mt ** 2) * t * p1[0] + 3 * mt * (t ** 2) * p2[0] + (t ** 3) * p3[0]
        y = (mt ** 3) * p0[1] + 3 * (mt ** 2) * t * p1[1] + 3 * mt * (t ** 2) * p2[1] + (t ** 3) * p3[1]
        seg = cov_capsule(prev[0], prev[1], x, y, r)
        for i in range(W * H):
            if seg[i] > c[i]:
                c[i] = seg[i]
        prev = (x, y)
    return c


def taper(x1, y1, x2, y2, r1, r2, steps=10):
    """Cone-ish strand: a chain of circles whose radius shrinks - hair locks."""
    c = _grid()
    for k in range(steps + 1):
        t = k / float(steps)
        x = x1 + (x2 - x1) * t
        y = y1 + (y2 - y1) * t
        r = r1 + (r2 - r1) * t
        d = cov_ellipse(x, y, r, r)
        for i in range(W * H):
            if d[i] > c[i]:
                c[i] = d[i]
    return c


# ---- frame painter -------------------------------------------------------
class Canvas:
    def __init__(self):
        self.idx = [KEY] * (W * H)

    def stamp(self, cov, color, thresh=0.50):
        idx = self.idx
        for i in range(W * H):
            if cov[i] >= thresh:
                idx[i] = color

    def px(self, x, y, color):
        if 0 <= x < W and 0 <= y < H:
            self.idx[y * W + x] = color

    def flip_h(self):
        out = [KEY] * (W * H)
        for y in range(H):
            for x in range(W):
                out[y * W + (W - 1 - x)] = self.idx[y * W + x]
        self.idx = out


def _dilate(mask):
    out = [0] * (W * H)
    for y in range(H):
        for x in range(W):
            if mask[y * W + x]:
                out[y * W + x] = 1
                continue
            for dy in (-1, 0, 1):
                ny = y + dy
                if ny < 0 or ny >= H:
                    continue
                for dx in (-1, 0, 1):
                    nx = x + dx
                    if 0 <= nx < W and mask[ny * W + nx]:
                        out[y * W + x] = 1
                        break
                if out[y * W + x]:
                    break
    return out


# ------------------------------------------------------------------ character
def sub(a, b):
    """coverage of a minus coverage of b - used for rings and hollow shapes."""
    return [a[i] if b[i] < 0.5 else 0.0 for i in range(W * H)]


def clip_above(cov, ymax):
    """Zero everything at or below ymax.  Lets a ring be cut down to an arc."""
    out = list(cov)
    for py in range(max(0, int(ymax)), H):
        row = py * W
        for px in range(W):
            out[row + px] = 0.0
    return out


def arc_band(cx, cy, rx, ry, thick, ymax):
    return clip_above(sub(cov_ellipse(cx, cy, rx, ry),
                          cov_ellipse(cx, cy, rx - thick, ry - thick)), ymax)


# The face is not built from ellipses: at seven pixels across, stacked
# ellipse coverage turns into noise.  These are hand-placed pixel maps, which
# is how the character is actually drawn in the reference art.
#   .  keep what is underneath      #  black lineart
#   D  navy  (iris shadow, upper half)   b  blue (iris)
#   c  light cyan (water line at the bottom of the iris)
#   W  white (the single specular dot)
# The reference art has one big iris with a hard white glint and a thick
# upper lash.  An earlier version wrapped the iris in a white ring, which
# read as spectacles - there is deliberately no sclera here.
EYE = [
    ".#####.",
    "#Dbbbb#",
    "#DbWbb#",
    "#Dbbbb#",
    "#bbbbc#",
    ".#bcb#.",
    "..###..",
]

MOUTH = {
    0: ["##"],
    1: ["###",
        "#r#"],
    2: ["###",
        "#r#",
        "###"],
}

PATCH = {"#": 1, "W": 5, "B": 2, "D": 2, "b": 3, "c": 4, "r": 8, "y": 9, "g": 6}


def stamp_patch(canvas, x0, y0, rows, mirror=False):
    for dy, row in enumerate(rows):
        for dx, ch in enumerate(row):
            if ch == '.':
                continue
            col = PATCH.get(ch)
            if col is None:
                continue
            x = (x0 + len(row) - 1 - dx) if mirror else (x0 + dx)
            canvas.px(x, y0 + dy, col)


def draw_girl(canvas, bob=0.0, sway=0.0, eye="open", mouth=0,
              leg=0, arm=0.0, blush=True, zzz=False, step_flip=False):
    """Draw the whale-girl maid, back to front.

    Follows the supplied illustration as closely as 72x56 allows:
      * a white frilled maid headdress worn *behind* the head, so it reads as
        a scalloped halo around the hair instead of a white bonnet on top;
      * navy hair, shaded strands along the length, bleaching to light cyan at
        the tips, a glossy sheen across the crown and a spiky fringe with skin
        showing in the notches - that zigzag is what says "anime fringe";
      * a large face, one big iris per eye with a single white glint;
      * whale flukes worn over the ears, a blue bow with a gem at the throat,
        a gold-studded waistband, and the whale tail behind the skirt.

    Three rules make this read at 72x56:
      * the dress is pure black, so the white apron and the skin tone pop;
      * the skirt stops high and the shoes are navy, not black - a black shoe
        under a black skirt is just an undefined blob after outlining;
      * hair is separated by *lighter* strands, never by black lines - black
        lines inside the hair read as cracks.
    """
    b  = bob                    # vertical bob, in pixels
    hx = sway * 0.9             # horizontal sway of everything above the neck
    L  = []                     # (coverage, colour); painted in this order

    # ---------- 1. the whale tail, behind everything ----------------------
    L.append((cov_bezier((42.4, 43.6 + b), (52.6, 44.4 + b),
                         (60.2, 39.4 + b), (62.6, 33.6 + b), 3.0), BLUE_D))
    L.append((cov_ellipse(62.0, 28.6 + b, 4.6, 2.0, rot=-0.95), BLUE_D))
    L.append((cov_ellipse(66.6, 32.2 + b, 4.0, 1.8, rot=0.50), BLUE_D))
    L.append((cov_ellipse(63.8, 31.0 + b, 3.0, 2.4, rot=-0.30), BLUE_D))
    # lighter underside: without it the tail disappears into the hair mass
    L.append((cov_bezier((43.6, 45.0 + b), (53.2, 45.7 + b),
                         (59.6, 41.6 + b), (61.9, 36.6 + b), 1.1), BLUE))
    L.append((cov_ellipse(62.6, 29.8 + b, 1.9, 0.8, rot=-0.95), BLUE))

    # ---------- 2. the white frilled headdress, worn behind the hair ------
    # a thin ring plus a row of scallop bumps; the hair painted next covers
    # the inner half, so only a serrated white halo is left showing - which is
    # exactly how the headdress looks in the reference art.  A solid band
    # here reads as a chef's hat, so it is kept as thin as possible.
    L.append((arc_band(36.0 + hx, 19.6 + b, 13.6, 12.4, 1.3, 22.0), WHITE))
    for k in range(13):
        a = math.radians(196.0 + k * 12.3)
        L.append((clip_above(cov_ellipse(36.0 + hx + 13.9 * math.cos(a),
                                         19.6 + b + 12.8 * math.sin(a),
                                         2.6, 2.6), 22.0), WHITE))

    # ---------- 3. hair mass behind the head ------------------------------
    L.append((cov_ellipse(36.0 + hx, 20.2 + b, 12.4, 11.5), BLUE_D))
    L.append((cov_ellipse(36.0 + hx, 26.6 + b, 10.8, 6.2), BLUE_D))
    L.append((cov_ellipse(36.0 + hx, 30.0 + b, 9.4, 3.0), BLUE))

    # ---------- 4. whale flukes worn under the hair ----------------------
    # They are drawn here, before the long locks, so the hair covers their
    # inner half and only the pointed tips show.  Drawing them in front made
    # the fanned shape break up into a hook at this resolution.
    for sgn in (-1.0, 1.0):
        ax = 36.0 + sgn * 9.0
        bx = 36.0 + sgn * 15.4
        # No black underlay.  It used to be one, 0.5 px larger than the
        # navy on every side; once the hair was drawn over the inner half,
        # what survived at the tips was the black rim alone - a few black
        # pixels with nothing coloured next to them.  On screen that read
        # as a stray black arc floating beside the head.  The global 1px
        # dilate draws the outline anyway, and it always hugs the colour.
        L.append((cov_capsule(ax, 18.4 + b, bx, 23.6 + b, 2.1), BLUE_D))
        L.append((cov_ellipse(bx + sgn * 2.6, 26.4 + b, 3.4, 1.8,
                              rot=sgn * 0.80), BLUE_D))
        # a single pale rib along the leading edge is enough to say "whale"
        L.append((taper(ax + sgn * 2.6, 19.4 + b,
                        bx + sgn * 1.6, 23.4 + b, 0.7, 0.9), BLUE))

    # ---------- 5. long locks falling behind the shoulders ----------------
    for sgn in (-1.0, 1.0):
        xt = 36.0 + sgn * 11.6 + hx
        xb = 36.0 + sgn * 13.4 + hx
        L.append((taper(xt, 19.0 + b, xb, 43.0 + b, 3.6, 2.0), BLUE_D))
        # the gradient is the point of this character's hair: navy at the
        # root, bright blue along the middle, pale cyan at the very tip
        L.append((taper(xt + sgn * 1.8, 25.0 + b,
                        xb + sgn * 0.2, 41.0 + b, 2.6, 1.5), BLUE))
        L.append((taper(xb - sgn * 0.1, 41.2 + b,
                        xb + sgn * 0.5, 43.6 + b, 1.2, 0.7), CYAN_L))

    # ---------- 6. legs and shoes, behind the skirt -----------------------
    lx, rx = 32.8, 39.2
    dyl = dyr = 0.0
    if leg == 1:
        lx, dyl, rx, dyr = 31.6, -1.6, 40.0, 0.3
    elif leg == 3:
        lx, dyl, rx, dyr = 32.0, 0.3, 40.8, -1.6
    elif leg == 2:
        lx, dyl, rx, dyr = 33.4, -0.7, 38.6, -0.7
    for (x, dy) in ((lx, dyl), (rx, dyr)):
        L.append((cov_capsule(x, 42.8 + b + dy, x, 46.2 + b + dy, 1.6), WHITE))
        L.append((cov_ellipse(x, 47.0 + b + dy, 2.5, 1.4), BLUE_D))

    # ---------- 7. dress: black, as in the illustration -------------------
    # the bodice is cut off at the waist so the apron reads as one piece
    L.append((cov_poly([(30.6, 33.2 + b), (41.4, 33.2 + b),
                        (42.6, 39.4 + b), (29.4, 39.4 + b)]), BLACK))
    L.append((cov_poly([(29.4, 39.4 + b), (42.6, 39.4 + b),
                        (46.6, 44.8 + b), (25.4, 44.8 + b)]), BLACK))
    L.append((cov_ellipse(36.0, 44.6 + b, 10.8, 1.4), BLACK))

    # ---------- 8. white apron --------------------------------------------
    L.append((cov_ellipse(36.0, 41.2 + b, 7.4, 3.4), WHITE))
    L.append((cov_ellipse(36.0, 43.2 + b, 7.8, 1.4), WHITE))     # ruffled hem

    # ---------- 9. apron straps, waistband, gold studs --------------------
    # No white bib: with the straps, the bib and the waistband all in white,
    # the black gaps between them read as a pair of eyes and the chest looks
    # like a rabbit face.  The reference has a navy bodice with two apron
    # straps over it, so that is what this draws.
    L.append((cov_capsule(32.4, 33.2 + b, 31.4, 39.4 + b, 1.2), WHITE))
    L.append((cov_capsule(39.6, 33.2 + b, 40.6, 39.4 + b, 1.2), WHITE))
    L.append((cov_poly([(29.6, 39.2 + b), (42.4, 39.2 + b),
                        (42.4, 40.6 + b), (29.6, 40.6 + b)]), BLACK))
    L.append((cov_ellipse(33.0, 39.9 + b, 0.9, 0.7), YELLOW))
    L.append((cov_ellipse(39.0, 39.9 + b, 0.9, 0.7), YELLOW))

    # ---------- 10. arms: navy sleeves, gold stitch, white cuff, skin hand -
    for sgn in (-1.0, 1.0):
        sx = 36.0 + sgn * 5.4
        ex = 36.0 + sgn * 8.4
        ay = arm * 1.6 * sgn
        L.append((cov_capsule(sx, 34.2 + b, ex, 40.6 + b + ay * sgn, 2.0), BLUE_D))
        L.append((cov_ellipse(36.0 + sgn * 7.0, 37.2 + b + ay * 0.4 * sgn,
                              0.9, 0.7), YELLOW))
        L.append((cov_ellipse(ex + sgn * 0.2, 41.4 + b + ay * sgn, 1.9, 1.2), WHITE))
        L.append((cov_ellipse(ex + sgn * 0.4, 42.8 + b + ay * sgn, 1.6, 1.4), SKIN))

    # ---------- 13. neck (tan, so the chin and the collar separate) -------
    L.append((cov_capsule(36.0, 29.2 + b, 36.0, 33.2 + b, 1.7), SKIN_D))

    # ---------- 14. face --------------------------------------------------
    L.append((cov_ellipse(36.0, 21.2 + b, 10.2, 8.0), SKIN))
    L.append((cov_ellipse(36.0, 25.2 + b, 5.8, 3.8), SKIN))

    # ---------- 15. side locks in front of the cheeks ---------------------
    for sgn in (-1.0, 1.0):
        L.append((taper(36.0 + sgn * 10.0 + hx, 18.6 + b,
                        36.0 + sgn * 11.4 + hx, 29.6 + b, 2.1, 1.5), BLUE_D))

    # ---------- 16. ruffled collar and the bow with its gem ---------------
    L.append((cov_ellipse(36.0, 32.9 + b, 5.2, 1.6), WHITE))
    for k in range(5):
        L.append((cov_ellipse(32.0 + k * 2.0, 32.5 + b, 1.2, 1.0), WHITE))
    L.append((cov_ellipse(33.6, 34.9 + b, 2.5, 1.6, rot=0.46), BLUE_D))
    L.append((cov_ellipse(38.4, 34.9 + b, 2.5, 1.6, rot=-0.46), BLUE_D))
    L.append((cov_ellipse(33.9, 34.3 + b, 1.8, 0.7, rot=0.46), BLUE))
    L.append((cov_ellipse(38.1, 34.3 + b, 1.8, 0.7, rot=-0.46), BLUE))
    L.append((cov_ellipse(36.0, 34.9 + b, 1.2, 1.2), BLACK))
    L.append((cov_ellipse(36.0, 35.1 + b, 0.7, 0.7), CYAN_L))

    # ---------- 17. fringe -------------------------------------------------
    # One zigzag polygon: the points hang down and the notch between each pair
    # lets the forehead show through.  A plain band across the brow makes her
    # look like she is wearing a swim cap.
    L.append((cov_ellipse(36.0 + hx, 12.0 + b, 11.2, 4.4), BLUE_D))
    L.append((cov_poly([(24.4, 10.2 + b), (47.8, 10.2 + b),
                        (47.4, 15.4 + b), (44.8, 17.8 + b),
                        (42.6, 15.2 + b), (40.6, 18.4 + b),
                        (38.4, 15.2 + b), (36.4, 15.6 + b),
                        (34.4, 15.2 + b), (32.4, 18.4 + b),
                        (30.4, 15.2 + b), (28.2, 17.8 + b),
                        (24.8, 15.0 + b)]), BLUE_D))
    # glossy sheen across the crown, and two lighter strands down the fringe -
    # these, not black lines, are what separate the hair into locks
    L.append((cov_ellipse(35.8 + hx, 13.8 + b, 7.6, 1.6, rot=0.04), BLUE))
    L.append((cov_ellipse(31.0 + hx, 13.4 + b, 3.0, 0.8, rot=-0.24), CYAN_L))
    L.append((cov_ellipse(41.6 + hx, 13.6 + b, 2.4, 0.7, rot=0.22), CYAN_L))
    for sgn in (-1.0, 1.0):
        L.append((taper(36.0 + sgn * 5.4 + hx, 12.6 + b,
                        36.0 + sgn * 6.4 + hx, 15.4 + b, 0.8, 0.6), BLUE))

    # ---------- 18. blue bow on the headdress -----------------------------
    L.append((cov_ellipse(46.4 + hx, 12.2 + b, 2.9, 1.5, rot=-0.58), BLUE))
    L.append((cov_ellipse(49.4 + hx, 13.3 + b, 2.7, 1.4, rot=0.58), BLUE))
    L.append((cov_ellipse(47.9 + hx, 12.8 + b, 1.1, 1.1), BLACK))
    L.append((cov_ellipse(47.0 + hx, 11.9 + b, 1.2, 0.6, rot=-0.58), CYAN_L))

    # ---------- 19. blush ---------------------------------------------------
    if blush:
        L.append((cov_ellipse(28.9, 26.4 + b, 1.4, 0.8), RED_L))
        L.append((cov_ellipse(43.1, 26.4 + b, 1.4, 0.8), RED_L))

    # ---------- composite: 1px lineart, then the fills ----------------------
    union = [0] * (W * H)
    for (cov, _c) in L:
        for i in range(W * H):
            if cov[i] >= 0.50:
                union[i] = 1
    out = _dilate(union)
    canvas.idx = [BLACK if out[i] else KEY for i in range(W * H)]

    for (cov, col) in L:
        canvas.stamp(cov, col, 0.50)

    # ---------- the face, hand placed on top --------------------------------
    ex_l, ex_r, ey = 28, 38, 19 + int(round(b))
    if eye == "open":
        stamp_patch(canvas, ex_l, ey, EYE)
        stamp_patch(canvas, ex_r, ey, EYE, mirror=True)
        canvas.px(ex_l - 1, ey + 1, BLACK)       # outer lash tip
        canvas.px(ex_r + 7, ey + 1, BLACK)
    elif eye == "blink":
        for x0 in (ex_l, ex_r):
            for dx in range(0, 7):
                canvas.px(x0 + dx, ey + 4, BLACK)
            canvas.px(x0 + 3, ey + 5, BLACK)
    elif eye == "happy":
        for x0 in (ex_l, ex_r):
            for dx, dy in ((1, 3), (2, 2), (3, 2), (4, 2), (5, 3)):
                canvas.px(x0 + dx, ey + dy, BLACK)
            canvas.px(x0 + 6, ey + 4, BLACK)
            canvas.px(x0, ey + 4, BLACK)
    else:  # sleep
        for x0 in (ex_l, ex_r):
            for dx in range(0, 7):
                canvas.px(x0 + dx, ey + 4, BLACK)
            canvas.px(x0 + 2, ey + 5, BLACK)
            canvas.px(x0 + 3, ey + 5, BLACK)

    stamp_patch(canvas, 35, 27 + int(round(b)), MOUTH[mouth if mouth < 3 else 2])

    # the little whale embroidered on the apron
    for (dx, dy) in ((0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (2, 1), (3, 0)):
        canvas.px(34 + dx, 41 + int(round(b)), BLUE)
    canvas.px(37, 40 + int(round(b)), BLUE)
    canvas.px(34, 41 + int(round(b)), WHITE)

    if zzz:
        for k, (zx, zy) in enumerate(((52, 9), (57, 4), (61, 0))):
            sz = 2.0 + k * 1.0
            canvas.stamp(cov_capsule(zx, zy, zx + sz, zy, 0.60), CYAN_L)
            canvas.stamp(cov_capsule(zx + sz, zy, zx, zy + sz, 0.60), CYAN_L)
            canvas.stamp(cov_capsule(zx, zy + sz, zx + sz, zy + sz, 0.60), CYAN_L)

    if step_flip:
        canvas.flip_h()


# ---- frame table ---------------------------------------------------------
# name, bob, sway, eye, mouth, leg, arm, blush, zzz, mirrored
FRAMES = [
    ("idle0", 0.0, 0.0, "open", 0, 0, 0.0, True, False, False),
    ("idle1", -1.0, 0.3, "open", 0, 0, 0.0, True, False, False),
    ("blink", 0.0, 0.0, "blink", 0, 0, 0.0, True, False, False),
    # The three talking frames MUST be identical outside the mouth: main.c
    # only redraws a 7x6 box around the mouth while a phrase plays, so any
    # difference elsewhere (a different bob, a different sway) would be
    # left on screen as a stale pixel.  Keep bob and sway equal here.
    ("talk0", -0.2, 0.0, "open", 0, 0, 0.0, True, False, False),
    ("talk1", -0.2, 0.0, "open", 1, 0, 0.0, True, False, False),
    ("talk2", -0.2, 0.0, "open", 2, 0, 0.0, True, False, False),
    ("happy", -1.6, 0.4, "happy", 2, 0, 1.0, True, False, False),
    ("sleep0", 1.2, 0.0, "sleep", 0, 0, 0.0, False, True, False),
    ("sleep1", 1.8, 0.2, "sleep", 0, 0, 0.0, False, True, False),
    ("walk0", 0.0, 0.0, "open", 0, 1, 1.0, True, False, False),
    ("walk1", -1.0, 0.4, "open", 0, 0, 0.0, True, False, False),
    ("walk2", 0.0, 0.0, "open", 0, 3, -1.0, True, False, False),
    ("walk3", -1.0, -0.4, "open", 0, 2, 0.0, True, False, False),
    # mirrored walking frames, for moving left
    ("walkL0", 0.0, 0.0, "open", 0, 1, 1.0, True, False, True),
    ("walkL1", -1.0, 0.4, "open", 0, 0, 0.0, True, False, True),
    ("walkL2", 0.0, 0.0, "open", 0, 3, -1.0, True, False, True),
    ("walkL3", -1.0, -0.4, "open", 0, 2, 0.0, True, False, True),
]


# ---- output --------------------------------------------------------------
def frame_bytes(canvas):
    bih = struct.pack("<IiiHHIIiiII", 40, W, H, 1, 4, 0, 0, 0, 0, 16, 16)
    pal = b"".join(struct.pack("BBBB", b, g, r, 0) for (r, g, b) in PAL)
    stride = ((W * 4 + 31) // 32) * 4
    bits = bytearray(stride * H)
    for y in range(H):
        src = (H - 1 - y) * W
        row = y * stride
        for x in range(0, W, 2):
            hi = canvas.idx[src + x] & 0x0F
            lo = canvas.idx[src + x + 1] & 0x0F
            bits[row + x // 2] = (hi << 4) | lo
    return bih + pal + bytes(bits)


def write_png(path, canvas, scale=5, indices=None):
    idx = indices if indices is not None else canvas.idx
    rows = []
    for y in range(H * scale):
        line = bytearray([0])
        for x in range(W * scale):
            i = idx[(y // scale) * W + (x // scale)]
            r, g, b = PAL[i]
            if i == KEY:
                v = 0xCC if ((x // 8 + y // 8) % 2) else 0xEE
                r = g = b = v
            line += bytes((r, g, b))
        rows.append(bytes(line))
    raw = b"".join(rows)

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", W * scale, H * scale, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)


def write_sheet(path, canvases, scale=3):
    """All frames side by side, one PNG, for eyeballing."""
    n = len(canvases)
    cw, ch = W * scale, H * scale
    rows = []
    for y in range(ch):
        line = bytearray([0])
        for c in canvases:
            for x in range(cw):
                i = c.idx[(y // scale) * W + (x // scale)]
                r, g, b = PAL[i]
                if i == KEY:
                    v = 0xCC if ((x // 8 + y // 8) % 2) else 0xEE
                    r = g = b = v
                line += bytes((r, g, b))
        rows.append(bytes(line))
    raw = b"".join(rows)

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", cw * n, ch, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)


def main():
    outdir = os.path.dirname(os.path.abspath(__file__))
    artdir = os.path.join(os.path.dirname(outdir), "art")
    os.makedirs(artdir, exist_ok=True)

    blobs, canvases = [], []
    for (name, bob, sway, eye, mouth, leg, arm, blush, zzz, fl) in FRAMES:
        c = Canvas()
        draw_girl(c, bob, sway, eye, mouth, leg, arm, blush, zzz, fl)
        canvases.append(c)
        blobs.append(frame_bytes(c))
        write_png(os.path.join(artdir, "frame_%s.png" % name), c, scale=6)
        print("frame %-7s %5d bytes" % (name, len(blobs[-1])))

    write_sheet(os.path.join(artdir, "all_frames.png"), canvases, scale=3)

    spr = b"DSP1" + struct.pack("<HHHH", len(blobs), W, H, 0) + b"".join(blobs)
    path = os.path.join(artdir, "DSPET.SPR")
    with open(path, "wb") as f:
        f.write(spr)
    print("\n%s : %d frames, %d bytes (%.1f KB)"
          % (path, len(blobs), len(spr), len(spr) / 1024.0))


if __name__ == "__main__":
    main()
