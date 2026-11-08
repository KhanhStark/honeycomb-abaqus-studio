"""Prepare 100 frozen Linux identities and an auditable sampling plan; no FE or catalog mutation."""
import json
import os
import platform
import subprocess
from pathlib import Path

from honeycomb_studio.campaign_queue import CampaignStore, admission
from honeycomb_studio.campaign_supplement import prepare_supplement
from honeycomb_studio.cloud_github import Github
from honeycomb_studio.models import digest


def main():
    if platform.system() != 'Linux':
        raise ValueError('Prepare identities in the same Linux runtime as native workers')
    github = Github(token=os.environ['GITHUB_TOKEN'])
    manifest = CampaignStore(github).load('core-damage-v2-20261107-v6p5')
    plan = prepare_supplement(manifest)
    plan['preparation_source_sha'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    candidate = {**manifest, 'designs': manifest['designs'] + plan['rows'],
                 'supplemental_collection_contract': plan['contract']}
    if not all(admission(candidate, r) for r in candidate['designs']):
        raise ValueError('At least one old/new configuration fails Linux admission')
    plan['linux_admission_verified'] = 500
    plan['plan_hash'] = digest(plan)
    target = Path('output/supplemental-100-plan.json')
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(plan, indent=2, allow_nan=False), encoding='utf8')
    print(json.dumps({'prepared': len(plan['rows']), 'plan_hash': plan['plan_hash'],
                      'coverage': {k: plan['selection_report'][k] for k in
                                   ('coverage_before', 'coverage_after')}, 'new_fe_processes': 0}))


if __name__ == '__main__':
    main()
