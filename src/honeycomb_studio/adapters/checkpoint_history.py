"""Read original buffered history after an orderly stop; Abaqus Python 2.7."""
import json
import sys

from odbAccess import openOdb

odb = openOdb(path=sys.argv[-2], readOnly=True)
try:
    channels = []
    for step_name, step in odb.steps.items():
        for region, histories in step.historyRegions.items():
            for variable, series in histories.historyOutputs.items():
                channels.append(dict(step=step_name, region=region, variable=variable, data=list(series.data)))
finally:
    odb.close()
with open(sys.argv[-1], 'w') as output:
    json.dump(channels, output)
