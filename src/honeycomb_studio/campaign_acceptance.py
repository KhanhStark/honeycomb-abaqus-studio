"""Evidence provenance and final FE acceptance, independent of prediction fitting."""
from copy import deepcopy

from .campaign import BOUNDS


def import_evidence(manifest, evidence, workflow):
    if (workflow.get('status') != 'completed' or workflow.get('conclusion') != 'success'
            or workflow.get('path', '').split('@')[0] != '.github/workflows/core-damage-validate.yml'):
        raise ValueError('Evidence must come from a successful validation workflow')
    for key in ('source_sha', 'runtime_hash'):
        if evidence.get(key) != manifest.get(key):
            raise ValueError('Validation ' + key + ' differs from the pinned campaign')
    if evidence.get('cross_runner') is not True:
        raise ValueError('Cross-runner restore evidence is required')
    result = deepcopy(manifest)
    for gate in ('material', 'restart', 'archive_restore'):
        report = evidence.get(gate, {})
        if report.get('passed') is not True:
            raise ValueError('Validation gate failed: ' + gate)
        result.setdefault('gates', {})[gate] = {**report, 'workflow_run_id': workflow['id'],
                                               'source_sha': evidence['source_sha'],
                                               'runtime_hash': evidence['runtime_hash']}
    return result


def confirmation_report(manifest):
    rows = [r for r in manifest['designs'] if r['role'] == 'confirmation']
    if len(rows) != manifest['confirmation_count'] or any(
            r['status'] != 'completed' or not r.get('archive_verified') for r in rows):
        raise ValueError('All FE confirmations must be archived before acceptance')
    baseline = next(r for r in manifest['designs'] if r['role'] == 'development' and not r['varied_parameters'])
    mass_limit = baseline['summary']['core_mass_kg']
    results, feasible = [], []
    for row in rows:
        summary = row['summary']
        constraints = (row.get('quality', {}).get('passed') is True
                       and summary.get('rear_skin_deleted') is False
                       and summary.get('event_finished') is True
                       and summary.get('core_mass_kg', float('inf')) <= mass_limit * (1 + 1.e-8))
        prediction = row.get('surrogate_prediction', {})
        errors = {k: summary[k] - value for k, value in prediction.items() if k in summary}
        results.append({'id': row['id'], 'inputs': {k: row['model'][k] for k in BOUNDS},
                        'constraints_passed': constraints, 'summary': summary,
                        'surrogate_prediction': prediction, 'prediction_error': errors})
        if constraints:
            feasible.append(row)
    known = [r for r in manifest['designs'] if r['role'] in ('development', 'adaptive', 'test', 'confirmation')
             and r.get('archive_verified') and r.get('quality', {}).get('passed')
             and r.get('summary', {}).get('rear_skin_deleted') is False
             and r['summary'].get('event_finished') is True
             and r['summary'].get('core_mass_kg', float('inf')) <= mass_limit * (1 + 1.e-8)
             and all(k in r['summary'] for k in ('SEA_core_J_kg', 'max_rear_downward_mm'))]
    pareto = []
    for row in feasible:
        a = row['summary']
        if not any(other['summary']['SEA_core_J_kg'] >= a['SEA_core_J_kg']
                   and other['summary']['max_rear_downward_mm'] <= a['max_rear_downward_mm']
                   and (other['summary']['SEA_core_J_kg'] > a['SEA_core_J_kg']
                        or other['summary']['max_rear_downward_mm'] < a['max_rear_downward_mm'])
                   for other in known):
            pareto.append(row['id'])
    model_passed = (manifest.get('model_locked') is True
                    and manifest.get('locked_model_report', {}).get('passed') is True
                    and manifest.get('locked_test_report', {}).get('passed') is True)
    return {'passed': model_passed and bool(pareto), 'configurations': results,
            'verified_pareto_ids': pareto, 'feasible_count': len(feasible), 'core_mass_limit_kg': mass_limit,
            'model_acceptance_passed': model_passed,
            'physical_scope': 'AA6061-T6 reference simulation; fracture evolution uncalibrated',
            'safety_standard_established': False}
