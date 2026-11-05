"""Versioned, unit-explicit inputs; the resolved JSON is the solver contract."""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from decimal import Decimal
from typing import Annotated, Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator


def parameter(default: Any, title: str, unit: str = "", source: str = "Numerical choice", **kw):
    return Field(default, title=title, json_schema_extra={"unit": unit, "source": source}, **kw)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class JohnsonCook(StrictModel):
    """MPa, seconds, degrees Celsius; D3 follows the Abaqus convention."""
    A: float = Field(default=324, gt=0)
    B: float = Field(default=114, ge=0)
    n: float = Field(default=0.42, gt=0)
    C: float = Field(default=0.002, ge=0)
    m: float = Field(default=1.34, gt=0)
    reference_rate: float = Field(default=1, gt=0)
    transition_temperature: float = 20
    melting_temperature: float = 650
    d1: float = -0.77
    d2: float = 1.45
    d3: float = 0.47
    d4: float = 0
    d5: float = 1.6
    failure_displacement_mm: float = Field(default=0.1, gt=0)
    specific_heat_J_kg_K: float = Field(default=900, gt=0)
    inelastic_heat_fraction: float = Field(default=0.9, ge=0, le=1)
    source: str = "https://doi.org/10.1177/1687814018797794; M1; Abaqus D3 convention"
    status: Literal["reference_unvalidated"] = "reference_unvalidated"

    @model_validator(mode="after")
    def temperatures(self):
        if self.melting_temperature <= self.transition_temperature:
            raise ValueError("Melting temperature must exceed transition temperature")
        # Plane-stress shell domain, including biaxial tension and compression.
        if any(self.d1 + self.d2 * math.exp(-self.d3 * eta) <= 0
               for eta in (-2 / 3, -1 / 3, 0, 1 / 3, 2 / 3)):
            raise ValueError("Nonpositive Johnson-Cook fracture strain in shell stress domain")
        return self


class Material(StrictModel):
    name: str = "Aluminium"
    density: float = parameter(2700.0, "Khối lượng riêng", "kg/m³", "Paper Table 1", gt=0)
    young: float = parameter(70000.0, "Mô đun đàn hồi", "MPa", "Paper Table 1", gt=0)
    poisson: float = parameter(0.33, "Hệ số Poisson", "", "Paper Table 1", gt=-1, lt=0.5)
    yield_stress: float = parameter(117.0, "Giới hạn chảy", "MPa", "Paper Table 1", gt=0)
    ultimate: float = parameter(
        124.0, "Giới hạn bền (metadata, không xóa phần tử)", "MPa", "Paper Table 1", gt=0
    )
    johnson_cook: JohnsonCook | None = None
    hardening: Literal["shifted_ramberg_osgood", "perfect_plastic", "bilinear", "table", "johnson_cook"] = (
        "shifted_ramberg_osgood"
    )
    alpha: float = parameter(3 / 7, "Hệ số Ramberg–Osgood", "", "Paper Eq. 1; shifted at yield", gt=0)
    exponent: float = parameter(10.0, "Số mũ Ramberg–Osgood", "", "Paper Eq. 1", gt=1)
    tangent_ratio: float = parameter(0.7, "Et/E của bilinear", "", "Paper p.23", gt=0, lt=1)
    plastic_table: list[tuple[float, float]] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_table(self):
        if (self.hardening == "johnson_cook") != (self.johnson_cook is not None):
            raise ValueError("Johnson-Cook hardening and its complete material card must be specified together")
        if self.hardening == "table":
            t = self.plastic_table
            if not t or t[0][1] != 0 or any(s <= 0 or e < 0 for s, e in t):
                raise ValueError("Bảng dẻo phải bắt đầu tại biến dạng dẻo 0, stress > 0")
            if any(b[1] <= a[1] or b[0] < a[0] for a, b in zip(t, t[1:], strict=False)):
                raise ValueError("Biến dạng dẻo phải tăng; stress không được giảm")
        return self

    def table(self) -> list[list[float]]:
        if self.johnson_cook:
            # CAE placeholder only. The solver deck receives the complete JC card.
            return [[self.johnson_cook.A, 0.0]]
        if self.hardening == "table":
            return [list(v) for v in self.plastic_table]
        if self.hardening == "perfect_plastic":
            return [[self.yield_stress, 0.0]]
        ep = [0.0] + [10 ** (-6 + i * 6.5 / 160) for i in range(161)]
        if self.hardening == "bilinear":
            h = self.young * self.tangent_ratio / (1 - self.tangent_ratio)
            return [[self.yield_stress + h * e, e] for e in ep]
        return [
            [
                self.yield_stress
                * (1 + e * self.young / (self.alpha * self.yield_stress)) ** (1 / self.exponent),
                e,
            ]
            for e in ep
        ]


class ModelSpec(StrictModel):
    physics_version: str = "legacy-v1"
    impactor_shape: Literal["sphere", "blunt_cone"] = "sphere"
    nose_diameter_mm: float = Field(default=20, gt=0)
    shank_diameter_mm: float = Field(default=40, gt=0)
    cone_height_mm: float = Field(default=10, gt=0)
    shank_height_mm: float = Field(default=30, gt=0)
    adiabatic: bool = False
    initial_temperature_C: float = 20
    core_topology: Literal["hexagonal", "reentrant_0"] = parameter(
        "hexagonal", "Cấu trúc lõi", source="Hexagonal reference / re-entrant image 1, 0 degrees"
    )
    panel: float = parameter(100.0, "Cạnh tấm vuông", "mm", "Paper section 2", gt=0)
    core_height: float = parameter(20.0, "Chiều cao lõi", "mm", "Paper section 3", gt=0)
    skin: float = parameter(0.75, "Chiều dày mặt trên", "mm", "Paper section 3", gt=0)
    bottom_skin: float | None = parameter(None, "Chiều dày mặt dưới (null = bằng mặt trên)", "mm", gt=0)
    cell_size: float = parameter(
        6.35, "Kích thước ô / bề rộng ô lõm", "mm", "Hexagon across flats; re-entrant bounding width", gt=0
    )
    hex_geometry: Literal["regular", "parametric"] = parameter(
        "regular", "Cách nhập ô lục giác", source="Ô đều theo kích thước ô hoặc nhập b, l, θ theo hình 7"
    )
    hex_b: float = parameter(6.35 / math.sqrt(3), "b — chiều dài vách đứng", "mm", "Hình 7, công thức (8); vách đứng dày 2t", gt=0)
    hex_l: float = parameter(6.35 / math.sqrt(3), "l — chiều dài vách nghiêng", "mm", "Hình 7, công thức (8)", gt=0)
    hex_theta_deg: float = parameter(60.0, "θ — góc vách nghiêng với phương đứng", "deg", "Hình 7; ô đều θ=60°", gt=0, lt=90)
    reentrant_cell_height: float = parameter(5.0, "Chiều cao ô lõm", "mm", "Assumed image-1 geometry", gt=0)
    reentrant_indent: float = parameter(1.25, "Độ lõm mỗi bên ô", "mm", "Assumed image-1 geometry", gt=0)
    reentrant_geometry: Literal["indent", "angle"] = parameter("indent", "Cách nhập ô lõm", source="Nhập độ lõm hoặc góc δ với phương đứng")
    reentrant_delta_deg: float = parameter(26.56505117707799, "δ — góc vách nghiêng với phương đứng", "deg", "d = h/2 × tan(δ)", gt=0, lt=90)
    reentrant_depth_seed: float = parameter(1.0, "Seed lõi theo chiều sâu Y", "mm", "Image-1 reference mesh", gt=0)
    phase_z: float = parameter(0.0, "Dịch pha ô lõm Z", "mm")
    foil: float = parameter(0.0635, "t — chiều dày foil đơn", "mm", "Paper section 3; vách kép dày 2t", gt=0)
    core_angle: float = parameter(0.0, "Góc hướng ô", "deg")
    phase_x: float = parameter(0.0, "Dịch pha ô X", "mm")
    phase_y: float = parameter(0.0, "Dịch pha ô Y", "mm")
    clamp_mode: Literal["circular", "perimeter"] = parameter(
        "circular", "Vị trí ngàm", source="Ngàm hai tấm mặt: ngoài lỗ tròn hoặc chỉ bốn cạnh ngoài"
    )
    clamp_diameter: float = parameter(76.4, "Đường kính lỗ kẹp", "mm", "Paper section 3; chỉ dùng với ngàm ngoài lỗ tròn", gt=0)
    ball_diameter: float = parameter(13.1, "Đường kính đầu va đập", "mm", "Paper section 2", gt=0)
    ball_size_mode: Literal["diameter", "radius"] = parameter("diameter", "Cách nhập kích thước viên bi", source="D = 2R")
    ball_radius: float = parameter(6.55, "Bán kính viên bi R", "mm", "D = 2R; độc lập với khối lượng chuyển động", gt=0)
    impactor_young: Literal[200000] = parameter(
        200000.0,
        "E vật liệu đầu rigid (không chi phối biến dạng rigid)",
        "MPa",
        "Paper section 3; fixed metadata",
    )
    impactor_poisson: float = parameter(
        0.3, "Poisson đầu rigid", "", "Paper section 3; fixed metadata", ge=0.3, le=0.3
    )
    min_segment_length: float = parameter(
        0.05, "Ngưỡng bỏ đoạn vách cực ngắn ở biên", "mm", "Reconstruction geometry tolerance", gt=0, le=0.1
    )
    mass_kg: float = parameter(2.65, "Khối lượng chuyển động", "kg", "Paper section 2", gt=0)
    loading: Literal["energy", "velocity"] = parameter("energy", "Cách nhập va đập", source="Nhập năng lượng hoặc vận tốc; E = ½mv²")
    energy_J: float = parameter(7.0, "Năng lượng ban đầu", "J", "Paper Fig.6", gt=0)
    velocity_m_s: float = parameter(2.29848186156091, "Vận tốc ban đầu (độ lớn)", "m/s", gt=0)
    impact_x: float = parameter(0.0, "Vị trí va đập X", "mm")
    impact_y: float = parameter(0.0, "Vị trí va đập Y", "mm")
    gap: float = parameter(0.1, "Khe hở hình học", "mm", "Paper section 3", ge=0)
    gravity: float = parameter(9.81, "Gia tốc trọng trường", "m/s²", ge=0)
    face_material: Material = Field(default_factory=lambda: Material(name="1100-H14"))
    core_material: Material = Field(
        default_factory=lambda: Material(name="3003-H19", yield_stress=220, ultimate=250)
    )
    friction: float = parameter(0.0, "Hệ số ma sát", "", "Paper: frictionless", ge=0)
    tie_tolerance: float = parameter(0.05, "Dung sai Tie", "mm", gt=0)
    skin_self_contact: bool = parameter(False, "Tự tiếp xúc mặt", "", "Reconstruction at 7 J")
    core_self_contact: Literal[True] = True
    perfect_bond: Literal[True] = True
    mesh_preset: Literal["reference", "quick", "fine", "custom"] = "reference"
    core_centre_seed: float = parameter(0.7, "Seed lõi vùng tâm", "mm", "Reference model", gt=0)
    core_outer_seed: float = parameter(1.3, "Seed lõi phía ngoài", "mm", "Reference model", gt=0)
    fine_radius: float = parameter(22.0, "Bán kính tinh lưới lõi", "mm", "Reference model", gt=0)
    skin_centre_seed: float = parameter(0.75, "Seed mặt vùng tâm", "mm", "Reference model", gt=0)
    skin_outer_seed: float = parameter(1.25, "Seed mặt phía ngoài", "mm", "Reference model", gt=0)
    skin_patch_half: float = parameter(12.0, "Nửa cạnh vùng chia mặt", "mm", "Reference model", gt=0)
    core_z_divisions: int = parameter(20, "Số lớp lưới theo chiều cao", "", "Reference model", ge=2, le=200)
    ball_seed: float = parameter(1.0, "Seed đầu va đập", "mm", "Reference model", gt=0)
    shell_points: int = parameter(5, "Điểm tích phân shell Simpson", "", ge=3, le=15)
    shell_element: Literal["S4R/S3R"] = "S4R/S3R"
    duration: float = parameter(0.006, "Thời gian vật lý", "s", "Reference numerical choice", gt=0, le=1)
    cpus: int = parameter(8, "Số CPU", "", ge=1, le=128)
    precision: Literal["double"] = "double"
    mass_scaling: Literal[False] = False
    bulk_linear: float = parameter(0.06, "Bulk viscosity tuyến tính", "", "Abaqus default", ge=0)
    bulk_quadratic: float = parameter(1.2, "Bulk viscosity bậc hai", "", "Abaqus default", ge=0)
    field_intervals: int = parameter(120, "Số khoảng field", "", ge=2, le=10000)
    history_intervals: int = parameter(1200, "Số khoảng history", "", ge=10, le=1000000)
    field_variables: list[str] = Field(
        default_factory=lambda: ["U", "S", "PEEQ", "CFORCE"]
    )
    history_variables: list[str] = Field(
        default_factory=lambda: ["ALLAE", "ALLIE", "ALLKE", "ALLPD", "ALLSE", "ALLVD", "ALLWK", "ETOTAL"]
    )

    @model_validator(mode="after")
    def geometry(self):
        if self.impactor_shape == "blunt_cone" and self.shank_diameter_mm <= self.nose_diameter_mm:
            raise ValueError("Cone shank diameter must exceed nose diameter")
        cards = [m.johnson_cook for m in (self.core_material, self.face_material)]
        if self.adiabatic and not all(cards):
            raise ValueError("Adiabatic campaign requires complete thermal material cards")
        if any(cards) and self.physics_version == "legacy-v1":
            raise ValueError("Damage models require an explicit physics version")
        cell_width = self.cell_size
        if self.core_topology == "hexagonal" and self.hex_geometry == "parametric":
            cell_width = 2 * self.hex_l * math.sin(math.radians(self.hex_theta_deg))
            if self.foil * 2 >= min(self.hex_b, self.hex_l, cell_width) / 4:
                raise ValueError("Foil quá dày so với b, l hoặc bề rộng ô")
        if self.clamp_mode == "circular" and (self.clamp_diameter >= self.panel or cell_width >= self.clamp_diameter):
            raise ValueError("Lỗ kẹp phải nhỏ hơn tấm, ô phải nhỏ hơn lỗ kẹp")
        if cell_width >= self.panel:
            raise ValueError("Ô phải nhỏ hơn tấm")
        if self.foil * 2 >= cell_width / 4:
            raise ValueError("Foil quá dày so với ô")
        if self.core_topology == "reentrant_0":
            indent = self.effective_indent()
            if indent >= self.cell_size / 2:
                raise ValueError("Độ lõm phải nhỏ hơn nửa bề rộng ô để eo ô còn mở")
            if self.foil * 2 >= min(self.reentrant_cell_height, self.cell_size - 2 * indent) / 4:
                raise ValueError("Vách quá dày so với chiều cao hoặc eo ô lõm")
            if self.core_angle != 0 or self.phase_y != 0:
                raise ValueError("Lõi tổ ong lõm Re-entrant cố định hướng 0° trong XZ; dùng phase_x và phase_z để dịch pha")
            if abs(self.phase_z) > self.reentrant_cell_height:
                raise ValueError("Dịch pha Z giới hạn trong ±một chiều cao ô lõm")
        if abs(self.phase_x) > cell_width or abs(self.phase_y) > cell_width:
            raise ValueError("Dịch pha giới hạn trong ±một kích thước ô")
        if self.shell_points % 2 != 1:
            raise ValueError("Số điểm Simpson phải lẻ")
        free_half = self.clamp_diameter / 2 / math.sqrt(2) if self.clamp_mode == "circular" else self.panel / 2
        if abs(self.impact_x) + self.skin_patch_half >= free_half or abs(
            self.impact_y
        ) + self.skin_patch_half >= free_half:
            raise ValueError("Vùng tinh lưới mặt phải nằm trong vùng tự do bên trong ngàm")
        return self

    def effective_indent(self):
        return (self.reentrant_cell_height / 2 * math.tan(math.radians(self.reentrant_delta_deg))
                if self.reentrant_geometry == "angle" else self.reentrant_indent)

    def resolved(self) -> dict:
        d = self.model_dump()
        if self.mesh_preset != "custom":
            factor = {"reference": 1.0, "quick": 1.4, "fine": 0.8}[self.mesh_preset]
            for key, value in {
                "core_centre_seed": 0.7,
                "core_outer_seed": 1.3,
                "skin_centre_seed": 0.75,
                "skin_outer_seed": 1.25,
                "ball_seed": 1.0,
                "reentrant_depth_seed": 1.0,
            }.items():
                d[key] = value * factor
            d["core_z_divisions"] = round(20 / factor)
        d["bottom_skin"] = self.bottom_skin or self.skin
        if self.ball_size_mode == "radius":
            d["ball_diameter"] = 2 * self.ball_radius
        else:
            d["ball_radius"] = self.ball_diameter / 2
        if self.loading == "energy":
            d["velocity_m_s"] = math.sqrt(2 * self.energy_J / self.mass_kg)
        else:
            d["energy_J"] = 0.5 * self.mass_kg * self.velocity_m_s**2
        d["velocity"] = d["velocity_m_s"] * 1000
        d["impact_mass"] = self.mass_kg / 1000
        d["impactor_effective_density_tonne_mm3"] = (
            2.25e-6 * (d["impact_mass"] / 0.00265) * (13.1 / d["ball_diameter"]) ** 3
        )
        if self.friction and "ALLFD" not in d["history_variables"]:
            d["history_variables"].append("ALLFD")
        if self.core_topology == "reentrant_0":
            indent = d["reentrant_indent"] = self.effective_indent()
            length = math.hypot(indent, self.reentrant_cell_height / 2)
            d["side"] = None
            d["periodic_density_kg_m3"] = (
                (2 * self.cell_size + 2 * length) * self.foil * self.core_material.density
                / ((self.cell_size - indent) * self.reentrant_cell_height)
            )
            d["core_cell_plane"] = "XZ"
            d["core_extrusion_axis"] = "Y"
            d["reentrant_inclined_length_mm"] = length
            d["reentrant_angle_to_z_deg"] = math.degrees(math.atan2(indent, self.reentrant_cell_height / 2))
            d["reentrant_delta_deg"] = d["reentrant_angle_to_z_deg"]
        else:
            if self.hex_geometry == "regular":
                d["hex_b"] = d["hex_l"] = self.cell_size / math.sqrt(3)
                d["hex_theta_deg"] = 60.0
            b, length, theta = d["hex_b"], d["hex_l"], math.radians(d["hex_theta_deg"])
            d["side"] = length
            d["cell_size"] = 2 * length * math.sin(theta) if self.hex_geometry == "parametric" else self.cell_size
            d["hex_pitch_y_mm"] = b + length * math.cos(theta)
            d["hex_cell_height_mm"] = b + 2 * length * math.cos(theta)
            d["periodic_density_kg_m3"] = (
                2 * (b + length) * self.foil * self.core_material.density
                / ((b + length * math.cos(theta)) * (2 * length * math.sin(theta)))
            )
            d["density_formula"] = "HD = 2(b+l)tρ / [(b+l cosθ)(2l sinθ)]"
        d["face_plastic_table"] = self.face_material.table()
        d["core_plastic_table"] = self.core_material.table()
        d["units"] = {
            "length": "mm",
            "mass": "tonne",
            "time": "s",
            "force": "N",
            "stress": "MPa",
            "energy": "N.mm",
        }
        d["validation_status"] = "reentrant_geometry_unvalidated" if self.core_topology == "reentrant_0" else "reconstruction_unvalidated"
        return d


class Axis(StrictModel):
    parameter: str
    start: float | None = None
    stop: float | None = None
    step: float | None = None
    values: list[float | str | bool] | None = None
    include_stop: bool = False

    def points(self, limit: int = 10000) -> list[float | str | bool]:
        vals: list[float | str | bool]
        if self.values is not None:
            vals = list(dict.fromkeys(self.values))
        else:
            if self.start is None or self.stop is None or self.step is None:
                raise ValueError("Khoảng cần đủ đầu, cuối, bước")
            a, b, h = map(lambda x: Decimal(str(x)), (self.start, self.stop, self.step))
            if h <= 0 or b < a:
                raise ValueError("Bước phải > 0; cuối phải >= đầu")
            count = int((b - a) // h) + 1
            if count > limit:
                raise ValueError("Quá nhiều điểm; giảm khoảng hoặc tăng bước")
            vals = [float(a + i * h) for i in range(count)]
            if self.include_stop and Decimal(str(vals[-1])) != b:
                vals.append(float(b))
        if (
            not vals
            or len(vals) > limit
            or any(
                (isinstance(x, (float, int)) and not math.isfinite(x)) or isinstance(x, str) and not x
                for x in vals
            )
        ):
            raise ValueError("Danh sách điểm trống, quá dài hoặc không hữu hạn")
        return vals


class BatchSpec(StrictModel):
    schema_version: Literal["1"] = "1"
    name: Annotated[str, Field(min_length=1, max_length=200)] = "Khảo sát honeycomb"
    notes: str = ""
    project_id: str = "research"
    model: ModelSpec = Field(default_factory=ModelSpec)
    sampling: Literal["grid", "lhs", "table"] = "grid"
    axes: list[Axis] = Field(default_factory=list)
    designs: list[dict[str, Any]] = Field(default_factory=list)
    samples: int = Field(32, ge=1, le=10000)
    seed: int = 42
    max_runs: int = Field(1000, ge=1, le=10000)
    runtime_budget_minutes: float = Field(30, gt=0)
    min_free_gb: float = Field(20, ge=1)
    min_available_ram_gb: float = Field(
        2, ge=0.5, description="Available RAM reserve before solver admission"
    )
    render_images: bool = True
    export_all_fields: bool = Field(
        False,
        description="Advanced archive: duplicate every recorded ODB field to Parquet; research mode otherwise",
    )
    backup_after_run: bool = False
    data_profile: Literal["research", "smoke"] = "research"
    execution_mode: Literal["sequential", "parallel"] = "sequential"
    max_parallel_runs: int = Field(2, ge=1, le=20)
    ram_per_run_gb: float = Field(4, ge=0.5, le=512, description="Declared admission RAM budget per simultaneous run; not measured usage")


def digest(data: Any) -> str:
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode()
    ).hexdigest()


def set_parameter(data: dict, key: str, value: Any):
    if key.endswith((".ultimate", ".name")):
        raise ValueError(
            "Tên vật liệu và UTS chỉ là metadata; khảo sát E, yield_stress, hardening hoặc bảng dẻo thực tế"
        )
    parts = key.split(".")
    node = data
    for part in parts[:-1]:
        if part not in node or not isinstance(node[part], dict):
            raise ValueError("Tham số không tồn tại: " + key)
        node = node[part]
    if parts[-1] not in node:
        raise ValueError("Tham số không tồn tại: " + key)
    node[parts[-1]] = value


def validate_overrides(model: ModelSpec, keys: list[str]):
    """Reject inputs that the effective model's modes would silently discard."""
    if model.core_topology == "reentrant_0":
        inactive = "reentrant_indent" if model.reentrant_geometry == "angle" else "reentrant_delta_deg"
        if inactive in keys:
            raise ValueError("Chọn đúng cách nhập độ lõm/góc δ trước khi khảo sát " + inactive)
    if model.core_topology != "hexagonal" and any(k.startswith("hex_") for k in keys):
        raise ValueError("Tham số b, l, θ chỉ áp dụng cho lõi lục giác")
    if model.core_topology == "hexagonal":
        inactive = {"cell_size"} if model.hex_geometry == "parametric" else {"hex_b", "hex_l", "hex_theta_deg"}
        if inactive.intersection(keys):
            raise ValueError("Chọn đúng cách nhập ô lục giác trước khi khảo sát b, l, θ hoặc kích thước ô")
    if ("ball_radius" if model.ball_size_mode == "diameter" else "ball_diameter") in keys:
        raise ValueError("Chọn đúng cách nhập bán kính/đường kính trước khi khảo sát viên bi")
    if model.clamp_mode == "perimeter" and "clamp_diameter" in keys:
        raise ValueError("Ngàm bốn cạnh không dùng đường kính lỗ kẹp")
    if model.core_topology == "hexagonal" and any(k.startswith("reentrant_") or k == "phase_z" for k in keys):
        raise ValueError("Tham số ô lõm chỉ áp dụng khi chọn lõi reentrant_0")
    if model.core_topology == "reentrant_0" and any(k in ("core_angle", "phase_y", "core_z_divisions") for k in keys):
        raise ValueError("Lõi tổ ong lõm Re-entrant dùng hướng 0°, dịch pha X/Z và reentrant_depth_seed; trục khảo sát này không áp dụng")
    if "reentrant_depth_seed" in keys and model.mesh_preset != "custom":
        raise ValueError("Quét lưới cần chọn preset custom")
    if "energy_J" in keys and "velocity_m_s" in keys:
        raise ValueError("Không quét đồng thời năng lượng và vận tốc")
    for key in keys:
        if (
            key.startswith(("core_", "skin_", "ball_seed")) and "seed" in key or key == "core_z_divisions"
        ) and model.mesh_preset != "custom":
            raise ValueError("Quét lưới cần chọn preset custom")
    if (
        "energy_J" in keys
        and model.loading != "energy"
        or "velocity_m_s" in keys
        and model.loading != "velocity"
    ):
        raise ValueError("Chọn đúng chế độ energy/velocity trước khi quét")


def expand(spec: BatchSpec) -> list[dict]:
    keys = [a.parameter for a in spec.axes]
    if len(set(keys)) != len(keys):
        raise ValueError("Một tham số chỉ được khai báo một trục")
    if spec.sampling == "table":
        overrides = spec.designs
    elif spec.sampling == "lhs":
        from scipy.stats import qmc

        if not spec.axes or any(a.start is None or a.stop is None or a.stop <= a.start for a in spec.axes):
            raise ValueError("LHS cần các khoảng đầu < cuối")
        samples = qmc.LatinHypercube(len(keys), seed=spec.seed).random(spec.samples)
        overrides = [
            dict(
                zip(
                    keys,
                    [
                        cast(float, a.start) + float(x) * (cast(float, a.stop) - cast(float, a.start))
                        for a, x in zip(spec.axes, row, strict=False)
                    ],
                    strict=False,
                )
            )
            for row in samples
        ]
    else:
        points = [a.points() for a in spec.axes]
        if math.prod(map(len, points)) > spec.max_runs:
            raise ValueError("Số tổ hợp vượt max_runs; dùng LHS hoặc giảm trục")
        overrides = [dict(zip(keys, v, strict=False)) for v in itertools.product(*points)]
    if not overrides or len(overrides) > spec.max_runs:
        raise ValueError("Số lượt trống hoặc vượt giới hạn")
    result, seen = [], set()
    for index, changes in enumerate(overrides, 1):
        data = spec.model.model_dump()
        try:
            for key, value in changes.items():
                set_parameter(data, key, value)
            requested = ModelSpec.model_validate(data)
            validate_overrides(requested, list(changes))
        except ValueError as exc:
            if spec.sampling == "table":
                raise ValueError(f"Dòng bảng {index}: {exc}") from exc
            raise
        resolved = requested.resolved()
        h = digest(resolved)
        if h in seen:
            continue
        seen.add(h)
        design = {
            key: resolved[key]
            for key in (
                "panel",
                "core_height",
                "skin",
                "bottom_skin",
                "cell_size",
                "foil",
                "core_angle",
                "phase_x",
                "phase_y",
                "face_material",
                "core_material",
            )
        }
        for material in ("face_material", "core_material"):
            design[material] = {k: v for k, v in design[material].items() if k not in ("name", "ultimate")}
        if resolved["clamp_mode"] == "perimeter":
            design["clamp_mode"] = "perimeter"
        elif resolved["clamp_diameter"] != 76.4:
            design["clamp_diameter"] = resolved["clamp_diameter"]
        if resolved["core_topology"] == "reentrant_0":
            design.update({k: resolved[k] for k in ("core_topology", "reentrant_cell_height", "reentrant_indent", "phase_z")})
        elif resolved["hex_geometry"] == "parametric":
            design.update({k: resolved[k] for k in ("hex_b", "hex_l", "hex_theta_deg")})
        for key in (
            "energy_J",
            "velocity_m_s",
            "loading",
            "gap",
            "gravity",
            "mass_kg",
            "ball_diameter",
            "impact_x",
            "impact_y",
            "cpus",
            "duration",
            "field_intervals",
            "history_intervals",
            "mesh_preset",
            "core_centre_seed",
            "core_outer_seed",
            "skin_centre_seed",
            "skin_outer_seed",
            "core_z_divisions",
            "ball_seed",
            "fine_radius",
            "skin_patch_half",
        ):
            design.pop(key, None)
        result.append(
            {
                "requested": requested.model_dump(),
                "resolved": resolved,
                "input_hash": h,
                "design_id": digest(design)[:20],
                "changes": changes,
            }
        )
    return result


def catalogue() -> list[dict]:
    rows = []

    def walk(model, prefix=""):
        for name, f in model.model_fields.items():
            key = prefix + name
            default = getattr(model(), name)
            if isinstance(default, Material):
                walk(Material, key + ".")
                continue
            extra = f.json_schema_extra or {}
            rows.append(
                {
                    "key": key,
                    "title": f.title or name,
                    "unit": extra.get("unit", ""),
                    "source": extra.get("source", "Numerical choice"),
                    "description": f.description or "",
                    "default": default,
                    "type": str(f.annotation),
                    "sweep_allowed": not key.endswith((".ultimate", ".name")) and key != "impactor_poisson",
                }
            )

    walk(ModelSpec)
    return rows
