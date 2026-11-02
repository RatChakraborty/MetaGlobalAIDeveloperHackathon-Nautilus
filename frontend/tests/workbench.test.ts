import {test} from 'node:test';import assert from 'node:assert/strict';
import {execFile} from 'node:child_process';import {promisify} from 'node:util';
import {loadWorkbench,loadWorkbenchDemo,comparisonEnd,trajectoryDigest,type SourceFile} from '../src/workbench.ts';
import {evidenceOverview,workbenchControls,comparisonOverview} from '../src/workbench-view.ts';
import {buildInvestigationArtifacts} from '../src/investigation-exports.ts';
import {synchronizedPoses} from '../src/replay-math.ts';
const output=await promisify(execFile)('.venv/bin/python',['frontend/tests/workbench_fixture.py'],{cwd:'..',env:{...process.env,PYTHONPATH:'.',OMP_NUM_THREADS:'1',OPENBLAS_NUM_THREADS:'1',MKL_NUM_THREADS:'1'},encoding:'utf8'});
const f=JSON.parse(output.stdout),documents=f.files as Record<string,string>;
const files=(values:Record<string,string>):SourceFile[]=>Object.entries(values).map(([name,text])=>({name,size:new TextEncoder().encode(text).length,text:async()=>text}));
const changed=(name:string,mutate:(v:any)=>void)=>{const docs={...documents},v=JSON.parse(docs[name]);mutate(v);docs[name]=JSON.stringify(v);return docs;};
test('one selection loads genuine exporter records and validated comparison atomically',async()=>{
 const before=JSON.stringify(documents),w=await loadWorkbench(files(documents));assert.ok(w.comparison);assert.equal(w.raw.host.schema_version,'nautilus.post-investigation.v1');assert.equal(w.record.file.source_kind,'recorded_laboratory_history');
 assert.equal(w.comparison.candidate.record.file.run_id,w.raw.host?JSON.parse(w.raw.host.events[0].body_canonical).run_references.candidate.run_id:null);
 assert.match(w.comparisonStatus,/not a verified repair/);assert.equal(JSON.stringify(documents),before);
 const poses=synchronizedPoses(w.comparison.candidate.visual,w.comparison.baseline.visual,.15);assert.equal(poses.primary.time_s,.15);assert.equal(poses.reference.time_s,.15);
 assert.equal(comparisonEnd(w.comparison),3);const shorter=structuredClone(w.comparison);shorter.candidate.visual.samples=shorter.candidate.visual.samples.slice(0,3);assert.equal(comparisonEnd(shorter),3);assert.equal(synchronizedPoses(shorter.candidate.visual,shorter.baseline.visual,2).primary.time_s,.1);
});
test('actual exporter fingerprints survive whitespace/key order and reject changed poses',async()=>{
 const w=await loadWorkbench(files(documents));assert.ok(w.comparison);
 const raw=documents['candidate.visualization.json'];const expected=JSON.parse(w.raw.host.events[0].body_canonical).run_references.candidate.trajectory_sha256;
 assert.equal(trajectoryDigest(raw,w.comparison.candidate.visual),expected);
 const altered=changed('candidate.visualization.json',v=>{v.samples[1].y_m+=.1;});await assert.rejects(loadWorkbench(files(altered)),/trajectory|fingerprint/);
 await assert.rejects(loadWorkbench(files(changed('candidate.visualization.json',v=>{v.controller.configuration_id='0'.repeat(64);}))),/differs/);
 await assert.rejects(loadWorkbench(files(changed('candidate.public.json',v=>{v.run_id='0'.repeat(64);}))),/match|differs/);
});
test('missing comparison exports are explicit, not advertised as a working comparison',async()=>{
 const partial={...documents};delete partial['candidate.visualization.json'];const w=await loadWorkbench(files(partial));assert.equal(w.comparison,null);assert.match(w.comparisonStatus,/candidate.visualization.json/);assert.match(workbenchControls(true,w.comparisonStatus,false,false),/id="compare-runs" disabled/);
});
test('manifest resolves primary without fetching and rejects traversal, missing, extra and duplicate files',async()=>{
 const manifest={schema_version:'nautilus.workbench.v1',investigation:'investigation.json',files:Object.keys(documents)};
 const w=await loadWorkbench(files({...documents,'workbench.json':JSON.stringify(manifest)}));assert.ok(w.comparison);
 await assert.rejects(loadWorkbench(files({...documents,'workbench.json':JSON.stringify({...manifest,investigation:'../session.json'})})),/manifest/);
 await assert.rejects(loadWorkbench(files({...documents,'workbench.json':JSON.stringify({...manifest,files:[...manifest.files,'missing.json']})})),/match/);
 await assert.rejects(loadWorkbench([...files(documents),files(documents)[0]]),/uniquely/);
 await assert.rejects(loadWorkbench(files({...documents,'session.json':'{"schema_version":"nautilus.private-session.v4","truth":{}}'})),/private/);
});
test('unrelated sidecars and modified comparison summaries fail without mutating existing evidence',async()=>{
 const w=await loadWorkbench(files(documents)),before=JSON.stringify(w);
 await assert.rejects(loadWorkbench(files(changed('configuration-evaluation.json',v=>{v.ledger_anchor='0'.repeat(64);}))),/match/);
 await assert.rejects(loadWorkbench(files(changed('comparison.json',v=>{v.candidate.metrics.rms_cross_track_m=500;}))),/differs/);
 assert.equal(JSON.stringify(w),before);
});
test('V4 pending and multi-cause findings use existing validators and truthful summaries',async()=>{
 for(const name of ['pending','joint']){const x=f.v4[name],w=await loadWorkbench(files({'investigation.json':JSON.stringify(x.record),'v4.json':JSON.stringify(x.v4)}));assert.equal(w.raw.v4.schema_version,'nautilus.v4-provenance.v1');const {readV4}=await import('../src/v4-provenance.ts');const overview=evidenceOverview(w.record,readV4(w.raw.v4,w.record),null);assert.match(overview,/Replay cannot authorize/);if(name==='pending')assert.match(overview,/AWAITING_OPERATOR/);else{assert.match(overview,/lateral_current/);assert.match(overview,/heading_bias/);}}
 const w=await loadWorkbench(files(documents));const fake={events:[{body_canonical:JSON.stringify({kind:'critic_review',data:{entry:{status:'validated',transport_kind:'offline_fixture_only'}}})}]};assert.match(evidenceOverview(w.record,fake,null),/not a real Muse action/);
});
test('downloads retain real report values and existing comparison JSON format',async()=>{
 const w=await loadWorkbench(files(documents)),a=await buildInvestigationArtifacts(w.record.file,w.raw.host),b=await buildInvestigationArtifacts(w.record.file,w.raw.host);assert.deepEqual(a,b);assert.ok(a.config);assert.ok(a.comparison);
 const comparison=JSON.parse(a.comparison.content),expected=JSON.parse(w.raw.host.events[0].body_canonical).comparison;
 assert.deepEqual(comparison,expected);assert.equal(comparison.schema_version,'nautilus.configuration-evaluation.v1');assert.equal(JSON.parse(a.config.content).deployment_ready,false);assert.match(a.report.content,/Measured simulation comparison/);assert.match(comparisonOverview((await import('../src/post-evaluation.ts')).readHostEvaluation(w.raw.host,w.record)),/shorter run holds/);
});
test('gated approved demo manifest uses only safe base-relative exports',async()=>{
 let calls:string[]=[];const fetcher=async(url:string)=>{calls.push(url);const name=url.split('/').at(-1)!;return {ok:true,text:async()=>name==='workbench.json'?JSON.stringify({schema_version:'nautilus.workbench.v1',investigation:'investigation.json',files:Object.keys(documents)}):documents[name]};};
 assert.equal(await loadWorkbenchDemo(false,fetcher,'/repo/','workbench.json'),null);assert.equal(calls.length,0);
 const w=await loadWorkbenchDemo(true,fetcher,'/repo/','workbench.json');assert.ok(w?.comparison);assert.ok(calls.every(u=>u.startsWith('/repo/demo/')));
 calls=[];await assert.rejects(loadWorkbenchDemo(true,fetcher,'/repo/','https://example.invalid/manifest.json'),/basename/);assert.equal(calls.length,0);
});

test('unknown prototype-like schemas cannot hide unrecognized private artifacts',async()=>{
 for(const schema of ['constructor','__proto__','toString'])await assert.rejects(loadWorkbench(files({...documents,'unrecognized.json':JSON.stringify({schema_version:schema,truth:'must not be accepted'})})),/Unsupported or private/);
});

test('ordinary local download filenames with spaces remain supported',async()=>{
 const renamed={...documents,'Investigation record (2).json':documents['investigation.json']};delete (renamed as Record<string,string>)['investigation.json'];const w=await loadWorkbench(files(renamed));assert.ok(w.comparison);
});

test('a private-only selection explains the privacy boundary before guessing a primary',async()=>{
 await assert.rejects(loadWorkbench(files({'session.json':'{"schema_version":"nautilus.private-session.v4"}'})),/private artifact/);
});

test('legacy-shaped incomplete cause details remain safe and explicitly unavailable',async()=>{
 const w=await loadWorkbench(files(documents)),record=structuredClone(w.record);record.file.recorded_conclusion={diagnosis:{hypothesis:'nominal',evidence_refs:[],causes:[null]} as any,confidence:'tentative'};
 assert.match(evidenceOverview(record,null,null),/Malformed recorded cause details/);
 assert.doesNotMatch(evidenceOverview(record,null,null),/<script>/);
});
