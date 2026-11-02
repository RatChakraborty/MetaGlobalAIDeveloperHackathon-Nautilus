/** Atomic local loading. Existing evidence schemas stay authoritative; no archives or uploads. */
import {readRecord,readVisual,bindController,type Investigation,type Visual} from './records.ts';
import {matchingEpisode,alignVisualization,compatibleReference} from './replay-math.ts';
import {readHostEvaluation,type HostEvaluation} from './post-evaluation.ts';
import {readMuseProvenance} from './muse-provenance.ts';
import {readV3} from './v3-provenance.ts';
import {readV4,readV4Evaluation} from './v4-provenance.ts';
import {readSupervisor,readVisualEvents} from './supervisor.ts';
import {sha256} from '@noble/hashes/sha256';
export type SourceFile={name:string;size:number;text():Promise<string>};
type Doc={name:string;text:string;value:any};
export type Run={record:Investigation;visual:Visual};
export type Comparison={candidate:Run;baseline:Run};
export type Workbench={record:Investigation;visual:Visual|null;raw:Record<string,any>;comparison:Comparison|null;comparisonStatus:string};
const safeName=(s:unknown):s is string=>typeof s==='string'&&/^[\p{L}\p{N} _().-]+\.json$/iu.test(s)&&!s.includes('..');
const schema=(d:Doc)=>d.value?.schema_version??'';
function manifest(v:any){if(!v||Object.keys(v).sort().join()!=='files,investigation,schema_version'||v.schema_version!=='nautilus.workbench.v1'||!safeName(v.investigation)||!Array.isArray(v.files)||!v.files.length||v.files.length>24||v.files.some((x:unknown)=>!safeName(x))||new Set(v.files).size!==v.files.length||!v.files.includes(v.investigation))throw Error('Invalid workbench manifest; use plain JSON basenames only.');return v as {investigation:string;files:string[]};}
/** Original exporter numeric lexemes retain Python float spelling (0.0/e-05).
 * Fixed numeric pose schema only; validates against parsed samples before hashing. */
export function trajectoryDigest(text:string,visual:Visual){
 const array=text.match(/"samples"\s*:\s*(\[[\s\S]*?\])/)?.[1];if(!array)throw Error('Original exported pose samples required for comparison fingerprint.');
 const rows=[...array.matchAll(/\{([^{}]*)\}/g)];if(rows.length!==visual.samples.length)throw Error('Pose fingerprint rows mismatch');
 const keys=['heading_rad','time_s','x_m','y_m'];
 const canonical='['+rows.map((r,i)=>{const tokens=new Map([...r[1].matchAll(/"(heading_rad|time_s|x_m|y_m)"\s*:\s*(-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?)/g)].map(m=>[m[1],m[2]]));if(tokens.size!==4||keys.some(k=>Number(tokens.get(k))!==visual.samples[i][k as keyof Visual['samples'][number]]))throw Error('Pose numeric fingerprint mismatch');return '{'+keys.map(k=>'"'+k+'":'+tokens.get(k)).join(',')+'}';}).join(',')+']';
 return Array.from(sha256(new TextEncoder().encode(canonical))).map(x=>x.toString(16).padStart(2,'0')).join('');
}
const digest=(s:string)=>Array.from(sha256(new TextEncoder().encode(s))).map(x=>x.toString(16).padStart(2,'0')).join('');
const ordered=(v:any):any=>Array.isArray(v)?v.map(ordered):v&&typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(k=>[k,ordered(v[k])])):v;
const equal=(a:any,b:any)=>JSON.stringify(ordered(a))===JSON.stringify(ordered(b));
export function bindRun(record:Investigation,input:unknown):Run{
 const visual=bindController(readVisual(input,record.file.run_id),record),episode=matchingEpisode(record,visual);
 if(!episode)throw Error('Visualization needs an explicit episode reference for multiple observation episodes.');
 return {record,visual:alignVisualization(visual,episode.observations!)};
}
async function comparison(host:HostEvaluation,docs:Doc[]):Promise<{value:Comparison|null;status:string}>{
 if(!host.comparison)return {value:null,status:'No completed controller evaluation recorded.'};
 const needed=['baseline','candidate'].flatMap(n=>[host.run_references[n].public_file,host.run_references[n].visualization_file]);
 const missing=needed.filter(name=>!docs.some(d=>d.name===name));if(missing.length)return {value:null,status:'To compare, include: '+missing.join(', ')};
 const runs:Record<string,Run>={};
 for(const name of ['baseline','candidate']){
  const refs=host.run_references[name],source=docs.find(d=>d.name===refs.public_file)!,poses=docs.find(d=>d.name===refs.visualization_file)!;
  const run=bindRun(await readRecord(source.value),poses.value),meta=run.visual.controller,expected=host.comparison[name] as any;
  const contextEvent=run.record.events.find(e=>e.type==='controller_context');const context=contextEvent?JSON.parse(contextEvent.context_canonical as string):null;
  const ep=matchingEpisode(run.record,run.visual)!;const body=run.record.file.ledger.find(e=>e.hash===ep.hash)!.body_canonical;const observations=body.match(/\"observations\"\s*:\s*(\[[\s\S]*?\])/ )?.[1];
  const identity=observations?digest('{\"context_hash\":'+JSON.stringify(expected.context_hash)+',\"observations\":'+observations+'}'):null;
  if(identity!==refs.run_id||run.record.file.run_id!==refs.run_id||!meta||!context||meta.implementation_version!==context.implementation_version||Object.entries(meta.configuration).some(([k,v])=>v!==context.declared_configuration[k].value)||!equal(meta.differences,name==='candidate'?host.comparison.approved_differences:{})||meta.configuration_id!==refs.configuration_id||meta.controller_id!==expected.controller_id||meta.context_hash!==expected.context_hash||meta.source_sha256!==expected.source_sha256||trajectoryDigest(poses.text,run.visual)!==refs.trajectory_sha256)throw Error('Comparison run/controller/trajectory differs from the recorded evaluation. Use original exported files.');
  runs[name]=run;
 }
 compatibleReference(runs.candidate.visual,runs.baseline.visual);
 return {value:{candidate:runs.candidate,baseline:runs.baseline},status:'Recorded candidate / baseline comparison ready. Simulation metrics; not a verified repair.'};
}
export async function loadWorkbench(files:Iterable<SourceFile>):Promise<Workbench>{
 const selected=[...files];if(!selected.length||selected.length>25||selected.reduce((n,f)=>n+f.size,0)>120_000_000||selected.some(f=>f.size>50_000_000||!safeName(f.name))||new Set(selected.map(f=>f.name)).size!==selected.length)throw Error('Choose up to 25 uniquely named exported JSON files (50 MB each, 120 MB total).');
 const docs=await Promise.all(selected.map(async f=>{const text=await f.text();return {name:f.name,text,value:JSON.parse(text)};}));
 const allowed=['nautilus.workbench.v1','nautilus.public-investigation.v1','nautilus.public-investigation.v2','nautilus.visualization-only.v1','nautilus.visualization-only.v2','nautilus.visualization-only.v3','nautilus.post-investigation.v1','nautilus.muse-provenance.v1','nautilus.v3-provenance.v1','nautilus.v4-provenance.v1','nautilus.supervisor-events.v1','nautilus.visualization-events.v1','nautilus.evaluation-summary.v4','nautilus.configuration-evaluation.v1','nautilus.control-lab-recommendation.v1'];
 for(const d of docs)if(!allowed.includes(schema(d)))throw Error('Unsupported or private artifact: '+d.name+'. Select public evidence exports only.');
 const manifests=docs.filter(d=>schema(d)==='nautilus.workbench.v1');if(manifests.length>1)throw Error('Choose one workbench manifest.');
 const plan=manifests[0]?manifest(manifests[0].value):null;
 if(plan&&(plan.files.some(n=>!docs.some(d=>d.name===n))||docs.some(d=>d!==manifests[0]&&!plan.files.includes(d.name))))throw Error('Selected files must match the manifest file list. No files are fetched from local manifests.');
 const records=docs.filter(d=>/^nautilus\.public-investigation\.v[12]$/.test(schema(d)));
 const hosts=docs.filter(d=>schema(d)==='nautilus.post-investigation.v1');if(hosts.length>1)throw Error('Choose one configuration evaluation sidecar.');
 const anchors=docs.filter(d=>/^nautilus\.(?:muse-provenance|v[34]-provenance)\.v1$/.test(schema(d))).map(d=>JSON.parse(d.value.body_canonical).ledger_anchor);
 const primary=plan?records.find(d=>d.name===plan.investigation):records.length===1?records[0]:records.find(d=>d.value.ledger?.at(-1)?.hash===(hosts[0]?.value.investigation_id??anchors[0]));
 if(!primary)throw Error('Select one investigation, or include a manifest identifying it when several records are present.');
 const record=await readRecord(primary.value),raw:Record<string,any>={};let visual:Visual|null=null;
 const selectedHost=hosts[0]?readHostEvaluation(hosts[0].value,record):null;
 const referenced=new Set(selectedHost?.comparison?Object.values(selectedHost.run_references).flatMap(r=>[r.public_file,r.visualization_file]):[]);
 for(const d of docs){
  const s=schema(d);if(d===primary||d===manifests[0])continue;
  if(/^nautilus\.public-investigation\.v[12]$/.test(s)){if(!referenced.has(d.name))throw Error('Additional investigation is not referenced by this evaluation.');await readRecord(d.value);continue;}
  if(/^nautilus\.visualization-only\.v[123]$/.test(s)){
   if(d.value.run_id===record.file.run_id){if(visual)throw Error('Multiple investigation visualizations selected.');visual=bindRun(record,d.value).visual;}
   else if(!referenced.has(d.name))throw Error('Visualization belongs to another investigation.');
   continue;
  }
  const role:Record<string,string>={'nautilus.post-investigation.v1':'host','nautilus.muse-provenance.v1':'muse','nautilus.v3-provenance.v1':'v3','nautilus.v4-provenance.v1':'v4','nautilus.supervisor-events.v1':'supervisor','nautilus.visualization-events.v1':'visualEvents','nautilus.evaluation-summary.v4':'evaluation','nautilus.configuration-evaluation.v1':'comparisonSummary','nautilus.control-lab-recommendation.v1':'controlLab'};
  if(!Object.hasOwn(role,s))throw Error('Unsupported or private artifact: '+d.name+'. Select public evidence exports only.');
  if(raw[role[s]])throw Error('Multiple '+role[s]+' companions selected.');raw[role[s]]=d.value;
 }
 const host=selectedHost;
 if(raw.muse)readMuseProvenance(raw.muse,record);
 if(raw.v3){if(!raw.muse)throw Error('V3 companion requires matching Muse provenance.');readV3(raw.v3,record,raw.muse);}
 if(raw.v4)readV4(raw.v4,record);
 if(raw.supervisor)readSupervisor(raw.supervisor,record);
 if(raw.visualEvents){if(!visual)throw Error('Visualization events require the matching pose export.');readVisualEvents(raw.visualEvents,record,visual);}
 if(raw.evaluation)readV4Evaluation(raw.evaluation);
 if(raw.comparisonSummary){
  if(!host?.comparison)throw Error('Comparison summary requires its anchored host evaluation.');
  const {records,...summary}=raw.comparisonSummary;if(!equal(summary,host.comparison))throw Error('Comparison summary differs from the host evaluation.');
  if(records){if(Object.keys(records).sort().join()!=='baseline,candidate')throw Error('Invalid comparison summary references');for(const name of ['baseline','candidate']){const row=records[name],ref=host.run_references[name];if(Object.keys(row).sort().join()!=='observation_ref,public,run_id,visualization'||row.public!==ref.public_file||row.visualization!==ref.visualization_file||row.run_id!==ref.run_id||!/^([a-f0-9]{64})$/.test(row.observation_ref))throw Error('Invalid comparison summary reference');const supplied=docs.find(d=>d.name===ref.public_file);if(supplied&&!supplied.value.ledger.some((e:any)=>e.hash===row.observation_ref&&JSON.parse(e.body_canonical).type==='observation'))throw Error('Comparison observation reference differs');}}
 }
 const compared=host?await comparison(host,docs):{value:null,status:'No completed controller evaluation loaded. Nominal references are not verified repairs.'};
 return {record,visual,raw,comparison:compared.value,comparisonStatus:compared.status};
}
export async function loadWorkbenchDemo(enabled:boolean,fetcher:(url:string)=>Promise<{ok:boolean;text():Promise<string>}>,base:string,filename:string){
 if(!enabled)return null;if(!safeName(filename))throw Error('Demo manifest must be a plain JSON basename.');
 const prefix=base.replace(/\/?$/,'/')+'demo/';const response=await fetcher(prefix+filename);if(!response.ok)throw Error('Approved workbench demo unavailable; open local records.');
 const text=await response.text(),plan=manifest(JSON.parse(text));
 const files=await Promise.all(plan.files.map(async name=>{const r=await fetcher(prefix+name);if(!r.ok)throw Error('Approved demo companion unavailable: '+name);const data=await r.text();return {name,size:new TextEncoder().encode(data).length,text:async()=>data};}));
 return loadWorkbench([...files,{name:filename,size:new TextEncoder().encode(text).length,text:async()=>text}]);
}
export function comparisonEnd(value:Comparison){return Math.max(value.candidate.visual.samples.at(-1)!.time_s,value.baseline.visual.samples.at(-1)!.time_s);}
