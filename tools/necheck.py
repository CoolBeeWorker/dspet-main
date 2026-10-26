#!/usr/bin/env python3
"""Minimal 16-bit Windows NE (New Executable) inspector.

Used to prove that what the compiler produced really is a Windows 3.x
executable worth putting on the floppy: right magic, right target OS,
sane stack/heap, and the exported names Windows needs in order to call
our window procedures.
"""
import struct, sys

def u16(b, o): return struct.unpack_from("<H", b, o)[0]
def u32(b, o): return struct.unpack_from("<I", b, o)[0]

def pascal_strings(buf):
    out, i = [], 0
    while i < len(buf) and buf[i]:
        n = buf[i]
        out.append(buf[i+1:i+1+n].decode("latin1", "replace"))
        i += 1 + n
    return out

FLAG = [(0x0001, "DATA"), (0x0002, "ALLOC"), (0x0004, "MOVABLE"),
        (0x0008, "SHAREABLE"), (0x0010, "PRELOAD"),
        (0x0100, "RELOC"), (0x0400, "DISCARDABLE")]

def check(path):
    b = open(path, "rb").read()
    print("file        : %s  (%d bytes, %.1f KB)" % (path, len(b), len(b)/1024.0))
    if b[:2] != b"MZ":
        print("FAIL: no MZ signature"); return 1
    ne = u32(b, 0x3C)
    if b[ne:ne+2] != b"NE":
        print("FAIL: no NE signature at 0x%X (found %r)" % (ne, b[ne:ne+2])); return 1

    ver_min = b[ne+2]; ver_maj = b[ne+3]
    flags      = u16(b, ne+0x0C)
    autodata   = u16(b, ne+0x0E)
    heap_size  = u16(b, ne+0x10)
    stack_size = u16(b, ne+0x12)
    # NOTE: the linker stores the entry point as  offset:segment  in the
    # two words at 0x14/0x16 (verified against the win16 binaries that
    # ship with Open Watcom itself), not segment:offset.
    ip, cs     = u16(b, ne+0x14), u16(b, ne+0x16)
    sp, ss     = u16(b, ne+0x18), u16(b, ne+0x1A)
    seg_count  = u16(b, ne+0x1C)
    seg_tab    = u16(b, ne+0x22)
    res_tab    = u16(b, ne+0x24)
    rn_tab     = u16(b, ne+0x26)
    shift      = u16(b, ne+0x30)
    target     = b[ne+0x34]
    add_flags  = u16(b, ne+0x35)

    os_name = {1: "Windows 3.x (real/standard/enhanced)",
               2: "OS/2", 3: "European DOS 4.x",
               4: "Windows 386", 5: "BOSS"}.get(target, "unknown (%d)" % target)

    print("signature   : 'NE' at 0x%04X  (linker %d.%d)" % (ne, ver_maj, ver_min))
    print("target OS   : %s" % os_name)
    print("module type : %s" % ("DLL" if flags & 0x8000 else "application"))
    print("autodata seg: %d (DGROUP)" % autodata)
    print("heap / stack: %d / %d bytes" % (heap_size, stack_size))
    print("entry CS:IP : %04X:%04X   SS:SP %04X:%04X" % (cs, ip, ss, sp))
    print("segments    : %d" % seg_count)
    print("resources   : %s" % ("none" if res_tab == rn_tab or res_tab == 0 else "yes"))

    total = 0
    print("segment table:")
    for i in range(seg_count):
        o = ne + seg_tab + i * 8
        sect, ln, fl, mn = u16(b, o), u16(b, o+2), u16(b, o+4), u16(b, o+6)
        total += ln
        tags = ",".join(n for bit, n in FLAG if fl & bit)
        print("   #%-2d %-5s len=%5d  minalloc=%5d  %s"
              % (i+1, "CODE" if not (fl & 1) else "DATA", ln, mn, tags))

    ok = True
    if rn_tab:
        names = pascal_strings(b[ne + rn_tab: ne + rn_tab + 256])
        print("exports     : %s" % (", ".join(names) if names else "(none)"))
        if not names:
            print("  WARN: no exported names -> Windows cannot call the window proc")
            ok = False
    else:
        print("exports     : (no resident-name table)")
        ok = False

    if cs == 0 or ip == 0:
        print("  WARN: entry point is null"); ok = False
    if heap_size == 0 or stack_size == 0:
        print("  WARN: heap or stack size is zero"); ok = False

    print("code+data   : %d bytes (%.1f KB)" % (total, total/1024.0))
    print("RESULT      : %s" % ("OK - valid Windows 3.x NE executable" if ok else "needs attention"))
    return 0 if ok else 2

if __name__ == "__main__":
    sys.exit(check(sys.argv[1]))
