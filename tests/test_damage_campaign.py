import copy
import importlib.util
import json
from pathlib import Path

import pytest

from honeycomb_studio.campaign import (
    campaign_manifest,
    freeze,
    geometry_valid,
    model_hashes,
    one_run_spec,
    pilots,
    reference_model,
)
from honeycomb_studio.models import BatchSpec, ModelSpec, digest


def test_campaign_identity_survives_json_and_worker_model_validation():
    manifest = campaign_manifest()
    for design in manifest['pilot_designs'] + manifest['designs']:
        transported = json.loads(json.dumps(design))
        worker_model = BatchSpec.model_validate(one_run_spec(transported)).model
        assert digest(transported['model']) == digest(worker_model.model_dump()), design['id']
        assert transported['physics_hash'] == digest(worker_model.resolved()), design['id']


def test_reference_contract_units_and_identity():
    model = reference_model()
    spec = model.resolved()
    assert spec["impact_mass"] == pytest.approx(.00077)
    assert spec["velocity"] == 15000
    assert spec["energy_J"] == pytest.approx(86.625)
    assert spec["core_height"] == 15
    assert spec["core_material"]["johnson_cook"]["d3"] == .47
    assert digest(spec) != digest(reference_model(velocity_m_s=10).resolved())
    BatchSpec.model_validate(one_run_spec(pilots()[0]))
    with pytest.raises(ValueError):
        reference_model(core_material={**model.core_material.model_dump(), "johnson_cook": {"d3": -47}})
    assert ModelSpec().impactor_shape == "sphere"
    before = model_hashes(model)
    mesh = model_hashes(reference_model(core_centre_seed=.35))
    foil = model_hashes(reference_model(foil=.05))
    assert before['physical_inputs_hash'] == mesh['physical_inputs_hash']
    assert before['numerical_inputs_hash'] != mesh['numerical_inputs_hash']
    assert before['physical_inputs_hash'] != foil['physical_inputs_hash']
    assert before['numerical_inputs_hash'] == foil['numerical_inputs_hash']
    assert before['physics_hash'] != mesh['physics_hash']


def test_manifest_reproducible_valid_partition_and_fail_closed():
    campaign = campaign_manifest()
    assert campaign == campaign_manifest()
    assert len(campaign["designs"]) == len({r["physics_hash"] for r in campaign["designs"]}) == 400
    for owner in {r["owner"] for r in campaign["designs"]}:
        assigned = [r for r in campaign["designs"] if r["owner"] == owner]
        assert len(assigned) == 50
        assert sum(r["role"] == "test" for r in assigned) == 10
    assert all(geometry_valid({k: r["model"][k] for k in campaign["bounds"]}) for r in campaign["designs"])
    with pytest.raises(ValueError, match="gates"):
        freeze(copy.deepcopy(campaign), 15, .004, 1, {})


def test_solver_material_deck_is_explicit_and_unit_correct(tmp_path):
    path = Path(__file__).parents[1] / "src/honeycomb_studio/adapters/damage_keywords.py"
    module_spec = importlib.util.spec_from_file_location("damage_keywords", path)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    deck = tmp_path / "test.inp"
    deck.write_text("*Shell Section, elset=CORE, material=REF\n.0635,5\n*Material, name=REF\n"
                    "*Density\n2.7e-9\n*Elastic\n70000,.33\n*Plastic\n324,0\n"
                    "*Step, name=Impact\n*Dynamic, Explicit\n,.004\n*End Step\n")
    model = reference_model()
    module.rewrite_input(str(deck), model.resolved(), {"REF": model.core_material.model_dump()})
    text = deck.read_text()
    assert "-0.77,1.45,0.47,0.0,1.6,650.0,20.0,1.0" in text
    assert "900000000.0" in text
    assert "CONTROLS=HC_DAMAGE" in text and "ELEMENT DELETION=YES" in text
    assert "*Dynamic, Explicit, ADIABATIC" in text
