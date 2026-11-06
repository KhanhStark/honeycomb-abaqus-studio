# -*- coding: utf-8 -*-
from abaqus import session
from abaqusConstants import *
import visualization, displayGroupOdbToolset as dgo
import os, sys, json

cfg = json.load(open(sys.argv[-1]))
out = str(cfg["figures_directory"])
if not os.path.isdir(out):
    os.makedirs(out)
summary = json.load(open(cfg["summary"]))
odb = session.openOdb(name=str(cfg["odb"]), readOnly=True)
try:
    vp = session.viewports[session.currentViewportName]
    vp.setValues(displayedObject=odb, width=250.0, height=180.0)
    vp.odbDisplay.display.setValues(plotState=(CONTOURS_ON_DEF,))
    vp.odbDisplay.commonOptions.setValues(
        deformationScaling=UNIFORM, uniformScaleFactor=1.0, visibleEdges=FEATURE
    )
    vp.view.setValues(
        cameraPosition=(170.0, -200.0, 155.0), cameraUpVector=(0.0, 0.0, 1.0), cameraTarget=(0.0, 0.0, 10.0)
    )
    session.printOptions.setValues(vpDecorations=OFF)
    session.pngOptions.setValues(imageSize=(1400, 1000))
    vp.viewportAnnotationOptions.setValues(title=OFF, state=ON, legend=ON, compass=OFF,
        legendBackgroundStyle=OTHER,legendBackgroundColor='#FFFFFF')
    step_name = odb.steps.keys()[0]
    frames = odb.steps[step_name].frames
    targets = [
        ("peak_force", summary["peak_force_time_ms"] / 1000.0),
        ("peak_displacement", summary["max_displacement_time_ms"] / 1000.0),
        ("final", frames[-1].frameValue),
    ]
    if cfg.get("compact", True):
        targets = [targets[0], targets[-1]]
    made = []
    missing = []
    names = list(odb.rootAssembly.instances.keys())
    for label, target in targets:
        index = min(range(len(frames)), key=lambda i: abs(frames[i].frameValue - target))
        vp.odbDisplay.setFrame(step=0, frame=index)
        for var in ["U", "S", "PEEQ"]:
            if var not in frames[index].fieldOutputs.keys():
                missing.append({"field": var, "frame": index})
                continue
            kwargs = {"variableLabel": var, "outputPosition": NODAL if var == "U" else INTEGRATION_POINT}
            if var == "U":
                kwargs["refinement"] = (COMPONENT, "U3")
            if var == "S":
                kwargs["refinement"] = (INVARIANT, "Mises")
            vp.odbDisplay.setPrimaryVariable(**kwargs)
            for view in (["core"] if var in ("S", "PEEQ") else ["full"]) if cfg.get("compact", True) else ["full", "core", "top"]:
                selected = (
                    names
                    if view == "full"
                    else [n for n in names if ("CORE" if view == "core" else "TOP") in n.upper()]
                )
                vp.odbDisplay.displayGroup.replace(
                    leaf=dgo.LeafFromPartInstance(partInstanceName=tuple(selected))
                )
                vp.view.fitView()
                # Reserve annotation space; fitView alone puts the mesh behind the legend.
                vp.view.zoom(zoomFactor=0.72)
                filename = "%s_%s_%s" % (label, var, view)
                session.printToFile(fileName=os.path.join(out, filename), format=PNG, canvasObjects=(vp,))
                made.append(
                    {
                        "file": filename + ".png",
                        "field": var,
                        "view": view,
                        "frame": index,
                        "time_s": frames[index].frameValue,
                        "deformation_scale": 1.0,
                        "unit":"mm" if var=='U' else 'MPa' if var=='S' else '1',
                    }
                )
    with open(os.path.join(out, "render-manifest.json"), "w") as f:
        json.dump({"figures": made, "missing": missing}, f, indent=2)
finally:
    odb.close()
