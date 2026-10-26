/* =====================================================================
 *  JOIN.C  -  reassemble the parts of a split file, on plain MS-DOS 5.0
 *
 *  Built as a 16-bit DOS .EXE with Open Watcom:
 *      wcc   -bt=dos -ml -os join.c
 *      wlink system dos name join.exe file join.obj
 *
 *  Usage
 *      JOIN                      -> reads JOIN.LST
 *      JOIN out.bin p1 p2 p3     -> command line form
 *
 *  JOIN.LST is a plain text file, one name per line:
 *      line 1 : the file to create
 *      line 2+: the parts, in order
 *
 *  It prints the size and a 16-bit checksum of the result so you can
 *  compare it with the numbers printed at split time.
 * ===================================================================== */
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#define BUFSZ 8192

static unsigned char buf[BUFSZ];
static unsigned long total;
static unsigned sum;

static int append(const char *out, const char *in)
{
    FILE *fi, *fo;
    size_t n;
    unsigned long got = 0UL;
    int first = (total == 0UL);

    fo = fopen(out, first ? "wb" : "ab");
    if (!fo) { printf("cannot open %s\n", out); return 0; }
    fi = fopen(in, "rb");
    if (!fi) { printf("cannot open %s\n", in); fclose(fo); return 0; }

    while ((n = fread(buf, 1, BUFSZ, fi)) > 0) {
        size_t i;
        for (i = 0; i < n; i++) sum += buf[i];
        if (fwrite(buf, 1, n, fo) != n) {
            printf("write error on %s (disk full?)\n", out);
            fclose(fi); fclose(fo); return 0;
        }
        got  += (unsigned long)n;
        total += (unsigned long)n;
    }
    fclose(fi);
    fclose(fo);
    printf("  + %-12s %8lu bytes  (running total %lu)\n", in, got, total);
    return 1;
}

int main(int argc, char **argv)
{
    char out[64];
    char line[80];
    FILE *lst;
    int ok = 1;

    printf("JOIN 1.0 - reassemble split files under MS-DOS\n\n");
    total = 0UL; sum = 0u;

    if (argc >= 3) {
        int i;
        strncpy(out, argv[1], sizeof(out) - 1);
        out[sizeof(out) - 1] = 0;
        for (i = 2; i < argc && ok; i++)
            ok = append(out, argv[i]);
    } else {
        lst = fopen("JOIN.LST", "rt");
        if (!lst) {
            printf("JOIN.LST not found.\n");
            printf("Usage: JOIN outfile part1 part2 ...\n");
            return 2;
        }
        if (!fgets(line, sizeof(line), lst)) { fclose(lst); return 2; }
        line[strcspn(line, "\r\n")] = 0;
        if (!line[0]) { fclose(lst); return 2; }
        strncpy(out, line, sizeof(out) - 1);
        out[sizeof(out) - 1] = 0;

        while (fgets(line, sizeof(line), lst)) {
            line[strcspn(line, "\r\n")] = 0;
            if (!line[0] || line[0] == ';') continue;
            if (!append(out, line)) { ok = 0; break; }
        }
        fclose(lst);
    }

    if (!ok) {
        printf("\nFAILED\n");
        return 1;
    }

    printf("\n%-14s %8lu bytes\n", out, total);
    printf("checksum       %04X\n", (unsigned)(sum & 0xFFFFu));
    printf("\nCompare with the numbers in JOIN.LST.TXT. If they match, the\n");
    printf("file was rebuilt byte for byte.\n");
    return 0;
}
