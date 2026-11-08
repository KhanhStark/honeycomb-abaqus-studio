"""Integrity receipts for cross-runner Explicit recover; never certify partial data."""
import hashlib
import json
import math
import re
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


def checkpoint_stop_time(raw: Path, job_name: str, acknowledgment: dict, predecessor=None):
    """Resolve a recovered callback's elapsed time against independent native evidence.

    Abaqus 2020's recovered invocation can report elapsed callback step time.
    Only a matching restart increment, orderly shutdown and a verified predecessor
    may establish its absolute time. Original acknowledgments are never rewritten.
    """
    from .solver import ROW

    text = (raw / (job_name + '.sta')).read_text(errors='replace')
    prior_text = ''
    headers = list(re.finditer(r'(?m)^[ \t]*Abaqus/Explicit[^\r\n]*\bDATE\b[^\r\n]*\bTIME\b', text))
    if headers:
        prior_text = text[:headers[-1].start()]
        text = text[headers[-1].start():]
    increment = acknowledgment.get('increment')
    if type(increment) is not int or increment <= 0:
        raise ValueError('Checkpoint acknowledgment lacks a valid native increment')
    requests = re.findall(r'additional restart frame at the end of increment\s+(\d+) is', text)
    restarts = re.findall(r'Restart Number\s+\d+ at ([\d.Ee+\-]+)', text)
    rows = [match for line in text.splitlines() if (match := ROW.match(line))]
    checkpoint = [row for row in rows if int(row[1]) == increment]
    if (not requests or set(map(int, requests)) != {increment} or not restarts or len(checkpoint) != 1
            or not rows or int(rows[-1][1]) != increment + 1
            or float(rows[-1][5]) > 1.e-13
            or 'THE ANALYSIS HAS NOT BEEN COMPLETED' not in text
            or 'THE ANALYSIS HAS COMPLETED SUCCESSFULLY' in text
            or 'A special ODB Field Frame' not in text):
        raise ValueError('Checkpoint lacks matching restart and orderly shutdown evidence')
    errors = re.findall(r'\*\*\*ERROR:\s*(.*)', text)
    allowed = ('The program will exit as per user request in VEXTERNALDB.',
               'The fatal error will generate a new field output in the last')
    if not errors or any(error.strip() not in allowed for error in errors):
        raise ValueError('Checkpoint contains an unrelated native solver error')
    stopped = float(restarts[-1])
    stable = float(checkpoint[0][5])
    # STA restart times have six significant digits; callback time is at the
    # start of its scheduled increment. Bound both rounding and that increment.
    tolerance = max(3 * stable, abs(stopped) * 5.e-6)
    if not math.isfinite(stopped) or stable <= 0 or abs(float(checkpoint[0][2]) - stopped) > max(tolerance, abs(stopped) * 5.e-4):
        raise ValueError('Native checkpoint restart time disagrees with its increment')
    original = acknowledgment['simulation_time_s']
    offset = 0.
    if abs(original - stopped) > tolerance:
        if not predecessor or predecessor.get('history_integrity', {}).get('passed') is not True:
            raise ValueError('Elapsed checkpoint time lacks a verified predecessor')
        prior_stop = predecessor['stop']
        prior_restarts = re.findall(r'Restart Number\s+\d+ at ([\d.Ee+\-]+)', prior_text)
        prior_rows = [match for line in prior_text.splitlines() if (match := ROW.match(line))]
        prior_checkpoint = [row for row in prior_rows if int(row[1]) == prior_stop.get('increment')]
        if not prior_restarts or not prior_checkpoint or not prior_rows or int(prior_rows[-1][1]) != prior_stop.get('increment', -2) + 1:
            raise ValueError('Recovered STA does not retain the verified predecessor increment')
        offset = float(prior_restarts[-1])
        prior_tolerance = max(3 * float(prior_checkpoint[-1][5]), abs(offset) * 5.e-6)
        if (not math.isfinite(offset) or offset <= 0
                or abs(offset - prior_stop['simulation_time_s']) > prior_tolerance
                or abs(original + offset - stopped) > tolerance + abs(offset) * 5.e-6):
            raise ValueError('Checkpoint elapsed time disagrees with native restart and predecessor')
    return {'simulation_time_s': stopped, 'increment': increment,
            'callback_acknowledgment': acknowledgment, 'predecessor_offset_s': offset,
            'time_basis': 'native-sta-restart', 'crosscheck_tolerance_s': tolerance}


def verify_checkpoint_history(raw: Path, job_name: str, executable: str, spec: dict, *, predecessor=None):
    from . import solver
    from .data import history_continuity
    from .engine import ADAPTERS

    acknowledgment = json.loads((raw / 'continuation-stop-ack.json').read_text())
    stopped = acknowledgment['simulation_time_s']
    if not isinstance(stopped, (int, float)) or not math.isfinite(stopped) or not 0 < stopped <= spec['duration']:
        raise ValueError('Invalid orderly stop acknowledgment')
    stop = acknowledgment
    if (raw / (job_name + '.sta')).exists():
        stop = checkpoint_stop_time(raw, job_name, acknowledgment, predecessor)
        stopped = stop['simulation_time_s']
        if not 0 < stopped < spec['duration']:
            raise ValueError('Checkpoint must precede the original end time')
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
    return {'stop': stop, 'history_integrity': integrity}


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
