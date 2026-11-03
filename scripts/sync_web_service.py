"""Build web's lightweight service from canonical modules; never fork model validation."""

import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
dest = root / "web/service"
dest.mkdir(parents=True, exist_ok=True)
fingerprints = {}
for name in (
    "__init__.py",
    "models.py",
    "execution.py",
    "estimates.py",
    "cloud_github.py",
    "cloud_matrix.py",
    "cloud_quality.py",
    "cloud_api.py",
    "cloud_runtime.py",
    "cloud_solver_download.py",
    "cloud_restore.py",
    "standalone_download.py",
    "runtime-evidence.json",
    "adapters/reentrant.py",
    "adapters/hexagonal.py",
):
    source = root / "src/honeycomb_studio" / name
    data = source.read_bytes().replace(b"\r\n", b"\n")
    (dest / name).parent.mkdir(parents=True, exist_ok=True)
    (dest / name).write_bytes(data)
    fingerprints[name] = hashlib.sha256(data).hexdigest()
(dest / "source-manifest.json").write_text(json.dumps(fingerprints, indent=2), encoding="utf-8")
