"""Collect original cloud results into one versioned, verified training release."""

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path

from honeycomb_studio.cloud_archive import ReleaseArchive
from honeycomb_studio.cloud_github import JOB_ID, REPOSITORY, Catalog, Github
from honeycomb_studio.cloud_job_data import BUILDER_VERSION, publish_job_data
from honeycomb_studio.cloud_matrix import TERMINAL
from honeycomb_studio.cloud_release import reserve_release
from honeycomb_studio.cloud_restore import public_asset, restore, validate_manifest
from honeycomb_studio.models import BatchSpec, expand
from honeycomb_studio.training_collection import (
    apply_history_audit,
    build_collection,
    collect_runs,
    training_paths,
)


def collect(github, catalog, root):
    sources = []
    # Snapshot the catalog once. Active jobs remain listed with a reason, not silently omitted.
    jobs = sorted(catalog.jobs(), key=lambda j: j["id"])
    print(f"Tổng hợp {len(jobs)} bài trong catalog; chỉ tải thiết lập và đường cong đã xác minh.", flush=True)
    for row in jobs:
        if not JOB_ID.fullmatch(row["id"]):
            raise ValueError("Invalid source job identity")
        parent, _ = catalog.get("jobs/" + row["id"])
        if parent is None:
            raise ValueError("Indexed source job is missing")
        for shard in parent.get("shards") or [parent]:
            source = {"job_id": parent["id"], "job_name": parent["name"], "index": shard.get("index", 0),
                      "shard_id": shard["id"], "status": shard["status"],
                      "profile": parent["profile"], "runs": [],
                      "job": {k: parent.get(k) for k in ("id", "name", "profile", "spec", "input_hash", "status", "workflow_run_id", "execution")}}
            sources.append(source)
            print(f"Nguồn {len(sources)} · {parent['name']} · {shard['id']} · {shard['status']}", flush=True)
            if parent["status"] not in TERMINAL:
                source["excluded_reason"] = "Đợt chạy chưa kết thúc; chờ tất cả lượt trước khi tổng hợp."
                continue
            if not shard.get("archive_verified") or not shard.get("release_url"):
                source["excluded_reason"] = "Chưa có bản lưu hoàn tất đã xác minh; bài đang chạy/chưa chạy/lỗi."
                continue
            if not JOB_ID.fullmatch(shard["id"]):
                raise ValueError("Invalid source shard identity")
            release = github.repo("GET", "/releases/tags/simulation-" + shard["id"])
            assets = []
            for page in range(1, 12):
                batch = github.repo("GET", f"/releases/{release['id']}/assets?per_page=100&page={page}")
                assets.extend(batch)
                if len(batch) < 100:
                    break
            else:
                raise ValueError("Source release exceeds bounded asset inventory")
            workflow = shard.get("workflow_run_id") or parent.get("workflow_run_id")
            name = f"workflow-{workflow}-artifact-manifest.json"
            asset = next((a for a in assets if a["name"] == name), None)
            if asset is None:
                raise ValueError("Verified source has no final manifest: " + shard["id"])
            if asset["size"] > 32 * 1024**2:
                raise ValueError("Source manifest exceeds size limit")
            url = public_asset(asset["browser_download_url"])
            response = github.client.get(url)
            response.raise_for_status()
            content = response.content
            digest = hashlib.sha256(content).hexdigest()
            if len(content) != asset["size"] or asset.get("digest") != "sha256:" + digest:
                raise ValueError("Source manifest failed GitHub SHA-256 verification")
            archive = json.loads(content)
            validate_manifest(archive, allow_incomplete=True)
            source.update(release_url=release["html_url"], manifest_url=url,
                          manifest_sha256=digest, workflow_run_id=workflow, archive=archive)
            if archive["complete"] is not True:
                source["excluded_reason"] = "Bản lưu chẩn đoán chưa hoàn chỉnh; không dùng huấn luyện."
                continue
            restored = root / shard["id"]
            restore(archive, restored, client=github.client, paths=training_paths(archive))
            runs = collect_runs(restored)
            apply_history_audit(runs, shard.get('history_audit') or {})
            if shard.get('history_audit'):
                source['history_audit'] = shard['history_audit']
            expected = {r["id"] for r in shard.get("runs", [])}
            if expected != {r["id"] for r in runs}:
                raise ValueError("Archived run inventory differs from source catalog")
            if not runs:
                source["excluded_reason"] = "Bản lưu chẩn đoán không có lượt mô phỏng."
            if parent["profile"] == "smoke":
                for run in runs:
                    run["quality"] = {**(run.get("quality") or {}), "ml_eligible": False}
                    run["collection_exclusion"] = "Smoke chỉ kiểm tra môi trường, không dùng huấn luyện"
            source.update(runs=runs, release_url=release["html_url"], manifest_url=url,
                          manifest_sha256=digest, workflow_run_id=workflow)
    return sources


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("output/training-collection"))
    parser.add_argument("--full-data", action="store_true", help="Publish complete solver ZIPs for every archived job")
    parser.add_argument("--full-job-id", default="", help="Limit complete solver ZIP construction to this parent job")
    parser.add_argument("--require-training-job", default="", help="Fail acceptance if this research job has any unaccepted sample")
    args = parser.parse_args()
    github = Github(token=os.environ["GITHUB_TOKEN"])
    catalog = Catalog(github)
    workflow = int(os.environ["GITHUB_RUN_ID"])
    attempt = int(os.getenv("GITHUB_RUN_ATTEMPT", "1"))
    tag = f"training-{workflow}-{attempt}"
    if args.full_job_id and not JOB_ID.fullmatch(args.full_job_id):
        raise ValueError("Invalid full-data job ID")
    release = reserve_release(github, tag=tag, sha=os.environ["GITHUB_SHA"],
                              name=f"Dữ liệu huấn luyện tổng hợp · {workflow} · lần {attempt}")
    reservations = {}
    for row in catalog.jobs():
        if row["status"] not in ("draft", "dispatching", "running", "preflight"):
            cached, _ = catalog.get("training/jobs/" + row["id"])
            wants_full = row["id"] == args.full_job_id or (args.full_data and not args.full_job_id)
            if (cached and cached.get("builder_version") == BUILDER_VERSION
                    and cached.get("source_status") == row["status"]
                    and cached.get("workflow_run_id") == row.get("workflow_run_id")
                    and (not wants_full or cached.get("full_bundle"))):
                reservations[row["id"]] = None
                continue
            reservations[row["id"]] = reserve_release(
                github, tag=f"job-data-{row['id']}-{workflow}-{attempt}", sha=os.environ["GITHUB_SHA"],
                name="Dữ liệu job · " + row["name"], source_tag=tag)
    sources = collect(github, catalog, args.root / "restored")
    directory = args.root / ("honeycomb-training-" + str(workflow) + "-" + str(attempt))
    summary = build_collection(sources, directory)
    archive = Path(shutil.make_archive(str(directory), "zip", directory.parent, directory.name))
    publisher = ReleaseArchive(github, release["id"], tag=tag)
    publisher.upload(archive, archive.name)
    for path, name in ((directory / "01_training/samples.csv", "samples.csv"),
                       (directory / "01_training/samples.parquet", "samples.parquet"),
                       (directory / "01_training/dataset.json", "dataset.json"),
                       (directory / "README.md", "README.md"),
                       (directory / "artifact-manifest.json", "artifact-manifest.json")):
        publisher.upload(path, name)
    all_results = {}
    for suffix in ("csv", "parquet"):
        path = directory / f"05_all_results/simulation-results.{suffix}"
        if path.is_file():
            all_results[f"all_results_{suffix}_url"] = publisher.upload(path, f"simulation-results.{suffix}")["url"]
    published = github.repo("PATCH", f"/releases/{release['id']}", {
        "draft": False, "prerelease": True,
        "body": f"Bộ tổng hợp: {summary['samples']} mẫu huấn luyện / {summary['runs']} lượt. "
                "ZIP gồm 01_training, 02_audit, 03_simulations. CSV/Parquet tải trực tiếp. "
                "X = input.*; y xem dataset.json. Smoke/review bị loại. "
                f"{summary['unavailable_sources']} nguồn chưa có bản lưu hoàn tất; xem source-jobs.json.",
    })
    record = {**summary, **all_results, "job_collections": (catalog.get("training/index")[0] or {}).get("jobs", []), "release_url": published["html_url"],
              "workflow_url": f"https://github.com/{REPOSITORY}/actions/runs/{workflow}",
              "csv_url": f"https://github.com/{REPOSITORY}/releases/download/{tag}/samples.csv",
              "parquet_url": f"https://github.com/{REPOSITORY}/releases/download/{tag}/samples.parquet",
              "zip_url": f"https://github.com/{REPOSITORY}/releases/download/{tag}/{archive.name}"}
    catalog.update("training/latest", lambda old: record)
    text = f"## Dữ liệu huấn luyện tổng hợp\n\n{summary['samples']} mẫu đạt / {summary['runs']} lượt lưu.\n\n[ZIP, CSV và Parquet]({record['release_url']})\n"
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as stream:
            stream.write(text)
    print(json.dumps(record, ensure_ascii=True))
    print("CSV/Parquet tổng hợp đã công bố; bắt đầu cập nhật thư mục từng job bằng nguồn sẵn có.", flush=True)
    jobs = []
    for identity in dict.fromkeys(s["job_id"] for s in sources):
        selected = [s for s in sources if s["job_id"] == identity]
        if identity not in reservations or not any(s.get("archive") for s in selected):
            continue
        full = identity == args.full_job_id or (args.full_data and not args.full_job_id)
        jobs.append(publish_job_data(github, catalog, selected, reservations[identity],
                                     workflow=workflow, attempt=attempt, full=full, root=args.root))
    record["job_collections"] = jobs
    catalog.update("training/latest", lambda old: record)
    catalog.update("training/index", lambda old: {"jobs": jobs})
    if args.require_training_job:
        source = next(s for s in sources if s["job_id"] == args.require_training_job)
        if source["profile"] != "smoke":
            expected = len(expand(BatchSpec.model_validate(source["job"]["spec"])))
            result = next((j for j in jobs if j["id"] == args.require_training_job), {})
            if result.get("samples") != expected or not result.get("source_complete"):
                raise RuntimeError(f"Chưa đạt nghiệm thu huấn luyện: {result.get('samples', 0)}/{expected} mẫu đạt. "
                                   "Dữ liệu đã lưu; xem 02_audit/run-selection.csv và quality.json, không hạ ngưỡng chất lượng.")


if __name__ == "__main__":
    main()
