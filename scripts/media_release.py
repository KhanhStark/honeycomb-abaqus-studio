"""Encrypted GitHub CDN mirror of the exact pinned ISO; no installer code changes."""
import hashlib
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse

import requests
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from honeycomb_studio.media_cache import ISO_BYTES, ISO_SHA256, verify_iso

REPOSITORY = 'xuankhanh24/honeycomb-abaqus-studio'
MANIFEST_NAME = 'encrypted-media-manifest.json'
BLOCK = 4 * 1024**2
PART_BYTES = 1024**3


class ReleaseTransferError(RuntimeError):
    """Sanitized, retryable CDN transport failure, distinct from invalid content."""


def media_key():
    value = os.environ.get('ABAQUS_MEDIA_RELEASE_KEY', '')
    if not re.fullmatch('[a-f0-9]{64}', value):
        raise ValueError('Encrypted media key is missing or invalid')
    return bytes.fromhex(value)


def tag_name():
    value = os.environ.get('ABAQUS_MEDIA_RELEASE_TAG', '')
    if not re.fullmatch(r'abaqus2020-encrypted-[a-f0-9]{16}-[a-f0-9]{8}', value):
        raise ValueError('Invalid pinned media release tag')
    return value


def api_json(path):
    try:
        response = requests.get('https://api.github.com/repos/' + REPOSITORY + path,
            headers={'Authorization': 'Bearer ' + os.environ['GITHUB_TOKEN'],
                     'Accept': 'application/vnd.github+json'}, timeout=(20, 45))
        if response.status_code != 200:
            raise ReleaseTransferError('Media release API HTTP ' + str(response.status_code))
        return response.json()
    except requests.RequestException:
        raise ReleaseTransferError('Media release API connection interrupted') from None


@contextmanager
def asset_stream(asset_id):
    """Send credentials only to api.github.com; fetch fresh signed URLs on retries."""
    try:
        with requests.get(f'https://api.github.com/repos/{REPOSITORY}/releases/assets/{int(asset_id)}',
                headers={'Authorization': 'Bearer ' + os.environ['GITHUB_TOKEN'],
                         'Accept': 'application/octet-stream'}, stream=True,
                allow_redirects=False, timeout=(20, 60)) as response:
            if response.status_code == 200:
                yield response
                return
            if response.status_code != 302:
                raise ReleaseTransferError('Media asset API HTTP ' + str(response.status_code))
            location = response.headers.get('Location', '')
        parsed = urlparse(location)
        if (parsed.scheme != 'https' or parsed.hostname not in (
                'release-assets.githubusercontent.com', 'objects.githubusercontent.com')
                or parsed.username or parsed.password or parsed.port not in (None, 443)):
            raise ValueError('Media release returned an unexpected CDN host')
        # A separate request carries no GitHub token to the asset host.
        with requests.get(location, stream=True, allow_redirects=False, timeout=(20, 90)) as body:
            if body.status_code != 200:
                raise ReleaseTransferError('Media CDN HTTP ' + str(body.status_code))
            yield body
    except requests.RequestException:
        raise ReleaseTransferError('Media CDN connection interrupted') from None


def validate_manifest(manifest, *, expected_bytes=ISO_BYTES, expected_sha256=ISO_SHA256):
    if (manifest.get('schema') != 1 or manifest.get('bytes') != expected_bytes
            or manifest.get('sha256') != expected_sha256):
        raise ValueError('Media manifest does not identify the pinned ISO')
    parts = manifest.get('parts', [])
    if not 1 <= len(parts) <= 64:
        raise ValueError('Invalid media part count')
    offset, nonces, names = 0, set(), set()
    for part in parts:
        if (not isinstance(part.get('bytes'), int) or not 0 < part['bytes'] < 2 * 1024**3
                or part.get('offset') != offset
                or not re.fullmatch(r'media-[0-9]{3}\.aes', part.get('name', ''))
                or not re.fullmatch('[a-f0-9]{64}', part.get('sha256', ''))
                or not re.fullmatch('[a-f0-9]{24}', part.get('nonce', ''))
                or not re.fullmatch('[a-f0-9]{32}', part.get('tag', ''))
                or part['nonce'] in nonces or part['name'] in names):
            raise ValueError('Invalid media part layout or authentication data')
        nonces.add(part['nonce'])
        names.add(part['name'])
        offset += part['bytes']
    if offset != expected_bytes:
        raise ValueError('Media parts do not cover the pinned ISO')


def decrypt_part(part, asset_id, destination, key, *, stream=asset_stream):
    for attempt in range(4):
        try:
            decryptor = Cipher(algorithms.AES(key), modes.GCM(
                bytes.fromhex(part['nonce']), bytes.fromhex(part['tag']))).decryptor()
            digest, count = hashlib.sha256(), 0
            with stream(asset_id) as response, Path(destination).open('r+b') as output:
                output.seek(part['offset'])
                for block in response.iter_content(BLOCK):
                    count += len(block)
                    if count > part['bytes']:
                        raise ValueError('Encrypted media part exceeds its pinned size')
                    digest.update(block)
                    output.write(decryptor.update(block))
                if count != part['bytes']:
                    raise ReleaseTransferError('Encrypted media part was truncated')
                if digest.hexdigest() != part['sha256']:
                    raise ValueError('Encrypted media part SHA-256 mismatch')
                output.write(decryptor.finalize())
            return
        except ReleaseTransferError:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)


def download_release(destination, *, logger=None, expected_bytes=ISO_BYTES,
                     expected_sha256=ISO_SHA256):
    started = time.monotonic()
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    key = media_key()
    release = api_json('/releases/tags/' + tag_name())
    assets = {a['name']: a for a in release.get('assets', []) if a.get('state') == 'uploaded'}
    asset = assets.get(MANIFEST_NAME)
    if not asset or not 0 < asset['size'] <= 128 * 1024:
        raise ValueError('Pinned encrypted media manifest is absent or too large')
    with asset_stream(asset['id']) as response:
        data = bytearray()
        for block in response.iter_content(16 * 1024):
            data.extend(block)
            if len(data) > 128 * 1024:
                raise ValueError('Encrypted media manifest exceeds limit')
    manifest = json.loads(data)
    validate_manifest(manifest, expected_bytes=expected_bytes, expected_sha256=expected_sha256)
    for part in manifest['parts']:
        if part['name'] not in assets or assets[part['name']]['size'] != part['bytes']:
            raise ValueError('Pinned encrypted media part is missing or has changed size')
    partial = destination.with_suffix(destination.suffix + '.release.part')
    try:
        with partial.open('wb') as output:
            output.truncate(expected_bytes)
        if logger:
            logger.emit('START', 'GitHub CDN: tải song song 4 phần bộ cài đã mã hóa')
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda p: decrypt_part(p, assets[p['name']]['id'], partial, key), manifest['parts']))
        result = verify_iso(partial, expected_bytes=expected_bytes, expected_sha256=expected_sha256)
        partial.replace(destination)
        seconds = time.monotonic() - started
        result.update(transport_source='encrypted_github_release', seconds=round(seconds, 3),
                      average_mib_s=round(expected_bytes / 1024**2 / seconds, 2), parallel_downloads=4)
        if logger:
            logger.emit('PASS', f'ISO SHA-256 đúng; GitHub CDN {result["average_mib_s"]} MiB/s, {seconds:.1f}s')
        return result
    finally:
        partial.unlink(missing_ok=True)


def publish_release(iso):
    """Publish ciphertext only. A release becomes visible after all assets exist."""
    from honeycomb_studio.cloud_github import Github
    verify_iso(Path(iso))
    key, tag = media_key(), tag_name()
    github = Github(token=os.environ['GITHUB_TOKEN'], repository=REPOSITORY)
    existing = github.repo('GET', '/releases/tags/' + tag, allow_missing=True)
    if existing:
        raise ValueError('Encrypted media release already exists; never overwrite it')
    release = github.repo('POST', '/releases', {'tag_name': tag, 'target_commitish': 'main',
        'name': 'Campaign installer cache (AES-256-GCM encrypted)', 'draft': True,
        'body': 'Encrypted installation media for authorized campaign runners. '
                'The key is stored only in Actions secrets. Original ISO SHA-256: ' + ISO_SHA256})

    def upload(path, name):
        # The upload host is fixed; no provider URL from a manifest is trusted.
        with Path(path).open('rb') as content:
            response = requests.post(
                f'https://uploads.github.com/repos/{REPOSITORY}/releases/{release["id"]}/assets',
                params={'name': name}, headers={'Authorization': 'Bearer ' + os.environ['GITHUB_TOKEN'],
                'Content-Type': 'application/octet-stream', 'Content-Length': str(Path(path).stat().st_size)},
                data=content, timeout=(30, 900))
        if response.status_code != 201:
            raise ReleaseTransferError('Media upload HTTP ' + str(response.status_code))
        asset = response.json()
        if asset['size'] != Path(path).stat().st_size or asset['state'] != 'uploaded':
            raise ValueError('Uploaded encrypted media size/state mismatch')
        return asset

    manifest = {'schema': 1, 'bytes': ISO_BYTES, 'sha256': ISO_SHA256, 'parts': []}
    with Path(iso).open('rb') as source:
        offset = 0
        while offset < ISO_BYTES:
            count = min(PART_BYTES, ISO_BYTES - offset)
            name = 'media-' + str(len(manifest['parts'])).zfill(3) + '.aes'
            temporary = Path(iso).parent / name
            nonce = os.urandom(12)
            encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
            digest, remaining = hashlib.sha256(), count
            try:
                with temporary.open('xb') as target:
                    while remaining:
                        block = source.read(min(BLOCK, remaining))
                        if not block:
                            raise ValueError('Pinned media changed during encryption')
                        remaining -= len(block)
                        encrypted = encryptor.update(block)
                        target.write(encrypted)
                        digest.update(encrypted)
                    final = encryptor.finalize()
                    target.write(final)
                    digest.update(final)
                upload(temporary, name)
            finally:
                temporary.unlink(missing_ok=True)
            manifest['parts'].append({'name': name, 'bytes': count, 'offset': offset,
                'nonce': nonce.hex(), 'tag': encryptor.tag.hex(), 'sha256': digest.hexdigest()})
            offset += count
            print(json.dumps({'encrypted_uploaded_parts': len(manifest['parts']), 'bytes': offset}), flush=True)
    validate_manifest(manifest)
    manifest_path = Path(iso).parent / MANIFEST_NAME
    manifest_path.write_text(json.dumps(manifest), encoding='utf8')
    upload(manifest_path, MANIFEST_NAME)
    github.repo('PATCH', '/releases/' + str(release['id']), {'draft': False})
    print(json.dumps({'encrypted_release_published': True, 'release_id': release['id'], 'tag': tag}), flush=True)
