import copy

import pytest

from honeycomb_studio.campaign import campaign_manifest
from honeycomb_studio.campaign_acceptance import confirmation_report, import_evidence
from honeycomb_studio.campaign_protocol import advance, runnable


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


def test_time_qualification_starts_at_the_pilot_duration():
    manifest = campaign_manifest()
    manifest.update(phase='pilot', execution_scope='full')
    for row in manifest['pilot_designs']:
        foil = row['model']['foil']
        row.update(status='completed', archive_verified=True, summary=dict(
            velocity_m_s=row['model']['velocity_m_s'], foil=foil,
            solver_completed=True, history_integrity_passed=True, damage_fields_complete=True,
            maximum_energy_balance_drift_percent=0., maximum_artificial_energy_ratio_developed_percent=0.,
            contact_force_check_max_relative_percent=0., expected_energy_J=1., initial_kinetic_energy_J=1.,
            rear_skin_deleted=False, max_rear_downward_mm={.035: 2.5, .0635: 2., .115: 1.5}[foil]))
    result = advance(manifest)
    assert result['phase'] == 'time'
    assert result['trial_duration_s'] == .008
    checks = [r for r in result['designs'] if r.get('purpose') == 'time']
    assert len(checks) == 3
    assert {r['model']['duration'] for r in checks} == {.012}


def test_pilot_only_stops_without_fallback_or_production_on_a_small_response():
    manifest = campaign_manifest()
    manifest.update(phase='pilot', enabled=True)
    for row in manifest['pilot_designs']:
        row.update(status='completed', archive_verified=True, summary=dict(
            velocity_m_s=8., foil=row['model']['foil'], solver_completed=True,
            history_integrity_passed=True, damage_fields_complete=True,
            maximum_energy_balance_drift_percent=0., maximum_artificial_energy_ratio_developed_percent=0.,
            contact_force_check_max_relative_percent=0., expected_energy_J=84.8, initial_kinetic_energy_J=84.8,
            rear_skin_deleted=False, max_rear_downward_mm=.2))
    result = advance(manifest)
    assert result['phase'] == 'pilot_completed'
    assert result['enabled'] is False
    assert result['pilot_report']['response_window_passed'] is False
    assert len(result['pilot_designs']) == 3
    assert len(result['designs']) == 400
    assert runnable(result) == []
    assert runnable({**result, 'phase': 'production'}) == []
