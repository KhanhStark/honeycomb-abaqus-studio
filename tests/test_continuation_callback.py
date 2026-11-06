"""Exercise Abaqus' public callback ABI, including its final zero-time increment."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

CONTROL = Path(__file__).resolve().parents[1] / 'scripts/linux_media/continuation_control.c'
HARNESS = r'''
#include <assert.h>
#include <stdio.h>
void vexternaldb_(const int *, int *, const int *, double *, const int *);
static int thread_id = 0;
static int exit_calls = 0;
int get_thread_id_(void) { return thread_id; }
void xplb_exit_(void) { ++exit_calls; }
int main(void) {
    int op = 0, ni = 7, nr = 3;
    int integers[7] = {9, 4, 1, 256, 0, 0, 0};
    double reals[3] = {.01, .01, .000001};
    vexternaldb_(&op, integers, &ni, reals, &nr);
    FILE *stop = fopen("continuation.stop", "w");
    assert(stop); fclose(stop);
    op = 2;
    thread_id = 1;
    for (int i = 0; i < 256; ++i)
        vexternaldb_(&op, integers, &ni, reals, &nr);
    assert(integers[5] == 0 && exit_calls == 0);
    thread_id = 0;
    for (int i = 0; i < 256; ++i)
        vexternaldb_(&op, integers, &ni, reals, &nr);
    assert(integers[5] == 1);
    assert(integers[4] == 0);
    op = 2;
    vexternaldb_(&op, integers, &ni, reals, &nr);
    assert(integers[5] == 1 && "same-increment callback must preserve the scheduled restart");
    assert(integers[4] == 0);
    integers[3] = 257;
    reals[1] = .0101;
    vexternaldb_(&op, integers, &ni, reals, &nr);
    assert(integers[5] == 0 && "restart must be cleared before termination");
    assert(integers[4] == 0 && exit_calls == 1);
    /* The exit stub returns so duplicate callbacks can be checked. */
    integers[4] = 0;
    integers[3] = 257;
    reals[2] = 0.;
    op = 2;
    vexternaldb_(&op, integers, &ni, reals, &nr);
    assert(integers[5] == 0 && "restart must not be rewritten during the zero-time shutdown increment");
    op = 4;
    vexternaldb_(&op, integers, &ni, reals, &nr);
    assert(integers[4] == 0 && "termination was requested again during shutdown");
    assert(exit_calls == 1);
    return 0;
}
'''


@unittest.skipUnless(shutil.which('gcc'), 'requires the Linux C compiler used by Abaqus')
class ContinuationCallbackTest(unittest.TestCase):
    def test_termination_is_requested_once_and_checkpoint_ack_remains_immutable(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            harness = root / 'harness.c'
            executable = root / 'callback-test'
            harness.write_text(HARNESS)
            subprocess.run(['gcc', '-std=c99', '-D_POSIX_C_SOURCE=200809L', '-Wall', '-Wextra', '-Werror',
                            str(CONTROL), str(harness), '-o', str(executable)], check=True, capture_output=True)
            result = subprocess.run([str(executable)], cwd=root, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            receipt = json.loads((root / 'continuation-stop-ack.json').read_text())
            self.assertEqual(receipt['increment'], 256)
            self.assertEqual(receipt['simulation_time_s'], .01)
