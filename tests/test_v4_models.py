from dataclasses import asdict
from copy import deepcopy
import numpy as np
import pytest
from nautilus.simulator import Mission,Experiment,simulate
from nautilus.v2_models import REGISTRY,configs
from nautilus.v4.models import compose,PAIRS,fit_pair,assess
from nautilus.v4.laboratory import V4Laboratory


def specification(names,values):return {'schema_version':'nautilus.physical-composition.v4','components':[{'mechanism':n,'value':v} for n,v in zip(names,values)]}


@pytest.mark.parametrize('name',list(REGISTRY))
def test_single_composition_exact_legacy_config_and_telemetry(name):
    spec=REGISTRY[name];v=sum(spec.bounds)/2 if spec.parameter else None
    actual=compose(specification([name],[v]));expected=configs(name,v)
    assert actual==expected
    a=simulate(faults=actual[0],plant=actual[1],controller=actual[2],mission=Mission(duration_s=1.,seed=450))
    b=simulate(faults=expected[0],plant=expected[1],controller=expected[2],mission=Mission(duration_s=1.,seed=450))
    assert a.observations==b.observations


def test_invalid_duplicate_overlapping_and_triple_specs():
    for names,values in [(['lateral_current']*2,[.2,.3]),(['port_degradation','common_thrust_scale'],[.4,.7]),(['lateral_current'],[float('nan')]),(['lateral_current','heading_bias','actuator_lag'],[.2,.2,.2])]:
        with pytest.raises(ValueError):compose(specification(names,values))


def test_actual_joint_fit_convergence_reproducibility_and_diagnostics():
    names=['lateral_current','port_degradation'];values=[.35,.55];f,p,c=compose(specification(names,values));ex=Experiment(maneuver='differential_step',duration_s=6.,cruise_thrust_n=3.,differential_n=.7,phase_s=2.)
    rows=simulate(faults=f,plant=p,controller=c,mission=Mission(duration_s=6.,seed=460),experiment=ex).observations
    episodes=[{'observations':rows,'experiment':ex}];name=next(n for n,v in PAIRS.items() if v['components']==names)
    a,d=fit_pair(episodes,name);b,e=fit_pair(episodes,name)
    assert a['converged'] and a['parameters']==b['parameters'] and a['penalized_score']==b['penalized_score']
    assert abs(a['parameters']['current_y']-.35)<.12 and abs(a['parameters']['port_efficiency']-.55)<.2
    assert d['rank']==2 and len(d['local_sensitivity_matrix'][0])==2
    assert d['starts']==2 and a['optimization_attempts']==4
    assert d['conditional_correlation'] is not None and 'early_mean' in d['residuals'][0][0]
    assert np.allclose(np.linalg.norm(d['local_sensitivity_matrix'],axis=0),np.linalg.norm(e['local_sensitivity_matrix'],axis=0))


def test_zero_excitation_rank_deficiency_not_causal_support():
    ex=Experiment(maneuver='thrust_step',duration_s=4.,amplitude_n=0.,phase_s=2.)
    rows=simulate(mission=Mission(duration_s=4.,seed=470),experiment=ex).observations
    pair='joint__lateral_current__port_degradation';a,d=fit_pair([{'observations':rows,'experiment':ex}],pair)
    assert d['rank']<2 and d['conditional_correlation'] is None
    a['evidence_refs']=['actual'];result=assess(pair,{pair:a},{pair:d},['actual'])
    assert not result['checks']['local_rank'] and not result['checks']['alternatives_complete']


def test_pair_budget_cost_and_structured_validation():
    rows=simulate(mission=Mission(duration_s=2.,seed=480)).observations
    l=V4Laboratory(rows,joint_enabled=True,optimization_budget=3,fit_budget=4)
    pair='joint__lateral_current__heading_bias'
    with pytest.raises(ValueError):l.call({'op':'propose_hypothesis','template':pair,'knobs':{},'bounds':{},'rationale':'Requires four units for two starts.'})
    assert l.fit_calls==0 and l.optimization_attempts==0
    l=V4Laboratory(rows,joint_enabled=True,optimization_budget=16,fit_budget=8)
    l.call({'op':'propose_hypothesis','template':pair,'knobs':{},'bounds':{},'rationale':'Genuine development joint numerical fit.'})
    assert l.fit_calls==1 and l.optimization_attempts==4
    f=l._reports[pair];components=PAIRS[pair]['components']
    diagnosis={'schema_version':'nautilus.diagnosis.v4','hypothesis':pair,'causes':[{'mechanism':n,'parameters':{REGISTRY[n].parameter:f['parameters'][REGISTRY[n].parameter]},'evidence_status':'tentative'} for n in components],'relationship':'joint','unresolved_sets':[['nominal']],'unexplained_residual':True,'qualification':'Numerical evidence only; alternatives incomplete.','evidence_refs':l.evidence_refs()}
    with pytest.raises(ValueError):l.validate_finalization(diagnosis,'supported','Cannot claim support without simpler alternatives and rank checks.')
    bad=deepcopy(diagnosis);bad['causes'][0]['parameters']['current_y']+=.01
    with pytest.raises(ValueError):l.validate_finalization(bad,'tentative','Never alter numerical estimates.')
    a=l.finalize(diagnosis,'tentative','Acknowledge uncertain attribution and missing alternatives.')
    assert len(a['diagnosis']['causes'])==2 and l._closed
