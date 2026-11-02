# Xử lý lỗi

| Hiện tượng | Kiểm tra / hành động |
|---|---|
| Không kết nối engine | Chạy start-engine.ps1 để xem lỗi; kiểm tra uv sync, session cũ và engine đang chạy. Không chạy hai engine cùng catalog. |
| Máy chỉ có .NET 8 | Cài SDK 10.0.402 hoặc dùng bản phát hành self-contained. Script ưu tiên `%USERPROFILE%/.dotnet/dotnet.exe`. |
| Job chưa chạy vì RAM/đĩa | Xem resource_error; giải phóng tài nguyên/chọn ổ dữ liệu đủ chỗ rồi tiếp tục. Không tự hạ lưới/đổi vật lý. |
| Abaqus không tìm thấy | Sửa lệnh trong cài đặt cho lần engine khởi động kế tiếp; kiểm tra launcher .bat dùng đúng phiên bản. |
| License không có | Xem log giai đoạn/datacheck; khôi phục license rồi tiếp tục/chạy lại lượt. Không đổi physics để xử lý license. |
| Datacheck lỗi | Xem .dat và checking.log, input thực tế và contact/Tie. Lượt lỗi không vào dataset. |
| Solver xong nhưng lượt lỗi | Xem failed_phase. Nếu lỗi trích xuất/render/PDF, retry sử dụng ODB đã hoàn tất. |
| ODB hỏng/thiếu output | Giữ bản gốc, xem inventory. Missing bắt buộc gây lỗi rõ ràng, không tự sinh số 0. |
| RF3 gần 0 | RP tự do Z; dùng contact resultant hoặc m(A3+g) với đúng mô hình dẫn hướng. |
| Output trường thiếu lớp shell | Chỉ xuất được section points đã ghi trong ODB; số điểm tích phân của section không có nghĩa mọi điểm đều đã được yêu cầu output. |
| CSV trường rất lớn | Dùng Parquet mặc định hoặc chọn field; CSV tách theo frame/khối, kèm metadata. |
| Báo cáo không có ảnh | Kiểm tra render_images và rendering.log, CAE license/khả năng render trên máy. Không thay ảnh thực bằng ảnh giả. |
| Drive cần đăng nhập lại | Testing OAuth có thể hết hạn; đăng nhập lại từ app. Không sửa token bằng tay hoặc commit client credential. |
| Upload không tiếp tục | Kiểm tra quota/mạng; session hết hạn cần tạo phiên mới. Giữ ZIP local để kiểm tra checksum. |
| Khôi phục checksum sai | Dừng dùng bản khôi phục; tải lại gói gốc. Không bỏ kiểm tra toàn vẹn. |

Log theo attempt nằm trong logs và raw; events trong SQLite/manifest giữ lịch sử. Không xóa attempt cũ để che lỗi. Trước khi chia sẻ log, kiểm tra nội dung đường dẫn và thông tin nghiên cứu của bạn.
