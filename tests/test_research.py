import json

import numpy as np
import pytest

from honeycomb_studio.data import consume_spool, verify_export
from honeycomb_studio.models import BatchSpec
from honeycomb_studio.research import field_reduction
from honeycomb_studio.store import write_json


@pytest.mark.parametrize('full_fields', [False, True])
@pytest.mark.parametrize('second_force,expected_error', [(100., 0.), (120., 20.)])
def test_restarted_frames_at_equal_times_are_checked_independently(
    tmp_path, full_fields, second_force, expected_error
):
    from honeycomb_studio.data import history_summary

    spec = BatchSpec().model.model_copy(update={'duration': .008, 'history_intervals': 4, 'gravity': 0}).resolved()
    times = [0., .002, .004, .006, .008]
    values = {'A3': 100. / spec['impact_mass'], 'V3': 0., 'U3': 0.,
              'ALLKE': 7000., 'ALLIE': 0., 'ALLAE': 0., 'ALLPD': 0.,
              'ALLSE': 0., 'ALLVD': 0., 'ALLWK': 0., 'ETOTAL': 7000.}
    histories = [{'step': 'Impact', 'region': 'IMPACTOR' if name in ('A3', 'V3', 'U3') else 'Assembly',
                  'variable': name, 'description': name, 'data': [[t, value] for t in times]}
                 for name, value in values.items()]
    write_json(tmp_path / 'histories.json', histories)
    write_json(tmp_path / 'inventory.json', {'frames': 6, 'fields': []})
    write_json(tmp_path / 'export-policy.json', {'full_fields': full_fields})
    spool = tmp_path / 'spool'
    spool.mkdir()
    sequence = 0
    for frame, resultant in ((2, 100.), (3, second_force)):
        # Two normal chunks and the shear chunk belong to each frame.
        for field, value in (('CNORMF', resultant * .8), ('CNORMF', resultant * .15),
                             ('CSHEARF', resultant * .05)):
            name = f'{sequence:08d}'
            np.savez(spool / (name + '.npz'), data=np.array([[0., 0., value]]),
                     instance_index=np.array([0]))
            write_json(spool / (name + '.ready'), {'npz': name + '.npz', 'sequence': sequence,
                'kind': 'field', 'step': 'Impact', 'frame': frame, 'time_s': .004,
                'field': field, 'instances': ['IMPACTOR-1'], 'components': ['X', 'Y', 'Z']})
            sequence += 1
    assert consume_spool(tmp_path) == 6
    summary, _ = history_summary(tmp_path, spec)
    assert summary['contact_force_check_max_relative_percent'] == pytest.approx(expected_error)


def test_reduced_export_preserves_exact_extremum_labels_and_source_coverage(tmp_path):
    assert not BatchSpec().export_all_fields
    spool = tmp_path / "spool"
    spool.mkdir()
    arrays = {
        "data": np.array([[1.0, 2.0, 3.0], [0.0, 4.0, 0.0]]),
        "mises": np.array([float("nan"), float("nan")]),
        "instance_index": np.array([0, 0]),
        "node_label": np.array([11, 22]),
        "element_label": np.array([-1, -1]),
        "integration_point": np.array([-1, -1]),
        "section_point": np.array([-1, -1]),
    }
    np.savez(spool / "0.npz", **arrays)
    meta = {
        "npz": "0.npz",
        "sequence": 0,
        "kind": "field",
        "step": "Impact",
        "frame": 3,
        "time_s": 0.001,
        "field": "U",
        "instances": ["TOP-1"],
        "components": ["U1", "U2", "U3"],
    }
    write_json(spool / "0.ready", meta)
    write_json(tmp_path / "export-policy.json", {"full_fields": False})
    write_json(tmp_path / "inventory.json", {"fields": [{**meta, "rows": 2}]})
    assert consume_spool(tmp_path) == 1
    assert not list((tmp_path / "fields").rglob("*.parquet"))
    result = json.loads(next((tmp_path / "reduced-fields").glob("*.json")).read_text())
    assert result["extremum"]["value"] == 4
    assert result["extremum"]["node_label"] == 22
    assert result["extremum"]["instance"] == "TOP-1"
    assert result["statistics"]["sum"] == [1, 6, 3]
    assert verify_export(tmp_path)["rows"] == 2
    contact = field_reduction(arrays, {**meta, "field": "CNORMF", "instances": ["IMPACTOR-1"]})
    assert contact["impactor_force_z_N"] == 3


def test_zero_components_remain_in_auditable_statistics_not_inferred_missing():
    arrays = {"data": np.zeros((3, 3)), "instance_index": np.zeros(3, dtype=int)}
    result = field_reduction(arrays, {"field": "CSHEARF", "instances": ["IMPACTOR-1"]})
    assert result["statistics"]["finite_count"] == [3, 3, 3]
    assert result["impactor_force_z_N"] == 0


def test_recorded_creep_and_damage_are_physical_dissipation(tmp_path):
    from honeycomb_studio.data import history_summary

    series = []
    for name, value in {
        "ALLKE": 7,
        "ALLIE": 4,
        "ALLAE": 0.01,
        "ALLPD": 2,
        "ALLSE": 1,
        "ALLVD": 0.02,
        "ALLWK": 0,
        "ETOTAL": 7,
        "ALLFD": 0.5,
        "ALLDMD": 0.3,
        "ALLCD": 9,
    }.items():
        series.append(
            {
                "step": "Impact",
                "region": "Assembly",
                "variable": name,
                "description": name,
                "data": [[0, value * 1000], [0.006, value * 1000]],
            }
        )
    for name in ("A3", "V3", "U3"):
        series.append(
            {
                "step": "Impact",
                "region": "IMPACTOR",
                "variable": name,
                "description": name,
                "data": [[0, 0], [0.006, 0]],
            }
        )
    write_json(tmp_path / "histories.json", series)
    write_json(tmp_path / "inventory.json", {"frames": 2, "fields": []})
    summary, _ = history_summary(tmp_path, BatchSpec().model.resolved(), {"panel_mass_kg": 1})
    assert summary["physical_dissipation_J"] == 11.8
    assert summary["SEA_J_kg"] == 11.8
    assert summary["physical_dissipation_components_J"]["ALLCD"] == 9


def test_default_dataset_contains_research_columns_not_solver_unit_duplicates(tmp_path):
    from pathlib import Path

    import pyarrow.parquet as pq

    from honeycomb_studio.data import dataset
    from honeycomb_studio.store import Store

    store = Store(tmp_path)
    batch = store.create(BatchSpec())
    run = store.list("runs", batch["id"])[0]
    run.update(
        status="completed",
        quality={"ml_eligible": True},
        summary={
            "peak_raw_contact_force_N": 2000,
            "plastic_dissipation_J": 6,
            "physical_dissipation_J": 6,
            "end_impactor_velocity_mm_s": 500,
        },
    )
    store.save("runs", run)
    result = dataset(store, [run["id"]], "Research")
    row = pq.read_table(Path(result["path"]) / "samples.parquet").to_pylist()[0]
    assert row["input.mass_kg"] == 2.65
    assert row["end_impactor_velocity_m_s"] == 0.5
    assert row["physical_dissipation_J"] == 6
    assert "input.impact_mass" not in row and "input.velocity" not in row
    assert "plastic_dissipation_J" not in row and "input.cpus" not in row
