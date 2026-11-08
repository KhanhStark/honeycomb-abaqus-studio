# -*- coding: utf-8 -*-
"""Abaqus Python: read exact native acceleration and contact force at requested frames."""
from __future__ import print_function
import json,sys,math
from odbAccess import openOdb

def vector(value):
    try:return list(value.dataDouble)
    except:return list(value.data)

def main(config):
    odb=openOdb(path=str(config['odb']),readOnly=True)
    rows=[]
    try:
        for request in config['frames']:
            frame=odb.steps[request['step']].frames[request['frame']]
            if abs(frame.frameValue-request['time_s'])>1.e-10:
                raise ValueError('Native frame time differs from immutable field export')
            acceleration=[]
            for value in frame.fieldOutputs['A'].values:
                if value.instance.name==config['instance'] and value.nodeLabel==config['node_label']:
                    acceleration.append(vector(value)[2])
            if len(acceleration)!=1:raise ValueError('Native impactor reference acceleration is missing or ambiguous')
            force=0.;components={}
            for field,output in frame.fieldOutputs.items():
                if not field.startswith(('CNORMF','CSHEARF')):continue
                values=[vector(value)[2] for value in output.values if value.instance.name==config['instance']]
                components[field]=sum(values);force+=sum(values)
            if not components:raise ValueError('Native contact force fields are missing')
            inertia=config['impact_mass']*(acceleration[0]+config['gravity']*1000.)
            if any(math.isnan(x) or math.isinf(x) for x in (inertia,force)):
                raise ValueError('Native force audit is nonfinite')
            rows.append(dict(request,acceleration_mm_s2=acceleration[0],inertial_force_N=inertia,
                contact_force_N=force,contact_components=components))
    finally:odb.close()
    with open(config['destination'],'w') as stream:json.dump({'rows':rows,'odb_opened_read_only':True},stream,indent=2)
if __name__=='__main__':
    with open(sys.argv[-1]) as stream:main(json.load(stream))
