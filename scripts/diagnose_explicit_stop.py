"""Compare native stop paths in one installed runtime; never admits research jobs."""
import json
import shutil
import subprocess
from pathlib import Path

from native_cloud_worker import native_runtime
from verify_explicit_recover import BUILD

from honeycomb_studio import solver

ROOT = Path('/tmp/honeycomb-stop-diagnostic')
MINIMAL = r'''
#ifdef DIAGNOSTIC_IO
#include <stdio.h>
#endif
extern "C" void vexternaldb_(const int *op, int *i, const int *ni,
                              double *r, const int *nr) {
    static int stopped = 0;
    if (*ni < 6 || *nr < 3) return;
    if (*op == 4 && r[0] > .02 && !stopped) {
        stopped = 1;
        i[4] = 2;
#ifdef DIAGNOSTIC_IO
        FILE *f = fopen("diagnostic-ack.txt", "w");
        if (f) { fprintf(f, "%d %.17g\n", i[3], r[0]); fclose(f); }
#endif
    }
}
'''
UTILITY = r'''
extern "C" void xplb_exit_();
extern "C" void vexternaldb_(const int *op, int *i, const int *ni,
                              double *r, const int *nr) {
    static int pending = 0;
    static int checkpoint = 0;
    if (*ni < 6 || *nr < 3) return;
    if (*op == 2 && pending && i[3] > checkpoint) {
        i[5] = 0;
        xplb_exit_();
    }
    if (*op == 2 && !pending && r[0] > .02) {
        i[5] = 1;
        checkpoint = i[3];
        pending = 1;
    }
}
'''
CRASHES = ('segmentation fault', 'double free', 'corrupted unsorted',
           'corruption (', 'invalid pointer', 'signal 6', 'signal 11')


def main():
    ROOT.mkdir()
    build = ROOT / 'build'
    build.mkdir()
    (build / 'build.py').write_text(BUILD)
    results = []
    with native_runtime(ROOT, continuation=True) as executable:
        subprocess.run(solver.command(str(executable), 'cae', 'noGUI=' + str(build / 'build.py')),
                       cwd=build, check=True, timeout=120)
        cases = [('tls_threads4', 4, MINIMAL.replace('static int stopped', 'static __thread int stopped'), 'THREADS'),
                 ('setup_threads4', 4, MINIMAL.replace('*op == 4', '*op == 2'), 'THREADS'),
                 ('utility_threads4', 4, UTILITY, 'THREADS'),
                 ('utility_threads1', 1, UTILITY, 'THREADS')]
        for name, cpus, source, mode in cases:
            folder = ROOT / name
            folder.mkdir()
            shutil.copy2(build / 'recover_probe.inp', folder)
            (folder / 'abaqus_v6.env').write_text('verbose=ON\n')
            args = ['job=recover_probe', 'cpus=' + str(cpus), 'double=both', 'interactive']
            if mode:
                args.append('mp_mode=' + mode)
            if source:
                callback = folder / 'diagnostic.cpp'
                callback.write_text(source)
                args.append('user=' + str(callback))
            print('DIAGNOSTIC starting ' + name, flush=True)
            try:
                with (folder / 'solver.log').open('w') as log:
                    process = subprocess.run(solver.command(str(executable), *args), cwd=folder,
                                             stdout=log, stderr=subprocess.STDOUT, timeout=240)
                text = (folder / 'solver.log').read_text(errors='replace').lower()
                row = dict(case=name, exit_code=process.returncode,
                           crash_markers=[marker for marker in CRASHES if marker in text],
                           stop_requested='exit as per user request in vexternaldb' in text,
                           utility_called='xplb_exit' in text,
                           state=solver.sta_progress(folder / 'recover_probe.sta', .06))
            except subprocess.TimeoutExpired:
                row = dict(case=name, timeout=True)
            results.append(row)
            print('DIAGNOSTIC ' + json.dumps(row), flush=True)
            (ROOT / 'results.json').write_text(json.dumps(results, indent=2))
    Path('output').mkdir(exist_ok=True)
    Path('output/explicit-stop-diagnostic.json').write_text(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
