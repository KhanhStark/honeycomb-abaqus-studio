import hashlib
import json
import re
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import media_release as media


def test_runtime_action_receives_repository_settings_through_declared_inputs():
    root = Path(__file__).parents[1]
    action = (root / '.github/actions/abaqus-runtime/action.yml').read_text(encoding='utf8')
    # The runner's action manifest expression context excludes vars/secrets.
    assert not re.search(r'\$\{\{\s*(?:vars|secrets)\.', action)
    inputs = action.split('inputs:\n', 1)[1].split('\nruns:', 1)[0]
    declared = set(re.findall(r'^  ([a-z_]+):$', inputs, re.M))
    assert {'media_release_key', 'media_release_tag'} <= declared
    assert 'ABAQUS_MEDIA_RELEASE_TAG: ${{ inputs.media_release_tag }}' in action
    for name in ('core-damage-worker.yml', 'core-damage-postprocess.yml'):
        workflow = (root / '.github/workflows' / name).read_text(encoding='utf8')
        assert 'media_release_tag: ${{ vars.ABAQUS_MEDIA_RELEASE_TAG }}' in workflow


def encrypted_fixture():
    payload, key = b'pinned installer bytes with ordered parts', bytes(range(32))
    manifest = {'schema': 1, 'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest(), 'parts': []}
    encrypted = {}
    for i, offset in enumerate(range(0, len(payload), 9)):
        data, nonce = payload[offset:offset + 9], i.to_bytes(12, 'big')
        encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
        ciphertext = encryptor.update(data) + encryptor.finalize()
        manifest['parts'].append({'name': f'media-{i:03}.aes', 'bytes': len(data), 'offset': offset,
            'nonce': nonce.hex(), 'tag': encryptor.tag.hex(), 'sha256': hashlib.sha256(ciphertext).hexdigest()})
        encrypted[i + 1] = ciphertext
    return payload, key, manifest, encrypted


def install_fake_release(monkeypatch, *, problem=None):
    payload, key, manifest, encrypted = encrypted_fixture()
    monkeypatch.setenv('ABAQUS_MEDIA_RELEASE_KEY', (bytes(32) if problem == 'wrong_key' else key).hex())
    monkeypatch.setenv('ABAQUS_MEDIA_RELEASE_TAG', 'abaqus2020-encrypted-d0b227290b5f62ea-12345678')
    assets = [{'name': part['name'], 'id': i + 1, 'size': part['bytes'], 'state': 'uploaded'}
              for i, part in enumerate(manifest['parts'])]
    data = json.dumps(manifest).encode()
    assets.append({'name': media.MANIFEST_NAME, 'id': 100, 'size': len(data), 'state': 'uploaded'})
    calls = []

    @contextmanager
    def stream(asset_id):
        calls.append(asset_id)
        body = data if asset_id == 100 else encrypted[asset_id]
        if asset_id == 2 and problem == 'wrong_hash':
            body = b'!' * len(body)
        if asset_id == 2 and problem == 'transient' and calls.count(2) == 1:
            raise media.ReleaseTransferError('sanitized interruption')
        yield type('Body', (), {'iter_content': lambda self, _: iter([body[:2], body[2:]])})()

    monkeypatch.setattr(media, 'api_json', lambda _: {'assets': assets})
    monkeypatch.setattr(media, 'asset_stream', stream)
    # decrypt_part resolves its explicit stream seam; do not bind a production function in this fixture.
    original = media.decrypt_part
    monkeypatch.setattr(media, 'decrypt_part', lambda *a: original(*a, stream=stream))
    monkeypatch.setattr(media.time, 'sleep', lambda _: None)
    return payload, manifest, calls


@pytest.mark.parametrize('problem', [None, 'transient', 'wrong_hash', 'wrong_key'])
def test_release_decryption_requires_authenticated_ordered_bytes_and_final_iso_hash(tmp_path, monkeypatch, problem):
    payload, manifest, calls = install_fake_release(monkeypatch, problem=problem)
    target = tmp_path / 'pinned.iso'
    args = {'expected_bytes': len(payload), 'expected_sha256': manifest['sha256']}
    if problem in ('wrong_hash', 'wrong_key'):
        with pytest.raises((ValueError, InvalidTag)):
            media.download_release(target, **args)
        assert not target.exists()
    else:
        result = media.download_release(target, **args)
        assert target.read_bytes() == payload
        assert result['transport_source'] == 'encrypted_github_release'
        assert calls.count(2) == (2 if problem == 'transient' else 1)
    assert not list(tmp_path.glob('*.part'))


@pytest.mark.parametrize('problem', ['gap', 'overlap', 'nonce_reuse', 'path', 'total', 'fingerprint'])
def test_manifest_cannot_change_installer_identity_or_part_layout(problem):
    payload, key, manifest, encrypted = encrypted_fixture()
    if problem == 'gap':
        manifest['parts'][1]['offset'] += 1
    elif problem == 'overlap':
        manifest['parts'][1]['offset'] -= 1
    elif problem == 'nonce_reuse':
        manifest['parts'][1]['nonce'] = manifest['parts'][0]['nonce']
    elif problem == 'path':
        manifest['parts'][0]['name'] = '../media-000.aes'
    elif problem == 'total':
        manifest['parts'].pop()
    else:
        manifest['sha256'] = '0' * 64
    with pytest.raises(ValueError):
        media.validate_manifest(manifest, expected_bytes=len(payload), expected_sha256=hashlib.sha256(payload).hexdigest())


def test_asset_redirect_never_forwards_github_token_to_cdn(monkeypatch):
    calls = []
    monkeypatch.setenv('GITHUB_TOKEN', 'private-api-credential')

    @contextmanager
    def get(url, **kwargs):
        calls.append((url, kwargs))
        yield type('Response', (), {'status_code': 302 if len(calls) == 1 else 200,
            'headers': {'Location': 'https://release-assets.githubusercontent.com/opaque-signed-url'}})()

    monkeypatch.setattr(media.requests, 'get', get)
    with media.asset_stream(123):
        pass
    assert calls[0][1]['headers']['Authorization'] == 'Bearer private-api-credential'
    assert 'headers' not in calls[1][1]


def test_asset_redirect_rejects_unexpected_hosts(monkeypatch):
    monkeypatch.setenv('GITHUB_TOKEN', 'private-api-credential')

    @contextmanager
    def get(url, **kwargs):
        yield type('Response', (), {'status_code': 302, 'headers': {'Location': 'https://untrusted.example/payload'}})()

    monkeypatch.setattr(media.requests, 'get', get)
    with pytest.raises(ValueError, match='unexpected CDN host'):
        with media.asset_stream(123):
            pass


def test_controller_relay_runs_after_tick_failure_but_respects_cancellation():
    workflow = (Path(__file__).parents[1] / '.github/workflows/core-damage-controller.yml').read_text()
    relay = workflow.split('name: Keep the active campaign moving', 1)[1]
    assert "!cancelled() && steps.dependencies.outcome == 'success'" in relay
    assert 'sleep 5' in relay


def test_publisher_uploads_only_ciphertext_and_exposes_release_after_manifest(tmp_path, monkeypatch):
    from honeycomb_studio import cloud_github
    payload = b'previously verified installation bytes'
    iso = tmp_path / 'pinned.iso'
    iso.write_bytes(payload)
    monkeypatch.setenv('GITHUB_TOKEN', 'private-token')
    monkeypatch.setenv('ABAQUS_MEDIA_RELEASE_KEY', bytes(range(32)).hex())
    monkeypatch.setenv('ABAQUS_MEDIA_RELEASE_TAG', 'abaqus2020-encrypted-d0b227290b5f62ea-12345678')
    monkeypatch.setattr(media, 'ISO_BYTES', len(payload))
    monkeypatch.setattr(media, 'ISO_SHA256', hashlib.sha256(payload).hexdigest())
    monkeypatch.setattr(media, 'PART_BYTES', 10)
    monkeypatch.setattr(media, 'verify_iso', lambda p: None)
    original_validate = media.validate_manifest
    monkeypatch.setattr(media, 'validate_manifest', lambda m: original_validate(m,
        expected_bytes=len(payload), expected_sha256=hashlib.sha256(payload).hexdigest()))
    calls, uploads = [], {}

    class Github:
        def __init__(self, **kwargs):
            pass

        def repo(self, method, path, body=None, **kwargs):
            calls.append((method, path, body))
            return None if method == 'GET' else {'id': 42}

    def post(url, *, params, headers, data, **kwargs):
        assert url.startswith('https://uploads.github.com/repos/' + media.REPOSITORY)
        uploads[params['name']] = data.read()
        return type('Response', (), {'status_code': 201,
            'json': lambda self: {'size': len(uploads[params['name']]), 'state': 'uploaded'}})()

    monkeypatch.setattr(cloud_github, 'Github', Github)
    monkeypatch.setattr(media.requests, 'post', post)
    media.publish_release(iso)
    assert calls[1][2]['draft'] is True
    assert calls[-1] == ('PATCH', '/releases/42', {'draft': False})
    manifest = json.loads(uploads.pop(media.MANIFEST_NAME))
    restored = bytearray()
    for part in manifest['parts']:
        encrypted = uploads[part['name']]
        decryptor = Cipher(algorithms.AES(bytes(range(32))), modes.GCM(
            bytes.fromhex(part['nonce']), bytes.fromhex(part['tag']))).decryptor()
        restored.extend(decryptor.update(encrypted) + decryptor.finalize())
        assert payload not in encrypted
    assert bytes(restored) == payload
    assert iso.read_bytes() == payload and not list(tmp_path.glob('*.aes'))
