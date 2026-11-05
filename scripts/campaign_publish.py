"""Recover a failed upload from its immutable Actions artifact; never invoke a solver."""
import argparse
import json
import os

from campaign_worker import ROOT, publish_execution, source_sha

from honeycomb_studio.campaign_queue import ticket_key
from honeycomb_studio.cloud_github import Catalog, Github


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('claim', 'run'))
    args = parser.parse_args()
    github = Github(token=os.environ['GITHUB_TOKEN'])
    catalog = Catalog(github)
    key = ticket_key(os.environ['CAMPAIGN_ID'], os.environ['TICKET'])
    if args.mode == 'claim':
        def claim_upload(old):
            if (not old or old.get('outcome') != 'upload_failed'
                    or old.get('publication_status') != 'ready'
                    or old.get('publication_workflow_run_id')):
                raise ValueError('Publication already claimed or result is not recoverable')
            return {**old, 'publication_status': 'claimed',
                    'publication_workflow_run_id': int(os.environ['GITHUB_RUN_ID'])}
        catalog.update(key, claim_upload)
        return
    work, _ = catalog.get(key)
    result = json.loads((ROOT / 'campaign-execution.json').read_text())
    if (not work or work.get('outcome') != 'upload_failed' or work['ticket'] != result['ticket']
            or work['workflow_run_id'] != int(os.environ['ORIGINAL_RUN_ID'])
            or work['source_sha'] != source_sha() or result['source_sha'] != source_sha()
            or work['design']['physics_hash'] != result['design']['physics_hash']):
        raise ValueError('Publication artifact does not belong to the failed execution')
    if result['outcome'] not in ('completed', 'checkpoint'):
        raise ValueError('Only computed results can be republished')
    if work.get('publication_workflow_run_id') != int(os.environ['GITHUB_RUN_ID']):
        raise ValueError('No exclusive publication claim')
    publish_execution(work, result, github, catalog, key)


if __name__ == '__main__':
    main()
