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
    L.append((arc_band(36.0 + hx, 19.6 + b, 14.2, 13.0, 1.7, 22.0), WHITE))
    for k in range(13):
        a = math.radians(196.0 + k * 12.3)
        L.append((clip_above(cov_ellipse(36.0 + hx + 13.2 * math.cos(a),
                                         19.6 + b + 12.2 * math.sin(a),
                                         2.1, 2.1), 22.0), WHITE))

    # ---------- 3. hair mass behind the head ------------------------------
    L.append((cov_ellipse(36.0 + hx, 20.2 + b, 12.4, 11.5), BLUE_D))
    L.append((cov_ellipse(36.0 + hx, 26.6 + b, 10.8, 6.2), BLUE_D))
    L.append((cov_ellipse(36.0 + hx, 30.0 + b, 9.4, 3.0), BLUE))

    # ---------- 4. long locks falling behind the shoulders ----------------
    for sgn in (-1.0, 1.0):
        xt = 36.0 + sgn * 11.0 + hx
        xb = 36.0 + sgn * 15.6 + hx
        L.append((taper(xt, 19.0 + b, xb, 43.0 + b, 3.8, 2.0), BLUE_D))
        # the gradient is the point of this character's hair: navy at the
        # root, bright blue along the middle, pale cyan at the very tip
        L.append((taper(xt + sgn * 1.8, 25.0 + b,
                        xb + sgn * 0.2, 41.0 + b, 2.6, 1.5), BLUE))
        L.append((taper(xb - sgn * 0.4, 36.4 + b,
                        xb + sgn * 0.8, 43.8 + b, 1.7, 0.9), CYAN_L))

    # ---------- 5. legs and shoes, behind the skirt -----------------------
    lx, rx = 32.8, 39.2
    dyl = dyr = 0.0
    if leg == 1:
        lx, dyl, rx, dyr = 31.6, -1.6, 40.0, 0.3
    elif leg == 3:
        lx, dyl, rx, dyr = 32.0, 0.3, 40.8, -1.6
    elif leg == 2:
        lx, dyl, rx, dyr = 33.4, -0.7, 38.6, -0.7
    for (x, dy) in ((lx, dyl), (rx, dyr)):
        L.append((cov_capsule(x, 41.8 + b + dy, x, 45.4 + b + dy, 1.7), WHITE))
        L.append((cov_ellipse(x, 46.3 + b + dy, 2.5, 1.5), BLUE_D))

    # ---------- 6. dress: black, as in the illustration -------------------
    # the bodice is cut off at the waist so the apron reads as one piece
    L.append((cov_poly([(30.6, 33.2 + b), (41.4, 33.2 + b),
                        (42.6, 39.4 + b), (29.4, 39.4 + b)]), BLACK))
    L.append((cov_poly([(29.4, 39.4 + b), (42.6, 39.4 + b),
                        (46.6, 44.4 + b), (25.4, 44.4 + b)]), BLACK))
    L.append((cov_ellipse(36.0, 44.2 + b, 10.6, 1.6), BLACK))
    L.append((cov_ellipse(36.0, 45.0 + b, 10.4, 0.8), BLUE))     # hem piping

    # ---------- 7. white apron --------------------------------------------
    L.append((cov_ellipse(36.0, 40.4 + b, 7.4, 3.8), WHITE))
    L.append((cov_ellipse(36.0, 42.6 + b, 7.9, 1.6), WHITE))     # ruffled hem

    # ---------- 8. apron bib, straps, waistband, gold studs ---------------
    # straps touch the bib, otherwise the black gaps between them read as a
    # pair of eyes and the whole chest looks like a rabbit face
    L.append((cov_capsule(32.2, 33.4 + b, 31.4, 36.6 + b, 1.2), WHITE))
    L.append((cov_capsule(39.8, 33.4 + b, 40.6, 36.6 + b, 1.2), WHITE))
    L.append((cov_poly([(31.2, 35.6 + b), (40.8, 35.6 + b),
                        (41.2, 39.4 + b), (30.8, 39.4 + b)]), WHITE))
    L.append((cov_poly([(29.6, 39.2 + b), (42.4, 39.2 + b),
                        (42.4, 40.6 + b), (29.6, 40.6 + b)]), BLACK))
    L.append((cov_ellipse(32.4, 39.9 + b, 0.9, 0.7), YELLOW))
    L.append((cov_ellipse(39.6, 39.9 + b, 0.9, 0.7), YELLOW))

    # ---------- 9. arms: navy sleeves, gold stitch, white cuff, skin hand -
    for sgn in (-1.0, 1.0):
        sx = 36.0 + sgn * 5.4
        ex = 36.0 + sgn * 8.4
        ay = arm * 1.6 * sgn
        L.append((cov_capsule(sx, 34.2 + b, ex, 40.6 + b + ay * sgn, 2.0), BLUE_D))
        L.append((cov_ellipse(36.0 + sgn * 7.0, 37.2 + b + ay * 0.4 * sgn,
                              0.9, 0.7), YELLOW))
        L.append((cov_ellipse(ex + sgn * 0.2, 41.4 + b + ay * sgn, 1.9, 1.2), WHITE))
        L.append((cov_ellipse(ex + sgn * 0.4, 42.8 + b + ay * sgn, 1.6, 1.4), SKIN))

    # ---------- 10. whale flukes worn over the ears -----------------------
    # laid down in black first, then in navy slightly smaller and offset:
    # that draws a clean outline separating the fluke from the hair behind it
    for sgn in (-1.0, 1.0):
        ax = 36.0 + sgn * 9.6
        bx = 36.0 + sgn * 18.4
        L.append((cov_bezier((ax, 17.6 + b), (ax + sgn * 4.4, 18.2 + b),
                             (bx + sgn * 2.0, 20.8 + b),
                             (bx + sgn * 1.0, 24.2 + b), 2.6), BLACK))
        L.append((cov_ellipse(bx + sgn * 2.2, 25.8 + b, 4.6, 2.1,
                              rot=sgn * 0.95), BLACK))
        L.append((cov_ellipse(bx - sgn * 0.6, 28.2 + b, 3.4, 1.6,
                              rot=sgn * 0.60), BLACK))
        L.append((cov_bezier((ax + sgn * 0.4, 17.4 + b),
                             (ax + sgn * 4.6, 18.0 + b),
                             (bx + sgn * 2.2, 20.6 + b),
                             (bx + sgn * 1.2, 24.0 + b), 2.3), BLUE_D))
        L.append((cov_ellipse(bx + sgn * 2.2, 25.7 + b, 4.1, 1.8,
                              rot=sgn * 0.95), BLUE_D))
        L.append((cov_ellipse(bx - sgn * 0.6, 28.1 + b, 2.9, 1.3,
                              rot=sgn * 0.60), BLUE_D))
        # bright rib down the fluke: the only thing that separates it from
        # the hair lock it lies against
        L.append((taper(bx + sgn * 1.2, 21.2 + b, bx + sgn * 3.2, 26.4 + b,
                        1.0, 1.4), CYAN_L))
        L.append((cov_ellipse(bx + sgn * 2.2, 24.4 + b, 1.3, 0.8,
                              rot=sgn * 0.95), BLUE))

    # ---------- 11. neck (tan, so the chin and the collar separate) -------
    L.append((cov_capsule(36.0, 29.0 + b, 36.0, 33.8 + b, 1.7), SKIN_D))

    # ---------- 12. face --------------------------------------------------
    L.append((cov_ellipse(36.0, 21.4 + b, 10.4, 8.4), SKIN))
    L.append((cov_ellipse(36.0, 26.6 + b, 7.0, 4.4), SKIN))

    # ---------- 13. side locks in front of the cheeks ---------------------
    for sgn in (-1.0, 1.0):
        L.append((taper(36.0 + sgn * 10.0 + hx, 18.6 + b,
                        36.0 + sgn * 11.4 + hx, 30.4 + b, 2.1, 1.5), BLUE_D))

    # ---------- 14. ruffled collar and the bow with its gem ---------------
    L.append((cov_ellipse(36.0, 33.4 + b, 6.4, 1.7), WHITE))
    for k in range(5):
        L.append((cov_ellipse(31.2 + k * 2.4, 33.0 + b, 1.3, 1.1), WHITE))
    L.append((cov_ellipse(33.6, 34.9 + b, 2.5, 1.6, rot=0.46), BLUE_D))
    L.append((cov_ellipse(38.4, 34.9 + b, 2.5, 1.6, rot=-0.46), BLUE_D))
    L.append((cov_ellipse(33.9, 34.3 + b, 1.8, 0.7, rot=0.46), BLUE))
    L.append((cov_ellipse(38.1, 34.3 + b, 1.8, 0.7, rot=-0.46), BLUE))
    L.append((cov_ellipse(36.0, 34.9 + b, 1.2, 1.2), BLACK))
    L.append((cov_ellipse(36.0, 35.1 + b, 0.7, 0.7), CYAN_L))

    # ---------- 15. fringe -------------------------------------------------
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

    # ---------- 16. blue bow on the headdress -----------------------------
    L.append((cov_ellipse(46.4 + hx, 12.2 + b, 2.9, 1.5, rot=-0.58), BLUE))
    L.append((cov_ellipse(49.4 + hx, 13.3 + b, 2.7, 1.4, rot=0.58), BLUE))
    L.append((cov_ellipse(47.9 + hx, 12.8 + b, 1.1, 1.1), BLACK))
    L.append((cov_ellipse(47.0 + hx, 11.9 + b, 1.2, 0.6, rot=-0.58), CYAN_L))

    # ---------- 17. blush ---------------------------------------------------
    if blush:
        L.append((cov_ellipse(28.8, 26.4 + b, 1.5, 0.8), RED_L))
        L.append((cov_ellipse(43.2, 26.4 + b, 1.5, 0.8), RED_L))

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
    ex_l, ex_r, ey = 28, 38, 18 + int(round(b))
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

    stamp_patch(canvas, 35, 28 + int(round(b)), MOUTH[mouth if mouth < 3 else 2])

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


