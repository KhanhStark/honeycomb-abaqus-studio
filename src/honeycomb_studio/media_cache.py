"""Private reusable installer ISO; the pinned hash does not prove publisher authenticity."""

import hashlib
import re
import time
from pathlib import Path

import requests

ISO_NAME = "DS.SIMULIA.Suite.2020.Linux64_Softgozar.com.iso"
DRIVE_NAME = "SIMULIA_Abaqus_2020_Linux64.iso"
ISO_BYTES = 10066642944
ISO_SHA256 = "d0b227290b5f62ea826b08c18bde222417817fc0d04b91abb0072cb52ebe43ad"
MEDIA_KEY = "abaqus2020-linux-" + ISO_SHA256[:16]


class DriveDownloadError(RuntimeError):
    def __init__(self, status_code):
        self.status_code = status_code
        super().__init__('Drive download HTTP ' + str(status_code))


def preflight_drive_iso(session, file_id):
    """Refresh authentication and verify private source metadata before fan-out."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{10,128}", file_id):
        raise ValueError("Mã file Google Drive không hợp lệ")
    response = session.get("https://www.googleapis.com/drive/v3/files/" + file_id,
                           params={"fields": "size,sha256Checksum,trashed,capabilities(canDownload)"}, timeout=30)
    if response.status_code != 200:
        raise RuntimeError(f"Kiểm tra kho bộ cài Drive thất bại (HTTP {response.status_code})")
    info = response.json()
    if info.get("trashed") or info.get("capabilities", {}).get("canDownload") is not True:
        raise ValueError("Bộ cài Drive đã bị xóa hoặc tài khoản không có quyền tải")
    if int(info.get("size", -1)) != ISO_BYTES or info.get("sha256Checksum") != ISO_SHA256:
        raise ValueError("Metadata bộ cài Drive không khớp kích thước/SHA-256 đã ghim")
    return {"bytes": ISO_BYTES, "sha256": ISO_SHA256, "download_allowed": True}


def drive_failure_hint(exc):
    """Only allowlisted OAuth codes reach public logs, never provider payloads."""
    if isinstance(exc, DriveDownloadError):
        return f'Drive HTTP {exc.status_code}: kiểm tra quyền tải hoặc thử lại khi dịch vụ ổn định'
    if isinstance(exc, requests.RequestException):
        return 'Kết nối tải Drive bị gián đoạn; đã thử tải lại có kiểm tra offset và SHA-256'
    if type(exc).__name__ == "RefreshError":
        code = next((a.get("error") for a in exc.args if isinstance(a, dict)), None)
        if code in ("invalid_grant", "invalid_client", "access_denied"):
            return f"Drive OAuth {code}: đăng nhập lại Drive và cập nhật secret HONEYCOMB_DRIVE_CREDENTIALS_JSON trên GitHub"
        return "Không làm mới được phiên Drive; kiểm tra đăng nhập OAuth và kết nối Google"
    return "Kiểm tra quyền tải bộ cài Drive, dung lượng và checksum đã ghim"


def verify_iso(path, *, expected_bytes=ISO_BYTES, expected_sha256=ISO_SHA256):
    if path.stat().st_size != expected_bytes:
        raise ValueError("Kích thước ISO không khớp bản đã thử nghiệm")
    sha, md5 = hashlib.sha256(), hashlib.md5(usedforsecurity=False)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b""):
            sha.update(block)
            md5.update(block)
    if sha.hexdigest() != expected_sha256:
        raise ValueError("SHA-256 của ISO không khớp; không được chạy bộ cài")
    return {"bytes": expected_bytes, "sha256": sha.hexdigest(), "md5": md5.hexdigest()}


def download_iso(session, file_id, destination: Path, *, logger=None,
                 expected_bytes=ISO_BYTES, expected_sha256=ISO_SHA256):
    if not re.fullmatch(r"[A-Za-z0-9_-]{10,128}", file_id):
        raise ValueError("Mã file Google Drive không hợp lệ")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        return verify_iso(destination, expected_bytes=expected_bytes, expected_sha256=expected_sha256)
    partial = destination.with_suffix(destination.suffix + ".part")
    transfer = logger.transfer("Tải trực tiếp ISO từ Google Drive riêng", expected_bytes) if logger else None
    count, digest = 0, hashlib.sha256()
    try:
        for attempt in range(3):
            try:
                headers = {'Range': f'bytes={count}-'} if count else {}
                with session.get("https://www.googleapis.com/drive/v3/files/" + file_id,
                                 params={"alt": "media"}, headers=headers,
                                 stream=True, timeout=(30, 120)) as response:
                    if response.status_code != (206 if count else 200):
                        raise DriveDownloadError(response.status_code)
                    if count:
                        span = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', response.headers.get('Content-Range', ''))
                        if (not span or int(span[1]) != count or int(span[3]) != expected_bytes
                                or not count <= int(span[2]) < expected_bytes):
                            raise ValueError('Drive returned an invalid resume offset or media size')
                    with partial.open('ab' if count else 'wb') as output:
                        for block in response.iter_content(8 * 1024**2):
                            count += len(block)
                            if count > expected_bytes:
                                raise ValueError("ISO tải về vượt kích thước đã ghim")
                            output.write(block)
                            digest.update(block)
                            if transfer:
                                transfer.advance(len(block))
                break
            except (requests.RequestException, DriveDownloadError) as exc:
                if (attempt == 2 or isinstance(exc, DriveDownloadError)
                        and exc.status_code not in (429, 500, 502, 503, 504)):
                    raise
                if logger:
                    logger.emit('RETRY', f'Drive: thử {attempt + 2}/3 từ byte {count}; ' + drive_failure_hint(exc))
                time.sleep(2 ** attempt)
        if count != expected_bytes or digest.hexdigest() != expected_sha256:
            raise ValueError("ISO tải về không khớp kích thước/SHA-256; không được chạy bộ cài")
        partial.replace(destination)
        if transfer:
            transfer.verified()
        return {"bytes": count, "sha256": digest.hexdigest()}
    finally:
        partial.unlink(missing_ok=True)
