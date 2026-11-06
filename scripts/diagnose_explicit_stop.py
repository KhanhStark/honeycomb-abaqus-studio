"""Compare native stop paths in one installed runtime; never admits research jobs."""
import json
import shutil
import subprocess
from pathlib import Path

from native_cloud_worker import native_runtime
from verify_explicit_recover import BUILD

from honeycomb_studio import solver
from honeycomb_studio.cloud_continuation import checkpoint_inventory, verify_solver_cleanup
from honeycomb_studio.data import history_continuity
from honeycomb_studio.engine import ADAPTERS

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
        step_control = Path('scripts/linux_media/continuation_control.c').read_text().replace(
            'integers[4] = 2;', 'integers[4] = 1;').replace(
            'access(stop_path, F_OK) == 0)', 'access(stop_path, F_OK) == 0 && reals[1] > .02)')
        cases = [('step_threads4', 4, MINIMAL.replace('i[4] = 2;', 'i[4] = 1;'), 'THREADS', []),
                 ('checkpoint_step_threads4', 4, step_control, 'THREADS', [])]
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
            if name.startswith('checkpoint_'):
                (folder / 'continuation.stop').touch()
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
                if name.startswith('checkpoint_') and not row['crash_markers']:
                    try:
                        row['recovery'] = recover_step_checkpoint(executable, folder, callback)
                    except (RuntimeError, ValueError, OSError, subprocess.SubprocessError) as error:
                        row['recovery'] = {'passed': False, 'error': str(error)}
            except subprocess.TimeoutExpired:
                row = dict(case=name, timeout=True)
            results.append(row)
            print('DIAGNOSTIC ' + json.dumps(row), flush=True)
            (ROOT / 'results.json').write_text(json.dumps(results, indent=2))
    Path('output').mkdir(exist_ok=True)
    Path('output/explicit-stop-diagnostic.json').write_text(json.dumps(results, indent=2))


def recover_step_checkpoint(executable, folder, callback):
    """A deliberately shortened step is never accepted as a completed simulation."""
    verify_solver_cleanup(folder / 'solver.log')
    acknowledgment = json.loads((folder / 'continuation-stop-ack.json').read_text())
    if not .02 < acknowledgment['simulation_time_s'] < .06:
        raise ValueError('Checkpoint did not interrupt the intended time window')
    checkpoint_inventory(folder, 'recover_probe')
    (folder / 'continuation.stop').unlink()
    for lock in folder.glob('*.lck'):
        lock.unlink()
    reader = ADAPTERS / 'checkpoint_history.py'
    def history(name):
        destination = folder / name
        subprocess.run(solver.command(str(executable), 'python', str(reader),
                       str(folder / 'recover_probe.odb'), str(destination)), cwd=folder,
                       check=True, timeout=120)
        return json.loads(destination.read_text())
    before = history('history-before.json')
    with (folder / 'recover.log').open('w') as log:
        subprocess.run(solver.command(str(executable), 'job=recover_probe', 'recover', 'cpus=4',
                       'double=both', 'user=' + str(callback), 'interactive'), cwd=folder,
                       stdout=log, stderr=subprocess.STDOUT, check=True, timeout=240)
    verify_solver_cleanup(folder / 'recover.log')
    state = solver.sta_progress(folder / 'recover_probe.sta', .06)
    if not state.get('solver_success') or state.get('simulation_time_s', 0) < .06:
        raise ValueError('Recover did not complete the original duration')
    after = history('history-after.json')
    integrity = history_continuity(after, {'duration': .06, 'history_intervals': 1000})
    if not integrity['passed']:
        raise ValueError('Recovered history has gaps')
    final = {(r['step'], r['region'], r['variable']): r['data'] for r in after}
    for row in before:
        values = final.get((row['step'], row['region'], row['variable']), [])
        if values[:len(row['data'])] != row['data']:
            raise ValueError('Recovery changed the original history prefix')
    return {'passed': True, 'after': state, 'history_integrity': integrity}


if __name__ == '__main__':
    main()
