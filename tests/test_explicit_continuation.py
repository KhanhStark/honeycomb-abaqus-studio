import importlib.util
import io
import json
import tarfile
from pathlib import Path

import pytest

from honeycomb_studio.cloud_continuation import checkpoint_inventory, verify_checkpoint
from honeycomb_studio.engine import Engine
from honeycomb_studio.models import BatchSpec
from honeycomb_studio.store import Store


def raw_files(tmp_path):
    for ext in ('abq', 'pac', 'res', 'sel', 'odb'):
        (tmp_path / ('hc.' + ext)).write_bytes(ext.encode())
    return checkpoint_inventory(tmp_path, 'hc')


def test_recovery_rejects_corruption_or_different_input(tmp_path):
    files = raw_files(tmp_path)
    receipt = dict(job_name='hc', input_hash='input', runtime_hash='runtime', cpus=4, files=files)
    verify_checkpoint(tmp_path, receipt, job_name='hc', input_hash='input', runtime_hash='runtime', cpus=4)
    with pytest.raises(ValueError, match='identity'):
        verify_checkpoint(tmp_path, receipt, job_name='hc', input_hash='other', runtime_hash='runtime', cpus=4)
    (tmp_path / 'hc.abq').write_bytes(b'broken')
    with pytest.raises(ValueError, match='checksum'):
        verify_checkpoint(tmp_path, receipt, job_name='hc', input_hash='input', runtime_hash='runtime', cpus=4)


def test_recovery_requires_all_state_families(tmp_path):
    raw_files(tmp_path)
    (tmp_path / 'hc.sel').unlink()
    with pytest.raises(ValueError, match='sel'):
        checkpoint_inventory(tmp_path, 'hc')


def test_engine_continues_original_attempt_without_building(monkeypatch, tmp_path):
    store = Store(tmp_path)
    batch = store.create(BatchSpec(name='recover'))
    run = store.list('runs', batch['id'])[0]
    attempt_path = Path(run['path']) / 'attempts/001'
    (attempt_path / 'raw').mkdir(parents=True)
    (attempt_path / 'logs').mkdir()
    run['attempts'] = [{'number': 1, 'path': str(attempt_path), 'job_name': 'original'}]
    run['explicit_recover'] = True
    engine = Engine(store, fake=False)
    calls = []
    def monitor(r, a, phase, args):
        assert phase == 'solving' and 'recover' in args
        assert 'job=original' in args and not any(v.startswith('input=') for v in args)
        calls.append(args)
        (attempt_path / 'raw/original.sta').write_text(
            ' 101338 6.000E-03 6.000E-03 00:23:48 5.704E-08 26813 3.013E+02 7.002E+03\n'
            'THE ANALYSIS HAS COMPLETED SUCCESSFULLY')
    monkeypatch.setattr(engine, '_monitor', monitor)
    monkeypatch.setattr(engine, '_postprocess', lambda *args: None)
    engine._execute(run, batch)
    assert len(calls) == 1 and len(run['attempts']) == 1
    assert (attempt_path / 'solver-complete.json').is_file()
    store.db.close()


def bundle_module():
    spec = importlib.util.spec_from_file_location('continuation_bundle', Path(__file__).parents[1] / 'scripts/continuation_bundle.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_segment_bundle_roundtrip_and_tamper(monkeypatch, tmp_path):
    mod = bundle_module()
    root = tmp_path / 'root'
    root.mkdir()
    (root / 'state').write_bytes(b'checkpoint')
    monkeypatch.setattr(mod, 'ROOT', root)
    folder = tmp_path / 'bundle'
    mod.pack(folder, 'checkpoint')
    (root / 'state').unlink()
    root.rmdir()
    assert mod.restore(folder, 1) is False
    assert (root / 'state').read_bytes() == b'checkpoint'
    (root / 'state').unlink()
    root.rmdir()
    (folder / 'state.tar').write_bytes(b'broken')
    with pytest.raises(ValueError, match='Corrupt'):
        mod.restore(folder, 1)


def test_bundle_rejects_traversal(monkeypatch, tmp_path):
    import hashlib
    mod = bundle_module()
    monkeypatch.setattr(mod, 'ROOT', tmp_path / 'root')
    archive = tmp_path / 'state.tar'
    with tarfile.open(archive, 'w') as tar:
        member = tarfile.TarInfo('../escape')
        member.size = 1
        tar.addfile(member, io.BytesIO(b'x'))
    (tmp_path / 'segment.json').write_text(json.dumps({'outcome': 'checkpoint', 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'bytes': archive.stat().st_size}))
    with pytest.raises(ValueError, match='Unsafe'):
        mod.restore(tmp_path, 1)
    assert not (tmp_path / 'escape').exists()
