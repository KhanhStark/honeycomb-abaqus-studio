# Kết quả kiểm tra bản 0.1.0

Ngày thực hiện: 21/10/2026. Máy Windows x64, Intel i7-12700H, RAM khoảng 16 GiB; Abaqus/Explicit 2017, Python Abaqus 2.7.3 / NumPy 1.6.2. Không sửa ODB/CAE tham chiếu gốc.

## Phần mềm

- 36 kiểm thử Python: khoảng/bước nhảy, LHS, bảng vật liệu, đổi E/v/m, điều phối ba lượt dừng/tiếp tục, phục hồi, hậu xử lý không chạy lại solver, license, lỗi backup, Parquet, checksum/ZIP/restore và chống rò rỉ dataset.
- `ruff check` và `ty check` engine Python hiện đại: đạt. Adapter Python 2.7 được tách khỏi công cụ Python 3.
- 4 kiểm thử hợp đồng C#: đạt. Build và publish WinUI x64 thực hiện trên máy thật.
- Runtime Python đóng gói được kiểm tra ở chế độ isolated (`-I`); import engine/PyArrow/NumPy/DPAPI từ thư mục phát hành, không từ editable source.
- Kiểm tra cây tiến trình: nhận diện child còn sống sau launcher kết thúc và chỉ dừng child có PID/creation time đã ghi.
- UI thật đã mở, kết nối engine độc lập, tải reference, hiển thị input và đường cong. Đóng UI giữ engine.

## ODB tham chiếu 7 J

Nguồn: `Honeycomb-paper-7J/Honeycomb-7J-run.odb`, mở read-only rồi nhập bản sao vào thư viện.

| Phép đo | Kết quả |
|---|---:|
| Số frame | 121 |
| Lực đỉnh từ m(A3+g) | 2.842,7550375 N |
| Hành trình viên lớn nhất từ đầu bước | 4,5661344528 mm |
| Độ võng tâm mặt trên | 4,4695701599 mm |
| Drift ETOTAL cực đại / KE ban đầu | 0,08061536% |
| max ALLAE / max ALLIE | 4,52209037% |
| Field/frame có dữ liệu | 1.816 |
| File Parquet field | 13.800 |
| Tổng bản ghi field | 180.200.225 |

Đối chiếu inventory ODB với số dòng Parquet từng field/frame không có sai khác. Vector/tensor, component, section point và integration point được giữ. 12 mẫu U/S/PEEQ ở nhiều instance, node/element, integration point và section point đã đối chiếu trực tiếp bằng FieldValue từ ODB với dữ liệu Parquet: đạt rtol 1e-6, atol 1e-8 và component khớp. Hồ sơ nhỏ nằm tại `docs/evidence/`.

PDF từng lượt và toàn job đã được mở bằng trình đọc PDF, render trang và kiểm tra tiếng Việt, phân trang, bảng trường, đồ thị và contour. PDF không thay thế dữ liệu nút/phần tử đầy đủ trong Parquet.

## Hội tụ lưới và thời gian

Ba mức lưới quick/reference/fine được chạy ở 7 J, 6 ms trong thư viện riêng `C:/UET/DO_AN/honeycomb-validation`. Chỉ công bố hội tụ khi cả ba ca và so sánh hoàn tất.

Ca quick đã hoàn tất solver và hậu xử lý: lực đỉnh 2.960,5554875 N; độ võng tâm trên 4,2312784195 mm; drift 0,03787673%; tỷ lệ năng lượng nhân tạo 4,98309970%. CPU time solver ghi trong STA là 16 phút 32 giây. Ca reference mới đã hoàn tất, tái tạo đúng lực đỉnh 2.842,7550375 N, hành trình viên 4,5661344528 mm và 121 frame. Wall time solver đo được 1.998,06 s (33,30 phút), trích xuất 635,12 s (10,59 phút). Thời gian bị ảnh hưởng tải máy/RAM; bản đo này đã được nhập vào calibration.json của thư viện hiện tại để dự báo và cảnh báo vượt ngân sách 30 phút. Ca fine đang được tính, chưa kết luận hội tụ.

Kết quả này chưa chứng minh tương đương thí nghiệm. Tất cả preset vẫn mang nhãn chưa xác nhận hội tụ. Ngân sách 20–30 phút chỉ tính solver; trích xuất mọi field có thể cần thêm nhiều phút và dung lượng lớn.

## Những kiểm tra cần tài khoản/máy nghiên cứu

- Drive thật: đã xác nhận tài khoản đăng nhập đúng tài khoản người dùng yêu cầu; upload job tổng hợp 25.242.407 byte, chủ động ngắt client sau khi server nhận 8 MiB, tiếp tục cùng phiên từ byte 8.388.608, đối chiếu size/MD5, tải về và khôi phục với SHA-256, checksum từng file, input và trạng thái chất lượng được giữ. Đây là gián đoạn client có kiểm soát trên dịch vụ thật, chưa phải thử ngắt mạng vật lý. Job tổng hợp luôn bị loại khỏi dữ liệu ML. Hồ sơ: `docs/evidence/drive-acceptance.json`; lệnh chạy lại: `scripts/validate_drive.py --root <thư-mục-thử-riêng> --account <email>` sau đăng nhập OAuth.
- Khởi động lại Windows thật chưa được thực hiện vì máy đang chạy công việc khác. Bộ kiểm thử kiểm tra phục hồi ownership và các trạng thái gián đoạn; cần nghiệm thu mất điện/reboot có kiểm soát trước một chiến dịch dài.
- Dừng/tiếp tục ba lượt đã kiểm tra với solver giả lập. Kiểm thử gián đoạn solver Abaqus thật phải thực hiện trong thư viện thử riêng, không trên dữ liệu nghiên cứu đang chạy.

Không đổi các mục chưa kiểm tra thành “đạt”. Dữ liệu numerical-quality passed vẫn có physical-validation not_established.

## Bản 0.2.0: báo cáo và dữ liệu nghiên cứu gọn

PDF tham chiếu được tạo lại thành 5 trang và render kiểm tra đủ 5 trang. Chế độ giảm gọn đã đọc 121 frame, xử lý 66.361.845 mẫu của 605 cặp field/frame, đối chiếu không sai lệch; lực đỉnh và cực trị U/PEEQ/von Mises khớp bản xuất toàn trường. Dữ liệu dẫn xuất khoảng 6,0 MB (không tính ODB/ảnh/PDF), thời gian 117,54 s trên máy hiện tại. Hồ sơ tại docs/evidence/research-profile.json. Các phép đo này là kiểm tra trích xuất, không xác nhận hội tụ/thí nghiệm.
