# Nghiệm thu

## Tự động, không cần Abaqus

- Khoảng Decimal chia hết/không chia hết, điểm cuối, một điểm, bước sai và giới hạn tổ hợp.
- E/v/m và hệ đơn vị; mật độ lõi suy ra; vật liệu và hình học sai bị chặn.
- LHS có seed; cùng thiết kế khác tải/lưới chung grouping.
- Dừng ở lượt hai của ba lượt: giữ lượt một, attempt mới cho lượt hai, lượt ba chạy tiếp.
- Local API token, preview không mutation, tìm ID và giới hạn mở file.
- Parquet roundtrip giữ vector/section/integration point và phát hiện số dòng sai.
- Quality số độc lập physical validation; loại failed/review khỏi dataset mặc định.
- Chia nhóm train/test, loại attempt trùng; ZIP checksum và chống path traversal.
- C# đọc đúng snake_case/đơn vị/progress, giữ lỗi API và truyền Unicode input.

## Cần Abaqus/license tại máy nghiên cứu

`uv run python scripts/validate_abaqus.py --smoke`: dựng/datacheck/solver ngắn, chỉ xác nhận đường chạy kỹ thuật.

`uv run python scripts/validate_abaqus.py --convergence`: ba mesh presets ở 7 J, đủ 6 ms và hậu xử lý. Kết quả ghi vào acceptance-results.json và mesh-comparison.json ngoài repo. Test reserve RAM mặc định 2 GiB; có tùy chọn hạ reserve cho kiểm thử có kiểm soát, không đổi mặc định sản phẩm.

Import ODB tham chiếu để regression: 121 frame, lực đỉnh khoảng 2.842,755 N, hành trình viên cực đại khoảng 4,566134 mm. Kiểm tra số dòng mọi field/frame và giá trị mẫu nguồn. Kiểm tra PDF bằng render trang thực, không chỉ kiểm tra file tồn tại.

## Cần tài khoản Google

Người dùng cấu hình OAuth Desktop và đăng nhập; upload gói lớn, ngắt mạng, tiếp tục, kiểm tra size/MD5 từ Drive, tải về và kiểm tra SHA-256/từng file khi restore. Chưa đăng nhập không được đánh dấu kiểm thử Drive thật đã qua.

## Ghi nhận kết quả

Xem VALIDATION_RESULTS.md cho các lần kiểm thử đã thực thi trong lần bàn giao. Không đánh dấu preset hội tụ chỉ vì solver không báo lỗi. Chưa có thí nghiệm độc lập thì physical validation giữ not_established.
