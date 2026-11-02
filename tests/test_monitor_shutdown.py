from pathlib import Path
from types import SimpleNamespace

import pytest

from honeycomb_studio.engine import Detached, Engine
from honeycomb_studio.models import BatchSpec
from honeycomb_studio.store import Store


def test_shutdown_during_monitor_wait_preserves_owned_process(tmp_path, monkeypatch):
    store = Store(tmp_path)
    batch = store.create(BatchSpec())
    run = store.list("runs", batch["id"])[0]
    attempt = {"path": str(Path(run["path"]) / "attempts/001"), "job_name": "fixture",
               "number": 1, "process": {"pid": 123, "created": 1}}
    engine = Engine(store, fake=True)
    monkeypatch.setattr("honeycomb_studio.engine.solver.owned_tree_alive", lambda _: True)
    monkeypatch.setattr("honeycomb_studio.engine.solver.refresh_owned_tree", lambda _: None)
    monkeypatch.setattr("honeycomb_studio.engine.solver.owned_alive", lambda _: False)
    monkeypatch.setattr(engine.shutdown, "wait", lambda _: engine.shutdown.set())
    with pytest.raises(Detached):
        engine._monitor(run, attempt, "solving", None)
    assert attempt["process"] == {"pid": 123, "created": 1}
    assert "durations" not in attempt
    store.db.close()


def test_recover_eta_uses_only_progress_since_checkpoint(tmp_path, monkeypatch):
    store = Store(tmp_path)
    batch = store.create(BatchSpec())
    run = store.list("runs", batch["id"])[0]
    run['resolved']['duration'] = .012
    attempt = {'path': str(Path(run['path']) / 'attempts/001'), 'job_name': 'fixture', 'number': 1}
    run['attempts'] = [attempt]
    engine = Engine(store, fake=True)
    states = iter([.008034, .008, .0081])  # previous STA, recovered checkpoint, new progress
    monkeypatch.setattr('honeycomb_studio.engine.solver.sta_progress',
                        lambda *args: {'simulation_time_s': next(states)})
    monkeypatch.setattr('honeycomb_studio.engine.solver.launch', lambda *args: SimpleNamespace(wait=lambda: 0))
    monkeypatch.setattr('honeycomb_studio.engine.solver.owner', lambda _: {'pid': 123, 'created': 1})
    alive = iter([True, True, False])
    monkeypatch.setattr('honeycomb_studio.engine.solver.owned_tree_alive', lambda _: next(alive))
    monkeypatch.setattr('honeycomb_studio.engine.solver.refresh_owned_tree', lambda _: None)
    monkeypatch.setattr('honeycomb_studio.engine.solver.owned_alive', lambda _: False)
    monkeypatch.setattr(engine.shutdown, 'wait', lambda _: None)
    clock = iter([100., 400., 400., 700., 700., 700., 700.])
    monkeypatch.setattr('honeycomb_studio.engine.time.time', lambda: next(clock))
    engine._monitor(run, attempt, 'solving', ['job=fixture', 'recover'])
    # Ten wall minutes advanced only .1 ms; 3.9 ms remain, approximately 6.5 h.
    assert run['progress']['eta_solver_seconds'] == pytest.approx(23400)
    store.db.close()
