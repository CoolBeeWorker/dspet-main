"""Preview the monochrome (1bpp) build of the sprite bank.

This is a re-implementation of MakeMono() in src/spr.c, run over the real
DSPET.SPR rather than over the PNG previews (those are 6x scaled, and
converting scaled art has produced wrong conclusions more than once in
this project).

    python tools/mono.py art/DSPET.SPR art/mono_v9.png [frame] [mode]

Modes:
    bayer   pure ordered dither over 0..255          (what 0.9 shipped)
    clamp   dither only in the middle, solid ends    (sharper, less noise)
    cut     plain threshold, no dither at all        (cleanest silhouette)
"""
import struct
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zoom import write_png

# 4x4 Bayer, identical to bayer4[] in spr.c.  Index is row-major.
BAYER = [
    0,  8,  2, 10,
    12,  4, 14,  6,
    3, 11,  1,  9,
    15,  7, 13,  5,
]

WHITE_CAP = 240     # keep a dot of texture in the whites (see spr.c)

LO, HI = 80, 200    # clamp mode: solid below LO, solid above HI


def load_spr(path):
    d = open(path, 'rb').read()
    assert d[:4] == b'DSP1', "not a DSP1 bank"
    n, w, h, _rsv = struct.unpack('<4H', d[4:12])
    stride4 = ((w * 4 + 31) // 32) * 4
    fs = 40 + 64 + stride4 * h
    frames = []
    for i in range(n):
        p = 12 + i * fs
        pal = d[p + 40:p + 104]
        bits = d[p + 104:p + 104 + stride4 * h]
        idx = [[0] * w for _ in range(h)]
        for y in range(h):
            row = bits[(h - 1 - y) * stride4:]      # DIB is bottom-up
            for x in range(w):
                b = row[x >> 1]
                idx[y][x] = (b & 0x0F) if (x & 1) else (b >> 4)
        frames.append((pal, idx))
    return n, w, h, frames


def lum_of(pal, k):
    b, g, r = pal[k * 4], pal[k * 4 + 1], pal[k * 4 + 2]
    return (r * 299 + g * 587 + b * 114) // 1000


def dither(lum, x, y):
    th = (BAYER[((y & 3) << 2) + (x & 3)] * 255) // 16 + 7
    return lum > th


def to_mono(pal, idx, w, h, invert=False, mode='bayer'):
    """None means transparent; 0/255 are the two displayable values."""
    cache = {}
    out = [[None] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            k = idx[y][x]
            if k == 0:
                continue
            if k not in cache:
                cache[k] = lum_of(pal, k)
            lum = cache[k]

            if mode == 'bayer':
                if lum > WHITE_CAP:
                    lum = WHITE_CAP
                white = dither(lum, x, y)
            elif mode == 'clamp':
                if lum <= LO:
                    white = False
                elif lum >= HI:
                    white = True
                else:
                    white = dither((lum - LO) * 255 // (HI - LO), x, y)
            else:                                   # 'cut'
                white = lum >= 128

            if invert:
                white = not white
            out[y][x] = 255 if white else 0
    return out


def flatten(mono, bg):
    return [[bg if v is None else v for v in row] for row in mono]


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else 'art/DSPET.SPR'
    dst = sys.argv[2] if len(sys.argv) > 2 else 'art/mono_v9.png'
    frame = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    modes = sys.argv[4].split(',') if len(sys.argv) > 4 else ['bayer', 'clamp', 'cut']
    Z = 6
    if len(sys.argv) > 5:
        global LO, HI
        LO, HI = [int(v) for v in sys.argv[5].split(',')]

    n, w, h, frames = load_spr(src)
    pal, idx = frames[frame % n]

    if frame < 0:
        # every frame in one row, the way it will actually be seen
        COLS = 6
        ROWS = (n + COLS - 1) // COLS
        CW, CH = w * Z, h * Z
        GAP = 4
        W = CW * COLS + GAP * (COLS + 1)
        H = CH * ROWS + GAP * (ROWS + 1)
        rows = [bytearray(b'\x80' * (W * 3)) for _ in range(H)]
        for i in range(n):
            img = flatten(to_mono(frames[i][0], frames[i][1], w, h,
                                  False, modes[0]), 255)
            ox = GAP + (i % COLS) * (CW + GAP)
            oy = GAP + (i // COLS) * (CH + GAP)
            for y in range(CH):
                r = rows[oy + y]
                for x in range(CW):
                    v = img[y // Z][x // Z]
                    o = (ox + x) * 3
                    r[o] = r[o + 1] = r[o + 2] = v
        write_png(dst, W, H, rows)
        print(f"{src} all {n} frames, {modes[0]}, white desktop -> {dst}  {W}x{H}")
        return

    CW, CH = w * Z, h * Z
    GAP = 4 * Z
    cols = 2
    W = CW * cols + GAP * (cols + 1)
    H = CH * len(modes) + GAP * (len(modes) + 1)
    rows = [bytearray(b'\x80' * (W * 3)) for _ in range(H)]

    def put(ox, oy, img):
        for y in range(CH):
            r = rows[oy + y]
            sy = y // Z
            for x in range(CW):
                v = img[sy][x // Z]
                o = (ox + x) * 3
                r[o] = r[o + 1] = r[o + 2] = v

    for row, mode in enumerate(modes):
        for col, inv in enumerate([False, True]):
            img = flatten(to_mono(pal, idx, w, h, inv, mode), 255)
            put(GAP + col * (CW + GAP), GAP + row * (CH + GAP), img)
        print(f"row {row}: {mode}   (left = normal, right = inverted, white desktop)")

    write_png(dst, W, H, rows)
    print(f"{src} frame {frame} -> {dst}  {W}x{H}")


if __name__ == '__main__':
    main()
