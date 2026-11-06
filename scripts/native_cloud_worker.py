"""Run a catalog shard in the same isolated Abaqus environment as native trials."""

import argparse
import ipaddress
import os
import re
import subprocess
from contextlib import contextmanager
from pathlib import Path

from cloud_worker import run

from honeycomb_studio.engine import ADAPTERS


def license_settings(endpoint, vendor):
    match = re.fullmatch(r"(\d{1,5})@([0-9.]+)", endpoint)
    if not match or not vendor.isdecimal():
        raise ValueError("blocked_license: cần địa chỉ FlexNet IPv4 và hai cổng riêng")
    manager, host = match.groups()
    ipaddress.IPv4Address(host)
    if not all(1 <= int(port) <= 65535 for port in (manager, vendor)):
        raise ValueError("blocked_license: cổng FlexNet không hợp lệ")
    return manager, host, vendor


@contextmanager
def native_runtime(root, *, continuation=False):
    manager, host, vendor = license_settings(
        os.environ["ABAQUS_LICENSE_ENDPOINT"], os.environ["ABAQUS_VENDOR_PORT"]
    )
    print("::add-mask::" + host, flush=True)
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    private = Path(os.environ["RUNNER_TEMP"]) / "cloud-private"
    private.mkdir(mode=0o700, exist_ok=True)
    config = private / "abaqus_v6.env"
    config.write_text("license_server_type=FLEXNET\nabaquslm_license_file="
                      + repr(os.environ["ABAQUS_LICENSE_ENDPOINT"])
                      + "\nmp_mode=THREADS\nparallel=DOMAIN\n", encoding="utf-8")
    if continuation:
        # This callback contains C only; do not invoke the default Fortran driver.
        with config.open('a') as stream:
            # Public utility symbols resolve from the running Explicit solver.
            # Avoid copying its transitive C++ libraries into the user library.
            stream.write("link_sl=['g++','-shared','-Wl,--as-needed','%E','-Wl,-soname,%U','-o','%U','%F','%A','%L','%B']\n")
    settings = {
        "HONEYCOMB_IMPACT_ROOT": str(root), "HONEYCOMB_LICENSE_HOST": host,
        "HONEYCOMB_ADAPTERS": str(ADAPTERS), "HONEYCOMB_LICENSE_CONFIG": str(config),
        "HONEYCOMB_SOLVER_CPUS": "4", "HONEYCOMB_SOLVER_MEMORY": "11g",
    }
    previous = {key: os.environ.get(key) for key in settings}
    os.environ.update(settings)
    wrapper = Path(__file__).resolve().parent / "linux_media/abaqus_container.py"
    wrapper.chmod(0o755)
    subnet = "172.29.231.0/24"
    drop = ["-s", subnet, "-j", "DROP"]
    allow = ["-s", subnet, "-d", host, "-p", "tcp", "-m", "multiport",
             "--dports", manager + "," + vendor, "-j", "ACCEPT"]
    rules = []
    created = False

    def command(*args):
        return subprocess.run(args, check=True, capture_output=True, text=True)

    try:
        command("docker", "network", "create", "--subnet", subnet, "honeycomb-impact")
        created = True
        for chain, rule in [("DOCKER-USER", drop), ("INPUT", drop), ("DOCKER-USER", allow)]:
            command("sudo", "iptables", "-I", chain, "1", *rule)
            rules.append((chain, rule))
        yield wrapper
    finally:
        # Containers belong to this ephemeral runner, including a cancelled solver.
        try:
            containers = command("docker", "ps", "-aq", "--filter", "label=honeycomb.impact=true").stdout.split()
            if containers:
                command("docker", "rm", "-f", *containers)
        finally:
            config.unlink(missing_ok=True)
            for chain, rule in reversed(rules):
                subprocess.run(["sudo", "iptables", "-D", chain, *rule], check=False, capture_output=True)
            if created:
                subprocess.run(["docker", "network", "rm", "honeycomb-impact"], check=False, capture_output=True)
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--parent-id", required=True)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    args.root = args.root.resolve()
    with native_runtime(args.root) as executable:
        args.abaqus = executable
        run(args)
