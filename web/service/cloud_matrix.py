"""One expanded design per hosted runner; atomic parent catalog aggregation."""

from copy import deepcopy
from math import isclose

from .models import BatchSpec, digest, expand

TERMINAL = {"completed", "review", "failed", "archive_failed", "cancelled", "timed_out",
            "blocked_license", "blocked_environment", "blocked_platform_policy"}

LABELS = {"reentrant_delta_deg": ("δ", "°", 1), "energy_J": ("E", " J", 1),
          "duration": ("t", " ms", 1000), "cpus": ("CPU", "", 1),
          "panel": ("Panel", " mm", 1), "foil": ("Lá lõi", " mm", 1),
          "skin": ("Mặt trên", " mm", 1), "core_height": ("Cao lõi", " mm", 1),
          "velocity_m_s": ("v", " m/s", 1), "mesh_preset": ("Lưới", "", 1)}


def parameter_title(runs):
    """Describe actual expanded inputs, including table/LHS and arbitrary axes."""
    models = [run["requested"] for run in runs]
    varying = [key for key in models[0] if any(m[key] != models[0][key] for m in models[1:])]
    context = (["reentrant_delta_deg"] if models[0]["core_topology"].startswith("reentrant") else [])
    context += ["energy_J", "duration", "cpus"]
    labels = []
    for key in dict.fromkeys(varying + context):
        label, unit, scale = LABELS.get(key, (key, "", 1))
        values = list(dict.fromkeys(str(m[key]) for m in models))
        raw = [m[key] for m in models]
        if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in raw):
            numbers = sorted(set(float(v) * scale for v in raw))
            if len(numbers) == 1:
                value = f"{numbers[0]:.6g}{unit}"
            elif len(numbers) > 2 and all(isclose(b - a, numbers[1] - numbers[0], rel_tol=1e-7, abs_tol=1e-9)
                                         for a, b in zip(numbers, numbers[1:], strict=False)):
                value = f"{numbers[0]:.6g}–{numbers[-1]:.6g}{unit} (bước {numbers[1] - numbers[0]:.6g}{unit})"
            else:
                value = "/".join(f"{v:.6g}" for v in numbers[:4]) + unit
                if len(numbers) > 4:
                    value += f"… ({len(numbers)} giá trị)"
        else:
            value = "/".join(values[:3])
            if len(values) > 3:
                value += f"… ({len(values)} giá trị)"
        labels.append(f"{label}={value}")
    return " · ".join(labels)


def workflow_title(spec):
    runs = expand(BatchSpec.model_validate(spec).model_copy(update={"max_runs": 100}))
    return f"{parameter_title(runs)[:170]} · {len(runs)} lượt"


def matrix_entries(parent, *, pending_only=True):
    # Use the original batch to identify varying parameters even when recovery
    # only selects one remaining design.
    reference = expand(BatchSpec.model_validate(parent["spec"]).model_copy(update={"max_runs": 100}))
    varying = [key for key in reference[0]["requested"]
               if any(r["requested"][key] != reference[0]["requested"][key] for r in reference[1:])]
    entries = []
    for shard in parent["shards"]:
        if pending_only and shard["status"] != "draft":
            continue
        model = expand(BatchSpec.model_validate(shard["spec"]))[0]
        requested = model["requested"]
        title = parameter_title([model])
        extras = []
        for key in varying:
            if key not in ("reentrant_delta_deg", "energy_J", "duration", "cpus"):
                label, unit, scale = LABELS.get(key, (key, "", 1))
                value = requested[key]
                value = f"{value * scale:.6g}" if isinstance(value, (int, float)) else str(value)
                extras.append(f"{label}={value}{unit}")
        title = " · ".join(extras + [title])
        entries.append({"child_id": shard["id"], "index": shard["index"], "display_index": shard["index"] + 1,
                        "display_name": f"Lượt {shard['index'] + 1}/{len(parent['shards'])} · {title}"[:240]})
    return {"include": entries}


def matrix_plan(spec):
    spec = BatchSpec.model_validate(spec)
    runs = expand(spec.model_copy(update={"max_runs": 100}))
    if any(r["resolved"]["cpus"] > 4 for r in runs):
        raise ValueError("Mỗi runner cloud có 4 CPU; CPU mỗi lượt phải nằm trong khoảng 1–4.")
    slots = min(len(runs), spec.max_parallel_runs if spec.execution_mode == "parallel" else 1)
    return {"requested_parallel_runs": spec.max_parallel_runs if spec.execution_mode == "parallel" else 1,
            "effective_parallel_runs": slots, "cpu_per_run": runs[0]["resolved"]["cpus"],
            "runner_cpus": 4, "runner_count": len(runs), "architecture": "github-job-per-run",
            "queue_scope": "github-account", "aggregation_scope": "terminal-batch",
            "estimate_only": True,
            "note": "Một lượt = một job/runner 4 CPU. Các đợt dùng chung quota GitHub; slot trống nhận lượt chờ, thứ tự do GitHub quyết định. Giới hạn song song áp dụng riêng mỗi đợt; license có thể làm solver chờ. Tổng hợp khi tất cả lượt trong đợt kết thúc."}


def prepare(old, workflow_id):
    if old.get("cancel_requested") or old["status"] not in ("draft", "dispatching"):
        raise ValueError("Batch cannot be claimed; duplicate dispatches and reruns require a new request ID")
    if old.get("workflow_run_id") and old["workflow_run_id"] != workflow_id:
        raise ValueError("Batch belongs to another workflow")
    if digest(old["spec"]) != old["input_hash"]:
        raise ValueError("Requested input digest does not match the catalog")
    plan = matrix_plan(old["spec"])
    expanded = expand(BatchSpec.model_validate(old["spec"]).model_copy(update={"max_runs": 100}))
    shards = []
    for index, run in enumerate(expanded):
        spec = deepcopy(old["spec"])
        spec.update(model=run["requested"], sampling="grid", axes=[], designs=[], max_runs=1,
                    execution_mode="sequential")
        identity = digest({"parent": old["id"], "index": index})[:32]
        shards.append({"id": identity, "name": old["name"], "profile": old["profile"],
                       "parent_job_id": old["id"], "parent_input_hash": old["input_hash"],
                       "index": index, "status": "draft", "spec": spec, "input_hash": digest(spec)})
    return {**old, "workflow_run_id": workflow_id, "status": "running", "phase": "matrix queued",
            "execution": plan, "shards": shards, "runs": []}


def recover(old, workflow_id, *, repair_indices=()):
    """Retry only interrupted/failed shards, retaining results and attempt history."""
    if old.get("cancel_requested") or old["status"] not in TERMINAL or not old.get("shards"):
        raise ValueError("Recovery requires a terminal matrix job without cancellation")
    if digest(old["spec"]) != old["input_hash"]:
        raise ValueError("Requested input digest does not match the catalog")
    if (not isinstance(repair_indices, (list, tuple)) or
            any(type(i) is not int or not 0 <= i < len(old['shards']) for i in repair_indices)):
        raise ValueError('Repair indices must identify existing matrix designs')
    for index in repair_indices:
        source = next(s for s in old['shards'] if s['index'] == index)
        if source['status'] != 'review' or source.get('history_audit', {}).get('passed') is not False:
            raise ValueError('Reviewed design requires a failed original-history audit before repair')
    shards = []
    for source in old["shards"]:
        shard = deepcopy(source)
        if (shard['index'] in repair_indices or
                shard["status"] not in ("completed", "review") or not shard.get("archive_verified")):
            history = shard.pop("previous_attempts", [])
            history.append(deepcopy(shard))
            shard = {k: shard[k] for k in ("id", "name", "profile", "parent_job_id",
                                           "parent_input_hash", "index", "spec", "input_hash")}
            # Each solver attempt reserves its own immutable source tag. Keep
            # the parent/folder and design index, but never retag old outputs.
            shard["id"] = digest({"parent": old["id"], "index": shard["index"],
                                  "recovery_workflow": workflow_id})[:32]
            shard.update(status="draft", previous_attempts=history)
        shards.append(shard)
    if not any(s["status"] == "draft" for s in shards):
        raise ValueError("No failed shards to recover; collect existing data instead")
    return aggregate({**old, "shards": shards, "workflow_run_id": workflow_id,
                      "recovery_dispatch_pending": False,
                      "previous_workflow_run_id": old["workflow_run_id"]})


def aggregate(parent):
    shards = parent["shards"]
    runs = [{**r, "matrix_index": s["index"], "release_url": s.get("release_url")}
            for s in shards for r in s.get("runs", [])]
    releases = [{"index": s["index"], "url": s["release_url"]} for s in shards if s.get("release_url")]
    statuses = [s["status"] for s in shards]
    status = "running"
    if all(s in TERMINAL for s in statuses):
        status = next((s for s in statuses if s not in ("completed", "review")),
                      "review" if "review" in statuses else "completed")
    return {**parent, "runs": runs, "releases": releases, "status": status,
            "release_url": releases[0]["url"] if releases else None,
            "archive_verified": all(s.get("archive_verified", False) for s in shards),
            "phase": ", ".join(f"{s['index'] + 1}: {s.get('phase', s['status'])}" for s in shards)}


class ShardCatalog:
    """Present one shard to the existing single-run worker, merging via parent CAS.

    Cancellation is inherited from the parent; writes never replace sibling data.
    Child records stay embedded so the public job index has one row per batch.
    """

    def __init__(self, catalog, parent_id, child_id, workflow_id):
        self.catalog, self.key = catalog, "jobs/" + parent_id
        self.child_id, self.workflow_id = child_id, workflow_id

    def _child(self, parent):
        if parent["workflow_run_id"] != self.workflow_id:
            raise ValueError("Matrix worker does not own this workflow")
        return next(s for s in parent["shards"] if s["id"] == self.child_id)

    def get(self, key):
        if key != "jobs/" + self.child_id:
            raise ValueError("Shard cannot access another catalog record")
        parent, sha = self.catalog.get(self.key)
        return {**self._child(parent), "cancel_requested": parent.get("cancel_requested", False)}, sha

    def update(self, key, transform):
        if key == "index":
            return None  # The underlying parent CAS maintains its public index.
        if key != "jobs/" + self.child_id:
            raise ValueError("Shard cannot modify another catalog record")

        def merge(parent):
            child = {**self._child(parent), "cancel_requested": parent.get("cancel_requested", False)}
            updated = transform(deepcopy(child))
            return aggregate({**parent, "shards": [updated if s["id"] == self.child_id else s
                                                   for s in parent["shards"]]})

        parent = self.catalog.update(self.key, merge)
        return self._child(parent)


def finalize(old, workflow_id):
    if not old.get("workflow_run_id") and old["status"] in ("draft", "dispatching"):
        # Preparation can fail before the matrix was created (including qualification).
        return {**old, "workflow_run_id": workflow_id,
                "status": "cancelled" if old.get("cancel_requested") else "blocked_environment",
                "error": "Preparation ended before runners were admitted; inspect the prepare job logs.",
                "archive_verified": False}
    if old.get("workflow_run_id") != workflow_id:
        raise ValueError("Finalizer does not own this batch")
    shards = [{**s, "status": "cancelled" if old.get("cancel_requested") else "blocked_environment",
               "error": "Runner ended before a durable final result; inspect its Actions logs."}
              if s["status"] not in TERMINAL else s for s in old["shards"]]
    return aggregate({**old, "shards": shards})
