# Theo dõi công việc trên GitHub Actions

Trong tab **Công việc**, mục **Actions đang chạy** đọc trạng thái thật của các workflow mô phỏng. Nút **Theo dõi trên GitHub Actions** mở đúng lượt chạy. Các lượt nghiệm thu native hiển thị riêng, không nhận quyền điều khiển hoặc đổi trạng thái bản nháp đã lưu. Job do web quản lý có thêm link trong bảng và phần chi tiết; link được giữ sau khi hoàn tất.

## Đọc log

- `START / OK`: bước hiện tại và thời gian thực thi.
- `HEARTBEAT / PROCESS`: PID, thời gian đã chạy và thời gian kể từ output cuối. Bước cài đặt không hiện phần trăm giả.
- `TRANSFER`: byte đã truyền/tổng, phần trăm, tốc độ trung bình MiB/s và ETA ước tính. “Đã xác minh” chỉ xuất hiện sau kiểm tra kích thước và digest. Media bên thứ ba mới tải xong chỉ ghi đã tính hash; ISO phải qua bước đối chiếu hash đã ghim trước khi chạy installer.
- `RUN`: giai đoạn, phần trăm đo được của giai đoạn, thời gian vật lý/tổng thời gian, thời gian đã chạy, ETA và PID. `review` yêu cầu xem chất lượng kết quả, không đồng nghĩa dữ liệu đã được kiểm chứng vật lý.
- `HOST / CONTAINER`: CPU/RAM/đĩa host và CPU/RAM/PIDs của container được gắn nhãn. CPU container 100% tương đương một core; RAM trình gọi Docker không phải RAM solver.
- `FAIL / FIX`: lỗi và bước chẩn đoán tiếp theo. Nhóm chi tiết lỗi có 25 dòng cuối, log đầy đủ và JSONL ở artifact `output/actions-logs`.

Job Summary tổng hợp các bước, tiến độ và lần truyền dữ liệu gần nhất. Summary được GitHub công bố khi step kết thúc; khi step còn chạy, xem console để có mốc mới nhất. Token, địa chỉ license và query của URL được che trước khi ghi console, artifact và summary.

Workflow **Actions log acceptance and preview** chạy test và truyền HTTP loopback thật để kiểm tra định dạng; mọi tiến độ solver minh họa đều có nhãn `FIXTURE`. Tốc độ loopback không phải băng thông Internet. Thay đổi log chỉ áp dụng lượt chạy từ commit mới, không sửa runner đang chạy.
