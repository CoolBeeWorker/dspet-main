/* =====================================================================
 *  SPR.C  -  sprite bank loader / transparent blitter
 *
 *  Bank layout (produced by tools/genart.py):
 *      'D','S','P','1'   u16 nFrames  u16 w  u16 h  u16 rsv
 *      ^------------------- 12 bytes -------------------^
 *      then nFrames x { BITMAPINFOHEADER(40) + 16*RGBQUAD(64) + bits }
 *
 *  The header is TWELVE bytes, not eight: magic plus four words.
 *  (19092 = 12 + 9 * (40 + 64 + 36 * 56)).  Reading it as eight bytes
 *  shifts every frame by four, and CreateDIBitmap then sees a bogus
 *  biSize of 56 and fails.
 *
 *  Transparency is done the 1990 way: a 1bpp mask + colour bitmap,
 *  SRCAND then SRCPAINT.  The mask is built by hand from the DIB bits
 *  (no reliance on the driver's colour->mono conversion).
 *
 *  Mask polarity, which is easy to get backwards:
 *      0 = sprite is opaque here   -> SRCAND clears the destination,
 *                                     so the colour pass has black to
 *                                     OR onto
 *      1 = transparent here        -> SRCAND leaves the desktop alone,
 *                                     and index 0 is force-patched to
 *                                     black so SRCPAINT is a no-op
 * ===================================================================== */
#include "dspet.h"

#define MAXFRAME 32
#define HDRSIZE  12                 /* magic(4) + four words */

static HANDLE  hBank;
static LPSTR   lpBank;
static int     nFrames, sprW, sprH;
static HBITMAP hColor[MAXFRAME];
static HBITMAP hMask[MAXFRAME];
static HDC     hdcColor, hdcMask;
static int     lastErr;

int Spr_LastError( void ) { return lastErr; }

/* ---- monochrome support -------------------------------------------
 * Set by the caller before Spr_Load.  Nothing here inspects the driver
 * itself: the caller already has a screen DC and the desktop capture, and
 * only the caller knows whether the desktop under the pet is light or
 * dark (see BgLooksLight in main.c).
 *
 * Why this exists at all.  The pet is a 4 bits-per-pixel DIB, and the
 * whole blitter is the 1991 icon trick: mask with SRCAND, colour with
 * SRCPAINT.  Both halves of that trick assume the source and the
 * destination have the SAME format.  On a 2-colour driver the memory DCs
 * are 1bpp, so the colour pass asks GDI to convert 4bpp -> 1bpp *while
 * applying a raster op*, and the small drivers of that era do not do
 * that: some threshold each byte, some take the high nibble, none of them
 * produce the picture.  The symptom on the real machine was a pet that
 * was not there at all, plus a smudge of the window underneath.
 *
 * The fix is to hand GDI bitmaps it does not have to convert.  We read
 * the palette ourselves, turn luminance into a 1bpp dot pattern with an
 * ordered dither, and every blit stays 1bpp to 1bpp. */
static int  monoMode;
static int  monoInvert;

void Spr_SetMono( int on )   { monoMode   = on; }
int  Spr_IsMono( void )      { return monoMode; }
void Spr_SetInvert( int on ) { monoInvert = on; }
int  Spr_IsInvert( void )    { return monoInvert; }

/* Luminance is split into three bands: below MONO_LO the picture goes
   solid black, above MONO_HI solid white, and only the middle band is
   dithered.

   A full-range dither (the first cut) turned every large area into 50%
   confetti.  On a 72x56 sprite that does not read as shading, it reads as
   dirt, and the character disappears into its own noise.  Clamping the
   ends keeps the hair a solid mass and the face a clean white, so the
   silhouette - not the texture - is what the eye picks up.  These two
   numbers came from rendering the real bank through tools/mono.py and
   looking at it, not from taste. */
#define MONO_LO 110
#define MONO_HI 185

/* 4x4 Bayer matrix, row-major.  Sixteen evenly spaced thresholds are what
   turns the middle band into its four or five visible densities. */
static const unsigned char bayer4[16] = {
     0,  8,  2, 10,
    12,  4, 14,  6,
     3, 11,  1,  9,
    15,  7, 13,  5
};

/* Build one 1bpp bitmap from a 4bpp frame.
   Index 0 is transparent, and it must stay 0 in the colour bitmap as well
   as being 1 in the mask: SRCPAINT ORs white in, so any stray white pixel
   in a transparent area would paint a dot of the pet's colour onto the
   desktop. */
static HBITMAP MakeMono( LPSTR pal, LPSTR bits, int stride4, int w, int h )
{
    int   mstride = ((w + 15) / 16) * 2;
    int   x, y;
    LPSTR mbuf = (LPSTR)GlobalAlloc( GMEM_FIXED | GMEM_ZEROINIT,
                                     (DWORD)((long)mstride * h) );
    if( !mbuf ) return NULL;

    for( y = 0; y < h; y++ )
    {
        LPSTR src = bits + (long)(h - 1 - y) * stride4;   /* DIB is bottom-up */
        LPSTR dst = mbuf + (long)y * mstride;

        for( x = 0; x < w; x++ )
        {
            int idx = (x & 1) ? (src[x >> 1] & 0x0F)
                              : ((src[x >> 1] >> 4) & 0x0F);
            int lum, th, white;

            if( idx == 0 ) continue;              /* transparent */

            {
                LPSTR q = pal + (long)idx * 4;    /* RGBQUAD: B,G,R,0 */
                int b = (unsigned char)q[0];
                int g = (unsigned char)q[1];
                int r = (unsigned char)q[2];
                lum = ( r * 299 + g * 587 + b * 114 ) / 1000;
            }

            /* three bands; only the middle one is dithered */
            if( lum <= MONO_LO )            white = 0;
            else if( lum >= MONO_HI )       white = 1;
            else
            {
                th = ( (int)bayer4[ ((y & 3) << 2) + (x & 3) ] * 255 ) / 16 + 7;
                white = ( ( (lum - MONO_LO) * 255 ) / (MONO_HI - MONO_LO) > th );
            }

            /* the monitor on the target machine inverts everything, so a
               pet that is logically dark is physically light.  The caller
               picks the polarity from the desktop it just captured; this
               switch is the manual override. */
            if( monoInvert ) white = !white;

            if( white ) dst[x >> 3] |= (char)(0x80 >> (x & 7));
        }
    }

    {
        HBITMAP hbm = CreateBitmap( w, h, 1, 1, mbuf );
        GlobalFree( (HANDLE)mbuf );
        return hbm;
    }
}

/* ------------------------------------------------------------------ */
static HFILE OpenRead( LPCSTR szFile )
{
    OFSTRUCT of;
    of.cBytes = sizeof( OFSTRUCT );
    return OpenFile( szFile, &of, OF_READ );
}

static long frameSize;              /* bytes per frame, from the directory */
static BOOL gLoaded;

/* Build the GDI bitmaps for frame i.  Split out of LoadAll so that the
   mono/invert switch can throw the bank away and rebuild it without
   touching the disk again - the file image stays in lpBank for the whole
   run. */
static BOOL MakeFrame( int i )
{
    LPSTR p    = lpBank + HDRSIZE + (long)i * frameSize;
    BITMAPINFOHEADER FAR *pbih = (BITMAPINFOHEADER FAR *)p;
    LPSTR pal  = p + 40;
    LPSTR bits = pal + 64;
    int   stride4 = ((sprW * 4 + 31) / 32) * 4;
    int   mstride = ((sprW + 15) / 16) * 2;
    int   x, y;
    LPSTR mbuf;

    if( pbih->biSize != 40 ||
        (int)pbih->biWidth  != sprW ||
        (int)pbih->biHeight != sprH )
        { lastErr = 3; return FALSE; }

    if( monoMode )
    {
        hColor[i] = MakeMono( pal, bits, stride4, sprW, sprH );
    }
    else
    {
        pal[0] = 0; pal[1] = 0; pal[2] = 0; pal[3] = 0;   /* index0 -> black */
        hColor[i] = CreateDIBitmap( hdcColor, pbih, (DWORD)CBM_INIT,
                                    bits, (LPBITMAPINFO)pbih,
                                    DIB_RGB_COLORS );
    }
    if( !hColor[i] ) { lastErr = 5; return FALSE; }

    mbuf = (LPSTR)GlobalAlloc( GMEM_FIXED | GMEM_ZEROINIT,
                               (DWORD)(mstride * sprH) );
    if( !mbuf ) { lastErr = 4; return FALSE; }

    for( y = 0; y < sprH; y++ )
    {
        LPSTR src = bits + (long)(sprH - 1 - y) * stride4;  /* DIB is bottom-up */
        LPSTR dst = mbuf + (long)y * mstride;
        for( x = 0; x < sprW; x++ )
        {
            int idx = (x & 1) ? (src[x >> 1] & 0x0F)
                              : ((src[x >> 1] >> 4) & 0x0F);
            if( idx == 0 )                       /* transparent -> mask bit 1 */
                dst[x >> 3] |= (char)(0x80 >> (x & 7));
        }
    }
    hMask[i] = CreateBitmap( sprW, sprH, 1, 1, mbuf );
    GlobalFree( (HANDLE)mbuf );
    if( !hMask[i] ) { lastErr = 5; return FALSE; }
    return TRUE;
}

static void DropFrames( void )
{
    int i;
    for( i = 0; i < MAXFRAME; i++ )
    {
        if( hColor[i] ) { DeleteObject( hColor[i] ); hColor[i] = NULL; }
        if( hMask[i] )  { DeleteObject( hMask[i] );  hMask[i]  = NULL; }
    }
}

/* Rebuild every frame from the copy of the file that is already in
   memory.  Used by the "Invert sprite" menu item. */
BOOL Spr_Rebuild( void )
{
    int i;

    if( !gLoaded || !lpBank ) return FALSE;
    DropFrames();
    for( i = 0; i < nFrames; i++ )
        if( !MakeFrame( i ) ) return FALSE;
    return TRUE;
}

static BOOL LoadAll( HFILE hf )
{
    BYTE  hdr[HDRSIZE];
    UINT  done;
    long  size;
    int   i, hdrW, hdrH;

    done = _lread( hf, hdr, HDRSIZE );
    if( done != HDRSIZE ) { lastErr = 2; return FALSE; }
    if( hdr[0]!='D' || hdr[1]!='S' || hdr[2]!='P' || hdr[3]!='1' )
        { lastErr = 2; return FALSE; }

    nFrames = (int)( hdr[4] | ((UINT)hdr[5] << 8) );
    hdrW    = (int)( hdr[6] | ((UINT)hdr[7] << 8) );
    hdrH    = (int)( hdr[8] | ((UINT)hdr[9] << 8) );

    if( nFrames <= 0 || nFrames > MAXFRAME ) { lastErr = 3; return FALSE; }
    if( hdrW <= 0 || hdrW > 320 )            { lastErr = 3; return FALSE; }
    if( hdrH <= 0 || hdrH > 200 )            { lastErr = 3; return FALSE; }
    sprW = hdrW;
    sprH = hdrH;

    size = _llseek( hf, 0L, 2 );                    /* file size */
    if( size < 200L || size > 60000L ) { lastErr = 3; return FALSE; }

    frameSize = (size - (long)HDRSIZE) / (long)nFrames;
    /* every frame must be exactly the size the DIB layout implies */
    {
        long need = 40L + 64L
                  + (long)(((sprW * 4 + 31) / 32) * 4) * (long)sprH;
        if( frameSize != need ) { lastErr = 3; return FALSE; }
    }

    hBank = GlobalAlloc( GMEM_MOVEABLE, (DWORD)size );
    if( !hBank ) { lastErr = 4; return FALSE; }
    lpBank = GlobalLock( hBank );
    if( !lpBank ) { lastErr = 4; return FALSE; }

    _llseek( hf, 0L, 0 );
    done = _lread( hf, lpBank, (UINT)size );
    if( done != (UINT)size ) { lastErr = 2; return FALSE; }

    /* walk the frames */
    for( i = 0; i < nFrames; i++ )
        if( !MakeFrame( i ) ) return FALSE;

    gLoaded = TRUE;
    return TRUE;
}

/* Try a list of candidate paths.  Windows shares one DOS current
   directory between all applications, so a bare "DSPET.SPR" is NOT
   guaranteed to resolve next to the EXE - the caller passes the module
   directory first, then the current directory as a fallback. */
BOOL Spr_Load( LPCSTR const *cand, int nCand )
{
    int   i;
    HFILE hf = HFILE_ERROR;

    lastErr  = 1;
    hdcColor = CreateCompatibleDC( NULL );
    hdcMask  = CreateCompatibleDC( NULL );
    if( !hdcColor || !hdcMask ) { lastErr = 5; return FALSE; }

    /* A 1bpp bitmap used as the SOURCE of a blit into a deeper DC is
       expanded to one full pixel per source bit before the raster op is
       applied: 1 becomes the DC's text colour, 0 its background colour.
       That is what makes the icon blit work at all, and it is also what
       makes a monochrome build dangerous on a 16-colour screen - leave
       the defaults alone and the "white" bits arrive as black.  Setting
       both explicitly costs two calls and removes the question.

       This does nothing to the colour path: those bitmaps are 4bpp, and
       a source that already matches the destination is never expanded. */
    SetTextColor( hdcColor, 0x00FFFFFFL );      /* 1 -> white */
    SetBkColor  ( hdcColor, 0x00000000L );      /* 0 -> black */
    SetTextColor( hdcMask,  0x00FFFFFFL );      /* 1 -> keep destination */
    SetBkColor  ( hdcMask,  0x00000000L );      /* 0 -> punch a hole */

    for( i = 0; i < nCand; i++ )
    {
        if( !cand[i] || !cand[i][0] ) continue;
        hf = OpenRead( cand[i] );
        if( hf != HFILE_ERROR ) break;
    }
    if( hf == HFILE_ERROR ) return FALSE;

    lastErr = 0;
    {
        BOOL ok = LoadAll( hf );
        _lclose( hf );
        return ok;
    }
}

int  Spr_Count( void ) { return nFrames; }
int  Spr_W( void )     { return sprW; }
int  Spr_H( void )     { return sprH; }

void Spr_Draw( HDC hdc, int x, int y, int frame )
{
    Spr_DrawPart( hdc, x, y, frame, 0, 0, sprW, sprH );
}

/* Blit only a sub-rectangle of the sprite.  Used for lip-sync so that the
   cost of one mouth update is a few hundred pixels instead of 4000 - the
   audio stream is blocking, and every microsecond here is a glitch. */
void Spr_DrawPart( HDC hdc, int x, int y, int frame, int l, int t, int r, int b )
{
    HBITMAP old;

    if( frame < 0 || frame >= nFrames ) return;
    if( !hdc || !hdcColor ) return;
    if( !hColor[frame] || !hMask[frame] ) return;   /* bank rebuilt mid-air */

    if( l < 0 ) l = 0;
    if( t < 0 ) t = 0;
    if( r > sprW ) r = sprW;
    if( b > sprH ) b = sprH;
    if( r <= l || b <= t ) return;

    old = SelectObject( hdcMask, hMask[frame] );
    BitBlt( hdc, x + l, y + t, r - l, b - t, hdcMask, l, t, SRCAND );
    SelectObject( hdcMask, old );

    old = SelectObject( hdcColor, hColor[frame] );
    BitBlt( hdc, x + l, y + t, r - l, b - t, hdcColor, l, t, SRCPAINT );
    SelectObject( hdcColor, old );
}

void Spr_Free( void )
{
    DropFrames();
    gLoaded = FALSE;
    nFrames = 0;
    if( hdcColor ) { DeleteDC( hdcColor ); hdcColor = NULL; }
    if( hdcMask )  { DeleteDC( hdcMask );  hdcMask  = NULL; }
    if( hBank )    { GlobalUnlock( hBank ); GlobalFree( hBank ); hBank = NULL; }
    lpBank = NULL;
}
