import os
import subprocess
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from honeycomb_studio.api import make_app
from honeycomb_studio.engine import Engine
from honeycomb_studio.models import Axis, BatchSpec
from honeycomb_studio.solver import command, owned_alive, sta_progress
from honeycomb_studio.store import Store


def wait_for(predicate, timeout=10):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("State transition timed out")


def test_stop_second_run_and_resume_only_unfinished(tmp_path):
    store = Store(tmp_path)
    engine = Engine(store, fake=True)
    b = store.create(BatchSpec(axes=[Axis(parameter="energy_J", values=[1, 2, 3])], render_images=False))
    engine.control(b["id"], "start")
    engine.start_worker()
    runs = store.list("runs", b["id"])
    first, second, third = [r["id"] for r in runs]
    try:
        wait_for(
            lambda: (
                store.get("runs", first)["status"] == "completed"
                and store.get("runs", second)["status"] == "solving"
            )
        )
        engine.control(b["id"], "stop")
        wait_for(lambda: store.get("runs", second)["status"] == "interrupted")
        assert len(store.get("runs", first)["attempts"]) == 1
        assert store.get("runs", third)["status"] == "queued"
        engine.control(b["id"], "resume")
        wait_for(lambda: store.get("runs", third)["status"] == "completed")
        assert len(store.get("runs", first)["attempts"]) == 1
        assert len(store.get("runs", second)["attempts"]) == 2
        assert store.get("runs", second)["resolved"]["energy_J"] == 2
    finally:
        engine.shutdown.set()
        engine.wake.set()
        engine.worker.join(5)


def test_http_auth_preview_and_table_import(tmp_path):
    store = Store(tmp_path / "data")
    engine = Engine(store, fake=True)
    app = make_app(store, engine, "test-token", tmp_path / "config", start_worker=False)
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/v1/status").status_code == 401
        headers = {"X-Honeycomb-Token": "test-token"}
        spec = BatchSpec(
            axes=[Axis(parameter="energy_J", start=0.85, stop=3, step=1, include_stop=True)]
        ).model_dump()
        response = client.post("/v1/preview", headers=headers, json=spec)
        assert response.status_code == 200
        assert [r["energy_J"] for r in response.json()["runs"]] == [0.85, 1.85, 2.85, 3]
        b = client.post("/v1/batches", headers=headers, json=spec).json()
        assert len(client.get("/v1/batches/" + b["id"], headers=headers).json()["runs"]) == 4
        assert (
            client.post("/v1/open", headers=headers, json={"path": str(tmp_path.parent)}).status_code == 400
        )


def test_reindex_portable_manifests(tmp_path):
    store = Store(tmp_path)
    b = store.create(BatchSpec())
    store.db.execute("DELETE FROM runs")
    store.db.execute("DELETE FROM batches")
    store.db.commit()
    assert store.reindex() == 2
    assert store.get("batches", b["id"])["runs_total"] == 1


def test_sta_and_process_identity(tmp_path):
    file = tmp_path / "a.sta"
    file.write_text(
        " 101338 6.000E-03 6.000E-03 00:23:48 5.704E-08 26813 3.013E+02 7.002E+03\n THE ANALYSIS HAS COMPLETED SUCCESSFULLY\n"
    )
    p = sta_progress(file, 0.006)
    assert p["solver_percent"] == 100
    assert p["increment"] == 101338
    assert p["solver_success"]
    assert not owned_alive({"pid": 99999999, "created": 1})


def test_successful_orderly_stop_is_not_a_completed_physical_analysis(tmp_path):
    file = tmp_path / 'partial.sta'
    file.write_text(' 101338 6.000E-03 6.000E-03 00:23:48 5.704E-08 26813 3.013E+02 7.002E+03\n'
                    ' THE ANALYSIS HAS COMPLETED SUCCESSFULLY\n')
    assert sta_progress(file, .012)['solver_success'] is False


def test_missing_odb_does_not_create_batch(tmp_path):
    store = Store(tmp_path)
    e = Engine(store)
    with pytest.raises(ValueError):
        e.import_reference(Path("missing.odb"))
    assert store.list("batches") == []


@pytest.mark.skipif(os.name != "nt", reason="Windows cmd quoting")
def test_batch_launcher_and_argument_paths_with_spaces(tmp_path):
    folder = tmp_path / "launcher with spaces"
    folder.mkdir()
    launcher = folder / "launch test.bat"
    launcher.write_text('@echo off\necho %~1>"%~2"\n', encoding="ascii")
    output = folder / "result file.txt"
    process = subprocess.run(command(str(launcher), "hello", str(output)), capture_output=True, timeout=10)
    assert process.returncode == 0 and output.read_text().strip() == "hello"
