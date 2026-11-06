import { useEffect, useState } from 'react';

type Report = {
    phase: string; enabled: boolean; percent: number; audited_configurations: number;
    training_configurations: number; archived_configurations: number;
    capacity_stage: number; license_capacity: number; eta_seconds: number | null;
    counts: Record<string, number>; owners: Record<string, Record<string, number>>;
    gates: Record<string, { passed?: boolean }>;
    errors: { id: string; owner: string; error?: string; status: string }[];
    updated_epoch: number;
    final_report_url?: string;
};

const phases: Record<string, string> = {
    material: 'Kiểm tra vật liệu và chạy nối', pilot: 'Pilot chọn vận tốc',
    pilot_completed: 'Pilot hoàn tất · chờ duyệt trước khi chạy dữ liệu chính', time: 'Kiểm tra thời gian',
    mesh: 'Kiểm tra hội tụ lưới', sensitivity: 'Độ nhạy hư hỏng',
    development_time_audit: 'Kiểm tra thời gian trên 40 cấu hình', production: '400 cấu hình ban đầu',
    adaptive: 'Bổ sung theo mô hình', analysis_pending: 'Phân tích dự đoán',
    confirmation: 'Xác nhận tối ưu bằng FE', completed: 'Hoàn tất và đã xác minh dữ liệu',
    verification_failed: 'Chưa đạt yêu cầu dự đoán hoặc xác nhận FE',
    insufficient_data: 'Chưa đủ dữ liệu đạt yêu cầu', needs_investigation: 'Cần kiểm tra lỗi',
};

export default function CampaignStatus() {
    const [report, setReport] = useState<Report | null>(null);
    const [error, setError] = useState('');
    useEffect(() => {
        const controller = new AbortController();
        const refresh = async () => {
            try {
                const response = await fetch('/api/campaigns/core-damage-v2-20261106', { signal: controller.signal });
                const data = await response.json();
                if (!response.ok) throw new Error(data.detail ?? 'Không tải được tiến độ.');
                setReport(data); setError('');
            } catch (failure) {
                if (!controller.signal.aborted) setError(failure instanceof Error ? failure.message : String(failure));
            }
        };
        void refresh();
        const timer = setInterval(() => void refresh(), 60000);
        return () => { clearInterval(timer); controller.abort(); };
    }, []);
    return <section className="sheet" aria-label="Tiến độ chiến dịch lõi có hư hỏng">
        <h2>Lõi có hư hỏng · 400 cấu hình ban đầu</h2>
        <p>AA6061-T6 tham khảo · H = 20 mm · viên bi cứng D = 13,1 mm, khối lượng 2,65 kg, vận tốc 8 m/s · thời gian 8 ms. Chỉ chạy pilot; dữ liệu chính đang chờ.</p>
        {error && <p role="alert">{error}</p>}
        {!report && !error && <p role="status">Đang tải tiến độ…</p>}
        {report && <>
            <h3>{phases[report.phase] ?? report.phase}</h3>
            <p>{report.enabled ? 'Điều phối đang bật' : 'Điều phối chưa bật'} · cập nhật {new Date(report.updated_epoch * 1000).toLocaleString('vi-VN')}</p>
            <progress max={100} value={report.percent} aria-label="Cấu hình đã lưu trữ" />
            <p><strong>{report.percent.toFixed(1)}%</strong> · đã lưu trữ và kiểm tra checksum {report.archived_configurations}/{report.training_configurations} cấu hình; {report.audited_configurations} qua kiểm tra số.</p>
            <p>Mức song song: {report.capacity_stage}; trần giấy phép được cấu hình: {report.license_capacity}.
                {' '}Thời gian còn lại: {report.eta_seconds == null ? 'chưa đủ số liệu để ước tính' : `khoảng ${(report.eta_seconds / 3600).toFixed(1)} giờ`}.</p>
            <h3>Cổng kiểm tra</h3>
            <ul>{Object.entries(report.gates).map(([name, gate]) => <li key={name}>{name}: {gate.passed === true ? 'Đạt' : 'Chưa đạt'}</li>)}</ul>
            <h3>Phân phối theo chủ sở hữu</h3>
            <div style={{ overflowX: 'auto' }}><table><thead><tr><th>Chủ sở hữu</th><th>Trạng thái cấu hình</th></tr></thead>
                <tbody>{Object.entries(report.owners).map(([owner, counts]) => <tr key={owner}><td>{owner}</td><td>{Object.entries(counts).map(([state, count]) => `${state}: ${count}`).join(' · ')}</td></tr>)}</tbody></table></div>
            {report.errors.length > 0 && <><h3>Các lượt cần kiểm tra</h3><ul>{report.errors.map(row => <li key={row.id}>{row.id} · {row.owner} · {row.status}: {row.error ?? 'Xem log của lượt chạy.'}</li>)}</ul></>}
            {report.final_report_url && <p><a href={report.final_report_url} target="_blank" rel="noreferrer">Tải dữ liệu tập trung và báo cáo xác nhận FE</a></p>}
            <p>Thông số phát triển hư hỏng chưa được hiệu chuẩn bằng thí nghiệm; kết quả không xác lập tiêu chuẩn an toàn.</p>
        </>}
    </section>;
}
