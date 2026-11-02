"""Licensed one-element stop/recover test. No research rows are published."""
import subprocess
import time
from pathlib import Path

from native_cloud_worker import native_runtime

from honeycomb_studio import solver
from honeycomb_studio.cloud_continuation import checkpoint_inventory, verify_checkpoint
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
m.ExplicitDynamicsStep(name='Test',previous='Initial',timePeriod=.5)
m.steps['Test'].Restart(numberIntervals=1000,timeMarks=OFF,overlay=ON)
m.fieldOutputRequests['F-Output-1'].setValues(numIntervals=10)
j=mdb.Job(name='recover_probe',model='Model-1',numCpus=4,numDomains=4,explicitPrecision=DOUBLE,nodalOutputPrecision=FULL)
j.writeInput(consistencyChecking=ON)
'''


def main():
    ROOT.mkdir()
    (ROOT / 'build.py').write_text(BUILD)
    with native_runtime(ROOT) as executable:
        subprocess.run(solver.command(str(executable), 'cae', 'noGUI=' + str(ROOT / 'build.py')), cwd=ROOT, check=True, timeout=120)
        process = solver.launch(str(executable), ['job=recover_probe', 'cpus=4', 'double=both', 'interactive'], ROOT, ROOT / 'first.log')
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError('Probe finished before interruption; recovery was not exercised')
            state = solver.sta_progress(ROOT / 'recover_probe.sta', .5)
            if state.get('simulation_time_s', 0) > .002:
                break
            time.sleep(.25)
        else:
            raise RuntimeError('Probe never reached a checkpoint')
        subprocess.run(solver.command(str(executable), 'terminate', 'job=recover_probe'), cwd=ROOT, check=False, timeout=60)
        process.wait(timeout=90)
        before = solver.sta_progress(ROOT / 'recover_probe.sta', .5)
        if before.get('solver_success'):
            raise RuntimeError('No interruption occurred')
        files = checkpoint_inventory(ROOT, 'recover_probe')
        receipt = dict(job_name='recover_probe', input_hash='probe', runtime_hash='probe', cpus=4, files=files)
        verify_checkpoint(ROOT, receipt, job_name='recover_probe', input_hash='probe', runtime_hash='probe', cpus=4)
        for p in ROOT.glob('*.lck'):
            p.unlink()
        subprocess.run(solver.command(str(executable), 'job=recover_probe', 'recover', 'cpus=4', 'double=both', 'interactive'), cwd=ROOT, stdout=(ROOT / 'recover.log').open('w'), stderr=subprocess.STDOUT, check=True, timeout=600)
        after = solver.sta_progress(ROOT / 'recover_probe.sta', .5)
        if not after.get('solver_success') or after.get('simulation_time_s', 0) < .5:
            raise RuntimeError('Recovered probe did not finish the original step')
        write_json(Path('output/explicit-recover-verification.json'), {'passed': True, 'before': before, 'after': after, 'files': sorted(files), 'physics_changed': False})


if __name__ == '__main__':
    main()
