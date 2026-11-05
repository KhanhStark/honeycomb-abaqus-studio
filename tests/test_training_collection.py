import csv
import json
from copy import deepcopy
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from honeycomb_studio.models import Axis, BatchSpec
from honeycomb_studio.store import Store
from honeycomb_studio.training_collection import build_collection, collect_runs, training_paths


def test_global_dedup_quality_selection_and_design_splits(tmp_path):
    store = Store(tmp_path / "store")
    sources = []
    all_runs = []
    for i, energy in enumerate((3, 7, 3)):
        batch = store.create(BatchSpec(axes=[Axis(parameter="energy_J", values=[energy])]))
        runs = store.list("runs", batch["id"])
        for run in runs:
            run.update(status="completed", summary={"SEA_J_kg": 12, "peak_raw_contact_force_N": 150},
                       quality={"ml_eligible": True})
        sources.append({"job_id": str(i), "job_name": "Tên bài " + str(i), "runs": runs})
        all_runs.extend(runs)
    excluded = deepcopy(all_runs[0])
    excluded.update(id="smoke", status="review", quality={"ml_eligible": False,
                    "physical_validation": "environment_smoke_only"})
    sources.append({"job_id": "smoke", "runs": [excluded]})
    out = tmp_path / "collection"
    result = build_collection(sources, out)
    assert result["samples"] == 2 and result["runs"] == 4
    rows = pq.read_table(out / "01_training/samples.parquet").to_pylist()
    assert {r["input.energy_J"] for r in rows} == {3, 7}
    assert len({r["design_id"] for r in rows}) == 1
    assert len({r["split"] for r in rows}) == 1
    audit = list(csv.DictReader((out / "02_audit/run-selection.csv").open(encoding="utf-8-sig")))
    assert len(audit) == 4
    assert any(r["reason"] == "Trùng đầu vào" for r in audit)
    assert "Smoke" in audit[-1]["reason"]
    contract = json.loads((out / "02_audit/input-output-contract.json").read_text(encoding="utf-8"))
    assert "input.energy_J" in contract["X"]
    assert "peak_raw_contact_force_N" in contract["y_candidates"]
    assert "run_id" not in contract["X"]
    assert list(out.glob("03_simulations/job--ten-bai-0--0/**/input/resolved.json"))
    assert list(out.glob("03_simulations/job--ten-bai-0--0/**/output/summary.json"))
    results = pq.read_table(out / "05_all_results/simulation-results.parquet").to_pylist()
    assert len(results) == 4
    assert sum(r["included_in_training"] for r in results) == 2
    assert results[-1]["status"] == "review"
    readiness = json.loads((out / "01_training/readiness.json").read_text(encoding="utf-8"))
    assert readiness["usable_rows_by_target"]["SEA_J_kg"] == 2
    assert readiness["evaluation_splits_available"] is False


def test_empty_collection_is_explicit_and_auditable(tmp_path):
    out = tmp_path / "empty"
    result = build_collection([{"job_id": "a", "runs": [], "excluded_reason": "Chưa chạy"}], out)
    assert result["samples"] == 0 and result["unavailable_sources"] == 1
    assert pq.read_table(out / "01_training/samples.parquet").num_rows == 0
    assert len((out / "01_training/samples.csv").read_text(encoding="utf-8-sig").splitlines()) == 1
    assert (out / "01_training/FIELD_DESCRIPTIONS.md").is_file()
    assert json.loads((out / "02_audit/source-jobs.json").read_text())[0]["excluded_reason"]


def test_rebase_archived_paths_and_preserve_history(tmp_path):
    store = Store(tmp_path / "archived")
    batch = store.create(BatchSpec())
    original = store.list("runs", batch["id"])[0]
    run_dir = Path(original["path"])
    original.update(status="completed", summary={"SEA_J_kg": 12}, quality={"ml_eligible": True},
                    attempts=[{"number": 1, "path": "/old/runner/attempts/001"}])
    store.save("runs", original)
    curves = run_dir / "attempts/001/extracted"
    curves.mkdir(parents=True)
    (curves / "impact_history.csv").write_text("time_s,contact_force_N\n0,0\n1,10\n")
    runs = collect_runs(store.root)
    assert runs[0]["attempts"][0]["path"] == str(run_dir / "attempts/001")
    out = tmp_path / "collection"
    build_collection([{"job_id": "a", "runs": runs}], out)
    assert (out / "01_training/curves" / original["id"] / "impact_history.csv").is_file()
    assert list(out.glob("03_simulations/**/output/attempt-001/impact_history.csv"))
    runs.append(deepcopy(runs[0]))
    with pytest.raises(ValueError, match="Duplicate run"):
        build_collection([{"job_id": "a", "runs": runs}], tmp_path / "duplicate")


def test_training_subset_excludes_heavy_fields():
    base = "projects/p/batches/b/runs/r/"
    names = ["run.json", "resolved-input.json", "attempts/001/extracted/impact_history.parquet",
             "attempts/001/raw/job.odb", "attempts/001/extracted/fields/part-001.parquet"]
    assert training_paths({"files": [{"path": base + p} for p in names]}) == [base + p for p in names[:3]]


def test_post_publication_history_rejection_excludes_originally_accepted_archive(tmp_path):
    from honeycomb_studio.training_collection import apply_history_audit
    store = Store(tmp_path / 'archive')
    batch = store.create(BatchSpec())
    run = store.list('runs', batch['id'])[0]
    run.update(status='completed', quality={'ml_eligible': True}, summary={'SEA_J_kg': 12})
    store.save('runs', run)
    original = (Path(run['path']) / 'run.json').read_bytes()
    runs = collect_runs(store.root)
    apply_history_audit(runs, {'passed': False, 'issues': [{'gap_count': 1}]})
    result = build_collection([{'job_id': 'a', 'runs': runs}], tmp_path / 'collection')
    assert result['samples'] == 0 and result['runs'] == 1
    assert runs[0]['original_publication_quality']['ml_eligible'] is True
    assert runs[0]['quality']['ml_eligible'] is False and runs[0]['status'] == 'review'
    assert (Path(run['path']) / 'run.json').read_bytes() == original
    store.db.close()
