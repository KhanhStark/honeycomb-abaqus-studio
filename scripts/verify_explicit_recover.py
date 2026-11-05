"""Licensed one-element stop/recover test. No research rows are published."""
import argparse
import json
import shutil
import subprocess
import time
from pathlib import Path

from native_cloud_worker import native_runtime

from honeycomb_studio import solver
from honeycomb_studio.cloud_continuation import checkpoint_inventory, verify_checkpoint
from honeycomb_studio.data import history_continuity
from honeycomb_studio.store import write_json

ROOT = Path('/tmp/honeycomb-recover-probe')
BUILD = '''from abaqus import *
from abaqusConstants import *
import part, material, section, assembly, step, interaction, load, mesh, job
import regionToolset, visualization, os
Mdb()
m=mdb.models['Model-1']
s=m.ConstrainedSketch(name='box',sheetSize=10.)
s.rectangle(point1=(0.,0.),point2=(1.,1.))
p=m.Part(name='Cube',dimensionality=THREE_D,type=DEFORMABLE_BODY)
p.BaseSolidExtrude(sketch=s,depth=1.)
a=m.rootAssembly
i=a.Instance(name='Cube-1',part=p,dependent=ON)
mat=m.Material(name='Elastic')
mat.Density(table=((2.7e-9,),))
mat.Elastic(table=((70000.,.33),))
m.HomogeneousSolidSection(name='S',material='Elastic')
p.SectionAssignment(region=p.Set(name='ALL',cells=p.cells),sectionName='S')
p.seedPart(size=.5)
p.setMeshControls(regions=p.cells,technique=STRUCTURED)
p.setElementType(regions=(p.cells,),elemTypes=(mesh.ElemType(elemCode=C3D8R,elemLibrary=EXPLICIT),))
p.generateMesh()
a.regenerate()
m.ExplicitDynamicsStep(name='Test',previous='Initial',timePeriod=.06)
m.steps['Test'].Restart(numberIntervals=1000,timeMarks=OFF,overlay=ON)
m.fieldOutputRequests['F-Output-1'].setValues(numIntervals=10)
m.historyOutputRequests['H-Output-1'].setValues(numIntervals=1000)
j=mdb.Job(name='recover_probe',model='Model-1',numCpus=4,numDomains=4,explicitPrecision=DOUBLE,nodalOutputPrecision=FULL)
j.writeInput(consistencyChecking=ON)
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=('all', 'create', 'restore'), default='all')
    args = parser.parse_args()
    if args.stage != 'restore':
        ROOT.mkdir()
        (ROOT / 'abaqus_v6.env').write_text('verbose=ON\n')
        (ROOT / 'build.py').write_text(BUILD)
    control = ROOT / 'continuation_control.c'
    shutil.copy2('scripts/linux_media/continuation_control.c', control)
    reader = ROOT / 'read_history.py'
    reader.write_text('''from odbAccess import openOdb
import json, sys
odb=openOdb('recover_probe.odb',readOnly=True)
channels=[]
for step, obj in odb.steps.items():
    for region, hist in obj.historyRegions.items():
        for variable, series in hist.historyOutputs.items():
            channels.append(dict(step=step,region=region,variable=variable,data=list(series.data)))
odb.close()
open(sys.argv[-1],'w').write(json.dumps(channels))
''')
    with native_runtime(ROOT, continuation=True) as executable:
        if args.stage != 'restore':
            create_checkpoint(executable, control, reader)
        if args.stage == 'create':
            return
        complete_checkpoint(executable, control, reader, cross_runner=args.stage == 'restore')


def create_checkpoint(executable, control, reader):
        subprocess.run(solver.command(str(executable), 'cae', 'noGUI=' + str(ROOT / 'build.py')), cwd=ROOT, check=True, timeout=120)
        process = solver.launch(str(executable), ['job=recover_probe', 'cpus=4', 'double=both', 'user=' + str(control), 'interactive'], ROOT, ROOT / 'first.log')
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError('Probe finished before interruption; recovery was not exercised')
            state = solver.sta_progress(ROOT / 'recover_probe.sta', .06)
            if state.get('simulation_time_s', 0) > .02:
                break
            time.sleep(.25)
        else:
            raise RuntimeError('Probe never reached a checkpoint')
        (ROOT / 'continuation.stop').touch()
        process.wait(timeout=90)
        if not (ROOT / 'continuation-stop-ack.json').exists():
            raise RuntimeError('Solver did not acknowledge orderly stop')
        (ROOT / 'continuation.stop').unlink()
        before = solver.sta_progress(ROOT / 'recover_probe.sta', .06)
        if before.get('solver_success'):
            raise RuntimeError('No interruption occurred')
        files = checkpoint_inventory(ROOT, 'recover_probe')
        receipt = dict(job_name='recover_probe', input_hash='probe', runtime_hash='probe', cpus=4, files=files)
        verify_checkpoint(ROOT, receipt, job_name='recover_probe', input_hash='probe', runtime_hash='probe', cpus=4)
        for p in ROOT.glob('*.lck'):
            p.unlink()
        subprocess.run(solver.command(str(executable), 'python', str(reader), str(ROOT / 'history-before.json')), cwd=ROOT, check=True, timeout=120)
        shutil.copy2(ROOT / 'recover_probe.sta', ROOT / 'before.sta')
        write_json(ROOT / 'checkpoint-receipt.json', {**receipt, 'before': before})


def complete_checkpoint(executable, control, reader, *, cross_runner=False):
        receipt = json.loads((ROOT / 'checkpoint-receipt.json').read_text())
        verify_checkpoint(ROOT, receipt, job_name='recover_probe', input_hash='probe', runtime_hash='probe', cpus=4)
        files, before = receipt['files'], receipt['before']
        subprocess.run(solver.command(str(executable), 'job=recover_probe', 'recover', 'cpus=4', 'double=both', 'user=' + str(control), 'interactive'), cwd=ROOT, stdout=(ROOT / 'recover.log').open('w'), stderr=subprocess.STDOUT, check=True, timeout=600)
        after = solver.sta_progress(ROOT / 'recover_probe.sta', .06)
        if not after.get('solver_success') or after.get('simulation_time_s', 0) < .06:
            raise RuntimeError('Recovered probe did not finish the original step')
        subprocess.run(solver.command(str(executable), 'python', str(reader), str(ROOT / 'history-after.json')), cwd=ROOT, check=True, timeout=120)
        channels = json.loads((ROOT / 'history-after.json').read_text())
        continuity = history_continuity(channels, {'duration': .06, 'history_intervals': 1000})
        if not continuity['passed']:
            raise RuntimeError('Recovered history is incomplete: ' + json.dumps(continuity))
        original = json.loads((ROOT / 'history-before.json').read_text())
        final = {(r['step'], r['region'], r['variable']): r['data'] for r in channels}
        for row in original:
            values = final.get((row['step'], row['region'], row['variable']), [])
            if values[:len(row['data'])] != row['data']:
                raise RuntimeError('Recovery changed the existing history prefix')
        write_json(Path('output/explicit-recover-verification.json'), {'passed': True, 'cross_runner': cross_runner, 'before': before, 'after': after, 'files': sorted(files), 'physics_changed': False, 'history_integrity': continuity,
                   'stop': json.loads((ROOT / 'continuation-stop-ack.json').read_text())})


if __name__ == '__main__':
    main()
