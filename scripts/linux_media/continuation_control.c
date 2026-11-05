/* VEXTERNALDB: request an orderly checkpoint and exit without OS signals.
 * Official interface: simasub-c-vexternaldb.htm (Abaqus Explicit).
 * Scientific state and time increments are never modified.
 */
#include <stdio.h>
#include <unistd.h>

#ifdef __cplusplus
extern "C"
#endif
void vexternaldb_(const int *operation, int *integers, const int *integer_count,
                 double *reals, const int *real_count)
{
    static int pending = 0;
    static unsigned int polls = 0;
    if (*integer_count < 6 || *real_count < 3) return;
    if (*operation == 0) { pending = 0; polls = 0; }
    if (*operation == 2 && (++polls % 256 == 0) &&
        access("continuation.stop", F_OK) == 0) {
        pending = 1;
        integers[5] = 1; /* write restart at the end of this increment */
    }
    if (*operation == 4 && pending) {
        integers[4] = 2; /* terminate analysis through the supported solver API */
        FILE *ack = fopen("continuation-stop-ack.json", "w");
        if (ack) {
            fprintf(ack, "{\"simulation_time_s\":%.17g,\"increment\":%d}\n", reals[1], integers[3]);
            fclose(ack);
        }
    }
}
