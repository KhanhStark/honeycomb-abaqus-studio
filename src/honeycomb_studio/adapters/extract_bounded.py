# -*- coding: utf-8 -*-
"""Abaqus Python 2.7: release native ODB caches after every bounded frame group."""
from __future__ import print_function
import json
import os
import shutil
import subprocess
import sys
import tempfile


def read(path):
    with open(path) as stream:
        return json.load(stream)


def write(path, value):
    temporary = path + '.tmp'
    with open(temporary, 'w') as stream:
        json.dump(value, stream, indent=2)
    os.rename(temporary, path)


def extract_groups(config, frames, launch, group_size=100):
    if config.get('full_fields', True) or config.get('frame_indices') is not None:
        raise ValueError('Bounded extraction requires the complete reduced-export profile')
    if frames < 1 or not 1 <= group_size <= 100:
        raise ValueError('Invalid bounded frame inventory')
    out = config['extract_directory']
    staging = tempfile.mkdtemp(prefix='bounded-extraction-', dir=out)
    state = os.path.join(staging, 'damage-state.json')
    merged = None
    sequence = 0
    for start in range(0, frames, group_size):
        stop = min(frames, start + group_size)
        part = os.path.join(staging, '%06d' % start)
        os.mkdir(part)
        child = dict(config, frame_start=start, frame_stop=stop, sequence_start=sequence,
                     metadata_directory=part, damage_state_path=state)
        child_path = os.path.join(part, 'config.json')
        write(child_path, child)
        launch(child_path)
        receipt = read(os.path.join(part, 'complete.json'))
        inventory = read(os.path.join(part, 'inventory.json'))
        if (receipt.get('complete') is not True or inventory['frames'] != stop - start
                or inventory['chunks'] != receipt['chunks'] or inventory['chunks'] < sequence):
            raise ValueError('Bounded extractor did not complete its exact frame group')
        if merged is None:
            merged = inventory
        else:
            for key in set(merged).union(inventory) - set(('fields', 'frames', 'chunks')):
                if merged.get(key) != inventory.get(key):
                    raise ValueError('ODB metadata changed between frame groups')
            merged['fields'].extend(inventory['fields'])
            merged['frames'] += inventory['frames']
            merged['chunks'] = inventory['chunks']
        sequence = inventory['chunks']
        # Histories must agree, including every original point. Mapping key
        # order may differ between independent native interpreters.
        history = os.path.join(part, 'histories.json')
        if start == 0:
            original_history = history
        else:
            if read(original_history) != read(history):
                raise ValueError('ODB histories changed between frame groups')
        print('Completed bounded ODB frames %d/%d; reader process released' % (stop, frames))
        sys.stdout.flush()
    if merged['frames'] != frames:
        raise ValueError('Incomplete bounded ODB inventory')
    shutil.copyfile(original_history, os.path.join(out, 'histories.json'))
    write(os.path.join(out, 'inventory.json'), merged)
    write(os.path.join(out, 'complete.json'), {'complete': True, 'chunks': sequence})


def main(path):
    from odbAccess import openOdb
    config = read(path)
    odb = openOdb(path=str(config['odb']), readOnly=True)
    try:
        steps = list(odb.steps.keys())
        if len(steps) != 1:
            raise ValueError('Bounded recovery requires the original single Impact step')
        frames = len(odb.steps[steps[0]].frames)
    finally:
        odb.close()
    adapter = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'extract.py')
    def launch(child_path):
        # Each native interpreter exits before the next starts; only the
        # extractor runs. No model building, data check or FE solver is admitted.
        subprocess.check_call(['/opt/SIMULIA/Commands/abaqus', 'python', adapter, child_path])
    extract_groups(config, frames, launch)


if __name__ == '__main__':
    main(sys.argv[-1])
