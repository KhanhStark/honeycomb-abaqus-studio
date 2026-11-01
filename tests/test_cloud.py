import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient

from honeycomb_studio.cloud_api import create_app
from honeycomb_studio.cloud_archive import ReleaseArchive, parts
from honeycomb_studio.cloud_runtime import qualification


def test_public_contract_and_unauthorized_write():
    with TestClient(create_app()) as client:
        template = client.get("/api/template").json()
        spec = template["spec"]
        result = client.post("/api/preview", json=spec)
        assert result.status_code == 200
        assert result.json()["runs"][0]["index"] == 1
        assert result.json()["runs"][0]["resolved"]["clamp_mode"] == "perimeter"
        assert client.post("/api/jobs", json={"request_id": "a" * 32, "spec": spec}).status_code == 403
        assert client.post("/api/jobs/" + "a" * 32 + "/dispatch", json={}).status_code == 403
        assert client.get("/api/status").json()["qualified_linux_solver"] is False
        assert client.post("/api/training/collect", json={}).status_code == 403
        assert client.get("/api/status").json()["max_runs"] == 100
        spec.update(execution_mode="parallel", max_parallel_runs=20,
                    axes=[{"parameter": "energy_J", "values": list(range(1, 21))}])
        preview = client.post("/api/preview", json=spec)
        assert preview.status_code == 200
        assert preview.json()["count"] == 20
        assert preview.json()["execution"]["effective_parallel_runs"] == 20
        spec["axes"][0]["values"].append(21)
        assert client.post("/api/preview", json=spec).json()["count"] == 21
        spec["axes"][0]["values"] = list(range(1, 102))
        assert client.post("/api/preview", json=spec).status_code == 422


def test_health_identifies_the_deployed_revision(monkeypatch):
    monkeypatch.setenv("VERCEL_GIT_COMMIT_SHA", "a" * 40)
    with TestClient(create_app()) as client:
        assert client.get("/api/health").json()["revision"] == "a" * 40
    monkeypatch.delenv("VERCEL_GIT_COMMIT_SHA")
    with TestClient(create_app()) as client:
        assert client.get("/api/health").json()["revision"] is None


def test_geometry_and_body_bounds():
    with TestClient(create_app()) as client:
        model = client.get("/api/template").json()["spec"]["model"]
        shape = client.post("/api/geometry", json=model)
        assert shape.status_code == 200
        assert len(shape.json()["walls"]) == 234
        model.update(phase_x=1e9)
        assert client.post("/api/geometry", json=model).status_code == 422
        assert client.post("/api/preview", content=b" " * 262145).status_code == 413


def test_fake_environment_receipt_is_insufficient(tmp_path, monkeypatch):
    monkeypatch.setenv("ABAQUS_RUNTIME_RECEIPT_URL", "https://example.com/fake")
    lock = tmp_path / "runtime-lock.json"
    lock.write_text(json.dumps({"smoke_receipt": {"solver_success": True}}))
    _, reasons = qualification(lock)
    assert {"blocked_environment", "blocked_license"} <= {r["status"] for r in reasons}


def test_bounded_archive_roundtrip_and_manifest_last(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    raw = b"actual ODB placeholder for transport testing only" * 4
    (source / "model.odb").write_bytes(raw)
    temporary = tmp_path / "temp"
    temporary.mkdir()
    chunks = []
    for part in parts(source / "model.odb", temporary, 17):
        chunks.append(part["path"].read_bytes())
        assert part["bytes"] <= 17
    assert b"".join(chunks) == raw
    assert list(temporary.iterdir()) == []

    class Recorder(ReleaseArchive):
        def __init__(self):
            self.limit = 17
            self.uploads = []

        def upload(self, path, name):
            self.uploads.append((name, path.read_bytes()))
            return {
                "url": "https://github.com/test/" + name,
                "bytes": path.stat().st_size,
                "digest": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(),
            }

    archive = Recorder()
    manifest = archive.publish(source, attempt="test", complete=True)
    assert archive.uploads[-1][0] == "test-artifact-manifest.json"
    assert manifest["complete"] is True
    odb = next(f for f in manifest["files"] if f["path"] == "model.odb")
    assert odb["sha256"] == hashlib.sha256(raw).hexdigest()
    previous_parts = [name for name, _ in archive.uploads if name.endswith(".part")]
    archive.uploads.clear()
    archive.publish(source, attempt="test", complete=False, checkpoint="run-one")
    assert archive.uploads[-1][0] == "test-checkpoint-run-one-artifact-manifest.json"
    assert [name for name, _ in archive.uploads if name.endswith(".part")] == previous_parts


def test_packaged_service_matches_canonical():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "web/service/source-manifest.json").read_text())
    for name, checksum in manifest.items():
        assert (root / "web/service" / name).read_bytes() == (
            root / "src/honeycomb_studio" / name
        ).read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256((root / "web/service" / name).read_bytes()).hexdigest() == checksum


def test_owner_csrf_idempotency_and_qualification(monkeypatch):
    import base64

    from itsdangerous import TimestampSigner

    from honeycomb_studio import cloud_api

    class Memory:
        def __init__(self, github):
            self.data = {}

        def get(self, key):
            return self.data.get(key), None

        def update(self, key, transform):
            self.data[key] = transform(self.data.get(key))
            return self.data[key]

        def jobs(self):
            return self.data.get("index", {}).get("jobs", [])

    class Connected:
        configured = True

        def repo(self, method, path, body):
            assert method == "POST"
            assert path == "/actions/workflows/abaqus-linux.yml/dispatches"
            assert body["ref"] == "main" and body["inputs"]["job_id"] == "b" * 32
            assert "E=7 J" in body["inputs"]["job_name"]
            assert "t=12 ms" in body["inputs"]["job_name"]
            assert "CPU=4" in body["inputs"]["job_name"]

    monkeypatch.setattr(cloud_api, "Catalog", Memory)
    monkeypatch.setenv("WEB_SESSION_SECRET", "test-secret-only")
    monkeypatch.setenv("WEB_LOCAL_HTTP", "1")
    session = base64.b64encode(json.dumps({"user_id": cloud_api.OWNER_ID, "csrf": "test-csrf"}).encode())
    with TestClient(create_app(Connected())) as client:
        client.cookies.set("session", TimestampSigner("test-secret-only").sign(session).decode())
        spec = client.get("/api/template").json()["spec"]
        body = {"request_id": "b" * 32, "profile": "research", "spec": spec}
        assert client.post("/api/jobs", json=body).status_code == 403
        headers = {"X-Honeycomb-CSRF": "test-csrf"}
        first = client.post("/api/jobs", json=body, headers=headers)
        assert first.status_code == 201
        assert client.post("/api/jobs", json=body, headers=headers).json() == first.json()
        body["spec"]["name"] = "Changed payload"
        assert client.post("/api/jobs", json=body, headers=headers).status_code == 409
        dispatched = client.post("/api/jobs/" + "b" * 32 + "/dispatch", json={}, headers=headers)
        assert dispatched.status_code == 200
        assert dispatched.json()["status"] == "dispatching"
        assert client.post("/api/jobs/" + "b" * 32 + "/dispatch", json={}, headers=headers).status_code == 409
        assert client.post("/api/jobs/" + "b" * 32 + "/cancel", json={}, headers=headers).status_code == 200
        assert client.get("/api/jobs/" + "b" * 32).json()["cancel_requested"] is True


def test_native_execution_does_not_fabricate_official_qualification(monkeypatch):
    from honeycomb_studio import cloud_runtime

    with TestClient(create_app()) as client:
        status = client.get("/api/status").json()
        assert status["gates"] == []
        assert status["execution_runtime"]["mode"] == "native_container"
        assert status["execution_runtime"]["production_runtime_qualified"] is False
        assert status["qualified_linux_solver"] is False
        assert status["qualification_gates"]
    monkeypatch.setattr(cloud_runtime, "technical_evidence", lambda: {"solver_success": True})
    assert cloud_runtime.execution_runtime()[1][0]["status"] == "blocked_environment"


def test_local_deadline_stops_solver_when_github_is_unreachable(tmp_path):
    from honeycomb_studio.cloud_progress import Progress
    from honeycomb_studio.models import BatchSpec
    from honeycomb_studio.store import Store

    store = Store(tmp_path)
    batch = store.create(BatchSpec())

    class Offline:
        def get(self, key):
            progress.done.set()
            raise ConnectionError("network unavailable")

    progress = Progress(None, Offline(), "fixture", store, batch["id"], 0)
    progress.loop()
    saved = store.get("batches", batch["id"])
    assert saved["pause_requested"] and saved["stop_immediately"]
    assert progress.stop_reason == "timed_out"
    store.db.close()


def test_preparation_counts_towards_total_job_budget():
    import pytest

    from honeycomb_studio.cloud_progress import execution_deadline

    # One hour of install/download leaves 255 minutes, not another 315 minutes.
    assert execution_deadline(1000, wall_time=4600, monotonic_time=50) == 50 + 255 * 60
    with pytest.raises(RuntimeError, match="timed_out"):
        execution_deadline(1000, wall_time=1000 + 315 * 60, monotonic_time=50)


def test_malformed_lock_fails_closed_and_checkout_without_entitlement_is_blocked(tmp_path, monkeypatch):
    monkeypatch.delenv("PLATFORM_POLICY_EVIDENCE_URL", raising=False)
    lock = tmp_path / "runtime-lock.json"
    for data in ([], {"smoke_receipt": None, "license_receipt": None},
                 {"license_receipt": {"features": [{"not": "a feature"}]}}):
        lock.write_text(json.dumps(data))
        assert len(qualification(lock)[1]) == 3
    lock.write_text(json.dumps({
        "release": "Abaqus 2020", "python": "2.7.15", "image_digest": "sha256:" + "a" * 64,
        "installer_sha256": "b" * 64, "media_publisher_authenticity_verified": True,
        "smoke_receipt": {"solver_success": True, "platform": "linux", "odb_reopened": True,
                          "evidence_url": "https://github.com/example/observed"},
        "license_receipt": {"linux_checkout": True, "features": ["cae", "explicit"],
                            "evidence_url": "https://github.com/example/observed"},
    }))
    assert {r["status"] for r in qualification(lock)[1]} == {"blocked_license", "blocked_platform_policy"}


def test_failed_upload_never_publishes_complete_manifest(tmp_path):
    import pytest

    (tmp_path / "data.odb").write_bytes(b"not a solver result: transport test fixture")

    class Broken(ReleaseArchive):
        limit = 4

        def __init__(self):
            self.names = []

        def upload(self, path, name):
            self.names.append(name)
            raise ConnectionError("interrupted upload")

    archive = Broken()
    with pytest.raises(ConnectionError):
        archive.publish(tmp_path, attempt="failed", complete=True)
    assert not any("manifest" in name for name in archive.names)


def test_production_entrypoint_starts_without_static_directory(tmp_path, monkeypatch):
    import runpy

    root = Path(__file__).resolve().parents[1]
    entrypoint = tmp_path / "app.py"
    entrypoint.write_bytes((root / "web/app.py").read_bytes())
    monkeypatch.syspath_prepend(str(root / "web"))
    monkeypatch.chdir(tmp_path)
    namespace = runpy.run_path(str(entrypoint))
    with TestClient(namespace["app"]) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["worker_started_in_web"] is False
