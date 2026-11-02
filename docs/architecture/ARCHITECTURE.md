# Kiến trúc và quyết định kỹ thuật

## Ranh giới tiến trình

WinUI 3 (.NET 10) giao tiếp HTTP/JSON với engine Python 3.13 trên loopback, bằng token trong header `X-Honeycomb-Token`. File discovery nằm tại `%LOCALAPPDATA%/HoneycombStudio/session.json`. Engine có khóa phiên người dùng; UI không làm chủ vòng đời solver.

Engine quản lý SQLite, input bất biến, hàng đợi tuần tự, tài nguyên, artifact, Parquet, biểu đồ/PDF và Drive. Chỉ adapter chạy trong Abaqus Python 2.7.3. Dựng CAE/render dùng `abaqus cae noGUI=...`; đọc kết quả dùng `abaqus python ...`; solver dùng Explicit interactive để theo dõi tiến trình đến khi kết thúc.

Mỗi tiến trình lưu PID, creation time, command và phase. Không kết luận process còn đúng chỉ từ PID. Lệnh terminate áp dụng cho job thuộc attempt hiện tại; fallback chỉ kết thúc cây tiến trình có ownership khớp.

## Bất biến dữ liệu

- BatchSpec version 1 được mở rộng và kiểm tra toàn bộ trước khi tạo thư mục.
- RunSpec gồm requested/resolved input, input hash và physical design ID.
- Attempt riêng cho mỗi lần solver thực thi. Hậu xử lý lỗi tái sử dụng solver output đã xác nhận thành công.
- SQLite phục vụ tìm kiếm; batch.json/run.json/input/artifact manifests đủ để xây lại index.
- Cập nhật file JSON bằng ghi file tạm rồi replace; thứ tự chạy dựa vào index lượt, không dựa SQLite rowid.

## Trích xuất lớn

Adapter mở ODB read-only. Bulk data cho trường single precision; FieldValue fallback cho double precision. Các khối NPZ chỉ chứa numeric/unicode arrays, không dùng object pickle; .ready được công bố sau khi đóng NPZ. Backpressure giới hạn số khối chưa tiêu thụ.

Engine đọc mỗi khối với allow_pickle=False, ghi Parquet Zstd, kiểm tra số dòng trước khi công bố và xóa khối trung gian. Vector/tensor lưu dạng list; section/integration point và instance không bị gộp mất. Quaternion gốc của bulk access và cơ sở 3×3 của FieldValue được phân biệt.

Sau khi kết thúc, đối chiếu tổng số dòng của từng field/frame với inventory ODB. Retry trích xuất chưa hoàn tất giữ bản cũ trong postprocess-history rồi tạo vùng xuất mới, tránh trộn file của hai lần chạy.

## Điều phối

Queued → Building → Checking → Solving → Extracting → Rendering → Reporting → Completed/Review. Failed ghi failed_phase; Interrupted giữ attempt và input. Backup có state machine riêng. Resume chỉ đưa lượt gián đoạn về hàng đợi; kết quả đã hoàn tất không đổi.

Cache dựng mô hình dùng hash resolved input không bao gồm năng lượng/vận tốc độc lập và hash mã adapter. Clone mở bản CAE cache, cập nhật initial velocity và ghi CAE/INP riêng, không sửa cache. Mọi thay đổi hình học, vật liệu, lưới hoặc cài đặt khác làm cache key đổi.

## Nguồn sự thật

Input JSON phiên bản hóa là hợp đồng với adapter; model_manifest bổ sung thông số đo sau dựng. ODB là nguồn kết quả gốc. Summary chứa định nghĩa phép đo; QualityReport tách numerical quality khỏi physical validation. ArtifactManifest ghi checksum và kích thước, không chứa credential.

Mỗi attempt mới lưu phiên bản engine và SHA-256 mã nguồn engine/adapter. Mỗi lần hậu xử lý có fingerprint riêng; thay đổi bộ đọc/báo cáo không xóa provenance dựng/solver. Manifest ZIP được đối chiếu với chính các byte ghi vào ZIP; nếu file nguồn thay đổi trong lúc đóng gói, thao tác báo lỗi thay vì chứng nhận gói không nhất quán.

Từ 0.2.0, export_all_fields mặc định false: adapter chỉ duyệt U/S/PEEQ và lực tiếp xúc; engine giảm từng khối thành thống kê/cực trị có vị trí rồi giải phóng NPZ. Inventory và bộ kiểm tra so số mẫu đã xử lý, không gọi JSON giảm gọn là bản xuất field đầy đủ. PDF/dataset là sản phẩm biên tập riêng với kho ODB.
