/* =====================================================================
 *  LINK.C  -  hardware report for the "Hardware check" menu item
 *
 *  HISTORY.  Every version of this file died for a different reason, and
 *  each reason is recorded here because all three are invisible when you
 *  read the source and obvious when you read the log:
 *
 *  0.2  probed COM and LPT ports with IN/OUT from inside a menu handler.
 *       Touching 0x3BC (the MDA/LCD range on a PS/2) or an absent 0x278
 *       from a Windows application is not recoverable: the port can
 *       belong to a driver and the trap handler has no way back.
 *
 *  0.4  removed the port I/O and still died, after a visible stall.
 *       The stall was GlobalCompact(0L) - that is not a query, it really
 *       compacts the global heap.  GlobalCompact(-1L) only reports.
 *       GetModuleFileName on the DISPLAY driver module went too: a
 *       driver module handle is not an ordinary instance handle.
 *
 *  0.5  died instantly, and DSPET.LOG named the spot.  The last line was
 *       "hw: GetVersion", so it died building the version line, i.e. in
 *       wsprintf.  The reason is worth remembering:
 *
 *         USER's wsprintf treats "%s" as a NEAR pointer.  It takes the
 *         two-byte offset and reads through the CALLER's DS, which for
 *         this program is DGROUP.  But this program's stack is its own
 *         segment - the NE header says SS:SP = 21C6:0001 while DGROUP is
 *         segment 2 and only about 5 KB in total - so a stack buffer
 *         handed to "%s" is read as DS:0FFxx.  That is past the end of
 *         the segment: protection violation, application terminated, and
 *         in protected mode no message box at all.
 *
 *         "%Fs" would have been the correct escape, and that is what 0.4
 *         used - which is exactly why 0.4 got further.  The honest fix,
 *         though, is to stop handing local buffers to a variadic call in
 *         the first place.  Nothing in this file uses wsprintf any more:
 *         strings are built with lstrcpy/lstrcat, which take a far
 *         pointer, and numbers with CatNum.
 *
 *  Every API call below is preceded AND followed by its own line in
 *  DSPET.LOG.  That is the only debugger available on the target
 *  machine, and it is how 0.5 got localised to a single statement.
 * ===================================================================== */
#include "dspet.h"

/* own copy of the logger: reaching back into main.c's static Log() would
   need a far function pointer across segments, and there is nothing to be
   gained by that risk in a file whose whole purpose is to stop crashing */
static void LLog( LPCSTR s )
{
    OFSTRUCT of;
    HFILE hf;
    char  path[160];
    int   n;

    lstrcpy( path, szAppDir );
    lstrcat( path, "\\DSPET.LOG" );

    hf = OpenFile( path, &of, OF_READWRITE );
    if( hf == HFILE_ERROR )
        hf = OpenFile( path, &of, OF_CREATE | OF_READWRITE );
    if( hf == HFILE_ERROR ) return;

    _llseek( hf, 0L, 2 );
    n = lstrlen( s );
    _lwrite( hf, (LPCSTR)s, n );
    _lwrite( hf, "\r\n", 2 );
    _lclose( hf );
}

static char szReport[1000];

/* Append with a hard budget and a guaranteed terminator.
   No lstrcpyn here, and that is deliberate: lstrcpyn is the one call in
   this file that has never survived a run.  0.2, 0.4, 0.5 and 0.6 all
   died inside this function, and the 0.6 log narrows the fault to a
   single statement between "hw: build version text" and the next line -
   which can only be the first Cat here.  lstrcpy and lstrcat are called
   by every log line, dozens of times per run, without trouble, so a
   plain byte loop is the one form whose behaviour on 3.0 is not in
   question.  It also fixes something lstrcpyn got wrong on its own: in
   Win16 it does not write the null when it truncates. */
static void Cat( LPSTR dst, LPCSTR s )
{
    int n = 0;

    /* find the end without lstrlen as well: this path is now completely
       free of API calls, so nothing about it depends on how KERNEL
       behaves on this particular Windows version */
    while( dst[n] && n < 890 ) n++;
    while( *s && n < 890 ) dst[n++] = *s++;
    dst[n] = 0;
}

/* Decimal append.  Deliberately NOT wsprintf: see the history above.
   Reverses into a local array, then hands the tail to Cat, which takes a
   far pointer and therefore keeps the segment. */
static void CatNum( LPSTR dst, int v )
{
    char     t[12];
    int      i = 11;
    unsigned u;

    t[i] = 0;
    u = ( v < 0 ) ? (unsigned)( -(long)v ) : (unsigned)v;
    do
    {
        t[--i] = (char)( '0' + (int)( u % 10 ) );
        u /= 10;
    } while( u && i > 0 );

    if( v < 0 && i > 0 ) t[--i] = '-';
    Cat( dst, t + i );
}

LPSTR Link_Report( void )
{
    /* A plain 2-D char array, not an array of initialised far pointers.
       That kind of array is data the loader has to fix up, and this file
       is not the place to re-open that question. */
    static const char portName[7][5] = {
        "COM1", "COM2", "COM3", "COM4", "LPT1", "LPT2", "LPT3"
    };
    char  val[40];
    DWORD flags, ver;
    HDC   hdc;
    int   i, kb, cx, cy, ncol;

    LLog( "== hw: begin ==" );

    lstrcpy( szReport, "DSPet hardware report\r\n----------------------\r\n" );
    LLog( "hw: header written" );

    LLog( "hw: GetWinFlags ..." );
    flags = GetWinFlags();
    LLog( "hw: GetWinFlags ok" );

    LLog( "hw: GetVersion ..." );
    ver = GetVersion();
    LLog( "hw: GetVersion ok" );

    /* one log line per statement while this section is still suspect: the
       previous three rounds were all lost to "somewhere in here" */
    LLog( "hw: v1 Cat literal" );
    Cat( szReport, "Windows " );
    LLog( "hw: v1 ok" );

    LLog( "hw: v2 CatNum major" );
    CatNum( szReport, (int)LOBYTE( LOWORD( ver ) ) );
    LLog( "hw: v2 ok" );

    LLog( "hw: v3 Cat dot" );
    Cat( szReport, "." );
    LLog( "hw: v3 ok" );

    LLog( "hw: v4 CatNum minor" );
    CatNum( szReport, (int)HIBYTE( LOWORD( ver ) ) );
    LLog( "hw: v4 ok" );

    LLog( "hw: v5 Cat mode" );
    if( flags & WF_ENHANCED )      Cat( szReport, "\r\n386 enhanced mode\r\n" );
    else if( flags & WF_STANDARD ) Cat( szReport, "\r\nstandard mode\r\n" );
    else                           Cat( szReport, "\r\nreal mode\r\n" );
    LLog( "hw: version text ok" );

    LLog( "hw: GetDC ..." );
    hdc = GetDC( NULL );
    LLog( "hw: GetDC ok" );

    if( hdc )
    {
        LLog( "hw: GetDeviceCaps HORZRES ..." );
        cx = GetDeviceCaps( hdc, HORZRES );
        LLog( "hw: GetDeviceCaps VERTRES ..." );
        cy = GetDeviceCaps( hdc, VERTRES );
        LLog( "hw: GetDeviceCaps NUMCOLORS ..." );
        ncol = GetDeviceCaps( hdc, NUMCOLORS );
        LLog( "hw: ReleaseDC ..." );
        ReleaseDC( NULL, hdc );
        LLog( "hw: ReleaseDC ok" );

        Cat( szReport, "Screen " );
        CatNum( szReport, cx );
        Cat( szReport, " x " );
        CatNum( szReport, cy );
        Cat( szReport, ", " );
        CatNum( szReport, ncol );
        Cat( szReport, " colours\r\n" );
        LLog( "hw: screen text ok" );
    }
    else
    {
        Cat( szReport, "Screen: GetDC failed\r\n" );
        LLog( "hw: GetDC returned 0" );
    }

    /* -1 is the query form: it returns the largest free block without
       moving anything.  0 would compact the heap, which on this machine
       is a visible pause that buys the caller nothing. */
    LLog( "hw: GlobalCompact(-1) ..." );
    kb = (int)( GlobalCompact( -1L ) / 1024L );
    LLog( "hw: GlobalCompact ok" );

    Cat( szReport, "Largest free block: " );
    CatNum( szReport, kb );
    Cat( szReport, " KB\r\n" );

    LLog( "hw: GetProfileString loop ..." );
    Cat( szReport, "Ports in WIN.INI:" );
    for( i = 0; i < 7; i++ )
    {
        val[0] = 0;
        GetProfileString( "ports", portName[i], "", val, (int)sizeof(val) );
        if( i == 4 ) Cat( szReport, "\r\n" );
        Cat( szReport, "  " );
        Cat( szReport, portName[i] );
        Cat( szReport, val[0] ? " yes" : " --" );
    }
    LLog( "hw: GetProfileString loop ok" );

    Cat( szReport, "\r\nNo port was touched, so this cannot hang the machine." );
    LLog( "hw: report built" );

    /* Also put the finished report in the log.  If the message box is what
       dies, the hardware details are still in DSPET.LOG instead of lost. */
    LLog( "-- report begins --" );
    LLog( szReport );
    LLog( "-- report ends --" );
    return szReport;
}
