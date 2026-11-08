# Nghiên cứu bổ sung 100 cấu hình FE

Ngày: 09/11/2026, Asia/Bangkok. Campaign: `core-damage-v2-20261107-v6p5`.

## Đề xuất

Chọn **100 mẫu development bằng maximin tuần tự trong miền hình học hợp lệ**. Giữ 320 development và 80 test hiện có; sau bổ sung có **420 development + 80 test = 500 cấu hình**. Giữ nguyên baseline và 60 OFAT cũ. Cách chọn này chưa cần chờ toàn bộ response của 400 lượt cũ, có thể phân phối đồng thời phần bổ sung khi slot cho phép.

Đây là đề xuất dựa trên khảo sát độ phủ tham số bên dưới, không phải chứng minh rằng 100 mẫu đã đủ cho mọi mô hình hồi quy/phân loại.

## Phạm vi đã kiểm tra

Nguồn nội bộ: `src/honeycomb_studio/campaign.py`, `models.py`, `campaign_protocol.py`, `campaign_queue.py`, và snapshot `output/current-error-repair-manifest.json`. Chỉ đọc role, ID, tham số, hash và cấu hình vận hành. **Không dùng kết quả/nhãn của 80 test** để chọn mẫu, đo tương quan hay khớp mô hình.

| Biến | Khoảng giữ nguyên |
|---|---|
| `reentrant_delta_deg` | 25–45 độ |
| `foil` | 0,035–0,115 mm |
| `cell_size` | 4,5–8,2 mm |
| `reentrant_cell_height` | 3–7 mm |

Miền chấp nhận hiện tại của campaign:

`cell_size - reentrant_cell_height * tan(delta) > max(8 * foil, 0.5 mm)`.

Đây là điều kiện hình học của code, chưa phải một chứng nhận khả năng chế tạo hay xác thực vật liệu. Tất cả 100 điểm nghiên cứu đã vượt `geometry_valid()` của code hiện tại. Giữ 6,5 m/s, 8 ms, 2,65 kg, vật liệu/tham số phá hủy, điều kiện biên và lưới tham chiếu Actions hiện tại. Không đổi ngưỡng quality, không gọi phần bổ sung là dữ liệu được kiểm chứng vật lý.

## Thuật toán cụ thể

1. Cố định thứ tự bốn biến như bảng. Chuẩn hóa từng trục bằng cận thiết kế: `u_j=(x_j-low_j)/(high_j-low_j)`.
2. Sinh **65.536 = 2^16** điểm ứng viên bằng `scipy.stats.qmc.Sobol(d=4, scramble=True, seed=20261109).random_base2(16)` với môi trường đã khóa.
3. Loại ứng viên không thỏa miền hình học. Loại cấu hình trùng chính xác với 400 cấu hình đã có. Tọa độ 80 test chỉ phục vụ loại trùng; **không đưa 80 tọa độ test vào tiêu chí khoảng cách**, không dùng test response.
4. Khởi tạo tập tâm bằng toàn bộ **320 development đã được lập kế hoạch**, kể cả điểm chưa chạy xong, để không lập lại vùng đã có FE đang chờ.
5. Với từng ứng viên, tính khoảng cách Euclid tới tâm gần nhất. Chọn điểm có khoảng cách lớn nhất, thêm nó vào tập tâm, cập nhật khoảng cách; lặp đủ 100. Khi hòa chọn chỉ số ứng viên đầu tiên để tái lập.
6. Xác nhận lại `geometry_valid` trên 100 điểm và kiểm tra trùng input. Lưu tọa độ đã chọn, thứ tự, seed, phiên bản thư viện và hash danh sách tham số; không tái sinh âm thầm sau khi đã ký kế hoạch.
7. Đánh giá độ phủ bằng một tập kiểm tra hình học độc lập: Sobol `2^16`, seed `20261110`, lọc cùng miền. Không dùng dữ liệu FE/test response cho bước đánh giá này.

Sobol cung cấp cơ chế sinh pool có thể tái lập; SciPy nhấn mạnh tính cân bằng cho số điểm là lũy thừa của hai. **Sau lọc miền và chọn 100 điểm, bộ cuối không còn được tuyên bố là một Sobol net cân bằng**; tên đúng là maximin từ pool Sobol. [Tài liệu SciPy Sobol](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.qmc.Sobol.html).

Cách chọn xa nhất thuộc họ farthest-first đã được nghiên cứu cho bài toán phủ/clustering theo khoảng cách. Chỉ dùng nó làm cơ sở thuật toán; không suy rộng giới hạn xấp xỉ của bài toán hữu hạn thành bảo đảm sai số FE hoặc tối ưu toàn miền liên tục. [Gonzalez, 1985, bài báo gốc](https://www.cs.columbia.edu/~verma/classes/uml/ref/clustering_minimize_intercluster_distance_gonzalez.pdf).

## Kết quả khảo sát tái lập

Tệp: `output/supplemental-100-research-coverage.json`. Khảo sát chạy bằng Python 3.13.7, NumPy 2.5.4, SciPy 1.18.1; thời gian tính khoảng 0,41 giây, không chạy FE, không tính physics hash.

- Pool: 65.536 điểm, **59.477 hợp lệ**, 6.059 bị loại (**9,2453%**).
- Tập đánh giá độc lập: **59.474 điểm hợp lệ**.
- 100/100 điểm được chọn vượt validator hình học.
- Khoảng cách nhỏ nhất giữa hai mẫu mới: **0,246286**.
- Khoảng cách nhỏ nhất từ mẫu mới tới development cũ: **0,244606**.
- Khoảng cách nhỏ nhất từ mẫu mới tới bất kỳ mẫu nào trong 400 cũ: **0,060100**; không có trùng.

Khoảng cách bên dưới là Euclid không thứ nguyên trong không gian chuẩn hóa. Mỗi phần tử của tập đánh giá đo khoảng cách tới development gần nhất; nhỏ hơn nghĩa là lỗ trống được thu hẹp. Dùng `cKDTree.query(k=1, eps=0, p=2)` để đo khoảng cách. [SciPy cKDTree.query](https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.cKDTree.query.html).

| Chỉ số | 320 development cũ | +100 maximin | +100 conditional LHS đối chiếu |
|---|---:|---:|---:|
| Trung bình khoảng cách gần nhất | 0,156994 | **0,140032** | 0,145486 |
| Phân vị 95% | 0,243165 | **0,198933** | 0,224817 |
| Khoảng cách lớn nhất trên tập đánh giá | 0,402110 | **0,265912** | 0,348335 |

Bổ sung maximin giảm lần lượt **10,80%**, **18,19%**, **33,87%** so với thiết kế cũ trên tập đánh giá này. Đối chiếu LHS sử dụng cùng ngân sách 100, seed 20261109, loại điểm bất hợp lệ rồi bù. Đây là một lần so sánh cố định seed, không phải chứng minh ưu thế với mọi seed/phương pháp. Không dùng discrepancy của hypercube đầy đủ làm tiêu chí chính vì miền khả thi đã bị cắt bởi hình học. SciPy cũng phân biệt minimum-distance criterion và discrepancy và yêu cầu giữ cùng kích thước khi so sánh chiến lược. [SciPy geometric_discrepancy](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.qmc.geometric_discrepancy.html).

Hash SHA-256 của JSON tham số được serialize bằng `json.dumps(selected_parameters, sort_keys=True, separators=(',', ':'))`:

`633fdbc9b49e1e30446886f1562340c81d843b3a67cd4f609df145c0eca0819f`.

Hash này chỉ nhận diện danh sách tham số khảo sát, **không thay physics hash/Linux identity** của campaign.

## Vì sao chưa chia 60 phủ + 40 quanh biên phá hủy

Phương án 60 phủ + 40 quanh biên có thể phù hợp nếu mục tiêu chính là học biên hỏng mặt đáy và đã có classifier được đánh giá bằng development. Hiện vẫn còn response chưa hoàn tất và chưa có bằng chứng kiểm chuẩn xác suất phân loại. Chọn 40 điểm theo `p≈0.5` lúc này có thể ưu tiên lỗi mô hình hoặc vùng thiếu dữ liệu thay vì biên vật lý thật. Đây là nhận định cho tình trạng hiện tại, không phải kết luận rằng active learning luôn kém hơn.

Nguồn gốc nghiên cứu uncertainty sampling chỉ ra các bảo đảm phụ thuộc mô hình/giả thiết và định nghĩa uncertainty. Tài liệu scikit-learn cũng giải thích xác suất classifier cần được đánh giá calibration trước khi diễn giải như độ tin cậy. [Raj & Bach, ICML 2022](https://proceedings.mlr.press/v162/raj22a.html), [scikit-learn calibration](https://scikit-learn.org/stable/modules/calibration.html).

Do người dùng cần dữ liệu nhanh và toàn bộ miền, **100 maximin là lựa chọn hiện tại**. Nếu nghiên cứu sau này nhắm riêng biên hỏng, chỉ huấn luyện và xác thực acquisition bằng development; giữ test đã khóa tới đánh giá cuối. [scikit-learn về rò rỉ dữ liệu](https://scikit-learn.org/stable/common_pitfalls.html#data-leakage).

## Đưa vào chạy

- Gắn 100 điểm vào cohort bổ sung riêng, ví dụ `supplemental-100-20261109`, role `development`, ID `development-0321`–`development-0420` nếu chưa tồn tại.
- Ghi quyền mở rộng và hash riêng cho cohort. Giữ nguyên contract/hash của 400 mẫu đầu; không thay đầu vào hoặc kết quả của mẫu đang chạy.
- Khóa scientific identities bằng cùng Linux/runtime với worker; không dùng Windows để thay identity đã có.
- Chia 100 mới cân bằng cho 8 owner, mỗi owner 12 hoặc 13; điều phối theo slot thực trống và quota hiện hành. Không hứa 160 solver cùng hoạt động nếu còn tải artifact/cài runtime/đợi license.
- Lưu archive/ODB/hash, log và numerical gate y như cohort cũ; bounded extraction; checkpoint tiếp tục theo giới hạn đã ghi nhận. Tách số hoàn tất 400 đầu và 100 bổ sung trong báo cáo.
- Bộ 100 không bảo đảm thời gian FE bằng nhau: maximin có thể chọn các vùng biên hình học tốn lưới/solver. Không bỏ vùng khó chỉ để làm đẹp thời gian hoàn tất.
- Việc mở rộng số mẫu không tự mở gate hội tụ lưới/thời gian, hiệu chuẩn vật liệu hay `physical_validation=not_established`.
