> Bản lưu phương án 6 m/s. Đã được thay thế theo yêu cầu mới bởi [KE_HOACH_CHOT_H20_BI_8MPS](KE_HOACH_CHOT_H20_BI_8MPS.md).

# Kế hoạch chốt: lõi H20, viên bi 2,65 kg, 6 m/s

Cập nhật ngày 06/11/2026 theo lựa chọn cuối của người dùng. Tài liệu này thay thế các phương án H15, đầu nón cụt và vận tốc 10–20 m/s trong kế hoạch trước.

Kế hoạch cho toàn bộ chiến dịch và danh sách 400 cấu hình: [Kế hoạch toàn bộ H20, viên bi 6 m/s](KE_HOACH_TOAN_BO_H20_BI_6MPS.md). Phạm vi thực thi đang bật vẫn được quản lý riêng, không tự mở rộng bằng việc lập kế hoạch.

## 1. Phạm vi thực hiện hiện tại

Chuẩn bị và chạy **3 pilot tại 6 m/s, thời gian 8 ms**, sau đó dừng để đánh giá. Bộ 400 cấu hình chính vẫn chờ quyết định sau pilot. Không tự tăng vận tốc, kéo dài thời gian hoặc chuyển sang chạy dữ liệu chính.

## 2. Cấu hình cố định

| Hạng mục | Giá trị chốt |
|---|---|
| Kết cấu | Tấm sandwich với lõi tổ ong lõm reentrant, hướng hiện tại 0° |
| Kích thước tấm | 100 × 100 mm |
| Chiều cao lõi | **20 mm** |
| Hai mặt | **0,75 mm mỗi mặt** |
| Vật liệu lõi và hai mặt | **AA6061-T6 tham khảo**, có dẻo và hư hỏng Johnson–Cook |
| Vật va chạm | Viên bi cứng **D13,1 mm**, bán kính 6,55 mm |
| Tổng khối lượng chuyển động | **2,65 kg**, gán cho cụm cứng tại điểm tham chiếu |
| Vận tốc ban đầu | **6 m/s**, vuông góc chính giữa tấm |
| Động năng ban đầu | **47,7 J** = ½ × 2,65 × 6² |
| Thời gian pilot | **8 ms** |
| Liên kết lõi–mặt | Tie hoàn hảo |
| Gá kẹp | Encastre ở biên theo mô hình hiện tại |
| Ma sát / khe hở | 0,2 / 0,1 mm |
| Trọng lực | 0 trong bước va chạm |
| Solver | Abaqus/Explicit, double precision, 4 CPU/job, không mass scaling |

D13,1 mm mô tả hình học tiếp xúc; 2,65 kg là khối lượng hiệu dụng của cả cụm chuyển động. Không suy ra khối lượng này từ mật độ của một viên bi kim loại đặc D13,1 mm.

### Vật liệu và hư hỏng

| Nhóm | Thông số |
|---|---|
| Đàn hồi | ρ = 2.700 kg/m³; E = 70.000 MPa; ν = 0,33 |
| Johnson–Cook dẻo | A = 324 MPa; B = 114 MPa; n = 0,42; C = 0,002; m = 1,34; tốc độ tham chiếu 1 s⁻¹ |
| Khởi tạo hư hỏng | D1 = −0,77; D2 = 1,45; D3 = +0,47 theo quy ước Abaqus; D4 = 0; D5 = 1,6 |
| Phát triển hư hỏng | Chuyển vị phá hủy 0,1 mm, mềm hóa tuyến tính; bật xóa phần tử |
| Nhiệt | Ban đầu/tham chiếu 20°C; nóng chảy 650°C; Cp = 900 J/kg·K; hệ số chuyển công dẻo thành nhiệt 0,9; đoạn nhiệt |

Đây là bộ vật liệu tham khảo chưa hiệu chuẩn phá hủy bằng thí nghiệm. Giá trị phát triển hư hỏng cần kiểm tra độ nhạy tại 0,05 và 0,20 mm trước dữ liệu chính.

### Lưới xuất phát

Lõi và hai mặt dùng shell S4R/S3R, 5 điểm tích phân Simpson qua chiều dày. Seed lõi vùng tâm/ngoài: 0,7/1,3 mm; theo chiều sâu lõi: 1 mm. Seed hai mặt vùng tâm/ngoài: 0,75/1,25 mm. Vùng tinh lưới lõi có bán kính 25 mm; vùng tinh lưới mặt có nửa cạnh 25 mm. Đây là lưới xuất phát, chưa được coi là hội tụ cho tải mới.

Xuất 800 khoảng field và 4.000 khoảng history trong 8 ms, tương ứng khoảng ghi 10 µs và 2 µs. Khoảng ghi kết quả không phải bước thời gian tích phân ổn định của solver.

## 3. Ba pilot được phép chạy

Giữ delta = 35°, cell_size = 6,35 mm, reentrant_cell_height = 5 mm. Chỉ thay đổi chiều dày lá lõi giữa ba lượt.

| Lượt | Foil (mm) | Vận tốc (m/s) | Thời gian (ms) | Mục đích |
|---|---:|---:|---:|---|
| P1 | 0,035 | 6 | 8 | Lõi mỏng |
| P2 | **0,0635** | 6 | 8 | **Cấu hình tham chiếu mới** |
| P3 | 0,115 | 6 | 8 | Lõi dày |

Mỗi pilot bắt đầu từ trạng thái ban đầu mới. Không dùng trạng thái va chạm đã chạy ở vận tốc khác làm trạng thái ban đầu cho 6 m/s.

### Dữ liệu đánh giá pilot

- Chuyển vị xuống cực đại trên **toàn bộ mặt sau**, theo không gian và thời gian; lưu thêm chuyển vị tâm và chuyển vị cuối bước.
- Khối lượng lõi ban đầu; ALLPD_core; ALLDMD_core; SEA_core.
- Lực tiếp xúc, vận tốc và chuyển vị vật va chạm; thời điểm kết thúc tiếp xúc.
- Trạng thái hư hỏng/xóa phần tử của lõi, mặt trước và mặt sau; các thành phần năng lượng và chất lượng số.
- So sánh độ phân biệt của ba chiều dày. Mục tiêu thăm dò là cấu hình tham chiếu có chuyển vị mặt sau khoảng **1–3 mm**, ưu tiên gần 2 mm và mặt sau nguyên vẹn. Đây là cửa sổ đáp ứng nghiên cứu, không phải tiêu chuẩn an toàn.

Nếu đáp ứng nhỏ, còn tiếp xúc ở cuối 8 ms, hoặc mặt sau bị hỏng, ghi nhận kết quả và đề xuất điều chỉnh. Không tự đổi thông số để tạo chuyển vị lớn hoặc hình ảnh rách.

## 4. Điều kiện trước bộ dữ liệu chính

Sau pilot, cần quyết định tiếp tục và hoàn thành các kiểm tra sau:

1. Kiểm tra vật liệu bằng kéo, nén, cắt; đúng đơn vị, khởi tạo, suy giảm và xóa phần tử.
2. Kiểm tra thời gian **8 so với 12 ms** trên ba cấu hình: hai mục tiêu thay đổi ≤2%, tiếp xúc kết thúc và năng lượng lõi gần ổn định. Chỉ chạy kiểm tra 12 ms khi chuyển sang giai đoạn này; không tự gắn nó vào đợt 3 pilot.
3. Kiểm tra lưới theo hệ số kích thước 1 / 0,75 / 0,5; chọn mức thô nhất sai khác hai mục tiêu ≤5% so với mức tiếp theo và cùng phân loại hư hỏng.
4. Kiểm tra độ nhạy phát triển hư hỏng 0,05 / 0,10 / 0,20 mm.
5. Cân bằng năng lượng sai lệch ≤5% động năng đầu; năng lượng nhân tạo ≤5% nội năng trong giai đoạn va chạm đã phát triển.
6. Xác minh general contact, tự tiếp xúc và bề mặt lộ ra sau xóa phần tử; thử chạy nối trên runner khác và phục hồi archive bằng checksum.
7. Khóa vật lý, lưới, thời gian chung và phiên bản mã; kiểm tra thời gian trên 40 cấu hình phát triển phủ miền trước khi phát phần còn lại.

Nếu 8 ms không đủ, chưa được coi kết quả 8 ms là bộ dữ liệu chính hoàn tất. Nếu 12 ms vẫn chưa đủ, dừng để xem lại giao thức.

## 5. Bộ dữ liệu chính dự kiến

Giữ H20, vật liệu, viên bi, vận tốc và các điều kiện biên cố định sau khi qua các kiểm tra. Khảo sát **4 biến hình học lõi**:

| Biến | Trường | Khoảng |
|---|---|---:|
| Góc delta | reentrant_delta_deg | 25–45° |
| Chiều dày lá lõi | foil | 0,035–0,115 mm |
| Kích thước ô | cell_size | 4,5–8,2 mm |
| Chiều cao ô lõm | reentrant_cell_height | 3–7 mm |

Chiều cao ô lõm khác chiều cao toàn bộ lõi H20. Theta không khảo sát; reentrant_indent suy ra từ delta và chiều cao ô, không phải biến độc lập. Chỉ nhận hình học có khe ô > max(8 × foil, 0,5 mm).

| Nhóm | Số cấu hình | Phương pháp |
|---|---:|---|
| Phát triển | 320 | 1 tham chiếu + 40 OFAT (10 mức/biến) + 279 Latin Hypercube hợp lệ |
| Kiểm tra giữ riêng | 80 | Latin Hypercube độc lập; không dùng chọn mô hình/điểm bổ sung |
| Bổ sung | Tối đa 80 | 40 bất định cao + 24 gần Pareto + 16 miền thưa |
| Xác nhận tối ưu | 20 | Cấu hình mới dọc Pareto, xác nhận bằng FE |
| **Tổng chính** | **420–500** | Chưa tính pilot, hội tụ, chạy nối và retry |

Seed 20261106. OFAT thay một biến mỗi lượt; Latin Hypercube thay phối hợp để học tương tác. Các lần retry/chạy nối không được tính thành mẫu mới.

## 6. Dự đoán và tối ưu

- Mục tiêu 1: tăng **SEA_core = (ALLPD_core + ALLDMD_core) / khối lượng lõi ban đầu**.
- Mục tiêu 2: giảm chuyển vị xuống cực đại toàn mặt sau.
- Ràng buộc: khối lượng lõi ≤ cấu hình tham chiếu H20 mới và mặt sau không có phần tử bị xóa.
- So sánh Ridge, hồi quy bậc hai, Gaussian Process và Extra Trees; kiểm định chéo 5 phần trên nhóm phát triển. Chuẩn hóa và chọn siêu tham số bên trong các vòng kiểm định.
- NSGA-II tìm Pareto. Chỉ kết luận phương án tối ưu sau FE xác nhận và kiểm tra số.
- Mục tiêu dữ liệu: ít nhất 250 mẫu phát triển có mặt sau nguyên vẹn; R² ≥0,90 và NRMSE ≤10% với mẫu số P95–P5. Không đạt sau ngân sách bổ sung thì báo chưa đủ.
- Giữ mẫu phá hủy vật lý để phân loại; tách lỗi solver khỏi phá hủy. Không dùng chuyển vị nhỏ giả từ nút/phần tử mất liên kết để đánh giá tốt một cấu hình.

## 7. Tự động hóa và bàn giao

Ba pilot được phân phối thành ba job độc lập. Giai đoạn chính dự kiến 50 cấu hình/repo trên 8 repo: 40 phát triển + 10 kiểm tra. Tăng song song theo giấy phép, bộ nhớ, truyền dữ liệu và quota thực tế; mục tiêu trần cấu hình 160 slot, không mặc định rằng đã có đủ công suất.

Một cấu hình chỉ có một job solver đang tính tại một thời điểm. Dừng có kiểm soát trước phút 240 tính từ lúc runner bắt đầu, timeout 330 phút, tối đa 4 đoạn. Khôi phục nguyên trạng thời gian, vận tốc và damage. Lỗi số retry tối đa 2 lần; upload lỗi chỉ upload lại kết quả đã tính.

Bàn giao tập trung: samples.csv, impact_history.csv từng mẫu, manifest/đơn vị/checksum, khối lượng, vật liệu/lưới/thời gian, trạng thái solver và chất lượng số, INP/ODB/log/checkpoint, nguồn repo và lịch sử retry. Kết quả dự đoán/Pareto/FE xác nhận đi cùng báo cáo cuối.

**Điểm dừng bắt buộc của đợt hiện tại: hoàn thành và lưu xác minh 3 pilot, sau đó báo cáo; 400 cấu hình chính vẫn bị khóa.**
