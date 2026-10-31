from copy import deepcopy
import pytest
import validate_laboratory as validation
from nautilus.simulator import Faults, PlantConfig
from nautilus.v2_experiments import Trial


def test_complete_investigation_repeats_with_identical_evidence(monkeypatch):
    monkeypatch.setattr(validation,'TEMPLATES',('nominal','heading_bias'))
    trial=Trial('differential_step',duration_s=4.,phase_s=1.,cruise_thrust_n=0.,differential_n=1.)
    a=validation.one(100,Faults(heading_bias_rad=-.3),PlantConfig(),trial)
    b=validation.one(100,Faults(heading_bias_rad=-.3),PlantConfig(),trial)
    assert validation.scientific(a)==validation.scientific(b)
    assert len(a['before']['evidence_refs'])==1 and len(a['after']['evidence_refs'])==2
    assert a['actions'][2]['name']==trial.name
    assert len(a['after']['fits'][0]['residual_diagnostics'])==2
    ledger=deepcopy(a['after']['history'])
    ledger[-1]['rationale']='Tampered'
    with pytest.raises(AssertionError):validation.audit(ledger)
