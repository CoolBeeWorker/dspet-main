import os, sys, time, urllib.request

TARGET = "ow.exe"
GH = "https://github.com/open-watcom/open-watcom-v2/releases/download/Current-build/open-watcom-2_0-c-win-x64.exe"
MIRRORS = ["https://ghproxy.net/" + GH, "https://gh-proxy.com/" + GH, "https://ghfast.top/" + GH]

def head(url):
    req = urllib.request.Request(url, headers={"Range": "bytes=0-0"})
    r = urllib.request.urlopen(req, timeout=25)
    cr = r.headers.get("Content-Range", "")
    r.read(1); r.close()
    if "/" in cr:
        return int(cr.split("/")[1])
    return None

total = None
for m in MIRRORS:
    try:
        total = head(m)
        print("mirror ok:", m.split("/")[2], "size =", total)
        break
    except Exception as e:
        print("mirror fail:", m.split("/")[2], e)
if not total:
    sys.exit("cannot determine size")

CH = 2 * 1024 * 1024
have = os.path.getsize(TARGET) if os.path.exists(TARGET) else 0
if have > total:
    have = 0
print("resume from", have)
f = open(TARGET, "r+b" if os.path.exists(TARGET) else "wb")
f.truncate(have)
f.seek(have)

mi, fails = 0, 0
while have < total:
    end = min(have + CH - 1, total - 1)
    url = MIRRORS[mi % len(MIRRORS)]
    try:
        req = urllib.request.Request(url, headers={"Range": "bytes=%d-%d" % (have, end)})
        r = urllib.request.urlopen(req, timeout=30)
        got = r.read()
        r.close()
        if len(got) != end - have + 1:
            raise IOError("short read %d != %d" % (len(got), end - have + 1))
        f.write(got); f.flush()
        have += len(got)
        fails = 0
        sys.stdout.write("\r  %6.1f / %.1f MB  (%d%%)" % (have/1048576, total/1048576, have*100//total))
        sys.stdout.flush()
    except Exception as e:
        fails += 1
        mi += 1
        sys.stdout.write("\r  retry %d @ %.1f MB (%s)\n" % (fails, have/1048576, str(e)[:50]))
        if fails > 60:
            f.close(); sys.exit("giving up")
        time.sleep(0.5)
f.close()
print("\ndone:", os.path.getsize(TARGET), "bytes")
