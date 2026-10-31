from dataclasses import replace
from types import SimpleNamespace
import json

import pytest

import evaluate_v2 as evaluation
from nautilus.simulator import Experiment
from nautilus.v2_models import finding


GATES={'groups':{'common_drag':{'qualified_ambiguity_family':False},
                 'lag_deadzone':{'qualified_ambiguity_family':True}}}


def test_v2_plans_are_disjoint_and_all_cases_receive_equal_active_permissions():
    manifest=evaluation.freeze(GATES)
    assert len(manifest['plans'])==20
    assert len({p['seed'] for p in manifest['plans']})==20
    assert all(p['seed']>=900000 and p['active_assessment'] for p in manifest['plans'])
    assert sum(p['stratum']=='A' for p in manifest['plans'])==12
    assert sum(p['stratum']=='C' for p in manifest['plans'])==4
    assert sum(p['stratum']=='D' for p in manifest['plans'])==4
    assert manifest['notes']['paired_physical_indices']==tuple(range(20))
    evaluation.validate(manifest)
    manifest['active']['count_budget']=3
    with pytest.raises(ValueError,match='Manifest modified'):evaluation.validate(manifest)


def test_failed_development_gate_prevents_freeze():
    bad={'groups':{'common_drag':{'qualified_ambiguity_family':False},
                   'lag_deadzone':{'qualified_ambiguity_family':False}}}
    with pytest.raises(ValueError,match='gate failed'):evaluation.freeze(bad)


def test_normal_physical_lag_is_not_automatically_called_degradation():
    assert finding(SimpleNamespace(hypothesis='actuator_lag',parameters={'actuator_tau_s':.15}))=='nominal'
    assert finding(SimpleNamespace(hypothesis='actuator_lag',parameters={'actuator_tau_s':.7}))=='actuator_lag'


def test_fit_cache_uses_only_public_evidence_and_is_order_independent(monkeypatch):
    calls=[]
    monkeypatch.setattr(evaluation,'fit_model',lambda episodes,name: calls.append(name) or SimpleNamespace(hypothesis=name))
    a={'observations':[{'time_s':0.,'example_public':1}], 'experiment':Experiment()}
    b={'observations':[{'time_s':0.,'example_public':2}], 'experiment':Experiment()}
    cache={}
    one=evaluation.all_fits([a,b],cache);two=evaluation.all_fits([b,a],cache)
    assert one is two and len(calls)==len(evaluation.REGISTRY)


def test_checkpoint_resume_skips_only_verified_completed_cases(tmp_path,monkeypatch):
    manifest=evaluation.freeze(GATES)
    manifest['plans']=[{'case_id':f'toy-{i}','index':i,'seed':606100+i,'family':'nominal','stratum':'D','active_assessment':True} for i in range(2)]
    manifest['fingerprint']=evaluation.digest({k:v for k,v in manifest.items() if k!='fingerprint'})
    seen=[]
    monkeypatch.setattr(evaluation,'one',lambda plan,active: seen.append(plan['case_id']) or {
        **plan,'operational':'toy','expanded':{},'resolvability':'toy'})
    monkeypatch.setattr(evaluation,'aggregate',lambda records:{'toy_count':len(records)})
    evaluation.run(manifest,tmp_path,1)
    evaluation.run(manifest,tmp_path,1)
    evaluation.run(manifest,tmp_path,1)
    assert seen==['toy-0','toy-1']
    path=tmp_path/'toy-0.json';record=json.loads(path.read_text());record['seed']=0;path.write_text(json.dumps(record))
    with pytest.raises(ValueError,match='Corrupt checkpoint'):evaluation.run(manifest,tmp_path,1)


def test_private_output_guards(tmp_path):
    with pytest.raises(ValueError):evaluation.write(evaluation.ROOT/'private_oracle.json',{})
    p=tmp_path/'existing.json';evaluation.write(p,{'saved':True})
    with pytest.raises(FileExistsError):evaluation.write(p,{})
    bad=tmp_path/'invalid.json'
    with pytest.raises(ValueError):evaluation.write(bad,{'bad':float('nan')})
    assert not bad.exists()
