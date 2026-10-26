/* =====================================================================
 *  PORTIO.H  -  direct hardware port I/O for 16-bit Windows
 *
 *  We do not use conio.h: it is not part of the win16 target's header
 *  set, and an inlined `out` is what the 8 kHz sample loop wants anyway.
 * ===================================================================== */
#ifndef PORTIO_H
#define PORTIO_H

static void PortOut( int port, int value );
#pragma aux PortOut = \
    "out dx,al"       \
    parm [dx] [al]    \
    modify [];

static int PortIn( int port );
#pragma aux PortIn = \
    "in al,dx"        \
    "xor ah,ah"       \
    parm [dx]         \
    value [ax]        \
    modify [];

#endif
