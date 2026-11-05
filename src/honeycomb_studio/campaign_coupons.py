"""Small shell material tests using the identical production keyword adapter."""
from pathlib import Path

from .adapters.damage_keywords import rewrite_input
from .campaign import reference_model
from .models import digest

CASES = {"tension": (1, 3.), "compression": (1, -.85), "shear": (2, 5.)}


def write_coupon(directory: Path, case: str):
    """Prescribed 1-mm S4R patch in mm-tonne-s. This checks implementation, not calibration."""
    component, displacement = CASES[case]
    directory.mkdir(parents=True, exist_ok=True)
    model = reference_model()
    c = model.core_material
    deck = directory / (case + ".inp")
    # Uniform simple shear prescribes horizontal displacement on the top edge.
    moving, fixed = ("TOP", "BOTTOM") if case == "shear" else ("RIGHT", "LEFT")
    dof = 1 if component == 2 else component
    lateral = "LEFT,2,2\n" if case != "shear" else "ALL,2,2\n"
    deck.write_text(
        "*Heading\nCore-damage-v2 material implementation test: " + case + "\n"
        "*Node\n1,0,0,0\n2,1,0,0\n3,1,1,0\n4,0,1,0\n"
        "*Element,type=S4R,elset=PATCH\n1,1,2,3,4\n"
        "*Nset,nset=ALL\n1,2,3,4\n*Nset,nset=SANDWICH_NODES\n1,2,3,4\n"
        "*Nset,nset=LEFT\n1,4\n*Nset,nset=RIGHT\n2,3\n"
        "*Nset,nset=TOP\n3,4\n*Nset,nset=BOTTOM\n1,2\n"
        "*Shell Section,elset=PATCH,material=REF\n1.,5\n"
        "*Material,name=REF\n*Density\n2.7e-9\n*Elastic\n70000,.33\n*Plastic\n324,0\n"
        "*Boundary\nALL,3,6\n" + fixed + ",1,1\n" + lateral +
        "*Amplitude,name=RAMP,definition=SMOOTH STEP\n0.,0.,.001,1.\n"
        "*Step,name=Coupon,nlgeom=YES\n*Dynamic,Explicit\n,.001\n"
        "*Boundary,amplitude=RAMP\n" + moving + "," + str(dof) + "," + str(dof) + "," + str(displacement) + "\n"
        "*Output,field,number interval=400\n*Element Output\nS,PEEQ,STATUS,SDEG,DMICRT,TEMP\n"
        "*Node Output\nU,RF\n*Output,history,time interval=.0000025\n"
        "*Energy Output\nALLIE,ALLPD,ALLDMD,ALLAE,ALLKE,ALLWK,ETOTAL\n*End Step\n",
        encoding="ascii")
    rewrite_input(str(deck), model.resolved(), {"REF": c.model_dump()})
    return {"case": case, "material_hash": digest(c.model_dump()), "deck": str(deck),
            "purpose": "implementation-only; not physical calibration"}
