"""One auditable training table across jobs, using the existing quality selection."""

from __future__ import annotations

import json
import math
import shutil
from copy import deepcopy
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from .data import dataset, manifest, write_data_dictionary, write_rows
from .job_data import full_manifest, job_folder, run_folder
from .research import FEATURES, PROVENANCE, TARGETS
from .retained import coverage
from .store import now, write_json


def training_paths(archive):
    """Download only original settings and extracted histories, never the large ODB."""
    names = {"run.json", "requested-input.json", "resolved-input.json",
             "impact_history.csv", "impact_history.parquet", "all_histories.parquet"}
    return [f["path"] for f in archive["files"]
            if "/runs/" in f["path"] and Path(f["path"]).name in names]


def collect_runs(root: Path):
    runs = []
    for file in sorted(root.glob("projects/*/batches/*/runs/*/run.json")):
        run = json.loads(file.read_text(encoding="utf-8"))
        if run["id"] != file.parent.name:
            raise ValueError("Run identity differs from its archived directory")
        run["path"] = str(file.parent)
        for attempt in run.get("attempts", []):
            number = attempt["number"]
            if type(number) is not int or number < 1:
                raise ValueError("Invalid attempt number")
            attempt["path"] = str(file.parent / "attempts" / f"{number:03d}")
        runs.append(run)
    return runs


def apply_history_audit(runs, audit):
    """Apply verified later findings to derived tables, preserving source archives."""
    if audit.get('passed') is not False:
        return
    for run in runs:
        run.setdefault('original_publication_quality', deepcopy(run.get('quality')))
        run['status'] = 'review'
        run['history_audit'] = deepcopy(audit)
        quality = dict(run.get('quality') or {})
        finding = 'Original ODB history contains a recovery gap; rerun required.'
        quality.update(ml_eligible=False, numerical_quality='review',
                       findings=list(dict.fromkeys([*quality.get('findings', []), finding])))
        run['quality'] = quality


class CollectionStore:
    def __init__(self, runs, root):
        self.root = root
        self.runs = {r["id"]: r for r in runs}
        if len(self.runs) != len(runs):
            raise ValueError("Duplicate run identity across archives")

    def get(self, kind, identity):
        if kind != "runs":
            raise ValueError("Only archived runs are available")
        return self.runs[identity]


def build_collection(sources, out: Path, *, single_job=False):
    """Sources carry human-readable job names, immutable archive URLs and restored runs."""
    out.mkdir(parents=True, exist_ok=False)
    runs = [run for source in sources for run in source.get("runs", [])]
    store = CollectionStore(runs, out)
    training = out / "01_training"
    valid = [r for r in runs if r.get("status") == "completed" and not r.get("test_only")
             and (r.get("quality") or {}).get("ml_eligible")]
    if valid:
        dataset(store, [r["id"] for r in runs], "Tổng hợp tất cả job cloud", destination=training)
    else:
        columns = [*sorted(PROVENANCE), *("input." + k for k in FEATURES), *TARGETS]
        training.mkdir()
        table = pa.table({k: pa.array([], type=pa.string()) for k in columns})
        pq.write_table(table, training / "samples.parquet", compression="zstd")
        # A header-only CSV explicitly represents zero accepted samples.
        import csv

        with (training / "samples.csv").open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.writer(stream)
            writer.writerow(columns)
        write_data_dictionary(training, columns)
        write_json(training / "dataset.json", {
            "samples": 0, "run_ids": [], "features": ["input." + k for k in FEATURES],
            "targets": TARGETS, "split_counts": {k: 0 for k in ("train", "validation", "test")},
            "varying_features": [],
            "note": "Chưa có mẫu đạt điều kiện. Không dùng bảng rỗng để huấn luyện.",
        })
    meta = json.loads((training / "dataset.json").read_text(encoding="utf-8"))
    audit = out / "02_audit"
    if runs:
        write_rows(audit / "run-selection.csv", coverage(runs, set(meta["run_ids"])))
    else:
        audit.mkdir(parents=True)
        (audit / "run-selection.csv").write_text("run_id,index,status,included,reason,quality_findings\n", encoding="utf-8")
    index = []
    all_results = []
    selection = {row["run_id"]: row for row in coverage(runs, set(meta["run_ids"]))}
    for source in sources:
        folder = job_folder(source["job_id"], source.get("job_name", "Mo phong"))
        index.append({k: v for k, v in source.items() if k not in ("runs", "archive", "job")} | {"folder": folder})
        if source.get("job"):
            write_json((out if single_job else out / "03_simulations" / folder) / "job.json", source["job"])
        for run in source.get("runs", []):
            base = out / "03_simulations" if single_job else out / "03_simulations" / folder
            dest = base / run_folder(run, source.get("index", 0))
            for name, payload in (("input/requested.json", run.get("requested")),
                                  ("input/resolved.json", run["resolved"]),
                                  ("output/summary.json", run.get("summary", {})),
                                  ("output/quality.json", run.get("quality", {}))):
                write_json(dest / name, payload)
            for attempt in run.get("attempts", []):
                for name in ("impact_history.csv", "impact_history.parquet", "all_histories.parquet"):
                    src = Path(attempt["path"]) / "extracted" / name
                    if src.is_file():
                        target = dest / "output" / f"attempt-{attempt['number']:03d}" / name
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src, target)
            result = {"job_id": source["job_id"], "job_name": source.get("job_name", ""),
                      "run_id": run["id"], "design_id": run["design_id"], "input_hash": run["input_hash"],
                      "status": run["status"], "included_in_training": run["id"] in meta["run_ids"],
                      "selection_reason": selection[run["id"]]["reason"],
                      "quality_findings": selection[run["id"]]["quality_findings"]}

            def flatten(payload, prefix):
                for key, value in payload.items():
                    if isinstance(value, dict):
                        flatten(value, prefix + key + ".")
                    elif isinstance(value, (str, int, float, bool)) or value is None:
                        result[prefix + key] = value

            flatten(run["resolved"], "input.")
            flatten(run.get("summary", {}), "output.")
            all_results.append(result)
    write_json(audit / "source-jobs.json", index)
    write_json(audit / "full-source-manifest.json", full_manifest(sources))
    if all_results:
        write_rows(out / "05_all_results/simulation-results.csv", all_results)
        columns = list(dict.fromkeys(k for row in all_results for k in row))
        normalized = [{k: row.get(k) for k in columns} for row in all_results]
        pq.write_table(pa.Table.from_pylist(normalized), out / "05_all_results/simulation-results.parquet", compression="zstd")
    write_json(out / "05_all_results/README.json", {
        "rows": len(all_results), "note": "Tất cả kết quả đã lưu, kể cả review/smoke. Đây không phải bảng huấn luyện đã lọc.",
        "input_prefix": "input.", "output_prefix": "output.", "training_file": "../01_training/samples.parquet",
    })
    write_json(audit / "input-output-contract.json", {
        "X": meta["features"], "y_candidates": meta["targets"],
        "provenance_do_not_train_on": sorted(PROVENANCE), "split_column": "split",
        "missing_values": "Ô trống/null là thiếu dữ liệu, không thay bằng 0.",
        "target_selection": "Chọn y theo bài toán; các chỉ số kiểm tra chất lượng chỉ dùng lọc/đánh giá.",
    })
    samples = pq.read_table(training / "samples.parquet").to_pylist()
    write_json(training / "readiness.json", {
        "numerically_eligible_samples": len(samples),
        "missing_feature_values": {key: sum(row.get(key) is None for row in samples) for key in meta["features"]},
        "usable_rows_by_target": {key: sum(isinstance(row.get(key), (int, float)) and math.isfinite(row[key])
                                           for row in samples) for key in meta["targets"]},
        "split_counts": meta["split_counts"],
        "evaluation_splits_available": all(meta["split_counts"].get(key, 0) > 0 for key in ("train", "validation", "test")),
        "experimental_validation": "not_established",
        "note": "Chất lượng số đạt không chứng minh hội tụ lưới, độ đúng thực nghiệm hoặc đủ số mẫu để tổng quát hóa. Chọn y và kiểm tra số dòng đầy đủ trước khi huấn luyện.",
    })
    (out / "README.md").write_text(
        "# Bộ dữ liệu mô phỏng tổng hợp\n\n"
        "## Bắt đầu ở đâu?\n\n"
        "- `01_training/samples.csv`: bảng huấn luyện chung; mỗi dòng là một đầu vào duy nhất đạt chất lượng.\n"
        "- `01_training/samples.parquet`: cùng dữ liệu, giữ kiểu và nén tốt hơn cho Python.\n"
        "- `01_training/dataset.json`: số mẫu, danh sách X/y và cách chia train/validation/test.\n"
        "- `input.reentrant_delta_deg`: góc lõm δ thực tế (độ); giữ cùng độ lõm mm. "
        "Các đầu vào dạng số/phân loại thay đổi giữa các mẫu cũng được giữ trong bảng; "
        "xem `dataset.json.varying_features` để nhận diện cột thay đổi.\n"
        "- `01_training/data-dictionary.csv` và `FIELD_DESCRIPTIONS.md`: tên, đơn vị và ý nghĩa từng cột.\n"
        "- `02_audit/run-selection.csv`: từng lượt được nhận hoặc lý do bị loại.\n"
        "- `02_audit/source-jobs.json`: tên bài, ID và liên kết kho gốc; ghi cả bài thiếu dữ liệu.\n"
        "- `03_simulations/job--<tên-bài>--<ID>/run-0001--<tham-số>--<ID>/input/`: requested.json (yêu cầu), resolved.json (đầu vào thực tế).\n"
        "- `03_simulations/.../output/`: summary.json (kết quả), quality.json (chất lượng), đường cong theo attempt.\n\n"
        "- `05_all_results/simulation-results.csv/Parquet`: bảng tất cả lượt đã lưu, gồm cả review/smoke; cột input.* là đầu vào, output.* là kết quả, không tự coi là bảng huấn luyện.\n"
        "- `02_audit/full-source-manifest.json`: thư mục nguồn đầy đủ gồm ODB/CAE/INP, log, báo cáo và dữ liệu trường. Kiểm tra complete trước khi khôi phục.\n\n"
        "## Đầu vào và đầu ra\n\n"
        "**Mô phỏng:** đầu vào gồm hình học (mm), vật liệu, ngàm, tải (J hoặc m/s), lưới và thời gian (s). "
        "Đầu ra gồm lực (N), chuyển vị (mm), năng lượng (J), ứng suất (MPa), đường cong theo thời gian và kiểm tra chất lượng.\n\n"
        "**Huấn luyện:** X là các cột `input.*` có trong `dataset.json.features`; "
        "y được chọn từ `dataset.json.targets`, ví dụ `peak_raw_contact_force_N`, "
        "`max_top_centre_downward_mm`, `SEA_J_kg`. Không đưa ID, split hoặc kết quả y vào X. "
        "Các đại lượng phân loại cần mã hóa; giá trị thiếu cần xử lý riêng. "
        "Không tự coi các chỉ số sai số/năng lượng nhân tạo là mục tiêu vật lý.\n\n"
        "Chỉ lấy lượt completed, ml_eligible=true, không phải test_only; smoke/review không dùng huấn luyện. "
        "Khử trùng theo input_hash trên toàn bộ job, chia theo design_id toàn cục để tránh rò rỉ giữa các tập. "
        "Dùng cột split có sẵn; không chia ngẫu nhiên lại từng dòng. "
        "Không có mẫu đạt thì CSV chỉ có tiêu đề và samples=0. "
        "ODB/CAE/INP dung lượng lớn vẫn ở release gốc được dẫn trong source-jobs.json.\n",
        encoding="utf-8",
    )
    summary = {"samples": meta["samples"], "runs": len(runs), "sources": len(sources),
               "unavailable_sources": sum(bool(s.get("excluded_reason")) for s in sources), "created_at": now()}
    write_json(out / "collection.json", summary)
    manifest(out)
    return summary
