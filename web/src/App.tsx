import { useEffect, useState, useRef, lazy, Suspense } from "react";
import { decodeHistory } from "./history-data";
import BatchSweep from "./BatchSweep";
import { updateAngleInput } from "./angle-input";
import { actionRunUrl } from "./action-links";
import ResultBoundary from "./ResultBoundary";
import JobDataFolder from "./JobDataFolder";
import JobExecution from "./JobExecution";
import CampaignStatus from "./CampaignStatus";
import { stateLabel } from "./job-state";
import {
    Box,
    SlidersHorizontal,
    ListChecks,
    Database,
    Link2,
    ArrowRight,
    Download,
    ExternalLink,
    LogIn,
    RefreshCw,
} from "lucide-react";
const HistoryChart = lazy(() => import("./HistoryChart"));
const FieldView = lazy(() => import("./FieldView"));

type Doc = Record<string, any>;
type Geometry = {
    plane: string;
    width: number;
    height: number;
    depth: number;
    walls: [number[], number[], boolean][];
    delta_deg?: number;
    reentrant_indent_mm?: number;
};
function number(value: unknown, digits = 3) {
    if (value === null || value === undefined || value === "") return "Chưa có";
    const n = Number(value);
    return Number.isFinite(n) ? n.toFixed(digits) : "Chưa có";
}
const repo = "https://github.com/xuankhanh24/honeycomb-abaqus-studio";
async function api(path: string, body?: unknown, csrf?: string): Promise<Doc> {
    const r = await fetch(path, {
        method: body === undefined ? "GET" : "POST",
        headers: {
            "Content-Type": "application/json",
            ...(csrf ? { "X-Honeycomb-CSRF": csrf } : {}),
        },
        ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    });
    const d = await r.json();
    if (!r.ok)
        throw new Error(
            typeof d.detail === "string"
                ? d.detail
                : JSON.stringify(d.detail ?? d),
        );
    return d;
}
function download(name: string, data: unknown) {
    const u = URL.createObjectURL(
        new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
    );
    const a = document.createElement("a");
    a.href = u;
    a.download = name;
    a.click();
    URL.revokeObjectURL(u);
}
const groups: [string, string[]][] = [
    ["Tấm sandwich", ["panel", "core_height", "skin", "bottom_skin", "foil"]],
    [
        "Ô lõi",
        [
            "core_topology",
            "cell_size",
            "reentrant_cell_height",
            "reentrant_geometry",
            "reentrant_indent",
            "reentrant_delta_deg",
            "hex_geometry",
            "hex_b",
            "hex_l",
            "hex_theta_deg",
            "core_angle",
        ],
    ],
    [
        "Viên bi và tải",
        [
            "ball_size_mode",
            "ball_radius",
            "ball_diameter",
            "mass_kg",
            "loading",
            "energy_J",
            "velocity_m_s",
            "impact_x",
            "impact_y",
        ],
    ],
    [
        "Ngàm và thời gian",
        [
            "clamp_mode",
            "clamp_diameter",
            "duration",
            "mesh_preset",
            "field_intervals",
            "history_intervals",
            "cpus",
        ],
    ],
];
const choices: Record<string, [string, string][]> = {
    reentrant_geometry: [["angle", "Nhập góc δ với phương đứng"], ["indent", "Nhập độ lõm d"]],
    core_topology: [
        ["reentrant_0", "Tổ ong lõm Re-entrant · 0°"],
        ["hexagonal", "Tổ ong lục giác"],
    ],
    hex_geometry: [
        ["regular", "Ô đều"],
        ["parametric", "Nhập b, l, θ"],
    ],
    ball_size_mode: [
        ["radius", "Bán kính R"],
        ["diameter", "Đường kính D"],
    ],
    loading: [
        ["energy", "Năng lượng"],
        ["velocity", "Vận tốc"],
    ],
    clamp_mode: [
        ["perimeter", "Chỉ bốn cạnh ngoài"],
        ["circular", "Ngoài lỗ tròn"],
    ],
    mesh_preset: [
        ["reference", "Tham chiếu"],
        ["quick", "Nhanh"],
        ["fine", "Mịn"],
        ["custom", "Tùy chỉnh"],
    ],
};
const tabs = [
    ["model", "Thiết lập", SlidersHorizontal],
    ["jobs", "Công việc", ListChecks],
    ["campaign", "Chiến dịch lõi", ListChecks],
    ["data", "Dữ liệu", Database],
    ["setup", "Kết nối", Link2],
] as const;

export default function App() {
    const [tab, setTab] = useState("model"),
        [spec, setSpec] = useState<Doc | null>(null),
        [params, setParams] = useState<Doc[]>([]),
        [status, setStatus] = useState<Doc>({ gates: [] }),
        [session, setSession] = useState<Doc>({}),
        [geometry, setGeometry] = useState<Geometry | null>(null),
        [geoError, setGeoError] = useState(""),
        [error, setError] = useState(""),
        [busy, setBusy] = useState(false),
        [preview, setPreview] = useState<Doc | null>(null),
        [jobs, setJobs] = useState<Doc[]>([]),
        [activity, setActivity] = useState<Doc>({ runs: [], available: null }),
        [selected, setSelected] = useState<Doc | null>(null),
        [profile, setProfile] = useState("research"),
        [json, setJson] = useState(""),
        [setup, setSetup] = useState<Doc | null>(null),
        [references, setReferences] = useState<Doc[]>([]),
        [training, setTraining] = useState<Doc | null>(null),
        [collecting, setCollecting] = useState(false),
        [dataJob, setDataJob] = useState<string | null>(new URLSearchParams(window.location.search).get("data_job")),
        [reference, setReference] = useState(0),
        [curve, setCurve] = useState<Doc[]>([]);
    const selectedId = useRef<string | null>(null);
    function openDataJob(identity: string) {
        setDataJob(identity); setTab("data");
        window.history.replaceState(null, "", "?data_job=" + encodeURIComponent(identity));
        window.scrollTo({ top: 0, behavior: "instant" });
    }
    useEffect(() => { if (dataJob) setTab("data"); }, []);
    useEffect(() => {
        selectedId.current = selected?.id ?? null;
    }, [selected]);
    async function refresh() {
        void api("/api/training").then(d => setTraining(d.collection)).catch(() => {});
        void api("/api/activity").then(setActivity).catch(() => setActivity({ runs: [], available: false }));
        try {
            const [s, u, j] = await Promise.all([
                api("/api/status"),
                api("/api/session"),
                api("/api/jobs"),
            ]);
            setStatus(s);
            setSession(u);
            setJobs(j.jobs);
            const id = selectedId.current;
            if (id) {
                const detail = await api("/api/jobs/" + id);
                if (selectedId.current === id) setSelected(detail);
            }
        } catch (e) {
            setError(String(e));
        }
    }
    useEffect(() => {
        api("/api/template")
            .then((t) => {
                setSpec(t.spec);
                setJson(JSON.stringify(t.spec, null, 2));
                setParams(t.parameters);
            })
            .catch((e) => setError(String(e)));
        void refresh();
        fetch("/reference/index.json")
            .then((r) => (r.ok ? r.json() : []))
            .then(setReferences)
            .catch(() => {});
    }, []);
    useEffect(() => {
        const active = activity.runs.length > 0 || jobs.some((j) =>
            ["running", "dispatching", "preflight"].includes(j.status),
        );
        const timer = setInterval(() => void refresh(), active ? 15000 : 60000);
        return () => clearInterval(timer);
    }, [jobs, activity.runs.length]);
    useEffect(() => {
        if (!spec) return;
        const abort = new AbortController();
        setGeometry(null);
        const timer = setTimeout(() => {
            fetch("/api/geometry", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(spec.model),
                signal: abort.signal,
            })
                .then(async (r) => {
                    const d = await r.json();
                    if (!r.ok) throw new Error(d.detail);
                    setGeometry(d);
                    setGeoError("");
                })
                .catch((e) => {
                    if (e.name !== "AbortError") setGeoError(String(e));
                });
        }, 350);
        return () => {
            clearTimeout(timer);
            abort.abort();
        };
    }, [spec]);
    useEffect(() => {
        setCurve([]);
        if (!references[reference]) return;
        const abort = new AbortController();
        fetch(references[reference].history, { signal: abort.signal })
            .then((r) => {
                if (!r.ok)
                    throw new Error(
                        "Không tải được history. Chọn lại bài để thử lại.",
                    );
                return r.arrayBuffer();
            })
            .then(async (bytes) => {
                const rows = await decodeHistory(bytes, references[reference].sha256);
                if (abort.signal.aborted) return;
                setCurve(rows);
            })
            .catch((e) => {
                if (e.name !== "AbortError") setError(String(e));
            });
        return () => abort.abort();
    }, [references, reference]);
    function update(key: string, value: unknown) {
        setSpec((s) => {
            const n = { ...s!, model: updateAngleInput(s!.model, key, value) };
            setJson(JSON.stringify(n, null, 2));
            return n;
        });
        setPreview(null);
    }
    function updateStudy(changes: Doc) {
        setSpec(s => {
            const next = {...s!, ...changes};
            setJson(JSON.stringify(next, null, 2));
            return next;
        });
        setPreview(null);
    }
    async function openJob(id: string) {
        selectedId.current = id;
        const d = await api("/api/jobs/" + id);
        if (selectedId.current === id) setSelected(d);
    }
    async function act(f: () => Promise<void>) {
        setError("");
        setBusy(true);
        try {
            await f();
        } catch (e) {
            setError(String(e));
        } finally {
            setBusy(false);
        }
    }
    const startDisabled = !session.owner || !!status.gates.length || !selected || selected.status !== "draft" || busy;
    const startReason = !session.owner
        ? "Bạn chưa đăng nhập quản trị. Đăng nhập tài khoản chủ dự án để lưu bài và yêu cầu chạy."
        : !selected
          ? "Chọn bài đã lưu trong ô phía trên để xem và chuẩn bị chạy."
          : status.gates.length
            ? "Luồng chạy từ web đang bị khóa bởi các điều kiện bên dưới."
            : selected.status !== "draft"
              ? "Bài đã được gửi. Xem từng lượt bên dưới; dùng Chạy bù lượt lỗi hoặc Đóng gói lại theo trạng thái."
              : busy ? "Đang xử lý thao tác trước…" : "Bài đã sẵn sàng để gửi sang GitHub Actions.";
    async function startSelectedJob() {
        if (startDisabled || !selected) return;
        await api(`/api/jobs/${selected.id}/dispatch`, {}, session.csrf);
        await refresh();
    }
    const model = spec?.model ?? {};
    const previewKeys = [...new Set([
        ...(spec?.axes ?? []).map((axis: Doc) => axis.parameter),
        ...(model.core_topology === "reentrant_0" ? ["reentrant_delta_deg", "reentrant_indent"] : []),
        "energy_J", "velocity_m_s", "cpus"
    ])] as string[];
    function previewValue(resolved: Doc, key: string) {
        const value = key.split(".").reduce((item: any, part) => item?.[part], resolved);
        return {raw: value == null ? "—" : String(value),
            text: value == null ? "—" : typeof value === "number" ? Number(value.toPrecision(10)).toString() : String(value)};
    }
    function visible(k: string) {
        if (k.startsWith("hex_"))
            return (
                model.core_topology === "hexagonal" &&
                (k === "hex_geometry" || model.hex_geometry === "parametric")
            );
        if (k.startsWith("reentrant_")) {
            if (model.core_topology !== "reentrant_0") return false;
            if (k === "reentrant_indent") return model.reentrant_geometry !== "angle";
            if (k === "reentrant_delta_deg") return model.reentrant_geometry === "angle";
            return true;
        }
        if (k === "core_angle") return model.core_topology === "hexagonal";
        if (k === "phase_y") return model.core_topology === "hexagonal";
        if (k === "cell_size")
            return (
                model.core_topology !== "hexagonal" ||
                model.hex_geometry === "regular"
            );
        if (k === "clamp_diameter") return model.clamp_mode === "circular";
        if (k === "ball_radius" || k === "ball_diameter")
            return (
                k ===
                (model.ball_size_mode === "radius"
                    ? "ball_radius"
                    : "ball_diameter")
            );
        if (k === "energy_J" || k === "velocity_m_s")
            return (
                k === (model.loading === "energy" ? "energy_J" : "velocity_m_s")
            );
        return true;
    }
    function field(k: string) {
        const p =
            k === "mesh_preset"
                ? { title: "Cấu hình lưới" }
                : (params.find((p) => p.key === k) ?? {
                      title:
                          (
                              { mesh_preset: "Cấu hình lưới" } as Record<
                                  string,
                                  string
                              >
                          )[k] ?? k,
                  });
        return (
            <label className="field" key={k}>
                <span>
                    {p.title}
                    {p.unit && <small>{p.unit}</small>}
                </span>
                {choices[k] ? (
                    <select
                        value={model[k]}
                        onChange={(e) => update(k, e.target.value)}
                    >
                        {choices[k].map(([v, l]) => (
                            <option key={v} value={v}>
                                {l}
                            </option>
                        ))}
                    </select>
                ) : (
                    <input
                        type="number"
                        step="any"
                        value={model[k] ?? ""}
                        placeholder={
                            k === "bottom_skin" ? "Bằng mặt trên" : undefined
                        }
                        onChange={(e) =>
                            update(
                                k,
                                e.target.value === ""
                                    ? null
                                    : Number(e.target.value),
                            )
                        }
                    />
                )}
            </label>
        );
    }
    return (
        <div className="shell">
            <a className="skip" href="#main">
                Đến nội dung chính
            </a>
            <aside className="sidebar">
                <a href="/" className="brand">
                    <Box size={28} />
                    <span>
                        Honeycomb<strong>Studio</strong>
                    </span>
                </a>
                <p className="workspace">Không gian nghiên cứu</p>
                <nav aria-label="Điều hướng">
                    {tabs.map(([id, label, Icon]) => (
                        <button
                            key={id}
                            aria-current={tab === id ? "page" : undefined}
                            onClick={() => {
                                setTab(id);
                                setError("");
                            }}
                        >
                            <Icon size={18} />
                            {label}
                        </button>
                    ))}
                </nav>
                <div className="sidebar-foot">
                    <a href={repo} target="_blank" rel="noreferrer">
                        Repo công khai <ExternalLink size={14} />
                    </a>
                    <span>Windows · Ubuntu cloud</span>
                </div>
            </aside>
            <div className="body">
                <header className="topbar">
                    <span>Sandwich / Va chạm viên bi</span>
                    <button
                        onClick={() =>
                            session.login_available
                                ? location.assign("/auth/login")
                                : setTab("setup")
                        }
                    >
                        <LogIn size={16} />
                        {session.owner ? "Chủ dự án" : "Đăng nhập quản trị"}
                    </button>
                </header>
                <main id="main">
                    <div className="page-heading">
                        <div>
                            <h1>{tabs.find((t) => t[0] === tab)?.[1]}</h1>
                            <p>
                                {tab === "model"
                                    ? "Dựng lõi, kiểm tra thông số và chuẩn bị bài va chạm."
                                    : tab === "jobs"
                                      ? "Theo dõi từng lần chạy và giữ lại nguồn gốc dữ liệu."
                                      : tab === "campaign"
                                        ? "Theo dõi pilot, kiểm tra số và bộ dữ liệu tối ưu lõi."
                                      : tab === "data"
                                        ? "Đọc kết quả thật, kiểm tra phạm vi và tải dữ liệu."
                                        : "Kết nối dịch vụ và kiểm tra điều kiện chạy Linux."}
                            </p>
                        </div>
                        <div className="heading-actions">
                            {tab === "model" && (
                                <button
                                    className="primary"
                                    disabled={busy || !spec}
                                    onClick={() =>
                                        void act(async () =>
                                            setPreview(
                                                await api("/api/preview", spec),
                                            ),
                                        )
                                    }
                                >
                                    Kiểm tra đầu vào
                                    <ArrowRight size={16} />
                                </button>
                            )}
                            <button
                                className="icon-button"
                                aria-label="Cập nhật trạng thái"
                                onClick={() => void refresh()}
                            >
                                <RefreshCw size={18} />
                            </button>
                        </div>
                    </div>
                    {error && (
                        <div role="alert" className="error">
                            {error}
                            <button onClick={() => setError("")}>Đóng</button>
                        </div>
                    )}
                    {tab === "campaign" && <CampaignStatus />}
                    {tab === "model" && (
                        <div className="workbench">
                            <section className="sheet">
                                <div className="sheet-title">
                                    <h2>Mô hình va chạm</h2>
                                    <span className="tag">
                                        Đơn vị mm · N · s
                                    </span>
                                </div>
                                {spec ? (
                                    <>
                                        <label className="name-field">
                                            Tên bài
                                            <input
                                                value={spec.name}
                                                onChange={(e) =>
                                                    setSpec({
                                                        ...spec,
                                                        name: e.target.value,
                                                    })
                                                }
                                            />
                                        </label>
                                        {groups.map(([title, keys]) => (
                                            <section
                                                className="parameter-group"
                                                key={title}
                                            >
                                                <h3>{title}</h3>
                                                <div className="fields">
                                                    {keys
                                                        .filter(visible)
                                                        .map(field)}
                                                </div>
                                            </section>
                                        ))}
                                        <section className="parameter-group">
                                            <h3>Dữ liệu đầu ra</h3>
                                            <label className="field">
                                                <span>
                                                    Profile xuất dữ liệu
                                                </span>
                                                <select
                                                    value={profile}
                                                    onChange={(e) =>
                                                        setProfile(
                                                            e.target.value,
                                                        )
                                                    }
                                                >
                                                    <option value="smoke">
                                                        Smoke · thử môi trường
                                                        ngắn
                                                    </option>
                                                    <option value="research">
                                                        Research · ODB, history,
                                                        thống kê, báo cáo
                                                    </option>
                                                    <option value="full">
                                                        Full · thêm toàn bộ
                                                        trường/frame sang
                                                        Parquet
                                                    </option>
                                                </select>
                                            </label>
                                            <p className="hint">
                                                Giữ double precision và không
                                                mass scaling. Full tạo thêm dữ
                                                liệu ngoài ODB; cần đo dung
                                                lượng trước khi chạy.
                                            </p>
                                        </section>
                                        <BatchSweep spec={spec} update={updateStudy} parameters={params.filter(p =>
                                            p.sweep_allowed && /float|int/.test(p.type) && !/list|tuple|dict|Literal/.test(p.type) && visible(p.key) &&
                                            (model.mesh_preset === "custom" || !["reentrant_depth_seed", "core_centre_seed", "core_outer_seed", "skin_centre_seed", "skin_outer_seed", "ball_seed", "core_z_divisions"].includes(p.key))
                                        ).map(p => ({...p,
                                            title: (p.key.startsWith("face_material.") ? "Mặt · " : p.key.startsWith("core_material.") ? "Lõi · " : "") + p.title,
                                            default: p.key.split(".").reduce((value: any, key: string) => value?.[key], model) ?? (p.key === "bottom_skin" ? model.skin : p.default)
                                        }))} />
                                        <details>
                                            <summary>
                                                Toàn bộ input, vật liệu và khảo
                                                sát nhiều lượt
                                            </summary>
                                            <p className="hint">
                                                Hợp đồng JSON dùng chung với
                                                worker; tối đa 100 lượt mỗi
                                                batch. Thay đổi nâng cao được áp
                                                dụng khi bạn bấm nút bên dưới.
                                            </p>
                                            <label className="json-label">
                                                Input JSON
                                                <textarea
                                                    spellCheck={false}
                                                    value={json}
                                                    onChange={(e) =>
                                                        setJson(e.target.value)
                                                    }
                                                    rows={14}
                                                />
                                            </label>
                                            <button
                                                onClick={() => {
                                                    try {
                                                        setSpec(
                                                            JSON.parse(json),
                                                        );
                                                        setPreview(null);
                                                        setError("");
                                                    } catch {
                                                        setError(
                                                            "JSON chưa hợp lệ. Kiểm tra dấu ngoặc và dấu phẩy.",
                                                        );
                                                    }
                                                }}
                                            >
                                                Áp dụng JSON
                                            </button>
                                        </details>
                                        <div className="actions">
                                            <button
                                                className="primary"
                                                disabled={busy}
                                                onClick={() =>
                                                    void act(async () =>
                                                        setPreview(
                                                            await api(
                                                                "/api/preview",
                                                                spec,
                                                            ),
                                                        ),
                                                    )
                                                }
                                            >
                                                {busy
                                                    ? "Đang kiểm tra…"
                                                    : "Kiểm tra đầu vào"}
                                                <ArrowRight size={16} />
                                            </button>
                                            <button
                                                onClick={() =>
                                                    download(
                                                        "requested-input.json",
                                                        spec,
                                                    )
                                                }
                                            >
                                                <Download size={16} />
                                                Tải input
                                            </button>
                                            <button
                                                disabled={
                                                    !session.owner ||
                                                    !preview ||
                                                    busy
                                                }
                                                title={
                                                    !session.owner
                                                        ? "Đăng nhập chủ dự án để lưu bài"
                                                        : "Kiểm tra đầu vào trước khi lưu"
                                                }
                                                onClick={() =>
                                                    void act(async () => {
                                                        const j = await api(
                                                            "/api/jobs",
                                                            {
                                                                request_id:
                                                                    crypto
                                                                        .randomUUID()
                                                                        .replaceAll(
                                                                            "-",
                                                                            "",
                                                                        ),
                                                                profile,
                                                                spec,
                                                            },
                                                            session.csrf,
                                                        );
                                                        setSelected(j);
                                                        setTab("jobs");
                                                        await refresh();
                                                    })
                                                }
                                            >
                                                Lưu bài
                                            </button>
                                            <button onClick={() => setTab("jobs")}>Đến bước chạy</button>
                                        </div>
                                        <p className="hint">Cách chạy: đăng nhập quản trị → kiểm tra đầu vào → Lưu bài → chọn Chạy mô phỏng trong Công việc.</p>
                                        {!session.owner && (
                                            <p className="hint">
                                                Mọi người có thể kiểm tra input.
                                                Chỉ chủ dự án được lưu và điều
                                                khiển job.
                                            </p>
                                        )}
                                        {preview && (
                                            <div
                                                role="status"
                                                className="preview-result"
                                            >
                                                <h3>
                                                    {preview.count} lượt hợp lệ
                                                </h3>
                                                <p className="hint">
                                                    Thông số đã được quy đổi
                                                    theo cùng quy tắc với
                                                    worker.
                                                </p>
                                                {preview.execution && <p className="measure">
                                                    Yêu cầu {preview.execution.requested_parallel_runs} lượt đồng thời ·
                                                    tối đa {preview.execution.effective_parallel_runs} runner riêng,
                                                    {preview.execution.cpu_per_run} CPU/lượt.
                                                    Worker kiểm tra lại tài nguyên trước mỗi nhóm lượt.
                                                </p>}
                                                <div className="table-scroll">
                                                    <table>
                                                        <thead>
                                                            <tr>
                                                                <th>Lượt</th>
                                                                {previewKeys.map(key => {
                                                                    const parameter = params.find(p => p.key === key);
                                                                    const prefix = key.startsWith("face_material.") ? "Mặt · " : key.startsWith("core_material.") ? "Lõi · " : "";
                                                                    return <th key={key}>{prefix}{parameter?.title ?? key}{parameter?.unit ? ` (${parameter.unit})` : ""}</th>;
                                                                })}
                                                                <th>
                                                                    Input hash
                                                                </th>
                                                            </tr>
                                                        </thead>
                                                        <tbody>
                                                            {preview.runs.map(
                                                                (r: Doc) => (
                                                                    <tr
                                                                        key={
                                                                                r.input_hash
                                                                        }
                                                                    >
                                                                        <td>
                                                                            {
                                                                                r.index
                                                                            }
                                                                        </td>
                                                                        {previewKeys.map(key => {
                                                                            const value = previewValue(r.resolved, key);
                                                                            return <td key={key} title={value.raw}>{value.text}</td>;
                                                                        })}
                                                                        <td>
                                                                            <code
                                                                                title={
                                                                                    r.input_hash
                                                                                }
                                                                            >
                                                                                {r.input_hash.slice(
                                                                                    0,
                                                                                    12,
                                                                                )}
                                                                            </code>
                                                                        </td>
                                                                    </tr>
                                                                ),
                                                            )}
                                                        </tbody>
                                                    </table>
                                                </div>
                                            </div>
                                        )}
                                    </>
                                ) : (
                                    <p role="status">
                                        Đang tải hợp đồng thông số…
                                    </p>
                                )}
                            </section>
                            <aside className="inspector">
                                <section className="geometry">
                                    <div className="sheet-title">
                                        <h2>Mặt cắt lõi</h2>
                                        <span>{geometry?.plane ?? "—"}</span>
                                    </div>
                                    {geometry ? (
                                        <>
                                            <svg
                                                role="img"
                                                aria-label={`Hình học lõi mặt ${geometry.plane}, ${geometry.walls.length} đoạn vách`}
                                                viewBox={`-5 -5 ${geometry.width + 10} ${geometry.height + 10}`}
                                            >
                                                <rect
                                                    width={geometry.width}
                                                    height={geometry.height}
                                                    fill="#f4f7fa"
                                                    stroke="#aeb9c7"
                                                    strokeWidth="0.15"
                                                />
                                                {geometry.walls.map(
                                                    ([u, v, d], i) => (
                                                        <line
                                                            key={i}
                                                            x1={
                                                                u[0] +
                                                                geometry.width /
                                                                    2
                                                            }
                                                            y1={
                                                                geometry.height /
                                                                    2 -
                                                                u[1]
                                                            }
                                                            x2={
                                                                v[0] +
                                                                geometry.width /
                                                                    2
                                                            }
                                                            y2={
                                                                geometry.height /
                                                                    2 -
                                                                v[1]
                                                            }
                                                            stroke={
                                                                d
                                                                    ? "#174e80"
                                                                    : "#527995"
                                                            }
                                                            strokeWidth={
                                                                d ? 0.38 : 0.22
                                                            }
                                                        />
                                                    ),
                                                )}
                                            </svg>
                                            <dl className="facts">
                                                <div>
                                                    <dt>Kích thước mặt cắt</dt>
                                                    <dd>
                                                        {geometry.width} ×{" "}
                                                        {geometry.height} mm
                                                    </dd>
                                                </div>
                                                <div>
                                                    <dt>Chiều sâu đùn</dt>
                                                    <dd>{geometry.depth} mm</dd>
                                                </div>
                                                <div>
                                                    <dt>Đoạn vách hình học</dt>
                                                    <dd>
                                                        {geometry.walls.length}
                                                    </dd>
                                                </div>
                                                {geometry.delta_deg !== undefined && <div>
                                                    <dt>Góc δ với phương đứng / độ lõm</dt>
                                                    <dd>{number(geometry.delta_deg)}° / {number(geometry.reentrant_indent_mm)} mm</dd>
                                                </div>}
                                            </dl>
                                        </>
                                    ) : (
                                        <p role="status">
                                            {geoError || "Đang dựng hình học…"}
                                        </p>
                                    )}
                                    <p className="hint">
                                        Preview hình học, chưa phải lưới hoặc
                                        kết quả solver. Vách đậm biểu diễn foil
                                        kép.
                                    </p>
                                </section>
                                <section className="readiness">
                                    <h2>Điều kiện chạy cloud</h2>
                                    {!status.gates.length && <p>Môi trường Linux thử nghiệm đã sẵn sàng nhận bài. Máy cấp license cần bật và kết nối Tailscale.</p>}
                                    {status.gates.map((g: Doc) => (
                                        <div className="gate" key={g.status}>
                                            <span className="status-dot" />
                                            <p>{g.message}</p>
                                        </div>
                                    ))}
                                    <button
                                        className="text-button"
                                        onClick={() => setTab("setup")}
                                    >
                                        Xem kết nối và bằng chứng{" "}
                                        <ArrowRight size={16} />
                                    </button>
                                </section>
                                <p className="inspector-note">
                                    Ngàm bốn cạnh chỉ khóa viền ngoài hai tấm
                                    mặt. Ngàm ngoài lỗ tròn là cấu hình tham
                                    chiếu cũ.
                                </p>
                            </aside>
                        </div>
                    )}
                    {tab === "jobs" && (
                        <section className="sheet">
                            <div className="sheet-title">
                                <h2>Danh sách bài</h2>
                                <span>{jobs.length} bài đã lưu</span>
                            </div>
                            <section className="run-start" aria-labelledby="run-start-title">
                                <h3 id="run-start-title">Bắt đầu mô phỏng từ web</h3>
                                {status.execution_runtime?.mode === "native_container" && <p className="hint">Dùng môi trường Linux đã chạy thử thành công, bộ cài trên Drive và license từ máy chủ dự án qua Tailscale. Actions kiểm tra kết nối trước khi chạy. Đây là môi trường thử nghiệm, chưa nghiệm thu chính thức.</p>}
                                <p>Chọn bài ngay tại đây. Nếu chưa có bài, vào Thiết lập để kiểm tra và lưu đầu vào.</p>
                                <label className="job-picker" htmlFor="run-job-select">
                                    <span>Chọn bài đã lưu</span>
                                    <select id="run-job-select" value={selected?.id ?? ""} disabled={busy || !jobs.length}
                                        aria-describedby="job-selection-help"
                                        onChange={event => {
                                            const identity = event.currentTarget.value;
                                            if (identity) void act(() => openJob(identity));
                                        }}>
                                        <option value="" disabled>{jobs.length ? "Chọn một bài để xem và chuẩn bị chạy…" : "Chưa có bài đã lưu"}</option>
                                        {jobs.map(job => <option key={job.id} value={job.id}>{job.parameter_title ?? job.name} · {stateLabel(job.status)}</option>)}
                                    </select>
                                </label>
                                <p id="job-selection-help" className="hint" aria-live="polite">
                                    {busy ? "Đang mở chi tiết bài…" : selected
                                        ? <>Bài đang chọn: <strong className="chosen-job-name">{selected.name}</strong>. {selected.status === "draft" ? "Bấm Chạy mô phỏng để gửi bài sang Actions." : "Bài đã được gửi; xem trạng thái và link Actions bên dưới."}</>
                                        : "Chọn bài trong ô trên; không cần cuộn xuống bảng để bấm Mở bài."}
                                </p>
                                <div className="actions">
                                    <button className="primary" disabled={startDisabled} aria-describedby="run-start-reason" title={startReason} onClick={() => void act(startSelectedJob)}>Chạy mô phỏng</button>
                                    {!session.owner && <button onClick={() => session.login_available ? location.assign("/auth/login") : setTab("setup")}>Đăng nhập để chạy</button>}
                                    <button onClick={() => setTab("model")}>Thiết lập và lưu bài</button>
                                    <button onClick={() => setTab("setup")}>Xem điều kiện chạy</button>
                                </div>
                                <p id="run-start-reason" className="hint">{startReason}</p>
                                {!!status.gates.length && <details className="run-blockers">
                                    <summary>Chạy từ web chưa sẵn sàng · {status.gates.length} điều kiện cần hoàn tất</summary>
                                    <ul>{status.gates.map((gate: Doc) => <li key={gate.status}>{gate.message}</li>)}</ul>
                                    <p>Đây là điều kiện của backend. Các workflow thử nghiệm được mở riêng trên GitHub; chúng không tự mở quyền chạy production từ web.</p>
                                </details>}
                            </section>
                            <section className="actions-activity" aria-label="Theo dõi GitHub Actions">
                                <h3>Actions đang chạy</h3>
                                {activity.runs.map((run: Doc) => (
                                    <div className="activity-run" key={run.id}>
                                        <div>
                                            <strong>{run.scope}</strong>
                                            <p>{run.name} · #{run.id} · {run.status === "queued" ? "Đang chờ runner" : "Đang chạy"}</p>
                                        </div>
                                        <a className="button" href={actionRunUrl(run.id) ?? undefined} target="_blank" rel="noopener noreferrer">
                                            Theo dõi trên GitHub Actions <ExternalLink size={14} />
                                        </a>
                                    </div>
                                ))}
                                {!activity.runs.length && <p>{activity.available === false
                                    ? "Chưa lấy được trạng thái Actions. Mở GitHub để kiểm tra lượt chạy mới nhất."
                                    : activity.available === null ? "Đang lấy trạng thái Actions…" : "Hiện không có lượt mô phỏng đang chạy."}</p>}
                                <p className="hint">Lượt thử nghiệm native được theo dõi riêng; trạng thái bài đã lưu vẫn giữ nguyên.</p>
                                <a href={`${repo}/actions`} target="_blank" rel="noopener noreferrer">Xem tất cả lượt chạy <ExternalLink size={14} /></a>
                            </section>
                            {jobs.length ? (
                                <div className="table-scroll">
                                    <table>
                                        <thead>
                                            <tr>
                                                <th>Tên bài</th>
                                                <th>Profile</th>
                                                <th>Trạng thái</th>
                                                <th>GitHub Actions</th>
                                                <th>Chi tiết</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {jobs.map((j) => (
                                                <tr key={j.id}>
                                                    <td><strong>{j.parameter_title ?? j.name}</strong>{j.parameter_title && <p className="hint">{j.name}</p>}</td>
                                                    <td>{j.profile}</td>
                                                    <td>{stateLabel(j.status)}</td>
                                                    <td>{actionRunUrl(j.workflow_run_id) ? <a href={actionRunUrl(j.workflow_run_id)!} target="_blank" rel="noopener noreferrer">Theo dõi #{j.workflow_run_id} <ExternalLink size={14} /></a> : "Chưa có lượt chạy"}</td>
                                                    <td>
                                                        <button
                                                            onClick={() =>
                                                                void act(
                                                                    async () =>
                                                                        openJob(
                                                                            j.id,
                                                                        ),
                                                                )
                                                            }
                                                        >
                                                            Mở bài
                                                        </button>
                                                        <button onClick={() => openDataJob(j.id)}>Mở thư mục dữ liệu</button>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            ) : (
                                <div className="empty">
                                    <ListChecks size={30} />
                                    <h3>Chưa có bài cloud được lưu</h3>
                                    <p>
                                        Kiểm tra đầu vào trong Thiết lập, sau đó
                                        đăng nhập chủ dự án để lưu bài. Chạy
                                        thật sẽ mở khi các bước nghiệm thu hoàn
                                        tất.
                                    </p>
                                    <button onClick={() => setTab("model")}>
                                        Về thiết lập
                                    </button>
                                </div>
                            )}
                            {selected && (
                                <section className="job-detail">
                                    <JobExecution key={selected.id} job={selected} parameters={params} owner={!!session.owner} busy={busy}
                                        openData={() => openDataJob(selected.id)} perform={async operation => {
                                            await api(`/api/jobs/${selected.id}/${operation === "recover" ? "recover" : "data/collect"}`, {}, session.csrf);
                                            await refresh();
                                        }}/>
                                    <div className="actions">
                                        {actionRunUrl(selected.workflow_run_id) && <a className="button" href={actionRunUrl(selected.workflow_run_id)!} target="_blank" rel="noopener noreferrer">Theo dõi trên GitHub Actions <ExternalLink size={14} /></a>}
                                        <button onClick={() => openDataJob(selected.id)}>Mở thư mục dữ liệu job</button>
                                        {selected.status === "review" && selected.profile !== "smoke" && selected.runs?.some((r: Doc) =>
                                            r.quality?.findings?.some((f: string) => f.startsWith("Cuối step còn tiếp xúc >10 N"))) &&
                                            <button disabled={!session.owner || busy} onClick={() => void act(async () => {
                                                const next = await api(`/api/jobs/${selected.id}/training-retry`, { request_id: crypto.randomUUID().replaceAll("-", "") }, session.csrf);
                                                selectedId.current = next.id; setSelected(next); await refresh();
                                            })}>Tạo job research với thời gian ×2</button>}
                                        {selected.quality_retry && <p>{selected.quality_retry} Bấm Bắt đầu chạy bài này để chạy job mới.</p>}
                                        {selected.status === "draft" && <button
                                            className="primary"
                                            disabled={startDisabled}
                                            aria-describedby="run-start-reason"
                                            title={startReason}
                                            onClick={() => void act(startSelectedJob)}
                                        >
                                            Bắt đầu chạy bài này
                                        </button>}
                                        {["running", "dispatching", "preflight"].includes(selected.status) && <button
                                            disabled={
                                                !session.owner ||
                                                ![
                                                    "running",
                                                    "dispatching",
                                                    "preflight",
                                                ].includes(selected.status) ||
                                                busy
                                            }
                                            onClick={() =>
                                                void act(async () => {
                                                    await api(
                                                        `/api/jobs/${selected.id}/cancel`,
                                                        {},
                                                        session.csrf,
                                                    );
                                                    await refresh();
                                                })
                                            }
                                        >
                                            Yêu cầu dừng
                                        </button>}
                                        <button
                                            onClick={() =>
                                                download(
                                                    `${selected.id}.json`,
                                                    selected,
                                                )
                                            }
                                        >
                                            Tải lịch sử và thiết đặt
                                        </button>
                                        {selected.release_url && !selected.releases?.length && (
                                            <a
                                                className="button"
                                                href={selected.release_url}
                                            >
                                                Kết quả trên GitHub{" "}
                                                <ExternalLink size={14} />
                                            </a>
                                        )}
                                    </div>
                                    {!!status.gates.length && (
                                        <p className="hint">
                                            Chưa đủ bằng chứng nghiệm thu
                                            Linux/license để chạy thật. Input đã
                                            lưu vẫn được giữ.
                                        </p>
                                    )}
                                    <ResultBoundary><Suspense
                                        fallback={<p>Đang mở bộ xem trường…</p>}
                                    >
                                        {selected.runs?.map(
                                            (run: Doc) =>
                                                run.field_view && (
                                                    <FieldView
                                                        key={run.id}
                                                        src={`/api/jobs/${selected.id}/field-view/${run.id}`}
                                                        sha256={
                                                            run.field_view
                                                                .sha256
                                                        }
                                                    />
                                                ),
                                        )}
                                    </Suspense></ResultBoundary>
                                    <details>
                                        <summary>
                                            Input, nguồn gốc và trạng thái đầy
                                            đủ
                                        </summary>
                                        <pre>
                                            {JSON.stringify(selected, null, 2)}
                                        </pre>
                                    </details>
                                </section>
                            )}
                        </section>
                    )}
                    {tab === "data" && (
                        <section className="sheet">
                            {dataJob && <JobDataFolder key={dataJob} identity={dataJob} session={session} close={() => { setDataJob(null); window.history.replaceState(null, "", window.location.pathname); }} />}
                            <section className="parameter-group" aria-labelledby="training-title">
                                <h2 id="training-title">Dữ liệu huấn luyện tổng hợp</h2>
                                <p>Tự động gom sau mỗi batch cloud. Mỗi dòng trong <code>samples.csv</code> hoặc <code>samples.parquet</code> là một lượt đạt chất lượng, đã khử trùng giữa các job.</p>
                                <dl className="training-contract">
                                    <dt>Đầu vào mô phỏng</dt><dd>Hình học (mm), vật liệu, ngàm, tải (J hoặc m/s), lưới và thời gian (s). Thư mục <code>03_simulations/.../input</code>.</dd>
                                    <dt>Đầu ra mô phỏng</dt><dd>Lực (N), chuyển vị (mm), năng lượng (J), ứng suất (MPa), đường cong và chất lượng. Thư mục <code>03_simulations/.../output</code>.</dd>
                                    <dt>Đầu vào huấn luyện X</dt><dd>Các cột <code>input.*</code> được liệt kê trong <code>dataset.json.features</code>. Cần mã hóa biến phân loại và xử lý giá trị thiếu.</dd>
                                    <dt>Mục tiêu dự đoán y</dt><dd>Chọn trong <code>dataset.json.targets</code>, ví dụ lực cực đại, chuyển vị cực đại, SEA. ID và split chỉ dùng truy vết/chia tập.</dd>
                                </dl>
                                <p><code>01_training</code>: bảng chung và từ điển cột · <code>02_audit</code>: nguồn, lý do loại · <code>03_simulations</code>: đầu vào/đầu ra từng lượt.</p>
                                {training ? <>
                                    <p className="measure">{training.samples} mẫu đạt · {training.runs} lượt lưu · {training.sources} nguồn · cập nhật {new Date(training.created_at).toLocaleString("vi-VN")}</p>
                                    {training.samples === 0 && <p>Chưa có mẫu đủ điều kiện huấn luyện. Bảng chỉ có tiêu đề; smoke/review vẫn có trong hồ sơ đối chiếu.</p>}
                                    {!!training.unavailable_sources && <p>{training.unavailable_sources} nguồn chưa có bản lưu hoàn tất; xem <code>02_audit/source-jobs.json</code>.</p>}
                                    <div className="actions">
                                        <a href={training.csv_url}>Tải bảng CSV</a>
                                        <a href={training.parquet_url}>Tải Parquet</a>
                                        <a href={training.zip_url}>Tải toàn bộ thư mục ZIP</a>
                                        <a href={training.release_url} target="_blank" rel="noreferrer">Xem bản phát hành</a>
                                        {training.all_results_csv_url && <a href={training.all_results_csv_url}>Tải mọi kết quả mô phỏng CSV</a>}
                                        {training.all_results_parquet_url && <a href={training.all_results_parquet_url}>Tải mọi kết quả Parquet</a>}
                                    </div>
                                    <p>Bảng mọi kết quả bao gồm cả review/smoke để kiểm tra. Bảng huấn luyện chỉ lấy các mẫu đã đạt chất lượng số.</p>
                                    {!!training.job_collections?.length && <div className="table-scroll"><table>
                                        <thead><tr><th>Job mô phỏng</th><th>Lượt / mẫu đạt</th><th>Dữ liệu</th><th>Actions</th></tr></thead>
                                        <tbody>{training.job_collections.map((job: Doc) => <tr key={job.id}>
                                            <td>{job.name}</td><td>{job.runs} / {job.samples}</td>
                                            <td><button onClick={() => openDataJob(job.id)}>Mở thư mục job</button></td>
                                            <td><a href={job.workflow_url} target="_blank" rel="noreferrer">Mở Actions mô phỏng</a></td>
                                        </tr>)}</tbody>
                                    </table></div>}
                                </> : <p>Chưa có bộ tổng hợp. Chạy tổng hợp để lấy các kết quả đã lưu trên GitHub.</p>}
                                <div className="actions">
                                    <button disabled={!session.owner || collecting} onClick={async () => {
                                        setCollecting(true);
                                        try {
                                            await api("/api/training/collect", {}, session.csrf);
                                            await refresh();
                                        } catch (e) { setError(String(e)); setCollecting(false); }
                                    }}>{collecting ? "Đã gửi yêu cầu · theo dõi Actions bên cạnh" : "Tổng hợp lại dữ liệu các job"}</button>
                                    <a href={`${repo}/actions/workflows/collect-training.yml`} target="_blank" rel="noreferrer">Theo dõi Actions tổng hợp</a>
                                    <button onClick={() => { setCollecting(false); void refresh(); }}>Làm mới</button>
                                </div>
                            </section>
                            <div className="sheet-title">
                                <h2>Kết quả mô phỏng</h2>
                                <span className="tag">
                                    Dữ liệu thật · Linux và Windows
                                </span>
                            </div>
                            <p className="measure">
                                Bài Linux dùng ngàm bốn cạnh. Các bài Windows cũ dùng
                                ngàm ngoài lỗ tròn; chưa thể dùng chúng để kết luận
                                ảnh hưởng riêng của hệ điều hành hay phiên bản solver.
                            </p>
                            {references.length ? (
                                <>
                                    <label className="field">
                                        <span>Bộ kết quả</span>
                                        <select
                                            value={reference}
                                            onChange={(e) => {
                                                setCurve([]);
                                                setReference(
                                                    Number(e.target.value),
                                                );
                                            }}
                                        >
                                            {references.map((r, i) => (
                                                <option value={i} key={r.id}>
                                                    {r.name}
                                                </option>
                                            ))}
                                        </select>
                                    </label>
                                    <p className="measure">
                                        {references[reference]?.platform} · Ngàm{" "}
                                        {references[reference]?.clamp_mode === "perimeter" ? "bốn cạnh" : "ngoài lỗ tròn"}
                                        {references[reference]?.status === "review" &&
                                            " · Cần xem xét: cuối 6 ms vẫn còn tiếp xúc 311 N; chưa đủ điều kiện huấn luyện."}
                                    </p>
                                    <div className="chart">
                                        {!curve.length && (
                                            <p role="status">
                                                Đang tải đường cong của bài đã
                                                chọn…
                                            </p>
                                        )}
                                        <ResultBoundary><Suspense
                                            fallback={
                                                <p role="status">
                                                    Đang nạp biểu đồ…
                                                </p>
                                            }
                                        >
                                            <HistoryChart curve={curve} />
                                        </Suspense></ResultBoundary>
                                    </div>
                                    <dl className="result-facts">
                                        <div>
                                            <dt>Lực đỉnh</dt>
                                            <dd>
                                                {Number(
                                                    references[reference]
                                                        ?.summary
                                                        ?.peak_raw_contact_force_N,
                                                ).toFixed(1)}{" "}
                                                N
                                            </dd>
                                        </div>
                                        <div>
                                            <dt>
                                                Tiêu tán dẻo cuối · toàn tấm
                                            </dt>
                                            <dd>
                                                {number(
                                                    references[reference]
                                                        ?.summary
                                                        ?.final_total_plastic_dissipation_J ??
                                                        curve.at(-1)?.ALLPD_J,
                                                )}{" "}
                                                J
                                            </dd>
                                        </div>
                                        <div>
                                            <dt>
                                                Dịch chuyển viên bi lớn nhất
                                            </dt>
                                            <dd>
                                                {Number(
                                                    references[reference]
                                                        ?.summary
                                                        ?.max_impactor_displacement_mm,
                                                ).toFixed(3)}{" "}
                                                mm
                                            </dd>
                                        </div>
                                    </dl>
                                    <p className="hint">
                                        ALLPD là tiêu tán dẻo toàn sandwich;
                                        không đồng nhất với năng lượng hấp thụ
                                        riêng của lõi. Dữ liệu so sánh chưa qua
                                        nghiệm thu tương đương thực nghiệm.
                                    </p>
                                    <div className="actions">
                                        {references[reference]?.report && (
                                            <a className="button" href={references[reference].report.url} target="_blank" rel="noreferrer">
                                                Báo cáo PDF
                                            </a>
                                        )}
                                        {references[reference]?.release_url && (
                                            <a className="button" href={references[reference].release_url} target="_blank" rel="noreferrer">
                                                CAE / INP / ODB và dữ liệu gốc
                                            </a>
                                        )}
                                        <a
                                            className="button"
                                            href={references[reference].history}
                                            download
                                        >
                                            <Download size={16} />
                                            History CSV đầy đủ
                                        </a>
                                        <button
                                            onClick={() =>
                                                download(
                                                    "reference-provenance.json",
                                                    references[reference],
                                                )
                                            }
                                        >
                                            Nguồn và checksum
                                        </button>
                                    </div>
                                    <details>
                                        <summary>
                                            Toàn bộ chỉ số và phạm vi kiểm chứng
                                        </summary>
                                        <pre>
                                            {JSON.stringify(
                                                references[reference].summary,
                                                null,
                                                2,
                                            )}
                                        </pre>
                                    </details>
                                    <ResultBoundary><Suspense
                                        fallback={<p>Đang mở bộ xem trường…</p>}
                                    >
                                        <FieldView
                                            key={references[reference].id}
                                            src={
                                                references[reference].field_view
                                                    ?.url
                                            }
                                            sha256={
                                                references[reference].field_view
                                                    ?.sha256
                                            }
                                        />
                                    </Suspense></ResultBoundary>
                                </>
                            ) : (
                                <p>
                                    Chưa nạp được bảng tham chiếu.{" "}
                                    <button onClick={() => location.reload()}>
                                        Tải lại
                                    </button>
                                </p>
                            )}
                            <section className="parameter-group">
                                <h3>So sánh chỉ số đã ghi</h3>
                                <p className="hint">Các hàng có điều kiện ngàm và phiên bản solver khác nhau.
                                    Bảng dùng để xem dữ liệu; chưa xác lập ảnh hưởng riêng của hướng lõi.</p>
                                <div style={{overflowX: "auto"}}>
                                    <table>
                                        <thead><tr><th>Bài</th><th>Ngàm</th><th>Lực đỉnh (N)</th>
                                            <th>ALLPD cuối (J)</th><th>Dịch chuyển bi lớn nhất (mm)</th></tr></thead>
                                        <tbody>{references.map(row => <tr key={row.id}>
                                            <td>{row.name}{row.status === "review" ? " · review" : ""}</td>
                                            <td>{row.clamp_mode === "perimeter" ? "Bốn cạnh" : "Ngoài lỗ tròn"}</td>
                                            <td>{number(row.summary?.peak_raw_contact_force_N, 1)}</td>
                                            <td>{number(row.summary?.plastic_dissipation_J ?? row.summary?.final_total_plastic_dissipation_J)}</td>
                                            <td>{number(row.summary?.max_impactor_displacement_mm)}</td>
                                        </tr>)}</tbody>
                                    </table>
                                </div>
                            </section>
                            <section className="parameter-group">
                                <h3>Dữ liệu cloud</h3>
                                <p>
                                    ODB, CAE, INP, bảng số và báo cáo của mỗi
                                    lượt nằm trong Releases. Manifest ghi
                                    SHA-256 từng phần; chỉ bộ đủ phần mới được
                                    công bố hoàn chỉnh.
                                </p>
                                <a href={repo + "/releases"}>
                                    Mở kho kết quả công khai{" "}
                                    <ExternalLink size={14} />
                                </a>
                            </section>
                        </section>
                    )}
                    {tab === "setup" && (
                        <section className="sheet">
                            <h2>Trạng thái nghiệm thu</h2>
                            {!status.gates.length && <p className="measure">Có thể gửi bài từ web sang GitHub Actions. Dùng chung môi trường với lượt thử Linux; các xác nhận nghiệm thu chính thức bên dưới vẫn đang chờ.</p>}
                            {status.technical_evidence?.solver_success && (
                                <p className="measure">
                                    Đã chạy smoke và bài va chạm 7 J / 6 ms trên Linux,
                                    checkout CAE/Explicit và mở ODB thành công. Bài va chạm
                                    cần xem xét do cuối step vẫn còn tiếp xúc.{" "}
                                    <a href={status.technical_evidence.impact_url}>Xem lượt chạy thật</a>
                                </p>
                            )}
                            {(status.qualification_gates ?? status.gates).map((g: Doc) => (
                                <div className="setup-row" key={g.status}>
                                    <code>{g.status}</code>
                                    <p>{g.message}</p>
                                </div>
                            ))}
                            <h3>Runner đã đo</h3>
                            <dl className="facts">
                                <div>
                                    <dt>Ubuntu public</dt>
                                    <dd>
                                        {status.runner?.cpu ?? "—"} CPU ·{" "}
                                        {status.runner?.ram_gib ?? "—"} GiB RAM
                                    </dd>
                                </div>
                                <div>
                                    <dt>Tổng đĩa / còn trống khi đo</dt>
                                    <dd>
                                        {status.runner?.disk_total_gib ?? "—"} /{" "}
                                        {status.runner?.disk_free_gib ?? "—"}{" "}
                                        GiB
                                    </dd>
                                </div>
                                <div>
                                    <dt>Thời điểm đo</dt>
                                    <dd>{status.runner?.measured_at ?? "—"}</dd>
                                </div>
                            </dl>
                            <a href={status.evidence_url}>
                                Xem workflow đo tài nguyên{" "}
                                <ExternalLink size={14} />
                            </a>
                            <h3>Quản trị và lưu trữ</h3>
                            <p className="measure">
                                Web chỉ chuẩn bị và điều phối bài. Worker chạy
                                tuần tự trên Actions; license server ở máy chủ
                                dự án cần bật và có mạng. Chỉ tài khoản chủ dự
                                án được điều khiển.
                            </p>
                            <dl className="facts">
                                <div>
                                    <dt>GitHub App</dt>
                                    <dd>
                                        {status.github_app_connected
                                            ? "Đã cấu hình"
                                            : "Chưa cấu hình"}
                                    </dd>
                                </div>
                                <div>
                                    <dt>Đăng nhập quản trị</dt>
                                    <dd>
                                        {session.login_available
                                            ? "Sẵn sàng"
                                            : "Chưa cấu hình OAuth"}
                                    </dd>
                                </div>
                                <div>
                                    <dt>Giới hạn</dt>
                                    <dd>
                                        100 lượt / batch · tối đa 20 runner đồng thời · 330 phút mỗi runner
                                    </dd>
                                </div>
                            </dl>
                            <div className="actions">
                                <a
                                    className="button"
                                    href={
                                        repo + "/blob/main/docs/CLOUD_STATUS.md"
                                    }
                                >
                                    Tài liệu triển khai{" "}
                                    <ExternalLink size={14} />
                                </a>
                                <button
                                    disabled={!session.owner}
                                    onClick={() =>
                                        void act(async () =>
                                            setSetup(await api("/api/setup")),
                                        )
                                    }
                                >
                                    Kiểm tra cấu hình quản trị
                                </button>
                            </div>
                            {setup && (
                                <pre>{JSON.stringify(setup, null, 2)}</pre>
                            )}
                        </section>
                    )}
                </main>
                <footer>
                    Honeycomb Studio{" "}
                    <span>
                        Dữ liệu công khai, quyền điều khiển theo tài khoản.
                    </span>
                    <a href={repo}>
                        Mã nguồn <ExternalLink size={12} />
                    </a>
                </footer>
            </div>
        </div>
    );
}
