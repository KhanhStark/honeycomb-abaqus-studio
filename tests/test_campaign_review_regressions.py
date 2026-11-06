"""Campaign acceptance cases exposed by independent standards/spec reviews."""
import copy

import httpx
import pytest

from honeycomb_studio.campaign import campaign_manifest, numerical_gate, reference_model
from honeycomb_studio.campaign_acceptance import confirmation_report
from honeycomb_studio.campaign_queue import apply_outcome
from honeycomb_studio.cloud_github import CampaignApp
from honeycomb_studio.data import history_summary
from honeycomb_studio.store import write_json


def test_core_sea_uses_part_dissipation_with_real_assembly_region_name(tmp_path):
    times = [0, .001, .002, .003, .004]
    histories = []

    def channel(variable, region, values):
        histories.append(dict(step='Impact', variable=variable, description=variable,
                              region=region, data=list(zip(times, values, strict=True))))

    for key in ('ALLKE', 'ALLIE', 'ALLAE', 'ALLPD', 'ALLSE', 'ALLVD', 'ALLWK', 'ETOTAL'):
        values = {'ALLKE': [86625]*5, 'ALLIE': [0, 1000, 5000, 10000, 10000],
                  'ALLAE': [0, 100, 100, 100, 100], 'ALLPD': [0, 100, 1000, 5000, 5000],
                  'ETOTAL': [86625]*5}.get(key, [0]*5)
        channel(key, 'Assembly ASSEMBLY', values)
    for group in ('CORE', 'FRONT', 'REAR'):
        for key in ('ALLPD', 'ALLDMD', 'ALLSE', 'ALLAE', 'ALLIE'):
            end = {'ALLPD': 12000, 'ALLDMD': 3000}.get(key, 0) if group == 'CORE' else 500
            channel(key, 'ElementSet ASSEMBLY.' + group + '_ENERGY', [0, end, end, end, end])
    for key in ('U3', 'V3', 'A3'):
        channel(key, 'Node IMPACTOR-1.1', [0]*5)
    write_json(tmp_path / 'histories.json', histories)
    write_json(tmp_path / 'inventory.json', {'frames': 5, 'fields': []})
    write_json(tmp_path / 'damage-summary.json', {'damage_fields_complete': True})
    fixture_model = reference_model(mass_kg=.77, velocity_m_s=15, duration=.004)
    summary, _ = history_summary(tmp_path, fixture_model.resolved(), {'core_mass_kg': .0003})
    assert summary['initial_kinetic_energy_J'] == 86.625
    assert summary['core_dissipation_J'] == 15
    assert summary['SEA_core_J_kg'] == pytest.approx(50000)
    # The ratio of the two maxima is 1%, but at the first developed instant it is 10%.
    assert summary['artificial_energy_over_max_internal_percent'] == 1
    assert summary['maximum_artificial_energy_ratio_developed_percent'] == 10
    assert 'maximum_artificial_energy_ratio_developed_percent' in numerical_gate(summary)['errors']


def test_numerically_bad_archived_runs_exhaust_two_retries():
    row = {**campaign_manifest()['pilot_designs'][0], 'ticket': 'a'*32}
    for attempt, expected in ((1, 'solver_retry'), (2, 'solver_retry'), (3, 'quarantined')):
        result = dict(ticket='a'*32, design=row, outcome='completed', archive_verified=True,
                      archive={}, summary={}, quality={'passed': False, 'errors': ['energy']}, workflow_run_id=11)
        row = apply_outcome(row, result)
        assert row['status'] == expected and row['attempt'] == attempt
        row['ticket'] = 'a'*32


def test_fe_confirmation_dominated_by_reference_is_not_a_verified_optimum():
    manifest = campaign_manifest()
    baseline = manifest['designs'][0]
    baseline.update(status='completed', archive_verified=True, quality={'passed': True},
                    summary=dict(core_mass_kg=.1, rear_skin_deleted=False, event_finished=True,
                                 SEA_core_J_kg=200., max_rear_downward_mm=1.))
    sample = copy.deepcopy(baseline)
    sample.update(id='confirmation-0001', role='confirmation')
    sample['summary'].update(core_mass_kg=.09, SEA_core_J_kg=100., max_rear_downward_mm=2.)
    manifest['designs'].append(sample)
    manifest.update(confirmation_count=1, model_locked=True, locked_model_report={'passed': True},
                    locked_test_report={'passed': True})
    report = confirmation_report(manifest)
    assert report['feasible_count'] == 1
    assert report['verified_pareto_ids'] == [] and report['passed'] is False


def test_campaign_repository_client_refreshes_its_own_expired_installation_token():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    issued, authorized = [], []

    def handle(request):
        if request.url.path.endswith('/installation'):
            return httpx.Response(200, json={'id': 123})
        if request.url.path.endswith('/access_tokens'):
            token = 'installation-token-' + str(len(issued) + 1)
            issued.append(token)
            return httpx.Response(201, json={'token': token})
        authorized.append(request.headers['Authorization'])
        return httpx.Response(200, json={'ok': True})

    with httpx.Client(transport=httpx.MockTransport(handle)) as transport:
        app = CampaignApp('test', key, transport)
        github = app.repository('xuankhanh24/honeycomb-abaqus-studio')
        github.repo('GET', '/actions/runs')
        github.expiry = 1
        github.repo('GET', '/actions/runs')
    assert authorized == ['Bearer installation-token-1', 'Bearer installation-token-2']
