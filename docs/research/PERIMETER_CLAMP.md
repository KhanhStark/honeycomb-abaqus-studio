# Ngàm bốn cạnh ngoài

Studio mặc định dùng `clamp_mode=perimeter` cho cấu hình mới. Với tấm 100 × 100 mm, chỉ các nút trên X = ±50 mm hoặc Y = ±50 mm của cả hai tấm mặt bị khóa cả sáu bậc tự do. Không ngàm một dải có bề rộng hữu hạn; các nút phía trong không bị khóa trực tiếp. Lõi vẫn liên kết Tie với hai tấm mặt.

Chọn **Liên kết và điều kiện biên → Vị trí ngàm → Chỉ bốn cạnh ngoài**. Lựa chọn **Vùng ngoài lỗ tròn** giữ cách ngàm cũ, theo đường kính 76,4 mm (bán kính 38,2 mm).

Cấu hình đã lưu không có `clamp_mode` vẫn được đọc là `circular` để giữ đúng điều kiện biên của dữ liệu cũ. Muốn đổi cấu hình đã lưu, phải chọn lại vị trí ngàm. Các kết quả mô phỏng cũ không thay đổi và không thể coi là kết quả ngàm bốn cạnh.

Thay đổi này không tự tạo hoặc chạy công việc mô phỏng.
