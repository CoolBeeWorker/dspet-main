/* =====================================================================
 *  DSPET.H  -  DeepSeek Desktop Pet for Windows 3.0 / 3.1
 *  16-bit, large model, Open Watcom target: windows (NE executable)
 *
 *  Written to stay inside the Windows 3.0 API surface:
 *    - no TrackPopupMenu (3.1+), no Shell_NotifyIcon (Win95)
 *    - no C runtime strings or stdio: USER's lstr-calls, wsprintf, and
 *      the KERNEL file I/O calls (_lread/_lwrite/OpenFile)
 * ===================================================================== */
#ifndef DSPET_H
#define DSPET_H

#define STRICT
#include <windows.h>

/* the win16 headers stop at Windows 3.1; this one is harmless there
   but missing from them, so we spell it out */
#ifndef WS_EX_TOOLWINDOW
#define WS_EX_TOOLWINDOW 0x00000080L
#endif

/* ---- tunables ------------------------------------------------------- */
#define APPNAME      "DSPet"
#define SPRW         72          /* sprite cell size, must match genart.py */
#define SPRH         56
#define TICK_MS      55          /* Windows 3.x minimum timer granularity  */
#define ID_TIMER     1

/* ---- pet behaviour states ------------------------------------------- */
#define ST_IDLE      0
#define ST_TALK      1
#define ST_HAPPY     2
#define ST_SLEEP     3
#define ST_WALK      4

/* private message: the context menu is opened from the MAIN message loop,
   never from inside a window procedure (see main.c) */
#define WM_APP_MENU  0x8001
/* left click asks for a greeting the same way: the playback blocks for a
   second or two, and blocking inside a mouse message is the same class of
   mistake that killed 0.2 when the menu did it */
#define WM_APP_HELLO 0x8002

/* ---- frame indices inside DSPET.SPR (order from genart.py) ---------- */
#define F_IDLE0      0
#define F_IDLE1      1
#define F_BLINK      2
#define F_TALK0      3
#define F_TALK1      4
#define F_TALK2      5
#define F_HAPPY      6
#define F_SLEEP0     7
#define F_SLEEP1     8
#define F_WALK_R0    9      /* walking right, 4-step cycle */
#define F_WALK_R1    10
#define F_WALK_R2    11
#define F_WALK_R3    12
#define F_WALK_L0    13     /* the same cycle mirrored, for walking left */
#define F_WALK_L1    14
#define F_WALK_L2    15
#define F_WALK_L3    16

/* ===================== spr.c : sprite bank =========================== */
/* candidate paths, tried in order; the first one that opens wins */
BOOL  Spr_Load( LPCSTR const *cand, int nCand );
int   Spr_LastError( void );       /* 1=not found 2=bad file 3=bad size
                                      4=no memory 5=GDI refused it      */
void  Spr_Free( void );
int   Spr_Count( void );
int   Spr_W( void );
int   Spr_H( void );
void  Spr_Draw( HDC hdc, int x, int y, int frame );
void  Spr_DrawPart( HDC hdc, int x, int y, int frame, int l, int t, int r, int b );

/* --- monochrome (2-colour display driver) support --------------------
 * On an MDA / VGA-mono / 8503 driver the memory DCs are 1 bit per pixel.
 * Blitting a 4bpp colour DIB onto a 1bpp DC with SRCPAINT is a colour
 * conversion that the old drivers simply do not implement, and the pet
 * comes out as a ghost.  When "mono" is set, the loader builds its own
 * 1bpp bitmaps from the palette (luminance + ordered dither) so every
 * blit is 1bpp-to-1bpp and the result cannot depend on the driver.
 * The caller decides, because only the caller can look at the desktop
 * that was just captured and see whether it wants a light or a dark pet. */
void  Spr_SetMono( int on );
int   Spr_IsMono( void );
void  Spr_SetInvert( int on );     /* swap black and white in the pet   */
int   Spr_IsInvert( void );
BOOL  Spr_Rebuild( void );         /* re-make the bitmaps, e.g. after
                                      Spr_SetInvert - no file read      */

/* ===================== snd.c : PC speaker PCM ======================== */
BOOL  Snd_Init( void );
BOOL  Snd_LoadBank( LPCSTR szFile );
void  Snd_Free( void );
int   Snd_Count( void );
BOOL  Snd_Play( int phrase );       /* blocking; see the note in snd.c    */
void  Snd_SetHook( void (__far *hook)(int) );
BOOL  Snd_Busy( void );
void  Snd_Stop( void );
void  Snd_Beep( int hz, int ms );   /* diagnostic tone                    */
int   Snd_Level( void );            /* 0..3 envelope of what is playing   */

/* ===================== link.c : hardware report ====================== */
/* Pure Windows API calls and WIN.INI lookups - this function performs NO
 * port I/O, because probing absent ports from a Windows app is what made
 * version 0.2 die with an unrecoverable application error.              */
LPSTR Link_Report( void );

/* ===================== menu.c : minimal popup menu =================== */
/* TrackPopupMenu is Windows 3.1+, so we roll our own.  Returns the
 * selected item index, or -1 if cancelled.                              */
int   Pop_Menu( HWND parent, int x, int y, const char * const *items, int n );

/* ===================== shared ---------------------------------------- */
extern HINSTANCE hInst;
extern HWND      hWnd;
extern char      szAppDir[128];

void  Pet_SetState( int st );
void  App_Quit( void );

#endif /* DSPET_H */
