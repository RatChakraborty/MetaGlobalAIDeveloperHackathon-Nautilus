"""Phase C offline fixtures: real laboratory and patched transport, no live requests."""
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch
import pytest
from nautilus.controller_context import canonical, fingerprint, initialize_controller_context, build_controller_context
from nautilus.laboratory import Laboratory
from nautilus.lab_safety import SafeBackend
from nautilus.simulator import simulate, Mission, OBSERVATION_FIELDS
from nautilus.muse import MetaProvider, Reply
from nautilus.muse_context import project_result, restore_result, SCHEMA
from nautilus.muse_investigator import run, Limits, validate_provenance
from test_muse import Fake, call, finish, body


def laboratory():
    l=Laboratory(simulate(mission=Mission(duration_s=.3)).observations,SafeBackend(),
        fit_budget=8,optimization_budget=16,experiment_budget=1,time_budget_s=16.)
    initialize_controller_context(l,build_controller_context())
    return l


def test_projection_preserves_real_adverse_experiment_and_complete_fit_diagnostics():
    l=laboratory()
    value=l.call({'op':'request_experiment','name':'differential_step','params':{'duration_s':12.,'phase_s':3.,'differential_n':4.,'cruise_thrust_n':8.}})
    original=deepcopy(value);projected,meta=project_result(value)
    assert meta['encoding']=='lossless_row_arrays' and meta['projected_bytes']<meta['original_bytes']
    assert restore_result(projected)==original and value==original
    assert projected['execution']==original['execution'] and projected['safety']==original['safety']
    assert projected['safety']['would_reject_enforced'] and projected['execution']['observed_excursion']
    assert projected['fit_reports_stale'] is True
    fitted=l.call({'op':'propose_hypothesis','template':'nominal','knobs':{},'bounds':{},'rationale':'Offline fixture'})
    fitted_projection,fitted_meta=project_result(fitted)
    assert fitted_meta['encoding']=='identity' and fitted_projection==fitted
    for key in ('parameters','weighted_rmse','penalized_score','residual_diagnostics','identifiability','bound_hits','warnings','converged','evidence_refs'):
        assert fitted_projection[key]==fitted[key]
    full=l.get_fit_report();compact,meta=project_result(full)
    assert restore_result(compact)==full and compact['schemas']==full['schemas']
    assert compact['fits']==full['fits'] # including adverse/conditional interpretation


@pytest.mark.parametrize('change',['value','channel','hash','extra','nonfinite'])
def test_projection_decoder_rejects_loss_or_tampering(change):
    rows=[dict(zip(OBSERVATION_FIELDS,[i*.05,1e-14,.1,.2,3.,4.])) for i in range(3)]
    p,_=project_result({'observations':rows});p=p['observations']
    assert p['schema_version']==SCHEMA
    if change=='value':p['samples'][0][1]+=1e-15
    if change=='channel':p['channels'].reverse()
    if change=='hash':p['sha256']='0'*64
    if change=='extra':p['extra']=1
    if change=='nonfinite':p['samples'][0][1]=float('nan')
    with pytest.raises(ValueError):restore_result(p)


def proposal(template,cid):
    return call('propose_hypothesis',{'template':template,'knobs':{},'bounds':{},'rationale':'Offline public-evidence comparison'},cid)


# Each call reports 10000 input tokens. Projections (request bytes + last call's input and output,
# added to measured input): call 1 = 28220, call 3 = 47885, call 4 = 57842. So 60000 permits all four
# calls, and 50000 permits three and refuses the fourth.
@pytest.mark.parametrize('input_threshold,expected_calls,expected_origin',[(60000,4,'model'),(50000,3,'host')])
def test_pending_third_fit_is_returned_when_budget_permits_and_retained_when_not(input_threshold,expected_calls,expected_origin):
    l=laboratory()
    def finalize(kwargs):
        assert kwargs['previous_response_id']=='3' and kwargs['input'][0]['call_id']=='heading'
        outcome=json.loads(kwargs['input'][0]['output'])
        assert restore_result(outcome['result'])['hypothesis']=='heading_bias'
        assert outcome['result']['converged']
        return [finish(l)]
    class Measured(Fake):
        def generate(self,**kwargs):
            r=super().generate(**kwargs)
            return Reply(r.response_id,r.model,r.output,{'input_tokens':10000,'output_tokens':5,'total_tokens':10005},r.latency_s,r.status)
    f=Measured([[proposal('nominal','nominal')],[proposal('port_degradation','port')],[proposal('heading_bias','heading')],finalize])
    original=deepcopy(l.ledger)
    r=run(l,f,limits=Limits(model_calls=12,actions=12,input_tokens_total=input_threshold,output_tokens_per_call=4096,output_tokens_total=32768))
    b=body(r)
    assert len(f.requests)==expected_calls and b['finalization_origin']==expected_origin
    assert l.fit_calls==3 and l.tests==0 and l.ledger[:len(original)]==original
    assert [e['report']['hypothesis'] for e in l.ledger if e['type']=='fit']==['nominal','port_degradation','heading_bias']
    assert r['tool_results'][2]['call_id']=='heading' and r['tool_results'][2]['result']['converged']
    assert len({a['call_id'] for a in b['actions']})==len(b['actions'])
    assert b['termination_reason']==('model_finalized' if expected_origin=='model' else 'input_token_limit')
    assert b['cost']['amount'] is None and b['cost']['currency'] is None


def test_repeated_call_id_reuses_same_projected_outcome_without_refitting():
    l=laboratory();action=proposal('nominal','repeat')
    f=Fake([[action],[action],lambda kwargs:[finish(l)]])
    r=run(l,f)
    assert l.fit_calls==1 and len(r['tool_results'])==2 # fit plus model finalize
    assert len(body(r)['actions'])==2
    assert f.requests[1]['input']==f.requests[2]['input']


def test_exact_request_json_bytes_match_transport_and_preserve_continuation(monkeypatch):
    from io import BytesIO
    monkeypatch.setenv('MODEL_API_KEY','offline-fixture-only')
    l=laboratory();sizes=[];actual=l.get_fit_report()
    class Response(BytesIO):
        status=200
        def __enter__(self):return self
        def __exit__(self,*args):self.close()
    class Opener:
        def open(self,request,timeout):
            sizes.append(len(request.data));p=json.loads(request.data)
            if len(sizes)==1:output=[call('get_fit_report',{},'read')]
            else:
                assert p['previous_response_id']=='response-1' and p['input'][0]['call_id']=='read'
                outcome=json.loads(p['input'][0]['output']);assert restore_result(outcome['result'])==actual
                output=[finish(l)]
            return Response(json.dumps({'model':'muse-wonder-1.0','id':'response-'+str(len(sizes)),
                'status':'completed','output':output,'reasoning':{'effort':'low'},'usage':{'input_tokens':100,'output_tokens':10,'total_tokens':110}}).encode())
    monkeypatch.setattr('urllib.request.build_opener',lambda *args:Opener())
    r=run(l,MetaProvider(reasoning_effort='low'),limits=Limits(output_tokens_per_call=4096))
    b=body(r)
    assert [x['request_bytes'] for x in b['model_requests']]==sizes
    assert all(x['request_bytes_kind']=='serialized_json' for x in b['model_requests'])
    assert b['request_bytes']==sum(sizes)
    assert b['safety_mode']=='simulation_advisory'
    assert b['model_requests'][1]['pending_input_bytes']>0
    assert r['tool_results'][0]['result']==actual
    assert fingerprint(actual)==b['actions'][0]['result_presentation']['original_sha256']


def test_exact_byte_limit_stops_before_transport(monkeypatch):
    l=laboratory()
    monkeypatch.setattr('urllib.request.build_opener',lambda *args:(_ for _ in ()).throw(AssertionError('No network allowed')))
    r=run(l,MetaProvider(reasoning_effort='low'),limits=Limits(request_bytes_total=1))
    assert not body(r)['model_requests'] and body(r)['termination_reason']=='request_byte_limit'
    assert l.fit_calls==0 and l.tests==0


def test_provenance_old_fields_remain_optional_and_new_metadata_is_closed():
    l=laboratory();r=run(l,Fake([[finish(l)]]))
    b=body(r)
    for key in ('runtime_limits','safety_mode'):b.pop(key)
    for request in b['model_requests']:
        for key in ('request_bytes','request_bytes_kind','pending_input_bytes'):request.pop(key)
    for action in b['actions']:action.pop('result_presentation')
    old={**r['provenance'],'body_canonical':canonical(b),'hash':fingerprint(b)}
    validate_provenance(old,r['public_record'])
    b=body(r);b['runtime_limits']['unexpected']=1
    bad={**r['provenance'],'body_canonical':canonical(b),'hash':fingerprint(b)}
    with pytest.raises(ValueError):validate_provenance(bad,r['public_record'])


def test_projection_never_serializes_private_backend_and_does_not_change_ledger():
    l=laboratory();l._backend.private_results.append({'truth':'PRIVATE_SENTINEL'})
    before=deepcopy(l.ledger);result=l.call({'op':'get_fit_report'})
    compact,_=project_result(result)
    assert 'PRIVATE_SENTINEL' not in canonical(compact) and l.ledger==before
    assert restore_result(compact)==result
