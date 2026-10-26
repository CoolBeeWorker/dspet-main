/* =====================================================================
 *  MENU.C  -  a small popup menu, because TrackPopupMenu is 3.1+
 *
 *  Two rules are followed here that version 0.2 broke, and breaking them
 *  is what raised "unrecoverable application error" as soon as an item
 *  was picked:
 *
 *   1. NEVER call DestroyWindow from inside the window's own procedure.
 *      Destroying a window while USER is still unwinding one of its own
 *      messages (WM_LBUTTONUP, WM_KILLFOCUS) leaves USER's window list
 *      half unlinked.  The procedure now only records the result and
 *      sets a flag; Pop_Menu destroys the window at top level.
 *
 *   2. NEVER let the popup take the focus.  A WS_POPUP created visible
 *      gets activated, which makes it receive WM_KILLFOCUS the moment
 *      anything else happens - a second path to the same crash.  It is
 *      created hidden and shown with SW_SHOWNA, so it never owns focus;
 *      the mouse is tracked with SetCapture instead.
 * ===================================================================== */
#include "dspet.h"

static HWND  m_hw;
static int   m_sel, m_cnt, m_cur, m_done;
static int   m_w, m_h, m_row;
static const char * const *m_items;

static void DrawMenu( HDC hdc )
{
    RECT rc;
    HBRUSH hb;
    HGDIOBJ oldFont, oldPen;
    int i;

    rc.left = 0; rc.top = 0; rc.right = m_w; rc.bottom = m_h;
    hb = CreateSolidBrush( RGB(255,255,255) );
    FillRect( hdc, &rc, hb );
    DeleteObject( hb );

    oldFont = SelectObject( hdc, GetStockObject( SYSTEM_FIXED_FONT ) );
    oldPen  = SelectObject( hdc, GetStockObject( BLACK_PEN ) );

    for( i = 0; i < m_cnt; i++ )
    {
        RECT r;
        r.left = 2; r.top = 2 + i * m_row;
        r.right = m_w - 2; r.bottom = r.top + m_row;

        if( i == m_cur )
        {
            HBRUSH hb2 = CreateSolidBrush( RGB(0,0,128) );
            FillRect( hdc, &r, hb2 );
            DeleteObject( hb2 );
            SetBkColor( hdc, RGB(0,0,128) );
            SetTextColor( hdc, RGB(255,255,255) );
        }
        else
        {
            SetBkColor( hdc, RGB(255,255,255) );
            SetTextColor( hdc, RGB(0,0,0) );
        }
        TextOut( hdc, r.left + 6, r.top + 3, m_items[i], lstrlen(m_items[i]) );
    }

    SelectObject( hdc, oldPen );
    SelectObject( hdc, oldFont );

    SelectObject( hdc, GetStockObject( BLACK_PEN ) );
    MoveTo( hdc, 0, 0 );            LineTo( hdc, m_w - 1, 0 );
    LineTo( hdc, m_w - 1, m_h - 1 ); LineTo( hdc, 0, m_h - 1 ); LineTo( hdc, 0, 0 );
}

LRESULT CALLBACK __export MenuProc( HWND hwnd, UINT msg, WPARAM wp, LPARAM lp )
{
    switch( msg )
    {
    case WM_PAINT:
    {
        PAINTSTRUCT ps;
        HDC hdc = BeginPaint( hwnd, &ps );
        DrawMenu( hdc );
        EndPaint( hwnd, &ps );
        return 0;
    }

    case WM_MOUSEMOVE:
    {
        int i;
        if( m_row <= 0 ) return 0;
        i = ( (int)HIWORD(lp) - 2 ) / m_row;
        if( i < 0 ) i = 0;
        if( i >= m_cnt ) i = m_cnt - 1;
        if( i != m_cur ) { m_cur = i; InvalidateRect( hwnd, NULL, TRUE ); }
        return 0;
    }

    case WM_LBUTTONUP:
        m_sel  = m_cur;
        m_done = 1;
        return 0;

    case WM_RBUTTONDOWN:
        m_sel  = -1;
        m_done = 1;
        return 0;

    case WM_KILLFOCUS:              /* should never arrive; harmless if it does */
        m_sel  = -1;
        m_done = 1;
        return 0;
    }
    return DefWindowProc( hwnd, msg, wp, lp );
}

int Pop_Menu( HWND parent, int x, int y, const char * const *items, int n )
{
    static WNDPROC pfnThunk;
    static BOOL    registered;
    MSG      m;
    HDC      hdc;
    HGDIOBJ  old;
    int      i, maxw = 0, tw;
    TEXTMETRIC tm;

    if( n <= 0 ) return -1;

    if( !registered )
    {
        WNDCLASS wc;
        pfnThunk = (WNDPROC)MakeProcInstance( (FARPROC)MenuProc, hInst );

        wc.style         = CS_SAVEBITS;
        wc.lpfnWndProc   = pfnThunk;
        wc.cbClsExtra    = 0;
        wc.cbWndExtra    = 0;
        wc.hInstance     = hInst;
        wc.hIcon         = NULL;
        wc.hCursor       = LoadCursor( NULL, IDC_ARROW );
        wc.hbrBackground = NULL;
        wc.lpszMenuName  = NULL;
        wc.lpszClassName = "DSPetMenu";
        if( !RegisterClass( &wc ) ) return -1;
        registered = TRUE;
    }

    hdc = GetDC( NULL );
    if( !hdc ) return -1;
    old = SelectObject( hdc, GetStockObject( SYSTEM_FIXED_FONT ) );
    GetTextMetrics( hdc, &tm );
    for( i = 0; i < n; i++ )
    {
        tw = LOWORD( GetTextExtent( hdc, items[i], lstrlen(items[i]) ) );
        if( tw > maxw ) maxw = tw;
    }
    SelectObject( hdc, old );
    ReleaseDC( NULL, hdc );

    m_row = (int)tm.tmHeight + 6;
    if( m_row < 10 ) m_row = 10;
    m_w   = maxw + 26;
    m_h   = n * m_row + 5;
    m_cnt = n;
    m_sel = -1;
    m_cur = 0;
    m_done = 0;
    m_items = items;

    if( x + m_w > GetSystemMetrics(SM_CXSCREEN) )
        x = GetSystemMetrics(SM_CXSCREEN) - m_w;
    if( y + m_h > GetSystemMetrics(SM_CYSCREEN) )
        y = GetSystemMetrics(SM_CYSCREEN) - m_h;
    if( x < 0 ) x = 0;
    if( y < 0 ) y = 0;

    /* NOT WS_VISIBLE: a visible popup gets activated and would then be
       sent WM_KILLFOCUS, giving a second window-destroy path. */
    m_hw = CreateWindow( "DSPetMenu", "", WS_POPUP,
                         x, y, m_w, m_h, parent, NULL, hInst, NULL );
    if( !m_hw ) return -1;

    ShowWindow( m_hw, SW_SHOWNA );      /* show without activating */
    UpdateWindow( m_hw );
    SetCapture( m_hw );

    while( IsWindow( m_hw ) )
    {
        if( !GetMessage( &m, NULL, 0, 0 ) )
        {
            PostQuitMessage( 0 );
            m_sel = -1;
            break;
        }
        TranslateMessage( &m );
        DispatchMessage( &m );

        if( m_done ) break;
    }

    ReleaseCapture();

    /* the window is destroyed here, at top level, never from inside
       MenuProc */
    if( IsWindow( m_hw ) ) DestroyWindow( m_hw );
    m_hw = NULL;
    return m_done ? m_sel : -1;
}
