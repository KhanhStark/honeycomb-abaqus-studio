"""Recover the pinned ISO from its existing mirror when private Drive refuses transport."""
import os
import re
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from honeycomb_studio.media_cache import ISO_BYTES, ISO_NAME, ISO_SHA256, verify_iso
from inspect_linux_media import SIZES, download


def download_pinned_mirror(destination, *, expected_bytes=ISO_BYTES, expected_sha256=ISO_SHA256):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(destination.parent).free < sum(SIZES) + expected_bytes + 2 * 1024**3:
        raise RuntimeError('Insufficient temporary disk for pinned mirror extraction')
    with tempfile.TemporaryDirectory(prefix='abaqus-pinned-mirror-', dir=destination.parent) as temporary:
        root = Path(temporary)
        with ThreadPoolExecutor(max_workers=3) as pool:
            volumes = list(pool.map(lambda i: download(i, root), range(len(SIZES))))
        archive = root / 'media.part1.rar'
        names = subprocess.run(['unrar', 'lb', '-pwww.softgozar.com', str(archive)],
                               check=True, capture_output=True, text=True, timeout=180).stdout.splitlines()
        matches = [n for n in names if n.lower().endswith('.iso')]
        if len(matches) != 1 or re.split(r'[/\\]', matches[0])[-1] != ISO_NAME:
            raise ValueError('Mirror does not contain the pinned ISO entry')
        entry = matches[0]
        if ':' in entry or any(p in ('..', 'crack') for p in re.split(r'[/\\]', entry.lower())):
            raise ValueError('Unsafe mirror ISO entry')
        iso_directory = root / 'iso'
        iso_directory.mkdir()
        subprocess.run(['unrar', 'e', '-idq', '-y', '-o-', '-pwww.softgozar.com', str(archive),
                        entry, str(iso_directory) + '/'], check=True, capture_output=True, timeout=1800)
        iso = iso_directory / ISO_NAME
        if iso.is_symlink() or not iso.is_file():
            raise ValueError('Mirror did not produce a regular ISO')
        result = verify_iso(iso, expected_bytes=expected_bytes, expected_sha256=expected_sha256)
        os.replace(iso, destination)
    return {**result, 'transport_source': 'original_pinned_mirror', 'volumes': volumes}
