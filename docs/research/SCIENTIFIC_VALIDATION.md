# Mô hình khoa học và kiểm chứng

## Nguồn và phạm vi

Foo C.C., Seah L.K., Chai G.B., *Low-velocity impact failure of aluminium honeycomb sandwich panels*, Composite Structures 85 (2008) 20–28, DOI 10.1016/j.compstruct.2007.10.016. File bài báo và mô hình 7 J do người dùng cung cấp; các file lớn không đưa vào Git.

Tấm 100×100 mm, mặt 0,75 mm, lõi 20 mm, ô 6,35 mm, foil 0,0635 mm, đầu cầu D13,1 mm, M2,65 kg, ngàm ngoài lỗ D76,4 mm, khe hở 0,1 mm. Shell honeycomb chi tiết, Tie hoàn hảo, frictionless, self-contact lõi và rigid impactor chỉ chuyển động Z.

## Giả định tái dựng

- Ô có cạnh `cell_size/sqrt(3)`, vách ghép đôi 2t. Phase và hướng ô không được bài báo công bố đầy đủ.
- Ramberg–Osgood dịch về zero plastic strain tại yield; hiểu stress là true stress. Bài báo không cung cấp bảng dẻo gốc.
- Lưới, khoảng output, thời gian step, Simpson 5 điểm, điểm lấy chuyển vị và thiết lập contact là các lựa chọn số học của bản tái dựng.
- Không mô phỏng tách keo, rách foil, fracture hay perforation bằng element deletion. Không suy ra khả năng chống thủng từ mô hình này.

## Tham chiếu 7 J đã có

ODB người dùng cung cấp có 121 frame. Summary đi kèm báo lực đỉnh 2.842,755 N, hành trình viên cực đại 4,566134 mm, độ võng mặt trên khoảng 4,46957 mm. Đây là mốc regression cho bộ đọc/trích xuất, **không phải bằng chứng mô hình đúng thí nghiệm**.

Summary gốc có drift năng lượng khoảng 0,081%, ALLAEmax/ALLIEmax khoảng 4,522%. Mô hình gốc đã ghi chú chưa xác nhận hội tụ và có sai khác so với đồ thị bài báo.

## Quy trình kiểm chứng

1. Datacheck: hình học/lưới, Tie, contact, khối lượng, đơn vị, initial energy và cảnh báo.
2. Solver: xác nhận .sta hoàn tất thành công, thời gian vật lý đạt yêu cầu, không kết luận chỉ từ ODB tồn tại.
3. Đọc dữ liệu: mọi field/frame có số dòng trùng inventory; đối chiếu giá trị mẫu với ODB và history.
4. Cân bằng lực: tổng CNORMF theo Z trên viên so với m(A3+g), nội suy history về frame time khi cần. Không dùng RF3 của RP tự do Z làm lực va đập.
5. Chất lượng: xem energy drift, artificial energy, kết thúc tiếp xúc, biến dạng phần tử và contact warnings.
6. Hội tụ ba mức lưới ở cùng 7 J, duration và output. Script ghi sai lệch lực, độ võng và thời gian tiếp xúc. Tiêu chí thực dụng 5% cho các đại lượng này được ghi riêng, không giả làm tiêu chí ứng suất 2% của bài báo.
7. Đối chiếu nhiều mức năng lượng và dữ liệu thí nghiệm độc lập trước khi gắn nhãn physical validation.

Chỉ đánh dấu preset hội tụ khi có kết quả đạt tiêu chí đã công bố. Lưới nhanh không được tự coi tương đương lưới tham chiếu. Những thiết kế ngoài miền nghiên cứu ban đầu phải kiểm tra lại tính phù hợp của mô hình vật liệu và failure mechanisms.

Các phép kiểm tra energy drift, artificial energy và đối chiếu lực phải có giá trị hữu hạn để kết quả đủ điều kiện ML. Thiếu phép kiểm tra (kể cả không xuất field lực để đối chiếu) hoặc giá trị NaN/Infinity chuyển chất lượng số sang `review`, ghi rõ chỉ số còn thiếu và đặt `ml_eligible=false`. Ngưỡng 1% / 5% / 2% giữ nguyên. Với kết quả đã lưu trước thay đổi này, cần hậu xử lý lại để áp dụng kiểm tra mới; bản sửa không tự thay đổi thư viện dữ liệu cũ.
