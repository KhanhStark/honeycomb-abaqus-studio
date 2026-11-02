# Kiểm tra sau khi sắp xếp workspace — 02/11/2026

## Phạm vi

Tài liệu trong repo được chia theo chủ đề; README và mục lục được viết lại. Các tệp rời, replay và cache trên máy được chuyển theo [sơ đồ workspace](../development/WORKSPACE_LAYOUT.md).

Mã nguồn ứng dụng, workflow, dependency và cấu hình chạy giữ nguyên. Thay đổi cục bộ có sẵn ở `scripts/linux_media/impact_test.py` được giữ trong working tree, không đưa vào commit tài liệu.

## Kết quả kiểm tra

| Kiểm tra | Kết quả |
| --- | --- |
| SHA-256 của 311 tệp Git ngoài Markdown so với trước khi sắp xếp | Không thay đổi |
| SHA-256 của 13 tệp CAE/ODB/INP/PDF/video sau khi chuyển | Khớp |
| Liên kết tương đối trong Markdown được rà soát | Không có đích bị thiếu |
| Thư viện dữ liệu, mô hình 7 J và executable của launcher/Task Scheduler | Đường dẫn tồn tại |
| Cú pháp script kiểm tra mô hình đối chiếu video | Hợp lệ |
| Bộ kiểm thử Python | **263 passed**, 1 cảnh báo dependency |
| `git diff --cached --check` | Đạt |

Lệnh kiểm thử chạy từ gốc repo:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
uv run --locked pytest -q -p no:cacheprovider
```

Cảnh báo đến từ FastAPI/Starlette về việc dùng `httpx` trong test client; không có test lỗi. Kiểm tra liên kết ở đây xác nhận đích cục bộ, không xác nhận trạng thái mọi URL Internet.

Script số hóa bài báo ngoài repo được sửa đường dẫn tới `research/papers/`; script kiểm tra mô hình đối chiếu video dùng vị trí của chính nó. Các thay đổi này chỉ sửa nơi đọc/ghi tệp. Không chạy lại solver hoặc thay dữ liệu số của nghiên cứu trong đợt sắp xếp.

Manifest nguồn/đích, checksum và báo cáo chi tiết nằm trong `C:/UET/DO_AN/local/archive/2026-11-02/`.
