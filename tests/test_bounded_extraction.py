import copy
import importlib.util
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace as Obj

import numpy as np
import pytest

ADAPTERS = Path(__file__).parents[1] / 'src/honeycomb_studio/adapters'


def load(name):
    spec = importlib.util.spec_from_file_location(name, ADAPTERS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Field:
    def __init__(self, values, components=()):
        self.values, self.componentLabels = values, components
        for value in values:
            value.position = 'NODAL'
        self.description, self.type = 'Original native field', 'VECTOR'
        self.locations, self.validInvariants = [], []
    def getSubset(self, region):
        return Field([v for v in self.values if v.instance.name == 'BOTTOM-1'])
    @property
    def bulkDataBlocks(self):
        return [Obj()]  # Native block without readable data exercises FieldValue fallback.


def odb_fixture():
    instances = {name: Obj(nodes=[Obj(label=i) for i in (1, 2, 3)],
        elements=[Obj(label=1, connectivity=(1, 2, 3))],
        nodeSets={'CLAMP': Obj(nodes=[Obj(label=1)])}) for name in ('BOTTOM-1', 'CORE-1', 'TOP-1')}
    frames = []
    for frame in range(5):
        status = [Obj(instance=Obj(name=name), elementLabel=1, data=0. if frame >= 3 and name == 'BOTTOM-1' else 1.)
                  for name in instances]
        # A nonzero initial U3 must survive the process boundary exactly.
        u = [Obj(instance=Obj(name='BOTTOM-1'), nodeLabel=i, data=(0, 0, .2 - frame * i)) for i in (1, 2, 3)]
        outputs = {'U': Field(u, ('U1', 'U2', 'U3')), 'STATUS': Field(status)}
        outputs.update({k: Field(status) for k in ('PEEQ', 'SDEG', 'JCCRT', 'TEMP')})
        frames.append(Obj(fieldOutputs=outputs, frameValue=frame * .002))
    history = Obj(historyOutputs={'ALLIE': Obj(description='Original complete history', data=((0, 0), (.008, 3)))})
    return Obj(rootAssembly=Obj(instances=instances), sections={}, jobData=Obj(version='2020'),
               steps={'Impact': Obj(timePeriod=.008, totalTime=0., historyRegions={'Assembly': history}, frames=frames)},
               close=lambda: None)


def test_independent_reader_groups_preserve_every_frame_field_history_and_damage_state(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, 'odbAccess', Obj(openOdb=lambda **kwargs: odb_fixture()))
    monkeypatch.setitem(sys.modules, 'cStringIO', Obj(StringIO=io.BytesIO))
    monkeypatch.setitem(sys.modules, 'damage_metrics', load('damage_metrics'))
    extractor, bounded = load('extract'), load('extract_bounded')
    records = []
    def publish(spool, sequence, kind, arrays, meta):
        records.append((sequence, kind, copy.deepcopy(meta), {k: np.array(v, copy=True) for k, v in arrays.items()}))
    monkeypatch.setattr(extractor, 'publish', publish)
    whole, groups = tmp_path / 'whole', tmp_path / 'groups'
    whole.mkdir()
    groups.mkdir()
    common = dict(odb='immutable-native.odb', full_fields=False, damage_metrics=True, chunk_size=2)
    extractor.run(dict(common, extract_directory=str(whole)))
    expected_records = records[:]
    records.clear()
    launches = []
    def launch(path):
        child = json.loads(Path(path).read_text())
        launches.append((child['frame_start'], child['frame_stop']))
        extractor.run(child)
    bounded.extract_groups(dict(common, extract_directory=str(groups)), 5, launch, group_size=2)
    assert launches == [(0, 2), (2, 4), (4, 5)]
    for name in ('inventory.json', 'histories.json', 'damage-summary.json', 'rear-field-history.json', 'complete.json'):
        assert json.loads((whole / name).read_text()) == json.loads((groups / name).read_text()), name
    assert len(records) == len(expected_records)
    for actual, expected in zip(records, expected_records):
        assert actual[:3] == expected[:3]
        for key, value in expected[3].items():
            np.testing.assert_array_equal(actual[3][key], value)


@pytest.mark.parametrize('problem', ['partial', 'changed_history', 'changed_metadata'])
def test_partial_or_inconsistent_groups_never_publish_complete_marker(tmp_path, problem):
    bounded = load('extract_bounded')
    def launch(path):
        child = json.loads(Path(path).read_text())
        folder = Path(child['metadata_directory'])
        later = child['frame_start'] > 0
        count = child['frame_stop'] - child['frame_start']
        inventory = {'frames': count, 'chunks': child['sequence_start'] + count, 'fields': [],
                     'instances': ['changed' if later and problem == 'changed_metadata' else 'original']}
        if later and problem == 'partial':
            inventory['frames'] -= 1
        (folder / 'inventory.json').write_text(json.dumps(inventory))
        (folder / 'complete.json').write_text(json.dumps({'complete': True, 'chunks': inventory['chunks']}))
        (folder / 'histories.json').write_text(json.dumps([2 if later and problem == 'changed_history' else 1]))
    with pytest.raises(ValueError):
        bounded.extract_groups({'full_fields': False, 'extract_directory': str(tmp_path)}, 3, launch, group_size=2)
    assert not (tmp_path / 'complete.json').exists()
