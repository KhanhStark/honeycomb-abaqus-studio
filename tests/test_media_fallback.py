import hashlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import media_fallback as fallback


@pytest.mark.parametrize('problem', [None, 'wrong_bytes', 'wrong_hash', 'unsafe_entry'])
def test_mirror_publishes_only_exact_pinned_iso_and_cleans_its_temporary_files(tmp_path, monkeypatch, problem):
    payload = b'unchanged pinned installation fixture'
    target = tmp_path / 'media.iso'
    monkeypatch.setattr(fallback, 'SIZES', [3, 4])
    def download(index, directory):
        (directory / ('media.part' + str(index + 1) + '.rar')).write_bytes(b'rar')
        return {'bytes': 3, 'sha256': 'verified-volume'}
    monkeypatch.setattr(fallback, 'download', download)
    calls = []
    def unrar(command, **kwargs):
        calls.append(command[1])
        if command[1] == 'lb':
            return SimpleNamespace(stdout=('../' if problem == 'unsafe_entry' else '') + fallback.ISO_NAME + '\n')
        (Path(command[-1]) / fallback.ISO_NAME).write_bytes(payload + (b'!' if problem == 'wrong_bytes' else b''))
    monkeypatch.setattr(fallback.subprocess, 'run', unrar)
    args = dict(expected_bytes=len(payload), expected_sha256=hashlib.sha256(
        b'wrong' if problem == 'wrong_hash' else payload).hexdigest())
    if problem:
        with pytest.raises(ValueError):
            fallback.download_pinned_mirror(target, **args)
        assert not target.exists()
    else:
        result = fallback.download_pinned_mirror(target, **args)
        assert target.read_bytes() == payload
        assert result['transport_source'] == 'original_pinned_mirror'
        assert calls == ['lb', 'e']
    assert not list(tmp_path.glob('abaqus-pinned-mirror-*'))
