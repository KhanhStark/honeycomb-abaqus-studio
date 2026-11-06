import copy

import pytest

from honeycomb_studio.campaign import campaign_manifest
from honeycomb_studio.campaign_queue import (
    admission,
    apply_outcome,
    available_slots,
    claim,
    page_jobs,
    ramp_capacity,
)


def test_claim_cannot_start_duplicate_or_mismatched_continuation():
    design = campaign_manifest()['pilot_designs'][0]
    work = dict(ticket='a' * 32, repository=design['repository'], source_sha='b' * 40,
                design=design, segment=0, status='ready')
    claimed = claim(work, ticket='a' * 32, workflow=11, source_sha='b' * 40, repository=design['repository'])
    for workflow in (11, 12):
        with pytest.raises(ValueError, match='duplicate'):
            claim(claimed, ticket='a' * 32, workflow=workflow, source_sha='b' * 40, repository=design['repository'])
    with pytest.raises(ValueError, match='predecessor'):
        claim({**work, 'segment': 1}, ticket='a' * 32, workflow=12, source_sha='b' * 40,
              repository=design['repository'])


def test_production_cannot_bypass_material_and_forty_design_time_audit():
    manifest = campaign_manifest()
    row = manifest['designs'][0]
    manifest.update(enabled=True, source_sha='a' * 40, runtime_hash='b' * 64, frozen=True,
                    infrastructure={row['owner']: {'passed': True}}, gates={k: {'passed': True} for k in
                    ('material', 'time', 'mesh', 'damage_sensitivity', 'archive_restore')})
    assert not admission(manifest, row)
    manifest['audit_ids'] = [row['id']]
    assert admission(manifest, row)
    manifest['gates']['material']['passed'] = False
    assert not admission(manifest, row)


def test_checkpoint_and_retries_are_bounded_and_upload_failure_never_restarts_solver():
    row = {**campaign_manifest()['pilot_designs'][0], 'ticket': 'a' * 32}
    output = dict(ticket=row['ticket'], design=row, outcome='checkpoint', segment=3, workflow_run_id=11,
                  archive_verified=True, receipt={}, archive={})
    assert apply_outcome(row, output)['status'] == 'budget_exhausted'
    output['archive_verified'] = False
    with pytest.raises(ValueError, match='Unverified'):
        apply_outcome(row, output)
    failed = {**output, 'outcome': 'solver_failed'}
    assert apply_outcome({**row, 'attempt': 2}, failed)['status'] == 'quarantined'
    assert apply_outcome(row, {**failed, 'outcome': 'upload_failed'})['status'] == 'publication_pending'
    assert row['status'] == 'pending'


def test_quota_counts_all_active_jobs_and_reserved_dispatches():
    jobs = [{'status': 'in_progress'}] * 11 + [{'status': 'queued'}] * 3 + [{'status': 'completed'}] * 9
    assert available_slots(20, jobs, reserved=2) == 4
    assert available_slots(8, jobs) == 0
    assert available_slots(200, [], reserved=1) == 19


def test_controller_does_not_consume_the_solver_budget_but_still_uses_owner_quota():
    controller = {'status': 'in_progress', 'campaign_solver': False}
    worker = {'status': 'in_progress', 'campaign_solver': True}
    assert available_slots(1, [controller]) == 1
    assert available_slots(1, [controller, worker]) == 0
    assert available_slots(20, [controller] * 19) == 1
    assert available_slots(20, [controller] * 20) == 0
    assert available_slots(1, [controller], reserved=1) == 0


def test_actions_inventory_separates_controller_from_worker_and_unknown_workflows():
    class Actions:
        repository = 'xuankhanh24/honeycomb-abaqus-studio'
        runs = [{'id': 1, 'path': '.github/workflows/core-damage-controller.yml'}]

        def request(self, method, path, **kwargs):
            if path.startswith('/users/'):
                return [{'full_name': self.repository}]
            if '/jobs?' in path:
                return {'total_count': 1, 'jobs': [{'status': 'in_progress'}]}
            return {'total_count': len(self.runs), 'workflow_runs': self.runs} if 'status=in_progress' in path else {}

    github = Actions()
    assert available_slots(1, page_jobs(github)) == 1
    github.runs.append({'id': 2, 'path': '.github/workflows/core-damage-worker.yml'})
    assert available_slots(1, page_jobs(github)) == 0
    github.runs[-1] = {'id': 2}
    assert available_slots(1, page_jobs(github)) == 0


def test_checkpoint_resume_keeps_model_identity():
    row = {**campaign_manifest()['pilot_designs'][0], 'ticket': 'a' * 32}
    before = copy.deepcopy(row['model'])
    output = dict(ticket=row['ticket'], design=row, outcome='checkpoint', segment=0,
                  archive_verified=True, receipt={'physics_hash': row['physics_hash']}, archive={})
    after = apply_outcome(row, output)
    assert after['segment'] == 1 and after['model'] == before and after['status'] == 'checkpoint'


def test_capacity_ramp_accepts_a_license_ceiling_between_planned_stages():
    manifest = {'capacity_stage': 80, 'license_capacity': 128, 'pilot_designs': [],
                'designs': [dict(archive_verified=True, quality={'passed': True},
                                 solver_started_at=1, solver_finished_at=100) for _ in range(128)]}
    assert ramp_capacity(manifest)['capacity_stage'] == 128
    assert ramp_capacity(manifest)['capacity_stage'] == 128
