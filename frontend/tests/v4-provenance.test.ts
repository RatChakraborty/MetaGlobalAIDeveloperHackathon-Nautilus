import {test} from 'node:test';
import assert from 'node:assert/strict';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {sha256} from '@noble/hashes/sha256';
import {readRecord} from '../src/records.ts';
import {readV4,v4Summary} from '../src/v4-provenance.ts';
import {buildInvestigationArtifacts} from '../src/investigation-exports.ts';
const hash=(s:string)=>Array.from(sha256(new TextEncoder().encode(s))).map(x=>x.toString(16).padStart(2,'0')).join('');
const result=await promisify(execFile)('.venv/bin/python',['tests/v4_fixture.py'],{cwd:'..',env:{...process.env,PYTHONPATH:'.',OMP_NUM_THREADS:'1',OPENBLAS_NUM_THREADS:'1',MKL_NUM_THREADS:'1'},encoding:'utf8'});const fixtures=JSON.parse(result.stdout);
test('Real numerical joint and pending records import and export deterministically',async()=>{
 for(const name of ['pending','joint']){
  const f=fixtures[name],r=await readRecord(f.record),v=readV4(f.v4,r);assert.match(v4Summary(v).approval_notice,/cannot authorize/);
  const a=await buildInvestigationArtifacts(f.record,null,null,null,null,f.v4),b=await buildInvestigationArtifacts(f.record,null,null,null,null,f.v4);assert.deepEqual(a,b);assert.match(a.report.content,/V4 safety/);assert.equal(a.config,null);
 }
 assert.equal(readV4(fixtures.pending.v4,await readRecord(fixtures.pending.record)).status,'AWAITING_OPERATOR');
 assert.equal(readV4(fixtures.joint.v4,await readRecord(fixtures.joint.record)).joint_enabled,true);
});
test('Forged approvals, wrong modes, private data and bad links are rejected',async()=>{
 const f=fixtures.pending,r=await readRecord(f.record);
 for(const kind of ['approval','mode','private','link','hash']){
  const v=structuredClone(f.v4),b=JSON.parse(v.body_canonical);
  if(kind==='approval')b.approved=true;
  if(kind==='mode')b.policy='simulation_advisory';
  if(kind==='link')b.ledger_anchor='0'.repeat(64);
  if(kind==='private'){const e=JSON.parse(b.events[0].body_canonical);e.data.screen.private_answer='forbidden';b.events[0].body_canonical=JSON.stringify(e);b.events[0].hash=hash(b.events[0].body_canonical);}
  v.body_canonical=JSON.stringify(b);v.hash=kind==='hash'?'0'.repeat(64):hash(v.body_canonical);assert.throws(()=>readV4(v,r),kind);
 }
});

test('Incomplete or private evaluation summaries fail before rendering',async()=>{
 const {readV4Evaluation}=await import('../src/v4-provenance.ts');
 const base={schema_version:'nautilus.evaluation-summary.v4',development_only:true,planned:60,attempted:60,completed:60,policies:['passive'],metrics:{passive:{}},generation_gates:{},api_requests:0,source_fingerprint:'a'.repeat(64),manifest_fingerprint:'b'.repeat(64)};
 assert.throws(()=>readV4Evaluation(base));
 assert.throws(()=>readV4Evaluation({...base,private_answers:{a:'forbidden'}}));
});
