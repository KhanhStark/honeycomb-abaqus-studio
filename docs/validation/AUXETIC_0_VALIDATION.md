# Tích hợp lõi auxetic hình 1 — hướng 0°

Ngày kiểm tra: 25/10/2026. Cấu trúc mới chọn trong **Tạo job → Thông số mô hình → Hình học → Cấu trúc lõi → Tổ ong lõm (Re-entrant) — 0°**.

## Phạm vi

- Ô lõm XZ, đùn theo Y; cấu hình mặc định ô rộng 6,35 mm, cao 5 mm, lõm 1,25 mm mỗi bên.
- Vách xiên `foil`, vách ghép thẳng `2×foil`. Cấu hình ngoài lõi lấy từ input hiện tại, không tự đặt lại tải, vật liệu, ngàm hoặc đầu va.
- Chỉnh được chiều cao ô, độ lõm, bề rộng, dịch pha X/Z và seed chiều sâu Y; không áp dụng các biến hướng XY và số lớp Z của lõi lục giác.
- Design ID phân biệt topology và hình học ô. Cache ghi fingerprint của bộ tạo ô lõm; dataset nhận biết topology, kể cả dữ liệu lục giác cũ.
- Mật độ tuần hoàn ô lõm dùng diện tích/chiều dài vách của ô lõm. Khối lượng hữu hạn ghi sau khi dựng, có xét cắt biên và bỏ vách trùng mặt dán.

## Kiểm tra bằng Abaqus 2017 thật

Đầu vào và artifact tại `output/reentrant-0-integration-20261025/`. Bộ dựng dùng trực tiếp adapter của Studio với ModelSpec `core_topology=reentrant_0`.

| Kiểm tra | Kết quả |
|---|---|
| Tọa độ mạng lõi so với mô hình 0° đã chạy trước đó | Khớp toàn bộ từng đoạn vách |
| Tổng vách / vách đôi / vách đơn | 234 / 74 / 160 |
| Phần tử shell lõi / nút lõi | 105.000 / 101.404 |
| Phần tử mỗi mặt / đầu va | 9.875 / 6.709 |
| Khối lượng lõi | 22,635062 g |
| Datacheck | Hoàn tất thành công |
| Chồng lấn tiếp xúc ban đầu và chồng lấn chưa xử lý | Không có |
| Điều chỉnh tọa độ do chồng lấn ban đầu | Không có |

Đã kiểm tra nhánh cache bằng Abaqus/CAE thật: clone CAE từ 7 J sang 9 J, ghi CAE/INP thành công, phần `Honeycomb-Core` trong INP khớp nguyên vẹn và manifest ghi `cache_hit=true`. Đây là kiểm tra đổi tải và tái sử dụng lưới, không phải chạy solver đủ 6 ms ở 9 J.

Giữ loại trừ tiếp xúc cục bộ tại hàng phần tử đầu lõi đã tie với mặt tương ứng. Tự tiếp xúc phần lõi vẫn hoạt động. Cảnh báo OP=NEW và seam vùng tie còn trong log như mô hình nền.

Đây là kiểm tra tích hợp dựng hình và khởi tạo; **không chạy lại một ca va đập đầy đủ trong lượt tích hợp này**. Kết quả 6 ms đã chạy trước đó nằm ngoài repo tại `../mo_phong/Auxetic-2-orientations-7J/01_image1_0deg/`. Chưa xác nhận hội tụ lưới hoặc tương đương thí nghiệm của lõi mới.

## Kiểm tra giao diện

Bản đóng gói `artifacts/HoneycombStudio-auxetic-0-win-x64/` đã được mở qua launcher Windows. Tên giao diện lúc kiểm tra là **Auxetic hình 1 — 0°**, hiện đổi thành **Tổ ong lõm (Re-entrant) — 0°**. Đã nhập danh sách năng lượng `[7]` và kiểm tra preview hợp lệ: một lượt, `core_topology=reentrant_0`, `core_cell_plane=XZ`, chiều cao ô 5 mm, độ lõm 1,25 mm. Không tạo batch hay khởi chạy solver từ giao diện trong lần kiểm tra tích hợp đó.

Kiểm thử mã nguồn: 69 bài pytest đạt, 9 bài C# đạt; Ruff và kiểm tra kiểu đạt, WinUI build/publish không có lỗi hay cảnh báo biên dịch.

![Lõi auxetic 0° trong Studio](../evidence/auxetic-0-studio-20261025.jpg)

Shortcut Desktop dùng `scripts/start-independent.ps1`; launcher và hai tác vụ mở thủ công của Studio đã trỏ sang gói mới. Dữ liệu hai job cũ, 14 lượt hoàn tất được giữ nguyên.
