# API cục bộ v1

Engine bind 127.0.0.1, cổng ngẫu nhiên. Mọi endpoint trừ `/health` cần header `X-Honeycomb-Token` từ file session của người dùng hiện tại. Không log token. OpenAPI xem qua client có header tại `/openapi.json`; schema BatchSpec trong contracts.

| Endpoint | Công dụng |
|---|---|
| GET /v1/status | Tài nguyên, vị trí dữ liệu, solver, backup |
| GET /v1/template | Spec nền, catalogue tham số và JSON schema |
| POST /v1/resolve | ModelSpec → input thực tế, đơn vị và bảng dẻo |
| POST /v1/preview | BatchSpec → danh sách lượt và dự toán, chưa ghi dữ liệu |
| POST /v1/batches | Tạo job/input bất biến, chưa chạy |
| GET /v1/batches, /v1/batches/{id} | Danh mục và các lượt |
| POST /v1/batches/{id}/start,resume,stop,pause_after_current | Điều phối |
| GET /v1/runs?q=&status= | Tìm kiếm thư viện |
| GET /v1/runs/{id} | Input, attempt, output, quality, artifact |
| POST /v1/runs/{id}/retry | Chạy lại riêng lượt / hậu xử lý lỗi |
| GET /v1/runs/{id}/history,logs | Đường cong và log |
| POST /v1/runs/{id}/open/{odb,cae,pdf,folder} | Mở artifact đúng lượt |
| POST /v1/import-reference | Copy ODB/CAE/INP tham chiếu chỉ đọc nguồn và đăng ký |
| POST /v1/import-designs | Nhập CSV; tên cột là dotted parameter path |
| POST /v1/batches/{id}/report/export?format=pdf hoặc docx | Báo cáo toàn job và run index; mặc định PDF |
| POST /v1/runs/{id}/report/export?format=pdf hoặc docx | Báo cáo từng lượt; mặc định PDF |
| POST /v1/batches/{id}/dataset/export | ZIP dữ liệu huấn luyện mọi lượt đủ điều kiện trong job; job-coverage.csv ghi nhận mọi lượt và lý do loại |
| POST /v1/batches/{id}/archive/export | ZIP64 job |
| POST /v1/runs/{id}/archive/export | ZIP64 lượt |
| POST /v1/runs/{id}/fields/csv?field= | CSV mọi field hoặc field chọn |
| POST /v1/datasets/{id}/archive/export | ZIP64 dataset, dictionary và đường cong |
| GET /v1/runs/{id}/fields/csv/preview | Số dòng và dự toán dung lượng CSV trước khi xuất |
| POST /v1/datasets | run_ids, name, seed, features, targets |
| GET /v1/datasets, /v1/pareto | Danh mục dataset / Pareto theo điều kiện tải |
| GET /v1/events?after= | Sự kiện tăng dần, cursor seq |
| GET /v1/events/stream?after= | SSE có heartbeat và event ID |
| GET /v1/operations/{id} | Trạng thái thao tác hậu xử lý nền |
| GET /v1/backup | Kết nối và các phiên upload |
| POST /v1/backup/connect | path tới OAuth client JSON |
| POST /v1/backup/check | Kiểm tra credential, kết nối và quota Drive chỉ đọc; trả operation |
| POST /v1/backup/batches/{id} | Xếp backup |
| POST /v1/backup/batches/{id}/readable | Bổ sung PDF và dataset dạng tệp thường trên Drive, không upload lại ZIP |
| GET /v1/retained | Danh sách bản giữ lại ngoài data root và link/checksum Drive |
| POST /v1/backup/resume/{id} | Tiếp tục phiên upload |
| POST /v1/backup/restore-local | path ZIP |
| POST /v1/backup/restore-drive | file_id + sha256 |
| POST /v1/catalog/reindex | Xây lại SQLite từ manifest |

Long operation trả `{id,kind,status}`; poll operation để lấy result/error. Input không hợp lệ trả 400/422; ID không tồn tại 404. Path mở artifact bị giới hạn trong data root; CAE/ODB chỉ mở qua run API.

Với `sampling=table`, mỗi dòng được kiểm tra theo chế độ nhập sau khi áp dụng toàn bộ override của dòng đó. Ví dụ, dòng đặt `energy_J` phải dùng `loading=energy` (kế thừa từ model hoặc đặt ngay trong dòng). Tham số không hoạt động bị từ chối kèm số dòng, trước khi tạo job; không âm thầm bỏ qua rồi khử trùng lượt.

`QualityReport.physical_validation=environment_smoke_only` dành cho kiểm tra môi trường native ngắn; payload này có `ml_eligible=false`. Schema công khai chấp nhận trạng thái này cùng các trạng thái cũ. Smoke không xác nhận vật lý của mô hình.

Tên batch/job của người dùng không được nội suy thành lệnh shell. Tham số mô phỏng đi qua JSON; tên file kỹ thuật do engine tạo. File session và URL resumable không đưa ra log/backup công khai.
