"""Distributed control-plane tests; fixtures do not claim native solver execution."""

from copy import deepcopy

import pytest

from honeycomb_studio.cloud_matrix import (
    ShardCatalog,
    finalize,
    matrix_entries,
    matrix_plan,
    prepare,
    recover,
    workflow_title,
)
from honeycomb_studio.models import BatchSpec, ModelSpec, digest, expand


def batch(mode="parallel"):
    spec = BatchSpec(model=ModelSpec(cpus=4), execution_mode=mode, max_parallel_runs=3,
                     axes=[{"parameter": "energy_J", "values": [5, 7, 9]}]).model_dump()
    return {"id": "a" * 32, "name": "fixture", "profile": "research", "status": "draft",
            "spec": spec, "input_hash": digest(spec)}


def test_parameter_names_show_delta_range_and_each_actual_design():
    spec = BatchSpec(model=ModelSpec(core_topology="reentrant_0", reentrant_geometry="angle", cpus=4,
                                    energy_J=7, duration=.012),
                     axes=[{"parameter": "reentrant_delta_deg", "values": list(range(25, 46))}]).model_dump()
    title = workflow_title(spec)
    assert "δ=25–45° (bước 1°)" in title
    assert "E=7 J" in title and "t=12 ms" in title and "21 lượt" in title
    parent = prepare({**batch(), "spec": spec, "input_hash": digest(spec)}, 123)
    entries = matrix_entries(parent)["include"]
    assert "Lượt 1/21 · δ=25°" in entries[0]["display_name"]
    assert "Lượt 21/21 · δ=45°" in entries[-1]["display_name"]
    for shard in parent["shards"][:-1]:
        shard.update(status="completed", archive_verified=True)
    assert matrix_entries(parent)["include"] == [entries[-1]]


def test_parameter_names_include_other_axes_and_irregular_values():
    parent = prepare(batch(), 123)
    assert "E=5/7/10 J" in workflow_title({**parent["spec"],
                                         "axes": [{"parameter": "energy_J", "values": [5, 7, 10]}]})
    entries = matrix_entries(parent)["include"]
    assert "E=5 J" in entries[0]["display_name"]
    assert "E=9 J" in entries[-1]["display_name"]


def test_twenty_one_runs_stay_in_one_job_with_twenty_parallel_slots():
    original = batch()
    original["spec"].update(max_parallel_runs=20,
                            axes=[{"parameter": "energy_J", "values": list(range(1, 21))}])
    original["input_hash"] = digest(original["spec"])
    parent = prepare(original, 123)
    assert len(parent["shards"]) == 20
    assert parent["execution"]["effective_parallel_runs"] == 20
    original["spec"]["axes"][0]["values"].append(21)
    original["input_hash"] = digest(original["spec"])
    parent = prepare(original, 124)
    assert len(parent["shards"]) == 21
    assert parent["execution"]["effective_parallel_runs"] == 20
    original["spec"]["axes"][0]["values"] = list(range(1, 102))
    with pytest.raises(ValueError):
        matrix_plan(original["spec"])


def test_separate_runners_preserve_four_cpus_and_physics():
    original = batch()
    parent = prepare(original, 123)
    assert parent["execution"]["effective_parallel_runs"] == 3
    assert parent["execution"]["runner_cpus"] == 4
    assert parent["execution"]["architecture"] == "github-job-per-run"
    assert matrix_plan(batch("sequential")["spec"])["effective_parallel_runs"] == 1
    expected = expand(BatchSpec.model_validate(original["spec"]))
    assert len({s["id"] for s in parent["shards"]}) == 3
    for shard, reference in zip(parent["shards"], expected, strict=True):
        runs = expand(BatchSpec.model_validate(shard["spec"]))
        assert len(runs) == 1
        assert runs[0]["resolved"] == reference["resolved"]
        assert runs[0]["resolved"]["cpus"] == 4
        assert runs[0]["resolved"]["duration"] == .006
    assert "shards" not in original


def test_reject_duplicate_claim_wrong_hash_and_oversized_cpu():
    parent = prepare(batch(), 123)
    with pytest.raises(ValueError):
        prepare(parent, 123)
    with pytest.raises(ValueError):
        prepare(parent, 124)
    corrupt = batch()
    corrupt["spec"]["model"]["energy_J"] = 1
    with pytest.raises(ValueError, match="digest"):
        prepare(corrupt, 123)
    oversized = batch()["spec"]
    oversized["model"]["cpus"] = 8
    with pytest.raises(ValueError, match="4 CPU"):
        matrix_plan(oversized)


class MemoryCatalog:
    def __init__(self, parent):
        self.parent = parent

    def get(self, key):
        return deepcopy(self.parent), None

    def update(self, key, transform):
        self.parent = transform(deepcopy(self.parent))
        return deepcopy(self.parent)


def test_sibling_updates_do_not_lose_results_and_cancel_reaches_every_worker():
    catalog = MemoryCatalog(prepare(batch(), 123))
    workers = [ShardCatalog(catalog, "a" * 32, s["id"], 123) for s in catalog.parent["shards"]]
    for worker in workers[:2]:
        identity = worker.child_id
        worker.update("jobs/" + identity, lambda old: {**old, "status": "completed",
                      "runs": [{"id": identity, "status": "completed"}],
                      "archive_verified": True, "release_url": "https://example.test/" + identity})
    assert len(catalog.parent["runs"]) == 2
    assert catalog.parent["status"] == "running"
    assert len(catalog.parent["releases"]) == 2
    catalog.parent["cancel_requested"] = True
    for worker in workers:
        assert worker.get("jobs/" + worker.child_id)[0]["cancel_requested"]
    finished = finalize(catalog.parent, 123)
    assert finished["status"] == "cancelled"
    assert finished["shards"][2]["status"] == "cancelled"
    assert len(finished["runs"]) == 2
    assert not finished["archive_verified"]


def test_finalize_marks_install_failure_and_preserves_verified_success():
    parent = prepare(batch(), 123)
    parent["shards"][0].update(status="review", archive_verified=True)
    result = finalize(parent, 123)
    assert result["status"] == "blocked_environment"
    assert result["shards"][0]["status"] == "review"
    assert result["shards"][1]["status"] == "blocked_environment"
    with pytest.raises(ValueError):
        finalize(parent, 124)
    worker = ShardCatalog(MemoryCatalog(parent), parent["id"], parent["shards"][0]["id"], 124)
    with pytest.raises(ValueError):
        worker.get("jobs/" + worker.child_id)


def test_all_verified_results_complete_batch_with_separate_releases():
    parent = prepare(batch(), 123)
    for shard in parent["shards"]:
        shard.update(status="completed", archive_verified=True)
    result = finalize(parent, 123)
    assert result["status"] == "completed" and result["archive_verified"]


def test_preparation_failure_and_early_cancel_become_terminal_without_shards():
    pending = batch()
    pending["status"] = "dispatching"
    result = finalize(pending, 123)
    assert result["status"] == "blocked_environment" and result["workflow_run_id"] == 123
    pending["cancel_requested"] = True
    assert finalize(pending, 123)["status"] == "cancelled"
    claimed = prepare(batch(), 124)
    with pytest.raises(ValueError, match="own"):
        finalize(claimed, 123)


def test_only_explicitly_audited_review_is_repaired_and_prior_archive_is_retained():
    parent = prepare(batch(), 123)
    for shard in parent['shards']:
        shard.update(status='completed', archive_verified=True, release_url='https://example.test/' + shard['id'])
    parent['shards'][1].update(status='review', history_audit={'passed': False})
    parent = finalize(parent, 123)
    original = deepcopy(parent)
    repaired = recover(parent, 124, repair_indices=[1])
    assert parent == original
    assert repaired['shards'][0] == original['shards'][0]
    assert repaired['shards'][2] == original['shards'][2]
    target = repaired['shards'][1]
    assert target['id'] != original['shards'][1]['id'] and target['status'] == 'draft'
    assert target['spec'] == original['shards'][1]['spec']
    assert target['previous_attempts'] == [original['shards'][1]]
    with pytest.raises(ValueError, match='audit'):
        recover(parent, 124, repair_indices=[0])
    parent['status'] = 'running'
    with pytest.raises(ValueError, match='terminal'):
        recover(parent, 124, repair_indices=[1])
