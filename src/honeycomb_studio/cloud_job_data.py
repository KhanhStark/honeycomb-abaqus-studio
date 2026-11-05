"""Publish one readable collection and one complete downloadable folder per parent job."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from .cloud_archive import ReleaseArchive
from .cloud_github import REPOSITORY
from .cloud_restore import validate_manifest
from .data import checksum, manifest
from .job_data import full_manifest, job_folder, standalone_downloader
from .models import digest
from .store import write_json
from .training_collection import build_collection

BUILDER_VERSION = "job-folder-v5-history-audit"


def publish_job_data(github, catalog, sources, release, *, workflow, attempt, full, root):
    identity = sources[0]["job_id"]
    job = sources[0]["job"]
    fingerprint = digest({"builder": BUILDER_VERSION, "sources": [
        {k: s.get(k) for k in ("shard_id", "manifest_sha256", "status", "excluded_reason")}
        for s in sources]})
    cached, _ = catalog.get("training/jobs/" + identity)
    # Refreshes must not remove an existing full-download capability when the
    # caller only requests lightweight data for another job.
    full = full or bool(cached and cached.get("full_bundle"))
    if (cached and cached.get("source_fingerprint") == fingerprint
            and (not full or cached.get("full_bundle"))):
        return {k: v for k, v in cached.items() if k != "files"}
    if release is None:
        raise ValueError("Source changed after reservation; retry collection on current main")
    folder = job_folder(identity, job["name"])
    publisher = ReleaseArchive(github, release["id"], tag=release["tag_name"])
    with tempfile.TemporaryDirectory(prefix="job-data-", dir=root) as temp:
        temporary = Path(temp)
        readable = temporary / "readable" / folder
        summary = build_collection(sources, readable, single_job=True)
        original = full_manifest(sources)
        write_json(readable / "02_audit/full-source-manifest.json", original)
        manifest(readable)
        readable_zip = Path(shutil.make_archive(str(temporary / "readable-data"), "zip", readable.parent, folder))
        uploaded = publisher.upload(readable_zip, "readable-data.zip")
        artifacts = {"zip_url": uploaded["url"]}
        for relative, name in (("01_training/samples.csv", "samples.csv"),
                               ("01_training/samples.parquet", "samples.parquet"),
                               ("01_training/dataset.json", "dataset.json"),
                               ("02_audit/full-source-manifest.json", "full-source-manifest.json"),
                               ("README.md", "README.md")):
            artifacts[name] = publisher.upload(readable / relative, name)["url"]
        complete_bundle = None
        if full:
            # Reference immutable, verified source parts instead of downloading,
            # compressing and uploading every ODB again after a selective retry.
            readable_bytes = readable_zip.stat().st_size
            readable_sha = checksum(readable_zip)
            package = {**original, "storage_mode": "direct-source-parts", "folder": folder,
                       "readable_prefix": folder + "/00_dataset_versions/" + fingerprint[:16],
                       "files": original["files"] + [{
                           "path": folder + "/00_dataset_versions/" + fingerprint[:16] + "/readable-data.zip", "role": "readable",
                           "bytes": readable_bytes, "sha256": readable_sha,
                           "parts": [{"index": 0, "offset": 0, "bytes": readable_bytes,
                                      "sha256": readable_sha, **uploaded}]}]}
            validate_manifest(package, allow_incomplete=True)
            write_json(temporary / "full-download.json", package)
            script = temporary / "download_full.py"
            script.write_text(standalone_downloader(package), encoding="utf-8")
            complete_bundle = {
                "manifest_url": publisher.upload(temporary / "full-download.json", "full-download.json")["url"],
                "helper_url": publisher.upload(script, "download_full.py")["url"],
                "storage_mode": "direct-source-parts",
                "bytes": sum(f["bytes"] for f in package["files"]),
                "parts": sum(len(f["parts"]) for f in package["files"]), "zip_url": None,
                "source_complete": original["complete"], "manifest_sha256": checksum(temporary / "full-download.json"),
            }
        # The folder browser lists readable files and every original solver file.
        files = [{"path": f["path"], "bytes": f["bytes"], "sha256": f["sha256"], "kind": "solver"}
                 for f in original["files"]]
        readable_manifest = json.loads((readable / "artifact-manifest.json").read_text(encoding="utf-8"))
        files += [{"path": folder + "/" + f["path"], "bytes": f["bytes"],
                   "sha256": f["sha256"], "kind": "readable"} for f in readable_manifest["files"]]
        published = github.repo("PATCH", f"/releases/{release['id']}", {
            "draft": False, "prerelease": True,
            "body": f"Một job web, một thư mục {folder}. {summary['runs']} lượt có hồ sơ, "
                    f"{summary['samples']} mẫu đạt huấn luyện. "
                    "readable-data.zip: đầu vào/đầu ra, đường cong, X/y và kiểm tra chất lượng. "
                    + ("Tải trực tiếp ODB/CAE/INP, logs, báo cáo và field từ nguồn đã lưu; "
                       "chạy py download_full.py để gom một thư mục, tái sử dụng phần đã xác minh. " if full else
                       "Bản đầy đủ được tham chiếu bởi full-source-manifest.json. ")
                    + ("Tất cả nguồn hoàn tất." if original["complete"] else
                       "Một số nguồn thiếu/chưa hoàn tất; xem source-jobs.json, không coi là job đầy đủ."),
        })
        record = {**summary, "id": identity, "name": job["name"], "folder": folder,
                  "builder_version": BUILDER_VERSION, "source_fingerprint": fingerprint,
                  "source_status": job["status"], "workflow_run_id": job.get("workflow_run_id"),
                  "source_complete": original["complete"], "release_url": published["html_url"],
                  "workflow_url": f"https://github.com/{REPOSITORY}/actions/runs/{job['workflow_run_id']}",
                  "collection_workflow_url": f"https://github.com/{REPOSITORY}/actions/runs/{workflow}",
                  "zip_url": artifacts["zip_url"], "csv_url": artifacts["samples.csv"],
                  "parquet_url": artifacts["samples.parquet"],
                  "full_manifest_url": artifacts["full-source-manifest.json"], "full_bundle": complete_bundle,
                  "files": files, "file_count": len(files), "solver_bytes": sum(f["bytes"] for f in original["files"])}
        catalog.update("training/jobs/" + identity, lambda old: record)
        return {k: v for k, v in record.items() if k != "files"}
