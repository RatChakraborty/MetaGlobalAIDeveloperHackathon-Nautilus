"""Fake-provider/transport tests; no real API calls or replacement laboratories."""
from copy import deepcopy
import json
from unittest.mock import patch
import pytest
from nautilus.controller_context import canonical, fingerprint
from nautilus.laboratory import Laboratory
from nautilus.lab_safety import SafeBackend
from nautilus.simulator import simulate, Mission
from nautilus.muse import MetaProvider, Reply, ProviderError, parse_reply
from nautilus.muse_investigator import function_tools, validate_provenance
from nautilus.muse_diagnostic import run_diagnostic, diagnostic_tools, diagnostic_context
from test_muse import Fake, call, body


def laboratory():
    return Laboratory(simulate(mission=Mission(duration_s=.3)).observations,SafeBackend(),
        fit_budget=1,optimization_budget=0,experiment_budget=0,time_budget_s=0.)


def acknowledgement():
    return [{'type':'message','content':[{'type':'output_text','text':'Received the public evidence and remaining budgets.'}]}]


def test_real_laboratory_dispatch_and_matching_continuation(tmp_path):
    l=laboratory();original=deepcopy(l.ledger);actual=l.get_fit_report()
    def second(kwargs):
        assert kwargs['previous_response_id']=='1'
        assert kwargs['input']==[{'type':'function_call_output','call_id':'actual-call','output':canonical(actual)}]
        assert len(kwargs['tools'])==1
        return acknowledgement()
    f=Fake([[call('get_fit_report',{},'actual-call')],second])
    with patch.object(l,'call',wraps=l.call) as dispatched:
        result=run_diagnostic(l,f)
    assert dispatched.call_args_list[0].args[0]=={'op':'get_fit_report'}
    assert len(dispatched.call_args_list)==2 # one real read, one explicitly host-labeled close
    assert result['tool_result']==actual
    b=body(result);assert b['termination_reason']=='diagnostic_completed'
    assert b['finalization_origin']=='host' and l.ledger[-1]['confidence']=='abstain'
    assert 'HOST-ENFORCED ABSTENTION' in l.ledger[-1]['stop_reason']
    assert l.ledger[:-1]==original and l.fit_calls==0 and l.tests==0
    assert b['diagnostic']['tool_result_hash']==fingerprint(actual)
    assert b['model_requests'][1]['submitted_call_ids']==['actual-call']
    assert len(f.requests)==2 and all(x['max_output_tokens']==4096 for x in f.requests)
    assert b['output_tokens_reserved']==8192
    validate_provenance(result['provenance'],result['public_record'])
    # Actual Python-generated diagnostic also passes the existing TS importer.
    import shutil, subprocess
    from pathlib import Path
    root=Path(__file__).parents[1]
    if shutil.which('node') and (root/'frontend/node_modules').exists():
        p=tmp_path/'diagnostic.json';p.write_text(canonical(result))
        script="import fs from 'node:fs';import {readRecord} from './frontend/src/records.ts';import {readMuseProvenance} from './frontend/src/muse-provenance.ts';const r=JSON.parse(fs.readFileSync(process.argv[1],'utf8'));readMuseProvenance(r.provenance,await readRecord(r.public_record));"
        subprocess.run(['node','--experimental-strip-types','--input-type=module','-e',script,str(p)],cwd=root,check=True,capture_output=True)


def test_diagnostic_menu_does_not_change_production_tools():
    before=function_tools();one=diagnostic_tools()
    assert len(before)==4 and len(one)==1 and one[0]['name']=='get_fit_report'
    assert one[0]['parameters']=={'type':'object','properties':{},'required':[],'additionalProperties':False}
    one[0]['parameters']['properties']['bad']={}
    assert function_tools()==before


@pytest.mark.parametrize('first',[
    [],acknowledgement(),[call('get_fit_report',{'unexpected':1})],
    [call('request_experiment',{'name':'thrust_step','params':{}})],
    [call('get_fit_report',{},'a'),call('get_fit_report',{},'b')],
    ProviderError('http_400'),ProviderError('http_401'),ProviderError('http_429',retryable=True),
    ProviderError('network_or_timeout')])
def test_first_failure_never_sends_a_second_request(first):
    l=laboratory();f=Fake([first]);r=run_diagnostic(l,f)
    assert len(f.requests)==1 and body(r)['termination_reason']!='diagnostic_completed'
    assert r['tool_result'] is None and l.tests==0 and l.fit_calls==0


def test_malformed_arguments_stop_without_continuation():
    l=laboratory();c=call('get_fit_report',{});c['arguments']='{"x":NaN}'
    f=Fake([[c]]);r=run_diagnostic(l,f)
    assert len(f.requests)==1 and not body(r)['actions'][0]['accepted']


def test_incomplete_usage_and_missing_breakdown_are_not_invented():
    value={'model':'muse-wonder-1.0','id':'response','status':'incomplete','output':[],
        'incomplete_details':{'reason':'max_output_tokens'},'usage':{'input_tokens':100,'output_tokens':4096,'total_tokens':4196,
        'output_tokens_details':{'reasoning_tokens':4000,'unapproved':'do not retain'},'input_tokens_details':{'cached_tokens':20}},'reasoning':{'effort':'low'}}
    reply=parse_reply(value,'muse-wonder-1.0',.1,200)
    assert reply.usage['reasoning_tokens']==4000 and reply.usage['cached_input_tokens']==20
    assert 'unapproved' not in canonical(reply.usage) and reply.reasoning_effort=='low'
    class Incomplete(Fake):
        model='muse-wonder-1.0'
        reasoning_effort='low'
        def generate(self,**kwargs):self.requests.append(kwargs);return reply
    f=Incomplete([]);r=run_diagnostic(laboratory(),f)
    assert len(f.requests)==1 and body(r)['termination_reason']=='incomplete_response'
    assert body(r)['model_requests'][0]['usage']['reasoning_tokens']==4000
    value['usage']={'input_tokens':100,'output_tokens':4096,'total_tokens':4196}
    assert 'reasoning_tokens' not in parse_reply(value,'muse-wonder-1.0',.1).usage


@pytest.mark.parametrize('effort',['none','high','unknown',True,{},17])
def test_unknown_reasoning_settings_rejected_before_network(effort):
    with pytest.raises(ValueError):MetaProvider(reasoning_effort=effort)


def test_reasoning_low_serialization_auto_and_no_hidden_reasoning_retention(monkeypatch):
    from io import BytesIO
    monkeypatch.setenv('MODEL_API_KEY','offline-only-credential')
    class Response(BytesIO):
        status=200
        def __enter__(self):return self
        def __exit__(self,*args):self.close()
    class Opener:
        def open(self,request,timeout):
            p=json.loads(request.data)
            assert p['reasoning']=={'effort':'low'} and p['tool_choice']=='auto'
            assert p['parallel_tool_calls'] is False and p['max_output_tokens']==4096
            return Response(json.dumps({'model':'muse-wonder-1.0','id':'response','status':'completed','output':acknowledgement(),
                'reasoning':{'effort':'low'},'usage':{'output_tokens':100,'output_tokens_details':{'reasoning_tokens':80}}}).encode())
    monkeypatch.setattr('urllib.request.build_opener',lambda *args:Opener())
    r=MetaProvider(reasoning_effort='low').generate(instructions='diagnostic',input=[],tools=diagnostic_tools(),previous_response_id=None,max_output_tokens=4096,timeout=1)
    assert r.reasoning_effort=='low' and r.usage['reasoning_tokens']==80


def test_repeated_call_id_after_continuation_does_not_execute_twice():
    l=laboratory();c=call('get_fit_report',{},'same')
    f=Fake([[c],[c]])
    with patch.object(l,'call',wraps=l.call) as dispatched:r=run_diagnostic(l,f)
    assert len(f.requests)==2 and len(body(r)['actions'])==1
    assert sum(k.args[0]['op']=='get_fit_report' for k in dispatched.call_args_list)==1
    assert body(r)['termination_reason']=='diagnostic_unexpected_followup'


def test_diagnostic_privacy_and_closed_or_budgeted_laboratory_rejected():
    l=laboratory();l._backend.private_results.append({'truth':'PRIVATE_SENTINEL'})
    c=diagnostic_context(l)
    assert 'PRIVATE_SENTINEL' not in canonical(c) and 'seed' not in canonical(c)
    assert c['evidence_refs']==l.evidence_refs()
    assert c['observations'][0]['observations']==l.ledger[0]['observations']
    assert c['remaining']['experiments']==0
    f=Fake([[call('get_fit_report',{})],acknowledgement()]);run_diagnostic(l,f)
    assert 'PRIVATE_SENTINEL' not in canonical(f.requests)
    with pytest.raises(ValueError):run_diagnostic(l,Fake([]))


def test_success_claim_requires_actual_two_response_linkage():
    l=laboratory();r=run_diagnostic(l,Fake([[call('get_fit_report',{})],acknowledgement()]))
    for change in ('call_id','previous_id','status','extra_request'):
        b=body(r)
        if change=='call_id':b['model_requests'][1]['submitted_call_ids']=['forged']
        if change=='previous_id':b['model_requests'][1]['previous_response_id']='forged'
        if change=='status':b['model_requests'][1]['status']='incomplete'
        if change=='extra_request':b['model_requests'].append(deepcopy(b['model_requests'][-1]))
        p={**r['provenance'],'body_canonical':canonical(b),'hash':fingerprint(b)}
        with pytest.raises(ValueError):validate_provenance(p,r['public_record'])


@pytest.mark.parametrize('usage',[{'output_tokens_details':{'reasoning_tokens':-1}}, {'output_tokens':10,'output_tokens_details':{'reasoning_tokens':11}}, {'input_tokens_details':{'cached_tokens':True}}])
def test_invalid_nested_usage_rejected_without_recording_details(usage):
    with pytest.raises(ProviderError):parse_reply({'id':'r','model':'test','status':'completed','output':[], 'usage':usage},'test',.1)
