import sys, zlib, struct

def read_png(p):
    d=open(p,'rb').read(); assert d[:8]==b'\x89PNG\r\n\x1a\n'
    i=8; idat=b''; w=h=0; ct=0; pal=None; trns=None
    while i < len(d):
        ln=struct.unpack('>I',d[i:i+4])[0]; typ=d[i+4:i+8]; dat=d[i+8:i+8+ln]; i+=12+ln
        if typ==b'IHDR':
            w,h,bd,ct = struct.unpack('>IIBB',dat[:10])
        elif typ==b'PLTE': pal=dat
        elif typ==b'tRNS': trns=dat
        elif typ==b'IDAT': idat+=dat
        elif typ==b'IEND': break
    raw=zlib.decompress(idat)
    bpp={0:1,2:3,3:1,4:2,6:4}[ct]
    stride=w*bpp
    out=bytearray(); prev=bytearray(stride)
    pos=0
    for y in range(h):
        f=raw[pos]; pos+=1
        line=bytearray(raw[pos:pos+stride]); pos+=stride
        if f==1:
            for x in range(bpp,stride): line[x]=(line[x]+line[x-bpp])&255
        elif f==2:
            for x in range(stride): line[x]=(line[x]+prev[x])&255
        elif f==3:
            for x in range(stride):
                a=line[x-bpp] if x>=bpp else 0
                line[x]=(line[x]+((a+prev[x])>>1))&255
        elif f==4:
            for x in range(stride):
                a=line[x-bpp] if x>=bpp else 0
                c=prev[x-bpp] if x>=bpp else 0
                b=prev[x]; pp=a+b-c
                pa=abs(pp-a); pb=abs(pp-b); pc=abs(pp-c)
                pr=a if (pa<=pb and pa<=pc) else (b if pb<=pc else c)
                line[x]=(line[x]+pr)&255
        out+=line; prev=line
    return w,h,ct,pal,trns,bytes(out)

def px(w,h,ct,pal,out,x,y):
    if ct==3:
        idx=out[y*w+x]
        return (pal[idx*3],pal[idx*3+1],pal[idx*3+2])
    if ct==2:
        o=(y*w+x)*3; return (out[o],out[o+1],out[o+2])
    if ct==6:
        o=(y*w+x)*4; return (out[o],out[o+1],out[o+2])
    return (0,0,0)

def write_png(p,w,h,rows):
    raw=b''.join(b'\x00'+bytes(r) for r in rows)
    def ch(t,d): 
        c=struct.pack('>I',len(d))+t+d
        return c+struct.pack('>I',zlib.crc32(t+d)&0xffffffff)
    hdr=struct.pack('>IIBBBBB',w,h,8,2,0,0,0)
    open(p,'wb').write(b'\x89PNG\r\n\x1a\n'+ch(b'IHDR',hdr)+ch(b'IDAT',zlib.compress(raw,9))+ch(b'IEND',b''))

if __name__ == '__main__':
    src,dst,z=sys.argv[1],sys.argv[2],int(sys.argv[3])
    w,h,ct,pal,trns,out=read_png(src)
    W,H=w*z,h*z
    rows=[]
    for y in range(H):
        r=bytearray()
        for x in range(W):
            R,G,B=px(w,h,ct,pal,out,x//z,y//z)
            r+=bytes((R,G,B))
        rows.append(r)
    write_png(dst,W,H,rows)
    print(f"{src} {w}x{h} -> {W}x{H}")
