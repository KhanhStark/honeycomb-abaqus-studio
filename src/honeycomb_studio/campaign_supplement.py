"""A bounded extension of the frozen 400-point collection; inputs only, no labels."""
from __future__ import annotations

from copy import deepcopy

import numpy as np
import scipy
import platform
from scipy.spatial import cKDTree
from scipy.stats import qmc

from .campaign import BOUNDS, OWNERS, geometry_valid, model_hashes, record
from .campaign_protocol import fixed_collection_authorized
from .models import ModelSpec, digest

BATCH_ID = 'supplemental-100-20261109'
SEED = 20261109
COUNT = 100


def select_points(manifest, *, pool_power=16, evaluation_power=16):
    """Greedy farthest points in normalized physical coordinates, seeded by development."""
    if not fixed_collection_authorized(manifest) or len(manifest['designs']) not in (400, 500):
        raise ValueError('Supplement requires an authorized collection of 400 or 500 configurations')
    low, high = np.array(list(BOUNDS.values())).T
    development = [r for r in manifest['designs'] if r['role'] == 'development']
    if len(development) != len(manifest['designs']) - 80:
        raise ValueError('Existing development configurations and the locked 80-test split are required')
    anchors = (np.array([[r['model'][k] for k in BOUNDS] for r in development]) - low) / (high - low)
    # Locked test INPUTS are consulted solely to prevent an exact duplicate.
    known = {tuple(r['model'][k] for k in BOUNDS) for r in manifest['designs']}

    def valid_pool(seed, power, exclude_known=False):
        unit = qmc.Sobol(d=4, scramble=True, seed=seed).random_base2(power)
        values = qmc.scale(unit, low, high)
        valid = np.array([geometry_valid(dict(zip(BOUNDS, map(float, v), strict=True)))
                          and (not exclude_known or tuple(v) not in known) for v in values])
        return unit[valid], values[valid], int(np.sum(~valid))

    candidates, physical, rejected = valid_pool(SEED, pool_power, True)
    if len(candidates) < COUNT:
        raise ValueError('Insufficient valid distinct candidates')
    distances = cKDTree(anchors).query(candidates)[0]
    chosen, selection_distance = [], []
    for _ in range(COUNT):
        index = int(np.argmax(distances))
        if distances[index] <= 1e-12:
            raise ValueError('Supplement would duplicate a known configuration')
        chosen.append(index)
        selection_distance.append(float(distances[index]))
        distances = np.minimum(distances, np.linalg.norm(candidates - candidates[index], axis=1))
        distances[chosen] = -1.
    evaluation, _, evaluation_rejected = valid_pool(SEED + 1, evaluation_power)
    before = cKDTree(anchors).query(evaluation)[0]
    after = cKDTree(np.vstack((anchors, candidates[chosen]))).query(evaluation)[0]

    def coverage(values):
        return {'mean': float(np.mean(values)), 'p95': float(np.quantile(values, .95)),
                'maximum': float(np.max(values))}

    report = {'method': 'sequential_maximin_from_geometry_filtered_scrambled_sobol',
              'versions': {'python': platform.python_version(), 'numpy': np.__version__, 'scipy': scipy.__version__},
              'seed': SEED, 'count': COUNT, 'candidate_count': 2**pool_power,
              'valid_candidates': len(candidates), 'rejected_candidates': rejected,
              'evaluation_seed': SEED + 1, 'evaluation_count': len(evaluation),
              'evaluation_rejected': evaluation_rejected,
              'distance': 'Euclidean after scaling each physical bound to [0,1]',
              'coverage_before': coverage(before), 'coverage_after': coverage(after),
              'selection_distances': selection_distance,
              'anchor_ids': [r['id'] for r in development], 'response_labels_used': False,
              'locked_test_outputs_used': False, 'locked_test_inputs': 'exact duplicate exclusion only',
              'coverage_is_empirical': True, 'physical_validation': 'not_established'}
    return physical[chosen], report


def prepare_supplement(manifest, *, pool_power=16, evaluation_power=16):
    points, report = select_points(manifest, pool_power=pool_power, evaluation_power=evaluation_power)
    # Linux generation checks the existing identities before freezing new ones.
    for row in manifest['designs']:
        if model_hashes(ModelSpec.model_validate(row['model'])) != {
                k: row[k] for k in ('physics_hash', 'physical_inputs_hash', 'numerical_inputs_hash')}:
            raise ValueError('Platform/model differs from frozen native identities; use the Linux worker runtime')
    template = deepcopy(next(r['model'] for r in manifest['designs'] if r['id'] == 'development-0001'))
    batch_number = (len(manifest['designs']) - 400) // COUNT + 1
    batch_id = BATCH_ID + ('-02' if batch_number == 2 else '')
    start_index = max(int(r['id'].split('-')[-1]) for r in manifest['designs'] if r['role'] == 'development') + 1
    rows = []
    for i, vector in enumerate(points):
        model = ModelSpec.model_validate({**template, **dict(zip(BOUNDS, map(float, vector), strict=True))})
        row = record(model, 'development', start_index + i, OWNERS[i % len(OWNERS)], list(BOUNDS))
        row.update(supplemental_batch_id=batch_id, selection_reason=report['method'],
                   max_checkpoint_segments=8, selection_order=i + 1)
        rows.append(row)
    contract = {'human_authorized': True, 'batch_id': batch_id, 'count': COUNT,
                'parent_initial_designs_hash': manifest['fixed_collection_contract']['initial_designs_hash'],
                'parent_collection_designs_hash': digest({r['id']: r['physics_hash'] for r in manifest['designs']}),
                'designs_hash': digest({r['id']: r['physics_hash'] for r in rows}),
                'models_hash': digest({r['id']: r['model'] for r in rows}),
                'selection_report_hash': digest(report),
                'human_instruction': 'kiểm tra sau đó nghiên cứu chạy thêm 100 mẫu nữa',
                'velocity_m_s': 6.5, 'duration_s': .008, 'test_split_unchanged': True}
    updated = with_supplement(manifest, rows, contract)
    if not fixed_collection_authorized(updated):
        raise ValueError('Supplement does not satisfy the extended immutable contract')
    return {'schema_version': 1, 'campaign_id': manifest['id'], 'rows': rows,
            'contract': contract, 'selection_report': report,
            'initial_model_hash': digest({r['id']: r['model'] for r in manifest['designs']}),
            'solver_source_sha': manifest['worker_metadata_upgrade']['source_sha'],
            'runtime_hash': manifest['runtime_hash'], 'platform': 'Linux'}


def with_supplement(manifest, rows, contract):
    updated = {**manifest, 'designs': manifest['designs'] + rows}
    if manifest.get('supplemental_collection_contract'):
        updated['additional_supplemental_contracts'] = [*manifest.get('additional_supplemental_contracts', []), contract]
    else:
        updated['supplemental_collection_contract'] = contract
    return updated
