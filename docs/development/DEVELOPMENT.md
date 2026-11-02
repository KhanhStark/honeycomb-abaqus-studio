# Phát triển và phát hành

## Cấu trúc repo

- `desktop/HoneycombStudio`: WinUI 3, MVVM state, HTTP client, form tham số, job monitor, thư viện/Drive và ScottPlot.
- `src/honeycomb_studio`: schema, DOE, SQLite, engine, trích xuất, báo cáo, backup và local API/CLI.
- `src/honeycomb_studio/adapters`: Python 2.7 chạy trong Abaqus; không dùng Python hiện đại để sửa/format nâng cấp cú pháp các file này.
- `contracts`: schema v1 và catalogue tham số; `examples`: cấu hình nghiên cứu nhỏ.
- `tests`: acceptance/unit tests Python và C#; `scripts`: setup/start/test/publish/real solver acceptance.

## Công cụ

`uv sync --locked`, `uv run ruff check src tests scripts`, `uv run pytest`. Khi thêm dependency dùng `uv add`; commit uv.lock. Adapter không import Pydantic, PyArrow hoặc thư viện Python 3.

WinUI dùng SDK trong global.json và dependency NuGet được khóa bằng packages.lock.json. `dotnet build ... -c Release -p:Platform=x64`; C# contract tests chạy không cần mở cửa sổ.

CI Windows kiểm thử engine bằng solver test-only; không giả định GitHub-hosted runner có Abaqus/license. Tất cả thông tin simulation thật thuộc acceptance records trên máy nghiên cứu.

## Thay đổi hợp đồng

Thêm input phải đi xuyên ModelSpec → resolved → adapter → model_manifest → UI/schema → docs/tests. Không chỉ thêm textbox rồi bỏ qua ở solver. Đổi phép lấy target phải ghi phiên bản extractor và cập nhật data dictionary. Đổi input vật lý làm input hash/design grouping phù hợp; đổi mã dựng làm cache invalid.

## Bản phát hành

`scripts/publish.ps1` tạo WinUI self-contained x64 và runtime Python riêng với dependencies khóa; người dùng không cần cài Python riêng cho bản phát hành. Abaqus vẫn là prerequisite riêng.

Bản phát hành được lưu trong artifacts, không commit binary. Chạy smoke từ runtime đã đóng gói để xác nhận không phụ thuộc editable path/source repo. Signing certificate/code signing chưa là prerequisite để chạy bản unpackaged nội bộ; không tự tạo chứng thư tin cậy trên máy người dùng.

Credential OAuth, token session, ODB, CAE, training data và log lớn đều nằm ngoài Git. Khi thay đổi docs/contract, chạy lại kiểm thử liên quan; kiểm thử khoa học chỉ chạy lại khi thay đổi mô hình hoặc khi nghiệm thu preset.

Đóng gói WinUI cần target `PublishProjectResources`: WindowsAppSDK bỏ sót project PRI trên luồng unpackaged publish ([upstream #6720](https://github.com/microsoft/WindowsAppSDK/issues/6720)). Target kiểm tra và sao chép PRI từ TargetDir; không bỏ qua kiểm tra mở ứng dụng sau publish. Tái tạo schema bằng `uv run python scripts/export_contracts.py`.

Nhập timing đo trên cùng máy từ catalog thử nghiệm: `uv run python scripts/calibrate_estimates.py --source C:/UET/DO_AN/honeycomb-validation --target C:/UET/DO_AN/honeycomb-data`. Calibration không đổi lưới/vật lý; dự báo vẫn có khoảng heuristic theo tải máy. Adapter/Python thực đã kiểm tra đường dẫn cấu hình có khoảng trắng qua bộ launcher Windows.
