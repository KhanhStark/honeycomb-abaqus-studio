# Từ điển dữ liệu

## Cấp lưu trữ

`projects/<project-id>/batches/<batch-id>` chứa batch.json, run-index CSV/Parquet và reports. `runs/<run-id>` chứa requested-input.json, resolved-input.json, run.json và attempts/001…; mỗi attempt có raw, extracted, figures, reports, logs và artifact-manifest.json.

- `raw`: CAE, INP, ODB, datacheck, file solver và model_manifest.
- `extracted/inventory.json`: steps, frame, tên/component/position/invariant của field, số bản ghi, instance, mesh sets và sections.
- `extracted/fields/<step>/<field>/frame=NNNNN/part-*.parquet`: dữ liệu trường theo khối.
- `extracted/mesh/<instance>/nodes|elements`: tọa độ và topology gốc.
- `histories.json`, `all_histories.csv/parquet`: toàn bộ history gốc, không đồng bộ lại mốc thời gian.
- `impact_history.csv/parquet`: bảng dẫn xuất theo mốc A3 của RP, các history khác nội suy tuyến tính để đối chiếu.
- `summary.json`, `quality.json`, `export-verification.json`: chỉ số, chất lượng và đối chiếu số dòng.
- `figures/render-manifest.json`: frame, thời gian, biến, view và hệ số biến dạng của ảnh.

## Chế độ nghiên cứu gọn (mặc định từ 0.2.0)

Không tạo bản sao hàng triệu dòng field hoặc mesh. `extracted/reduced-fields/*.json` lưu min/max/sum/count và cực trị có vị trí, được tính trên mọi mẫu của U/S/PEEQ và lực tiếp xúc đã ghi qua mọi frame. Có đối chiếu số mẫu nguồn; đây không phải bảng field đầy đủ, không được dùng như dữ liệu phân bố không gian. ODB gốc giữ toàn bộ dữ liệu đã được solver ghi và có thể mở bằng Abaqus.

Các field mặc định yêu cầu solver là U, S, PEEQ, CFORCE; V3/A3/U3 ở RP vẫn được ghi dưới dạng history. Không giảm số frame hoặc đổi lưới/vật lý để cắt dung lượng. Job cũ giữ cấu hình output cũ.

Bật `export_all_fields=true` trong Giới hạn job để sao chép mọi field/mesh đã ghi sang Parquet. Chỉ chế độ này hỗ trợ CSV nút/phần tử; đó là công cụ chuyên sâu, không phải dữ liệu tabular ML mặc định.

## Field Parquet (chế độ lưu trữ đầy đủ)

Metadata schema `honeycomb` chứa field name gốc, descriptions, components theo đúng thứ tự, step/frame/time_s, instance index mapping, section-point descriptions, start_row và định nghĩa cơ sở tọa độ.

| Cột | Ý nghĩa |
|---|---|
| instance_index | Index trong metadata.instances; -1 là assembly/không gắn instance |
| node_label / element_label | Nhãn gốc trong instance; không phải chỉ số toàn mô hình |
| integration_point | Số điểm tích phân, -1 nếu không áp dụng |
| section_point | Điểm qua chiều dày shell, -1 nếu không áp dụng |
| position | NODAL, INTEGRATION_POINT… |
| data | Vector/tensor/scalar theo componentLabels gốc |
| conjugate_data | Thành phần phức nếu có; NaN/null khi không có |
| local_quaternion | Quaternion gốc từ ODB bulk access; không tự diễn giải thành basis với quy ước khác |
| local_basis | Cơ sở 3×3 theo thứ tự hàng từ FieldValue fallback; không có thì NaN/null |
| mises | Invariant von Mises của S nếu được ODB cung cấp |

Không tự lấy trung bình qua section point hoặc biến tensor thành invariant để thay bản gốc. Giá trị stress/strain giữ hệ tọa độ output của ODB; chỉ chuyển hệ khi người phân tích thực hiện rõ ràng.

Node mesh: label, x/y/z (mm). Element mesh: label, element_type và connectivity JSON list các node label gốc. Sets/section assignments giữ ánh xạ vùng; local instance labels phải được dùng cùng instance.

## Chỉ số

| Chỉ số | Đơn vị / định nghĩa |
|---|---|
| initial_kinetic_energy_J | ALLKE[0]/1000 |
| peak_raw_contact_force_N | max m_tonne×(A3+g_mm_s²), đầu va đập rigid dẫn hướng Z |
| peak_force_time_ms | Thời điểm lực đỉnh trên history gốc |
| max_impactor_displacement_mm | max(-RP.U3), có bao gồm rơi qua khe hở |
| max_indentation_from_contact_mm | Hành trình viên đặt lại mốc tại lần đầu F>10 N |
| max_top/bottom_centre_downward_mm | max(-U3) của nút gần tâm va đập được chọn khi dựng |
| contact_duration_ms | Khoảng lần đầu tới lần cuối F>10 N; ngưỡng được công bố |
| plastic_dissipation_J | ALLPD cuối step /1000 |
| physical_dissipation_J | ALLPD + ALLFD (ma sát), ALLDMD (hư hỏng), ALLCD (creep/nhớt vật liệu) có ghi; loại ALLAE và nhớt số |
| transferred_energy_at_last_contact_J | K0 − K(t) + công trọng lực lên viên; không đồng nhất với tiêu tán |
| panel_mass_kg | Khối lượng hai mặt và lõi hữu hạn, không bao gồm đầu rơi |
| SEA_J_kg | Tiêu tán vật lý / khối lượng sandwich |
| energy drift | max abs(ETOTAL−ETOTAL[0])/K0 ×100% |
| artificial energy ratio | max abs(ALLAE)/max ALLIE ×100% |

Field extrema lưu cả value, step, frame, time, instance, label, integration/section point. Mất output không được thay bằng 0.

## Dataset ML

`samples.csv/parquet`: bảng học máy với cột được chọn, không nhân đôi thành samples-full.csv. `provenance/<run-id>` giữ input, summary và quality JSON để kiểm tra nguồn. `data-dictionary.json`, `dataset.json` mô tả seed, grouping, split, source runs và quy tắc resample. `curves/<run-id>` giữ original histories và resampled.parquet riêng.

physical design ID giữ hình học và vật liệu; thay tải, lưới hoặc attempt không tạo nhóm vật lý mới. Mặc định split theo thiết kế 70/15/15; với ít thiết kế, một số split có thể trống. Không tự lấp bằng cách chia các đường cong của cùng thiết kế qua nhiều tập.

Giữ cờ `physical_validation=not_established` khi huấn luyện trên mô hình chưa kiểm chứng. Không gọi đó là dữ liệu thí nghiệm.

Dataset luôn ghi chất lượng số, physical validation, attempt và extractor version trong bảng đầy đủ. Cực trị PEEQ/von Mises/chuyển vị có cột scalar để chọn làm target; vị trí chi tiết giữ trong summary nguồn. data-dictionary.json ghi đơn vị, định nghĩa, nguồn và vai trò từng cột. LIBRARY.csv tại data root ánh xạ tên job sang thư mục ID.

### Bộ biến ML mặc định

`samples.csv/parquet`: một lượt đủ chất lượng = một dòng. Giữ kích thước/vật liệu/điều kiện tải; loại các bản sao tấn/mm/s của khối lượng/vận tốc, cấu hình CPU và các nhãn vật liệu không chi phối vật lý. Đầu ra gồm khối lượng sandwich, lực đỉnh, độ võng mặt trên/dưới, hành trình từ tiếp xúc, tiêu tán vật lý, SEA, thời gian tiếp xúc, các cực trị PEEQ/von Mises và cờ kiểm tra số. `physical_validation` vẫn thể hiện trạng thái chưa được kiểm chứng thí nghiệm.

Các cột hằng được liệt kê trong `dataset.json/constant_features`; có thể loại trong tiền xử lý ML. Nếu dùng bảng dẻo tùy ý, phải thiết kế feature cho đường cong hoặc dùng mô hình nhận đường cong; chỉ E/yield/alpha/n không đủ biểu diễn mọi bảng. Bảng gốc được giữ trong resolved-input.json. Không thể khẳng định tập dữ liệu đủ huấn luyện chỉ từ một ca 7 J.

PDF từng lượt mặc định 5 trang: kết quả/điều kiện tải; vật liệu/lưới; F-delta/năng lượng; ảnh ghép đỉnh lực; ảnh ghép cuối bước. Không in bảng điểm dẻo, thống kê tensor bằng 0 hay dump JSON. Các giá trị được làm tròn để đọc; dữ liệu xuất giữ độ chính xác gốc.

Định nghĩa năng lượng: [Abaqus - Output of the energy balance](https://docs.software.vt.edu/abaqusv2025/English/SIMACAEGSARefMap/simagsa-c-ovwoutput.htm). ALLCD gắn với nhớt vật liệu/creep; ALLDMD gắn với hư hỏng. Không tự coi biến không ghi là bằng 0.
