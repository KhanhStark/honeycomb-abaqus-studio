"""Prefer the verified private Drive ISO; original mirror is used only before configuration."""

import argparse
import json
import os
from pathlib import Path

from honeycomb_studio.actions_log import get_actions_log
from honeycomb_studio.backup import SCOPES
from honeycomb_studio.media_cache import DriveDownloadError, ISO_NAME, download_iso, drive_failure_hint, preflight_drive_iso


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", action="store_true", help="Verify Drive authentication and pinned source before starting runners")
    args = parser.parse_args()
    file_id = os.getenv("ABAQUS_MEDIA_DRIVE_FILE_ID", "")
    if not file_id:
        if args.preflight:
            raise ValueError("Thiếu ABAQUS_MEDIA_DRIVE_FILE_ID để kiểm tra kho bộ cài trước khi chạy")
        from inspect_linux_media import main as original

        return original()
    if not os.getenv("HONEYCOMB_DRIVE_CREDENTIALS_JSON"):
        raise ValueError("Đã chọn kho ISO riêng nhưng thiếu cấu hình đăng nhập Drive")
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2.credentials import Credentials

    logger = get_actions_log()
    credentials = Credentials.from_authorized_user_info(json.loads(os.environ["HONEYCOMB_DRIVE_CREDENTIALS_JSON"]), SCOPES)
    target = Path(os.environ["RUNNER_TEMP"]) / "abaqus-media-inspection/iso" / ISO_NAME
    with AuthorizedSession(credentials) as session:
        if args.preflight:
            preflight_drive_iso(session, file_id)
            print("Drive OK: đăng nhập, quyền tải, kích thước và SHA-256 bộ cài đã xác minh; chưa khởi động runner mô phỏng.")
            return
        try:
            result = download_iso(session, file_id, target, logger=logger)
        except DriveDownloadError as exc:
            if exc.status_code != 403:
                raise
            from media_fallback import download_pinned_mirror
            if logger:
                logger.emit('RETRY', 'Drive refuses media transport; retrieve the original mirror and require the same pinned ISO SHA-256')
            result = download_pinned_mirror(target)
    output = Path("output/media-inspection")
    output.mkdir(parents=True, exist_ok=True)
    (output / "inspection.json").write_text(json.dumps({
        "kind": "pinned-iso-download", "source": result.get('transport_source', 'private_google_drive'),
        "iso": {"name": ISO_NAME, **result}, "passed_media_inventory": True,
        "publisher_authenticity_verified": False, "installer_executed": False,
        "verification": "Exact bytes and SHA-256 of the previously inventoried ISO; not a publisher signature",
    }, indent=2), encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Never print credential errors or resumable bearer URLs into public logs.
        logger = get_actions_log()
        if logger:
            logger.failure(type(exc).__name__, "Tải bộ cài", drive_failure_hint(exc))
        else:
            print(drive_failure_hint(exc))
        raise SystemExit(1) from None
