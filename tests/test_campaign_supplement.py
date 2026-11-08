from copy import deepcopy

import numpy as np
import pytest

from honeycomb_studio.campaign import BOUNDS, geometry_valid
from honeycomb_studio.campaign_protocol import advance, fixed_collection_authorized, runnable
from honeycomb_studio.campaign_queue import admission
from honeycomb_studio.campaign_supplement import prepare_supplement, select_points
from test_campaign_fixed_velocity import fresh_collection


@pytest.fixture(scope='module')
def proposal():
    manifest = fresh_collection()
    manifest['worker_metadata_upgrade'] = {'source_sha': 'a' * 40}
    return manifest, prepare_supplement(manifest, pool_power=10, evaluation_power=10)


def extended(proposal):
    manifest, plan = deepcopy(proposal)
    manifest['designs'].extend(plan['rows'])
    manifest['supplemental_collection_contract'] = plan['contract']
    return manifest


def test_authorized_extension_admits_all500_and_preserves_original400(proposal):
    manifest = extended(proposal)
    assert manifest['designs'][:400] == proposal[0]['designs']
    assert fixed_collection_authorized(manifest)
    assert len(runnable(manifest)) == 500
    assert all(admission(manifest, r) for r in manifest['designs'])
    assert {r['id'] for r in manifest['designs'][400:]} == {f'development-{i:04d}' for i in range(321, 421)}
    assert all(geometry_valid({k: r['model'][k] for k in BOUNDS}) for r in manifest['designs'][400:])
    assert sum(r['role'] == 'test' for r in manifest['designs']) == 80


@pytest.mark.parametrize('change', ['unapproved', 'missing', 'extra', 'physics', 'model', 'parent', 'role', 'duplicate'])
def test_extension_rejects_contract_drift(proposal, change):
    manifest = extended(proposal)
    contract = manifest['supplemental_collection_contract']
    if change == 'unapproved':
        contract['human_authorized'] = False
    elif change == 'missing':
        manifest['designs'].pop()
    elif change == 'extra':
        manifest['designs'].append(deepcopy(manifest['designs'][-1]))
    elif change == 'physics':
        manifest['designs'][-1]['physics_hash'] = 'f' * 64
    elif change == 'model':
        manifest['designs'][-1]['model']['velocity_m_s'] = 8
    elif change == 'parent':
        contract['parent_initial_designs_hash'] = 'f' * 64
    elif change == 'role':
        manifest['designs'][-1]['role'] = 'test'
    else:
        manifest['designs'][-1]['id'] = manifest['designs'][0]['id']
    assert not fixed_collection_authorized(manifest)
    assert runnable(manifest) == []
    assert not admission(manifest, manifest['designs'][-1])


def test_selection_ignores_all_outputs_and_is_reproducible(proposal):
    manifest, plan = deepcopy(proposal)
    for r in manifest['designs']:
        r.update(summary={'rear_skin_deleted': True, 'SEA_core_J_kg': float('nan')},
                 status='completed', quality={'passed': False})
    actual, report = select_points(manifest, pool_power=10, evaluation_power=10)
    expected = np.array([[r['model'][k] for k in BOUNDS] for r in plan['rows']])
    assert np.array_equal(actual, expected)
    assert not report['response_labels_used'] and not report['locked_test_outputs_used']
    assert report['coverage_after']['maximum'] < report['coverage_before']['maximum']


def test_completed400_does_not_finish_while_supplement_is_pending(proposal):
    from test_campaign_provisional_failure import complete

    manifest = extended(proposal)
    for row in manifest['designs'][:400]:
        complete(row)
    assert advance(manifest)['phase'] == 'fixed_collection'
    for row in manifest['designs'][400:]:
        complete(row)
    result = advance(manifest)
    assert result['phase'] == 'collection_completed'
    assert result['collection_report']['completed_verified'] == 500
    assert result['collection_report']['initial_designs_hash'] == manifest['fixed_collection_contract']['initial_designs_hash']
