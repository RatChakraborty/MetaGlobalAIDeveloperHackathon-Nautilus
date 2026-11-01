import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readRecord} from '../src/records.ts';
import {readMuseProvenance} from '../src/muse-provenance.ts';
import {buildInvestigationArtifacts} from '../src/investigation-exports.ts';
import {sha256} from '@noble/hashes/sha256';
const hash=(s:string)=>Array.from(sha256(new TextEncoder().encode(s))).map(b=>b.toString(16).padStart(2,'0')).join('');
const observation=JSON.stringify({index:0,type:'observation',previous_hash:null,observations:[0,1].map(time_s=>({time_s,observed_y_m:0,observed_heading_rad:0,observed_yaw_rate_radps:0,port_command_n:1,starboard_command_n:1}))});
const ref=hash(observation),final=JSON.stringify({index:1,type:'finalized',previous_hash:ref,diagnosis:{hypothesis:null,evidence_refs:[ref]},confidence:'abstain',stop_reason:'Offline fixture only'}),anchor=hash(final);
const b={provider:'meta',model:'fake-offline',initial_observation_ref:ref,ledger_anchor:anchor,model_requests:[{latency_s:.01,usage:{input_tokens:10,output_tokens:5,total_tokens:15},status:'completed',function_calls:1}],actions:[{call_id:'fixture',name:'finalize',accepted:true,ledger_before:ref,ledger_after:anchor}],errors:[],retries:0,termination_reason:'model_finalized',finalization_origin:'model',elapsed_s:.02,output_tokens_reserved:100,request_bytes:200,remaining:{fit_calls:4,optimization_attempts:8,experiments:1,time_s:4},configuration_evaluation:'disabled',cost:{currency:null,amount:null,limitation:'No verified provider tariff; token/request ceilings bound usage, not a dollar estimate.'}};
const body=JSON.stringify(b),fixture={public_record:{schema_version:'nautilus.public-investigation.v1',run_id:'offline-fixture',source_kind:'offline-fixture',disclosure:'Schema test only, no real model measurements',recorded_conclusion:null,ledger:[{hash:ref,body_canonical:observation},{hash:anchor,body_canonical:final}]},provenance:{schema_version:'nautilus.muse-provenance.v1',body_canonical:body,hash:hash(body)}};
test('Offline fixture provenance imports and appears in report',async()=>{
 const r=await readRecord(fixture.public_record),p=readMuseProvenance(fixture.provenance,r);
 assert.equal(p.model,'fake-offline');assert.equal(p.finalization_origin,'model');
 const artifacts=await buildInvestigationArtifacts(fixture.public_record,null,null,fixture.provenance);
 assert.match(artifacts.report.content,/fake/);assert.match(artifacts.report.content,/Model provenance/);assert.equal(artifacts.config,null);
});
test('Muse importer rejects hash, link, unknown fields and fabricated metrics',async()=>{
 const r=await readRecord(fixture.public_record);
 for(const change of ['hash','anchor','unknown','usage','origin']){
  const p=structuredClone(fixture.provenance),b=JSON.parse(p.body_canonical);
  if(change==='anchor')b.ledger_anchor='0'.repeat(64);
  if(change==='unknown')b.authorization='forbidden';
  if(change==='usage')b.model_requests[0].usage.output_tokens=-1;
  if(change==='origin')b.finalization_origin='host';
  p.body_canonical=JSON.stringify(b);p.hash=change==='hash'?'0'.repeat(64):hash(p.body_canonical);
  assert.throws(()=>readMuseProvenance(p,r));
 }
});
