# Cấu trúc workspace và nơi lưu tệp

## Repository trên GitHub

`honeycomb-abaqus-studio/` là repository mã nguồn. Các đường dẫn `src/`, `desktop/`, `web/`, `scripts/`, `tests/`, `contracts/` và `.github/workflows/` được giữ vì build, import và workflow đang sử dụng chúng.

Tài liệu được chia theo chủ đề trong [mục lục](../README.md). `DESIGN.md` và `PRODUCT.md` nằm ở gốc; `web/DESIGN.md` và `web/DEPLOYMENT.md` đi cùng ứng dụng web.

## Workspace nghiên cứu trên máy

```text
C:/UET/DO_AN/
├── README.md                       # Bản đồ workspace
├── honeycomb-abaqus-studio/         # Repository Git
├── research/
│   ├── papers/                     # Bài báo gốc
│   ├── translations/               # Bản dịch PDF
│   ├── media/                      # Video tham chiếu
│   └── notes/                      # Ghi chú nghiên cứu
├── mo_phong/
│   ├── Honeycomb-paper-7J/          # Mô hình nền
│   ├── Auxetic-2-orientations-7J/   # Hai hướng lõi auxetic
│   └── video-reference/            # CAE/ODB đối chiếu video
├── honeycomb-data/                 # Thư viện ứng dụng
├── honeycomb-data-retained/        # Bản giữ lại độc lập
├── honeycomb-validation/           # Kiểm chứng Abaqus
├── honeycomb-drive-validation/     # Kiểm chứng Drive
├── output/                         # Bộ dữ liệu và kết quả xuất
├── tmp/                            # Chẩn đoán và tệp làm việc
└── local/archive/2026-11-02/        # Tệp phát sinh đã lưu và nhật ký
```

Các thư viện dữ liệu và hai mô hình 7 J giữ đường dẫn hiện có vì cấu hình, script và nguồn truy vết đang tham chiếu chúng. Khi cần chuyển thư viện, dùng chức năng quản lý/backup và cấu hình lại data root.

## Đặt tệp mới ở đâu?

Các đường dẫn dưới đây tính từ gốc repository.

| Loại tệp | Nơi lưu |
| --- | --- |
| Engine và adapter dùng chung | `src/honeycomb_studio/` |
| Công cụ tái sử dụng | `scripts/` |
| Chẩn đoán một lần | `../tmp/` |
| Input mẫu nhỏ | `examples/` |
| Hướng dẫn | Nhóm phù hợp trong `docs/` |
| Bằng chứng nhỏ | `docs/evidence/` |
| Kết quả kiểm tra cục bộ | `output/` |
| Bộ dữ liệu xuất trên máy | `../output/` |
| Bản đóng gói và runtime | `artifacts/` |
| Bài báo, bản dịch và ghi chú | `../research/` |

`.venv/`, `.tools/`, `web/node_modules/` và kết quả build do công cụ quản lý. Launcher và Windows Task Scheduler có thể trỏ vào `artifacts/`; kiểm tra các đường dẫn trước khi chuyển bản đóng gói.

## Sắp xếp ngày 02/11/2026

- Gom tài liệu rời vào `research/` và bộ đối chiếu video vào `mo_phong/video-reference/`.
- Lưu replay Abaqus, cache kiểm thử/lint, wheel cũ và bản sao script dựng 7 J ở kho lưu cục bộ. Script chính trong `Honeycomb-paper-7J/` giữ nguyên.
- Chia 25 tài liệu trong repo theo chủ đề và cập nhật liên kết.
- Cập nhật đường dẫn PDF cho script số hóa bài báo; đưa ảnh nghiệm thu auxetic vào `docs/evidence/` để GitHub hiển thị được.
- Chuyển README cũ sang [sổ tay vận hành](../guides/OPERATIONS.md), viết lại trang giới thiệu và mục lục.

Đợt sắp xếp không dùng cấu hình ẩn của Explorer. Manifest tại `local/archive/2026-11-02/` trong workspace ghi nguồn/đích và checksum khi chuyển; `document-moves.json` ghi đường dẫn tài liệu trong repo.
