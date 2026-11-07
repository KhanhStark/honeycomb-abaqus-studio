from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import uuid
import zipfile
from itertools import chain
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from .field_storage import remote_reductions
from .models import digest
from .quantities import describe_column
from .research import FEATURES, PROVENANCE, TARGETS, field_reduction, merge_statistics
from .store import now, write_json


def safe_name(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", text)[:100]


def consume_spool(directory: Path, field_sink=None) -> int:
    count = 0
    policy = directory / "export-policy.json"
    compact = policy.exists() and not json.loads(policy.read_text(encoding="utf-8"))["full_fields"]
    for ready in sorted((directory / "spool").glob("*.ready")):
        meta = json.loads(ready.read_text())
        source = ready.parent / meta["npz"]
        with np.load(source, allow_pickle=False) as arrays:
            if compact and meta["kind"] == "field":
                write_json(
                    directory / "reduced-fields" / ("part-%08d.json" % meta["sequence"]),
                    field_reduction(arrays, meta),
                )
                arrays.close()
                source.unlink()
                ready.unlink()
                count += 1
                continue
            cols = {}
            for key in arrays.files:
                arr = arrays[key]
                if key == "data":
                    matrix = arr.reshape((len(arr), -1))
                    valid = np.isfinite(matrix)
                    counts = valid.sum(axis=0)
                    mins = np.where(valid, matrix, np.inf).min(axis=0)
                    maxs = np.where(valid, matrix, -np.inf).max(axis=0)
                    sums = np.where(valid, matrix, 0.0).sum(axis=0)
                    meta["statistics"] = {
                        "finite_count": counts.tolist(),
                        "min": [float(v) if math.isfinite(v) else None for v in mins],
                        "max": [float(v) if math.isfinite(v) else None for v in maxs],
                        "sum": [float(v) if math.isfinite(v) else None for v in sums],
                        "rows": len(matrix),
                    }
                cols[key] = (
                    pa.FixedSizeListArray.from_arrays(pa.array(arr.reshape(-1)), arr.shape[1])
                    if arr.ndim == 2
                    else pa.array(arr)
                )
            if meta["kind"] == "field":
                path = (
                    directory
                    / "fields"
                    / safe_name(meta["step"])
                    / safe_name(meta["field"])
                    / ("frame=%05d" % meta["frame"])
                )
            else:
                path = directory / "mesh" / safe_name(meta["instance"]) / meta["kind"]
            path.mkdir(parents=True, exist_ok=True)
            table = pa.table(cols).replace_schema_metadata({b"honeycomb": json.dumps(meta).encode()})
            dest = path / ("part-%08d.parquet" % meta["sequence"])
            temp = dest.with_suffix(".tmp")
            pq.write_table(table, temp, compression="zstd")
            with pq.ParquetFile(temp) as check:
                if check.metadata.num_rows != table.num_rows:
                    raise ValueError("Parquet row count mismatch")
            temp.replace(dest)
            if field_sink is not None and meta["kind"] == "field":
                field_sink(dest, field_reduction(arrays, meta))
        source.unlink()
        ready.unlink()
        count += 1
    return count


def history_continuity(history: list[dict], spec: dict) -> dict:
    """Check original ODB samples; never certify interpolated recovery gaps."""
    interval = spec["duration"] / spec["history_intervals"]
    # Output is recorded at the next solver increment, with small time jitter.
    tolerance = interval * 1.5
    issues = []
    for channel in history:
        label = {k: channel.get(k) for k in ("step", "region", "variable")}
        values = np.asarray(channel["data"], dtype=float)
        if values.ndim != 2 or values.shape[1] != 2 or len(values) < 2 or not np.isfinite(values).all():
            issues.append({**label, "error": "missing or nonfinite samples"})
            continue
        times = values[:, 0]
        gaps = np.diff(times)
        nonincreasing = int(np.count_nonzero(gaps <= 0))
        missing = int(np.count_nonzero(gaps > tolerance))
        coverage = bool(abs(times[0]) <= tolerance and abs(times[-1] - spec["duration"]) <= tolerance)
        if nonincreasing or missing or not coverage:
            issues.append({**label, "gap_count": missing, "max_gap_s": float(gaps.max()),
                           "nonincreasing_count": nonincreasing, "covers_duration": coverage})
    return {"passed": bool(history) and not issues, "channels": len(history),
            "expected_interval_s": interval, "maximum_allowed_gap_s": tolerance, "issues": issues}


def history_summary(
    directory: Path, spec: dict, actual: dict | None = None, checkpoint=None
) -> tuple[dict, list[dict]]:
    history = json.loads((directory / "histories.json").read_text())
    integrity = history_continuity(history, spec)

    def find(var, region_contains=None, optional=False):
        items = [
            h
            for h in history
            if h["variable"] == var and (not region_contains or region_contains in h["region"].upper())
        ]
        if not region_contains and (var.startswith('ALL') or var == 'ETOTAL'):
            items = [h for h in items if h['region'].upper() in ('ASSEMBLY', 'ASSEMBLY ASSEMBLY', 'WHOLE MODEL')]
        if not items:
            if optional:
                return None
            raise ValueError("ODB thiếu history bắt buộc: " + var + " / " + str(region_contains))
        if len(items) != 1:
            raise ValueError("History không duy nhất; không tự đoán region cho " + var)
        return np.asarray(items[0]["data"], dtype=float)

    acc = find("A3", "IMPACTOR")
    vel = find("V3", "IMPACTOR")
    disp = find("U3", "IMPACTOR")
    time = acc[:, 0]

    def sample(series):
        return (
            np.interp(time, series[:, 0], series[:, 1]) if series is not None else np.full(len(time), np.nan)
        )

    f = spec["impact_mass"] * (acc[:, 1] + spec["gravity"] * 1000)
    u, v = -sample(disp), sample(vel)
    top, bottom = sample(find("U3", "TOP", True)), sample(find("U3", "BOTTOM", True))
    energies = {
        k: sample(find(k, optional=True)) / 1000
        for k in (
            "ALLKE",
            "ALLIE",
            "ALLAE",
            "ALLPD",
            "ALLSE",
            "ALLVD",
            "ALLWK",
            "ETOTAL",
            "ALLFD",
            "ALLDMD",
            "ALLCD",
        )
    }
    required = ("ALLKE", "ALLIE", "ALLAE", "ALLPD", "ALLSE", "ALLVD", "ALLWK", "ETOTAL")
    missing = [k for k in required if np.isnan(energies[k]).all()]
    if missing:
        raise ValueError("Thiếu năng lượng bắt buộc: " + ", ".join(missing))
    contact = np.flatnonzero(f > 10)
    first = int(contact[0]) if len(contact) else None
    last = int(contact[-1]) if len(contact) else None
    peak = int(np.argmax(f))
    maxdisp = int(np.argmax(u))
    k0 = float(energies["ALLKE"][0])
    mass = (actual or {}).get("panel_mass_kg")
    if mass is None and (actual or {}).get("core_cut_density_kg_m3") is not None:
        mass = (
            spec["panel"] ** 2
            * (
                (spec["skin"] + spec["bottom_skin"]) * spec["face_material"]["density"]
                + spec["core_height"] * (actual or {})["core_cut_density_kg_m3"]
            )
            * 1e-9
        )
    penergy = float(energies["ALLPD"][-1])
    # Friction is physical; numerical bulk viscosity and hourglass energy are separate.
    extra = {}
    for key in ("ALLFD", "ALLDMD", "ALLCD"):
        extra[key] = None if np.isnan(energies[key]).all() else float(energies[key][-1])
    physical = penergy + sum(value for value in extra.values() if value is not None)
    transmitted = None
    if last is not None:
        transmitted = (
            k0
            - 0.5 * spec["impact_mass"] * v[last] ** 2 / 1000
            + spec["mass_kg"] * spec["gravity"] * u[last] / 1000
        )
    summary = {
        "schema_version": "1",
        "history_integrity": integrity,
        "validation_status": "reconstruction_unvalidated",
        "initial_kinetic_energy_J": k0,
        "peak_raw_contact_force_N": float(f[peak]),
        "peak_force_time_ms": float(time[peak] * 1000),
        "max_impactor_displacement_mm": float(u[maxdisp]),
        "max_displacement_time_ms": float(time[maxdisp] * 1000),
        "max_indentation_from_contact_mm": None if first is None else float(np.max(u[first:] - u[first])),
        "max_top_centre_downward_mm": None if np.isnan(top).all() else float(np.nanmax(-top)),
        "max_bottom_centre_downward_mm": None if np.isnan(bottom).all() else float(np.nanmax(-bottom)),
        "end_impactor_velocity_mm_s": float(v[-1]),
        "end_impactor_velocity_m_s": float(v[-1] / 1000),
        "end_contact_force_N": float(f[-1]),
        "contact_first_above_10N_ms": None if first is None else float(time[first] * 1000),
        "contact_last_above_10N_ms": None if last is None else float(time[last] * 1000),
        "contact_duration_ms": None if first is None else float((time[last] - time[first]) * 1000),
        "maximum_energy_balance_drift_percent": float(
            100 * np.max(np.abs(energies["ETOTAL"] - energies["ETOTAL"][0])) / max(abs(k0), 1e-12)
        ),
        "artificial_energy_over_max_internal_percent": float(
            100 * np.max(np.abs(energies["ALLAE"])) / max(float(np.max(energies["ALLIE"])), 1e-12)
        ),
        "plastic_dissipation_J": penergy,
        "physical_dissipation_J": physical,
        "physical_dissipation_components_J": {"ALLPD": penergy, **extra},
        "transferred_energy_at_last_contact_J": transmitted,
        "panel_mass_kg": mass,
        "SEA_J_kg": physical / mass if mass else None,
        "last_time_s": float(time[-1]),
        "solver_completed": bool(time[-1] >= spec["duration"] * 0.999),
        "force_method": "m_tonne*(A3_mm_s2+gravity_mm_s2); +Z contact on guided rigid impactor",
        "missing_optional_outputs": [k for k, val in extra.items() if val is None],
    }
    damage_path = directory / "damage-summary.json"
    part_energies = {}
    if spec["core_material"].get("johnson_cook"):
        if not damage_path.exists():
            raise ValueError("Damage campaign requires rear-face STATUS/connectivity audit")
        summary.update(json.loads(damage_path.read_text()))
        for group in ("CORE", "FRONT", "REAR"):
            for variable in ("ALLPD", "ALLDMD", "ALLSE", "ALLAE", "ALLIE"):
                part_energies[group + "_" + variable] = sample(find(variable, group + "_ENERGY")) / 1000
        core_mass = (actual or {}).get("core_mass_kg")
        if not core_mass or core_mass <= 0:
            raise ValueError("Missing initial core mass")
        core_dissipation = part_energies["CORE_ALLPD"] + part_energies["CORE_ALLDMD"]
        tail = time >= max(0, time[-1] - .0005)
        force_limit = max(1., .01 * float(f[peak]))
        stable_energy = float(np.ptp(core_dissipation[tail])) <= .01 * max(float(core_dissipation[-1]), 1.e-6)
        # Ignore the initial near-zero denominator; audit every later recorded time,
        # rather than dividing two maxima that can occur at different times.
        developed = energies['ALLIE'] >= .01 * abs(k0)
        artificial_ratio = (float(100 * np.max(np.abs(energies['ALLAE'][developed]) /
                                             np.abs(energies['ALLIE'][developed])))
                            if np.any(developed) else None)
        summary.update(physics_version=spec["physics_version"], expected_energy_J=spec["energy_J"],
                       core_mass_kg=core_mass, core_dissipation_J=float(core_dissipation[-1]),
                       SEA_core_J_kg=float(core_dissipation[-1]) / core_mass,
                       history_integrity_passed=integrity["passed"],
                       maximum_artificial_energy_ratio_developed_percent=artificial_ratio,
                       developed_impact_internal_energy_threshold_J=.01 * abs(k0),
                       event_finished=bool(np.max(np.abs(f[tail])) <= force_limit and stable_energy),
                       velocity_m_s=spec["velocity_m_s"], foil=spec["foil"],
                       validation_status="AA6061-T6-reference-unvalidated")
    rows = []
    for i, t in enumerate(time):
        row = {
            "time_s": float(t),
            "time_ms": float(t * 1000),
            "contact_force_N": float(f[i]),
            "impactor_displacement_mm": float(u[i]),
            "velocity_mm_s": float(v[i]),
            "acceleration_mm_s2": float(acc[i, 1]),
            "top_U3_mm": float(top[i]),
            "bottom_U3_mm": float(bottom[i]),
        }
        row.update({k + "_J": float(a[i]) for k, a in energies.items()})
        row.update({k + "_J": float(a[i]) for k, a in part_energies.items()})
        rows.append({k: None if isinstance(x, float) and not math.isfinite(x) else x for k, x in row.items()})
    write_rows(directory / "impact_history.csv", rows)
    pq.write_table(pa.Table.from_pylist(rows), directory / "impact_history.parquet", compression="zstd")
    all_rows = [
        {
            "step": h["step"],
            "region": h["region"],
            "variable": h["variable"],
            "description": h["description"],
            "time_s": t,
            "value": x,
        }
        for h in history
        for t, x in h["data"]
    ]
    pq.write_table(pa.Table.from_pylist(all_rows), directory / "all_histories.parquet", compression="zstd")
    write_rows(directory / "all_histories.csv", all_rows)
    inventory = json.loads((directory / "inventory.json").read_text())
    summary["frames"] = inventory["frames"]
    force_checks = []
    extrema = {}
    field_stats: dict[str, dict[str, Any]] = {}
    parts = sorted((directory / "fields").glob("**/*.parquet"))
    for part_index, file in enumerate(parts):
        if checkpoint:
            checkpoint(part_index, len(parts))
        pf = pq.ParquetFile(file)
        meta = json.loads(pf.schema_arrow.metadata[b"honeycomb"])
        field = meta["field"]
        stats = meta.get("statistics")
        if stats is None:
            column = pf.read(columns=["data"])["data"].combine_chunks()
            matrix = column.values.to_numpy(zero_copy_only=False).reshape((len(column), -1))
            valid = np.isfinite(matrix)
            counts = valid.sum(axis=0)
            stats: dict[str, Any] = {
                "finite_count": counts.tolist(),
                "min": np.where(valid, matrix, np.inf).min(axis=0).tolist(),
                "max": np.where(valid, matrix, -np.inf).max(axis=0).tolist(),
                "sum": np.where(valid, matrix, 0.0).sum(axis=0).tolist(),
                "rows": len(matrix),
            }
        merge_statistics(field_stats, field, stats, meta.get("components"))
        if field.startswith(("CNORMF", "CSHEARF")):
            tb = pf.read(columns=["instance_index", "data"])
            index = next((i for i, n in enumerate(meta["instances"]) if "IMPACTOR" in n.upper()), None)
            if index is not None:
                total = sum(
                    -x[2] if spec.get("impactor_shape") == "blunt_cone" else x[2]
                    for idx, x in zip(tb["instance_index"].to_pylist(), tb["data"].to_pylist(), strict=False)
                    if (idx != index if spec.get("impactor_shape") == "blunt_cone" else idx == index)
                )
                force_checks.append((meta.get("step"), meta.get("frame"), meta["time_s"], total))
        if field in ("PEEQ", "S", "U"):
            tb = pf.read(
                columns=[
                    "data",
                    "mises",
                    "node_label",
                    "element_label",
                    "instance_index",
                    "integration_point",
                    "section_point",
                ]
            )
            vals = (
                tb["mises"].to_pylist()
                if field == "S"
                else [float(np.linalg.norm(x)) if field == "U" else x[0] for x in tb["data"].to_pylist()]
            )
            candidates = [(x, i) for i, x in enumerate(vals) if x is not None and math.isfinite(x)]
            if candidates:
                value, i = max(candidates)
                key = {"PEEQ": "PEEQ_max", "S": "mises_max_MPa", "U": "displacement_magnitude_max_mm"}[field]
                if key not in extrema or value > extrema[key]["value"]:
                    extrema[key] = {
                        "value": value,
                        "step": meta["step"],
                        "frame": meta["frame"],
                        "time_s": meta["time_s"],
                        "instance": meta["instances"][tb["instance_index"][i].as_py()],
                        **{
                            k: tb[k][i].as_py()
                            for k in ("node_label", "element_label", "integration_point", "section_point")
                        },
                    }
        pf.close()
    if checkpoint:
        checkpoint(len(parts), len(parts))
    reduced = sorted((directory / "reduced-fields").glob("*.json"))
    remote_count = sum(1 for _ in (directory / "remote-fields").glob("*.json"))
    entries = chain((json.loads(path.read_text(encoding="utf-8")) for path in reduced), remote_reductions(directory))
    for index, entry in enumerate(entries):
        if checkpoint:
            checkpoint(index, len(reduced) + remote_count)
        merge_statistics(field_stats, entry["field"], entry["statistics"], entry.get("components"))
        key, extreme = entry.get("extremum_key"), entry.get("extremum")
        if extreme and (key not in extrema or extreme["value"] > extrema[key]["value"]):
            extrema[key] = extreme
        if "impactor_force_z_N" in entry:
            force_checks.append((entry.get("step"), entry.get("frame"), entry["time_s"], entry["impactor_force_z_N"]))
    summary["field_storage"] = "full_parquet_remote" if remote_count else "reduced" if reduced else "full_parquet"
    # Sum chunks/components within each frame. Explicit recover can retain two
    # different frames at the same time; their forces must be checked separately.
    if force_checks:
        sums = {}
        for step, frame, t, x in force_checks:
            key = (step, frame, t)
            sums[key] = sums.get(key, 0.0) + x
        # A recovered ODB can span the full duration while missing buffered
        # history. Interpolation across such gaps is not a physical force check.
        acceleration_integrity = history_continuity(
            [h for h in history if h["variable"] == "A3" and "IMPACTOR" in h["region"].upper()], spec
        )
        if acceleration_integrity["passed"]:
            errors = [abs(x - float(np.interp(t, time, f))) for (_, _, t), x in sums.items()]
            summary["contact_force_check_max_relative_percent"] = 100 * max(errors) / max(float(f[peak]), 1e-12)
        else:
            summary["contact_force_check_max_relative_percent"] = None
    else:
        summary["contact_force_check_max_relative_percent"] = None
    summary["field_extrema"] = extrema
    for field, stats in field_stats.items():
        stats["mean"] = [s / n if n else None for s, n in zip(stats.pop("sum"), stats["count"], strict=True)]
        stats["unit"] = {
            "A": "mm/s²",
            "AR": "rad/s²",
            "U": "mm",
            "UR": "rad",
            "V": "mm/s",
            "VR": "rad/s",
            "S": "MPa",
            "CPRESS": "MPa",
            "CNORMF": "N",
            "CSHEARF": "N",
            "RF": "N",
            "RM": "N.mm",
            "LE": "1",
            "PE": "1",
            "PEEQ": "1",
        }.get(field.split()[0], "ODB-native")
    summary["field_statistics"] = field_stats
    if spec["core_material"].get("johnson_cook"):
        from .campaign import numerical_gate
        summary["campaign_quality"] = numerical_gate(summary)
    write_json(directory / "field-statistics.json", field_stats)
    write_json(directory / "summary.json", summary)
    return summary, rows


def quality(summary: dict) -> dict:
    if "campaign_quality" in summary:
        gate = summary["campaign_quality"]
        return {"solver_completed": summary["solver_completed"],
                "numerical_quality": "passed" if gate["passed"] else "review",
                "physical_validation": "not_established", "findings": gate["errors"],
                "ml_eligible": gate["passed"] and gate["rear_intact"] and summary.get("event_finished", False)}
    findings = []
    if summary.get("history_integrity", {}).get("passed") is False:
        findings.append("History ODB thiếu mẫu, không liên tục hoặc không phủ đủ thời gian; cần chạy lại dữ liệu gốc")
    if not summary.get("solver_completed"):
        findings.append("Solver chưa đạt thời gian vật lý yêu cầu")
    for key, threshold in (
        ("maximum_energy_balance_drift_percent", 1.0),
        ("artificial_energy_over_max_internal_percent", 5.0),
        ("contact_force_check_max_relative_percent", 2.0),
    ):
        value = summary.get(key)
        if value is None or not math.isfinite(value):
            findings.append(f"Thiếu hoặc không hữu hạn: {key}; chưa đủ bằng chứng kiểm tra chất lượng")
        elif value > threshold:
            findings.append(f"{key}={value:.5g}% vượt {threshold}%")
    if abs(summary["initial_kinetic_energy_J"]) < 1e-12:
        findings.append("Động năng ban đầu bằng 0")
    end_force = summary.get("end_contact_force_N")
    if end_force is None or not math.isfinite(end_force):
        findings.append("Thiếu hoặc không hữu hạn: end_contact_force_N; chưa đủ bằng chứng tách tiếp xúc")
    elif end_force > 10:
        findings.append("Cuối step còn tiếp xúc >10 N; cần xem xét tăng thời gian vật lý")
    return {
        "solver_completed": summary.get("solver_completed", False),
        "numerical_quality": "review" if findings else "passed",
        "physical_validation": "not_established",
        "findings": findings,
        "thresholds": {
            "energy_drift_percent": 1.0,
            "artificial_energy_percent": 5.0,
            "force_crosscheck_percent": 2.0,
        },
        "definition": "max(abs(ETOTAL-ETOTAL[0]))/KE0; max(abs(ALLAE))/max(ALLIE)",
        "ml_eligible": not findings,
    }


def write_rows(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(
            {k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in r.items()}
            for r in rows
        )


def checksum(path: Path, algorithm="sha256", checkpoint=None) -> str:
    h = hashlib.new(algorithm)
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
            if checkpoint:
                checkpoint(len(block))
    return h.hexdigest()


def manifest(root: Path, metadata: dict | None = None, checkpoint=None) -> dict:
    paths = [
        p
        for p in sorted(root.rglob("*"))
        if p.is_file()
        and p != root / "artifact-manifest.json"
        and not p.name.endswith((".tmp", ".lck"))
        and "spool" not in p.parts
    ]
    files = []
    total = sum(p.stat().st_size for p in paths)
    done = 0

    def advance(size):
        nonlocal done
        done += size
        if checkpoint:
            checkpoint(done, total)

    for p in paths:
        stat = p.stat()
        files.append(
            {
                "path": p.relative_to(root).as_posix(),
                "bytes": stat.st_size,
                "sha256": checksum(p, checkpoint=advance),
            }
        )
    data = {"schema_version": "1", "created_at": now(), "metadata": metadata or {}, "files": files}
    write_json(root / "artifact-manifest.json", data)
    return data


def archive(root: Path, destination: Path, checkpoint=None):
    if destination.resolve().is_relative_to(root.resolve()):
        raise ValueError("Gói ZIP phải nằm ngoài thư mục nguồn")
    snapshot = manifest(
        root, checkpoint=(lambda done, total: checkpoint("hashing", done, total)) if checkpoint else None
    )
    entries: list[dict[str, Any]] = [
        *snapshot["files"],
        {
            "path": "artifact-manifest.json",
            "bytes": (root / "artifact-manifest.json").stat().st_size,
            "sha256": checksum(root / "artifact-manifest.json"),
        },
    ]
    done = 0
    total = sum(item["bytes"] for item in entries)
    with zipfile.ZipFile(
        destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True
    ) as z:
        for item in entries:
            p = root / item["path"]
            h = hashlib.sha256()
            size = 0
            with p.open("rb") as source, z.open(item["path"], "w", force_zip64=True) as target:
                for block in iter(lambda: source.read(8 * 1024 * 1024), b""):
                    target.write(block)
                    h.update(block)
                    size += len(block)
                    done += len(block)
                    if checkpoint:
                        checkpoint("archiving", done, total)
            if size != item["bytes"] or h.hexdigest() != item["sha256"]:
                raise ValueError(
                    "File thay đổi trong lúc đóng gói; chờ thao tác ghi kết thúc rồi xuất lại: "
                    + item["path"]
                )


def pareto(rows: list[dict]) -> list[dict]:
    objectives = ["panel_mass_kg", "peak_raw_contact_force_N", "max_top_centre_downward_mm", "SEA_J_kg"]
    valid = [r for r in rows if all(r.get(k) is not None for k in objectives)]
    points = np.array([[r[k] * (-1 if k == "SEA_J_kg" else 1) for k in objectives] for r in valid])
    return [
        r
        for i, r in enumerate(valid)
        if not any(np.all(p <= points[i]) and np.any(p < points[i]) for j, p in enumerate(points) if i != j)
    ]


def dataset(
    store,
    run_ids: list[str],
    name: str,
    seed=42,
    features=None,
    targets=None,
    curve_points=201,
    destination: Path | None = None,
):
    rows: list[dict[str, Any]] = []
    groups = {}
    requested_keys = set()
    for rid in dict.fromkeys(run_ids):
        run = store.get("runs", rid)
        if (
            run.get("test_only")
            or run.get("status") != "completed"
            or not (run.get("quality") or {}).get("ml_eligible")
        ):
            continue
        flat = {}

        def flatten(d, prefix="input."):
            for k, v in d.items():
                if isinstance(v, dict):
                    flatten(v, prefix + k + ".")
                elif isinstance(v, (str, int, float, bool)) or v is None:
                    flat[prefix + k] = v

        flatten(run["resolved"])
        # Retain swept controls outside the physical feature shortlist, such
        # as duration, CPU count and output sampling, in the default export.
        def requested_columns(payload, prefix="input."):
            for key, value in payload.items():
                if isinstance(value, dict):
                    requested_columns(value, prefix + key + ".")
                elif isinstance(value, (str, int, float, bool)) or value is None:
                    requested_keys.add(prefix + key)

        requested_columns(run.get("requested") or run["resolved"])
        if flat.get("input.core_topology") == "reentrant_0":
            height = flat.get("input.reentrant_cell_height")
            indent = flat.get("input.reentrant_indent")
            if height and indent is not None:
                # The saved angle setting is inactive in indent mode. Export
                # the angle of the geometry actually used by the solver.
                flat["input.reentrant_delta_deg"] = round(math.degrees(math.atan2(2 * indent, height)), 12)
        flat.setdefault("input.core_topology", "hexagonal")
        flat.setdefault("input.clamp_mode", "circular")
        if flat["input.core_topology"] == "hexagonal":
            flat.setdefault("input.hex_geometry", "regular")
            if flat["input.hex_geometry"] == "regular" and "input.cell_size" in flat:
                flat.setdefault("input.hex_b", flat["input.cell_size"] / math.sqrt(3))
                flat.setdefault("input.hex_l", flat["input.cell_size"] / math.sqrt(3))
                flat.setdefault("input.hex_theta_deg", 60.0)
        if "input.ball_diameter" in flat:
            flat.setdefault("input.ball_radius", flat["input.ball_diameter"] / 2)
        row = {
            "run_id": rid,
            "batch_id": run["batch_id"],
            "design_id": run["design_id"],
            "input_hash": run["input_hash"],
            "physical_validation": run["quality"].get("physical_validation", "not_established"),
            "numerical_quality": run["quality"].get("numerical_quality", "unknown"),
            "attempt_number": run["attempts"][-1]["number"] if run["attempts"] else None,
            "extractor_version": (
                (run["attempts"][-1].get("postprocess_sources") or [{}])[-1].get("version", "unknown")
                if run["attempts"]
                else "unknown"
            ),
            **flat,
            **{k: v for k, v in run["summary"].items() if isinstance(v, (int, float, str)) or v is None},
        }
        if "end_impactor_velocity_m_s" not in row and row.get("end_impactor_velocity_mm_s") is not None:
            row["end_impactor_velocity_m_s"] = row["end_impactor_velocity_mm_s"] / 1000
        row.update({k: v["value"] for k, v in run["summary"].get("field_extrema", {}).items()})
        if row["input_hash"] in groups:
            continue
        groups[row["input_hash"]] = rid
        rows.append(row)
    if not rows:
        raise ValueError("Không có lượt đủ chất lượng để tạo dataset")
    designs = sorted(set(r["design_id"] for r in rows))
    np.random.default_rng(seed).shuffle(designs)
    # Assign entire physical designs, including numerical variants, to one split.
    n = len(designs)
    train = max(1, int(n * 0.7))
    val = int(n * 0.15)
    split = {
        g: ("train" if i < train else "validation" if i < train + val else "test")
        for i, g in enumerate(designs)
    }
    for row in rows:
        row["split"] = split[row["design_id"]]
    spec_hash = digest(
        {
            "runs": sorted(groups),
            "seed": seed,
            "features": features,
            "targets": targets,
            "curve_points": curve_points,
            "source_attempts": [(r["run_id"], r["attempt_number"]) for r in rows],
            "builder_sha256": checksum(Path(__file__)),
        }
    )
    identity = "d" + uuid.uuid4().hex[:16]
    out = destination if destination is not None else store.root / "datasets" / identity
    out.mkdir(parents=True, exist_ok=True)
    varying_requested = {key for key in requested_keys if len({r.get(key) for r in rows}) > 1}
    default_features = {"input." + key for key in FEATURES} | varying_requested
    selected = []
    for row in rows:
        keys = PROVENANCE & row.keys()
        keys.update(
            features if features is not None else default_features & row.keys()
        )
        keys.update(targets if targets is not None else [k for k in TARGETS if k in row])
        unknown = keys - row.keys()
        if unknown:
            raise ValueError("Tên feature/target không tồn tại: " + ", ".join(sorted(unknown)))
        selected.append({k: row[k] for k in row if k in keys})
    selected_columns = list(dict.fromkeys(k for row in selected for k in row))
    selected = [{k: row.get(k) for k in selected_columns} for row in selected]
    write_rows(out / "samples.csv", selected)
    pq.write_table(pa.Table.from_pylist(selected), out / "samples.parquet", compression="zstd")
    # Original time samples and a separate, explicitly resampled curve product.
    for row in rows:
        run = store.get("runs", row["run_id"])
        audit = out / "provenance" / run["id"]
        for filename, payload in (
            ("resolved-input.json", run["resolved"]),
            ("summary.json", run["summary"]),
            ("quality.json", run["quality"]),
        ):
            write_json(audit / filename, payload)
        if not run["attempts"]:
            continue
        source = Path(run["attempts"][-1]["path"]) / "extracted"
        if not (source / "impact_history.csv").exists() and not (source / "impact_history.parquet").exists():
            from .history_sources import load_history

            history = load_history(run)
            if history:
                source = history["directory"]
        curves = out / "curves" / run["id"]
        curves.mkdir(parents=True, exist_ok=True)
        import shutil

        for filename in ("impact_history.csv", "impact_history.parquet", "all_histories.parquet"):
            if (source / filename).exists():
                shutil.copy2(source / filename, curves / filename)
        if (source / "impact_history.parquet").exists():
            raw = pq.read_table(source / "impact_history.parquet").to_pylist()
            t = np.array([r["time_s"] for r in raw])
            contact = run["summary"].get("contact_first_above_10N_ms")
            start = contact / 1000 if contact is not None else float(t[0])
            grid = np.linspace(start, float(t[-1]), curve_points)
            sampled = {"time_since_contact_s": grid - start, "time_s": grid}
            for key in ("contact_force_N", "impactor_displacement_mm", "velocity_mm_s"):
                sampled[key] = np.interp(grid, t, [r[key] for r in raw])
            pq.write_table(pa.table(sampled), curves / "resampled.parquet", compression="zstd")
    write_data_dictionary(out, selected[0])
    write_json(
        out / "dataset.json",
        {
            "id": identity,
            "created_at": now(),
            "export_spec_hash": spec_hash,
            "builder_sha256": checksum(Path(__file__)),
            "source_attempts": [{"run_id": r["run_id"], "attempt": r["attempt_number"]} for r in rows],
            "name": name,
            "seed": seed,
            "group_by": "physical design, excludes loading and mesh",
            "samples": len(rows),
            "designs": n,
            "split_counts": {s: sum(r["split"] == s for r in rows) for s in ("train", "validation", "test")},
            "run_ids": [r["run_id"] for r in rows],
            "features": features
            if features is not None
            else [k for k in selected_columns if k.startswith("input.")],
            "targets": targets if targets is not None else [k for k in selected_columns if k in TARGETS],
            "constant_features": [
                k for k in selected[0] if k.startswith("input.") and len({r.get(k) for r in selected}) == 1
            ],
            "varying_features": [
                k for k in selected_columns if k.startswith("input.") and len({r.get(k) for r in selected}) > 1
            ],
            "note": "Constant features may be removed by training preprocessing; custom plastic tables require explicit curve features. Numerical quality does not establish experimental validity.",
            "resampling": {
                "points": curve_points,
                "method": "linear",
                "alignment": "first F>10 N; fallback first sample",
                "originals_preserved": True,
            },
        },
    )
    manifest(out)
    return {"id": identity, "path": str(out), "samples": len(rows)}


def write_data_dictionary(directory: Path, columns) -> dict:
    """Keep training rows machine-readable and ship their meanings alongside them."""
    dictionary = {key: describe_column(key) for key in columns}
    write_json(directory / "data-dictionary.json", dictionary)
    roles = {"input": "Đầu vào", "target": "Kết quả", "provenance": "Truy vết / chia tập"}
    write_rows(
        directory / "data-dictionary.csv",
        [
            {
                "Tên trường": key,
                "Tên tiếng Việt": value["title"],
                "Vai trò": roles[value["role"]],
                "Đơn vị": value["unit"],
                "Mô tả / cách tính": value["definition"],
                "Nguồn": value["source"],
                "Giá trị thiếu": value["missing"],
            }
            for key, value in dictionary.items()
        ],
    )
    lines = [
        "# Mô tả các trường dữ liệu huấn luyện",
        "",
        "Mỗi dòng trong samples.csv/samples.parquet là một lượt mô phỏng được chọn. "
        "Tên cột và giá trị được giữ nguyên để đọc bằng chương trình; tra mô tả trong bảng dưới "
        "hoặc data-dictionary.csv (UTF-8 BOM, mở bằng Excel) và data-dictionary.json.",
        "",
        "Các cột input.* là đặc trưng đầu vào; kết quả là nhãn dự đoán. Các mã định danh, "
        "mã băm, số attempt và split dùng truy vết/chia tập, không nên đưa trực tiếp vào đặc trưng học. "
        "Các chỉ số chất lượng số dùng sàng lọc; không chứng minh độ đúng thực nghiệm. "
        "Cực trị chỉ xét các mẫu/frame đã ghi. Ô trống là giá trị thiếu, không phải số 0.",
        "",
        "Các mẫu cùng design_id nằm trong cùng một split để tránh rò rỉ. "
        "Nếu chỉ có một thiết kế, validation/test có thể trống. "
        "Tham số vật liệu không hoạt động với quy luật hóa bền đã chọn nên được loại khi tiền xử lý.",
        "",
        "| Tên trường | Tên tiếng Việt | Vai trò | Đơn vị | Mô tả / cách tính |",
        "| --- | --- | --- | --- | --- |",
    ]
    for key, value in dictionary.items():
        cells = [key, value["title"], roles[value["role"]], value["unit"], value["definition"]]
        lines.append("| " + " | ".join(str(c).replace("|", "\\|").replace("\n", " ") for c in cells) + " |")
    (directory / "FIELD_DESCRIPTIONS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dictionary


def verify_export(directory: Path, checkpoint=None) -> dict:
    inventory = json.loads((directory / "inventory.json").read_text())
    expected = {(f["step"], f["frame"], f["field"]): f["rows"] for f in inventory["fields"]}
    observed = {}
    parts = 0
    for path in (directory / "reduced-fields").glob("*.json"):
        item = json.loads(path.read_text(encoding="utf-8"))
        key = (item["step"], item["frame"], item["field"])
        observed[key] = observed.get(key, 0) + item["rows"]
        parts += 1
    for item in remote_reductions(directory):
        key = (item["step"], item["frame"], item["field"])
        observed[key] = observed.get(key, 0) + item["rows"]
        parts += 1
    files = list((directory / "fields").glob("**/*.parquet"))
    for index, path in enumerate(files):
        if checkpoint:
            checkpoint(index, len(files))
        with pq.ParquetFile(path) as pf:
            meta = json.loads(pf.schema_arrow.metadata[b"honeycomb"])
            key = (meta["step"], meta["frame"], meta["field"])
            observed[key] = observed.get(key, 0) + pf.metadata.num_rows
            parts += 1
    mismatch = {
        str(k): {"expected": expected.get(k), "observed": observed.get(k, 0)}
        for k in set(expected) | set(observed)
        if expected.get(k, 0) != observed.get(k, 0)
    }
    result = {
        "passed": not mismatch,
        "mode": inventory.get("export_profile", "full_fields"),
        "rows_definition": "source field samples processed; reduced mode stores statistics and extrema, not these rows",
        "parts": parts,
        "field_frame_pairs": len(expected),
        "rows": sum(observed.values()),
        "mismatches": mismatch,
    }
    write_json(directory / "export-verification.json", result)
    if mismatch:
        raise ValueError("Số mẫu đã xử lý không khớp danh mục ODB; xem export-verification.json")
    return result
