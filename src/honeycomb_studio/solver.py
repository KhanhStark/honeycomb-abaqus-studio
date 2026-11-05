"""Process ownership, Windows Abaqus launch and incremental .sta progress."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import psutil


def command(abaqus: str, *args: str) -> str | list[str]:
    if os.name == "nt" and abaqus.lower().endswith((".bat", ".cmd")):
        values = [abaqus, *args]
        if any(any(c in value for c in '"%!?^&|<>\r\n') for value in values):
            raise ValueError("Đường dẫn/lệnh Abaqus không được chứa ký tự điều khiển cmd")
        # cmd /s strips its outer quote pair. Pass a raw command line so Python's
        # list2cmdline does not backslash-escape cmd's own nested quote syntax.
        return (
            '"'
            + os.environ.get("COMSPEC", "cmd.exe")
            + '" /d /s /c "'
            + " ".join('"' + v + '"' for v in values)
            + '"'
        )
    return [abaqus, *args]


def launch(abaqus: str, args: list[str], cwd: Path, log: Path):
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("ab", buffering=0) as output:
        return subprocess.Popen(
            command(abaqus, *args),
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=output,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )


def owner(process) -> dict:
    p = psutil.Process(process.pid)
    return {"pid": p.pid, "created": p.create_time(), "command": p.cmdline(), "descendants": []}


def refresh_owned_tree(record: dict | None):
    if not record or not owned_alive(record):
        return
    known = {(r["pid"], r["created"]): r for r in record.setdefault("descendants", [])}
    try:
        for process in psutil.Process(record["pid"]).children(recursive=True):
            try:
                identity = {
                    "pid": process.pid,
                    "created": process.create_time(),
                    "command": process.cmdline(),
                }
                known[(identity["pid"], identity["created"])] = identity
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    record["descendants"] = list(known.values())


def owned_tree_alive(record: dict | None) -> bool:
    return bool(record) and (
        owned_alive(record) or any(owned_alive(child) for child in record.get("descendants", []))
    )


def owned_alive(record: dict | None) -> bool:
    if not record:
        return False
    try:
        p = psutil.Process(record["pid"])
        return (
            abs(p.create_time() - record["created"]) < 0.05
            and p.is_running()
            and p.status() != psutil.STATUS_ZOMBIE
        )
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False


def terminate_owned(record: dict | None):
    if record is None:
        return
    if record:
        for child in reversed(record.get("descendants", [])):
            terminate_owned(child)
    if not owned_alive(record):
        return
    p = psutil.Process(record["pid"])
    children = p.children(recursive=True)
    for child in reversed(children):
        try:
            child.terminate()
        except psutil.NoSuchProcess:
            pass
    try:
        p.terminate()
    except psutil.NoSuchProcess:
        pass
    _, alive = psutil.wait_procs(children + [p], timeout=5)
    for child in alive:
        try:
            child.kill()
        except psutil.NoSuchProcess:
            pass


ROW = re.compile(
    r"^\s*(\d+)\s+([\d.Ee+\-]+)\s+([\d.Ee+\-]+)\s+(\d+:\d+:\d+)\s+([\d.Ee+\-]+)\s+(\d+)\s+([\d.Ee+\-]+)\s+([\d.Ee+\-]+)\s*$"
)


def sta_progress(path: Path, duration: float) -> dict:
    if not path.exists():
        return {}
    with path.open("rb") as f:
        size = f.seek(0, 2)
        f.seek(max(0, size - 65536))
        text = f.read().decode("ascii", errors="replace")
    result = {
        "solver_success": "THE ANALYSIS HAS COMPLETED SUCCESSFULLY" in text,
        "solver_error": "THE ANALYSIS HAS NOT BEEN COMPLETED" in text,
    }
    for line in reversed(text.splitlines()):
        m = ROW.match(line)
        if m:
            increment, step, total, cpu, stable, critical, ke, energy = m.groups()
            result.update(
                increment=int(increment),
                simulation_time_s=float(step),
                total_time_s=float(total),
                cpu_time=cpu,
                stable_increment_s=float(stable),
                critical_element=int(critical),
                kinetic_energy_Nmm=float(ke),
                total_energy_Nmm=float(energy),
                solver_percent=min(100.0, 100 * float(step) / duration),
            )
            break
    # VEXTERNALDB can close a solver cleanly before its requested end time.
    # The success banner alone must not make that checkpoint a solved model.
    result['solver_success'] = bool(result['solver_success'] and not result['solver_error']
                                    and float(result.get('simulation_time_s', 0)) >= duration * .999)
    return result


def tail(path: Path, limit=16000):
    if not path.exists():
        return ""
    with path.open("rb") as f:
        size = f.seek(0, 2)
        f.seek(max(0, size - limit))
        return f.read().decode("utf-8", errors="replace")
