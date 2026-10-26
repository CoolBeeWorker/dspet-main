#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Print one sprite frame as a character map, one char per logical pixel.

Reading the PNG by eye is not reliable at 72x56 - a one pixel mistake just
looks "a bit chunky" at 6x zoom.  This dumps the actual colour index of every
pixel so shapes can be counted.

usage: dump.py art/frame_idle0.png x0 x1 y0 y1
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from zoom import read_png
from genart import PAL

# 0..15 in palette order
SYM = ".KBDCWhHrYcMgGmR"
NAME = ["key", "black", "navy", "blue", "cyan", "white", "skin", "tan",
        "ltred", "yellow", "cyandk", "ltmag", "green", "brown", "red",
        "ltgreen"]

RGB2IDX = {(r, g, b): i for i, (r, g, b) in enumerate(PAL)}


def main():
    src = sys.argv[1]
    x0, x1, y0, y1 = (int(v) for v in sys.argv[2:6])
    w, h, ct, pal, trns, raw = read_png(src)
    S = w // 72                      # frame png is written pre-scaled
    print("      " + "".join(str(x % 10) for x in range(x0, x1)))
    for y in range(y0, y1):
        row = ""
        for x in range(x0, x1):
            o = ((y * S) * w + (x * S)) * 3
            rgb = (raw[o], raw[o + 1], raw[o + 2])
            i = RGB2IDX.get(rgb)
            row += SYM[i] if i is not None else "?"
        print("%3d | %s" % (y, row))
    print("\nlegend: " + "  ".join("%s=%s" % (SYM[i], NAME[i]) for i in range(16)))


if __name__ == "__main__":
    main()
