"""Execute real AA6061-T6 shell coupons in the pinned licensed Linux runtime."""
import json
import subprocess
from pathlib import Path

from native_cloud_worker import native_runtime

from honeycomb_studio import solver
from honeycomb_studio.campaign_coupons import CASES, write_coupon
from honeycomb_studio.engine import ADAPTERS
from honeycomb_studio.store import write_json


def main():
    root = Path('/tmp/honeycomb-material-validation')
    root.mkdir()
    results = []
    with native_runtime(root) as executable:
        for case in CASES:
            folder = root / case
            card = write_coupon(folder, case)
            with (folder / 'solver.log').open('w') as log:
                subprocess.run(solver.command(str(executable), 'job=' + case, 'cpus=1',
                                              'double=both', 'interactive'), cwd=folder, stdout=log,
                               stderr=subprocess.STDOUT, check=True, timeout=600)
            subprocess.run(solver.command(str(executable), 'python', str(ADAPTERS / 'coupon_extract.py'),
                                          str(folder / (case + '.odb')), str(folder / 'result.json')),
                           cwd=folder, check=True, timeout=120)
            results.append({**card, **json.loads((folder / 'result.json').read_text())})
    report = {'passed': all(r['passed'] for r in results), 'cases': results,
              'validation_scope': 'material implementation only; fracture parameters remain uncalibrated'}
    write_json(Path('output/core-damage-material-validation.json'), report)
    if not report['passed']:
        raise RuntimeError('Material implementation checks failed; production admission remains closed')


if __name__ == '__main__':
    main()
