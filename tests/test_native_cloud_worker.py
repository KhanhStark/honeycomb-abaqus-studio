"""Real adapter setup/teardown and restricted license routes, without a solver."""

import importlib
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
native_cloud_worker = importlib.import_module("native_cloud_worker")


@pytest.mark.parametrize("endpoint,vendor", [("invalid", "27012"), ("27011@not-a-host", "27012"),
                                               ("0@100.100.1.1", "27012"), ("27011@100.100.1.1", "65536")])
def test_invalid_license_configuration(endpoint, vendor):
    with pytest.raises(ValueError):
        native_cloud_worker.license_settings(endpoint, vendor)


@pytest.mark.parametrize('continuation', [False, True])
def test_native_context_restricts_network_and_cleans_private_config(tmp_path, monkeypatch, continuation):
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))
    monkeypatch.setenv("ABAQUS_LICENSE_ENDPOINT", "27011@100.100.1.1")
    monkeypatch.setenv("ABAQUS_VENDOR_PORT", "27012")
    monkeypatch.delenv("HONEYCOMB_IMPACT_ROOT", raising=False)
    monkeypatch.setattr(Path, "chmod", lambda *args: None)
    commands = []

    def invoke(args, **kwargs):
        commands.append(list(args))
        return SimpleNamespace(stdout="", returncode=0)

    monkeypatch.setattr(native_cloud_worker.subprocess, "run", invoke)
    with pytest.raises(RuntimeError, match="interrupted"):
        with native_cloud_worker.native_runtime(tmp_path / "results", continuation=continuation) as executable:
            assert executable.name == "abaqus_container.py"
            assert Path(os.environ["HONEYCOMB_LICENSE_CONFIG"]).is_file()
            config = Path(os.environ["HONEYCOMB_LICENSE_CONFIG"]).read_text()
            assert ('link_sl=' in config) is continuation
            if continuation:
                assert "'g++','-shared'" in config and 'ifort' not in config
                assert "'%E'" in config  # Abaqus uses this to retain required archive symbols.
                assert 'mp_mode=MPI' in config
                assert "os.environ['MPI_REMSH']='/probe/mpi_local_shell.py'" in config
            assert os.environ["HONEYCOMB_IMPACT_ROOT"] == str((tmp_path / "results").resolve())
            raise RuntimeError("interrupted")
    assert not (tmp_path / "cloud-private/abaqus_v6.env").exists()
    assert "HONEYCOMB_IMPACT_ROOT" not in os.environ
    additions = [args for args in commands if "iptables" in args and "-I" in args]
    assert len(additions) == 3
    assert additions[-1][-3:] == ["27011,27012", "-j", "ACCEPT"]
    assert len([args for args in commands if "iptables" in args and "-D" in args]) == 3
    assert commands[-1] == ["docker", "network", "rm", "honeycomb-impact"]
