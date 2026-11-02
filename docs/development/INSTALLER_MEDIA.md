# Kho bộ cài dùng lại cho GitHub Actions

Bộ cài thử nghiệm hiện tại là ISO Abaqus 2020 Linux64 từ mirror Softgozar. Repo giữ script và metadata, không lưu ISO nhiều GB trong Git.

- ISO: `SIMULIA_Abaqus_2020_Linux64.iso`, 10.066.642.944 byte.
- SHA-256: `d0b227290b5f62ea826b08c18bde222417817fc0d04b91abb0072cb52ebe43ad`.
- Nguồn và checksum của 5 phần RAR: `docs/evidence/linux-media-inspection-20261025.json`.
- Đây là hash ghim đúng tệp đã thử nghiệm; nguồn phát hành chính hãng chưa được xác minh. Không chứa file license hoặc công cụ kích hoạt được tách từ thư mục ngoài ISO.

## Lưu một lần vào Drive riêng

Chạy workflow **Lưu bộ cài Linux vào Google Drive riêng** (`mirror-linux-media.yml`). Workflow kiểm tra dung lượng trước, tải nguồn cũ, chỉ tách ISO, kiểm tra SHA-256, rồi upload có thể tiếp tục và đối chiếu MD5/kích thước từ Drive.

Drive có thư mục **Honeycomb · Bộ cài riêng**, chứa ISO, `SHA256SUMS.txt` và `HUONG_DAN.md`. Workflow chỉ dùng tài khoản OAuth đã cấu hình trong secret `HONEYCOMB_DRIVE_CREDENTIALS_JSON`; không tạo quyền chia sẻ công khai. Thông tin đăng nhập và URL phiên upload không vào artifact hoặc dữ liệu nghiên cứu.

Biên bản `media-mirror-receipt.json` trong artifact có link Drive và `drive_file_id`. Đặt biến repo `ABAQUS_MEDIA_DRIVE_FILE_ID` bằng ID đó sau khi upload đã xác minh. ID là cấu hình; OAuth vẫn nằm trong secret riêng.

## Tải nhanh ở các lượt mô phỏng sau

Hai workflow native gọi `scripts/prepare_linux_media.py`. Khi có ID, Actions tải thẳng một ISO từ Drive bằng tài khoản đã cấu hình và kiểm tra lại toàn bộ SHA-256 trước khi cài. Không cần tải/ghép/giải nén 5 phần RAR. Nếu chưa cấu hình ID, nguồn cũ vẫn dùng được. Nếu đã cấu hình nhưng không truy cập được Drive, bước tải thất bại rõ ràng, không âm thầm đổi nguồn hoặc bỏ checksum.

Người dùng tải ISO và `SHA256SUMS.txt` cùng thư mục, rồi chạy `sha256sum -c SHA256SUMS.txt` trên Linux hoặc `Get-FileHash .\SIMULIA_Abaqus_2020_Linux64.iso -Algorithm SHA256` trên PowerShell. Môi trường cài và license vẫn theo quy trình của project; lưu lại ISO không mở các cổng nghiệm thu production.
