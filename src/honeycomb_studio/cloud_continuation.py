"""Integrity receipts for cross-runner Explicit recover; never certify partial data."""
import hashlib
from pathlib import Path


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
