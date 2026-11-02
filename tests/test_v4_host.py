import json
from copy import deepcopy
import pytest
from test_v4_approval import lab,request
from test_muse_v3 import Fake,call_reply,proposal,critic
from nautilus.v4.host import Host,LIMITS
from nautilus.v4.checkpoint import load
from nautilus.v4.records import sidecar,validate,export
from nautilus.v4.policies import diagnosis
from nautilus.muse import MetaProvider,ProviderError

class Offline(Fake):offline_fixture=True


def test_suspend_resume_original_call_and_checkpoint_identity(tmp_path):
    l=lab(tmp_path)
    def generate(i,k):
        if i==1:return call_reply(i,'request_experiment',{'name':'thrust_step','params':{'duration_s':4.,'amplitude_n':0.,'phase_s':2.}})
        assert k['previous_response_id']=='response1' and k['input'][0]['call_id']=='call1'
        result=json.loads(k['input'][0]['output'])['result'];assert result['accepted'] and result['evidence_ref'] in l2.evidence_refs()
        return call_reply(i,'finalize',proposal(l2,'Actual experiment exists; no fitted cause justified.'))
    p=Offline(generate);path=tmp_path/'session.json';h=Host(l,p,critic_enabled=False,path=path)
    first=h.run();assert first['status']=='AWAITING_OPERATOR' and len(p.requests)==1 and not l._closed
    assert h.s['pending']==[] and h.s['waiting_call']=='call1' # no fabricated premature tool output
    l2,state=load(l.authority,path);l.authority._decide(first['request_id'],'approve',source='test_simulated_human')
    resumed=Host(l2,p,critic_enabled=False,path=path,state=state);assert resumed.run()['status']=='completed'
    assert len(p.requests)==2 and l2.tests==1 and len(l2.evidence_refs())==2
    with pytest.raises(ValueError,match='Stale'):h.run()
    validate(sidecar(l2),__import__('nautilus.muse_investigator',fromlist=['public_source']).public_source(l2))


def test_denied_request_continues_same_model_conversation(tmp_path):
    l=lab(tmp_path)
    def step(i,k):
        if i==1:return call_reply(i,'request_experiment',{'name':'thrust_step','params':{'duration_s':4.}})
        assert json.loads(k['input'][0]['output'])['result']['status']=='DENIED'
        assert k['input'][0]['call_id']=='call1' and k['previous_response_id']=='response1'
        return call_reply(i,'finalize',proposal(l))
    p=Offline(step);h=Host(l,p,critic_enabled=False);r=h.run();l.authority._decide(r['request_id'],'deny',source='test')
    assert h.run()['status']=='completed' and l.tests==0


def test_pair_critic_read_only_and_structured_finalization(tmp_path):
    l=lab(tmp_path,'simulation_enforced');l.joint_enabled=True
    pair='joint__lateral_current__heading_bias';l.call({'op':'propose_hypothesis','template':pair,'knobs':{},'bounds':{},'rationale':'Actual numerical fixture fit.'})
    d=diagnosis(l,pair);cp=critic(l);cp.offline_fixture=True
    def step(i,k):
        if i==1:return call_reply(i,'finalize',{'diagnosis':d,'confidence':'tentative','ambiguity_statement':'Unresolved alternatives and correlated parameters limit attribution.'})
        out=json.loads(k['input'][0]['output'])['result'];assert out['status']=='pending_critic' and not l._closed
        return call_reply(i,'finalize',{'diagnosis':d,'confidence':'tentative','ambiguity_statement':'critic:'+out['review_hash']+' I qualify this numerical pair because alternatives, missing speed and local coupling prevent unique attribution.'})
    p=Offline(step);before=deepcopy(l._reports);r=Host(l,p,critic_provider=cp).run()
    assert r['status']=='completed' and len(cp.requests)==1 and cp.requests[0]['tools']==[] and cp.requests[0]['previous_response_id'] is None
    assert l._reports==before and len(l.ledger[-1]['diagnosis']['causes'])==2
    assert all(k not in json.dumps(cp.requests) for k in ('private_results','MODEL_API_KEY','ground_truth'))
    record=__import__('nautilus.muse_investigator',fromlist=['public_source']).public_source(l);validate(sidecar(l),record)


def test_uncertain_provider_never_retried_and_live_is_blocked(tmp_path):
    l=lab(tmp_path,'simulation_enforced');p=Offline(lambda i,k:(_ for _ in ()).throw(RuntimeError('Simulated host crash after dispatch')))
    path=tmp_path/'session.json';h=Host(l,p,critic_enabled=False,path=path)
    with pytest.raises(RuntimeError):h.run()
    restored,state=load(l.authority,path)
    with pytest.raises(ValueError,match='Uncertain'):Host(restored,p,critic_enabled=False,path=path,state=state)
    assert len(p.requests)==1
    with pytest.raises(ValueError,match='admission'):Host(l,MetaProvider(model='muse-wonder-1.0',reasoning_effort='low'),critic_enabled=False)


def test_operator_stop_prevents_approved_execution(tmp_path):
    l=lab(tmp_path);p=Offline(lambda i,k:call_reply(i,'request_experiment',{'name':'thrust_step','params':{'duration_s':4.}}));h=Host(l,p,critic_enabled=False,path=tmp_path/'session.json')
    rid=h.run()['request_id'];l.authority._decide(rid,'approve',source='test');(tmp_path/'STOP').write_text('local operator stop')
    assert h.run()['status']=='stopped' and l.execution_backend.count==0 and len(p.requests)==1


def test_public_export_rejects_private_and_import_is_not_authority(tmp_path):
    l=lab(tmp_path);request(l)
    export(l,tmp_path/'record.json',tmp_path/'v4.json')
    b=json.loads((tmp_path/'v4.json').read_text());assert 'operator-authority.key' not in json.dumps(b)
    from nautilus.controller_context import canonical,fingerprint
    body=json.loads(b['body_canonical']);body['approved']=True;b['body_canonical']=canonical(body);b['hash']=fingerprint(body)
    with pytest.raises(ValueError):validate(b,json.loads((tmp_path/'record.json').read_text()))
    assert l.authority.get(l.pending)['state']=='AWAITING_OPERATOR'
