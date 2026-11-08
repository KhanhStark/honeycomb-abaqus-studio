import importlib.util
import sys
from pathlib import Path


def test_original_history_acceleration_does_not_imply_field_acceleration():
    scripts = Path(__file__).parents[1] / 'scripts'
    sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location('force_sampling_test', scripts / 'verify_force_sampling.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original = ('*Output, field, number interval=800\n*Node Output\nU, V\n'
                '*Contact Output\nCFORCE,\n*Output, history, time interval=2e-06\n'
                '*Node Output, nset=Impactor-1.RP\nA3, RF3, U3, V3\n*End Step\n')
    assert not module.field_acceleration_requested(original)
    assert module.field_acceleration_requested(original.replace('U, V\n', 'U, V, A\n'))
    assert not module.field_acceleration_requested(original.replace('U, V\n', '** A is unavailable\nU, V\n'))
