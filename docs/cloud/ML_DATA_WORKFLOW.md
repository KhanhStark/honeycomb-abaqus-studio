# Job mô phỏng, thư mục dữ liệu và huấn luyện

## Đã kiểm thử thật — 28/10/2026

[Job research 20°/30°, 7 J, panel 100 mm, 12 ms](https://github.com/xuankhanh24/honeycomb-abaqus-studio/actions/runs/40630762284) hoàn tất thành công: **2/2 mẫu đạt chất lượng số**, lực tiếp xúc cuối bước 0 N; không giảm các ngưỡng chất lượng. [Thư mục job trên web](https://honeycomb-abaqus-studio.vercel.app/?data_job=e583980b8c8e401c9a63f0d7fe363d44) chứa cả hai lượt đồng thời. [Gói đầy đủ](https://github.com/xuankhanh24/honeycomb-abaqus-studio/releases/tag/job-data-e583980b8c8e401c9a63f0d7fe363d44-40645400771-1) có 2.832.649.534 byte, chia 3 phần kèm công cụ tải/kiểm tra SHA-256.

[Bộ tổng hợp đã nghiệm thu](https://github.com/xuankhanh24/honeycomb-abaqus-studio/releases/tag/training-40645400771-1) có **19 lượt đã lưu, 2 mẫu được nhận**. CSV/Parquet huấn luyện có 2 dòng, 69 cột, không có giá trị thiếu; mọi y ứng viên có 2 dòng số hữu hạn. Bảng mọi kết quả giữ 19 dòng, kể cả mẫu bị loại. Bộ này có train=1, validation=0, test=1: cấu trúc và chất lượng mẫu đạt, **số mẫu chưa đủ để huấn luyện/đánh giá mô hình có khả năng tổng quát hóa**. Không coi việc solver chạy thành công là bằng chứng hội tụ lưới hay kiểm chứng thí nghiệm.

Kiểm thử trình duyệt trên web thật xác nhận link Actions, thư mục job, bộ lọc ODB, tải gói đầy đủ và giao diện máy tính/điện thoại. [Kiểm thử web trên GitHub Actions](https://github.com/xuankhanh24/honeycomb-abaqus-studio/actions/runs/40632739953) đã qua; [workflow đóng gói cuối](https://github.com/xuankhanh24/honeycomb-abaqus-studio/actions/runs/40645400771) thành công. Các kết quả này là ảnh chụp nghiệm thu theo thời điểm, không thay thế trạng thái catalog hiện tại.

## Một lần chạy = một job = một thư mục

Một lần bấm chạy trên web tạo một job cha và một workflow Actions. Nếu chọn đồng thời, workflow chia các lượt cho runner riêng; tất cả vẫn thuộc cùng job. Mỗi lượt có chỉ số và thư mục con riêng. Các release gốc của runner giữ dữ liệu bất biến; release **Dữ liệu job** gom chúng thành một thư mục tải về chung.

Tên thư mục dùng tên bài bỏ dấu để tương thích Windows, kèm 12 ký tự ID. ID đầy đủ và tên tiếng Việt được giữ trong `job.json` và `source-jobs.json`. Ví dụ:

```text
job--khao-sat-loi-lom--e583980b8c8e/
├── job.json                          # Yêu cầu, profile, hash và workflow của cả job
├── 01_training/
│   ├── samples.csv / samples.parquet # Bảng chỉ gồm mẫu đạt chất lượng số
│   ├── dataset.json                  # X, y ứng viên, split, nguồn và phiên bản
│   ├── readiness.json                # Số dòng dùng được cho từng y, thiếu X, chia tập
│   ├── data-dictionary.csv/json      # Tên tiếng Việt, đơn vị, vai trò, cách tính
│   ├── FIELD_DESCRIPTIONS.md
│   ├── provenance/<run-id>/
│   └── curves/<run-id>/
├── 02_audit/
│   ├── run-selection.csv             # Nhận/loại từng lượt, findings cụ thể
│   ├── source-jobs.json              # Bao gồm nguồn thiếu hoặc chưa hoàn tất
│   ├── input-output-contract.json
│   └── full-source-manifest.json      # Mọi tệp gốc, kích thước, SHA-256 và phần tải
├── 03_simulations/
│   ├── run-0001--delta-20deg--energy-7J--<run-id>/
│   │   ├── input/requested.json       # Đầu vào yêu cầu
│   │   ├── input/resolved.json        # Đầu vào thực tế
│   │   └── output/
│   │       ├── summary.json           # Kết quả đo
│   │       ├── quality.json           # Kết quả kiểm tra chất lượng
│   │       └── attempt-001/           # Đường cong CSV/Parquet
│   └── run-0002--delta-30deg--energy-7J--<run-id>/...
├── 04_solver_archive/                 # Có trong gói ZIP đầy đủ
│   ├── run-0001/attempts/001/          # ODB, CAE, INP, log, báo cáo, field đã lưu
│   └── run-0002/attempts/001/...
└── 05_all_results/
    ├── simulation-results.csv         # Mọi lượt, gồm review/smoke, chưa lọc ML
    ├── simulation-results.parquet
    └── README.json
```

## Các nút trên web

- **Công việc → Mở bài → Theo dõi trên GitHub Actions** mở đúng workflow của job.
- **Mở thư mục dữ liệu job** mở cây tệp trực tuyến, số lượt, mẫu đạt, dung lượng và checksum.
- **Tải đầu vào/đầu ra, đường cong và X/y** tải ZIP nhỏ để đọc ngay.
- **Tải ZIP đầy đủ** có ODB/CAE/INP, log và báo cáo, khi gói vừa một phần.
- Với gói lớn, tải **download_full.py** vào thư mục trống rồi chạy CMD: `py download_full.py`. Script không cần thư viện ngoài, Abaqus hoặc license. Nó tải các phần, kiểm tra SHA-256 toàn phần/toàn ZIP và giải nén. Không sửa hoặc ghép thủ công các part của kho solver.
- **Đóng gói lại toàn bộ dữ liệu job** dùng khi cần tạo/cập nhật gói đầy đủ từ các bản lưu gốc.
- **Dữ liệu → Dữ liệu huấn luyện tổng hợp** gom các job vào một bảng chung, khử trùng toàn cục; có bảng mọi kết quả và danh sách mở thư mục từng job.

Thư mục đang chạy sẽ có dữ liệu sau khi solver đóng tệp và bản lưu được xác minh. Job bị lỗi có thể có thư mục chưa đầy đủ: web và `source_complete=false` ghi rõ tình trạng này. Một ZIP tải xuống thành công không có nghĩa mọi lượt trong job đã hoàn tất hoặc mọi mẫu đã đạt.

## Đầu vào X và đầu ra y

Đầu vào **mô phỏng** gồm hình học mm, vật liệu, ngàm, tải J hoặc m/s, lưới, thời gian s và lựa chọn ghi output. Đầu ra gồm lực N, chuyển vị mm, năng lượng J, ứng suất MPa, đường cong, ODB và kiểm tra chất lượng.

Đầu vào **huấn luyện X** là đúng các cột `input.*` được liệt kê trong `dataset.json.features`. Chọn y theo bài toán trong `dataset.json.targets`, ví dụ `peak_raw_contact_force_N`, `max_top_centre_downward_mm`, `SEA_J_kg`. Các chỉ số năng lượng nhân tạo/sai số dùng kiểm tra số; không tự coi chúng là mục tiêu vật lý. ID, hash, split, attempt và trạng thái không đưa vào X.

`05_all_results` dùng tiền tố `input.*` và `output.*` để đọc mọi thông số/kết quả đã lưu. Đây không phải bảng huấn luyện đã được chấp nhận. Đọc `run-selection.csv` và `readiness.json` trước khi chọn mẫu/y. Dữ liệu thiếu là null/ô trống, không phải số 0.

## Điều kiện nhận mẫu và cách sửa

Lượt phải hoàn tất, không phải test_only/smoke, có `ml_eligible=true`. Các kiểm tra hiện tại gồm solver đạt thời gian yêu cầu, kiểm tra năng lượng, lực history so với field, động năng đầu và lực tiếp xúc cuối bước.

Ở các lượt research 6 ms đã kiểm tra, các chỉ số năng lượng/lực đạt ngưỡng nhưng cuối bước còn tiếp xúc trên 10 N. Vì vậy phải chạy lâu hơn để quan sát đầy đủ quá trình; không sửa cờ quality hoặc giảm ngưỡng để nhận dữ liệu cũ.

Web dùng mặc định 12 ms cho mẫu cloud mới; đây là lựa chọn khởi đầu, không bảo đảm mọi cấu hình đều đạt. Khi một job chỉ bị chặn vì còn tiếp xúc, nút **Tạo job research với thời gian ×2** tạo một bản yêu cầu mới, giữ hình học, tải và lưới, tăng mật độ tổng số mẫu history tương ứng. Job cũ được giữ nguyên. Kiểm tra cấu hình và bấm bắt đầu để chạy job mới. Đề xuất tự động dừng ở 24 ms; nếu còn vấn đề phải xem đường cong/ngân sách và điều chỉnh có căn cứ.

Workflow mô phỏng mới kiểm tra nghiệm thu huấn luyện sau khi đã giữ dữ liệu: research còn mẫu bị loại sẽ báo bước nghiệm thu thất bại, dù solver đã tính xong. Workflow tổng hợp riêng vẫn xuất hồ sơ review/failed để chẩn đoán.

Mẫu đạt chất lượng số chưa đồng nghĩa mô hình đã hội tụ lưới hoặc được kiểm chứng thực nghiệm. Số mẫu ít vẫn có thể chưa đủ để tổng quát hóa. Dùng `split` có sẵn theo design_id, kiểm tra đủ train/validation/test và số dòng hợp lệ cho từng y trong readiness.json.
