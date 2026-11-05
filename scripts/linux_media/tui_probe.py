"""Run the unmodified 2020 installer offline; stop on unrecognized questions.

Page vocabulary checked against the original 2020 installation transcript:
https://gist.github.com/branfosj/f0bfa2410f7279e5c2d0dfb58bc3c2e6
This driver supplies no activation tools, server or license file.
"""

import json
import os
import re
import subprocess
import time
from pathlib import Path

import pexpect


def install_caa():
    """Install the original companion API package required for user callbacks."""
    with Path('/results/caa-installer.log').open('w', buffering=1) as log:
        child = pexpect.spawn('/bin/bash',
            ['/media/4/SIMULIA_EstablishedProducts_CAA_API/Linux64/1/StartTUI.sh'],
            encoding='utf-8', codec_errors='replace', timeout=900, dimensions=(50, 160))
        child.logfile_read = log
        try:
            for _ in range(50):
                index = child.expect([r'Enter selection(?: \(default: (?:Next|Install|Close)\))?:\s*',
                                      r'Default \[([^\r\n]*)\]:\s*', pexpect.EOF])
                page = child.before.replace('\r', '')
                print(page[-4000:], flush=True)
                if index == 2:
                    child.close()
                    if child.exitstatus != 0:
                        raise RuntimeError('CAA installer failed; inspect caa-installer.log')
                    return
                answer = ''
                if index == 1:
                    default = child.match.group(1)
                    if default not in ('/usr/SIMULIA/EstProducts/2020', '/opt/SIMULIA/EstProducts/2020'):
                        raise RuntimeError('Unrecognized CAA path question: ' + default)
                    answer = '/opt/SIMULIA/EstProducts/2020'
                elif not any(word in page for word in ('Welcome', 'Legal Notices', 'enough information',
                                                       'Installation', 'installation', 'press Enter')):
                    raise RuntimeError('Unrecognized CAA installer question; inspect caa-installer.log')
                child.sendline(answer)
            raise RuntimeError('CAA installer prompt limit exceeded')
        finally:
            if child.isalive():
                child.close(force=True)


def main():
    result = {
        "installer_executed": True,
        "activation_tools_executed": False,
        "network_enabled": False,
        "license_checked_out": False,
        "solver_executed": False,
        "installation_completed": False,
    }
    log = Path("/results/installer.log").open("w", buffering=1)
    child = pexpect.spawn(
        "/bin/bash",
        ["/media/4/SIMULIA_EstablishedProducts/Linux64/1/StartTUI.sh"],
        encoding="utf-8",
        codec_errors="replace",
        timeout=900,
        dimensions=(50, 160),
    )
    child.logfile_read = log
    started = time.monotonic()
    skip_selected = False
    showing_error_details = False
    try:
        for _ in range(100):
            index = child.expect(
                [
                    r"Enter selection(?: \(default: (Next|Install|Close)\))?:\s*",
                    r"Default \[([^\r\n]*)\]:\s*",
                    r"Please choose an action:\s*",
                    pexpect.EOF,
                ]
            )
            page = child.before.replace("\r", "")
            if index == 3:
                child.close()
                result["installer_exit_code"] = child.exitstatus
                break
            print(page[-4000:], flush=True)
            if showing_error_details:
                raise RuntimeError("Installer failed; technical details captured in installer.log")
            answer = ""
            if index == 2:
                if "[T] Show technical details" in page:
                    child.sendline("T")
                    showing_error_details = True
                    continue
                if "[1] Continue" not in page:
                    raise RuntimeError("Unrecognized installer action")
                answer = "1"
            elif index == 1:
                default = child.match.group(1)
                paths = {
                    "/usr/SIMULIA/EstProducts/2020": "/opt/SIMULIA/EstProducts/2020",
                    "/var/DassaultSystemes/SIMULIA/Commands": "/opt/SIMULIA/Commands",
                    "/var/DassaultSystemes/SIMULIA/CAE/plugins/2020": "/opt/SIMULIA/plugins/2020",
                }
                if default not in paths:
                    raise RuntimeError("Unrecognized path question: " + default)
                answer = paths[default]
            elif re.search(r"^\s*1 \[[^]]+\] Abaqus/Standard Solver", page, re.M):
                entries = re.findall(r"^\s*(\d+) \[([^]]+)\] (.+)$", page, re.M)
                wanted = {
                    "Abaqus/Standard Solver",
                    "Abaqus/Explicit Solver",
                    "Cosimulation Services",
                    "Abaqus ODB API Services",
                    "Abaqus CAE",
                }
                if not wanted.issubset({label.strip() for _, _, label in entries}):
                    raise RuntimeError("Unrecognized component menu")
                component_actions = [
                    number
                    for number, mark, label in entries
                    if (mark.strip() in ("*", "X")) != (label.strip() in wanted)
                ]
                if component_actions:
                    answer = component_actions.pop(0)
            elif "Skip licensing configuration" in page:
                if not skip_selected:
                    answer = "3"
                    skip_selected = True
            elif any(
                s in page
                for s in [
                    "Welcome to",
                    "Please refer to the documentation for the Legal Notices",
                    "The installation program has enough information",
                    "Just press Enter to exit",
                    "Installation complete",
                    "installation has completed",
                    "Installation successful",
                ]
            ):
                pass
            else:
                raise RuntimeError("Unrecognized installer question; inspect installer.log")
            child.sendline(answer)
        else:
            raise RuntimeError("Installer prompt limit exceeded")
        command = Path("/opt/SIMULIA/Commands/abaqus")
        if result.get("installer_exit_code") != 0 or not command.exists():
            raise RuntimeError("Installer did not create a successful Abaqus installation")
        result["installation_completed"] = True
        if os.getenv('HONEYCOMB_INSTALL_CAA') == '1':
            install_caa()
            result['caa_api_installed'] = True
        for label, args in [
            ("release", ["information=release"]),
            ("odb_import", ["python", "-c", "import sys,odbAccess; print(sys.version)"]),
        ]:
            with Path("/results/" + label + ".log").open("w") as stream:
                completed = subprocess.run(
                    [str(command), *args], stdout=stream, stderr=subprocess.STDOUT, timeout=120
                )
            result[label + "_exit_code"] = completed.returncode
            if completed.returncode:
                raise RuntimeError(label + " command failed")
    except Exception as exc:
        result["error"] = str(exc)
        raise
    finally:
        if child.isalive():
            child.sendline("!q")
            child.close(force=True)
        result["seconds"] = time.monotonic() - started
        diagnostics = []
        for path in Path("/opt/SIMULIA/EstProducts/2020/InstallData/log").rglob("*"):
            if path.is_file() and path.suffix.lower() in (".log", ".txt"):
                diagnostics.append(str(path) + "\n" + path.read_text(errors="replace")[-30000:])
                if sum(map(len, diagnostics)) > 500000:
                    break
        Path("/results/installer-diagnostics.log").write_text("\n\n".join(diagnostics))
        Path("/results/install-probe.json").write_text(json.dumps(result, indent=2))
        log.close()


if __name__ == "__main__":
    main()
