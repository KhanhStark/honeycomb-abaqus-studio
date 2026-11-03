import { useState } from "react";
import { Download } from "lucide-react";

type SolverFile = { path: string; name: string; type: string; bytes: number; sha256: string };
export type SolverRun = {
    id: string; index: number; source: string; attempt: number; model_name: string;
    parameters: { name: string; value: string | number }[]; files: SolverFile[];
};
const labels: Record<string, string> = {
    reentrant_delta_deg: "δ (°)", foil: "Lá lõi (mm)", core_height: "Cao lõi (mm)",
    cell_size: "Ô lõi (mm)", reentrant_cell_height: "Cao ô (mm)",
    "core_material.density": "Khối lượng riêng lõi (kg/m³)", velocity_m_s: "Vận tốc (m/s)",
    ball_diameter: "Đường kính bi (mm)", energy_J: "Năng lượng (J)",
};
function size(bytes: number) {
    return new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 2 }).format(bytes / 1024 ** (bytes >= 1024 ** 3 ? 3 : 2))
        + (bytes >= 1024 ** 3 ? " GiB" : " MiB");
}
function description(run: SolverRun) {
    return `Lượt ${run.index} · ` + (run.parameters.map(p => `${labels[p.name] ?? p.name}: ${typeof p.value === "number" ? new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 6 }).format(p.value) : p.value}`).join(" · ") || run.model_name)
        + ` · lần ${run.attempt} · ${run.source.slice(0, 8)}`;
}

export default function SolverDownload({ identity, runs }: { identity: string; runs: SolverRun[] }) {
    const [runId, setRunId] = useState(runs[0]?.id ?? "");
    const [types, setTypes] = useState(["cae", "odb", "inp"]);
    const [busy, setBusy] = useState(false), [error, setError] = useState(""), [saved, setSaved] = useState("");
    const run = runs.find(r => r.id === runId) ?? runs[0];
    const available = run?.files ?? [];
    const chosen = available.filter(f => types.includes(f.type));
    async function save(format: "script" | "manifest") {
        if (!run || !chosen.length) return;
        setBusy(true); setError(""); setSaved("");
        try {
            const query = new URLSearchParams({ selection: run.id, types: chosen.map(f => f.type).join(","), format });
            const response = await fetch(`/api/jobs/${identity}/data/solver-download?${query}`);
            if (!response.ok) {
                const data = await response.json();
                throw new Error(typeof data.detail === "string" ? data.detail : "Chưa tạo được công cụ tải. Thử lại.");
            }
            const name = `download_run_${String(run.index).padStart(4, "0")}.${format === "script" ? "py" : "json"}`;
            const url = URL.createObjectURL(await response.blob());
            const link = document.createElement("a");
            link.href = url; link.download = name; link.click();
            setTimeout(() => URL.revokeObjectURL(url), 1000);
            if (format === "script") setSaved(name);
        } catch (e) { setError(e instanceof Error ? e.message : "Chưa tải được. Kiểm tra kết nối rồi thử lại."); }
        finally { setBusy(false); }
    }
    return <section className="solver-download" aria-labelledby="solver-download-title">
        <h3 id="solver-download-title">Tải riêng một lượt mô phỏng</h3>
        <p>Chọn cấu hình và loại tệp cần lấy. Công cụ tải đúng các tệp đã chọn từ bản lưu gốc, tự ghép phần và kiểm tra SHA-256.</p>
        {!run ? <p>Chưa có CAE, ODB hoặc INP được lưu cho job này. Làm mới thư mục sau khi bản lưu hoàn tất.</p> : <>
            <label className="field"><span>Lượt chạy và tham số khảo sát</span>
                <select disabled={busy} value={run.id} onChange={e => { setRunId(e.target.value); setSaved(""); setError(""); }}>
                    {runs.map(r => <option key={r.id} value={r.id}>{description(r)}</option>)}
                </select>
            </label>
            <fieldset className="solver-file-types" disabled={busy}>
                <legend>Loại tệp cần tải</legend>
                {["cae", "odb", "inp"].map(type => <label key={type}>
                    <input type="checkbox" checked={types.includes(type) && available.some(f => f.type === type)}
                        disabled={!available.some(f => f.type === type)}
                        onChange={e => { setTypes(current => e.target.checked ? [...current, type] : current.filter(t => t !== type)); setSaved(""); setError(""); }} />
                    {type.toUpperCase()}{!available.some(f => f.type === type) && " (chưa lưu)"}
                </label>)}
            </fieldset>
            <div className="table-scroll"><table><caption>Tệp của lượt đã chọn</caption><thead><tr><th>Tên tệp</th><th>Dung lượng</th></tr></thead>
                <tbody>{chosen.map(f => <tr key={f.path}><td>{f.name}</td><td>{size(f.bytes)}</td></tr>)}</tbody>
            </table></div>
            <p className="measure" role="status">{chosen.length ? `Tổng tải: ${size(chosen.reduce((sum, f) => sum + f.bytes, 0))} · ${chosen.length} tệp` : "Chọn ít nhất một loại tệp để tải."}</p>
            <div className="actions">
                <button className="primary" disabled={busy || !chosen.length} onClick={() => void save("script")}><Download size={16} />{busy ? "Đang chuẩn bị tệp tải…" : "Tải công cụ cho lượt này"}</button>
                <button disabled={busy || !chosen.length} onClick={() => void save("manifest")}>Tải danh sách và checksum</button>
            </div>
            {error && <p role="alert">{error}</p>}
            {saved && <p role="status">Đã gửi <code>{saved}</code> tới trình duyệt. Chạy <code>py .\{saved}</code> trong thư mục muốn lưu dữ liệu.</p>}
            <p>Dùng Python 3.11 trở lên. Đặt công cụ trong thư mục muốn lưu, mở PowerShell tại đó và chạy <code>py .\download_run_{String(run.index).padStart(4, "0")}.py</code>. CAE/ODB/INP sẽ nằm trong thư mục con <code>solver-run-{String(run.index).padStart(4, "0")}--{run.id}</code>.</p>
            <p>Nếu tải bị ngắt, chạy lại cùng công cụ để tiếp tục các phần đã xác minh. Tệp CAE/ODB giữ nguyên phiên bản Abaqus gốc; tải về không chuyển chúng sang Abaqus 2017.</p>
        </>}
    </section>;
}
