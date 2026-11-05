# -*- coding: utf-8 -*-
"""Reuse the exact mesh/material cache and update the independent impact load."""
from abaqus import *
from abaqusConstants import *
import json, os, sys

def byteify(value):
    if isinstance(value,unicode):return value.encode('utf-8')
    if isinstance(value,dict):return dict((byteify(k),byteify(v)) for k,v in value.items())
    if isinstance(value,list):return [byteify(v) for v in value]
    return value

cfg=byteify(json.load(open(sys.argv[-1])))
openMdb(pathName=cfg['cache_cae'])
m=mdb.models['Honeycomb-Study']
m.setValues(description=('%s; %%g J; mm-tonne-s-N; see manifest.'%('Assumed reentrant image-1 core; baseline external setup' if cfg.get('core_topology')=='reentrant_0' else 'Foo2008 reconstruction'))%cfg['energy_J'])
m.predefinedFields['Initial-Impact-Velocity'].setValues(velocity3=-cfg['velocity'])
jobname=cfg['job_name']
for old_job in list(mdb.jobs.keys()):del mdb.jobs[old_job]
mdb.Job(name=jobname,model=m.name,type=ANALYSIS,numCpus=cfg['cpus'],numDomains=cfg['cpus'],explicitPrecision=DOUBLE,nodalOutputPrecision=FULL,memory=70,memoryUnits=PERCENTAGE)
out=cfg['output_directory'];os.chdir(out)
mdb.saveAs(pathName=os.path.join(out,jobname+'.cae'))
mdb.jobs[jobname].writeInput(consistencyChecking=ON)
if cfg['core_material'].get('johnson_cook') or cfg['face_material'].get('johnson_cook'):
    sys.path.insert(0,cfg['adapter_directory'])
    from damage_keywords import rewrite_input
    rewrite_input(jobname+'.inp',cfg,{
        'AA6061-T6-Facesheets':cfg['face_material'],'AA6061-T6-Core':cfg['core_material']})
actual=json.load(open(cfg['cache_manifest']))
actual.update(cfg);actual['cache_hit']=True
with open(os.path.join(out,'model_manifest.json'),'w') as f:json.dump(actual,f,indent=2,sort_keys=True)
