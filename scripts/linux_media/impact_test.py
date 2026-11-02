"""One real 7-J development acceptance run; never enables the web dispatch gate."""

import ipaddress
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from publication import prepare

from honeycomb_studio.actions_log import get_actions_log
from honeycomb_studio.cloud_archive import ALLOWED, ReleaseArchive
from honeycomb_studio.cloud_github import Github
from honeycomb_studio.cloud_release import reserve_release
from honeycomb_studio.data import manifest
from honeycomb_studio.engine import ADAPTERS, Engine
from honeycomb_studio.models import BatchSpec, digest, expand
from honeycomb_studio.store import Store, write_json


class ParallelSmokeEngine(Engine):
    """Align two native solver commands for bounded development acceptance only."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.barrier = threading.Barrier(2)
        self.command_intervals = {}

    def _monitor(self, r, a, phase, args, spool=None):
        if phase == "solving" and args is not None:
            self.barrier.wait(timeout=300)
            start = time.time()
            try:
                return super()._monitor(r, a, phase, args, spool)
            finally:
                self.command_intervals[r["id"]] = {"start": start, "end": time.time()}
        return super()._monitor(r, a, phase, args, spool)

def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True)


def parallel_smoke_input(requested):
    effective = json.loads(json.dumps(requested))
    effective.update(name="SMOKE ONLY - two native delta-angle jobs", data_profile="smoke",
                     execution_mode="parallel", max_parallel_runs=2, max_runs=2,
                     sampling="grid", designs=[], render_images=False, runtime_budget_minutes=30,
                     axes=[{"parameter": "reentrant_delta_deg", "values": [20, 30]}])
    effective["model"].update(cpus=2, reentrant_geometry="angle", duration=.00002,
                              field_intervals=2, history_intervals=10, mesh_preset="quick")
    spec = BatchSpec.model_validate(effective)
    if len(expand(spec)) != 2:
        raise ValueError("Native parallel smoke requires exactly two distinct validated runs")
    return effective


def main(parallel_smoke=False):
    root = Path.cwd()
    guard_minutes = 30 if parallel_smoke else 285
    output = Path(os.environ["RUNNER_TEMP"]) / "honeycomb-impact"
    output.mkdir()
    endpoint = os.environ["ABAQUS_LICENSE_ENDPOINT"]
    match = re.fullmatch(r"(\d{1,5})@([0-9.]+)", endpoint)
    if not match:
        raise ValueError("Expected private IPv4 license endpoint")
    manager, host = match.groups()
    ipaddress.IPv4Address(host)
    vendor = int(os.environ["ABAQUS_VENDOR_PORT"])
    if not all(1 <= int(p) <= 65535 for p in (manager, vendor)):
        raise ValueError("Invalid private license port")
    print("::add-mask::" + host, flush=True)
    private = Path(os.environ["RUNNER_TEMP"]) / "impact-private"
    private.mkdir(mode=0o700)
    config = private / "abaqus_v6.env"
    cpus = 2 if parallel_smoke else 4
    config.write_text(
        "license_server_type=FLEXNET\nabaquslm_license_file="
        + repr(endpoint)
        + "\nmp_mode=THREADS\nparallel=DOMAIN\ndomains=" + str(cpus) + "\n"
    )
    os.environ.update(
        HONEYCOMB_IMPACT_ROOT=str(output),
        HONEYCOMB_LICENSE_HOST=host,
        HONEYCOMB_ADAPTERS=str(ADAPTERS),
        HONEYCOMB_LICENSE_CONFIG=str(config),
        HONEYCOMB_SOLVER_CPUS=str(cpus),
        HONEYCOMB_SOLVER_MEMORY="5g" if parallel_smoke else "11g",
    )
    wrapper = root / "scripts/linux_media/abaqus_container.py"
    wrapper.chmod(0o755)
    requested = json.loads((root / "examples/reentrant-perimeter-7J.json").read_text(encoding="utf-8"))
    write_json(output / "original-requested-input.json", requested)
    effective = json.loads(json.dumps(requested))
    effective["model"]["cpus"] = 4
    effective.update(runtime_budget_minutes=285)
    if parallel_smoke:
        effective = parallel_smoke_input(requested)
    spec = BatchSpec.model_validate(effective)
    expand(spec)
    logger = get_actions_log()
    if logger:
        if parallel_smoke:
            logger.emit("PLAN", "KIỂM TRA SMOKE NGẮN | Hai góc lõi, mỗi mô hình 2 CPU, thời gian vật lý 20 micro-giây; không phải kết quả nghiên cứu đầy đủ.")
        else:
            logger.emit("PLAN", "MÔ PHỎNG THẬT 7 J | Đủ 6 mili-giây thời gian vật lý | 4 CPU | Lưới tham chiếu | Ngàm bốn cạnh | Không mass scaling.")
        logger.emit("PLAN", "Thứ tự: dựng mô hình → kiểm tra input → tính va chạm → đọc ODB → kiểm tra dữ liệu → tạo hình/báo cáo → tải lên và xác minh checksum.")
    write_json(
        output / "execution-adjustments.json",
        {
            "cpus": {"requested": requested["model"]["cpus"], "effective": cpus},
            "parallel_mode": "threads",
            "domains": cpus,
            "render_images": not parallel_smoke,
            "notes": "Explicitly shortened, quick-mesh parallel environment smoke; not research data" if parallel_smoke else "Original model, extraction and rendering settings retained; only CPU allocation and wall-clock budget adjusted.",
            "physics_changed": parallel_smoke,
            "profile": "parallel_smoke_not_research" if parallel_smoke else "research",
            "smoke_overrides": effective if parallel_smoke else None,
            "solver_budget_minutes": guard_minutes,
        },
    )
    network = "honeycomb-impact"
    subnet = "172.29.231.0/24"
    drop = ["-s", subnet, "-j", "DROP"]
    allow = [
        "-s",
        subnet,
        "-d",
        host,
        "-p",
        "tcp",
        "-m",
        "multiport",
        "--dports",
        manager + "," + str(vendor),
        "-j",
        "ACCEPT",
    ]
    created = dropped = input_dropped = allowed = False
    engine = store = None
    receipt = {
        "kind": "linux-parallel-angle-smoke" if parallel_smoke else "linux-7j-impact-acceptance",
        "workflow_run_id": os.environ["GITHUB_RUN_ID"],
        "source_commit": os.environ["GITHUB_SHA"],
        "solver_success": False,
        "production_runtime_qualified": False,
        "input_hash": digest(effective),
    }
    try:
        run("docker", "network", "create", "--subnet", subnet, network)
        created = True
        run("sudo", "iptables", "-I", "DOCKER-USER", "1", *drop)
        dropped = True
        run("sudo", "iptables", "-I", "INPUT", "1", *drop)
        input_dropped = True
        run("sudo", "iptables", "-I", "DOCKER-USER", "1", *allow)
        allowed = True
        store = Store(output)
        batch = store.create(spec)
        engine = (ParallelSmokeEngine if parallel_smoke else Engine)(store, abaqus=str(wrapper), fake=False)
        engine.runtime_fingerprint = "abaqus2020-centos7-2threads-parallel-smoke" if parallel_smoke else "abaqus2020-centos7-4threads-impact-acceptance"
        engine.control(batch["id"], "start")
        engine.start_worker()
        started = time.monotonic()
        while True:
            all_runs = store.list("runs", batch["id"])
            current = all_runs[0]
            phase = current["status"]
            progress = current.get("progress", {})
            logger = get_actions_log()
            if logger:
                logger.runs(all_runs, scope="trình gọi Docker (không phải RAM solver)")
                logger.resources(output, containers=True)
            else:
                print(
                    json.dumps(
                        {
                            "phase": phase,
                            "elapsed_minutes": round((time.monotonic() - started) / 60, 2),
                            "progress": progress,
                        },
                        default=str,
                    ),
                    flush=True,
                )
            if all(r["status"] in ("completed", "review", "failed", "interrupted") for r in all_runs):
                receipt.update(
                    status=phase,
                    summary=current.get("summary"),
                    quality=current.get("quality"),
                    error=current.get("error"),
                )
                if current["attempts"]:
                    attempt = Path(current["attempts"][-1]["path"])
                    receipt["solver_success"] = (attempt / "solver-complete.json").exists()
                if parallel_smoke:
                    intervals = list(engine.command_intervals.values())
                    overlap = min(i["end"] for i in intervals) - max(i["start"] for i in intervals) if len(intervals) == 2 else 0
                    success = len(all_runs) == 2 and overlap > 0 and all(
                        r["attempts"] and (Path(r["attempts"][-1]["path"]) / "solver-complete.json").exists()
                        and r["status"] == "review" for r in all_runs)
                    receipt.update(status="review" if success else "failed", solver_success=success,
                                   profile="parallel_smoke_not_research", ml_eligible=False,
                                   solver_command_intervals=engine.command_intervals,
                                   solver_command_overlap_seconds=max(0, overlap),
                                   note="Command lifetimes overlap; not proof of exact integration-kernel overlap or full-study speedup",
                                   runs=all_runs)
                break
            b = store.get("batches", batch["id"])
            if b["status"] == "paused":
                raise RuntimeError(b.get("resource_error", "Batch paused"))
            if time.monotonic() - started > guard_minutes * 60:
                engine.control(batch["id"], "stop")
                raise RuntimeError("Acceptance budget exceeded; full physics duration was not shortened")
            time.sleep(10 if parallel_smoke else 45)
    except Exception as exc:
        receipt["error"] = str(exc).replace(endpoint, "<private-endpoint>").replace(host, "<private-host>")
        logger = get_actions_log()
        if logger:
            logger.failure(exc, "Native acceptance", "artifact: logs/checking.log, logs/solving.log")
        raise
    finally:
        if engine is not None:
            engine.shutdown.set()
            engine.wake.set()
            if engine.worker:
                engine.worker.join(timeout=30)
        # Exact label applies only to disposable containers started by this adapter.
        ids = run("docker", "ps", "-aq", "--filter", "label=honeycomb.impact=true").stdout.split()
        if ids:
            run("docker", "rm", "-f", *ids)
        config.unlink(missing_ok=True)
        for chain, rule, exists in [
            ("DOCKER-USER", allow, allowed),
            ("DOCKER-USER", drop, dropped),
            ("INPUT", drop, input_dropped),
        ]:
            if exists:
                run("sudo", "iptables", "-D", chain, *rule)
        if created:
            run("docker", "network", "rm", network)
        if store is not None:
            store.db.close()
        for path in output.rglob("*"):
            if path.is_file() and path.suffix in (".json", ".log", ".dat", ".msg", ".sta", ".txt"):
                text = path.read_text(errors="replace")
                path.write_text(text.replace(endpoint, "<private-endpoint>").replace(host, "<private-host>"))
        for inventory in output.rglob("artifact-manifest.json"):
            metadata = json.loads(inventory.read_text()).get("metadata", {})
            metadata["public_text_redaction"] = (
                "Private license endpoint/host removed; original binary results unchanged"
            )
            manifest(inventory.parent, metadata)
        write_json(output / "impact-receipt.json", receipt)
        Path("output").mkdir(exist_ok=True)
        shutil.copyfile(output / "impact-receipt.json", "output/impact-receipt.json")

    if receipt.get("status") not in ("completed", "review"):
        logger = get_actions_log()
        if logger:
            logger.failure(receipt.get("error") or "Solver không hoàn tất", receipt.get("status"), "artifact: impact-receipt.json và logs của attempt")
        raise RuntimeError("Impact acceptance did not finish; real diagnostics retained")


def reserve(parallel_smoke=False):
    return reserve_release(
        Github(token=os.environ["GITHUB_TOKEN"]),
        tag=("linux-parallel-angle-smoke-" if parallel_smoke else "linux-impact-7j-") + os.environ["GITHUB_RUN_ID"],
        sha=os.environ["GITHUB_SHA"],
        name="Native parallel delta-angle SMOKE ONLY" if parallel_smoke else "Linux 7 J re-entrant perimeter test",
    )


def publish():
    """Archive actual outputs, including partial outputs, without certifying them as complete."""
    output = Path(os.environ["RUNNER_TEMP"]) / "honeycomb-impact"
    if not output.exists():
        return
    receipt = json.loads((output / "impact-receipt.json").read_text())
    github = Github(token=os.environ["GITHUB_TOKEN"])
    github.client.timeout = 300
    release = reserve(receipt["kind"] == "linux-parallel-angle-smoke")
    # Draft asset URLs use an untagged slug. Publish before recording download URLs.
    release = github.repo("PATCH", f"/releases/{release['id']}", {"draft": False,
                "body": "Uploading native outputs; completeness is not established until the final archive manifest exists. Research quality is separate."})
    archive = ReleaseArchive(github, release["id"])
    # Thousands of small reduction records must not exhaust Release asset limits.
    # Large binaries are hard-linked into this view; only small records are packed.
    with tempfile.TemporaryDirectory(
        dir=os.environ["RUNNER_TEMP"], prefix="impact-publication-"
    ) as temporary:
        publication = Path(temporary)
        prepare(output, publication)
        ALLOWED.add(".tar")
        archive.publish(
            publication, attempt="impact", complete=receipt.get("status") in ("completed", "review")
        )
    github.repo("PATCH", f"/releases/{release['id']}", {"draft": False,
                "body": "Real native outputs. Read impact-artifact-manifest.json and impact-receipt.json; review results are not certified."})
    print("Results release: " + release["html_url"], flush=True)
    write_json(Path("output/impact-release.json"), {"url": release["html_url"]})


if __name__ == "__main__":
    import sys

    if "--reserve" in sys.argv:
        reserve(parallel_smoke="--parallel-smoke" in sys.argv)
    elif "--publish" in sys.argv:
        publish()
    else:
        main(parallel_smoke="--parallel-smoke" in sys.argv)
