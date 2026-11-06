# -*- coding: utf-8 -*-
"""Streaming rear-face metrics from original ODB frames; Python 2.7 compatible."""
import math


def value_data(value):
    try:
        return value.dataDouble
    except Exception:
        return value.data


class RearMetrics(object):
    def __init__(self, odb):
        self.rear = next(v for k, v in odb.rootAssembly.instances.items() if k.upper() == 'BOTTOM-1')
        self.elements = dict((e.label, tuple(e.connectivity)) for e in self.rear.elements)
        self.clamps = set()
        for name, group in self.rear.nodeSets.items():
            if 'CLAMP' in name.upper():
                self.clamps.update(n.label for n in group.nodes)
        self.complete = bool(self.clamps)
        self.initial = {}
        self.rows = []
        self.deleted = set()
        self.connected = set(n.label for n in self.rear.nodes)
        self.max_raw = 0.
        self.max_corrected = 0.
        self.deletion_counts = {}

    def frame(self, frame, total_time):
        outputs = frame.fieldOutputs
        if any(name not in outputs for name in ('PEEQ', 'SDEG', 'JCCRT', 'TEMP')):
            self.complete = False
        if 'U' not in outputs:
            self.complete = False
            return
        # Abaqus 2017 Repository supports membership and indexing, not dict.get.
        status = outputs['STATUS'] if 'STATUS' in outputs else None
        if status is None:
            self.complete = False
            return
        deleted = set()
        for value in status.getSubset(region=self.rear).values:
            if float(value_data(value)) < .5:
                deleted.add(value.elementLabel)
        if deleted != self.deleted:
            adjacency = {}
            for label, nodes in self.elements.items():
                if label in deleted:
                    continue
                for node in nodes:
                    adjacency.setdefault(node, set()).update(nodes)
            visited = set(self.clamps.intersection(adjacency))
            pending = list(visited)
            while pending:
                for neighbour in adjacency[pending.pop()]:
                    if neighbour not in visited:
                        visited.add(neighbour)
                        pending.append(neighbour)
            self.connected = visited
            self.deleted = deleted
        maximum = 0.
        for value in outputs['U'].getSubset(region=self.rear).values:
            z = float(value_data(value)[2])
            if math.isnan(z) or math.isinf(z):
                self.complete = False
                continue
            self.initial.setdefault(value.nodeLabel, z)
            self.max_raw = max(self.max_raw, -z)
            if value.nodeLabel in self.connected:
                maximum = max(maximum, self.initial[value.nodeLabel] - z)
        self.max_corrected = max(self.max_corrected, maximum)
        self.rows.append({'time_s': total_time, 'rear_downward_mm': maximum,
                          'rear_deleted_elements': len(deleted)})
        for instance in ('CORE-1', 'TOP-1', 'BOTTOM-1'):
            values = [v for v in status.values if v.instance.name.upper() == instance]
            if not values:
                self.complete = False
            self.deletion_counts[instance] = max(self.deletion_counts.get(instance, 0),
                                                sum(float(value_data(v)) < .5 for v in values))

    def summary(self):
        return {'damage_fields_complete': self.complete and bool(self.rows),
                'max_rear_downward_mm': self.max_corrected,
                'max_rear_raw_downward_mm': self.max_raw,
                'rear_end_downward_mm': self.rows[-1]['rear_downward_mm'] if self.rows else None,
                'rear_skin_deleted': bool(self.deletion_counts.get('BOTTOM-1', 0)),
                'deleted_elements_by_instance': self.deletion_counts,
                'rear_measurement': 'max over time and nodes connected to clamp; U3 minus initial frame',
                'rear_frame_count': len(self.rows)}
