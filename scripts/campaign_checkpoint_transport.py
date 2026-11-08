"""Fetch exact predecessor bytes through GitHub's asset API; run the frozen worker."""
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

import httpx

from honeycomb_studio.cloud_restore import public_asset, restore, validate_manifest


def history_verifier():
    """Load only receipt validation from the independently pinned tool checkout."""
    path = Path(__file__).resolve().parents[1] / 'src/honeycomb_studio/cloud_continuation.py'
    spec = importlib.util.spec_from_file_location('honeycomb_studio._checkpoint_receipt_repair', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReleaseAssetTransport:
    def __init__(self, github, client):
        self.github, self.client = github, client
        self.repository = github.repository
        self.assets = {}

    def asset_id(self, url):
        public_asset(url, repository=self.repository)
        if url in self.assets:
            return self.assets[url]
        prefix = '/' + self.repository + '/releases/download/'
        tag, name = urlparse(url).path[len(prefix):].rsplit('/', 1)
        release = self.github.repo('GET', '/releases/tags/' + quote(unquote(tag), safe=''))
        candidates = release.get('assets', [])
        for page in range(1, 102):
            for asset in candidates:
                if (asset.get('browser_download_url') == url and asset.get('name') == unquote(name)
                        and asset.get('state') == 'uploaded'):
                    self.assets[url] = asset['id']
                    return asset['id']
            if page > 1 and len(candidates) < 100:
                break
            candidates = self.github.repo('GET', f'/releases/{release["id"]}/assets?per_page=100&page={page}')
        raise ValueError('Original checkpoint release asset is absent')

    @contextmanager
    def stream(self, method, url):
        if method != 'GET':
            raise ValueError('Checkpoint transport is read only')
        asset = self.asset_id(url)
        response = self.github.client.get(
            f'https://api.github.com/repos/{self.repository}/releases/assets/{asset}',
            headers={'Authorization': 'Bearer ' + self.github.access_token(),
                     'Accept': 'application/octet-stream'}, follow_redirects=False)
        if response.status_code != 302:
            response.raise_for_status()
            raise ValueError('Checkpoint API did not return an asset redirect')
        location = response.headers['location']
        parsed = urlparse(location)
        if (parsed.scheme != 'https' or parsed.hostname not in (
                'release-assets.githubusercontent.com', 'objects.githubusercontent.com')
                or parsed.username or parsed.password or parsed.port not in (None, 443)):
            raise ValueError('Checkpoint API returned an unexpected asset host')
        # This separate client has no GitHub authorization header.
        try:
            with self.client.stream('GET', location) as body:
                yield body
        except httpx.HTTPStatusError as exc:
            # Keep signed download URLs out of the public Actions traceback.
            safe = httpx.Response(exc.response.status_code, request=httpx.Request('GET', url))
            raise httpx.HTTPStatusError('Checkpoint transfer HTTP ' + str(safe.status_code),
                                        request=safe.request, response=safe) from None
        except httpx.TransportError:
            raise httpx.ReadError('Checkpoint transfer interrupted') from None


def restore_checkpoint(manifest, root, *, transport, sleep=time.sleep, **kwargs):
    validate_manifest(manifest, allow_incomplete=kwargs.get('allow_incomplete', False),
                      repository=transport.repository)
    for attempt in range(6):
        try:
            return restore(manifest, root, client=transport, repository=transport.repository, **kwargs)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in (408, 429, 500, 502, 503, 504) or attempt == 5:
                raise
        except httpx.TransportError:
            if attempt == 5:
                raise
        # The original reader verifies/reuses complete parts and truncates partial parts.
        sleep(min(2 ** (attempt + 1), 30))


def main():
    from honeycomb_studio.campaign_queue import ticket_key
    from honeycomb_studio.cloud_github import Catalog, Github

    original = Path.cwd()
    sys.path.insert(0, str(original / 'scripts'))
    import campaign_worker as worker

    github = Github(token=os.environ['GITHUB_TOKEN'])
    catalog = Catalog(github)
    key = ticket_key(os.environ['CAMPAIGN_ID'], os.environ['TICKET'])
    workflow = int(os.environ['GITHUB_RUN_ID'])
    tool_source = subprocess.check_output(['git', '-C', str(Path(__file__).resolve().parents[1]),
                                           'rev-parse', 'HEAD'], text=True).strip()
    tool_digest = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

    def record(old):
        if (not old or old.get('status') != 'claimed' or old.get('workflow_run_id') != workflow
                or old.get('source_sha') != worker.source_sha()):
            raise ValueError('Checkpoint transport has no exclusive frozen worker claim')
        return {**old, 'checkpoint_transport': {'source_sha': tool_source, 'script_sha256': tool_digest,
                 'worker_source_sha': old['source_sha'], 'workflow_run_id': workflow,
                 'mode': 'github-release-asset-api', 'utc_epoch': time.time()}}

    catalog.update(key, record)
    verifier = history_verifier()

    def verify_history(raw, job_name, executable, spec):
        marker = worker.ROOT / 'continuation.json'
        predecessor = json.loads(marker.read_text()).get('orderly_checkpoint') if marker.exists() else None
        result = verifier.verify_checkpoint_history(raw, job_name, executable, spec, predecessor=predecessor)
        result['receipt_verifier'] = {'source_sha': tool_source,
            'sha256': hashlib.sha256(Path(verifier.__file__).read_bytes()).hexdigest()}
        return result

    worker.verify_checkpoint_history = verify_history
    with httpx.Client(timeout=120, follow_redirects=True) as body_client:
        transport = ReleaseAssetTransport(github, body_client)
        worker.restore = lambda manifest, root, **kwargs: restore_checkpoint(
            manifest, root, transport=transport, **kwargs)
        worker.main()


if __name__ == '__main__':
    main()
