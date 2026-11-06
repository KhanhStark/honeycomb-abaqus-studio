# -*- coding: utf-8 -*-
"""Read-only Abaqus Python 2.7 display export; never changes the analysis mesh.

Shell elements and frames are sampled deterministically. Element stress/plastic
strain are maxima over recorded integration/section points, without smoothing.
Missing values remain null. Numerical research data stays in ODB/Parquet.
"""
from __future__ import print_function

import json
import math
import os
import sys


def indices(count, limit):
    if count <= limit:
        return list(range(count))
    return sorted(set(int(round(i * (count - 1.0) / (limit - 1))) for i in range(limit)))


def finite(value):
    try:
        value = float(value)
        return float('%.8g' % value) if not math.isnan(value) and not math.isinf(value) else None
    except (ValueError, TypeError):
        return None


def components(value):
    try:
        return list(value.dataDouble)
    except Exception:
        return list(value.data)


def export(odb, config):
    max_elements = max(4, min(6000, int(config.get('max_elements', 1000))))
    max_frames = max(2, min(25, int(config.get('max_frames', 13))))
    instances = []
    candidates = []
    unsupported = {}
    for name in sorted(odb.rootAssembly.instances.keys()):
        inst = odb.rootAssembly.instances[name]
        supported = [e for e in inst.elements if str(e.type).startswith(('S3', 'S4', 'STRI', 'R3D3', 'R3D4'))]
        for element in inst.elements:
            if not str(element.type).startswith(('S3', 'S4', 'STRI', 'R3D3', 'R3D4')):
                key = str(element.type)
                unsupported[key] = unsupported.get(key, 0) + 1
        if supported:
            candidates.append((name, inst, supported))
    total = sum(len(item[2]) for item in candidates)
    # One global sampling budget preserves small instances, with no mesh interpolation.
    remaining = max_elements
    for number, (name, inst, elements) in enumerate(candidates):
        budget = min(remaining - (len(candidates) - number - 1), max(1, int(max_elements * len(elements) / float(total))))
        chosen = [elements[i] for i in indices(len(elements), max(2, budget))] if budget >= 2 else elements[:1]
        remaining -= len(chosen)
        labels = set(n for e in chosen for n in e.connectivity)
        nodes = [n for n in inst.nodes if n.label in labels]
        lookup = dict((n.label, i) for i, n in enumerate(nodes))
        instances.append({
            'name': name,
            'original_elements': len(elements),
            'node_labels': [n.label for n in nodes],
            'coordinates': [[float(v) for v in n.coordinates] for n in nodes],
            'elements': [{'label': e.label, 'type': str(e.type), 'nodes': [lookup[n] for n in e.connectivity]} for e in chosen],
        })
    if len(candidates) > max_elements:
        raise ValueError('Too many instances for the display budget')
    frames = []
    frame_keys = [(name, i) for name, step in odb.steps.items() for i in range(len(step.frames))]
    selected_frames = set(frame_keys[i] for i in indices(len(frame_keys), max_frames))
    for step_name, step in odb.steps.items():
        for frame_index in range(len(step.frames)):
            if (step_name, frame_index) not in selected_frames:
                continue
            frame = step.frames[frame_index]
            data = []
            for mesh in instances:
                inst = odb.rootAssembly.instances[mesh['name']]
                lookup = dict((label, i) for i, label in enumerate(mesh['node_labels']))
                element_lookup = dict((e['label'], i) for i, e in enumerate(mesh['elements']))
                displacement = [None] * len(lookup)
                stress = [None] * len(element_lookup)
                plastic = [None] * len(element_lookup)
                if 'U' in frame.fieldOutputs.keys():
                    for value in frame.fieldOutputs['U'].getSubset(region=inst).values:
                        index = lookup.get(value.nodeLabel)
                        if index is not None:
                            displacement[index] = [finite(v) for v in components(value)]
                for field_name, target in [('S', stress), ('PEEQ', plastic)]:
                    if field_name not in frame.fieldOutputs.keys():
                        continue
                    for value in frame.fieldOutputs[field_name].getSubset(region=inst).values:
                        index = element_lookup.get(value.elementLabel)
                        if index is None:
                            continue
                        if field_name == 'S':
                            scalar = finite(value.mises)
                        else:
                            try:
                                scalar = finite(value.dataDouble)
                            except Exception:
                                scalar = finite(value.data)
                        if scalar is not None:
                            target[index] = scalar if target[index] is None else max(target[index], scalar)
                data.append({'u': displacement, 'mises': stress, 'peeq': plastic})
            frames.append({'step': step_name, 'frame': frame_index, 'time_s': frame.frameValue, 'instances': data})
    return {
        'schema_version': 1, 'kind': 'honeycomb-field-view',
        'source': config.get('source', {}),
        'solver_release': str(odb.jobData.version),
        'units': {'coordinates': 'mm', 'u': 'mm', 'mises': 'MPa', 'peeq': '1', 'time': 's'},
        'units_basis': 'model contract mm-N-s; ODB itself does not encode physical units',
        'sampling': {'original_shell_elements': total, 'display_elements': sum(len(i['elements']) for i in instances),
                     'max_frames': max_frames, 'unsupported_elements': unsupported,
                     'method': 'deterministic element/frame subsample; original node coordinates and connectivity',
                     'element_fields': 'maximum of recorded integration and section points; no nodal extrapolation or smoothing',
                     'display_significant_digits': 8,
                     'missing_values': 'null; never replaced with zero', 'research_data_replaced': False},
        'instances': instances, 'frames': frames,
    }


if __name__ == '__main__':
    from odbAccess import openOdb
    config = json.load(open(sys.argv[-1]))
    odb = openOdb(path=str(config['odb']), readOnly=True)
    try:
        result = export(odb, config)
        directory = os.path.dirname(config['output'])
        if not os.path.isdir(directory):
            os.makedirs(directory)
        with open(config['output'] + '.tmp', 'w') as stream:
            json.dump(result, stream, separators=(',', ':'), allow_nan=False)
        os.rename(config['output'] + '.tmp', config['output'])
    finally:
        odb.close()
