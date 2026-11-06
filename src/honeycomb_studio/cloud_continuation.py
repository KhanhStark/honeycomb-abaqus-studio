"""Integrity receipts for cross-runner Explicit recover; never certify partial data."""
import hashlib
import json
import math
import subprocess
from pathlib import Path


def verify_solver_cleanup(log: Path):
    """A stop acknowledgment does not certify that the native solver closed cleanly."""
    markers = ('segmentation fault', 'double free', 'corrupted unsorted', 'corruption (',
               'invalid pointer', 'corrupted double-linked', 'signal 6', 'signal 11')
    with log.open(errors='replace') as stream:
        for line in stream:
            if any(marker in line.lower() for marker in markers):
                raise RuntimeError('Checkpoint stop crashed during solver cleanup; inspect ' + str(log))


def verify_checkpoint_history(raw: Path, job_name: str, executable: str, spec: dict):
    from . import solver
    from .data import history_continuity
    from .engine import ADAPTERS

    acknowledgment = json.loads((raw / 'continuation-stop-ack.json').read_text())
    stopped = acknowledgment['simulation_time_s']
    if not isinstance(stopped, (int, float)) or not math.isfinite(stopped) or not 0 < stopped <= spec['duration']:
        raise ValueError('Invalid orderly stop acknowledgment')
    destination = raw / 'checkpoint-history.json'
    with (raw / 'checkpoint-history-check.log').open('w') as log:
        subprocess.run(solver.command(executable, 'python', str(ADAPTERS / 'checkpoint_history.py'),
                                      str(raw / (job_name + '.odb')), str(destination)),
                       cwd=raw, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=120)
    histories = json.loads(destination.read_text())
    integrity = history_continuity(histories, {'duration': stopped,
            'history_intervals': stopped / (spec['duration'] / spec['history_intervals'])})
    if not integrity['passed']:
        raise ValueError('Checkpoint has unflushed or missing original history; refusing recover: ' + json.dumps(integrity))
    return {'stop': acknowledgment, 'history_integrity': integrity}


def checkpoint_inventory(raw: Path, job_name: str):
    files = sorted(p for p in raw.iterdir() if p.is_file() and p.name.startswith(job_name + '.'))
    # Distributed Explicit can retain per-domain state/selected files.
    for extension in ('abq', 'pac', 'res', 'sel', 'odb'):
        if not any(p.name == job_name + '.' + extension or p.name.startswith(job_name + '.' + extension + '.')
                   for p in files if p.stat().st_size):
            raise ValueError('Missing nonempty Explicit recovery file family: ' + extension)
    inventory = {}
    for p in files:
        if p.suffix in ('.lck', '.023'):
            continue
        with p.open('rb') as stream:
            inventory[p.name] = {'bytes': p.stat().st_size, 'sha256': hashlib.file_digest(stream, 'sha256').hexdigest()}
    return inventory


def verify_checkpoint(raw: Path, receipt, *, job_name, input_hash, runtime_hash, cpus):
    expected = (job_name, input_hash, runtime_hash, cpus)
    actual = tuple(receipt.get(k) for k in ('job_name', 'input_hash', 'runtime_hash', 'cpus'))
    if actual != expected:
        raise ValueError('Checkpoint job/input/runtime/CPU identity mismatch')
    if checkpoint_inventory(raw, job_name) != receipt['files']:
        raise ValueError('Checkpoint file inventory or checksum mismatch')
