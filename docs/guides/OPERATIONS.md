> Nội dung vận hành chuyển từ README ngày 02/11/2026. Các số liệu có ngày là hồ sơ lịch sử; xem catalog và hồ sơ nghiệm thu tương ứng để biết phạm vi của từng kết quả.

Chạy các lệnh trong tài liệu từ thư mục gốc repository `honeycomb-abaqus-studio/`.

# Honeycomb Abaqus Studio

Ứng dụng Windows **WinUI 3 + Python** để tự động hóa khảo sát va đập tấm sandwich honeycomb bằng **Abaqus/Explicit 2017**, tạo dữ liệu có thể truy vết và báo cáo nghiên cứu.

**Tiến độ cloud — 28/10/2026:** hai lượt research 7 J, panel 100 mm, thời gian 12 ms đã chạy thật trên GitHub Actions và đạt kiểm tra chất lượng số. Web có thư mục từng job và bảng tổng hợp 19 lượt đã lưu, gồm 2 mẫu huấn luyện được nhận. Hai mẫu chưa đủ đánh giá khả năng tổng quát hóa; hội tụ lưới và kiểm chứng thực nghiệm chưa được xác lập. Xem [hướng dẫn và kết quả nghiệm thu dữ liệu](../cloud/ML_DATA_WORKFLOW.md).

Mô hình nền tái dựng theo Foo, Seah & Chai, *Composite Structures* 85 (2008), DOI [10.1016/j.compstruct.2007.10.016](https://doi.org/10.1016/j.compstruct.2007.10.016). Mô hình không tự nhận là đã hội tụ hoặc tương đương thí nghiệm.

## Bản Windows x64

[Tải bản 0.2.0 preview](https://github.com/xuankhanh24/honeycomb-abaqus-studio/releases/tag/v0.2.0-preview). Giải nén đầy đủ vào đường dẫn ASCII, ví dụ `C:/HoneycombStudio`, rồi mở `HoneycombStudio.exe`. Bản này có .NET/WinAppSDK và Python riêng; Abaqus/license dùng bản đã cài trên máy. Không chạy exe tách khỏi các DLL/runtime đi kèm.

Xem [kết quả nghiệm thu](../validation/VALIDATION_RESULTS.md) để phân biệt các kiểm thử đã đạt với kiểm tra hội tụ, gián đoạn Abaqus thật và reboot chưa hoàn tất. Drive thật đã được kiểm tra upload, tiếp tục và khôi phục. Đây là bản nghiên cứu nội bộ chưa ký mã.

## Dữ liệu gọn từ bản 0.2.0

Nút **Dữ liệu ML gọn** xuất `samples.csv/Parquet` (mỗi lượt một dòng), đường cong và từ điển cột. Mặc định không nhân bản dữ liệu trường của ODB. PDF mỗi lượt 5 trang tiếng Việt; bảng dẻo và thống kê nút/phần tử nằm ngoài PDF. CSV nút/phần tử là chức năng nâng cao có thể tạo hàng chục GB, không cần cho mô hình ML dạng bảng.

## Cloud: chạy đồng thời và dữ liệu tổng hợp

**Mỗi lần bấm chạy tạo một job cha, một workflow và một thư mục dữ liệu chung**, chứa các lượt đồng thời. Trên web có nút **Mở thư mục dữ liệu job**, theo dõi Actions, tải ZIP nhỏ và gói đầy đủ ODB/CAE/INP. Có bảng **mọi kết quả đã mô phỏng** và bảng huấn luyện chỉ gồm mẫu đạt chất lượng. Xem [hướng dẫn thư mục, X/y và sửa mẫu chưa đạt](../cloud/ML_DATA_WORKFLOW.md).

Web cho phép **100 lượt mỗi batch, tối đa 20 runner đồng thời**, mỗi runner giải một lượt.
Giới hạn 8 trước đây do ứng dụng tự đặt; giới hạn batch 10 cũng đã được nâng lên 100.
[GitHub Free cho phép 20 job đồng thời trên runner tiêu chuẩn](https://docs.github.com/en/actions/reference/limits#job-concurrency-limits-for-github-hosted-runners).
Quota này dùng chung với các workflow khác của tài khoản. License Abaqus, CPU/RAM/đĩa và thời gian cài đặt vẫn quyết định khả năng chạy thực tế.
Chọn **Đồng thời** và nhập số runner mong muốn ở web. **Một lượt = một Actions job**, một đợt = một lần gửi khoảng tham số (tối đa 100 lượt). Giới hạn song song trên web áp dụng cho từng đợt; quota tài khoản dùng chung cho mọi đợt và CI. Ví dụ 21 lượt, mức song song 20: lượt còn lại có thể nhận slot khi một job kết thúc. Một đợt khác cũng được đưa vào hàng đợi ngay, không chờ cả đợt trước hoàn thành. GitHub quyết định thứ tự cấp runner; license vẫn phải đủ cho số solver thực tế.

**Chỉ tổng hợp đợt đã kết thúc toàn bộ lượt** (kể cả lượt lỗi). Dữ liệu của đợt đang chạy được ghi rõ là đang chờ và chưa đưa vào bảng huấn luyện chung. Lượt lỗi có báo cáo, không được giả thành mẫu đạt; chạy bù giữ nguyên lượt thành công. Mỗi đợt giữ nguyên mã, thư mục, đầu vào, kết quả từng lượt và checksum. Các bước xuất bảng chung dùng hàng đợi riêng `queue: max`, tránh ghi đè giữa các đợt; chúng không khóa các job mô phỏng.

Web hiển thị **chờ runner / đang xử lý / đã lưu / lỗi**, nút **Mở Actions hiện tại**, **Mở log job của lượt** và **Mở thư mục dữ liệu**. Khi API GitHub tạm lỗi, web ghi rõ số chờ dựa trên catalog. Bản tổng hợp toàn bộ dữ liệu vẫn có CSV/Parquet và báo cáo loại mẫu.

Kiểm tra hàng đợi độc lập: workflow **Kiểm thử hàng đợi nhiều đợt** chạy 21 + 3 job nhỏ, tổng hợp riêng sau từng đợt và kiểm SHA-256. Artifact `queue-fixture-*` là dữ liệu kiểm thử hạ tầng, không phải mô phỏng Abaqus, không đưa vào catalog/huấn luyện.
Trên máy cá nhân, worker vẫn kiểm tra tài nguyên trước khi nhận lượt.

### Đầu vào và đầu ra là gì?

| Giai đoạn | Đầu vào | Đầu ra |
| --- | --- | --- |
| Mô phỏng Abaqus | Hình học: panel, skin, core_height, foil, cell_size… (mm); vật liệu; ngàm; năng lượng (J) hoặc vận tốc (m/s); lưới; thời gian (s) | Kết quả lực (N), chuyển vị (mm), năng lượng (J), ứng suất (MPa), đường cong theo thời gian; trạng thái và kiểm tra chất lượng |
| Huấn luyện dạng bảng | **X**: đúng các cột `input.*` trong `dataset.json.features`, gồm hình học, tải, ngàm và tham số vật liệu được chọn | **y**: chọn một hoặc nhiều cột trong `dataset.json.targets` theo bài toán; ví dụ lực cực đại, chuyển vị cực đại hoặc SEA |

Ví dụ mục tiêu dự đoán:

| Tên cột giữ nguyên trong dữ liệu | Ý nghĩa | Đơn vị |
| --- | --- | --- |
| `peak_raw_contact_force_N` | Lực tiếp xúc cực đại từ các mẫu đã ghi | N |
| `max_top_centre_downward_mm` | Chuyển vị xuống cực đại tại tâm tấm mặt trên | mm |
| `physical_dissipation_J` | Năng lượng tiêu tán vật lý theo các kênh năng lượng đã ghi | J |
| `SEA_J_kg` | Năng lượng tiêu tán vật lý chia cho khối lượng tấm sandwich | J/kg |
| `mises_max_MPa` | Ứng suất von Mises cực đại trong các frame đã ghi | MPa |

`run_id`, `batch_id`, `design_id`, `input_hash`, `split`, số attempt và thông tin chất lượng dùng **truy vết/chia tập**, không đưa vào X.
Các chỉ số sai số/năng lượng nhân tạo dùng sàng lọc chất lượng; chọn y vật lý phù hợp thay vì dùng tất cả cột một cách máy móc.
Lưới, CPU và thời gian mô phỏng được lưu trong `resolved.json` để kiểm tra; không phải mọi tham số mô phỏng đều được chọn làm X mặc định.
Biến phân loại cần mã hóa, ô trống/null là giá trị thiếu, không tự thay bằng 0.

### Lấy file chung ở đâu?

Trên **web → Dữ liệu → Dữ liệu huấn luyện tổng hợp** có nút tải CSV, Parquet, ZIP, tổng hợp lại và theo dõi Actions.
Mỗi batch cloud kết thúc sẽ tự chạy tổng hợp từ các job đã có bản lưu hoàn tất; cũng có thể chạy riêng workflow [Tổng hợp dữ liệu huấn luyện](https://github.com/xuankhanh24/honeycomb-abaqus-studio/actions/workflows/collect-training.yml).
Bản tổng hợp được phát hành dưới tag `training-<workflow-id>-<attempt>`, giữ lịch sử từng phiên bản và SHA-256.
Không cần bật Abaqus hoặc license để chỉ tổng hợp dữ liệu đã lưu.

```text
honeycomb-training-<workflow-id>-<attempt>/
├── README.md                         # Hướng dẫn đọc bộ dữ liệu
├── collection.json                   # Số mẫu, số lượt, thời điểm tổng hợp
├── 01_training/
│   ├── samples.csv                   # FILE HUẤN LUYỆN CHUNG: mỗi dòng một mẫu đạt
│   ├── samples.parquet               # Cùng bảng, định dạng có kiểu cho Python
│   ├── dataset.json                  # Danh sách X/y, số mẫu và chia tập
│   ├── readiness.json                # Thiếu đầu vào/đầu ra, số mẫu và độ phủ chia tập
│   ├── data-dictionary.csv/json      # Tên cột, tiếng Việt, đơn vị, vai trò
│   ├── FIELD_DESCRIPTIONS.md
│   ├── curves/<run-id>/              # Đường cong của mẫu được chọn, nếu có
│   └── provenance/<run-id>/          # Đầu vào, kết quả, chất lượng của mẫu
├── 02_audit/
│   ├── source-jobs.json              # Tên bài, ID, link release, checksum nguồn
│   ├── run-selection.csv             # Nhận/loại từng lượt và lý do
│   └── input-output-contract.json    # X, y ứng viên và cột chỉ để truy vết
├── 03_simulations/
│   └── job--<ten-bai-khong-dau>--<id12>/run-0001--delta-20deg--energy-7J--<run-id>/
│       ├── input/requested.json      # Đầu vào người dùng yêu cầu
│       ├── input/resolved.json       # Đầu vào thực tế sau xử lý
│       └── output/
│           ├── summary.json          # Chỉ số kết quả
│           ├── quality.json          # Kiểm tra chất lượng
│           └── attempt-001/          # Đường cong theo thời gian, nếu có
├── 05_all_results/
│   └── simulation-results.csv/parquet # Mọi lượt, kể cả review/smoke, có lý do nhận/loại
└── artifact-manifest.json            # Danh sách tệp và SHA-256
```

Tên thư mục chứa tên bài không dấu và ID; từng lượt có số thứ tự, góc và năng lượng để đối chiếu. Tên bài gốc nằm trong `source-jobs.json`.
Mỗi job còn có gói dữ liệu đầy đủ riêng: `04_solver_archive` giữ ODB/CAE/INP, log và báo cáo gốc. Trên web mở **Thư mục dữ liệu job** để tải ZIP đầy đủ hoặc `download_full.py` khi gói được chia nhiều phần; checksum được kiểm tra khi tải. Thư mục solver đang chạy giữ nguyên.
Chỉ nhận lượt `completed`, `ml_eligible=true`, không phải `test_only`. Smoke/review/failed giữ hồ sơ nhưng không vào bảng huấn luyện.
Khử trùng `input_hash` trên toàn bộ job, chia train/validation/test theo `design_id` toàn cục; dùng cột `split` có sẵn để tránh rò rỉ dữ liệu.
Nếu chưa có mẫu đạt, `samples=0`, CSV chỉ có tiêu đề; không coi đó là bộ dữ liệu đã sẵn sàng huấn luyện.
Job chưa có bản lưu hoàn tất được ghi lý do trong `source-jobs.json`; lỗi checksum hoặc thiếu nguồn đã xác nhận sẽ làm bước tổng hợp thất bại và giữ bản tổng hợp trước đó.

## Chức năng

- Chọn lõi lục giác hoặc **auxetic re-entrant hình 1 — 0°**; chỉnh kích thước ô lõm, dịch pha X/Z và lưới chiều sâu Y. Xem [kiểm tra tích hợp](../validation/AUXETIC_0_VALIDATION.md).
- Xem/sửa hình học, bảng vật liệu, điều kiện tải, liên kết, lưới và output; preview input thực tế và toàn bộ lượt trước khi chạy.
- Quét năng lượng/vận tốc với bước nhảy, tổ hợp nhiều biến, Latin Hypercube có seed hoặc bảng CSV.
- Thực thi tuần tự hoặc đồng thời có kiểm tra tài nguyên; cloud hỗ trợ tối đa 20 runner trong một batch; tiến độ vật lý, ETA, log, CPU/RAM và datacheck.
- Dừng hàng đợi hoặc dừng ngay; tiếp tục lượt bị dừng từ đầu, giữ các lượt đã hoàn tất và mọi attempt.
- Mở CAE/ODB bằng Abaqus; mặc định xuất chỉ số, đường cong và cực trị để huấn luyện/tối ưu; chế độ nâng cao sao chép mọi field ODB sang Parquet.
- CSV, JSON, Parquet, PDF từng lượt/toàn job, ZIP64 có manifest và checksum.
- Tập dữ liệu có chia nhóm thiết kế để tránh rò rỉ train/test; đường cong gốc và nội suy riêng; so sánh Pareto theo cùng điều kiện tải.
- Google Drive OAuth, upload tiếp tục, kiểm tra checksum và khôi phục về job mới.

## Chạy từ mã nguồn

Yêu cầu Windows x64, .NET SDK **10.0.402**, `uv`, Python 3.13 (uv có thể cung cấp) và Abaqus đã cài/license hợp lệ. Python hiện đại không thay thế Python của Abaqus.

```powershell
git clone https://github.com/xuankhanh24/honeycomb-abaqus-studio.git
cd honeycomb-abaqus-studio
./scripts/setup.ps1
./scripts/start-app.ps1
```

Ứng dụng tự kết nối/khởi động engine nền. Đóng giao diện không dừng solver. Xem log engine trực tiếp bằng `./scripts/start-engine.ps1` khi chưa có engine khác.

Dữ liệu mặc định: `C:/UET/DO_AN/honeycomb-data`; lệnh Abaqus: `C:/SIMULIA/Commands/abaqus.bat`. Đổi trong **Backup và cài đặt** cho lần khởi động engine tiếp theo. File session/token nằm trong `%LOCALAPPDATA%/HoneycombStudio`, không đưa vào repo.

## Bật cấp license cho GitHub Actions bằng CMD

GitHub Actions kết nối qua **Tailscale** tới dịch vụ **SIMULIA FlexNet Server** trên máy chủ dự án để xin license. Máy này phải bật, có Internet và không Sleep/Hibernate trong suốt lượt mô phỏng. Không cần mở Abaqus hoặc upload key mỗi lần chạy.

Trên máy Windows đang giữ license, tìm **CMD** trong Start → chọn **Run as administrator**, rồi chạy:

```cmd
sc config "SIMULIA FlexNet Server" start= auto
net start "SIMULIA FlexNet Server"
net start Tailscale
"C:\Program Files\Tailscale\tailscale.exe" up
```

Nếu Tailscale hiện đường dẫn đăng nhập, mở đường dẫn đó và đăng nhập tài khoản đã cấu hình cho dự án. Nếu báo dịch vụ đã chạy rồi thì không cần khởi động lại.

Kiểm tra dịch vụ và kết nối:

```cmd
sc query "SIMULIA FlexNet Server"
sc query Tailscale
"C:\Program Files\Tailscale\tailscale.exe" status
```

Hai dịch vụ cần hiện **RUNNING**; Tailscale cần kết nối, không báo đang đăng xuất hoặc đã dừng. Đây là kiểm tra dịch vụ/mạng; Actions sẽ kiểm tra kết nối và khả năng lấy license thực tế khi chạy.

Để máy không tự ngủ hoặc tự Hibernate **khi cắm điện**, chạy:

```cmd
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
```

Các lệnh trên thay đổi thiết lập nguồn hiện tại; không thay đổi hành vi khi gập nắp laptop. Giữ máy cắm nguồn và không gập nắp nếu thao tác đó làm máy ngủ. Sau khi mô phỏng kết thúc, có thể đặt lại thời gian trong **Settings → System → Power & battery**.

Sau đó mở [web quản lý](https://honeycomb-abaqus-studio.vercel.app) → đăng nhập **Chủ dự án** → **Công việc** → **Chọn bài đã lưu** → **Chạy mô phỏng**. Bấm **Theo dõi trên GitHub Actions** để xem log. Không đưa file license, key hoặc mật khẩu vào repo hay log công khai.

## Lưới mặc định

Lõi 0,7 mm tại vùng tâm bán kính 22 mm, ngoài 1,3 mm, 20 lớp theo chiều cao. Mặt 0,75/1,25 mm. Thời gian vật lý 6 ms, 120 khoảng field và 1.200 khoảng history. Tám CPU, double precision, không mass scaling. **20–30 phút là ngân sách dự báo, không phải cam kết cho mọi thiết kế và máy.** Thời gian trích xuất toàn field, PDF và backup được tính riêng.

## Kiểm thử và đóng gói

```powershell
./scripts/test.ps1
uv run python scripts/validate_abaqus.py --smoke
uv run python scripts/validate_abaqus.py --convergence
./scripts/publish.ps1
```

CI dùng solver giả lập chỉ để kiểm tra điều phối; kiểm thử mô phỏng thật cần máy có Abaqus. Script convergence chạy ba mức lưới 7 J và ghi tiêu chí/sai lệch, không tự ép kết quả khớp bài báo.

## Tài liệu

- [Hướng dẫn sử dụng](USER_GUIDE.md)
- [Kiến trúc và giao thức](../architecture/ARCHITECTURE.md), [API](../architecture/API.md)
- [Tham số và đơn vị](../architecture/PARAMETERS.md), [Từ điển dữ liệu](../architecture/DATA_DICTIONARY.md)
- [Kiểm chứng khoa học](../research/SCIENTIFIC_VALIDATION.md), [Nghiệm thu](../validation/ACCEPTANCE.md)
- [Google Drive](../cloud/DRIVE_BACKUP.md), [Xử lý lỗi](TROUBLESHOOTING.md)
- [Phát triển và phát hành](../development/DEVELOPMENT.md)

Repo chứa mã nguồn, tài liệu, schema và cấu hình nhỏ. CAE/ODB, dữ liệu huấn luyện, credential và bản phát hành được lưu riêng.

## Public web preview

[Open Honeycomb Studio](https://honeycomb-abaqus-studio.vercel.app) to inspect inputs, geometry and genuine Windows circular-clamp reference curves. Owner login and private runner connectivity are verified. The licensed Ubuntu solver remains blocked pending authorized Linux media and native qualification. See [measured cloud status](../CLOUD_STATUS.md) and [deployment settings and remaining acceptance](../CLOUD_WEB.md).


## Chạy bù lượt lỗi trên GitHub Actions

Nếu một job có một số lượt lỗi, dùng **Actions → Mô phỏng bài đã chọn từ web → Run workflow**:

- `job_id`: mã job gốc trên web.
- `recover`: bật `true`. Chỉ lượt lỗi hoặc thiếu bản lưu được chạy lại; lượt `completed`/`review` đã lưu được giữ nguyên.
- Toàn bộ lượt vẫn nằm trong cùng job và thư mục. Lịch sử lần chạy cũ được giữ, nguồn dữ liệu ghi đúng workflow của từng lượt.
- Job phải kết thúc trước khi chạy bù. Nếu mọi lượt đã lưu thành công và chỉ lỗi đóng gói, chạy workflow **Tổng hợp dữ liệu huấn luyện từ các job** với `job_id` gốc.

Ví dụ CMD (cần GitHub CLI đã đăng nhập):

```cmd
gh workflow run abaqus-linux.yml --ref main -f job_id=MA_JOB_GOC -f recover=true
```

Cập nhật catalog tự thử lại khi GitHub gặp lỗi tạm thời; mỗi lần ghi đọc lại phiên bản mới để giữ dữ liệu các runner khác. Bước tổng hợp/đóng gói có ngân sách 330 phút; lỗi đóng gói không làm mất các bản lưu solver trên Releases.


### Quản trị job theo tham số

Trong **Công việc → Mở bài**, xem tóm tắt tham số, bốn bước Đầu vào → Mô phỏng → Đóng gói → Tải dữ liệu và số lượt đã lưu. Mở từng lượt để xem chất lượng số, bản lưu gốc và workflow đúng lần thử; dùng bộ lọc lỗi/đang chạy để tìm lượt cần xử lý.

- **Chạy bù lượt lỗi**: xem phạm vi rồi xác nhận; giữ các lượt thành công trong cùng job/folder. Chỉ dùng khi workflow trước đã kết thúc.
- **Đóng gói lại dữ liệu đã lưu**: tạo gói dữ liệu từ Releases, không chạy solver. Dùng khi mô phỏng hoàn tất nhưng đóng gói lỗi/hết thời gian.
- **Mở Actions hiện tại** và **Mở thư mục dữ liệu** dẫn tới log và dữ liệu tương ứng. Actions cũ giữ nguyên trạng thái lịch sử.
- Các lượt mới được đặt tên từ input áp dụng, ví dụ `Lượt 21/21 · δ=45° · E=7 J · t=12 ms · CPU=4`. Tiêu đề workflow từ web ghi khoảng tham số và số lượt. Workflow đã khởi động giữ tiêu đề cũ.

Kiểm thử giao diện fixture (không khởi động solver): phục vụ `web/dist` tại `127.0.0.1:8768`, rồi chạy `uv run --locked --with playwright --extra cloud python scripts/verify_job_management_web.py` với Chrome đã cài.


### Tổng hợp nhanh, không nhân bản ODB

Các lần tổng hợp mới công bố CSV/Parquet toàn cục trước rồi cập nhật thư mục job. `download_full.py` lấy trực tiếp các phần solver đã xác minh trên GitHub Releases, thay vì chờ Actions tải xuống, nén và upload lại hàng chục GiB. Input vật lý, lưới, thời gian mô phỏng và tiêu chí chất lượng không đổi.

- Chạy `py download_full.py` trong thư mục tải. Có thể chạy lại sau mất mạng: tệp hoàn tất và từng phần có checksum đúng được dùng lại.
- Sau khi chạy bù, tải công cụ mới vào cùng thư mục: solver cũ không cần tải lại; lần thử mới có đường dẫn riêng dưới `04_solver_archive/run-XXXX/source-ID`.
- Bảng X/y, input/output và audit từng phiên bản nằm trong `00_dataset_versions/ID`; giữ các phiên bản trước, không ghi đè dữ liệu khác checksum.
- Chỉ các tệp nhỏ như bảng/đường cong, ZIP dễ đọc và manifest được tạo/upload lại. Các tệp TAR chứa field vẫn được giữ nguyên như bản lưu solver.
- Các gói ZIP đầy đủ lịch sử và công cụ cũ vẫn dùng được. Workflow đã khởi động dùng mã nguồn của lần khởi chạy; muốn áp dụng cách tổng hợp mới cho dữ liệu đã lưu, chạy lại workflow **Tổng hợp dữ liệu huấn luyện từ các job** trên `main`.
