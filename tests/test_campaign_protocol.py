import copy

import pytest

from honeycomb_studio.campaign import campaign_manifest
from honeycomb_studio.campaign_acceptance import confirmation_report, import_evidence
from honeycomb_studio.campaign_protocol import advance


def test_evidence_requires_same_source_runtime_successful_validation_workflow():
    manifest = campaign_manifest()
    manifest.update(source_sha='a' * 40, runtime_hash='b' * 64)
    evidence = dict(source_sha='a' * 40, runtime_hash='b' * 64,
                    material={'passed': True}, restart={'passed': True},
                    archive_restore={'passed': True}, cross_runner=True)
    run = dict(id=123, status='completed', conclusion='success',
               path='.github/workflows/core-damage-validate.yml')
    with pytest.raises(ValueError, match='source'):
        import_evidence(manifest, {**evidence, 'source_sha': 'c' * 40}, run)
    with pytest.raises(ValueError, match='successful'):
        import_evidence(manifest, evidence, {**run, 'conclusion': 'failure'})
    updated = import_evidence(manifest, evidence, run)
    assert updated['gates']['restart']['passed']
    assert advance(updated)['phase'] == 'pilot'


def test_confirmation_does_not_call_physical_failure_a_valid_optimum():
    manifest = campaign_manifest()
    baseline = manifest['designs'][0]
    baseline['summary'] = {'core_mass_kg': .1}
    sample = copy.deepcopy(baseline)
    sample.update(id='confirmation-0001', role='confirmation', status='completed',
                  archive_verified=True, quality={'passed': True},
                  summary={'core_mass_kg': .09, 'rear_skin_deleted': True, 'event_finished': True,
                           'SEA_core_J_kg': 100., 'max_rear_downward_mm': 2.},
                  surrogate_prediction={'SEA_core_J_kg': 101., 'max_rear_downward_mm': 2.1})
    manifest.update(confirmation_count=1, model_locked=True,
                    locked_model_report={'passed': True}, locked_test_report={'passed': True})
    manifest['designs'].append(sample)
    report = confirmation_report(manifest)
    assert report['passed'] is False and report['verified_pareto_ids'] == []
    assert report['configurations'][0]['constraints_passed'] is False
    sample['summary']['rear_skin_deleted'] = False
    assert confirmation_report(manifest)['passed'] is True
    manifest['locked_test_report']['passed'] = False
    assert confirmation_report(manifest)['passed'] is False


def test_quarantined_pilot_stops_instead_of_waiting_forever():
    manifest = campaign_manifest()
    manifest['phase'] = 'pilot'
    manifest['pilot_designs'][0]['status'] = 'quarantined'
    result = advance(manifest)
    assert result['phase'] == 'needs_investigation'
    assert result['blocked_design_ids'] == [manifest['pilot_designs'][0]['id']]
