# Chạy độc lập với ChatGPT

`Start-Process` hoặc `CreateNoWindow` chỉ mở tiến trình mới/ẩn console; chúng không bảo đảm thoát khỏi Windows Job Object của chương trình đang gọi. Khi app/engine được mở từ công cụ trong ChatGPT, đóng chương trình chủ có thể kết thúc cả cây tiến trình và solver. Đây là lỗi triển khai cách khởi chạy, không phải lỗi kết quả Abaqus.

Chạy `scripts/start-independent.ps1` hoặc shortcut **Honeycomb Abaqus Studio** trên Desktop. Script đăng ký hai tác vụ Windows **chỉ chạy theo yêu cầu**, không có trigger, không chạy định kỳ, không tự chạy khi đăng nhập:

- `HoneycombStudio-Engine`: chạy Python nền bằng tài khoản người dùng hiện tại, không lưu mật khẩu; không giới hạn thời gian thực thi. Engine có log tại `%LOCALAPPDATA%/HoneycombStudio/logs/engine.log`.
- `HoneycombStudio-UI`: chạy giao diện độc lập. Đóng UI không ra lệnh dừng job.

Hai tác vụ tách biệt và do Task Scheduler khởi chạy. EngineClient ưu tiên tác vụ engine đã đăng ký khi cần khởi động engine, thay vì tạo engine dưới tiến trình UI. Vẫn có cơ chế khóa một engine/người dùng.

Lệnh `scripts/start-independent.ps1 -EngineOnly` chỉ mở engine. `scripts/start-app.ps1` dùng cách chạy độc lập này. Dừng job qua nút Dừng hoặc Dừng sau lượt hiện tại trong app; đóng ChatGPT không phải thao tác dừng job. Máy vẫn phải bật và không Sleep/Shutdown.

## Cấu hình của ứng dụng đóng gói Windows

ChatGPT cài qua MSIX có thể chuyển hướng AppData sang `Packages/OpenAI.Codex_2p2nqsd0c76g0/LocalCache/Local/HoneycombStudio`. App mở từ Windows dùng AppData thông thường. Khi chuyển lần đầu, sao chép cấu hình OAuth và token DPAPI sang thư mục HoneycombStudio của cùng tài khoản Windows; không sao chép file lock hoặc session cũ. Không đưa cấu hình hoặc token lên Git.

## Xác minh

Kiểm tra chuỗi cha của engine/UI: `svchost.exe` (dịch vụ Task Scheduler), `services.exe`, `wininit.exe`; không có ChatGPT/codex trong chuỗi. Xác nhận API health, PID trong session, không có solver trùng và job tiếp tục. Kiểm tra danh sách tác vụ có **0 trigger**. Trạng thái đang chạy phải lấy từ engine hiện tại, không dùng session cũ trong AppData chuyển hướng.

Đóng ChatGPT không được làm mất engine. Đăng xuất Windows, tắt máy hoặc Sleep vẫn có thể làm gián đoạn mô phỏng; tiếp tục hàng đợi sẽ chạy lại lượt bị gián đoạn từ đầu và giữ các lượt hoàn tất.

Để gỡ cơ chế mở độc lập, dừng job và đóng app trước, rồi xóa hai tác vụ trên trong Task Scheduler và shortcut Desktop. Không xóa dữ liệu mô phỏng.
