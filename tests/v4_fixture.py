"""Genuine numerical/approval-pending fixtures; no real model or human approval."""
import tempfile
from pathlib import Path
from test_v4_approval import lab,request
from nautilus.v4.records import sidecar,validate
from nautilus.v4.policies import diagnosis
from nautilus.muse_investigator import public_source
from nautilus.controller_context import canonical

def fixture():
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp);pending=lab(root/'pending');request(pending)
        joint=lab(root/'joint','simulation_enforced');joint.joint_enabled=True
        joint.call({'op':'propose_hypothesis','template':'joint__lateral_current__heading_bias','knobs':{},'bounds':{},'rationale':'Recorded offline numerical demonstration; not a real Muse result.'})
        joint.finalize(diagnosis(joint,'joint__lateral_current__heading_bias'),'tentative','Joint numerical fit only; alternatives and confidence checks remain unresolved.')
        records={}
        for name,l in (('pending',pending),('joint',joint)):
            record=public_source(l);v4=sidecar(l);validate(v4,record);records[name]={'record':record,'v4':v4}
        return records

if __name__=='__main__':print(canonical(fixture()))
