"""Seal/restore same-workflow continuation artifacts; reject traversal and symlinks."""
import argparse
import hashlib
import json
import os
import tarfile
from pathlib import Path

ROOT = Path('/tmp/honeycomb-results')


def pack(folder, outcome):
    if outcome not in ('completed', 'checkpoint'):
        raise ValueError('A failed solver cannot produce a continuation bundle')
    folder.mkdir(parents=True, exist_ok=True)
    receipt = {'outcome': outcome}
    if outcome == 'checkpoint':
        archive = folder / 'state.tar'
        with tarfile.open(archive, 'w') as tar:
            for path in sorted(ROOT.rglob('*')):
                if path.is_symlink():
                    raise ValueError('Symlink in checkpoint')
                if path.is_file():
                    if path.name in ('publication-pending.json', 'publication-result.json'):
                        continue
                    tar.add(path, arcname=path.relative_to(ROOT), recursive=False)
        with archive.open('rb') as stream:
            receipt.update(sha256=hashlib.file_digest(stream, 'sha256').hexdigest(), bytes=archive.stat().st_size)
    (folder / 'segment.json').write_text(json.dumps(receipt), encoding='utf-8')


def restore(folder, segment):
    if segment == 0:
        if ROOT.exists() and any(ROOT.iterdir()):
            raise ValueError('Initial segment must be clean')
        return False
    receipt = json.loads((folder / 'segment.json').read_text())
    if receipt['outcome'] == 'completed':
        return True
    if receipt['outcome'] != 'checkpoint' or ROOT.exists():
        raise ValueError('Invalid continuation outcome or nonempty destination')
    archive = folder / 'state.tar'
    with archive.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != receipt['sha256'] or archive.stat().st_size != receipt['bytes']:
            raise ValueError('Corrupt continuation archive')
    with tarfile.open(archive) as tar:
        for member in tar.getmembers():
            path = Path(member.name)
            if not member.isfile() or path.is_absolute() or '..' in path.parts or '\\' in member.name or ':' in member.name:
                raise ValueError('Unsafe continuation member')
        ROOT.mkdir()
        tar.extractall(ROOT, filter='data')
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['restore', 'pack'])
    parser.add_argument('--folder', type=Path, required=True)
    parser.add_argument('--segment', type=int)
    parser.add_argument('--outcome')
    args = parser.parse_args()
    if args.mode == 'pack':
        pack(args.folder, args.outcome)
    else:
        done = restore(args.folder, args.segment)
        with open(os.environ['GITHUB_OUTPUT'], 'a') as out:
            out.write('done=' + str(done).lower() + '\n')


if __name__ == '__main__':
    main()
