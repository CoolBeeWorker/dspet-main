#!/usr/bin/env python3
"""Build the 1.44 MB floppy payload and copy it to the target directory.

Rules taken from the hardware we are targeting:
  * a 1.44 MB diskette really holds 1,457,664 bytes, but after the FAT,
    the root directory and the usual "leave something free" margin the
    safe usable figure is about 1,300,000 bytes
  * nothing larger than one part may be produced, so anything that does
    not fit is split into PART.001, PART.002 ... and a JOIN.LST is
    written next to it for JOIN.EXE
  * the checksum printed by this script is byte-for-byte the same
    algorithm JOIN.EXE uses, so the numbers can be compared by eye
"""
import os, re, sys, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DIST = os.path.join(ROOT, "dist")
FLOPPY_LIMIT = 1300000          # conservative usable bytes on a 1.44 MB disk

# name on the floppy  ->  source path
PAYLOAD = [
    ("DSPET.EXE",  os.path.join(DIST, "DSPET.EXE")),
    ("DSPET.SPR",  os.path.join(ROOT, "art", "DSPET.SPR")),
    ("VOICE.DAT",  os.path.join(ROOT, "art", "VOICE.DAT")),
    ("JOIN.EXE",   os.path.join(DIST, "JOIN.EXE")),
    ("CRC.EXE",    os.path.join(DIST, "CRC.EXE")),
]


def csum(data):
    """16-bit byte sum - identical to the one JOIN.EXE prints."""
    return sum(data) & 0xFFFF


def readme(entries, split):
    def table():
        out = []
        for name, size, sumv in entries:
            out.append("  %-12s %8d bytes   checksum %04X" % (name, size, sumv))
        return "\n".join(out)

    split_block = ""
    if split:
        split_block = """
THIS DISK CARRIES SPLIT FILES
-----------------------------
The program came in several parts because it did not fit on one disk.
You do NOT have to do anything special: JOIN.LST already lists the parts
in the right order.

   1. Copy every PART.00n file and JOIN.LST to the hard disk, into the
      same directory, for example C:\\DSPET
   2. Go to that directory:      C:
                                 CD \\DSPET
   3. Type:                      JOIN
      If there is more than one list file on this disk, type instead:
                                  JOIN <NAME>.LST
      (for example  JOIN DSPETEXE.LST ) and repeat for each list.
   4. JOIN rebuilds the file and prints a size and a checksum.
      Compare them with the table below. They must match exactly.
   5. Then delete the numbered part files to get the disk space back.
"""

    return """DSPET 0.9 - a DeepSeek whale-girl for Windows 3.0
=================================================

WHAT THIS IS
  A small blue-haired whale girl who lives on your Windows desktop.
  She stands in the corner, blinks, breathes, walks around on her own,
  falls asleep if you ignore her for a while, and talks through the PC
  speaker - no sound card needed.  Real 16-bit Windows 3.0 program,
  written for a 386/20 with 2 MB of RAM.

HOW SHE IS DRAWN  (redrawn in 0.4 from the illustration you supplied)
  Everything below is hand-placed pixel art at 72 x 56 dots, sixteen
  colours, one-pixel black outline.  At that size only the strongest
  features survive, so the drawing keeps exactly these:
      - the white frilled maid headdress, worn behind the head, so it
        shows as a serrated lace halo around the hair
      - long navy hair, brightening down its length and bleaching to
        pale blue at the very tips
      - big blue eyes with a single white glint, a spiky fringe with the
        forehead showing through the notches
      - navy maid dress, white apron with a tiny whale embroidered on
        it, gold studs on the waistband, blue bow with a gem at the neck
      - the whale's flukes worn behind the ears, and the two-lobe whale
        tail curling up behind the skirt
  Things too small to survive at 72 x 56 and therefore simplified: the
  lace texture, the gold embroidery on the sleeves, the frilled cuffs,
  the exact wavy shape of individual hair locks.

WHAT IS NEW IN 0.9 - THE TWO-COLOUR SCREEN
  You told me the machine has a black-and-white monitor, and that it runs
  inverted.  That one fact explains every visual fault that survived the
  last four versions.

  What was happening: the pet is sixteen-colour artwork, and the blitter
  handed those colour bitmaps to a driver that has exactly two colours,
  in the middle of a raster operation (SRCAND for the mask, SRCPAINT for
  the colour).  Converting colour to black-and-white inside an OR is a
  corner of the API that the small drivers of that era never implemented
  properly - each one improvises, and the improvisation lands on the bit
  pattern rather than on the colour.  The wreckage is what you saw: a pet
  that was mostly not there, and a black arc where a nibble happened to
  line up.

  0.9 stops asking the driver to do that.
    - at start-up it reads NUMCOLORS and BITSPIXEL * PLANES from the
      screen.  Two colours means a monochrome driver, and then the sprite
      bank is built HERE, by this program, from the palette in the file.
    - luminance is split into three bands: solid black below 110, solid
      white above 185, and a 4x4 ordered dither in between.  A plain
      threshold makes a paper cut-out with no face; a dither across the
      whole range turns the hair into confetti and the pet disappears
      into its own noise.  The two cut-off points come from rendering the
      real bank through tools/mono.py and looking at the result, not from
      taste.
    - every blit is now one bit deep to one bit deep, so there is nothing
      left for the driver to interpret.
    - the polarity follows the desktop that was just captured.  A light
      desktop gets the artwork as drawn - dark hair, dark outline.  A dark
      desktop gets its negative.  Yours is light, so it takes the first
      path; and because your monitor inverts, the black mass of her hair
      and the black outline reach the glass as WHITE.  On your screen she
      is a white figure on a black desktop, which is the most legible two
      colours can be.

  The menu item "Sprite look" cycles through three renderings, and redraws
  the moment you pick one:
      colour         the sixteen-colour artwork
      mono           this program's own one-bit build of the artwork
      mono inverted  the same, with black and white swapped
  The choice is written to DSPET.INI next to the EXE, so it survives a
  restart.

  One warning that matters on your machine.  The automatic test reads the
  DRIVER, and a driver cannot see the monitor.  Your 8543-A44 is an L40 SX:
  a monochrome STN panel driven by a colour VGA controller (WD90C20).
  Windows loads the ordinary sixteen-colour VGA driver, that driver
  reports sixteen colours, and the panel turns them into shades of grey by
  itself.  So the program picks "colour" and is not wrong to - it simply
  cannot tell what the panel did with them.  If you want the two ends of
  the range instead of the greys, pick "mono" by hand; that is the only
  way, because the panel cannot be asked.

  Command line, for experiments (these win over the saved choice):
      DSPET MONO      start in mono
      DSPET COLOR     start in colour
      DSPET INVERT    start in inverted mono

  The log now begins with a line like
      gfx: 640x480 colours=16 bpp=4 driver=colour look=mono
  which records both the driver's answer and the rendering actually used.

WHAT WAS NEW IN 0.8
  Four faults, and the fourth one is the reason the other three were so
  hard to see.

  1. "Every menu item now ends the program."
     The hardware check and the About box both worked (the log shows
     "box closed"), and then the program died a millisecond later.  Both
     of them called one function after the box, and "Walk around" called
     the same function, and so did the automatic stroll three seconds
     after a plain start - which is why some runs in your log consist of
     nothing but the "run starts" line.
     That function was the desktop-recapture routine added in 0.5 and
     extended in 0.7.  It is GONE.  It hid the window, pumped the message
     queue, called InvalidateRect and UpdateWindow on whatever window was
     underneath, photographed the screen and showed the window again.
     Nothing that aggressive belongs in a 55 ms timer handler.
     What is left is the 1991 algorithm, and it is enough: PutBg writes
     the saved desktop back into the framebuffer, GrabBg reads it back,
     and the pet is provably absent from the framebuffer at that instant.
     Both message boxes now just repaint.

  2. "She becomes invisible while walking, only a translucent shadow that
     drags a picture of a window around."
     That is what two pets look like.  Each pet photographs the screen to
     learn what is behind it - so each one photographs the OTHER pet and
     paints those pixels back on every frame.  Two pets also write this
     log file, and OpenFile refuses a second writer, which is why lines
     went missing and why two lines came out as interleaved garbage.
     The duplicate check in 0.1 was written the textbook way:
         if (hPrevInstance) { already running }
     In Windows 3.x hPrevInstance is ALWAYS 0, so that branch never ran
     and every copy you started stayed alive.  FindWindow is now used
     instead, and it works.  Starting a second copy brings the running
     one to the front and exits; it never adds a second pet.

  3. "The saved background gets polluted."
     Verified by simulation rather than by argument: replaying the exact
     PutBg / GrabBg / compose / blit sequence over 220 one-pixel steps
     against a synthetic desktop gives ZERO wrong pixels in the saved
     copy.  Replaying it with the PutBg step removed poisons 2644 of the
     4032 pixels.  PutBg is not housekeeping, it is what makes the
     capture honest, and it is still there.
     Two changes make the walk cheaper and steadier on a 386:
       - the window class no longer has CS_HREDRAW | CS_VREDRAW, and
         SetWindowPos now passes SWP_NOREDRAW.  USER was repainting all
         4032 pixels of the window on every 1-pixel step, on top of the
         blit this program already does.  That repaint is gone.
       - after a message box the desktop copy is still valid (the box
         never painted into it), so nothing is recaptured.

  4. New: the log now records the things that were impossible to tell
     apart from the outside.
       "wnd: created at x,y"        window really exists, and where
       "wnd: 72x56 visible"         and it is visible
       "walk: start dir=... ticks="  every stroll, with direction
       "walk: from x,y"             where it started
       "walk: end x,y"              and where it finished
       "wnd: was NOT visible ..."   the window lost WS_VISIBLE and was
                                    shown again (a self-healing check that
                                    runs on every tick)
       "wnd: WM_DESTROY"            the window really was destroyed
       "loop: message loop ended"   and the program really did exit
       "app: quit requested"        by the Exit menu item, i.e. on purpose
     So the next log answers "did it exit or did it just go invisible?"
     without guessing.

WHAT WAS NEW IN 0.7
  Three faults: the hardware check (third attempt), a black arc beside the
  head, and a translucent shadow that dragged a piece of a window around.

  1. Hardware check.
     The log you sent ends at "hw: build version text", so the fault is in
     the first statement after that line - the first call to Cat().  That
     rules wsprintf out completely (it is already gone) and leaves
     lstrcpyn as the only KERNEL call in this program that has never
     survived a run: 0.2, 0.4, 0.5 and 0.6 all died inside the same
     function.  Meanwhile every log line calls lstrcpy and lstrcat on a
     stack buffer dozens of times per run without any trouble.
     So Cat() now copies byte by byte with no API call at all, and the
     lstrcpyn that copied the report into the message-box buffer is gone
     the same way.  That section also logs one line per statement now, so
     if anything still fails the log names the statement and not just the
     function.

  2. The black arc beside the head.
     The whale flukes were drawn as a black shape slightly larger than the
     deep-blue shape on top of it, to give them an edge.  The hair is
     painted over their inner half, so what survived at the tips was the
     black rim on its own - a handful of black pixels with no colour next
     to them, which on screen read as a stray arc floating beside the
     head.  The black underlay is gone; the global one-pixel outline pass
     draws the edge anyway and always hugs the colour.

  3. The translucent shadow that dragged a window image while walking.
     The desktop copy behind her was captured while the window she had
     just uncovered had not repainted yet.  ShowWindow(SW_HIDE) only
     INVALIDATES that area; the painting waits for that window's
     WM_PAINT, which on an idle desktop may never be dispatched.  So the
     camera photographed pixels that were still hers, or pixels of
     whatever window had been on top a moment earlier.  Those pixels were
     painted back on every frame afterwards, and every later capture
     copied the dirty copy again - a smear that can never heal by itself.
     The window underneath is now invalidated and updated synchronously
     before the camera is opened, and the copy is refreshed at the start
     of every walk as well as while idle.

WHAT WAS NEW IN 0.6
  One fault: "Hardware check now kills the program outright, with no
  error box at all.  It used to hang for a moment first."

  The log you sent ended at "hw: GetVersion", so the fault was in the
  very next statement - building the version line with wsprintf.

  Why: in 16-bit Windows, the %%s conversion inside USER's wsprintf takes a
  NEAR pointer.
  It takes only the 16-bit offset and reads through the CALLER's DS,
  which for this program is DGROUP.  But this program's stack is its own
  segment - the NE header says SS:SP = 23A2:0001 while DGROUP is segment
  2 and only about 6 KB in total - so the offset of a stack buffer used
  as DS:offset points past the end of the segment.  In protected mode
  that is a protection violation: no error box, the application is just
  gone.  That is exactly what you saw.

  0.4 used %%Fs, which means "far pointer" and was correct, which is why
  0.4 got further (all the way to the heap compaction) before dying.
  0.5 "simplified" it to a near-pointer conversion and moved the fault
  forward.  My mistake.

  The fix is not another format letter: wsprintf is gone from the
  program.  Every string is built with lstrcpy/lstrcat, which take a far
  pointer and keep the segment, and numbers go through a 12-line decimal
  converter.  Verified: no percent-s or percent-Fs conversion remains anywhere in the
  source, and no wsprintf call does either.

  The one other place that used wsprintf (the "start: transparent
  640x480 voice=on" line) survived only because its arguments were string
  literals sitting in DGROUP at small offsets - luck, not correctness -
  and it is converted the same way.

  The hardware report also logs entry and exit around every API call now,
  so if anything at all still goes wrong the last line of DSPET.LOG names
  the statement, and the finished report is written to the log before the
  message box is shown.

WHAT WAS NEW IN 0.5
  Three faults you reported, and what each one really was.

  1. "Hardware check still terminates, but it hangs for a moment first."
     The hang was GlobalCompact(0L).  That is not a query - it compacts
     the whole global heap, and on a 2 MB machine that is a visible
     pause.  It is now GlobalCompact(-1L), which only reports.  The same
     path also called GetModuleFileName on the DISPLAY driver module,
     which a driver handle is not guaranteed to survive, and that call is
     gone.  The report is built from GetWinFlags / GetVersion /
     GetDeviceCaps / WIN.INI only.  It also goes into DSPET.LOG as well
     as into the message box, so even if the box dies you still have it.
     Every single API call now writes its own line to DSPET.LOG BEFORE it
     runs, so if this still dies the last line of that file names it.

  2. "Most of her disappears while she talks."
     The lip-sync dirty rectangle was 26..46 x 28..40 - twenty by twelve
     pixels that covered the chin, the neck, the collar and the apron
     bib, not just the mouth.  All of it was rewritten about thirty times
     a second, and each rewrite was two blits (mask with SRCAND, then
     colour with SRCPAINT).  In between those two blits the destination
     is a black silhouette; at one hertz nobody sees it, at thirty hertz
     the eye reads it as that part of her being gone.  Two changes:
       - the rectangle is now 33..39 x 25..30, the mouth and one pixel
         of margin (the mouth is stamped at 35,27 and is at most 3x3)
       - every update is composed off-screen first and put on screen
         with ONE blit, so there is no intermediate black state at all
     The three talking frames are also byte-identical outside that box
     now, which is what makes a partial redraw legitimate.

  3. "She moves too fast to follow."
     She took TWO pixels per 55 ms tick - 36 px/s, doubling the number of
     erase/move/repaint cycles and repainting the desktop under her 18
     times a second.  Now one pixel per tick, 18 px/s, and the leg cycle
     turns every four ticks instead of two.  The window is also no longer
     invalidated for every move: the finished picture is blitted directly.

  Also in 0.5:
    - clicking her to make her talk no longer plays the voice from inside
      the mouse handler.  It posts a message and the playback happens in
      the main loop, like the menu does.  Blocking inside a window
      procedure is the same mistake that killed 0.2
    - both dialog boxes are now ownerless.  The pet window is a
      WS_EX_TOOLWINDOW popup that has never held focus, and MessageBox
      disabling and re-enabling such a window is a known way to raise an
      unrecoverable application error in 3.0
    - the desktop copy is refreshed properly: the window is hidden while
      the capture is taken.  The old erase-then-capture pair could never
      pick up a change, because it wrote the old copy back first
    - DSPET.LOG is bounded and starts each run with a marker line

WHAT WAS NEW IN 0.4
  - the character was redrawn to match the reference illustration.
    The face, the headdress and the hair silhouette were all rebuilt;
    the eyes are drawn from a pixel map rather than stacked ellipses
  - skin is its own palette entry now.  In 0.3 the face, the apron and
    the headdress all used pure white, so they merged into one shape
  - the side fins are drawn behind the hair instead of in front of it,
    which is what made them look like a pair of wings
  - she no longer looks like she is wearing a helmet: the long locks
    fall straight down instead of flaring wider than her head
  - the skirt was raised and the shoes recoloured, so the legs are
    visible while she walks

WHAT WAS NEW IN 0.3
  - she walks: when idle she picks a direction, strolls for a few
    seconds, bounces off the screen edges and rests again
  - the right-click menu no longer kills the application.  The menu used
    to destroy its own window from inside its own message handler, which
    is what produced the "unrecoverable application error"
  - "Hardware check" no longer writes to any I/O port.  Probing absent
    COM/LPT addresses from a Windows app is not safe and was the other
    half of that crash; it now asks Windows and WIN.INI instead
  - the voice bank was 71800 bytes, over the 60000 the loader accepts,
    so it had never actually loaded and "Say hello" was silent.  It is
    now 6 kHz / 53857 bytes and really plays
  - every menu command writes a line to DSPET.LOG first, so a crash can
    be traced to the exact command

WHAT WILL AND WILL NOT WORK YET
  Works now : character, transparency, dragging, walking, idle/sleep,
              lip-sync, seven voice lines, hardware report
  Not yet   : free text to speech, serial/parallel/IR/network link to
              another machine

FILES ON THIS DISK
%s

HOW TO RUN IT, STEP BY STEP
  1. Put the disk in drive A:.
  2. Copy the files to your hard disk.  At the DOS prompt:
         C:
         MD \\DSPET
         CD \\DSPET
         COPY A:*.*
  3. Start Windows by typing   WIN   and pressing Enter.
  4. In Program Manager choose  File > Run  and type:
         C:\\DSPET\\DSPET.EXE
  5. The whale appears near the bottom right corner of the desktop.

HOW TO USE IT
  Left button, drag      move her anywhere
  Left button, click     she says hello
  Right button           opens a small menu
  Menu > Say hello          same as a plain click
  Menu > Tell me something  one of the longer lines
  Menu > Walk around        start a stroll right now
  Menu > Hardware check     Windows mode, screen, driver, memory, and
                            which ports WIN.INI lists.  Touches no
                            hardware, so it cannot crash
  Menu > Sprite look        cycles colour / mono / mono inverted, and
                            remembers the choice in DSPET.INI.  On a
                            black and white monitor pick mono - see
                            "WHAT IS NEW IN 0.9"
  Menu > About DSPet        version and this list of controls
  Menu > Exit               quits (there is no other way out - she has
                            no title bar on purpose)

  She also walks by herself: after a few idle seconds she starts moving,
  turns round at the screen edge, and stops to rest.

IF SOMETHING GOES WRONG
  A) A box says "Cannot load the sprite bank"
     The box now lists every path it tried and gives a reason code.
     Read the code at the end of the message:
       (1) no such file      the SPR really is not on that path.  Check
                             with  DIR DSPET.SPR  that the file is there
                             and that its name is not abbreviated, e.g.
                             DSPET~1.SPR, which means it was copied from
                             a disk with long-file-name damage.
       (2) damaged or short  the file was truncated in transit.  Re-copy
                             it and run  CRC  again.
       (3) header/size       the SPR is a different version from the EXE,
          mismatch           or was edited.  Re-copy both together - they
                             must come from the same disk.
       (4) out of memory     close other applications; the bank needs
                             about 19 KB of global memory.
       (5) GDI refused       the display driver would not make a bitmap.
                             Note the resolution and driver name from
                             Hardware check and send them to me.
     The program also searches  C:\\DSPET\\DSPET.SPR  and the current
     directory, so a wrong working directory is no longer fatal.
  B) Nothing appears at all, or Windows says it cannot run the program
     Copy CRC.EXE to the hard disk too, then type
         CRC DSPET.EXE DSPET.SPR VOICE.DAT
     and compare the numbers it prints with the table above.  If they
     match, the files arrived intact and the problem is elsewhere.
  C) She appears but you hear nothing
     The PC speaker path uses direct I/O to ports 61h/42h/43h.  Under
     "386 enhanced mode" some machines block that.  Try Windows in
     standard mode:   WIN /S   - then run DSPET again and click the
     whale.  If it speaks there, that is the cause and I will add a
     fallback.
  D) The whale leaves a trail of old pictures behind it, or the desktop
     under it looks wrong, some other application is repainting over it.
     Start it with the switch   C:\\DSPET\\DSPET.EXE -solid   which turns
     off the see-through trick and draws a plain grey box behind the
     whale.  That tells us whether the capture/restore code is at fault.
  E) An "unrecoverable application error" box appears
     Open DSPET.LOG (it sits next to DSPET.EXE, plain text) and look at
     the LAST line.  Every menu command writes there before it runs, so
     the last line names the exact operation that died - for example
     "cmd: say hello" or "cmd: hwcheck, building report".  Send me that
     line and I can point at the code.

  F) The pet is hard to see, or looks like scattered dots
     Right-click and choose "Sprite look" once or twice.  It cycles
     colour -> mono -> mono inverted, and one of the three will be the
     clean black-and-white figure.  No restart is needed and the choice
     is remembered.  Whichever you end up with, send me the "gfx:" line
     from DSPET.LOG - it records what the driver reported and what was
     actually drawn.

WHAT TO SEND BACK
  DSPET.LOG is written next to the EXE every time it starts.  It is a
  plain text file with one or two lines.  Send me that file together
  with the text of the Hardware check box and I will know what your
  machine looks like.
%s
""" % (table(), split_block)


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else r"G:\ "
    target = target.strip()

    entries = []
    files = []
    for name, src in PAYLOAD:
        if not os.path.exists(src):
            print("  skip (missing):", src)
            continue
        data = open(src, "rb").read()
        entries.append([name, len(data), csum(data)])
        files.append((name, data))

    total = sum(e[1] for e in entries)
    print("payload: %d files, %d bytes (%.1f KB), floppy limit %d"
          % (len(entries), total, total / 1024.0, FLOPPY_LIMIT))

    # ---- split only if we are over the limit -------------------------
    # Parts are named STEM001.EXE style so they stay legal 8.3 names and
    # never collide: DSPET.EXE -> DSPETEXE.001, VOICE.DAT -> VOICEDAT.001
    split = False
    lists = {}                       # list file name -> (output, [parts])
    if total > FLOPPY_LIMIT:
        split = True
        per = 640000
        newfiles, newentries = [], []
        for name, data in files:
            if len(data) <= per:
                newfiles.append((name, data))
                newentries.append([name, len(data), csum(data)])
                continue
            stem = re.sub(r"[^A-Z0-9]", "", name.upper())[:8]
            parts = []
            n = 0
            for off in range(0, len(data), per):
                n += 1
                pn = "%s.%03d" % (stem, n)
                chunk = data[off:off + per]
                newfiles.append((pn, chunk))
                newentries.append([pn, len(chunk), csum(chunk)])
                parts.append(pn)
            lists[stem + ".LST"] = (name, parts)
        files, entries = newfiles, newentries
        print("  split into %d parts (%d list files)" % (len(files), len(lists)))

    # ---- stage -------------------------------------------------------
    stage = os.path.join(DIST, "floppy")
    if os.path.isdir(stage):
        shutil.rmtree(stage)
    os.makedirs(stage)

    for name, data in files:
        open(os.path.join(stage, name), "wb").write(data)

    for lst, (out, parts) in lists.items():
        body = out + "\r\n" + "".join(pn + "\r\n" for pn in parts)
        with open(os.path.join(stage, lst), "wb") as f:
            f.write(body.encode())
        if len(lists) == 1:
            with open(os.path.join(stage, "JOIN.LST"), "wb") as f:
                f.write(body.encode())

    with open(os.path.join(stage, "README.TXT"), "wb") as f:
        f.write(readme(entries, split).replace("\n", "\r\n").encode("ascii"))

    # ---- report ------------------------------------------------------
    allf = sorted(os.listdir(stage))
    grand = 0
    print("\n%-14s %10s  %s" % ("FILE", "BYTES", "CHECKSUM"))
    for n in allf:
        d = open(os.path.join(stage, n), "rb").read()
        grand += len(d)
        print("%-14s %10d  %04X" % (n, len(d), csum(d)))
    print("%-14s %10d  (%.1f KB of %d)" % ("TOTAL", grand, grand / 1024.0,
                                           FLOPPY_LIMIT))
    if grand > FLOPPY_LIMIT:
        print("!! STILL TOO BIG FOR ONE DISKETTE")

    # ---- copy --------------------------------------------------------
    if target and os.path.isdir(target):
        for n in allf:
            shutil.copy2(os.path.join(stage, n), os.path.join(target, n))
        print("\ncopied %d files to %s" % (len(allf), target))
    else:
        print("\ntarget %r not available; files are in %s" % (target, stage))
    return 0


if __name__ == "__main__":
    sys.exit(main())
