import hashlib
import importlib.util
from contextlib import contextmanager
from pathlib import Path

import httpx
import pytest


def load_tool():
    path = Path(__file__).parents[1] / 'scripts/campaign_checkpoint_transport.py'
    spec = importlib.util.spec_from_file_location('checkpoint_transport_tool', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inventory(payload=b'original checkpoint'):
    sha = hashlib.sha256(payload).hexdigest()
    url = 'https://github.com/owner/repo/releases/download/checkpoint/state.part'
    return {'schema_version': '1', 'kind': 'honeycomb-release-archive', 'complete': False,
            'files': [{'path': 'state.bin', 'bytes': len(payload), 'sha256': sha,
                       'parts': [{'index': 0, 'offset': 0, 'bytes': len(payload), 'sha256': sha,
                                  'digest': 'sha256:' + sha, 'url': url}]}]}, url


def test_original_verified_restore_uses_api_when_public_endpoint_returns_504(tmp_path):
    tool = load_tool()
    payload = b'original checkpoint'
    manifest, url = inventory(payload)
    requests = []

    def handle(request):
        requests.append(request)
        if request.url.host == 'github.com':
            return httpx.Response(504)
        if request.url.host == 'api.github.com':
            assert request.headers['authorization'] == 'Bearer test-token'
            assert request.headers['accept'] == 'application/octet-stream'
            return httpx.Response(302, headers={'Location': 'https://release-assets.githubusercontent.com/exact-state'})
        assert request.url.host == 'release-assets.githubusercontent.com'
        assert 'authorization' not in request.headers
        return httpx.Response(200, content=payload)

    class Github:
        repository = 'owner/repo'
        client = httpx.Client(transport=httpx.MockTransport(handle))
        def access_token(self): return 'test-token'
        def repo(self, method, path):
            assert method == 'GET' and path == '/releases/tags/checkpoint'
            return {'id': 7, 'assets': [{'id': 11, 'name': 'state.part', 'browser_download_url': url,
                                        'state': 'uploaded'}]}

    with httpx.Client(transport=httpx.MockTransport(handle)) as body_client:
        transport = tool.ReleaseAssetTransport(Github(), body_client)
        result = tool.restore_checkpoint(manifest, tmp_path, transport=transport,
                                         allow_incomplete=True, sleep=lambda _: None)
    assert (tmp_path / 'state.bin').read_bytes() == payload
    assert not result['complete_dataset']
    assert [r.url.host for r in requests] == ['api.github.com', 'release-assets.githubusercontent.com']


@pytest.mark.parametrize('case', ['504', 'partial'])
def test_retry_reuses_verified_parts_and_restarts_unverified_part(tmp_path, case):
    tool = load_tool()
    manifest, _ = inventory()
    calls = []

    class BrokenStream(httpx.SyncByteStream):
        def __iter__(self):
            yield b'original '
            raise httpx.ReadError('interrupted')

    class Transport:
        repository = 'owner/repo'
        @contextmanager
        def stream(self, method, url):
            calls.append(url)
            request = httpx.Request(method, url)
            if len(calls) == 1:
                response = (httpx.Response(504, request=request) if case == '504' else
                            httpx.Response(200, request=request, stream=BrokenStream()))
            else:
                response = httpx.Response(200, request=request, content=b'original checkpoint')
            try: yield response
            finally: response.close()

    tool.restore_checkpoint(manifest, tmp_path, transport=Transport(), allow_incomplete=True,
                            sleep=lambda _: None)
    assert len(calls) == 2
    assert (tmp_path / 'state.bin').read_bytes() == b'original checkpoint'


@pytest.mark.parametrize('status', [403, 404])
def test_permanent_errors_do_not_retry_or_publish(tmp_path, status):
    tool = load_tool()
    manifest, _ = inventory()
    calls = []
    class Transport:
        repository = 'owner/repo'
        @contextmanager
        def stream(self, method, url):
            calls.append(url)
            response = httpx.Response(status, request=httpx.Request(method, url))
            try: yield response
            finally: response.close()
    with pytest.raises(httpx.HTTPStatusError):
        tool.restore_checkpoint(manifest, tmp_path, transport=Transport(), allow_incomplete=True,
                                sleep=lambda _: None)
    assert len(calls) == 1 and not (tmp_path / 'state.bin').exists()


def test_changed_bytes_still_fail_original_digest_gate(tmp_path):
    tool = load_tool()
    manifest, _ = inventory()
    class Transport:
        repository = 'owner/repo'
        @contextmanager
        def stream(self, method, url):
            response = httpx.Response(200, request=httpx.Request(method, url), content=b'wrong bytes')
            try: yield response
            finally: response.close()
    with pytest.raises(ValueError, match='SHA-256'):
        tool.restore_checkpoint(manifest, tmp_path, transport=Transport(), allow_incomplete=True,
                                sleep=lambda _: None)
    assert not (tmp_path / 'state.bin').exists()
