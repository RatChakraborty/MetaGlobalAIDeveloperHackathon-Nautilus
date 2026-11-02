from copy import deepcopy
import json
import pytest
from nautilus.simulator import simulate,Mission,Faults
from nautilus.v2_experiments import Trial
from nautilus.lab_safety import screen
from nautilus.v4.approval import Authority,Policy,AuthorizationDenied
from nautilus.v4.laboratory import V4Laboratory
from nautilus.v4.checkpoint import save,load


def lab(tmp_path,mode='simulation_operator_approved',clock=None):
    a=Authority(tmp_path,**({'clock':clock} if clock else {}));rows=simulate(faults=Faults(current_y=.4),mission=Mission(duration_s=2.,seed=407)).observations
    return V4Laboratory(rows,authority=a,policy=Policy(mode),settings={'faults':Faults(current_y=.4),'seed':407},experiment_budget=1,time_budget_s=16.,fit_budget=8,optimization_budget=16,starts=2)


def request(l):return l.call({'op':'request_experiment','name':'thrust_step','params':{'duration_s':4.,'amplitude_n':0.,'phase_s':2.}})


def test_three_modes_strict_default_and_pending(tmp_path):
    l=lab(tmp_path/'strict','simulation_enforced');r=request(l)
    assert not r['accepted'] and l.tests==0 and l.test_time_s==0 and len(l.evidence_refs())==1
    l=lab(tmp_path/'approved');r=request(l)
    assert r['status']=='AWAITING_OPERATOR' and not l._closed and l.tests==0 and l.execution_backend.count==0
    assert len(l.evidence_refs())==1
    with pytest.raises(ValueError):l.call({'op':'get_fit_report','approved':True})
    with pytest.raises(ValueError):request(l)
    a=lab(tmp_path/'advisory','simulation_advisory');r=request(a)
    assert r['accepted'] and a.tests==1 and r['execution']['mode']=='simulation_advisory'
    assert any(e['type']=='safety' and not e['screen']['accepted'] for e in a.ledger)


def test_single_use_approval_and_original_risk_survives(tmp_path):
    l=lab(tmp_path);r=request(l);rid=r['request_id'];before=deepcopy(l.ledger)
    l.authority._decide(rid,'approve',source='test_simulated_human_NOT_REAL_OPERATOR')
    result=l.resolve_operator(rid)
    assert result['accepted'] and l.tests==1 and l.test_time_s==6 and len(l.evidence_refs())==2
    assert l.ledger[:len(before)]==before and not before[-1]['screen']['accepted']
    assert result['execution']['mode']=='simulation_enforced' and result['execution']['fallback_safety']=='unverified'
    assert l.authority.get(rid)['state']=='COMPLETED'
    with pytest.raises(ValueError):l.resolve_operator(rid)
    with pytest.raises(ValueError):l.authority._decide(rid,'approve',source='duplicate')
    assert l.execution_backend.count==1


@pytest.mark.parametrize('decision,state',[('deny','DENIED'),('cancel','CANCELLED')])
def test_denial_cancel_no_observations_or_time(tmp_path,decision,state):
    l=lab(tmp_path);rid=request(l)['request_id'];l.authority._decide(rid,decision,source='test_simulated_human')
    assert l.resolve_operator(rid)['status']==state and l.tests==0 and len(l.evidence_refs())==1


def test_expiration_and_revocation(tmp_path):
    now=[10.];l=lab(tmp_path/'expired',clock=lambda:now[0]);rid=request(l)['request_id'];l.authority._decide(rid,'approve',source='test')
    now[0]=1000.;assert l.resolve_operator(rid)['status']=='EXPIRED' and l.tests==0
    l=lab(tmp_path/'revoked');rid=request(l)['request_id'];l.authority._decide(rid,'approve',source='test');l.authority._decide(rid,'cancel',source='test')
    assert l.resolve_operator(rid)['status']=='CANCELLED' and l.execution_backend.count==0


def test_forged_stale_mismatched_and_budget_bypass(tmp_path):
    l=lab(tmp_path);rid=request(l)['request_id'];t=Trial('thrust_step',duration_s=4.,amplitude_n=0.,phase_s=2.);s=screen(t)
    with pytest.raises(AuthorizationDenied):l.execution_backend.execute(t,epoch=l.epoch,budget=l.budget(),request_id=rid)
    l.authority._decide(rid,'approve',source='test')
    for kw in ({'epoch':'stale'},{'request_id':'made-up'},{'budget':{'experiments':0}}):
        args={'epoch':l.epoch,'budget':l.budget(),'request_id':rid};args.update(kw)
        with pytest.raises(AuthorizationDenied):l.execution_backend.execute(t,**args)
    with pytest.raises(AuthorizationDenied):l.execution_backend.execute(Trial('thrust_step',duration_s=6.,amplitude_n=0.,phase_s=3.),epoch=l.epoch,budget=l.budget(),request_id=rid)
    assert l.execution_backend.count==0
    l.optimization_attempts+=1
    with pytest.raises(AuthorizationDenied):l.resolve_operator(rid)
    assert l.tests==0


def test_signed_checkpoint_resume_and_duplicate_callback(tmp_path):
    l=lab(tmp_path);rid=request(l)['request_id'];path=tmp_path/'session.json';save(l,path,{'previous_response_id':'real-path-fixture','pending_call_id':'original-call'})
    restored,host=load(l.authority,path)
    assert host['pending_call_id']=='original-call' and restored.pending==rid and not restored._closed
    l.authority._decide(rid,'approve',source='test_simulated_human')
    restored.resolve_operator(rid);save(restored,path,host)
    latest,_=load(l.authority,path);assert latest.tests==1 and latest.pending is None
    with pytest.raises(AuthorizationDenied):l.resolve_operator(rid) # older callback cannot replay
    data=json.loads(path.read_text());data['data']['policy']='simulation_advisory';path.write_text(json.dumps(data))
    with pytest.raises(AuthorizationDenied):load(l.authority,path)


def test_interrupt_after_consumption_is_not_replayed(tmp_path):
    l=lab(tmp_path);rid=request(l)['request_id'];l.authority._decide(rid,'approve',source='test');t=Trial('thrust_step',duration_s=4.,amplitude_n=0.,phase_s=2.)
    l.authority.check(rid,l.session_id,l.epoch,t,screen(t),l.policy,l.budget(),consume=True)
    with pytest.raises(AuthorizationDenied):l.resolve_operator(rid)
    assert l.state=='FAILED' and l.authority.get(rid)['state']=='FAILED' and l.execution_backend.count==0


def test_no_unattended_cli_approval(tmp_path,monkeypatch):
    import os
    l=lab(tmp_path);rid=request(l)['request_id']
    monkeypatch.setattr(os,'open',lambda *a,**k:(_ for _ in ()).throw(OSError('No controlling terminal')))
    with pytest.raises(OSError):l.authority.decide_interactive(rid)
