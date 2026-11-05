"""Collect all eight owners' verified histories, or full solver archives, into one directory."""
import argparse
import hashlib
import json
import re
from pathlib import Path

import httpx

from honeycomb_studio.campaign import OWNERS
from honeycomb_studio.cloud_restore import public_asset, restore
from honeycomb_studio.store import write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('index', type=Path, help='archive-index.json from the consolidated campaign release')
    parser.add_argument('destination', type=Path)
    parser.add_argument('--all-files', action='store_true', help='Also download INP/ODB/logs and all archived exports')
    args = parser.parse_args()
    index = json.loads(args.index.read_text(encoding='utf-8'))
    results = []
    with httpx.Client(timeout=120, follow_redirects=True) as client:
        for row in index:
            reference = row.get('archive') or {}
            if reference.get('kind') != 'honeycomb-archive-reference' or not reference.get('complete'):
                continue
            if (row['repository'] not in {owner + '/honeycomb-abaqus-studio' for owner in OWNERS}
                    or not re.fullmatch(r'[A-Za-z0-9_.-]{1,150}', row['id'])):
                raise ValueError('Unapproved campaign repository or design ID')
            url = public_asset(reference['manifest_url'], repository=row['repository'])
            payload = bytearray()
            with client.stream('GET', url) as response:
                response.raise_for_status()
                for block in response.iter_bytes():
                    payload.extend(block)
                    if len(payload) > 8 * 1024**2:
                        raise ValueError('Archive inventory exceeds 8 MiB')
            if hashlib.sha256(payload).hexdigest() != reference['manifest_sha256']:
                raise ValueError('Archive inventory checksum differs')
            archive = json.loads(payload)
            paths = None if args.all_files else [f['path'] for f in archive['files'] if f['path'].endswith('impact_history.csv')]
            if paths == []:
                raise ValueError('Completed sample is missing impact_history.csv: ' + row['id'])
            verified = restore(archive, args.destination / row['id'], client=client, paths=paths,
                               repository=row['repository'])
            results.append({'id': row['id'], 'repository': row['repository'], **verified})
            write_json(args.destination / 'download-verification.json', {'designs': results})
            print(row['id'] + ': verified', flush=True)


if __name__ == '__main__':
    main()
