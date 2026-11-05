#!/usr/bin/python3
"""CLI adapter for the existing engine; mount only results, adapters and client config."""

import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

root = Path(os.environ["HONEYCOMB_IMPACT_ROOT"]).resolve()
cwd = Path.cwd().resolve()
if not cwd.is_relative_to(root):
    raise SystemExit("Solver working directory escaped impact root")
name = "honeycomb-impact-" + str(os.getpid()) + "-" + str(time.time_ns())
cpus = os.environ.get("HONEYCOMB_SOLVER_CPUS", "4")
memory = os.environ.get("HONEYCOMB_SOLVER_MEMORY", "11g")
if not cpus.isdigit() or not 1 <= int(cpus) <= 4 or not re.fullmatch(r"(?:[1-9]|10|11)g", memory):
    raise SystemExit("Invalid bounded container resources")
command = [
    "docker",
    "run",
    "--rm",
    "--name",
    name,
    "--label",
    "honeycomb.impact=true",
    "--label",
    "honeycomb.actions=true",
    "--network",
    "honeycomb-impact",
    "--user",
    str(os.getuid()) + ":" + str(os.getgid()),
    "--cap-drop",
    "ALL",
    "--security-opt",
    "no-new-privileges",
    "--cpus",
    cpus,
    "--pids-limit",
    "1024",
    "--memory",
    memory,
    "--shm-size",
    "1g",
    "--dns",
    "127.0.0.1",
    "--add-host",
    "STARK:" + os.environ["HONEYCOMB_LICENSE_HOST"],
    "--workdir",
    str(cwd),
    "--env",
    "HOME=/home/modelrunner",
    "--env",
    "HONEYCOMB_CONTINUATION_DIRECTORY=" + str(cwd),
    "--mount",
    "type=volume,source=honeycomb-install,target=/opt,readonly",
]
for source, target, readonly in [
    (root, root, False),
    (Path(os.environ["HONEYCOMB_ADAPTERS"]), Path(os.environ["HONEYCOMB_ADAPTERS"]), True),
    (Path(os.environ["HONEYCOMB_LICENSE_CONFIG"]), Path("/home/modelrunner/abaqus_v6.env"), True),
]:
    command += [
        "--mount",
        "type=bind,source=" + str(source) + ",target=" + str(target) + (",readonly" if readonly else ""),
    ]
command += ["honeycomb-install-probe", "python3", "/probe/entrypoint.py", *sys.argv[1:]]


def interrupted(signum, frame):
    raise KeyboardInterrupt


signal.signal(signal.SIGTERM, interrupted)
try:
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    for line in process.stdout:
        sys.stdout.buffer.write(
            line.replace(os.environ["HONEYCOMB_LICENSE_HOST"].encode(), b"<private-license-host>")
        )
        sys.stdout.buffer.flush()
    sys.exit(process.wait())
finally:
    subprocess.run(["docker", "rm", "-f", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
