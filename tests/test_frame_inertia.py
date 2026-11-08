import importlib.util,json,sys
from pathlib import Path
from types import SimpleNamespace
import pytest

def test_exact_native_frame_audit_does_not_interpolate_off_grid_acceleration(tmp_path,monkeypatch):
    time=.007081075105816126
    mass=.00265
    contact=2527.2409901761566
    instance=SimpleNamespace(name='IMPACTOR-1')
    acceleration=SimpleNamespace(instance=instance,nodeLabel=1,dataDouble=(0.,0.,contact/mass-9810.))
    normal=SimpleNamespace(instance=instance,nodeLabel=2,dataDouble=(0.,0.,contact))
    frame=SimpleNamespace(frameValue=time,fieldOutputs={'A':SimpleNamespace(values=[acceleration]),'CNORMF':SimpleNamespace(values=[normal])})
    closed=[]
    odb=SimpleNamespace(steps={'Impact':SimpleNamespace(frames=[frame])},close=lambda:closed.append(True))
    def opened(**kwargs):
        assert kwargs['readOnly'] is True
        return odb
    monkeypatch.setitem(sys.modules,'odbAccess',SimpleNamespace(openOdb=opened))
    path=Path(__file__).parents[1]/'src/honeycomb_studio/adapters/frame_inertia.py'
    spec=importlib.util.spec_from_file_location('native_frame_inertia_test',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    destination=tmp_path/'audit.json'
    config={'odb':'original.odb','destination':str(destination),'frames':[dict(step='Impact',frame=0,time_s=time)],'instance':'IMPACTOR-1','node_label':1,'impact_mass':mass,'gravity':9.81}
    module.main(config)
    result=json.loads(destination.read_text())['rows'][0]
    assert result['contact_force_N']==contact
    assert result['inertial_force_N']==pytest.approx(contact)
    assert result['inertial_force_N']!=pytest.approx(2408.278729303422)
    assert closed==[True]
    config['frames'][0]['time_s']+=.000002
    with pytest.raises(ValueError,match='frame time'):module.main(config)
    assert closed==[True,True]
