"""Pre-freeze evaluator development fixtures; no live API or campaign seeds."""
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch
import pytest
import evaluate_muse as e
from nautilus.controller_context import canonical,fingerprint
from nautilus.muse import Reply,ProviderError
from nautilus.muse_context import restore_result


def manifest():return e.make_manifest(seed_base=2**40+404000,shuffle_seed=19)


def install(tmp_path):
    m=manifest();e.write_private(tmp_path/'manifest.json',m)
    import hashlib
    e.write_private(tmp_path/'manifest-sha256.json',{'file_sha256':hashlib.sha256((tmp_path/'manifest.json').read_bytes()).hexdigest(),'body_fingerprint':m['fingerprint']})
    return m


class Fake:
    provider='meta';model=e.DEFAULT_MODEL;reasoning_effort='low'
    def __init__(self):self.requests=[];self.refs=None
    def generate(self,**kwargs):
        self.requests.append(deepcopy(kwargs))
        if len(self.requests)==1:
            context=json.loads(kwargs['input'][0]['content'][0]['text']);self.refs=context['evidence_refs']
            assert 'mechanisms' not in context and 'seed' not in canonical(context)
            assert len(kwargs['tools'])==4
            call={'type':'function_call','name':'get_fit_report','arguments':'{}','call_id':'read'}
        else:
            assert kwargs['previous_response_id']=='fake-1'
            assert kwargs['input'][0]['call_id']=='read'
            result=restore_result(json.loads(kwargs['input'][0]['output'])['result'])
            assert result['evidence_refs']==self.refs
            call={'type':'function_call','name':'finalize','call_id':'done','arguments':canonical({'diagnosis':{'hypothesis':None,'evidence_refs':self.refs},'confidence':'abstain','ambiguity_statement':'Offline fake-provider fixture; insufficient evidence.'})}
        return Reply('fake-'+str(len(self.requests)),self.model,[call],{'input_tokens':100,'output_tokens':10,'total_tokens':110,'reasoning_tokens':5,'cached_input_tokens':0},.01,'completed',200,None,'low')


def test_frozen_plan_and_no_generation_at_freeze(monkeypatch):
    monkeypatch.setattr(e,'generate',lambda *_:(_ for _ in ()).throw(AssertionError('No physical generation before freeze')))
    m=manifest();e.validate_manifest(m)
    assert len(m['plans'])==len({p['seed'] for p in m['plans']})==12
    assert min(p['seed'] for p in m['plans'])>2000000
    assert m['candidate_commit']==e.CANDIDATE and m['model_limits']['retries']==0
    assert e.fingerprint({k:v for k,v in m.items() if k!='fingerprint'})==m['fingerprint']
    m['model_limits']['model_calls']=13
    with pytest.raises(ValueError):e.validate_manifest(m)


def test_all_strata_reproducible_independent_and_private():
    m=manifest();counts={}
    for p in m['plans']:
        case=e.generate(p);assert case==e.generate(p)
        counts[e.group(case)]=counts.get(e.group(case),0)+1
        a=e.create_lab(case,p);b=e.create_lab(case,p)
        assert a is not b and a._backend is not b._backend
        assert a.ledger==b.ledger and a.episodes is not b.episodes
        from nautilus.muse_investigator import initial_context
        public=initial_context(a)
        assert 'mechanisms' not in public and str(p['seed']) not in canonical(public)
        assert 'faults' not in public and 'plant' not in public
        assert public['controller']['declared_configuration']==m['controller_context']['declared_configuration']
        a.call({'op':'get_fit_report'});assert a.ledger==b.ledger
        assert len(case['mechanisms'])==(2 if p['kind'] in ('current_bias','current_port','joint_plant') else 1)
    assert counts=={'nominal':2,'current':2,'thruster':2,'sensor':2,'compound':2,'mismatch':2}


def test_actual_paired_baseline_semantics_and_stale_fit_behavior():
    p={'case_id':'toy','kind':'nominal','seed':23};case=e.generate(p)
    a=e.create_lab(case,p);r=e.baseline_run(a,'fixed_reference');m=e.closed_metrics(a,r,'fixed_reference')
    assert m['fit_calls']==8 and m['experiments']==1 and m['confidence']=='abstain'
    assert not a.get_fit_report()['fits'] # original fixed consumed fits before invalidation
    b=e.create_lab(case,p);r=e.baseline_run(b,'fixed_matched');m=e.closed_metrics(b,r,'fixed_matched')
    assert m['fit_calls']==8 and m['optimization_starts']<=16 and m['experiments']==1 and m['simulation_s']==12
    assert b.get_fit_report()['fits'] and all(f['evidence_refs']==b.evidence_refs() for f in b.get_fit_report()['fits'])
    assert a.ledger[0]==b.ledger[0]
    # Same fixed request and backend seed produce exactly matched public episode.
    ao=[x for x in a.ledger if x['type']=='observation'];bo=[x for x in b.ledger if x['type']=='observation']
    assert [x['observations'] for x in ao]==[x['observations'] for x in bo]
    assert ao[-1]['execution']==bo[-1]['execution']


def test_truth_scoring_has_no_correct_abstention_or_compound_exact_credit():
    case=e.generate({'kind':'current_bias','seed':7})
    metrics={'origin':'model','physical_finding':'lateral_current','hypothesis':'lateral_current','confidence':'supported'}
    s=e.score(case,metrics);assert not s['exact'] and s['partial_constituent'] and s['supported_incomplete']
    assert not s['truth_inconsistent_supported']
    metrics.update(physical_finding='starboard_degradation',hypothesis='starboard_degradation')
    assert e.score(case,metrics)['truth_inconsistent_supported']
    metrics.update(physical_finding=None,hypothesis=None,confidence='abstain')
    s=e.score(case,metrics);assert s['scientific_abstention'] and 'correct_abstention' not in s
    metrics['origin']='host';assert not e.score(case,metrics)['scientific_abstention']


def test_resume_skips_completed_pairs_and_prevents_duplicates(tmp_path):
    m=install(tmp_path);providers=[]
    def factory():f=Fake();providers.append(f);return f
    r=e.run_campaign(tmp_path,provider_factory=factory,batch=1)
    assert r['terminal_pairs']==1 and len(providers)==1 and len(providers[0].requests)==2
    assert r['summary']['muse']['usage']['input_tokens']==200 and r['summary']['muse']['requests']==2
    first=m['plans'][0]['case_id'];checkpoint=(tmp_path/(first+'.completed.json')).read_bytes()
    r=e.run_campaign(tmp_path,provider_factory=factory,batch=1)
    assert r['terminal_pairs']==2 and len(providers)==2
    assert (tmp_path/(first+'.completed.json')).read_bytes()==checkpoint
    public=e.sanitized_report(tmp_path)
    e.exporter().reject_private(public)
    assert public['attempted']==2 and public['terminal_pairs']==2
    for row in public['cases']:
        assert 'private_case' not in row and 'seed' not in row
        assert all('hypothesis' not in info and 'physical_finding' not in info for info in row['policies'].values())
    # Corruption is never silently skipped.
    path=tmp_path/(first+'.completed.json');data=json.loads(path.read_text());data['case_id']='tampered';path.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='checkpoint'):e.run_campaign(tmp_path,provider_factory=factory,batch=1)


def test_started_case_blocks_automatic_rerun(tmp_path):
    m=install(tmp_path);first=m['plans'][0]['case_id']
    e.write_private(tmp_path/(first+'.started.json'),{'case_id':first,'state':'started'})
    with pytest.raises(ValueError,match='Interrupted'):e.run_campaign(tmp_path,provider_factory=lambda:(_ for _ in ()).throw(AssertionError('No model calls')))


def test_provider_failure_is_terminal_case_and_campaign_stop(tmp_path):
    install(tmp_path)
    class Failure(Fake):
        def generate(self,**kwargs):raise ProviderError('http_401')
    r=e.run_campaign(tmp_path,provider_factory=Failure,batch=12)
    assert r['attempted']==1 and r['terminal_pairs']==1
    m=r['summary']['muse'];assert m['voluntary_completions']==0 and m['host_terminations']==1 and m['provider_failure_cases']==1
    assert m['scientific_abstention']==0 and m['requests']==1
    with pytest.raises(ValueError,match='stopped after provider'):e.run_campaign(tmp_path,provider_factory=Failure)


def test_aggregate_budget_prevents_new_case(tmp_path,monkeypatch):
    m=install(tmp_path)
    fake={'case_id':m['plans'][0]['case_id'],'metrics':{'muse':{'reason':'model_finalized','usage':{'input_tokens':4200000},'reserved_output':0}}}
    monkeypatch.setattr(e,'completed_records',lambda *_:[fake])
    monkeypatch.setattr(e,'aggregate',lambda rows:{'not_executed':True})
    r=e.run_campaign(tmp_path,provider_factory=lambda:(_ for _ in ()).throw(AssertionError('No case may start')))
    assert not list(tmp_path.glob('E*.started.json')) and r['attempted']==0


def test_frozen_file_hash_and_source_change_stop(tmp_path,monkeypatch):
    install(tmp_path)
    monkeypatch.setattr(e,'sources',lambda:{'changed':'hash'})
    with pytest.raises(ValueError,match='source'):e.run_campaign(tmp_path,provider_factory=Fake)


def test_private_artifacts_cannot_enter_checkout():
    with pytest.raises(ValueError):e.write_private(e.ROOT/'private-case.json',{'seed':7})


def test_offline_fixture_cannot_start_real_provider(tmp_path):
    install(tmp_path)
    with pytest.raises(ValueError,match='fixture'):e.run_campaign(tmp_path)


def test_open_lab_cannot_be_scored_and_all_numerical_budgets_are_equal():
    p={'case_id':'toy','kind':'nominal','seed':17};case=e.generate(p)
    labs=[e.create_lab(case,p) for _ in range(3)]
    assert all(l.get_fit_report()['remaining']==labs[0].get_fit_report()['remaining'] for l in labs)
    with pytest.raises(ValueError,match='open'):e.closed_metrics(labs[0],{},'muse')


def test_partial_started_case_remains_in_reliability_denominator(tmp_path):
    m=install(tmp_path);first=m['plans'][0]['case_id']
    e.write_private(tmp_path/(first+'.started.json'),{'case_id':first,'state':'started'})
    public=e.sanitized_report(tmp_path)
    assert public['attempted']==1 and public['terminal_pairs']==0
    assert public['summary']['muse']['attempted']==1
    assert public['summary']['muse']['end_to_end_completion_rate']==0
    assert public['summary']['muse']['unscored_started']==1
    assert public['summary']['paired_terminal_pairs']==0
