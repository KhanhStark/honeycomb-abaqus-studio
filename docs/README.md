# Tài liệu Honeycomb Abaqus Studio

[Giới thiệu dự án](../README.md) · [Cấu trúc workspace](development/WORKSPACE_LAYOUT.md)

## Sử dụng và vận hành

- [Hướng dẫn sử dụng](guides/USER_GUIDE.md)
- [Khởi chạy độc lập](guides/INDEPENDENT_LAUNCH.md)
- [Xử lý lỗi](guides/TROUBLESHOOTING.md)
- [Sổ tay vận hành: license server, chạy bù và dữ liệu](guides/OPERATIONS.md)

## Kiến trúc và dữ liệu

- [Kiến trúc](architecture/ARCHITECTURE.md), [API](architecture/API.md)
- [Tham số và đơn vị](architecture/PARAMETERS.md), [từ điển dữ liệu](architecture/DATA_DICTIONARY.md)
- [Phạm vi sản phẩm](../PRODUCT.md), [thiết kế desktop](../DESIGN.md), [thiết kế web](../web/DESIGN.md)

## Cloud và bộ dữ liệu

- [Cấu hình cloud](CLOUD_WEB.md), [triển khai web](../web/DEPLOYMENT.md)
- [Lịch sử trạng thái cloud](CLOUD_STATUS.md)
- [Job và dữ liệu huấn luyện](cloud/ML_DATA_WORKFLOW.md)
- [Khảo sát góc và chạy đồng thời](cloud/ANGLE_BATCH.md)
- [Google Drive](cloud/DRIVE_BACKUP.md)
- [Runtime Linux](cloud/LINUX_MEDIA_FINDINGS.md)

`CLOUD_WEB.md` và `CLOUD_STATUS.md` giữ địa chỉ cũ vì API và giao diện đang liên kết trực tiếp tới hai tệp này.

## Nghiên cứu

- [Hình học và va đập](research/GEOMETRY_AND_IMPACT.md)
- [Ngàm chu vi](research/PERIMETER_CLAMP.md)
- [Kiểm chứng khoa học](research/SCIENTIFIC_VALIDATION.md)
- [Xuất trường theo luồng](research/ROLLING_FIELDS.md)

## Phát triển

- [Phát triển và phát hành](development/DEVELOPMENT.md)
- [Cấu trúc workspace và lưu tệp](development/WORKSPACE_LAYOUT.md)
- [Bộ cài Abaqus](development/INSTALLER_MEDIA.md)
- [Log GitHub Actions](development/actions-logging.md)

## Kiểm thử và nghiệm thu

- [Tiêu chí](validation/ACCEPTANCE.md), [kết quả](validation/VALIDATION_RESULTS.md)
- [Đối chiếu yêu cầu](validation/PLAN_ACCEPTANCE.md), [rà soát hoàn thành](validation/COMPLETION_REVIEW.md)
- [Auxetic 0°](validation/AUXETIC_0_VALIDATION.md), [va đập 7 J trên Linux](validation/LINUX_IMPACT_ACCEPTANCE.md)
- [Khắc phục cập nhật giao diện](validation/UI_REFRESH_FIX.md)
- [Hồ sơ JSON và hình ảnh](evidence/)
- [Kiểm tra sau khi sắp xếp workspace ngày 02/11/2026](validation/WORKSPACE_CLEANUP_20261102.md)

Các biên bản có ngày phản ánh thời điểm kiểm tra. Đối chiếu đúng phiên bản, mô hình và job khi sử dụng kết quả.
