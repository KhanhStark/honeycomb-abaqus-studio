"""Observed native execution and formal production qualification are separate states."""

import json
import os
import re
from pathlib import Path


def technical_evidence():
    """Observed trials used by the experimental lane, never formal certification."""
    path = Path(__file__).with_name("runtime-evidence.json")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def execution_runtime():
    """The owner-requested observed native runtime, distinct from certification.

    Installation hashes and network/solver checks still run on every runner.
    No production qualification or license entitlement is inferred here.
    """
    data = technical_evidence()
    required = ("solver_success", "odb_reopened", "cae_checkout", "explicit_checkout")
    if not all(data.get(key) is True for key in required):
        return {}, [{"status": "blocked_environment", "message": "Chưa có lượt thử Linux hoàn tất solver và mở lại ODB."}]
    return {
        "mode": "native_container", "release": "2020", "python": data["python"],
        "continuation_parallel_mode": "MPI", "continuation_domains": 4,
        "installer_sha256": "d0b227290b5f62ea826b08c18bde222417817fc0d04b91abb0072cb52ebe43ad",
        "production_runtime_qualified": False,
        "media_publisher_authenticity_verified": data.get("media_publisher_authenticity_verified", False),
        "license_entitlement_verified": data.get("license_entitlement_verified", False),
        "evidence_url": data["smoke_url"],
    }, []


def qualification(path=None):
    path = Path(path) if path else Path(__file__).with_name("runtime-lock.json")
    reasons = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    runtime_ok = all(data.get(k) for k in ("release", "python", "image_digest"))
    runtime_ok = runtime_ok and bool(re.fullmatch(r"[a-f0-9]{64}", str(data.get("installer_sha256", ""))))
    smoke = data.get("smoke_receipt", {})
    if not isinstance(smoke, dict):
        smoke = {}
    runtime_ok = runtime_ok and smoke.get("solver_success") is True and smoke.get("platform") == "linux"
    runtime_ok = runtime_ok and smoke.get("odb_reopened") is True
    runtime_ok = runtime_ok and data.get("media_publisher_authenticity_verified") is True
    runtime_ok = runtime_ok and str(smoke.get("evidence_url", "")).startswith("https://github.com/")
    if not runtime_ok:
        reasons.append(
            {
                "status": "blocked_environment",
                "message": "Đã có thử nghiệm Linux thật; runtime chính thức còn thiếu xác minh nguồn bộ cài và lock được nghiệm thu.",
            }
        )
    license = data.get("license_receipt", {})
    if not isinstance(license, dict):
        license = {}
    features = license.get("features", [])
    if not isinstance(features, list) or not all(isinstance(f, str) for f in features):
        features = []
    if not (
        runtime_ok
        and license.get("linux_checkout") is True
        and set(features) >= {"cae", "explicit"}
        and license.get("entitlement_verified") is True
        and str(license.get("authorization_evidence_url", "")).startswith("https://")
        and str(license.get("evidence_url", "")).startswith("https://github.com/")
    ):
        reasons.append(
            {
                "status": "blocked_license",
                "message": "CAE/Explicit đã checkout trong thử nghiệm; quyền sử dụng license cho Linux/cloud chưa được xác minh.",
            }
        )
    if not os.getenv("PLATFORM_POLICY_EVIDENCE_URL", "").startswith("https://"):
        reasons.append(
            {
                "status": "blocked_platform_policy",
                "message": "Chưa xác nhận phạm vi dùng Actions cho backend nghiên cứu đầy đủ.",
            }
        )
    return data, reasons
