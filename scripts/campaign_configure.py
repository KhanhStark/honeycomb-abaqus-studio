"""Configure authorized runner secrets using encrypted local credentials, without plaintext files."""
import argparse
import json
import os
import socket
import subprocess
from pathlib import Path

from campaign_admin import owner_client

from honeycomb_studio.campaign import OWNERS
from honeycomb_studio.media_cache import preflight_drive_iso


def main():
    import win32crypt  # ty: ignore[unresolved-import]
    from google.auth.transport.requests import AuthorizedSession, Request
    from google.oauth2.credentials import Credentials

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--owners', nargs='+', choices=OWNERS, required=True)
    parser.add_argument('--oidc-clients', type=Path, help='JSON mapping of owner to repository-scoped client ID')
    args = parser.parse_args()
    source = owner_client('xuankhanh24')
    media = source.request('GET', '/repos/xuankhanh24/honeycomb-abaqus-studio/actions/variables/ABAQUS_MEDIA_DRIVE_FILE_ID')['value']
    encrypted = Path(os.environ['LOCALAPPDATA']) / 'HoneycombStudio/drive-token.dpapi'
    payload = win32crypt.CryptUnprotectData(encrypted.read_bytes(), None, None, None, 0)[1]
    credentials = Credentials.from_authorized_user_info(json.loads(payload))
    try:
        credentials.refresh(Request())
        with AuthorizedSession(credentials) as session:
            preflight_drive_iso(session, media)
    except Exception:
        raise RuntimeError('Drive preflight failed; re-authenticate the media account') from None
    address = subprocess.run([r'C:\Program Files\Tailscale\tailscale.exe', 'ip', '-4'],
                             check=True, capture_output=True, text=True).stdout.strip()
    if not address.startswith('100.') or '\n' in address:
        raise ValueError('Expected the local license host tailnet address')
    for port in (27011, 27012):
        with socket.create_connection((address, port), timeout=10):
            pass
    clients = json.loads(args.oidc_clients.read_text()) if args.oidc_clients else {}
    for owner in args.owners:
        github = owner_client(owner)
        repository = owner + '/honeycomb-abaqus-studio'
        if github.request('GET', '/user')['login'].lower() != owner.lower():
            raise ValueError('CLI account identity differs')
        values = {'HONEYCOMB_DRIVE_CREDENTIALS_JSON': credentials.to_json(),
                  'ABAQUS_LICENSE_ENDPOINT': '27011@' + address, 'ABAQUS_VENDOR_PORT': '27012'}
        if owner in clients:
            values.update(TS_OAUTH_CLIENT_ID=clients[owner], TS_AUDIENCE='api.tailscale.com/' + clients[owner])
        for name, value in values.items():
            result = subprocess.run(['gh', 'secret', 'set', name, '--repo', repository],
                input=value, text=True, capture_output=True, env={**os.environ, 'GH_TOKEN': github.token})
            if result.returncode:
                raise RuntimeError('Cannot set authorized runner secret: ' + name)
        path = '/repos/' + repository + '/actions/variables'
        existing = github.request('GET', path + '/ABAQUS_MEDIA_DRIVE_FILE_ID', allow_missing=True)
        github.request('PATCH' if existing else 'POST', path + '/ABAQUS_MEDIA_DRIVE_FILE_ID' if existing else path,
                       {'name': 'ABAQUS_MEDIA_DRIVE_FILE_ID', 'value': media})
        print(json.dumps({'owner': owner, 'configured_secret_names': sorted(values),
                          'drive_preflight': True, 'local_license_ports_reachable': True,
                          'plaintext_credentials_written': False}), flush=True)


if __name__ == '__main__':
    main()
