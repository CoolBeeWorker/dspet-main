/* =====================================================================
 *  SND.C  -  PC speaker PCM playback (no sound card required)
 *
 *  IBM PS/2 laptops of the 386 era have no Sound Blaster; they have the
 *  keyboard-controller speaker driven by 8253 channel 2.  We turn that
 *  into an 8-bit DAC with the classic one-shot PWM trick:
 *
 *      for each sample, program ch2 mode-0 twice -
 *      once for the "high" time (duty), once for the "low" time -
 *      polling port 61h bit 5 (the timer OUT pin) for each edge.
 *
 *  16 I/O writes per sample at 8 kHz; that is ~10 % of a 386/20 and it
 *  is *blocking*, so a phrase is played in one go while a hook keeps the
 *  lips in sync.  Windows 3.x is cooperatively multitasked; nothing else
 *  can run during that second.  That is exactly how 1992 shareware did
 *  it, and it is on the list to improve if it bothers you.
 * ===================================================================== */
#include "dspet.h"
#include "portio.h"

#define PORT_SPK  0x61
#define PORT_PITC 0x43
#define PORT_PIT2 0x42
#define PIT_BASE  1193180L

/* --- edge wait: must be real asm, the optimiser may hoist PortIn() ------- */
static void WaitOutHigh( void );
#pragma aux WaitOutHigh =  \
    "mov dx,61h"           \
    "WH1:"                 \
    "in al,dx"             \
    "test al,20h"          \
    "jz WH1"               \
    modify [ax dx];

static void PitProg( WORD count )
{
    PortOut( PORT_PITC, 0xB0 );            /* ch2, lobyte/hibyte, mode 0 */
    PortOut( PORT_PIT2, count & 0xFF );
    PortOut( PORT_PIT2, (count >> 8) & 0xFF );
}

/* --- state ----------------------------------------------------------- */
static HANDLE hBank;
static LPSTR  lpBank;
static UINT   bankSize;          /* <= 60000, so 16-bit offsets are safe */
static int    nPhrase, rate;
static WORD   tps;                      /* PIT ticks per sample */
static int    spkOnVal, spkOffVal;
static int    g_level;
static BOOL   g_busy;
static void (__far *g_hook)(int);

void Snd_SetHook( void (__far *hook)(int) )
{
    g_hook = hook;
}

/* --- bank -------------------------------------------------------------*/
BOOL Snd_LoadBank( LPCSTR szFile )
{
    OFSTRUCT of;
    HFILE hf;
    char  hdr[8];
    UINT  done;
    long  size;

    hf = OpenFile( szFile, &of, OF_READ );
    if( hf == HFILE_ERROR ) return FALSE;

    done = _lread( hf, hdr, 8 );
    if( done != 8 ) { _lclose(hf); return FALSE; }
    if( hdr[0]!='D' || hdr[1]!='S' || hdr[2]!='P' || hdr[3]!='A' )
        { _lclose(hf); return FALSE; }

    {
        int cnt = (int)( (BYTE)hdr[4] | ((WORD)(BYTE)hdr[5] << 8) );
        int rt  = (int)( (BYTE)hdr[6] | ((WORD)(BYTE)hdr[7] << 8) );
        if( cnt <= 0 || cnt > 64 || rt < 4000 || rt > 16000 )
            { _lclose(hf); return FALSE; }
        /* kept local: nPhrase must stay 0 unless the whole bank loads,
           otherwise Snd_Count() lies and the caller plays garbage */
    }

    size = _llseek( hf, 0L, 2 );
    /* 60000, not 65535: Windows 3.x hands back one selector per block and
       offset arithmetic inside it stays 16-bit */
    if( size < 16L || size > 60000L ) { _lclose(hf); return FALSE; }
    _llseek( hf, 0L, 0 );

    hBank = GlobalAlloc( GMEM_MOVEABLE, (DWORD)size );
    if( !hBank ) { _lclose(hf); return FALSE; }
    lpBank = GlobalLock( hBank );
    if( !lpBank ) { _lclose(hf); return FALSE; }

    done = _lread( hf, lpBank, (UINT)size );
    _lclose( hf );
    if( done != (UINT)size ) return FALSE;

    nPhrase  = (int)( (BYTE)hdr[4] | ((WORD)(BYTE)hdr[5] << 8) );
    rate     = (int)( (BYTE)hdr[6] | ((WORD)(BYTE)hdr[7] << 8) );
    bankSize = (UINT)size;
    tps      = (WORD)( PIT_BASE / (long)rate );
    return TRUE;
}

int  Snd_Count( void ) { return nPhrase; }
BOOL Snd_Busy( void )  { return g_busy; }
int  Snd_Level( void ) { return g_level; }

/* --- init ------------------------------------------------------------*/
BOOL Snd_Init( void )
{
    int v = PortIn( PORT_SPK ) | 0x01;      /* keep the gate open, speaker off */
    spkOnVal  = v | 0x02;
    spkOffVal = v & ~0x02;
    PortOut( PORT_SPK, spkOffVal );
    g_busy = FALSE;
    g_level = 0;
    return TRUE;
}

void Snd_Stop( void )
{
    PortOut( PORT_SPK, spkOffVal );
    g_busy = FALSE;
    g_level = 0;
}

/* --- one-shot tone ---------------------------------------------------*/
void Snd_Beep( int hz, int ms )
{
    DWORD t0;
    WORD  c;

    if( hz < 40 ) hz = 40;
    if( hz > 8000 ) hz = 8000;
    c = (WORD)( PIT_BASE / (long)hz );

    PortOut( PORT_PITC, 0xB6 );             /* ch2, mode 3 square wave */
    PortOut( PORT_PIT2, c & 0xFF );
    PortOut( PORT_PIT2, (c >> 8) & 0xFF );
    PortOut( PORT_SPK, spkOnVal );

    t0 = GetTickCount();
    while( (GetTickCount() - t0) < (DWORD)ms )
        ;

    PortOut( PORT_SPK, spkOffVal );
}

/* --- blocking playback of one phrase ---------------------------------*/
/* The directory is walked with a 16-bit OFFSET, not a far pointer.  Adding
 * an int to an LPSTR in the medium model wraps inside one segment, and a
 * bank that crossed a 64K boundary would silently walk off the block. */
BOOL Snd_Play( int phrase )
{
    UINT  off, end, len;
    int   idx, i, peak;
    UINT  np;

    if( phrase < 0 || phrase >= nPhrase || !lpBank ) return FALSE;
    if( g_busy ) return FALSE;

    /* 8-byte header, then nPhrase * (u16 len, u16 rsv) */
    off = 8;
    for( idx = 0; idx < phrase; idx++ )
    {
        if( off + 4 >= bankSize ) return FALSE;
        len  = (UINT)(BYTE)lpBank[off] | ((UINT)(BYTE)lpBank[off + 1] << 8);
        off += 4 + len;
    }
    if( off + 4 >= bankSize ) return FALSE;

    len  = (UINT)(BYTE)lpBank[off] | ((UINT)(BYTE)lpBank[off + 1] << 8);
    off += 4;
    end  = off + len;
    if( len == 0 || end > bankSize ) return FALSE;

    g_busy  = TRUE;
    g_level = 0;
    i = 0;

    while( off < end )
    {
        WORD s = (WORD)(BYTE)lpBank[off++];
        WORD duty, rest;

        /* 8-bit unsigned -> 1 .. tps-1 PIT ticks */
        duty = (WORD)( ((DWORD)s * (DWORD)(tps - 2)) / 255UL ) + 1;
        rest = (WORD)( tps - duty );

        PortOut( PORT_SPK, spkOnVal );
        PitProg( duty );
        WaitOutHigh();
        PortOut( PORT_SPK, spkOffVal );
        PitProg( rest );
        WaitOutHigh();

        if( (++i & 255) == 0 )
        {
            /* every ~32 ms: report the envelope so the caller can move the
               mouth.  The caller must keep its repaint cheap (dirty rect),
               otherwise the 8 kHz stream stutters. */
            peak = 0;
            for( np = 0; np < 64 && (off + np) < end; np++ )
            {
                int d = (int)(BYTE)lpBank[off + np] - 128;
                if( d < 0 ) d = -d;
                if( d > peak ) peak = d;
            }
            g_level = peak >> 5;                  /* 0..3 */
            if( g_hook ) g_hook( g_level );
        }
    }

    PortOut( PORT_SPK, spkOffVal );
    g_busy  = FALSE;
    g_level = 0;
    return TRUE;
}

void Snd_Pump( void ) { /* playback is blocking; nothing to pump */ }

void Snd_Free( void )
{
    Snd_Stop();
    if( hBank ) { GlobalUnlock( hBank ); GlobalFree( hBank ); hBank = NULL; }
    nPhrase = 0;
    bankSize = 0;
}
