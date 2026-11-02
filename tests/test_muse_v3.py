import json
from copy import deepcopy
from dataclasses import replace
from unittest.mock import patch
import pytest
from nautilus.simulator import simulate,Mission,Faults
from nautilus.lab_safety import screen,SafeBackend,guarded_trial
from nautilus.v2_experiments import Trial
from nautilus.controller_context import canonical,fingerprint,initialize_controller_context,build_controller_context
from nautilus.muse import Reply,ProviderError
from nautilus.muse_investigator import Limits,run as legacy_run,validate_provenance
from nautilus.muse_v3 import Flags,make_lab,run,V3_LIMITS,validate_v3
from nautilus.muse_critic import validate_review,packet,review
from nautilus.active_planner import candidates,safety_audit,plan,separation,trajectories


def laboratory(flags=Flags(),faults=Faults()):
    rows=simulate(faults=faults,mission=Mission(duration_s=2.,seed=555)).observations
    lab=make_lab(rows,flags=flags,backend_settings={'faults':faults,'seed':555},fit_budget=8,optimization_budget=16,experiment_budget=1,time_budget_s=16,starts=2)
    initialize_controller_context(lab,build_controller_context());return lab


def fit(lab,name='nominal'):
    return lab.call({'op':'propose_hypothesis','template':name,'knobs':{},'bounds':{},'rationale':'Offline fixture actual numerical fit'})


def proposal(lab,reason='Evidence is limited; abstention preserves uncertainty.',name=None,confidence='abstain'):
    return {'diagnosis':{'hypothesis':name,'evidence_refs':lab.evidence_refs()},'confidence':confidence,'ambiguity_statement':reason}


def review_value(lab):
    return {'severity':'high','evidence_refs':lab.evidence_refs(),'strongest_competing_explanation':'An untested competing singleton may remain.',
      'unsupported_claims':[],'stale_evidence_concerns':[],'confidence_concerns':['No independent identifiability reference.'],
      'recommendation':'qualify','rationale':'Available channels do not include surge speed; distinguish numerical fit from cause.'}


class Fake:
    provider='meta';model='muse-wonder-1.0';reasoning_effort='low'
    def __init__(self,fn):self.fn=fn;self.requests=[]
    def generate(self,**kwargs):
        self.requests.append(deepcopy(kwargs));return self.fn(len(self.requests),kwargs)


def call_reply(i,name,args):
    return Reply('response'+str(i),'muse-wonder-1.0',[{'type':'function_call','call_id':'call'+str(i),'name':name,'arguments':canonical(args)}],{'input_tokens':100,'output_tokens':30,'reasoning_tokens':5},.01,'completed',200,reasoning_effort='low')


def critic(lab,value=None):
    value=review_value(lab) if value is None else value
    return Fake(lambda i,k:Reply('critic1','muse-wonder-1.0',[{'type':'message','content':[{'type':'output_text','text':canonical(value)}]}],{'input_tokens':120,'output_tokens':80,'reasoning_tokens':10},.02,'completed',200,reasoning_effort='low'))


def test_finite_reproducible_original_screen():
    a=safety_audit();assert a==safety_audit();assert a['generated']==36 and a['ensemble_size']==15
    assert a['accepted']==0 and a['rejected']==36
    for t,r in zip(candidates(),a['rows']):
        assert r['screen']==screen(t)
        assert r['predictive_margin_m']==pytest.approx(r['screen']['limit_m']-r['screen']['ensemble_max_y_m']-.14)


def test_rejection_never_executes_observes_or_consumes_time():
    lab=laboratory();before=len(lab.evidence_refs())
    with patch('nautilus.lab_safety.guarded_trial',wraps=guarded_trial) as execution:
        # Screen uses guarded_trial; backend.execute must never be called by lab.
        with patch.object(lab,'_execute',side_effect=AssertionError('Rejected execution')):
            for _ in range(4):
                r=lab.call({'op':'request_experiment','name':'thrust_step','params':{'duration_s':4.,'amplitude_n':0.,'phase_s':2.}})
                assert not r['accepted'] and r['constraint']=='predictive_envelope'
    assert len(lab.evidence_refs())==before and lab.tests==0 and lab.test_time_s==0
    assert lab._backend.private_results==[]
    assert len([x for x in lab.ledger if x['type']=='safety'])==4


@pytest.mark.parametrize('params',[{'duration_s':1.},{'amplitude_n':float('nan')},{'override':True},{'phase_s':0.}])
def test_malformed_never_executes(params):
    lab=laboratory()
    with pytest.raises(ValueError):lab.call({'op':'request_experiment','name':'thrust_step','params':params})
    assert lab.tests==0 and lab._backend.private_results==[] and len(lab.evidence_refs())==1


def test_accepted_branch_monitors_and_preserves_adverse_outcome():
    # Deliberate test-only accepted screen exercises downstream monitor; not a real feasibility claim.
    lab=laboratory(faults=Faults(current_y=.65));accepted={**screen(Trial('thrust_step')),'accepted':True}
    with patch('nautilus.laboratory.screen',return_value=accepted),patch('nautilus.lab_safety.screen',return_value=accepted):
        r=lab.call({'op':'request_experiment','name':'thrust_step','params':{'duration_s':4.,'amplitude_n':0.,'phase_s':2.}})
    assert r['accepted'] and r['execution']['mode']=='simulation_enforced'
    assert r['execution']['guard_intervened'] and r['execution']['fallback_safety']=='unverified'
    assert r['execution']['observed_excursion'] and r['execution']['observed_max_y_m']>1.5
    assert lab.tests==1 and lab.test_time_s==6 and len(lab.evidence_refs())==2


def test_forecast_is_public_pure_aligned_and_stale_aware():
    lab=laboratory();fit(lab);fit(lab,'lateral_current');r=lab.get_fit_report()
    # Guarantee a competitive public fixture without accessing hidden fields.
    for f in r['fits']:f['penalized_score']=1.;f['bound_hits']=[]
    from nautilus.active_planner import current_fits
    assert len(current_fits(r))==2
    rows=trajectories(current_fits(r),candidates()[0]);d=separation(rows)
    assert len(d['pairs'])==1 and d['minimum']>=0
    with patch.object(lab._backend,'execute',side_effect=AssertionError('Counterfactual touched plant')):
        p=plan(r)
    assert p['recommended_ids']==[] and p['status']=='no_safe_informative_candidate' and p['forward_simulations']==72
    assert 'No surge-speed/x channel' in p['qualification']
    stale=deepcopy(r);stale['fits'][0]['evidence_refs']=[]
    assert len(current_fits(stale))==1
    assert plan(stale)['forward_simulations']==0
    bad=deepcopy(rows);next(iter(bad.values()))[1]['time_s']+=.01
    with pytest.raises(ValueError):separation(bad)


def test_legacy_off_exact_ledgers_and_requests():
    flags=Flags.legacy();left=laboratory(flags);right=laboratory(flags)
    p=Fake(lambda i,k:call_reply(i,'finalize',proposal(left)))
    q=Fake(lambda i,k:call_reply(i,'finalize',proposal(right)))
    a=legacy_run(left,p);b=run(right,q,flags=flags)
    assert a['public_record']==b['public_record'] and p.requests==q.requests
    v=validate_v3(b['v3_provenance'],b['public_record'],b['provenance'])
    assert not any(v['flags'].values()) and v['events']==[] and v['critic'] is None


def test_pending_critic_continuation_finalizes_without_reopening():
    lab=laboratory();cp=critic(lab)
    def invoke(i,k):
        if i==1:return call_reply(i,'propose_hypothesis',{'template':'nominal','knobs':{},'bounds':{},'rationale':'Fit genuine initial observations.'})
        if i==2:return call_reply(i,'finalize',proposal(lab))
        assert not lab._closed and k['previous_response_id']=='response2'
        out=json.loads(k['input'][0]['output'])
        assert k['input'][0]['call_id']=='call2' and out['result']['status']=='pending_critic' and not out['result']['finalized']
        marker=out['result']['required_response_marker']
        return call_reply(i,'finalize',proposal(lab,marker+' I retain abstention because missing channels and untested alternatives prevent attribution.'))
    ip=Fake(invoke);result=run(lab,ip,critic_provider=cp)
    assert len(cp.requests)==1 and cp.requests[0]['tools']==[] and cp.requests[0]['previous_response_id'] is None
    assert cp.requests[0]['max_output_tokens']==2048
    assert lab._closed and len([e for e in lab.ledger if e['type']=='finalized'])==1
    body=validate_v3(result['v3_provenance'],result['public_record'],result['provenance'])
    assert body['critic']['status']=='validated' and not body['critic_failure']
    assert [json.loads(x['body_canonical'])['kind'] for x in body['events']].count('pending_finalization')==1
    assert all(x not in canonical(cp.requests) for x in ('private_results','ground_truth','injected','MODEL_API_KEY'))


def test_failed_critic_stops_once_and_host_abstains():
    lab=laboratory();cp=Fake(lambda i,k:(_ for _ in ()).throw(ProviderError('http_400')))
    p=Fake(lambda i,k:call_reply(i,'finalize',proposal(lab)))
    r=run(lab,p,critic_provider=cp)
    b=validate_v3(r['v3_provenance'],r['public_record'],r['provenance'])
    assert b['critic_failure'] and b['critic']['error']=='http_400' and len(p.requests)==len(cp.requests)==1
    assert validate_provenance(r['provenance'],r['public_record'])['finalization_origin']=='host'


@pytest.mark.parametrize('field,value',[('evidence_refs',['madeup']),('severity','critical'),('recommendation','execute'),('extra','forbidden')])
def test_critic_schema_rejects(field,value):
    lab=laboratory();v=review_value(lab);v[field]=value
    with pytest.raises(ValueError):validate_review(v,lab.evidence_refs())


def test_finalization_validation_is_nonmutating():
    lab=laboratory();before=deepcopy(lab.ledger)
    with pytest.raises(ValueError):lab.validate_finalization(**proposal(lab,name='nominal',confidence='supported'))
    assert not lab._closed and lab.ledger==before
    fit(lab);lab.validate_finalization(**proposal(lab,name='nominal',confidence='tentative'))
    assert not lab._closed


def test_no_critic_response_marker_host_terminates_bounded():
    lab=laboratory();cp=critic(lab);ip=Fake(lambda i,k:call_reply(i,'finalize',proposal(lab)))
    r=run(lab,ip,critic_provider=cp)
    assert len(ip.requests)==3 and len(cp.requests)==1
    b=validate_provenance(r['provenance'],r['public_record']);assert b['finalization_origin']=='host'


def test_repeated_rejections_action_bound():
    lab=laboratory();ip=Fake(lambda i,k:call_reply(i,'request_experiment',{'name':'thrust_step','params':{'duration_s':4.}}))
    flags=Flags(False,True,False,False)
    r=run(lab,ip,flags=flags,limits=replace(V3_LIMITS,actions=3))
    assert len(ip.requests)==3 and lab.tests==0 and lab.test_time_s==0
    assert validate_provenance(r['provenance'],r['public_record'])['termination_reason']=='action_limit'


def test_mode_and_flag_validation():
    with pytest.raises(ValueError):Flags(risk_aware_planning=1)
    with pytest.raises(ValueError):run(laboratory(Flags.legacy()),Fake(None))
    with pytest.raises(ValueError):make_lab([],backend_settings={'mode':'simulation_advisory'})

@pytest.mark.parametrize('flags',[Flags.legacy(),Flags(True,True,False,True),Flags(False,False,True,False),Flags()])
def test_four_predeclared_ablation_flags(flags):
    lab=laboratory(flags);cp=critic(lab)
    def step(i,k):
        if i==1:return call_reply(i,'finalize',proposal(lab))
        out=json.loads(k['input'][0]['output'])['result']
        return call_reply(i,'finalize',proposal(lab,out['required_response_marker']+' I retain scientific abstention because alternatives remain untested and confidence is limited.'))
    ip=Fake(step);r=run(lab,ip,critic_provider=cp if flags.critic_enabled else None,flags=flags)
    assert len(cp.requests)==int(flags.critic_enabled)
    assert len(ip.requests)==1+int(flags.critic_enabled)
    assert validate_v3(r['v3_provenance'],r['public_record'],r['provenance'])['flags']==flags.__dict__


def test_private_sidecar_injection_rejected_even_rehashed():
    lab=laboratory(Flags.legacy());r=run(lab,Fake(lambda i,k:call_reply(i,'finalize',proposal(lab))),flags=Flags.legacy())
    v=deepcopy(r['v3_provenance']);b=json.loads(v['body_canonical']);b['scientific_validation']={'private_case':'forbidden'}
    v['body_canonical']=canonical(b);v['hash']=fingerprint(b)
    with pytest.raises(ValueError):validate_v3(v,r['public_record'],r['provenance'])


def test_prediction_precedes_actual_and_preserves_original():
    from nautilus.muse_v3 import Extension
    lab=laboratory();fit(lab);fit(lab,'lateral_current');flags=Flags(False,True,False,True)
    # Equalized public-only competitive-fit fixture, test-only accepted screen.
    for f in lab._reports.values():f['penalized_score']=1.;f['bound_hits']=[]
    ext=Extension(flags,None,V3_LIMITS);accepted={**screen(Trial('thrust_step')),'accepted':True}
    with patch('nautilus.muse_v3.screen',return_value=accepted),patch('nautilus.laboratory.screen',return_value=accepted),patch('nautilus.lab_safety.screen',return_value=accepted):
        ext.call(lab,{'op':'request_experiment','name':'thrust_step','params':{'duration_s':4.,'amplitude_n':2.,'phase_s':2.}})
    assert [json.loads(v['body_canonical'])['kind'] for v in ext.events]==['prediction_before','prediction_comparison']
    first=json.loads(ext.events[0]['body_canonical']);last=json.loads(ext.events[1]['body_canonical'])
    assert first['ledger_anchor']!=last['ledger_anchor'] and 'predictions' in first['data']
    assert lab.get_fit_report()['fits']==[] # original stale-fit invalidation
    assert first['data']['evidence_refs']!=lab.evidence_refs()


def test_development_design_disjoint_reproducible_and_all_groups(tmp_path):
    import evaluate_v3 as e
    m=e.reserve(tmp_path);assert len(m['plans'])==24 and len({p['seed'] for p in m['plans']})==24
    assert min(p['seed'] for p in m['plans'])>=2**54
    assert len(m['pilot_ids'])==6 and len({p['stratum'] for p in m['plans'] if p['case_id'] in m['pilot_ids']})==6
    for p in m['plans']:
        a=e.generate(p);assert a==e.generate(p)
        assert a['representable']==(len(a['mechanisms'])==1)
    with pytest.raises(FileExistsError):e.reserve(tmp_path)


def test_backend_defense_in_depth_rejects_before_execution():
    backend=SafeBackend(mode='simulation_enforced')
    r=backend.execute(Trial('thrust_step',duration_s=4.,amplitude_n=0.,phase_s=2.))
    assert not r['accepted'] and backend.private_results==[] and backend._count==0 and backend._time==0
