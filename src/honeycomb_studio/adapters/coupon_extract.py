# -*- coding: utf-8 -*-
"""Abaqus Python 2.7: observe initiation, degradation, deletion and adiabatic heat."""
import json
import sys
from odbAccess import openOdb


def check(path):
    odb = openOdb(path=path, readOnly=True)
    try:
        step = odb.steps.values()[-1]
        rows = []
        for frame in step.frames:
            row = {'time_s': frame.frameValue}
            for name in ('SDEG', 'JCCRT', 'STATUS', 'PEEQ', 'TEMP'):
                if name not in frame.fieldOutputs.keys():
                    raise ValueError('Missing material test field ' + name)
                values = [float(v.data) for v in frame.fieldOutputs[name].values]
                row[name] = (min(values) if name == 'STATUS' else max(values)) if values else None
            rows.append(row)
        initiated = next((i for i, r in enumerate(rows) if (r['JCCRT'] or 0) >= .99), None)
        softened = next((i for i, r in enumerate(rows) if 0 < (r['SDEG'] or 0) < 1), None)
        deleted = next((i for i, r in enumerate(rows) if r['STATUS'] == 0), None)
        errors = []
        if step.frames[-1].frameValue < .000999:
            errors.append('solver_incomplete')
        if initiated is None or softened is None or deleted is None:
            errors.append('initiation_softening_deletion_not_observed')
        elif not initiated <= softened <= deleted:
            errors.append('damage_sequence')
        if max(r['TEMP'] or 20 for r in rows) <= 20:
            errors.append('adiabatic_heat_not_observed')
        return {'passed': not errors, 'errors': errors, 'history': rows,
                'purpose': 'implementation check; not material calibration'}
    finally:
        odb.close()


if __name__ == '__main__':
    result = check(sys.argv[-2])
    with open(sys.argv[-1], 'w') as stream:
        json.dump(result, stream, indent=2)
