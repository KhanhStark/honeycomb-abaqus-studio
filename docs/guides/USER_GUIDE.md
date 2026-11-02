# Hướng dẫn sử dụng

## Lõi auxetic hình 1, hướng 0°

Trong **Tạo job → Hình học → Cấu trúc lõi**, chọn **Tổ ong lõm (Re-entrant) — 0°**. Lõi ô lõm nằm trong XZ và đùn theo Y; các tấm mặt, đầu va và ngàm giữ cấu hình bạn đang nhập. Mặc định ô rộng 6,35 mm, cao 5 mm, lõm mỗi bên 1,25 mm; vách xiên dày `foil`, vách thẳng ghép đôi dày `2×foil`. Đây là kích thước thiết kế giả định theo ảnh, chưa xác nhận hội tụ hay tương đương thí nghiệm.

Có thể khảo sát bề rộng ô (`cell_size`), chiều cao ô (`reentrant_cell_height`), độ lõm (`reentrant_indent`) và dịch pha X/Z. Hướng này cố định 0°; `core_angle` và `phase_y` của lõi lục giác không áp dụng. Chọn lưới `custom` để sửa `reentrant_depth_seed` (mặc định 1 mm theo Y); vùng tinh lưới tiết diện dùng khoảng cách X tới vị trí va đập. Hàng phần tử sát đầu lõi đã tie được loại trừ tiếp xúc với tấm mặt tương ứng để tránh chồng lấn shell; tự tiếp xúc lõi vẫn hoạt động.

Ví dụ một ca 7 J: `examples/reentrant-image1-0deg-7J.json`. Kiểm tra danh sách trục khảo sát trước khi tạo job; đổi cấu trúc lõi không tự đổi năng lượng hoặc xóa trục khảo sát. Manifest ghi khối lượng lõi sau cắt biên; không dùng công thức mật độ tổ ong lục giác cho ô lõm.

## Tạo khảo sát

1. Mở **Tạo job**, đặt tên và kiểm tra các nhóm hình học, vật liệu, va đập, liên kết, lưới, solver/output. Mỗi dòng có đơn vị và nguồn. `bottom_skin=null` nghĩa là mặt dưới bằng mặt trên.
2. Chọn `loading=energy` để quét `energy_J`; chọn `loading=velocity` để quét `velocity_m_s`. Khối lượng thay đổi sẽ làm đại lượng phụ thuộc được tính lại.
3. Trong **Khoảng và bước nhảy**, khai báo đầu/cuối/bước hoặc danh sách JSON. Ví dụ `[0.85,2,4,7,10,13]`. Các hàng được tổ hợp khi chọn grid; LHS dùng khoảng đầu/cuối và số mẫu/seed, không dùng bước.
4. Để thay seed thủ công, chọn `mesh_preset=custom`. Các preset còn lại ghi đè seed bằng thông số preset trong input thực tế. Quick/fine chưa tự động được công nhận hội tụ.
5. Chọn **Kiểm tra và preview**. Kiểm tra số lượt, input thực tế, dữ liệu vật liệu, thời gian/dung lượng ước tính; sau đó tạo job. Tạo job chưa tự chạy solver.
6. Sang **Job mô phỏng**, chọn job và bấm **Chạy / Tiếp tục**.

## Theo dõi và dừng

Job hiển thị số lượt theo trạng thái. Chọn cột để ẩn/hiện trạng thái, giai đoạn hoặc attempt; kéo thanh cuộn ngang để xem toàn bộ thời gian/CPU/RAM. Chọn lượt để xem input/output/attempt, log, ảnh và đường cong. Phần trăm solver tính từ thời gian vật lý, không phải phần trăm thời gian thực. Dựng hình/render có thể không có phần trăm đo được.

- **Dừng**: dừng hàng đợi và lượt đang thực thi, giữ file attempt. Khi tiếp tục, lượt chưa tính xong chạy lại từ 0 trong attempt mới.
- **Dừng sau lượt này**: giữ lượt hiện tại chạy hết, sau đó tạm dừng.
- **Chạy lại lượt**: chỉ chọn lại một lượt. Lỗi trích xuất/render/PDF sau solver hoàn tất chỉ làm lại hậu xử lý.
- Đóng cửa sổ không dừng engine. Khi mở lại, ứng dụng kết nối tới engine đang chạy. Sau sự cố engine, ownership PID + thời điểm tạo tiến trình được dùng để nhận diện tiến trình cũ.

Không chỉnh bộ input của job đã tạo. Tạo job mới để giữ lịch sử tái lập.

## Xem và xuất

Mở ODB/CAE bằng nút trong lượt; ODB dùng Abaqus/Viewer, CAE dùng Abaqus/CAE. PDF và thư mục dùng ứng dụng Windows mặc định. File chỉ xuất hiện khi giai đoạn tương ứng đã hoàn tất.

Mỗi lượt có JSON input, dữ liệu Parquet/CSV, ảnh và PDF; ZIP đóng gói toàn bộ dữ liệu đã hoàn tất kèm checksum. **Dữ liệu ML gọn** xuất bảng mỗi lượt một dòng và các đường cong cần cho huấn luyện/tối ưu. **CSV nút/phần tử (nâng cao)** là bản sao mọi giá trị theo frame, có thể lớn hàng chục GB; chỉ dùng khi thực sự cần học trường không gian. Tùy chọn Lưu mọi trường trong Giới hạn job mặc định tắt.

PDF toàn job gồm bảng mọi lượt và so sánh. PDF mỗi lượt khoảng 5 trang, không in bảng dẻo dài hoặc thống kê tensor rỗng; input đầy đủ vẫn giữ trong JSON/CSV và ODB. Parquet trường đầy đủ chỉ được tạo khi bật chế độ nâng cao.

Khi xuất lại báo cáo toàn job sau khi dọn thư mục attempt, ứng dụng đọc đường cong gốc từ bản giữ lại hoặc dataset có cùng mã lượt và attempt. Nếu không có dữ liệu phù hợp, báo cáo ghi rõ lượt thiếu đường cong thay vì vẽ khung trống hoặc suy diễn từ chỉ số cực đại. reports/history-sources.json ghi nguồn và số mẫu dùng cho từng lượt.

**DOCX toàn job** và **DOCX** từng lượt xuất báo cáo Word có thể chỉnh sửa, cùng nội dung và hình với PDF, dùng chữ đen và font hỗ trợ tiếng Việt. Báo cáo tổng hợp thêm đầu vào dùng chung, tham số thay đổi theo lượt, đơn vị, các chỉ số kết quả và chất lượng số.

**Dữ liệu huấn luyện toàn job** tạo ZIP gồm samples.csv/Parquet, từ điển cột, input và kết quả truy vết, đường cong gốc/nội suy và job-coverage.csv. Bảng coverage ghi mọi lượt được chọn hoặc bị loại vì chưa hoàn tất, chất lượng số, dữ liệu giả lập hoặc trùng đầu vào. Job chỉ có một thiết kế hình học có thể chỉ có tập train để tránh rò rỉ giữa các mức tải.

## Dataset và Pareto

Trong thư viện, lọc lượt đủ chất lượng, chọn nhiều lượt rồi xuất dataset. Tên feature có tiền tố `input.`, ví dụ `input.skin,input.core_height,input.foil`; target ví dụ `peak_raw_contact_force_N,SEA_J_kg`.

Dataset giữ provenance, input đầy đủ riêng và đường cong gốc; dữ liệu nội suy có tên riêng. Các thiết kế giống nhau qua tải/lưới/attempt được nhóm trong cùng split. Ít thiết kế có thể làm validation/test trống; cần bổ sung thiết kế độc lập trước khi đánh giá ML.

Mỗi lần xuất dữ liệu huấn luyện (từng lượt, toàn job hoặc từ thư viện) đều có `data-dictionary.csv`, `data-dictionary.json` và `FIELD_DESCRIPTIONS.md`: tên tiếng Việt, đơn vị, vai trò, ý nghĩa/cách tính và quy ước giá trị thiếu cho từng cột. CSV mô tả mở trực tiếp bằng Excel; bảng `samples.csv` giữ nguyên tên cột và dữ liệu số để dùng cho huấn luyện. Bản giữ lại và backup Drive mới cũng kèm các tệp mô tả này. Với bản xuất cũ, cần xuất lại để có mô tả mới.

Pareto chia theo điều kiện tải, đồng thời giảm khối lượng/lực/độ võng và tăng SEA. Đây là phân tích tập dữ liệu đã mô phỏng, chưa phải quá trình huấn luyện hoặc tự sinh thiết kế AI.

## Cài đặt và backup

Thay thư mục/lệnh Abaqus được lưu cho lần khởi động engine tiếp theo. Đường dẫn kỹ thuật nên dùng ASCII để tương thích Abaqus 2017. Không chạy nhiều engine thủ công trên cùng dữ liệu.

Google Drive cần OAuth client Desktop. Khi kết nối thành công có thể backup job và tiếp tục upload bị gián đoạn. Khôi phục luôn tạo job mới và kiểm tra file; không ghi đè job gốc. Xem [hướng dẫn Drive](../cloud/DRIVE_BACKUP.md).

**Backup Drive** tự lưu ZIP mô phỏng cùng thư mục PDF/DOCX và dữ liệu huấn luyện riêng để mở trực tiếp trên Drive. **Backup PDF/ML riêng** bổ sung thư mục này cho ZIP cũ. **Bản giữ lại** mở `<data-root>-retained` ở máy, nằm ngoài thư viện mô phỏng; giữ thư mục này khi xóa dữ liệu nặng. Chỉ dọn sau khi ZIP và các tệp riêng của đúng bản backup đều được xác minh. Ứng dụng không tự xóa dữ liệu.

Sau khi xuất dataset, nút ZIP dataset vừa xuất tạo gói ZIP64 kèm manifest/checksum. Data root có README.md và LIBRARY.csv để tìm job theo tên; từng lượt có bảng input thực tế, output/chất lượng và attempt, với JSON đầy đủ ở tab riêng.
