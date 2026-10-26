/* =====================================================================
 *  MAIN.C  -  DeepSeek Desktop Pet, Windows 3.0 / 3.1, 16-bit
 *
 *  Transparency without SetWindowRgn (that is Win95): the window keeps a
 *  copy of the desktop that is *underneath* it, and paints desktop copy +
 *  sprite on every WM_PAINT.  Moving is: paint the old copy back onto the
 *  screen, grab the new copy, move the window.  Because the pet is always
 *  inside the rectangle we just restored, the new grab can never catch
 *  the pet itself.  This is how Neko for Windows did it in 1991.
 * ===================================================================== */
#include "dspet.h"

HINSTANCE hInst;
HWND      hWnd;
char      szAppDir[128];

static HBITMAP hBg;
static HDC     hBgDC;
/* Everything that reaches the screen is composed here first, so the screen
   ever only sees ONE SRCCOPY per update.  See ComposeRect(). */
static HBITMAP hFrame;
static HDC     hFrameDC;
static int     curX, curY;
static BOOL    solidMode;

static int     petState;
static int     petFrame = F_IDLE0;
static int     lastDrawn = -1;
static DWORD   tickCount;
static int     idleTicks;
static int     happyTicks;

/* How the sprite is rendered:
 *   0  colour   - the 4bpp artwork, blitted as it is
 *   1  mono     - rebuilt as 1bpp by this program (normal polarity)
 *   2  mono+inv - the same, with black and white swapped
 *
 * This is a user choice, not a driver property, which is the whole point
 * of 0.9's second half: a PS/2 with a monochrome monitor still runs
 * Windows with the COLOUR VGA driver (vga.drv reports 16 colours - the
 * driver has no idea what glass is plugged into it), so the automatic
 * test in WinMain says "colour" while the screen is black and white.
 * The driver's opinion is only a default; this is the override. */
static int     lookMode;

/* walking */
static int     restTicks = 60;   /* idle ticks before the next stroll   */
static int     walkLeft;         /* ticks left in this stroll           */
static int     walkDir  = 1;     /* +1 right, -1 left                   */

/* the context menu is opened from the main loop, so the click point is
   parked here for the posted message to pick up */
static POINT   menuPt;

/* A second copy cannot just refuse: if the running pet has somehow lost
   its window the user would be locked out.  A registered message is the
   only cross-task channel in 3.0 that needs no shared memory, so the
   running copy answers it by showing itself on top. */
static UINT    msgWake;

/* set once, so a permanently hidden window does not fill the log */
static BOOL    warnedHidden;

static BOOL    dragging, dragMoved;
static POINT   dragOrg, dragWin;
static POINT   dragCur;

/* ------------------------------------------------------------------ */
static void PathCat( LPSTR dst, LPCSTR base, LPCSTR name )
{
    lstrcpy( dst, base );
    lstrcat( dst, "\\" );
    lstrcat( dst, name );
}

static void Log( LPCSTR s )
{
    OFSTRUCT of;
    HFILE hf;
    char  path[160];

    PathCat( path, szAppDir, "DSPET.LOG" );
    hf = OpenFile( path, &of, OF_READWRITE );
    if( hf == HFILE_ERROR )
        hf = OpenFile( path, &of, OF_CREATE | OF_READWRITE );
    if( hf == HFILE_ERROR ) return;
    _llseek( hf, 0L, 2 );
    _lwrite( hf, (LPCSTR)s, lstrlen(s) );
    _lwrite( hf, "\r\n", 2 );
    _lclose( hf );
}

/* Decimal append for log lines.
   This replaces wsprintf, and the reason is not style.  In Win16, "%s" in
   USER's wsprintf is a NEAR pointer: it uses only the offset and reads
   through the caller's DS, which is DGROUP.  This program's stack is a
   separate segment (the NE header says SS:SP = 21C6:0001, while DGROUP is
   segment 2 and about 5 KB in total), so a stack buffer passed to "%s" is
   read as DS:0FFxx - past the end of the segment.  That is a protection
   violation in protected mode, and the application vanishes without a
   dialog.  It is exactly what killed the hardware check in 0.5.  Literals
   happened to work because they live in DGROUP at small offsets, but
   "works because of where the linker put it" is not a foundation. */
static void LogNum( LPSTR dst, int v )
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
    lstrcat( dst, t + i );
}

/* "tag ax b" in one line - used for geometry, so the log can show whether
   the pet actually moved and whether the window is where it thinks it is */
static void LogPos( LPCSTR tag, int a, int b )
{
    char t[80];

    lstrcpy( t, tag );
    LogNum( t, a );
    lstrcat( t, "," );
    LogNum( t, b );
    Log( t );
}

/* Start a new section in the log, and keep it bounded.  Without this the
   file grows across runs and "the last line" - which is how we localise a
   crash on a machine with no debugger - stops being the interesting one. */
static void LogStart( void )
{
    OFSTRUCT of;
    HFILE hf;
    char  path[160];
    long  sz;

    PathCat( path, szAppDir, "DSPET.LOG" );
    hf = OpenFile( path, &of, OF_READWRITE );
    if( hf != HFILE_ERROR )
    {
        sz = _llseek( hf, 0L, 2 );
        _lclose( hf );
        if( sz > 16000L )
        {
            hf = OpenFile( path, &of, OF_CREATE | OF_READWRITE );
            if( hf != HFILE_ERROR ) _lclose( hf );
        }
    }
    Log( "================ DSPet run starts ================" );
}

static BOOL HasArg( LPSTR cmd, LPCSTR key )
{
    int i, j;
    if( !cmd ) return FALSE;
    for( i = 0; cmd[i]; i++ )
    {
        for( j = 0; key[j]; j++ )
            if( cmd[i+j] != key[j] ) break;
        if( !key[j] ) return TRUE;
    }
    return FALSE;
}

/* ------------------------ background capture ----------------------- */
static void GrabBg( int x, int y )
{
    HDC hs = GetDC( NULL );
    if( hs )
    {
        BitBlt( hBgDC, 0, 0, SPRW, SPRH, hs, x, y, SRCCOPY );
        ReleaseDC( NULL, hs );
    }
}

static void PutBg( int x, int y )
{
    HDC hs = GetDC( NULL );
    if( hs )
    {
        BitBlt( hs, x, y, SPRW, SPRH, hBgDC, 0, 0, SRCCOPY );
        ReleaseDC( NULL, hs );
    }
}

/* Is the desktop we just photographed mostly light?
 *
 * Only consulted on a 2-colour driver, and only to choose the polarity of
 * the pet.  A black-and-white display has no shades: either the pet is a
 * dark shape on a light desktop or a light shape on a dark one, and which
 * one it must be is a property of the desktop, not of the pet.  Windows
 * 3.0's default desktop is white, so the pet is normally built dark; a
 * user who runs a black desktop (and the target machine does, because its
 * monitor inverts everything) gets the other polarity automatically.
 *
 * Sampled on a 4-pixel grid: 252 GetPixel calls instead of 4032, and the
 * answer cannot change by more than a few percent. */
static BOOL BgLooksLight( void )
{
    int x, y, n = 0, light = 0;

    if( !hBgDC ) return FALSE;
    for( y = 0; y < SPRH; y += 4 )
        for( x = 0; x < SPRW; x += 4 )
        {
            COLORREF k = GetPixel( hBgDC, x, y );
            if( k == (COLORREF)0xFFFFFFFFL ) continue;   /* CLR_INVALID */
            n++;
            if( k != 0 ) light++;
        }
    if( n == 0 ) return FALSE;
    return ( light * 2 >= n );
}

/* ---------------------- composition --------------------------------- */
/* Version 0.4 blitted the mask with SRCAND and the colour with SRCPAINT
   straight onto the window DC.  That is two passes over the same pixels,
   and between them the destination is a black silhouette.  On a 386 the
   second pass lands late enough to be seen, and when the same rectangle
   is being rewritten 30 times a second the eye reads it as that part of
   the character having disappeared.

   Now the desktop copy and the sprite are merged in an off-screen bitmap
   and the result is put on screen with a single SRCCOPY.  There is no
   intermediate black state to see, and a partial update is one small
   blit instead of two plus a restore. */
static void ComposeRect( int l, int t, int r, int b )
{
    BitBlt( hFrameDC, l, t, r - l, b - t, hBgDC, l, t, SRCCOPY );
    Spr_DrawPart( hFrameDC, 0, 0, petFrame, l, t, r, b );
}

static void ComposeAll( void )
{
    ComposeRect( 0, 0, SPRW, SPRH );
}

static void BlitRect( int l, int t, int r, int b )
{
    HDC hdc = GetDC( hWnd );
    if( !hdc ) return;
    BitBlt( hdc, l, t, r - l, b - t, hFrameDC, l, t, SRCCOPY );
    ReleaseDC( hWnd, hdc );
}

/* Redraw from the composed bitmap.  No InvalidateRect: we already have the
   finished picture, so asking USER to send WM_PAINT only adds a round trip
   and an erase we do not need.  WM_PAINT is still handled, for the times
   Windows uncovers us on its own. */
static void Repaint( void )
{
    ComposeAll();
    BlitRect( 0, 0, SPRW, SPRH );
}

static void PetMoveTo( int nx, int ny )
{
    if( nx == curX && ny == curY ) return;

    PutBg( curX, curY );          /* erase the pet from the screen   */
    GrabBg( nx, ny );             /* the pet is gone, so this is pure
                                     desktop - even when the old and
                                     new rectangles overlap          */
    curX = nx; curY = ny;

    /* compose BEFORE the move: SetWindowPos can synchronously deliver
       WM_PAINT, and that would paint the old picture at the new place
       for one frame */
    ComposeAll();
    /* SWP_NOREDRAW: USER would otherwise generate a WM_PAINT for the
       whole window on every step (the class used to be CS_HREDRAW |
       CS_VREDRAW, so every move invalidated all 72x56 of it).  We blit
       the finished frame ourselves two lines below, and the part of the
       screen we uncover was already written by PutBg.  That removes one
       complete repaint per 55 ms tick. */
    SetWindowPos( hWnd, NULL, nx, ny, 0, 0,
                  SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_NOREDRAW );
    BlitRect( 0, 0, SPRW, SPRH );
}

/* NOTE 0.8 - the whole "refresh the desktop copy" machinery is gone.
   It grew from 0.5 to 0.7: hide the window, pump the message queue, force
   the window underneath to repaint with InvalidateRect + UpdateWindow,
   then photograph, then show the window again.  Every single unexplained
   death in the 0.7 log happens on a path that ends in that function, and
   the visual result was worse than what it was meant to cure: a pet that
   vanished, and only a translucent smudge of somebody else's window
   sliding around the desktop.

   The capture pair that does work is the 1991 one, and it does not need
   any of that: PutBg writes the saved desktop back into the framebuffer
   (our window is still on top, but a blit to the screen DC writes the
   framebuffer regardless), then GrabBg reads that framebuffer back.  The
   pet is gone from the framebuffer at that instant, so the picture is
   honest for the overlapping case.  It also refreshes itself as the pet
   travels, because every step captures pixels that were never covered.

   After a modal box the saved copy is still valid - the box never painted
   into it - so all that is needed is Repaint(). */

/* ------------------------ cheap lip-sync --------------------------- */
/* Only the mouth is redrawn.  These bounds MUST be the mouth and nothing
   else: 0.4 used 26..46 x 28..40, a 20x12 box that also covered the chin,
   the neck, the collar and the apron bib.  Every audio update rewrote all
   of it, so the most recognisable part of the character was the part
   being churned 30 times a second - which is exactly what "most of her
   vanishes while she talks" was.

   genart.py stamps the mouth at (35, 27) and the widest shape is 3x3, so
   a 7x6 box centred on it with one pixel of margin is enough. */
#define MOUTH_L 33
#define MOUTH_T 25
#define MOUTH_R 40
#define MOUTH_B 31

static void DrawMouthOnly( void )
{
    ComposeRect( MOUTH_L, MOUTH_T, MOUTH_R, MOUTH_B );
    BlitRect( MOUTH_L, MOUTH_T, MOUTH_R, MOUTH_B );
}

static void __far Lipsync( int level )
{
    int f;
    if( level <= 1 )      f = F_TALK0;
    else if( level == 2 ) f = F_TALK1;
    else                  f = F_TALK2;

    if( f != petFrame )
    {
        petFrame = f;
        lastDrawn = f;
        DrawMouthOnly();
    }
}

/* ------------------------ behaviour -------------------------------- */
static void SetFrame( int f )
{
    if( f == petFrame ) return;
    petFrame = f;
    Repaint();
}

static void Speak( int phrase )
{
    int prev = petState;

    if( Snd_Count() <= 0 || phrase < 0 || phrase >= Snd_Count() )
    {
        Snd_Beep( 880, 60 );
        return;
    }
    petState = ST_TALK;
    petFrame = F_TALK1;
    Repaint();
    Log( "speak: start" );
    Snd_Play( phrase );           /* blocking, hook moves the mouth */
    Log( "speak: done" );
    petState = (prev == ST_SLEEP) ? ST_IDLE : prev;
    petFrame = (petState == ST_HAPPY) ? F_HAPPY : F_IDLE0;
    lastDrawn = -1;
    Repaint();
}

static void StartWalk( void )
{
    DWORD t = GetTickCount();

    walkDir   = (t & 0x40) ? 1 : -1;
    walkLeft  = 34 + (int)( t % 70 );     /* ~1.9 .. 5.7 s at 55 ms  */
    petState  = ST_WALK;
    idleTicks = 0;

    /* the log is the only instrument on the target machine, so record the
       start of every stroll: if the pet "disappears while walking", the
       presence or absence of "walk: end" says whether it was still alive */
    {
        char t[48];
        lstrcpy( t, "walk: start dir=" );
        LogNum( t, walkDir );
        lstrcat( t, " ticks=" );
        LogNum( t, walkLeft );
        Log( t );
    }
    LogPos( "walk: from ", curX, curY );
}

static void Pet_Tick( void )
{
    tickCount++;

    switch( petState )
    {
    case ST_IDLE:
        idleTicks++;
        if( idleTicks > 900 ) { petState = ST_SLEEP; break; }   /* ~50 s */
        if( --restTicks <= 0 ) { StartWalk(); break; }
        if( (tickCount % 110) < 3 )          SetFrame( F_BLINK );
        else SetFrame( (tickCount & 6) ? F_IDLE1 : F_IDLE0 );
        break;

    case ST_WALK:
    {
        int maxX = GetSystemMetrics( SM_CXSCREEN ) - SPRW;
        /* ONE pixel per tick, not two.  At 55 ms a tick that is 18 px/s,
           which is a stroll and - more importantly on a 386 - it halves
           the number of erase/move/repaint cycles, so the desktop under
           her is not being repainted 18 times a second.  Two pixels per
           tick was fast enough to read as a stutter, not as walking. */
        int nx   = curX + walkDir;

        if( nx < 4 || nx > maxX - 4 )       /* bounce off the screen edge */
        {
            walkDir = -walkDir;
            nx = curX + walkDir;
        }

        /* set the frame FIRST, so the repaint PetMoveTo does anyway
           already shows the new step - two repaints per tick would
           flicker on a 386.  The leg cycle turns every four ticks, i.e.
           about 4.5 steps a second. */
        petFrame = ( walkDir > 0 ) ? ( F_WALK_R0 + ( (tickCount >> 2) & 3 ) )
                                   : ( F_WALK_L0 + ( (tickCount >> 2) & 3 ) );
        PetMoveTo( nx, curY );

        if( --walkLeft <= 0 )
        {
            petState  = ST_IDLE;
            idleTicks = 0;
            restTicks = 40 + (int)( GetTickCount() % 90 );
            SetFrame( F_IDLE0 );
            LogPos( "walk: end ", curX, curY );
        }
        break;
    }

    case ST_SLEEP:
        SetFrame( (tickCount & 8) ? F_SLEEP1 : F_SLEEP0 );
        break;

    case ST_HAPPY:
        SetFrame( F_HAPPY );
        if( --happyTicks <= 0 ) petState = ST_IDLE;
        break;

    case ST_TALK:
        /* frame is owned by Lipsync() */
        break;
    }

    /* Self-heal the one failure that would make the pet look gone while
       it is really alive: a window that lost WS_VISIBLE.  IsWindowVisible
       is the only test that can tell the difference between "covered" and
       "hidden", and it costs nothing. */
    if( !IsWindowVisible( hWnd ) )
    {
        if( !warnedHidden )
        {
            Log( "wnd: was NOT visible, showing it again" );
            warnedHidden = TRUE;
        }
        ShowWindow( hWnd, SW_SHOWNOACTIVATE );
        Repaint();
    }
}

/* ------------------------ sprite look ------------------------------ */
/* Stored in DSPET.INI next to the EXE, one digit.  A missing file, a
   read-only disk or a corrupt value all mean "use the automatic choice",
   which is what -1 says. */
#define INI_APP "DSPet"
#define INI_KEY "Look"

static int ReadLook( void )
{
    char path[160], val[8];

    PathCat( path, szAppDir, "DSPET.INI" );
    val[0] = 0;
    GetPrivateProfileString( INI_APP, INI_KEY, "", val, (int)sizeof(val), path );
    if( val[0] >= '0' && val[0] <= '2' && val[1] == 0 )
        return (int)( val[0] - '0' );
    return -1;
}

static void SaveLook( void )
{
    char path[160], val[4];

    PathCat( path, szAppDir, "DSPET.INI" );
    val[0] = (char)( '0' + lookMode );
    val[1] = 0;
    WritePrivateProfileString( INI_APP, INI_KEY, val, path );
}

/* Rebuild the whole bank from the copy of DSPET.SPR that is already in
   memory and put the result on screen.  No file is read, so this is safe
   to call from a menu item while the timer is off. */
static void ApplyLook( void )
{
    char t[40];

    Spr_SetMono( lookMode != 0 );
    Spr_SetInvert( lookMode == 2 );

    if( !Spr_Rebuild() )
    {
        Log( "look: rebuild FAILED" );
        return;
    }
    Repaint();

    lstrcpy( t, "look: " );
    lstrcat( t, ( lookMode == 0 ) ? "colour" :
                ( lookMode == 1 ) ? "mono" : "mono inverted" );
    Log( t );
}

/* ------------------------ menu ------------------------------------- */
static const char * const menuItems[] = {
    "Say hello",
    "Tell me something",
    "Walk around",
    "Hardware check",
    "Sprite look",              /* replaced at run time by LookText() */
    "About DSPet",
    "Exit"
};
#define NMENU (sizeof(menuItems)/sizeof(menuItems[0]))

static char lookText[40];

static void LookText( void )
{
    lstrcpy( lookText, "Sprite look: " );
    lstrcat( lookText, ( lookMode == 0 ) ? "colour" :
                       ( lookMode == 1 ) ? "mono" : "mono inverted" );
}

/* Every step of a menu command writes a line to DSPET.LOG first.  If the
   program dies, the last line in that file names the operation that killed
   it - which is the only debugging channel available on a machine with no
   debugger. */
static void DoMenu( int x, int y )
{
    int  sel;
    /* static, not on the stack: this buffer is handed to USER and lives
       across a modal message box, and a 12 KB stack shared with the menu
       loop is not the place for half a kilobyte */
    static char buf[600];

    Log( "menu: open" );

    /* stop the behaviour timer while the menu is up: otherwise ticks are
       dispatched into this nested loop and the pet walks away underneath
       its own menu */
    KillTimer( hWnd, ID_TIMER );
    /* the fourth entry shows the CURRENT rendering, so it is built here
       rather than being a constant in the table */
    LookText();
    {
        const char *items[8];
        int k;
        for( k = 0; k < (int)NMENU && k < 8; k++ ) items[k] = menuItems[k];
        items[4] = lookText;
        sel = Pop_Menu( hWnd, x, y, items, (int)NMENU );
    }
    Log( "menu: closed" );

    idleTicks = 0;
    restTicks = 60;
    if( petState == ST_SLEEP || petState == ST_WALK ) petState = ST_IDLE;

    switch( sel )
    {
    case 0:
        Log( "cmd: say hello" );
        petState = ST_HAPPY; happyTicks = 30; Speak( 0 );
        break;

    case 1:
        Log( "cmd: tell me something" );
        petState = ST_HAPPY; happyTicks = 30;
        Speak( 2 + (int)( GetTickCount() % 3 ) );
        break;

    case 2:
        Log( "cmd: walk" );
        StartWalk();
        break;

    case 3:
        Log( "cmd: hwcheck, enter" );
        {
            /* a byte loop instead of lstrcpyn - see the note on Cat() in
               link.c.  lstrcpyn is the one KERNEL call that has never
               survived a run here, and this line sits right after the
               report is built, so it would be the next thing to die. */
            LPSTR rs = Link_Report();
            int   k  = 0;

            while( *rs && k < 599 ) buf[k++] = *rs++;
            buf[k] = 0;
        }
        Log( "cmd: hwcheck, report ready" );
        /* NULL owner on purpose.  The pet window is a WS_EX_TOOLWINDOW
           popup that was shown with SW_SHOWNOACTIVATE and has never held
           the focus; handing it to MessageBox makes USER disable and
           re-enable a window whose focus state it does not understand,
           which is a documented way to produce "unrecoverable
           application error" in 3.0.  An ownerless box has no such
           problem. */
        Log( "cmd: hwcheck, box opening" );
        MessageBox( NULL, buf, "DSPet hardware check", MB_OK );
        Log( "cmd: hwcheck, box closed" );
        /* the box painted on the screen, never into our saved copy, so the
           copy is still the desktop that belongs under the pet */
        Repaint();
        break;

    case 4:
        /* Cycle colour -> mono -> mono inverted -> colour.
           This used to refuse to run unless the DRIVER said it had two
           colours, which is the wrong test: a PS/2 with a monochrome
           monitor still has the colour VGA driver loaded, and that driver
           reports sixteen colours no matter what is plugged into it.
           What the screen does with those sixteen colours is the monitor's
           business, and the monitor cannot be asked.  So the user decides,
           and the choice is remembered in DSPET.INI. */
        Log( "cmd: sprite look" );
        lookMode = ( lookMode + 1 ) % 3;
        ApplyLook();
        SaveLook();
        break;

    case 5:
        Log( "cmd: about" );
        MessageBox( NULL,
            "DSPet 0.9 (milestone 2)\r\n"
            "A DeepSeek whale-girl desktop pet\r\n"
            "for Windows 3.0 / 3.1\r\n\r\n"
            "Left drag  : move me\r\n"
            "Left click : say hello\r\n"
            "Right click: menu\r\n\r\n"
            "Menu > Sprite look cycles colour / mono / mono inverted.\r\n"
            "On a black and white monitor, choose mono.\r\n\r\n"
            "I walk around on my own when idle.\r\n"
            "Runs on a 386 with 2 MB, no sound card.",
            "About DSPet", MB_OK );
        Log( "cmd: about, box closed" );
        Repaint();
        break;

    case 6:
        Log( "cmd: exit" );
        App_Quit();
        break;

    default:
        Log( "menu: cancelled" );
        break;
    }

    /* "Exit" destroys the window, so only restart the timer if it is
       still alive - SetTimer on a dead HWND is a fault, not an error */
    if( IsWindow( hWnd ) ) SetTimer( hWnd, ID_TIMER, TICK_MS, NULL );
}

void App_Quit( void )
{
    Log( "app: quit requested by menu" );
    KillTimer( hWnd, ID_TIMER );
    Snd_Stop();
    DestroyWindow( hWnd );
}

void Pet_SetState( int st ) { petState = st; }

/* ------------------------ window proc ------------------------------ */
LRESULT CALLBACK __export WndProc( HWND hwnd, UINT msg, WPARAM wp, LPARAM lp )
{
    /* the private "come to the front" message has to be tested with ==,
       not in the switch, because its number is assigned at run time */
    if( msgWake && msg == msgWake )
    {
        ShowWindow( hwnd, SW_SHOWNOACTIVATE );
        SetWindowPos( hwnd, HWND_TOP, curX, curY, 0, 0,
                      SWP_NOSIZE | SWP_NOACTIVATE );
        SetTimer( hwnd, ID_TIMER, TICK_MS, NULL );
        Repaint();
        return 0;
    }

    switch( msg )
    {
    case WM_PAINT:
    {
        PAINTSTRUCT ps;
        HDC hdc = BeginPaint( hwnd, &ps );
        /* the composed bitmap is already the finished picture, so this is
           one SRCCOPY and nothing else */
        BitBlt( hdc, 0, 0, SPRW, SPRH, hFrameDC, 0, 0, SRCCOPY );
        lastDrawn = petFrame;
        EndPaint( hwnd, &ps );
        return 0;
    }
    case WM_ERASEBKGND:
        return 1;                       /* we paint every pixel ourselves */

    case WM_LBUTTONDOWN:
        idleTicks = 0;
        if( petState == ST_SLEEP ) { petState = ST_IDLE; SetFrame( F_IDLE0 ); }
        SetCapture( hwnd );
        dragging   = TRUE;
        dragMoved  = FALSE;
        {
            POINT p;
            p.x = (int)(short)LOWORD(lp);
            p.y = (int)(short)HIWORD(lp);
            ClientToScreen( hwnd, &p );
            dragOrg = p;
        }
        dragWin.x = curX;
        dragWin.y = curY;
        return 0;

    case WM_MOUSEMOVE:
    {
        POINT p;
        p.x = (int)(short)LOWORD(lp);
        p.y = (int)(short)HIWORD(lp);
        ClientToScreen( hwnd, &p );
        dragCur = p;
        idleTicks = 0;
        if( dragging )
        {
            int nx = dragWin.x + (p.x - dragOrg.x);
            int ny = dragWin.y + (p.y - dragOrg.y);
            int mw = GetSystemMetrics(SM_CXSCREEN) - SPRW;
            int mh = GetSystemMetrics(SM_CYSCREEN) - SPRH;

            if( nx < 0 ) nx = 0;  if( nx > mw ) nx = mw;
            if( ny < 0 ) ny = 0;  if( ny > mh ) ny = mh;
            if( nx != dragWin.x || ny != dragWin.y ) dragMoved = TRUE;
            PetMoveTo( nx, ny );
        }
        return 0;
    }
    case WM_LBUTTONUP:
        ReleaseCapture();
        dragging = FALSE;
        if( !dragMoved ) PostMessage( hwnd, WM_APP_HELLO, 0, 0 );
        return 0;

    case WM_RBUTTONUP:
    {
        POINT p;
        p.x = (int)(short)LOWORD(lp);
        p.y = (int)(short)HIWORD(lp);
        ClientToScreen( hwnd, &p );
        menuPt = p;
        /* Do NOT open the menu here.  Running a nested GetMessage loop from
           inside a mouse handler, with capture held and the timer still
           firing into this window, is how 0.2 managed to raise an
           unrecoverable application error.  Post it; the main loop opens it
           at top level. */
        PostMessage( hwnd, WM_APP_MENU, 0, 0 );
        return 0;
    }
    case WM_TIMER:
        if( wp == ID_TIMER ) Pet_Tick();
        return 0;

    case WM_DESTROY:
        /* logged because "the application just disappeared" has two very
           different causes on this machine: the window really was
           destroyed (this line appears) or it merely went invisible */
        Log( "wnd: WM_DESTROY -> posting WM_QUIT" );
        PostQuitMessage( 0 );
        return 0;
    }
    return DefWindowProc( hwnd, msg, wp, lp );
}

/* ------------------------ WinMain ---------------------------------- */
int PASCAL WinMain( HINSTANCE hInstance, HINSTANCE hPrev,
                    LPSTR lpCmdLine, int nCmdShow )
{
    static WNDPROC pfnThunk;
    WNDCLASS wc;
    MSG      msg;
    HDC      hdc;
    char     path[160], buf[200];
    int      sw, sh, ncol, nbp, monoMode, invert;

    hInst = hInstance;
    (void)nCmdShow;

    (void)hPrev;

    /* ONE instance only, and this test is not optional.
       In Windows 3.x hPrevInstance is ALWAYS 0, so the textbook
       "if (hPrev) { already running }" test can never fire - which is how
       two pets ended up on one desktop.  Two pets is not a cosmetic
       problem: each one photographs the screen for its background and
       each one therefore photographs the OTHER pet's pixels, then paints
       them back for ever.  That is the "translucent shadow dragging a
       window image" exactly, and it cannot heal.  Two pets also both call
       Log(), which is what those two garbled lines in the last log were:
       two writers interleaving into one file.
       FindWindow is the only reliable duplicate test in 3.x. */
    msgWake = RegisterWindowMessage( "DSPetWake" );
    {
        HWND hOld = FindWindow( "DSPetClass", NULL );

        if( hOld )
        {
            /* NOT a crash and NOT a second pet: the running one brings
               itself to the front, then this copy goes away.  Two pets is
               a rendering disaster, because each one captures the other's
               pixels as "desktop" and paints them back for ever. */
            if( msgWake ) PostMessage( hOld, msgWake, 0, 0 );
            MessageBox( NULL,
                        "DSPet is already running.\r\n"
                        "Bringing the copy on the desktop to the front.",
                        APPNAME, MB_OK | MB_ICONINFORMATION );
            return 0;
        }
    }

    /* remember where we were started from */
    GetModuleFileName( hInstance, path, 120 );
    {
        int i, k = -1;
        for( i = 0; path[i]; i++ )
            if( path[i] == '\\' ) k = i;
        if( k >= 0 ) path[k] = 0; else lstrcpy( path, "." );
    }
    lstrcpy( szAppDir, path );
    LogStart();
    solidMode = HasArg( lpCmdLine, "SOLID" );

    /* ---- window class ---- */
    pfnThunk = (WNDPROC)MakeProcInstance( (FARPROC)WndProc, hInstance );
    /* deliberately 0: the pet repaints itself, and CS_HREDRAW|CS_VREDRAW
       made USER invalidate all 4032 pixels on every 1 px step */
    wc.style         = 0;
    wc.lpfnWndProc   = pfnThunk;
    wc.cbClsExtra    = 0;
    wc.cbWndExtra    = 0;
    wc.hInstance     = hInstance;
    wc.hIcon         = LoadIcon( NULL, IDI_APPLICATION );
    wc.hCursor       = LoadCursor( NULL, IDC_ARROW );
    wc.hbrBackground = NULL;
    wc.lpszMenuName  = NULL;
    wc.lpszClassName = "DSPetClass";
    if( !RegisterClass( &wc ) ) return 0;

    /* ---- screen metrics and the off-screen buffers ----------------
       These have to exist BEFORE the sprite bank is loaded (the bank
       builds 1bpp bitmaps for a 1bpp driver) and before the desktop is
       captured.  Both buffers are DDBs created from the screen DC, so on
       a two-colour driver they are 1bpp - which is exactly what the
       monochrome path in spr.c needs. */
    hdc = GetDC( NULL );
    hBg    = CreateCompatibleBitmap( hdc, SPRW, SPRH );
    hBgDC  = CreateCompatibleDC( hdc );
    SelectObject( hBgDC, hBg );
    /* the compose target: desktop copy + sprite, merged off-screen */
    hFrame   = CreateCompatibleBitmap( hdc, SPRW, SPRH );
    hFrameDC = CreateCompatibleDC( hdc );
    SelectObject( hFrameDC, hFrame );
    sw   = GetDeviceCaps( hdc, HORZRES );
    sh   = GetDeviceCaps( hdc, VERTRES );
    ncol = GetDeviceCaps( hdc, NUMCOLORS );
    nbp  = GetDeviceCaps( hdc, BITSPIXEL ) * GetDeviceCaps( hdc, PLANES );
    ReleaseDC( NULL, hdc );

    if( !hBg || !hBgDC || !hFrame || !hFrameDC )
    {
        MessageBox( NULL, "Out of GDI memory.", APPNAME, MB_OK | MB_ICONSTOP );
        return 0;
    }

    /* ---- where to stand, and what is under our feet ----
       The desktop is captured BEFORE our window exists: a capture taken
       after CreateWindowEx would photograph the pet itself and the
       "transparent" background would be a copy of the whale. */
    curX = sw - SPRW - 16;
    curY = sh - SPRH - 40;
    if( curX < 0 ) curX = 0;
    if( curY < 0 ) curY = 0;

    if( solidMode )
    {
        /* fallback: no desktop capture, plain grey box */
        RECT r;
        r.left = 0; r.top = 0; r.right = SPRW; r.bottom = SPRH;
        FillRect( hBgDC, &r, (HBRUSH)GetStockObject( LTGRAY_BRUSH ) );
    }
    else
    {
        GrabBg( curX, curY );
    }

    /* ---- colour or two-colour -------------------------------------
       NUMCOLORS is 2 on an MDA / VGA-mono / IBM 8503 driver and 16 or
       more on anything with colour.  BITSPIXEL * PLANES is 1 only when
       the memory DCs really are one bit deep, which is the condition the
       blitter actually cares about.  Either test is enough on its own;
       both are reported so the log says which one fired.

       The polarity is then chosen from the desktop we just captured:
       a light desktop wants a dark pet, a dark desktop wants a light
       one, and on a two-colour screen there is nothing in between. */
    monoMode = ( ncol <= 2 ) || ( nbp <= 1 );   /* what the DRIVER says */
    if( HasArg( lpCmdLine, "MONO" ) )  monoMode = 1;
    if( HasArg( lpCmdLine, "COLOR" ) ) monoMode = 0;

    /* The artwork is already dark-on-light: hair and outline are the dark
       mass, face and dress are the light one.  So a LIGHT desktop needs no
       inversion at all, and only a dark desktop asks for the negative.
       (Getting this backwards is not subtle - it turns the pet into a
       handful of scattered dots, because the side that was carrying the
       silhouette merges with the background.) */
    invert = 0;
    if( monoMode && !solidMode ) invert = BgLooksLight() ? 0 : 1;

    /* Priority: command line, then the choice saved last time, then the
       driver's own answer refined by the desktop we just captured.
       A driver that says "sixteen colours" is only half the story - it
       cannot see the monitor. */
    lookMode = ReadLook();
    if( lookMode < 0 ) lookMode = monoMode ? ( invert ? 2 : 1 ) : 0;
    if( HasArg( lpCmdLine, "MONO" ) )   lookMode = 1;
    if( HasArg( lpCmdLine, "COLOR" ) )  lookMode = 0;
    if( HasArg( lpCmdLine, "INVERT" ) ) lookMode = 2;

    Spr_SetMono( lookMode != 0 );
    Spr_SetInvert( lookMode == 2 );

    /* ---- sprite bank ----
       Windows keeps ONE current directory for the whole session, so a bare
       "DSPET.SPR" does not necessarily resolve next to the EXE.  We pass
       several candidates and let the loader find the first one that opens. */
    {
        char   p1[160], msg[240];
        LPCSTR cand[3];

        PathCat( p1, szAppDir, "DSPET.SPR" );
        cand[0] = p1;
        cand[1] = "DSPET.SPR";
        cand[2] = "C:\\DSPET\\DSPET.SPR";

        if( !Spr_Load( cand, 3 ) )
        {
            lstrcpy( msg, "Cannot load the sprite bank.\r\n\r\nTried:\r\n" );
            lstrcat( msg, p1 );
            lstrcat( msg, "\r\nDSPET.SPR\r\nC:\\DSPET\\DSPET.SPR\r\n\r\nReason: " );
            switch( Spr_LastError() )
            {
            case 1: lstrcat( msg, "no such file (1)" );                  break;
            case 2: lstrcat( msg, "file damaged or short (2)" );         break;
            case 3: lstrcat( msg, "header says a different size (3)" );  break;
            case 4: lstrcat( msg, "out of memory (4)" );                 break;
            default:lstrcat( msg, "GDI refused a bitmap (5)" );          break;
            }
            MessageBox( NULL, msg, APPNAME, MB_OK | MB_ICONSTOP );
            return 0;
        }
    }

    /* one line that answers "why does it look like that?" without a
       second trip to the machine */
    {
        char t[120];
        lstrcpy( t, "gfx: " );
        LogNum( t, sw );
        lstrcat( t, "x" );
        LogNum( t, sh );
        lstrcat( t, " colours=" );
        LogNum( t, ncol );
        lstrcat( t, " bpp=" );
        LogNum( t, nbp );
        lstrcat( t, " driver=" );
        lstrcat( t, monoMode ? "mono" : "colour" );
        lstrcat( t, " look=" );
        lstrcat( t, ( lookMode == 0 ) ? "colour" :
                    ( lookMode == 1 ) ? "mono" : "mono-inverted" );
        Log( t );
    }

    /* ---- voice bank ---- */
    PathCat( path, szAppDir, "VOICE.DAT" );
    if( !Snd_LoadBank( path ) )
        Log( "voice: VOICE.DAT not loaded (pet will beep instead)" );

    hWnd = CreateWindowEx( WS_EX_TOOLWINDOW, "DSPetClass", APPNAME,
                           WS_POPUP | WS_VISIBLE,
                           curX, curY, SPRW, SPRH,
                           NULL, NULL, hInstance, NULL );
    if( !hWnd )
    {
        MessageBox( NULL, "CreateWindowEx failed.", APPNAME, MB_OK | MB_ICONSTOP );
        return 0;
    }

    Snd_Init();
    Snd_SetHook( Lipsync );
    LogPos( "wnd: created at ", curX, curY );
    {
        char t[80];
        lstrcpy( t, "wnd: " );
        LogNum( t, SPRW );
        lstrcat( t, "x" );
        LogNum( t, SPRH );
        lstrcat( t, IsWindowVisible( hWnd ) ? " visible" : " NOT visible" );
        Log( t );
    }

    ComposeAll();               /* hFrame must hold a picture before the
                                   first WM_PAINT arrives */
    ShowWindow( hWnd, SW_SHOWNOACTIVATE );
    UpdateWindow( hWnd );
    SetTimer( hWnd, ID_TIMER, TICK_MS, NULL );

    /* built by concatenation, not with wsprintf's %s - see LogNum above */
    lstrcpy( buf, "start: " );
    lstrcat( buf, solidMode ? "solid" : "transparent" );
    lstrcat( buf, "  " );
    LogNum( buf, sw );
    lstrcat( buf, "x" );
    LogNum( buf, sh );
    lstrcat( buf, "  " );
    lstrcat( buf, ( Snd_Count() > 0 ) ? "voice=on" : "voice=off" );
    Log( buf );

    while( GetMessage( &msg, NULL, 0, 0 ) )
    {
        /* the menu runs here, at the top of the message loop, not inside
           the mouse handler that asked for it */
        if( msg.message == WM_APP_MENU )
        {
            DoMenu( menuPt.x, menuPt.y );
            continue;
        }
        if( msg.message == WM_APP_HELLO )
        {
            petState  = ST_HAPPY;
            happyTicks = 26;
            Speak( 0 );
            continue;
        }
        TranslateMessage( &msg );
        DispatchMessage( &msg );
    }

    Log( "loop: message loop ended" );
    Snd_Free();
    Spr_Free();
    return 0;
}
