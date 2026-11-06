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
LOCAL_SHELL = '''#!/usr/bin/python3
"""Launch MPI children only inside this container, using ssh argument conventions."""
import os
import socket
import sys
args = sys.argv[1:]
while args and args[0].startswith('-'):
    option = args.pop(0)
    if option == '-l':
        args.pop(0)
    elif option != '-n':
        raise SystemExit('Unsupported MPI local-shell option')
if len(args) < 2 or args.pop(0) not in (socket.gethostname(), 'localhost', '127.0.0.1'):
    raise SystemExit('MPI local shell refuses another host')
os.execv('/bin/sh', ['sh', '-c', ' '.join(args)])
'''
CRASHES = ('segmentation fault', 'double free', 'corrupted unsorted',
           'corruption (', 'invalid pointer', 'corrupted double-linked', 'signal 6', 'signal 11')


def main():
    ROOT.mkdir()
    build = ROOT / 'build'
    build.mkdir()
    (build / 'build.py').write_text(BUILD)
    results = []
    with native_runtime(ROOT, continuation=True) as executable:
        subprocess.run(solver.command(str(executable), 'cae', 'noGUI=' + str(build / 'build.py')),
                       cwd=build, check=True, timeout=120)
        local_shell = ROOT / 'mpi_local_shell.py'
        local_shell.write_text(LOCAL_SHELL)
        local_shell.chmod(0o755)
        main_thread = '#include <SMAAspUserSubroutines.h>\n' + MINIMAL.replace(
            'static int stopped = 0;', 'static int stopped = 0;\n    if (get_thread_id() != 0) return;')
        main_utility = '#include <SMAAspUserSubroutines.h>\n' + UTILITY.replace(
            'static int pending = 0;', 'static int pending = 0;\n    if (get_thread_id() != 0) return;')
        cases = [('minimal_mpi4_local', 4, MINIMAL, 'MPI', []),
                 ('main_threads4', 4, main_thread, 'THREADS', []),
                 ('main_utility_threads4', 4, main_utility, 'THREADS', []),
                 ('loop_threads4', 4, MINIMAL, 'THREADS', ['parallel=loop'])]
        for name, cpus, source, mode, extra in cases:
            folder = ROOT / name
            folder.mkdir()
            shutil.copy2(build / 'recover_probe.inp', folder)
            environment = 'verbose=ON\n'
            if mode == 'MPI':
                environment += ("import os\nos.environ['MPI_REMSH']=" + repr(str(local_shell)) +
                                '\nmp_file_system=(SHARED,SHARED)\n')
            (folder / 'abaqus_v6.env').write_text(environment)
            args = ['job=recover_probe', 'cpus=' + str(cpus), 'double=both', 'interactive', *extra]
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
                           utility_called='analysis is terminated from user subroutine' in text,
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
