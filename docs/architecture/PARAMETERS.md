# Tham số và đơn vị

Schema máy đọc: `contracts/batch-spec.schema.json`; catalogue: `contracts/parameters.json`. API `/v1/template` cung cấp cùng thông tin. Các giá trị request được lưu trước khi derive; resolved là giá trị thật gửi tới adapter.

## Quy ước

UI/API dùng mm, kg cho đầu va đập, kg/m³ cho density, m/s, J và MPa. Adapter quy đổi về **mm–tonne–s–N–MPa**. Năng lượng ODB N.mm chia 1.000 để ra J; mật độ kg/m³ nhân 1e-12 để ra tonne/mm³; kg chia 1.000 để ra tonne; m/s nhân 1.000 để ra mm/s.

`impact_mass=mass_kg/1000`; `velocity=velocity_m_s*1000`. `energy_J` độc lập khi `loading=energy`, ngược lại tính E từ vận tốc. Các mức năng lượng là động năng ban đầu; có gravity nên động năng ở lúc chạm tăng thêm một lượng nhỏ theo khe hở.

## Hình học

`panel`: cạnh tấm vuông. `skin`, `bottom_skin`: chiều dày mặt; null mặt dưới liên kết theo mặt trên. `core_height`, `cell_size`, `foil`: chiều cao, khoảng cách giữa hai cạnh đối diện ô và foil đơn. Vách ghép đôi có chiều dày 2×foil, không tạo hai vách chồng lặp. `core_angle`, `phase_x/y`: hướng/pha mạng ô. Vùng lõi cắt theo tấm, nên density hữu hạn có thể khác density tuần hoàn.

`periodic_density_kg_m3=8*foil*rho/(3*cell_size)`. Density lá nhôm vẫn là density vật liệu (mặc định 2.700 kg/m³), không dùng 72 kg/m³ cho shell foil.

## Vật liệu

Face/core material tách riêng; hỗ trợ perfect plastic, bilinear, shifted Ramberg–Osgood hoặc bảng trực tiếp true stress/plastic strain. Bảng phải bắt đầu ở plastic strain 0, strain tăng và stress không giảm.

Ramberg–Osgood được dịch về điểm chảy: `ep=alpha*sy/E*((sigma/sy)^m-1)`. Đây là quy ước tái dựng được ghi công khai, không phải bảng gốc do tác giả cung cấp. Bilinear dùng `H=E*Et/(E-Et)` cho stress theo plastic strain. UTS chỉ là metadata; không dùng làm tiêu chuẩn xóa phần tử và không được chọn làm biến khảo sát. Tên/UTS không tách physical-design grouping.

## Contact, kẹp và đầu va đập

Vùng ngoài lỗ tròn bị ngàm trên cả hai mặt, sáu bậc tự do bằng 0. Tie mặt–lõi hoàn hảo; core self-contact luôn bật. Có thể bật self-contact mặt và ma sát. Không có mô hình tách keo, fracture hoặc element deletion trong phiên bản đầu.

Đầu cầu rigid mesh có point mass correction để khối lượng tổng đúng `mass_kg`. Khi đường kính/khối lượng đổi, effective density được scale; trọng lực đặt lên cả rigid elements và phần mass correction. Chỉ Z tự do.

## Lưới, solver và output

Reference: core 0,7/1,3 mm, radius 22 mm, z divisions 20; skin 0,75/1,25 mm, patch nửa cạnh 12 mm; ball seed 1 mm. Quick scale seed ×1,4 và giảm lớp; fine ×0,8 và tăng lớp. Custom dùng giá trị nhập. Shell S4R/S3R, C3D4 cho rigid mesh, Simpson 5 điểm mặc định.

Duration 0,006 s; field_intervals 120; history_intervals 1.200; CPU 8; double precision; mass scaling tắt. Giới hạn tài nguyên thuộc BatchSpec: reserve đĩa 20 GB, available RAM 2 GiB mặc định, một solver. Các lựa chọn số học không tự đổi để ép thời gian.

`field_variables`, `history_variables` hiển thị/chỉnh qua JSON; bỏ biến cần cho summary sẽ tạo lỗi trích xuất rõ ràng. Abaqus datacheck xác nhận biến/keyword được phiên bản cài đặt hỗ trợ.
