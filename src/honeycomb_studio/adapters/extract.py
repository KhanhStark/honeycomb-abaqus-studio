# -*- coding: utf-8 -*-
"""Abaqus Python 2.7: abaqus python extract.py config.json.

Producer writes bounded numeric NPZ chunks and publishes .ready JSON atomically.
The modern engine consumes each chunk into Parquet while this process continues.
Never imports pyarrow, opens the ODB read-only, never mutates the supplied model.
"""

from __future__ import print_function
from odbAccess import openOdb
import os, sys, json, math, time
import numpy as np
import zipfile
from cStringIO import StringIO


def dump(path, obj):
    temp = path + ".tmp"
    with open(temp, "w") as f:
        json.dump(obj, f, indent=2)
    if os.path.exists(path):
        os.remove(path)
    os.rename(temp, path)


def attr(obj, key, default=None):
    try:
        value = getattr(obj, key)
        return default if value is None else value
    except Exception:
        return default


def numeric(value, key="data"):
    data = attr(value, key + "Double")
    if data is None:
        data = attr(value, key)
    if data is None:
        return None
    if np.isscalar(data):
        return [float(data)]
    return [float(x) for x in data]


def publish(spool, sequence, kind, arrays, meta):
    base = os.path.join(spool, "%08d" % sequence)
    # NumPy 1.6 savez creates a disk tempfile per array before adding it to ZIP.
    # Write NPY members in memory instead: same portable format, bounded buffers,
    # drastically fewer file opens on Windows, no object pickle payloads.
    with zipfile.ZipFile(base + ".npz",'w',zipfile.ZIP_STORED,allowZip64=True) as bundle:
        for key,array in arrays.items():
            array=np.asarray(array)
            if array.dtype.hasobject:raise ValueError('Object arrays are forbidden')
            buffer=StringIO()
            np.lib.format.write_array(buffer,array)
            bundle.writestr(key+'.npy',buffer.getvalue())
            buffer.close()
    meta.update({"kind": kind, "sequence": sequence, "npz": os.path.basename(base) + ".npz"})
    dump(base + ".ready", meta)
    # Backpressure bounds temporary disk footprint when Parquet writing is slower.
    while len([n for n in os.listdir(spool) if n.endswith(".ready")]) > 8:
        time.sleep(0.1)


def bulk_field(blocks, meta, spool, sequence, chunk_size, instance_lookup):
    """Vectorized single precision; retain Abaqus native quaternion orientation."""
    pending = []; pending_rows = 0; start = 0; sections = {}
    def labels(raw, n):
        if raw is None or len(raw) == 0: return np.ones(n, dtype=np.int64)*-1
        arr = np.asarray(raw, dtype=np.int64)
        if len(arr) == n: return arr
        if n % len(arr): raise ValueError('Bulk label count is inconsistent')
        return np.repeat(arr, n//len(arr))
    def flush(parts, current, offset):
        arrays = dict((k,np.concatenate([p[k] for p in parts],axis=0)) for k in parts[0])
        publish(spool,current,'field',arrays,dict(meta,section_points=dict(sections),start_row=offset,orientation_representation='native Abaqus quaternion (bulk), 3x3 basis (FieldValue)'))
        return current+1
    for block in blocks:
        data = np.asarray(block.data,dtype=np.float64)
        if data.ndim == 1: data = data.reshape((-1,1))
        n = len(data)
        if not n: continue
        section = attr(block,'sectionPoint'); section_no = attr(section,'number',-1)
        if section is not None: sections[str(section_no)] = attr(section,'description','')
        basis = attr(block,'localCoordSystem'); imag = attr(block,'conjugateData')
        if imag is None or not len(imag): imag = np.ones(data.shape)*float('nan')
        else: imag = np.asarray(imag,dtype=np.float64).reshape(data.shape)
        mises = attr(block,'mises') if meta['field'] == 'S' else None
        nodes = labels(attr(block,'nodeLabels'),n); elements = labels(attr(block,'elementLabels'),n); ips = labels(attr(block,'integrationPoints'),n)
        for offset in range(0,n,chunk_size):
            end = min(n,offset+chunk_size); count = end-offset
            arrays = {
                'instance_index':np.ones(count,dtype=np.int32)*instance_lookup.get(attr(attr(block,'instance'),'name',''),-1),
                'node_label':nodes[offset:end], 'element_label':elements[offset:end],
                'integration_point':ips[offset:end], 'section_point':np.ones(count,dtype=np.int32)*section_no,
                'position':np.array([str(block.position)]*count,dtype='U32'),
                'data':data[offset:end].copy(), 'conjugate_data':imag[offset:end].copy(),
                'local_basis':np.ones((count,9))*float('nan'),
                'local_quaternion':np.asarray(basis[offset:end],dtype=np.float64).copy() if basis is not None and len(basis) else np.ones((count,4))*float('nan'),
                'mises':np.asarray(mises[offset:end],dtype=np.float64).copy() if mises is not None and len(mises) else np.ones(count)*float('nan')
            }
            pending.append(arrays); pending_rows += count
            if pending_rows >= chunk_size:
                sequence = flush(pending,sequence,start); start += pending_rows; pending = []; pending_rows = 0
    if pending: sequence = flush(pending,sequence,start)
    return sequence


def run(config):
    out = config["extract_directory"]
    if not os.path.isdir(out):
        os.makedirs(out)
    spool = os.path.join(out, "spool")
    if not os.path.isdir(spool):
        os.makedirs(spool)
    odb = openOdb(path=str(config["odb"]), readOnly=True)
    try:
        damage_metrics = None
        if config.get('damage_metrics'):
            from damage_metrics import RearMetrics
            damage_metrics = RearMetrics(odb)
        sequence = 0
        instances = list(odb.rootAssembly.instances.keys())
        instance_lookup = dict((name, i) for i, name in enumerate(instances))
        inventory = {
            "schema_version": "1",
            "export_profile": "full_fields" if config.get("full_fields", True) else "research_reduced",
            "odb_version": str(odb.jobData.version),
            "instances": instances,
            "steps": [],
            "fields": [],
            "sets": {},
            "sections": {},
            "frames": 0,
        }
        for name in instances:
            inst = odb.rootAssembly.instances[name]
            if not config.get("full_fields", True):
                inventory.setdefault("mesh_counts", {})[name] = {"nodes": len(inst.nodes), "elements": len(inst.elements)}
                continue
            labels = np.array([n.label for n in inst.nodes], dtype=np.int64)
            xyz = np.array([n.coordinates for n in inst.nodes], dtype=np.float64)
            publish(
                spool,
                sequence,
                "nodes",
                {"label": labels, "x": xyz[:, 0], "y": xyz[:, 1], "z": xyz[:, 2]},
                {"instance": name},
            )
            sequence += 1
            # Store connectivity as JSON strings: preserves arbitrary element topology.
            publish(
                spool,
                sequence,
                "elements",
                {
                    "label": np.array([e.label for e in inst.elements], dtype=np.int64),
                    "element_type": np.array([e.type for e in inst.elements], dtype="U32"),
                    "connectivity": np.array([json.dumps(list(e.connectivity)) for e in inst.elements]),
                },
                {"instance": name},
            )
            sequence += 1
            inventory["sets"][name] = {"nodes": {}, "elements": {}, "section_assignments": []}
            for k, ns in inst.nodeSets.items():
                inventory["sets"][name]["nodes"][k] = [n.label for n in ns.nodes]
            for k, es in inst.elementSets.items():
                inventory["sets"][name]["elements"][k] = [e.label for e in es.elements]
            for assignment in inst.sectionAssignments:
                inventory["sets"][name]["section_assignments"].append(
                    {
                        "section": assignment.sectionName,
                        "region": attr(assignment.region, "name", ""),
                        "elements": [e.label for e in assignment.region.elements],
                    }
                )
        for name, section in odb.sections.items():
            inventory["sections"][name] = {
                "type": str(type(section)),
                "material": attr(section, "material"),
                "thickness": attr(section, "thickness"),
                "integration_rule": str(attr(section, "integrationRule")),
                "integration_points": attr(section, "numIntPts"),
            }
        # Assembly sets may span instances and must not lose the instance labels.
        inventory["assembly_sets"] = {"nodes": {}, "elements": {}}
        for category, repo in ([] if not config.get("full_fields", True) else [
            ("nodes", odb.rootAssembly.nodeSets),
            ("elements", odb.rootAssembly.elementSets),
        ]):
            for name, region in repo.items():
                groups = getattr(region, category)
                if groups and not isinstance(groups[0], (list, tuple)) and hasattr(groups[0], "label"):
                    groups = [groups]
                inventory["assembly_sets"][category][name] = [
                    [{"instance": attr(v, "instanceName", ""), "label": v.label} for v in group]
                    for group in groups
                ]
        histories = []
        chunk_size = int(config.get("chunk_size", 12000))
        for step_name, step in odb.steps.items():
            inventory["steps"].append(
                {
                    "name": step_name,
                    "time_period": step.timePeriod,
                    "total_time": step.totalTime,
                    "frames": len(step.frames),
                }
            )
            for region_name, region in step.historyRegions.items():
                for variable, series in region.historyOutputs.items():
                    histories.append(
                        {
                            "step": step_name,
                            "region": region_name,
                            "variable": variable,
                            "description": series.description,
                            "data": list(series.data),
                        }
                    )
            for frame_index, frame in enumerate(step.frames):
                if damage_metrics is not None:
                    damage_metrics.frame(frame, step.totalTime + frame.frameValue)
                if config.get("frame_indices") is not None and frame_index not in config["frame_indices"]:
                    continue
                for field_name, field in frame.fieldOutputs.items():
                    if not config.get("full_fields", True) and field_name not in ("U", "S", "PEEQ") and not field_name.startswith(("CNORMF", "CSHEARF")):
                        continue
                    meta = {
                        "step": step_name,
                        "frame": frame_index,
                        "time_s": frame.frameValue,
                        "field": field_name,
                        "description": field.description,
                        "components": list(field.componentLabels),
                        "type": str(field.type),
                        "instances": instances,
                        "locations": [str(x.position) for x in field.locations],
                        "valid_invariants": [str(v) for v in field.validInvariants],
                    }
                    # Avoid materializing FieldValueArray even for len().
                    blocks=list(field.bulkDataBlocks)
                    try:
                        row_count=sum(len(block.data) for block in blocks)
                    except Exception:
                        blocks=None;row_count=len(field.values)
                    inventory["fields"].append(dict(meta, rows=row_count))
                    if blocks is not None:
                        sequence = bulk_field(blocks,meta,spool,sequence,chunk_size,instance_lookup)
                        continue
                    for start in range(0, len(field.values), chunk_size):
                        sequence_values = field.values
                        values = [
                            sequence_values[i]
                            for i in range(start, min(start + chunk_size, len(sequence_values)))
                        ]
                        if not values:
                            continue
                        data = [numeric(v) for v in values]
                        components = len(data[0])
                        local = []
                        for v in values:
                            basis = attr(v, "localCoordSystemDouble")
                            if basis is None:
                                basis = attr(v, "localCoordSystem")
                            local.append([x for row in basis for x in row] if basis is not None and len(basis) else [float("nan")] * 9)
                        sections = {}
                        for v in values:
                            sp = attr(v, "sectionPoint")
                            if sp:
                                sections[str(sp.number)] = sp.description
                        arrays = {
                            "instance_index": np.array(
                                [
                                    instance_lookup.get(attr(attr(v, "instance"), "name", ""), -1)
                                    for v in values
                                ],
                                dtype=np.int32,
                            ),
                            "node_label": np.array(
                                [attr(v, "nodeLabel", -1) for v in values], dtype=np.int64
                            ),
                            "element_label": np.array(
                                [attr(v, "elementLabel", -1) for v in values], dtype=np.int64
                            ),
                            "integration_point": np.array(
                                [attr(v, "integrationPoint", -1) for v in values], dtype=np.int32
                            ),
                            "section_point": np.array(
                                [attr(attr(v, "sectionPoint"), "number", -1) for v in values], dtype=np.int32
                            ),
                            "position": np.array([str(v.position) for v in values], dtype="U32"),
                            "data": np.array(data, dtype=np.float64),
                            "conjugate_data": np.array(
                                [numeric(v, "conjugateData") or [float("nan")] * components for v in values],
                                dtype=np.float64,
                            ),
                            "local_basis": np.array(local, dtype=np.float64),
                            "local_quaternion": np.ones((len(values),4))*float('nan'),
                            "mises": np.array(
                                [
                                    attr(v, "mises", float("nan")) if field_name == "S" else float("nan")
                                    for v in values
                                ],
                                dtype=np.float64,
                            ),
                        }
                        publish(
                            spool,
                            sequence,
                            "field",
                            arrays,
                            dict(meta, section_points=sections, start_row=start),
                        )
                        sequence += 1
                inventory["frames"] += 1
                dump(
                    os.path.join(out, "progress.json"),
                    {
                        "step": step_name,
                        "frame": frame_index,
                        "frames_total": len(step.frames),
                        "time_s": frame.frameValue,
                        "chunks": sequence,
                    },
                )
        if damage_metrics is not None:
            dump(os.path.join(out, 'damage-summary.json'), damage_metrics.summary())
            dump(os.path.join(out, 'rear-field-history.json'), damage_metrics.rows)
        dump(os.path.join(out, "histories.json"), histories)
        inventory["chunks"] = sequence
        dump(os.path.join(out, "inventory.json"), inventory)
        dump(os.path.join(out, "complete.json"), {"complete": True, "chunks": sequence})
    finally:
        odb.close()


if __name__ == "__main__":
    run(json.load(open(sys.argv[-1])))
