#!/usr/bin/env python3
"""Fold the rendered WAV lines into VOICE.DAT for the 16-bit app.

Target format is deliberately 1990s: 8000 Hz, 8-bit unsigned, mono,
no header per phrase.  That is 8 KB per second; the whole fixed-voice
bank for milestone 1 still lands under 80 KB, and the PC speaker cannot
reproduce more than this anyway.

VOICE.DAT layout
    'D','S','P','A'   u16 count   u16 rate   then per phrase:
    u16 length, u16 reserved, length bytes of unsigned PCM
"""
import glob, os, struct, sys

RATE_OUT = 6000
ART = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "art")


def read_wav(path):
    b = open(path, "rb").read()
    if b[:4] != b"RIFF" or b[8:12] != b"WAVE":
        raise ValueError("not a RIFF/WAVE file: " + path)
    p, fmt, data = 12, None, None
    while p + 8 <= len(b):
        cid = b[p:p + 4]
        sz = struct.unpack_from("<I", b, p + 4)[0]
        body = b[p + 8:p + 8 + sz]
        if cid == b"fmt ":
            fmt = body
        elif cid == b"data":
            data = body
        p += 8 + sz + (sz & 1)
    if fmt is None or data is None:
        raise ValueError("missing fmt/data chunk")
    tag, ch, rate, _br, _align, bits = struct.unpack_from("<HHIIHH", fmt, 0)
    if tag != 1 or bits != 16:
        raise ValueError("expected 16-bit PCM, got tag=%d bits=%d" % (tag, bits))
    n = len(data) // 2
    s = struct.unpack_from("<%dh" % n, data, 0)
    if ch == 2:                                  # downmix
        s = [(s[i] + s[i + 1]) // 2 for i in range(0, n - 1, 2)]
    return list(s), rate


def downsample(s, rate_in, rate_out):
    """Box-filter decimation: crude but it is exactly what a 1993 tool did,
    and it kills the aliasing that would otherwise hiss on a tiny speaker."""
    if rate_in == rate_out:
        return list(s)
    ratio = rate_in / float(rate_out)
    out, pos = [], 0.0
    while pos < len(s):
        end = pos + ratio
        a, b = int(pos), min(int(end) + 1, len(s))
        if b <= a:
            out.append(s[a] if a < len(s) else 0)
        else:
            out.append(int(sum(s[a:b]) / float(b - a)))
        pos = end
    return out


def trim(s, thresh=90):
    i, j = 0, len(s) - 1
    while i < len(s) and abs(s[i]) < thresh:
        i += 1
    while j > i and abs(s[j]) < thresh:
        j -= 1
    if j <= i:
        return s
    pad = RATE_OUT // 50                        # 20 ms of air each side
    return s[max(0, i - pad):min(len(s), j + pad)]


def main():
    files = sorted(glob.glob(os.path.join(ART, "voice", "*.wav")))
    if not files:
        print("no wav files; run tools/genvoice.js first")
        return 1

    blobs = []
    for f in files:
        s, rate = read_wav(f)
        s = downsample(s, rate, RATE_OUT)
        s = trim(s)
        peak = max(1, max(abs(v) for v in s))
        gain = (0.86 * 32767.0) / peak
        n = len(s)
        fade = RATE_OUT // 200                  # 5 ms
        out = bytearray(n)
        for i, v in enumerate(s):
            x = v * gain
            g = 1.0
            if i < fade:
                g = i / float(fade)
            elif i > n - fade:
                g = (n - i) / float(fade)
            u = int(128 + x * g / 256.0)
            out[i] = 0 if u < 0 else (255 if u > 255 else u)
        blobs.append(bytes(out))
        print("  %-14s %5.2f s  %6d bytes  (from %d Hz)"
              % (os.path.basename(f), n / float(RATE_OUT), n, rate))

    total = 8 + sum(4 + len(b) for b in blobs)
    buf = bytearray(b"DSPA")
    buf += struct.pack("<HH", len(blobs), RATE_OUT)
    for b in blobs:
        buf += struct.pack("<HH", len(b), 0)
        buf += b

    path = os.path.join(ART, "VOICE.DAT")
    open(path, "wb").write(buf)
    print("\n%s : %d phrases, %d bytes (%.1f KB)"
          % (path, len(blobs), len(buf), len(buf) / 1024.0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
