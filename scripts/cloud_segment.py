"""One bounded segment of a real Explicit analysis, preserving state between runners."""
import argparse
import json
import os
import signal
import time
from pathlib import Path

from cloud_worker import require_qualification
from native_cloud_worker import native_runtime

from honeycomb_studio import solver
from honeycomb_studio.cloud_archive import ReleaseArchive
from honeycomb_studio.cloud_continuation import checkpoint_inventory, verify_checkpoint
from honeycomb_studio.cloud_github import JOB_ID, Catalog, Github
from honeycomb_studio.cloud_matrix import ShardCatalog
from honeycomb_studio.cloud_progress import Progress
from honeycomb_studio.engine import Engine
from honeycomb_studio.models import BatchSpec, digest, expand
from honeycomb_studio.store import Store, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent-id', required=True)
    parser.add_argument('--job-id', required=True)
    parser.add_argument('--segment', type=int, required=True, choices=range(4))
    args = parser.parse_args()
    if not all(JOB_ID.fullmatch(i) for i in (args.parent_id, args.job_id)):
        raise ValueError('Invalid job identity')
    root = Path('/tmp/honeycomb-results')  # portable absolute path across all segment runners
    workflow = int(os.environ['GITHUB_RUN_ID'])
    github = Github(token=os.environ['GITHUB_TOKEN'])
    catalog = ShardCatalog(Catalog(github), args.parent_id, args.job_id, workflow)
    key = 'jobs/' + args.job_id
    job, _ = catalog.get(key)
    if job.get('cancel_requested'):
        raise ValueError('Batch cancelled')
    if args.segment == 0 and job['status'] != 'draft':
        raise ValueError('Initial segment already claimed; do not rerun duplicate jobs')
    if args.segment > 0 and job['status'] != 'running':
        raise ValueError('Continuation requires an unfinished running shard')
    if digest(job['spec']) != job['input_hash']:
        raise ValueError('Catalog input digest mismatch')
    runtime_hash = digest(require_qualification(Path.cwd()))
    model = dict(job['spec'])
    model.update(render_images=False, backup_after_run=False, max_runs=1, export_all_fields=job['profile'] == 'full')
    spec = BatchSpec.model_validate(model)
    expected = expand(spec)[0]
    store = Store(root)
    marker = root / 'continuation.json'
    if args.segment == 0:
        if store.list('batches'):
            raise ValueError('Initial segment requires clean storage')
        batch = store.create(spec)
        run = store.list('runs', batch['id'])[0]
    else:
        receipt = json.loads(marker.read_text())
        if receipt['segment'] != args.segment - 1 or receipt['child_id'] != args.job_id or receipt['workflow'] != workflow:
            raise ValueError('Wrong predecessor segment')
        batch = store.get('batches', receipt['batch_id'])
        run = store.get('runs', receipt['run_id'])
        attempt = run['attempts'][-1]
        raw = Path(attempt['path']) / 'raw'
        verify_checkpoint(raw, receipt, job_name=attempt['job_name'], input_hash=expected['input_hash'],
                          runtime_hash=runtime_hash, cpus=run['resolved']['cpus'])
        if run['input_hash'] != expected['input_hash'] or run['resolved'] != expected['resolved']:
            raise ValueError('Restored scientific input mismatch')
        if not solver.sta_progress(raw / (attempt['job_name'] + '.sta'), run['resolved']['duration']).get('solver_success'):
            run['explicit_recover'] = True
        for lock in raw.glob(attempt['job_name'] + '*.lck'):
            lock.unlink()
        attempt['process'] = None  # never adopt an old PID on a different runner
        run.update(status='queued', phase='queued', error=None)
        store.save('runs', run)
    batch.update(status='running', pause_requested=False, stop_immediately=False)
    store.save('batches', batch)
    catalog.update(key, lambda old: {**old, 'status': 'running', 'workflow_run_id': workflow,
                                    'phase': f'Explicit continuation segment {args.segment + 1}/4'})
    # 240-minute slice leaves room for multi-GB checkpoint transfer and publication.
    deadline = time.monotonic() + max(0, 240 * 60 - (time.time() - float(os.environ['HONEYCOMB_WORKFLOW_STARTED_EPOCH'])))
    progress = Progress(github, catalog, args.job_id, store, batch['id'], deadline)
    try:
        with native_runtime(root) as executable:
            engine = Engine(store, abaqus=str(executable), fake=False)
            engine.explicit_continuation = True
            engine.runtime_fingerprint = runtime_hash
            for sig in (signal.SIGTERM, signal.SIGINT):
                signal.signal(sig, lambda *_: progress.stop_solver('cancelled'))
            progress.start(os.environ['GITHUB_SHA'])
            try:
                engine.execute_wave([run], batch)
            finally:
                progress.done.set()
                progress.thread.join(timeout=70)
        run = store.get('runs', run['id'])
        if run['status'] in ('completed', 'review'):
            publisher = ReleaseArchive(github, job['reserved_release_id'])
            publisher.publish(root, attempt=f'workflow-{workflow}', complete=True)
            release = github.repo('PATCH', f'/releases/{job["reserved_release_id"]}', {'draft': False})
            catalog.update(key, lambda old: {**old, 'status': run['status'], 'archive_verified': True,
                           'release_id': release['id'], 'release_url': release['html_url'],
                           'phase': 'completed across Explicit segments',
                           'runs': [{k: run.get(k) for k in ('id', 'status', 'summary', 'quality', 'error')}]})
            outcome = 'completed'
        else:
            if progress.stop_reason != 'timed_out' or run['status'] != 'interrupted':
                raise RuntimeError('Solver failed independently of segment budget: ' + str(run.get('error')))
            attempt = run['attempts'][-1]
            raw = Path(attempt['path']) / 'raw'
            files = checkpoint_inventory(raw, attempt['job_name'])
            receipt = {'segment': args.segment, 'workflow': workflow, 'child_id': args.job_id,
                       'batch_id': batch['id'], 'run_id': run['id'], 'job_name': attempt['job_name'],
                       'input_hash': run['input_hash'], 'runtime_hash': runtime_hash,
                       'cpus': run['resolved']['cpus'], 'files': files,
                       'progress': solver.sta_progress(raw / (attempt['job_name'] + '.sta'), run['resolved']['duration'])}
            write_json(marker, receipt)
            if args.segment == 3:
                raise RuntimeError('Four segment budget exhausted; retained checkpoint requires investigation')
            outcome = 'checkpoint'
        try:
            github.repo('PATCH', f'/check-runs/{progress.check}', {
                'status': 'completed', 'conclusion': 'neutral' if outcome == 'checkpoint' else 'success',
                'output': {'title': outcome, 'summary': 'Verified state retained for next segment' if outcome == 'checkpoint' else 'Solver and archive completed'},
            })
        except Exception:
            pass  # A convenience check update cannot invalidate verified data.
        with open(os.environ['GITHUB_OUTPUT'], 'a') as out:
            out.write('outcome=' + outcome + '\n')
        print(json.dumps({'outcome': outcome, 'run_id': run['id'], 'segment': args.segment}), flush=True)
    except Exception as exc:
        error = str(exc)
        catalog.update(key, lambda old: {**old, 'status': 'failed', 'error': error})
        raise
    finally:
        store.db.close()


if __name__ == '__main__':
    main()
