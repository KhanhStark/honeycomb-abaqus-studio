"""SQLite is an index; portable manifests remain the source of provenance."""

from __future__ import annotations

import builtins
import csv
import json
import os
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .models import BatchSpec, catalogue, expand


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Each writer owns its temporary file. Windows readers/scanners can briefly
    # prevent replacement even after the write handle has been closed.
    tmp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        for attempt in range(10):
            try:
                os.replace(tmp, path)
                break
            except PermissionError as error:
                if getattr(error, "winerror", None) not in (5, 32, 33) or attempt == 9:
                    raise
                time.sleep(0.05 * (attempt + 1))
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


def write_input_csv(path: Path, data: dict):
    known = {p["key"]: p for p in catalogue()}
    derived = {
        "impact_mass": "tonne",
        "velocity": "mm/s",
        "periodic_density_kg_m3": "kg/m³",
        "panel_mass_kg": "kg",
        "actual_mesh_gap_mm": "mm",
        "impactor_effective_density_tonne_mm3": "tonne/mm³",
    }
    rows = []

    def flatten(values, prefix=""):
        for key, value in values.items():
            name = prefix + key
            if isinstance(value, dict):
                flatten(value, name + ".")
            else:
                info = known.get(name, {})
                rows.append(
                    {
                        "parameter": name,
                        "value": json.dumps(value, ensure_ascii=False),
                        "unit": info.get("unit", derived.get(name, "")),
                        "source": info.get("source", "derived / actual model"),
                        "title": info.get("title", name),
                    }
                )

    flatten(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["parameter", "title", "value", "unit", "source"])
        writer.writeheader()
        writer.writerows(rows)


class Store:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.root / "catalog.sqlite", check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
          PRAGMA journal_mode=WAL;
          CREATE TABLE IF NOT EXISTS batches(id TEXT PRIMARY KEY, document TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, batch_id TEXT NOT NULL, document TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT, batch_id TEXT, run_id TEXT, payload TEXT);
          CREATE INDEX IF NOT EXISTS run_batch ON runs(batch_id);
        """)
        guide = self.root / "README.md"
        if not guide.exists():
            guide.write_text(
                "# Thư viện Honeycomb Abaqus Studio\n\nMở LIBRARY.csv để tìm tên job, ID và thư mục tương ứng. catalog.sqlite là chỉ mục tìm kiếm; có thể xây lại từ manifest trong ứng dụng.\n\n- projects/<project>/batches/<batch>: batch.json, run-index.csv và reports/batch-report.pdf.\n- runs/<run>: requested-input và resolved-input (JSON/CSV có đơn vị và nguồn).\n- attempts/001, 002…: mỗi lần thực thi solver giữ raw (CAE/INP/ODB), extracted (history/field Parquet), figures, reports, logs và checksum manifest.\n- datasets: mẫu ML, từ điển cột, nhóm train/validation/test và đường cong gốc.\n- backup-manifests/backups/restores: upload có thể tiếp tục, ZIP và bản khôi phục.\n\nKhông đổi tên các thư mục ID bằng Explorer. Đặt tên hiển thị/ghi chú khi tạo job trong ứng dụng; không xóa file đang được solver dùng. Solver hoàn tất, chất lượng số và kiểm chứng vật lý là ba trạng thái riêng.\n",
                encoding="utf-8",
            )

    def save(self, table: str, doc: dict):
        if table not in ("batches", "runs"):
            raise ValueError(table)
        with self.lock:
            doc["updated_at"] = now()
            payload = json.dumps(doc, ensure_ascii=False)
            if table == "batches":
                self.db.execute("INSERT OR REPLACE INTO batches VALUES (?,?)", (doc["id"], payload))
            else:
                self.db.execute(
                    "INSERT OR REPLACE INTO runs VALUES (?,?,?)", (doc["id"], doc["batch_id"], payload)
                )
            self.db.commit()
            path = Path(doc["path"]) / ("batch.json" if table == "batches" else "run.json")
            write_json(path, doc)

    def get(self, table: str, identity: str) -> dict:
        if table not in ("batches", "runs"):
            raise ValueError(table)
        with self.lock:
            row = self.db.execute("SELECT document FROM " + table + " WHERE id=?", (identity,)).fetchone()
        if not row:
            raise KeyError(identity)
        return json.loads(row[0])

    def list(self, table: str, batch_id: str | None = None) -> builtins.list[dict]:
        if table not in ("batches", "runs"):
            raise ValueError(table)
        with self.lock:
            if batch_id:
                rows = self.db.execute(
                    "SELECT document FROM runs WHERE batch_id=? ORDER BY json_extract(document,'$.index')",
                    (batch_id,),
                ).fetchall()
            else:
                rows = self.db.execute(
                    "SELECT document FROM " + table + " ORDER BY json_extract(document,'$.created_at') DESC"
                ).fetchall()
        return [json.loads(r[0]) for r in rows]

    def create(self, spec: BatchSpec) -> dict:
        # Validate the complete expansion before creating anything on disk.
        entries = expand(spec)
        identity = "b" + uuid.uuid4().hex[:12]
        # project_id is a label, never an unchecked filesystem component.
        project = "p" + __import__("hashlib").sha256(spec.project_id.encode()).hexdigest()[:12]
        path = self.root / "projects" / project / "batches" / identity
        batch = {
            "id": identity,
            "name": spec.name,
            "path": str(path),
            "spec": spec.model_dump(),
            "created_at": now(),
            "status": "draft",
            "pause_requested": False,
            "runs_total": len(entries),
        }
        self.save("batches", batch)
        for i, entry in enumerate(entries):
            rid = "r%05d_%s" % (i + 1, entry["input_hash"][:8])
            # Globally unique run IDs avoid collisions between repeated studies.
            rid = identity + "_" + rid
            rp = path / "runs" / rid
            run = {
                "schema_version": "1",
                "id": rid,
                "batch_id": identity,
                "index": i + 1,
                "path": str(rp),
                "status": "queued",
                "phase": "queued",
                "attempts": [],
                "progress": {},
                "created_at": now(),
                **entry,
            }
            self.save("runs", run)
            write_json(rp / "requested-input.json", entry["requested"])
            write_json(rp / "resolved-input.json", entry["resolved"])
            write_input_csv(rp / "requested-input.csv", entry["requested"])
            write_input_csv(rp / "resolved-input.csv", entry["resolved"])
        self.event(identity, None, {"type": "batch_created", "runs": len(entries)})
        self.refresh_library_index()
        return batch

    def refresh_library_index(self):
        # This human-readable index is a cache, not a precondition for saving a job.
        with self.lock:
            try:
                self._write_library_index()
            except OSError as exc:
                self.event(None, None, {"type": "library_index_warning", "error": str(exc)})

    def _write_library_index(self):
        path = self.root / "LIBRARY.csv"
        temporary = path.with_suffix(".csv.tmp")
        with temporary.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=["name", "batch_id", "runs", "created_at", "folder"])
            writer.writeheader()
            for batch in self.list("batches"):
                writer.writerow(
                    {
                        "name": batch["name"],
                        "batch_id": batch["id"],
                        "runs": batch["runs_total"],
                        "created_at": batch["created_at"],
                        "folder": batch["path"],
                    }
                )
        temporary.replace(path)

    def event(self, batch_id: str | None, run_id: str | None, payload: dict):
        with self.lock:
            self.db.execute(
                "INSERT INTO events(time,batch_id,run_id,payload) VALUES (?,?,?,?)",
                (now(), batch_id, run_id, json.dumps(payload, ensure_ascii=False)),
            )
            self.db.commit()

    def events(self, after: int = 0, limit: int = 300):
        with self.lock:
            rows = self.db.execute(
                "SELECT * FROM events WHERE seq>? ORDER BY seq LIMIT ?", (after, limit)
            ).fetchall()
        return [{**dict(r), "payload": json.loads(r["payload"])} for r in rows]

    def snapshot(self, destination: Path):
        destination.parent.mkdir(parents=True, exist_ok=True)
        with self.lock, sqlite3.connect(destination) as target:
            self.db.backup(target)

    def reindex(self):
        count = 0
        for name, table in (("batch.json", "batches"), ("run.json", "runs")):
            for file in self.root.glob("projects/**/" + name):
                doc = json.loads(file.read_text(encoding="utf-8"))
                old_path = Path(doc["path"])
                doc["path"] = str(file.parent)
                for attempt in doc.get("attempts", []):
                    try:
                        attempt["path"] = str(file.parent / Path(attempt["path"]).relative_to(old_path))
                    except ValueError as exc:
                        raise ValueError("Attempt path lies outside run manifest: " + str(file)) from exc
                    attempt["process"] = None
                self.save(table, doc)
                count += 1
        self.refresh_library_index()
        return count
