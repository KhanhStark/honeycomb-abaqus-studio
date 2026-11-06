/* VEXTERNALDB: request an orderly checkpoint and exit without OS signals.
 * Official interface: simasub-c-vexternaldb.htm (Abaqus Explicit).
 * Scientific state and time increments are never modified.
 */
#include <stdio.h>
#include <stdlib.h>
#include <limits.h>
#include <unistd.h>

static int control_path(char *path, size_t length, const char *name)
{
    const char *directory = getenv("HONEYCOMB_CONTINUATION_DIRECTORY");
    int written = snprintf(path, length, "%s/%s", directory ? directory : ".", name);
    return written >= 0 && (size_t)written < length;
}

#ifdef __cplusplus
extern "C"
#endif
void vexternaldb_(const int *operation, int *integers, const int *integer_count,
                 double *reals, const int *real_count)
{
    static int pending = 0;
    static int initialized = 0;
    static unsigned int polls = 0;
    char stop_path[PATH_MAX], ack_path[PATH_MAX];
    if (!initialized) {
        char metadata[PATH_MAX];
        if (control_path(metadata, sizeof(metadata), "continuation-control.json")) {
            FILE *receipt = fopen(metadata, "w");
            if (receipt) {
                fprintf(receipt, "{\"first_operation\":%d,\"integer_count\":%d,\"real_count\":%d}\n",
                        *operation, *integer_count, *real_count);
                fclose(receipt);
            }
        }
        initialized = 1;
    }
    if (*integer_count < 6 || *real_count < 3) return;
    if (!control_path(stop_path, sizeof(stop_path), "continuation.stop") ||
        !control_path(ack_path, sizeof(ack_path), "continuation-stop-ack.json")) return;
    if (*operation == 0) { pending = 0; polls = 0; }
    if (*operation == 2 && pending == 2)
        integers[5] = 0; /* checkpoint is already written; no restart from the shutdown increment */
    if (*operation == 2 && pending == 0 && (++polls % 256 == 0) &&
        access(stop_path, F_OK) == 0) {
        pending = 1;
        integers[5] = 1; /* write restart at the end of this increment */
    }
    if (*operation == 4 && pending == 1) {
        /* Termination adds one zero-time increment. Do not request it again
         * from that increment, or overwrite the acknowledged checkpoint. */
        pending = 2;
        integers[4] = 2; /* terminate analysis through the supported solver API */
        FILE *ack = fopen(ack_path, "w");
        if (ack) {
            fprintf(ack, "{\"simulation_time_s\":%.17g,\"increment\":%d}\n", reals[1], integers[3]);
            fclose(ack);
        }
    }
}
