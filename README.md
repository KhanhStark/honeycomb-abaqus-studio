# Honeycomb Abaqus Studio

Ứng dụng nghiên cứu va đập vận tốc thấp trên tấm sandwich nhôm lõi honeycomb và auxetic: dựng mô hình Abaqus, khảo sát tham số, theo dõi solver, trích xuất kết quả và xuất dữ liệu có thể truy vết.

**Giao diện:** Windows WinUI 3 và web React/TypeScript. **Engine:** Python 3.13, FastAPI và SQLite. Adapter chạy bằng Python đi kèm Abaqus, tách khỏi môi trường Python của engine.

[Mở web](https://honeycomb-abaqus-studio.vercel.app) · [Tải bản Windows](https://github.com/xuankhanh24/honeycomb-abaqus-studio/releases/tag/v0.2.0-preview) · [Tài liệu](docs/README.md) · [GitHub Actions](https://github.com/xuankhanh24/honeycomb-abaqus-studio/actions)

## Chức năng

- Dựng lõi lục giác và auxetic re-entrant 0°; chỉnh hình học, vật liệu, tải, liên kết và lưới.
- Khảo sát bằng grid, Latin Hypercube hoặc CSV; kiểm tra input trước khi chạy.
- Điều phối mô phỏng cục bộ và cloud; lưu trạng thái, log và lịch sử từng attempt.
- Đọc CAE/ODB, xuất đường cong, CSV/Parquet, PDF/DOCX và gói kết quả có checksum.
- Tổng hợp dữ liệu X/y, sàng lọc chất lượng, khử trùng đầu vào và chia tập theo thiết kế.
- Sao lưu Google Drive và khôi phục dữ liệu đã lưu.

Solver hoàn tất, đạt chất lượng số và được kiểm chứng vật lý là các mức đánh giá riêng. Xem [kiểm chứng khoa học](docs/research/SCIENTIFIC_VALIDATION.md) và [hồ sơ nghiệm thu](docs/validation/VALIDATION_RESULTS.md). Các ghi nhận có ngày phản ánh thời điểm nghiệm thu; số mẫu hiện tại được đọc từ catalog hoặc `collection.json` của bộ dữ liệu.

## Cấu trúc repository

```text
honeycomb-abaqus-studio/
├── .github/workflows/        # CI, mô phỏng cloud và khôi phục
├── contracts/               # JSON Schema và danh mục tham số
├── desktop/HoneycombStudio/ # Giao diện Windows WinUI 3
├── docs/
│   ├── README.md            # Mục lục tài liệu
│   ├── guides/              # Sử dụng và vận hành
│   ├── architecture/        # Kiến trúc, API và dữ liệu
│   ├── cloud/               # Job, Drive, ML và runtime Linux
│   ├── development/         # Phát triển và đóng gói
│   ├── research/            # Mô hình và kiểm chứng khoa học
│   ├── validation/          # Hồ sơ kiểm thử và nghiệm thu
│   ├── evidence/            # Bằng chứng JSON và hình ảnh
│   ├── CLOUD_WEB.md         # Địa chỉ tài liệu API đang liên kết
│   └── CLOUD_STATUS.md      # Lịch sử trạng thái cloud
├── examples/                # Input mẫu JSON/CSV
├── scripts/                 # Setup, chạy, kiểm thử và vận hành
├── src/honeycomb_studio/    # Engine Python và adapter Abaqus
├── tests/                   # Kiểm thử Python và C#
├── web/                     # React/TypeScript và API web
├── DESIGN.md                # Quy ước giao diện desktop
├── PRODUCT.md               # Phạm vi sản phẩm
├── HoneycombStudio.sln      # Solution .NET
├── global.json              # Phiên bản .NET SDK
├── pyproject.toml           # Dự án Python
└── uv.lock                  # Dependency Python đã khóa
```

## Chạy bản Windows

Giải nén đầy đủ [bản 0.2.0 preview](https://github.com/xuankhanh24/honeycomb-abaqus-studio/releases/tag/v0.2.0-preview), rồi mở `HoneycombStudio.exe`. Gói có runtime .NET/WinAppSDK và Python riêng; cần Abaqus cùng license phù hợp. Đây là bản preview nghiên cứu chưa ký mã.

## Chạy từ mã nguồn

Yêu cầu Windows x64, .NET SDK **10.0.402** theo `global.json`, `uv`, Python **3.13** và Abaqus đã cài. Mô hình nền dùng Abaqus/Explicit 2017 trên Windows; môi trường Linux có [hồ sơ runtime riêng](docs/CLOUD_WEB.md).

```powershell
git clone https://github.com/xuankhanh24/honeycomb-abaqus-studio.git
cd honeycomb-abaqus-studio
./scripts/setup.ps1
./scripts/start-app.ps1
```

Ứng dụng kết nối hoặc khởi động engine nền. Xem [khởi chạy độc lập](docs/guides/INDEPENDENT_LAUNCH.md) để hiểu vòng đời ứng dụng và solver.

Cấu hình nơi lưu dữ liệu và lệnh Abaqus trong **Backup và cài đặt**; thay đổi có hiệu lực ở lần khởi động engine tiếp theo.

## Phát triển web

```powershell
cd web
npm ci
npm run dev
```

Vite chuyển tiếp `/api` và `/auth` tới backend ở `127.0.0.1:8765`. Cấu hình backend và đăng nhập nằm trong [hướng dẫn cloud](docs/CLOUD_WEB.md); xem [triển khai web](web/DEPLOYMENT.md) khi phát hành.

## Kiểm thử và đóng gói

Từ thư mục gốc repo:

```powershell
./scripts/test.ps1
./scripts/publish.ps1
```

Kiểm tra riêng web:

```powershell
cd web
npm run build
npm test
```

Kiểm thử bằng solver giả lập kiểm tra phần mềm và điều phối. Kiểm chứng mô phỏng thật cần Abaqus/license và [quy trình khoa học](docs/research/SCIENTIFIC_VALIDATION.md). Hướng dẫn license server, chạy bù, đóng gói lại và tải dữ liệu đầy đủ được giữ trong [sổ tay vận hành](docs/guides/OPERATIONS.md).

## Tài liệu theo công việc

| Công việc | Tài liệu |
| --- | --- |
| Tạo job, theo dõi và xuất báo cáo | [Hướng dẫn sử dụng](docs/guides/USER_GUIDE.md) |
| Hiểu input, đơn vị và API | [Tham số](docs/architecture/PARAMETERS.md), [API](docs/architecture/API.md) |
| Lấy bảng huấn luyện và dữ liệu solver | [Quy trình dữ liệu ML](docs/cloud/ML_DATA_WORKFLOW.md) |
| Sao lưu và khôi phục | [Google Drive](docs/cloud/DRIVE_BACKUP.md) |
| Sửa lỗi và phát triển | [Xử lý lỗi](docs/guides/TROUBLESHOOTING.md), [Phát triển](docs/development/DEVELOPMENT.md) |
| Kiểm tra phạm vi kết quả | [Nghiệm thu](docs/validation/VALIDATION_RESULTS.md), [Trạng thái cloud](docs/CLOUD_STATUS.md) |

Mô hình nền dựa trên Foo, Seah & Chai, *Composite Structures* 85 (2008), DOI [10.1016/j.compstruct.2007.10.016](https://doi.org/10.1016/j.compstruct.2007.10.016). CAE/ODB, bộ dữ liệu lớn, bản phát hành và cấu hình xác thực được quản lý ngoài mã nguồn.
