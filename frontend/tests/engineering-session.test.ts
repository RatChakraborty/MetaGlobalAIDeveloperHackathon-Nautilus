import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {readEngineeringContext,engineeringHandoff} from '../src/engineering-session.ts';
import {engineeringReport,initialStudio,setEngineeringBinding,studioState,resetStudio,studioMarkup} from '../src/studio-view.ts';
import {fieldMarkup} from '../src/field-data.ts';
const result=spawnSync('../.venv/bin/python',['-c',`import json,sys
sys.path.insert(0,"..")
from nautilus_api.jobs import run_investigation
from nautilus_api.schema import scenario
f,m,r=scenario({'scenario':{},'duration_s':2.,'seed':74214})
run=run_investigation(f,m,r)
print(json.dumps({'context':run['engineering_context'],'request':r,'ledger':run['public_ledger_canonical']}))`],{encoding:'utf8'});
assert.equal(result.status,0,result.stderr);
const {context,request,ledger}=JSON.parse(result.stdout);
const changed=(body:unknown)=>{const body_canonical=JSON.stringify(body);return {body_canonical,hash:createHash('sha256').update(body_canonical).digest('hex')};};
test('real Python evidence transfers automatically with matching session, six channels and no generation inputs',()=>{
 const body=readEngineeringContext(context),handoff=engineeringHandoff(context);
 assert.equal(handoff.reproducibility.run_id,body.session_id);
 assert.equal(handoff.observations.episodes,body.episodes.length);
 assert.equal(Object.keys(body.episodes[0].observations[0]).length,6);
 assert.doesNotMatch(context.body_canonical,/"(?:truth|scenario|seed|faults|plant)"/);
 resetStudio();setEngineeringBinding({context,request,publicEvidence:{ledger_canonical:ledger}});
 const state=studioState();assert.equal(state.binding?.context.hash,context.hash);
 const report=engineeringReport(state);
 assert.equal(report.session_id,body.session_id);assert.deepEqual(report.investigation,context);
 assert.equal((JSON.parse(JSON.stringify(report)).public_evidence).ledger_canonical,ledger);
 assert.doesNotMatch(JSON.stringify(report),/"scenario_request"|"seed"|"faults"|"plant"/);
 assert.match(studioMarkup(state),/trusted_host/);assert.match(studioMarkup(state),/pending/);
 setEngineeringBinding(null);assert.equal(studioState().trial,null);assert.equal(studioState().binding,null);resetStudio();
});
test('altered evidence, private channels and broken identities fail closed',()=>{
 assert.throws(()=>readEngineeringContext({...context,body_canonical:context.body_canonical+' '}));
 const b=JSON.parse(context.body_canonical);b.episodes[0].observations[0].x_m=7;assert.throws(()=>readEngineeringContext(changed(b)));
 delete b.episodes[0].observations[0].x_m;b.session_id='a'.repeat(64);assert.throws(()=>readEngineeringContext(changed(b)));
});
test('missing physical data remains unavailable instead of a synthetic field case',()=>{
 assert.match(fieldMarkup(null),/unavailable/);assert.match(fieldMarkup(null),/no physical-data bridge/);
});
