/* =====================================================================
 *  CRC.C  -  print size + 16-bit checksum for files, under MS-DOS 5.0
 *            Same algorithm as JOIN.EXE, so the numbers compare directly.
 *
 *      wcc -bt=dos -ml -os crc.c
 *      wlink system dos name crc.exe file crc.obj
 * ===================================================================== */
#include <stdio.h>
#include <string.h>
#include <dos.h>

static unsigned char buf[8192];

static void one(const char *name)
{
    FILE *f;
    size_t n;
    unsigned long size = 0UL;
    unsigned sum = 0u;

    f = fopen(name, "rb");
    if (!f) { printf("%-14s  -- not found --\n", name); return; }
    while ((n = fread(buf, 1, sizeof(buf), f)) > 0) {
        size_t i;
        for (i = 0; i < n; i++) sum += buf[i];
        size += (unsigned long)n;
    }
    fclose(f);
    printf("%-14s %9lu bytes   checksum %04X\n", name, size, (unsigned)(sum & 0xFFFFu));
}

int main(int argc, char **argv)
{
    int i;

    printf("CRC 1.0 - size and 16-bit checksum\n\n");
    if (argc > 1) {
        for (i = 1; i < argc; i++) one(argv[i]);
    } else {
        struct find_t ff;
        if (_dos_findfirst("*.*", _A_NORMAL | _A_ARCH | _A_RDONLY, &ff) == 0) {
            do {
                if (!(ff.attrib & _A_SUBDIR)) one(ff.name);
            } while (_dos_findnext(&ff) == 0);
        }
    }
    return 0;
}
