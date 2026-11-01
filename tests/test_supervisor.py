from copy import deepcopy
from dataclasses import replace
import json

import pytest

from nautilus.controller_context import build_controller_context,controller_event,canonical,fingerprint
from nautilus.supervisor import derive_public_events,derive_visual_events,public_event_summary,validate_public_events,validate_visual_events
from nautilus.lab_safety import guarded_trial
from nautilus.simulator import Controller,Faults,PlantConfig
from nautilus.v2_experiments import parse_trial


def record(episodes,context=False,executions=None):
    ledger=[]
    def add(kind,**payload):
        body={'index':len(ledger),'type':kind,'previous_hash':ledger[-1]['hash'] if ledger else None,**payload}
        ledger.append({'hash':fingerprint(body),'body_canonical':canonical(body)})
    if context:add('controller_context',**controller_event(build_controller_context()))
    for i,rows in enumerate(episodes):add('observation',observations=rows,**({'execution':executions[i]} if executions else {}))
    return {'schema_version':'nautilus.public-investigation.v2' if context else 'nautilus.public-investigation.v1','run_id':'unit-development','source_kind':'test','disclosure':'Synthetic unit fixture, not study outcomes','recorded_conclusion':None,'ledger':ledger}


def rows(values):
    return [{'time_s':float(i),'observed_y_m':v,'observed_heading_rad':0.,'observed_yaw_rate_radps':0.,'port_command_n':0.,'starboard_command_n':0.} for i,v in enumerate(values)]


def unpack(log):return [json.loads(e['body_canonical']) for e in log['events']]


@pytest.mark.parametrize('sign',[1,-1])
def test_observed_threshold_hysteresis_and_deterministic_ids(sign):
    r=record([rows([sign*v for v in [0,.99,1.01,.99,1.02,.9,1.1]])]);a=derive_public_events(r)
    assert [e['time_s'] for e in unpack(a)]==[2.,6.]
    assert a==derive_public_events(r) and validate_public_events(a,r)==a
    assert all(e['disclosure']=='public-derived' and e['supporting_value']*sign>0 for e in unpack(a))
    assert derive_public_events(record([rows([0,.8,.99])]))['events']==[]
    assert 'not independent evidence' in public_event_summary(a,r)['scope']


def test_saturation_requires_declared_limits_and_rearms_per_signed_channel():
    sample=rows([0]*6)
    for i,v in enumerate([0,45,-45,44,45,0]):sample[i]['port_command_n']=v
    sample[2]['starboard_command_n']=-45
    r=record([sample],context=True);events=unpack(derive_public_events(r))
    assert [(e['source_field'],e['time_s']) for e in events]==[('port_command_n',1.),('starboard_command_n',2.),('port_command_n',4.)]
    assert all(e['threshold']==45 and e['units']=='N' for e in events)
    assert derive_public_events(record([sample]))['events']==[]


@pytest.mark.parametrize('execution',[None,{'mode':'simulation_advisory','guard_intervened':False,'guard_time_s':1.,'would_guard_trigger_s':1.,'stop_reason':'duration_complete'}, {'mode':'simulation_enforced','guard_intervened':False,'stop_reason':'duration_complete','elapsed_s':2.}])
def test_final_timestamp_and_advisory_warning_do_not_establish_guard_stop(execution):
    r=record([rows([0,2.,0])],executions=[execution]);assert all(e['type']!='guard_stop' for e in unpack(derive_public_events(r)))


def test_actual_simulator_guard_intervention_is_recorded_without_private_truth():
    trial=parse_trial('cable_follow',{'duration_s':8.,'cruise_thrust_n':10.})
    observed,execution,private=guarded_trial(trial,Faults(current_y=.8),PlantConfig(),Controller(),98137,noise_y=0.,mode='simulation_enforced')
    assert execution['guard_intervened']
    r=record([observed],executions=[execution]);events=unpack(derive_public_events(r));guard=next(e for e in events if e['type']=='guard_stop')
    assert guard['time_s']==execution['guard_time_s']
    assert 'true_excursion' not in json.dumps(events) and 'speed_mps' not in json.dumps(events)
    assert private['truth'] and guard['threshold'] is None


def test_multiple_reset_episodes_keep_independent_clocks_and_source_refs():
    r=record([rows([0,2]),rows([0,-2])]);log=derive_public_events(r);a,b=unpack(log)
    assert a['time_s']==b['time_s']==1. and a['episode_ref']!=b['episode_ref']
    assert (a['episode_index'],b['episode_index'])==(0,1)
    assert a['investigation_index']<b['investigation_index']
    visual={'run_id':r['run_id'],'samples':[{'time_s':0.,'x_m':0.,'y_m':0.,'heading_rad':0.},{'time_s':1.,'x_m':1.,'y_m':2.,'heading_rad':0.}], 'reference':{'cable_length_m':110.,'cable_half_width_m':1.5,'source':'unit'}}
    with pytest.raises(ValueError):derive_visual_events(r,visual)
    result=derive_visual_events(r,visual,b['episode_ref']);assert result['episode_ref']==b['episode_ref']


def test_truth_breaches_stay_separate_and_tampering_fails():
    r=record([rows([0,.1,.2,.1])]);visual={'run_id':r['run_id'],'samples':[{'time_s':float(i),'x_m':float(i),'y_m':y,'heading_rad':0.} for i,y in enumerate([0,2,2,0])], 'reference':{'cable_length_m':110.,'cable_half_width_m':1.5,'source':'unit'}}
    public=derive_public_events(r);truth=derive_visual_events(r,visual)
    assert public['events']==[] and len(truth['events'])==1
    assert unpack(truth)[0]['disclosure']=='visualization-only'
    assert validate_visual_events(truth,r,visual)==truth
    bad=deepcopy(public);bad['extra_private']={}
    with pytest.raises(ValueError):validate_public_events(bad,r)
    bad=deepcopy(truth);bad['events'][0]['id']='0'*64
    with pytest.raises(ValueError):validate_visual_events(bad,r,visual)
    bad=deepcopy(visual);bad['samples'][1]['y_m']=3.
    with pytest.raises(ValueError):validate_visual_events(truth,r,bad)
    bad=deepcopy(r);body=json.loads(bad['ledger'][0]['body_canonical']);body['observations'][0]['x_m']=3
    bad['ledger'][0]={'hash':fingerprint(body),'body_canonical':canonical(body)}
    with pytest.raises(ValueError):derive_public_events(bad)


def test_invalid_guard_clock_and_nonfinite_rules_rejected():
    r=record([rows([0,2])],executions=[{'mode':'simulation_enforced','guard_intervened':True,'stop_reason':'observed_guard','guard_time_s':.5}])
    with pytest.raises(ValueError):derive_public_events(r)
    from nautilus.supervisor import RULES
    with pytest.raises(ValueError):derive_public_events(record([rows([0,0])]),{**RULES,'warning_m':float('nan')})
