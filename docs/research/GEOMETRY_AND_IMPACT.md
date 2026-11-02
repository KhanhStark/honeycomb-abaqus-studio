# Hình học theo công thức (8) và kích thước viên bi

Với lõi tổ ong lục giác, chọn **Cách nhập ô lục giác → Nhập b, l, θ**:

- b: chiều dài vách đứng (mm), có chiều dày kép 2t.
- l: chiều dài vách nghiêng (mm), có chiều dày t.
- θ: góc vách nghiêng so với phương đứng (độ), 0 < θ < 90. Góc xoay toàn mạng ô được nhập riêng.
- t: chiều dày foil đơn (mm).
- ρ: khối lượng riêng vật liệu lõi (kg/m³), chỉnh trong Vật liệu lõi.

HD = 2(b + l)tρ / [(b + l cosθ)(2l sinθ)] (kg/m³).

Bề rộng ô là 2l sinθ; bước hàng là b + l cosθ; chiều cao bao toàn ô là b + 2l cosθ. Các tham số này điều khiển mạng vách thực tế dùng trong Abaqus. Đây là khối lượng riêng của mạng tuần hoàn; khối lượng lõi hữu hạn sau khi cắt theo mép tấm được tính riêng từ mô hình.

Chế độ **Ô đều theo kích thước ô** giữ cách nhập cũ: b = l = cell_size/√3 và θ = 60°. Khi đó hệ số chính xác là 8/(3√3) ≈ 1,5396, tương ứng công thức rút gọn HD ≈ 1,54tρ/b. Không áp dụng hệ số này cho b, l, θ bất kỳ hoặc cho lõi re-entrant. Lõi re-entrant giữ hình học và công thức khối lượng riêng riêng trong giao diện.

Trong **Va đập**, chọn **Nhập vận tốc v (m/s)** để nhập vận tốc dương theo hướng va chạm; E = ½mv² được tính từ khối lượng chuyển động m (kg). Chọn nhập năng lượng thì vận tốc được suy ra từ v = √(2E/m).

Chọn **Nhập bán kính R** hoặc **Nhập đường kính D**; R và D tính bằng mm, D = 2R. Ví dụ R = 6,55 mm tương ứng D = 13,1 mm. Thay đổi kích thước viên bi không tự thay đổi khối lượng chuyển động. Mô hình vẫn dùng đầu rigid có khối lượng chuyển động hiệu dụng được điều chỉnh theo m đã nhập.

Có thể khảo sát b, l, θ, vận tốc và bán kính trong chế độ nhập tương ứng. Cấu hình cũ thiếu các lựa chọn mới vẫn được hiểu theo ô đều, đường kính và chế độ năng lượng/vận tốc đã lưu. Không tự chạy mô phỏng khi đổi các lựa chọn.
