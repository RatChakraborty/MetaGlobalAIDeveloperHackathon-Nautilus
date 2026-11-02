import {test} from 'node:test';
import assert from 'node:assert/strict';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {sha256} from '@noble/hashes/sha256';
import {readRecord} from '../src/records.ts';
import {readV3,v3Summary} from '../src/v3-provenance.ts';
import {buildInvestigationArtifacts} from '../src/investigation-exports.ts';
const hash=(s:string)=>Array.from(sha256(new TextEncoder().encode(s))).map(b=>b.toString(16).padStart(2,'0')).join('');
const fixtureOutput=await promisify(execFile)('.venv/bin/python',['tests/v3_fixture.py'],{cwd:'..',env:{...process.env,PYTHONPATH:'.',OMP_NUM_THREADS:'1',OPENBLAS_NUM_THREADS:'1',MKL_NUM_THREADS:'1'},encoding:'utf8'});
const f=JSON.parse(fixtureOutput.stdout);
test('Real laboratory fake-provider critic unicode review imports and exports deterministically',async()=>{
 const r=await readRecord(f.public_record),b=readV3(f.v3_provenance,r,f.provenance);
 assert.equal(b.critic.status,'validated');assert.equal(v3Summary(b).events.length,3);
 const a=await buildInvestigationArtifacts(f.public_record,null,null,f.provenance,f.v3_provenance),c=await buildInvestigationArtifacts(f.public_record,null,null,f.provenance,f.v3_provenance);
 assert.deepEqual(a,c);assert.match(a.report.content,/V3 planning and critic/);assert.equal(a.config,null);
});
test('Prior export path remains optional',async()=>{const a=await buildInvestigationArtifacts(f.public_record,null,null,f.provenance);assert.doesNotMatch(a.report.content,/V3 planning and critic/);});
test('V3 rejects private fields, changed roles, missing reviews and bad links',async()=>{
 const r=await readRecord(f.public_record);
 for(const kind of ['private','hash','link','mode','count','review','missing']){
  const b=JSON.parse(f.v3_provenance.body_canonical);
  if(kind==='private')b.scientific_validation={private_case:'forbidden'};
  if(kind==='link')b.ledger_anchor='0'.repeat(64);
  if(kind==='mode')b.flags.enforced_experiment_safety=true;
  if(kind==='count')b.critic_request_limit=2;
  if(kind==='review'){const e=JSON.parse(b.events[1].body_canonical);e.data.review.evidence_refs=['not-real'];b.events[1]={body_canonical:JSON.stringify(e),hash:hash(JSON.stringify(e))};}
  if(kind==='missing'){b.events=[];b.critic=null;}
  const body_canonical=JSON.stringify(b),v={schema_version:'nautilus.v3-provenance.v1',body_canonical,hash:kind==='hash'?'0'.repeat(64):hash(body_canonical)};
  assert.throws(()=>readV3(v,r,f.provenance),kind);
 }
});
