import { useEffect, useState } from "react";
import { ExternalLink, FolderOpen, FileText, Download, RefreshCw } from "lucide-react";
import SolverDownload from "./SolverDownload";

type Doc = Record<string, any>;
type File = { path: string; bytes: number; sha256: string; kind: string };
type Tree = { folders: Record<string, Tree>; files: File[] };
function size(bytes: number) {
    return new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 1 }).format(bytes / 1024 ** (bytes >= 1024 ** 3 ? 3 : 2)) + (bytes >= 1024 ** 3 ? " GiB" : " MiB");
}
function tree(files: File[], prefix: string): Tree {
    const root: Tree = { folders: {}, files: [] };
    for (const file of files) {
        const parts = file.path.startsWith(prefix + "/") ? file.path.slice(prefix.length + 1).split("/") : file.path.split("/");
        let folder = root;
        for (const part of parts.slice(0, -1)) folder = folder.folders[part] ??= { folders: {}, files: [] };
        folder.files.push(file);
    }
    return root;
}
function FileTree({ value, select }: { value: Tree; select: (f: File) => void }) {
    return <ul className="data-tree">
        {Object.entries(value.folders).sort(([a], [b]) => a.localeCompare(b)).map(([name, child]) =>
            <li key={name}><details><summary><FolderOpen size={16} aria-hidden="true" />{name}</summary><FileTree value={child} select={select} /></details></li>)}
        {value.files.map(file => <li key={file.path} className="data-file"><button onClick={() => select(file)}><FileText size={14} aria-hidden="true" />{file.path.split("/").at(-1)}</button><span>{size(file.bytes)}</span></li>)}
    </ul>;
}

export default function JobDataFolder({ identity, session, close }: { identity: string; session: Doc; close: () => void }) {
    const [data, setData] = useState<Doc | null>(null), [error, setError] = useState(""),
        [building, setBuilding] = useState(false), [selected, setSelected] = useState<File | null>(null),
        [filter, setFilter] = useState("");
    async function load() {
        const r = await fetch(`/api/jobs/${identity}/data`);
        const result = await r.json();
        if (!r.ok) throw new Error(result.detail ?? "Chưa tải được thư mục dữ liệu.");
        return result;
    }
    useEffect(() => {
        let active = true;
        setData(null); setError(""); setSelected(null); setFilter(""); setBuilding(false);
        void load().then(d => { if (active) setData(d); }).catch(e => { if (active) setError(String(e)); });
        return () => { active = false; };
    }, [identity]);
    const collection = data?.collection;
    const running = ["running", "preflight", "dispatching"].includes(data?.status);
    const files: File[] = collection?.files ?? [];
    const shown = files.filter(f => f.path.toLocaleLowerCase().includes(filter.toLocaleLowerCase()));
    return <section className="parameter-group job-data-folder" aria-labelledby="job-data-title">
        <div className="sheet-title"><h2 id="job-data-title">Thư mục dữ liệu job</h2><button onClick={close}>Đóng thư mục</button></div>
        {error && <p role="alert">{error}</p>}
        {!data && !error && <p role="status">Đang đọc danh sách tệp của job…</p>}
        {data && <>
            <h3>{data.name}</h3>
            <p>Một lần bấm chạy tạo một job. Mỗi lượt đồng thời là một thư mục con có input, output và dữ liệu solver riêng.</p>
            <div className="actions">
                {data.workflow_url && <a className="button" href={data.workflow_url} target="_blank" rel="noreferrer">Mở Actions của job <ExternalLink size={14} /></a>}
                <button onClick={() => void load().then(setData).catch(e => setError(String(e)))}><RefreshCw size={14} />Làm mới thư mục</button>
            </div>
            {collection ? <>
                <p className="measure">{collection.runs} lượt có hồ sơ · {collection.samples} mẫu đạt chất lượng số · {collection.file_count} tệp · {size(collection.solver_bytes)} dữ liệu solver gốc</p>
                {!collection.source_complete && <p className="gate">Job còn nguồn thiếu hoặc chưa hoàn tất. Thư mục chứa các tệp đã lưu; xem bảng kiểm tra trước khi sử dụng.</p>}
                {collection.samples === 0 && <p>Chưa có mẫu đủ điều kiện huấn luyện. Mở <code>02_audit/run-selection.csv</code> để xem lý do và <code>05_all_results</code> để xem mọi kết quả đã mô phỏng.</p>}
                <div className="actions">
                    <a className="button" href={collection.zip_url}><Download size={14} />Tải đầu vào/đầu ra, đường cong và X/y</a>
                    <a href={collection.csv_url}>Bảng huấn luyện CSV</a>
                    <a href={collection.parquet_url}>Bảng huấn luyện Parquet</a>
                    <a href={collection.release_url} target="_blank" rel="noreferrer">Mở kho dữ liệu job <ExternalLink size={14} /></a>
                </div>
                <SolverDownload key={identity + (collection.source_fingerprint ?? "")} identity={identity} runs={data.solver_runs ?? []} />
                {collection.full_bundle ? <div className="full-download">
                    <h3>Tải toàn bộ thư mục, gồm ODB / CAE / INP</h3>
                    <p>{collection.full_bundle.storage_mode === "direct-source-parts"
                        ? `Tải trực tiếp ${size(collection.full_bundle.bytes)} từ ${collection.full_bundle.parts} phần nguồn đã lưu. Không cần chờ nén và upload lại toàn bộ ODB.`
                        : `Gói đầy đủ ${size(collection.full_bundle.bytes)} gồm ${collection.full_bundle.parts} phần, kèm log, báo cáo và dữ liệu trường đã lưu.`}</p>
                    <div className="actions">
                        {collection.full_bundle.zip_url && <a className="button" href={collection.full_bundle.zip_url}>Tải ZIP đầy đủ <Download size={14} /></a>}
                        <a className="button" href={collection.full_bundle.helper_url}>Tải công cụ lấy toàn bộ thư mục</a>
                        <a href={collection.full_bundle.manifest_url}>Danh sách phần tải và checksum</a>
                    </div>
                    <p>Tải <code>download_full.py</code>, mở CMD tại thư mục chứa tệp rồi chạy <code>py download_full.py</code>. Công cụ gom dữ liệu vào một thư mục, kiểm tra SHA-256; không cần Abaqus hoặc license.
                        {collection.full_bundle.storage_mode === "direct-source-parts" && " Nếu bị ngắt, chạy lại để dùng tiếp các tệp và phần đã xác minh. Khi job có lượt chạy bù, tải công cụ mới vào cùng thư mục để bổ sung dữ liệu. Bảng X/y và báo cáo theo phiên bản nằm trong 00_dataset_versions; solver trong 04_solver_archive. Tệp đã có khác checksum sẽ được báo lỗi, không ghi đè."}</p>
                </div> : <p>Danh sách dưới đây đã tham chiếu toàn bộ tệp gốc. Dùng nút đóng gói để tạo thêm ZIP đầy đủ; <a href={collection.full_manifest_url}>manifest nguồn đầy đủ</a> luôn được giữ.</p>}
                <label className="field"><span>Tìm tệp hoặc thư mục</span><input value={filter} onChange={e => setFilter(e.target.value)} placeholder="Ví dụ: input, output, .odb, quality, samples.csv" /></label>
                <p className="folder-path"><FolderOpen size={16} aria-hidden="true" />{collection.folder}</p>
                {shown.length ? <FileTree value={tree(shown, collection.folder)} select={setSelected} /> : <p>Không có tệp khớp bộ lọc.</p>}
                {selected && <div className="data-file-info" role="status"><h3>Thông tin tệp</h3><p>{selected.path}</p><p>{size(selected.bytes)} · {selected.kind === "solver" ? "Tệp solver gốc" : "Tệp đọc trực tiếp"}</p><p>SHA-256: <code>{selected.sha256}</code></p><p>Tệp nằm trong gói ZIP tương ứng ở phía trên; giữ nguyên checksum khi sử dụng.</p></div>}
            </> : <p>{running ? "Job đang chạy. Các lượt sẽ được gom vào thư mục chung sau khi đóng tệp và xác minh bản lưu." : "Job chưa có thư mục tổng hợp. Nếu đã chạy mô phỏng, dùng nút đóng gói bên dưới để gom dữ liệu đã lưu."}</p>}
            <div className="actions">
                <button disabled={!session.owner || building || running} onClick={async () => {
                    setError(""); setBuilding(true);
                    try {
                        const r = await fetch(`/api/jobs/${identity}/data/collect`, { method: "POST", headers: { "X-Honeycomb-CSRF": session.csrf } });
                        const result = await r.json();
                        if (!r.ok) throw new Error(result.detail ?? "Không gửi được yêu cầu đóng gói.");
                    } catch (e) { setError(String(e)); setBuilding(false); }
                }}>{building ? "Đã gửi yêu cầu đóng gói · xem Actions" : "Đóng gói lại toàn bộ dữ liệu job"}</button>
                <a href={collection?.collection_workflow_url ?? "https://github.com/xuankhanh24/honeycomb-abaqus-studio/actions/workflows/collect-training.yml"} target="_blank" rel="noreferrer">Theo dõi Actions đóng gói</a>
            </div>
        </>}
    </section>;
}
