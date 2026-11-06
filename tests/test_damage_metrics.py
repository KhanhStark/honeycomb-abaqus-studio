from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace as Obj


class OdbRepository:
    """The ODB mapping intentionally has no dict.get method."""
    def __init__(self, values):
        self.values = values

    def __contains__(self, key):
        return key in self.values

    def __getitem__(self, key):
        return self.values[key]

    def __delitem__(self, key):
        del self.values[key]


def test_rear_peak_ignores_detached_nodes_and_remembers_deletion():
    path = Path(__file__).parents[1] / "src/honeycomb_studio/adapters/damage_metrics.py"
    spec = spec_from_file_location("damage_metrics", path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    rear = Obj(nodes=[Obj(label=i) for i in (1, 2, 3, 4, 5, 6)],
               elements=[Obj(label=1, connectivity=(1, 2, 3)), Obj(label=2, connectivity=(3, 4, 5)),
                         Obj(label=3, connectivity=(4, 5, 6))],
               nodeSets={"PERIMETER_CLAMP": Obj(nodes=[Obj(label=1)])})
    metric = module.RearMetrics(Obj(rootAssembly=Obj(instances={"BOTTOM-1": rear})))

    class Field:
        def __init__(self, values):
            self.values = values

        def getSubset(self, region):
            return Field([v for v in self.values if v.instance.name == "BOTTOM-1"])

    def frame(deleted, displacement):
        status = [Obj(instance=Obj(name=instance), elementLabel=i, data=0. if i in deleted and instance == "BOTTOM-1" else 1.)
                  for instance in ("BOTTOM-1", "CORE-1", "TOP-1") for i in (1, 2, 3)]
        u = [Obj(instance=Obj(name="BOTTOM-1"), nodeLabel=i, data=(0, 0, z))
             for i, z in enumerate(displacement, 1)]
        return Obj(fieldOutputs=OdbRepository({"U": Field(u), "STATUS": Field(status),
                                 **{k: Field(status) for k in ('PEEQ', 'SDEG', 'JCCRT', 'TEMP')}}))

    metric.frame(frame([], [.2] * 6), 0)
    metric.frame(frame([], [.2, -.8, -1.8, -.8, -.8, -.8]), .001)
    metric.frame(frame([2], [.2, -.8, -1.8, -100, -100, -100]), .002)
    summary = metric.summary()
    assert summary["max_rear_downward_mm"] == 2
    assert summary["max_rear_raw_downward_mm"] == 100
    assert summary["rear_skin_deleted"] is True
    assert summary["damage_fields_complete"] is True
    missing = frame([], [.2] * 6)
    del missing.fieldOutputs['JCCRT']
    metric.frame(missing, .003)
    assert metric.summary()['damage_fields_complete'] is False
    missing_status = frame([], [.2] * 6)
    del missing_status.fieldOutputs['STATUS']
    metric.frame(missing_status, .004)
    assert metric.summary()['damage_fields_complete'] is False
