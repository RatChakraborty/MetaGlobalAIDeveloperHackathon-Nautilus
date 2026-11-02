import {sha256} from '@noble/hashes/sha256';
import {readMuseProvenance} from './muse-provenance.ts';
import type {Investigation} from './records.ts';
type Obj=Record<string,any>;
const object=(v:unknown):v is Obj=>!!v&&typeof v==='object'&&!Array.isArray(v);
const closed=(v:unknown,keys:string[])=>{if(!object(v)||Object.keys(v).sort().join()!==keys.sort().join())throw Error('Unexpected V3 fields');return v;};
const hash=(s:string)=>Array.from(sha256(new TextEncoder().encode(s))).map(x=>x.toString(16).padStart(2,'0')).join('');
const bounded=(x:unknown,n:number)=>{if(!Array.isArray(x)||x.length>n)throw Error('Unbounded V3 list');return x;};
const text=(x:unknown,n:number)=>{if(typeof x!=='string'||!x.length||x.length>n)throw Error('Invalid V3 text');return x;};
function clean(v:unknown){if(object(v)){for(const [k,x] of Object.entries(v)){if(/private|oracle|ground_truth|injected|credential|authorization/i.test(k)||['faults','plant','truth','seed'].includes(k))throw Error('Nonpublic V3 content');clean(x);}}else if(Array.isArray(v))v.forEach(clean);else if(typeof v==='number'&&!Number.isFinite(v))throw Error('Nonfinite V3 content');}
function review(v:unknown,refs:Set<string>){
 const r=closed(v,['severity','evidence_refs','strongest_competing_explanation','unsupported_claims','stale_evidence_concerns','confidence_concerns','recommendation','rationale']);
 if(!['low','medium','high'].includes(r.severity)||!['retain','qualify','reconsider','abstain','request_more_evidence'].includes(r.recommendation))throw Error('Invalid critic enum');
 if(!bounded(r.evidence_refs,8).length||r.evidence_refs.some((x:unknown)=>typeof x!=='string'||!refs.has(x)))throw Error('Invalid critic references');
 for(const k of ['strongest_competing_explanation','rationale'])text(r[k],800);
 for(const k of ['unsupported_claims','stale_evidence_concerns','confidence_concerns'])bounded(r[k],6).forEach(x=>text(x,300));
}
const params:Record<string,string[]>={cable_follow:['duration_s','cruise_thrust_n'],thrust_step:['duration_s','amplitude_n','phase_s'],coast_down:['duration_s','amplitude_n','differential_n','phase_s'],differential_step:['duration_s','differential_n','cruise_thrust_n','phase_s'],amplitude_ramp:['duration_s','amplitude_n','phase_s'],heading_response:['duration_s','cruise_thrust_n','phase_s','heading_step_rad']};
function trial(v:Obj){if(typeof v.name!=='string'||!params[v.name])throw Error('Unknown V3 maneuver');closed(v.params,params[v.name]);if(Object.values(v.params).some(x=>typeof x!=='number'||!Number.isFinite(x)))throw Error('Invalid maneuver values');}
const kinds=['numerical_plan','pending_finalization','critic_review','investigator_response','prediction_before','prediction_comparison'];
export function readV3(input:unknown,record:Investigation,investigator:unknown):Obj{
 const p=readMuseProvenance(investigator,record),r=closed(input,['schema_version','body_canonical','hash']);
 if(r.schema_version!=='nautilus.v3-provenance.v1'||typeof r.body_canonical!=='string'||new TextEncoder().encode(r.body_canonical).length>2_000_000||hash(r.body_canonical)!==r.hash)throw Error('Invalid V3 envelope');
 const b=closed(JSON.parse(r.body_canonical),['schema_version','flags','model','reasoning_effort','investigator_provenance_hash','ledger_anchor','events','critic','planning_passes','planning_limit','critic_request_limit','critic_failure','total_elapsed_s','scientific_validation']);clean(b);
 if(b.schema_version!=='nautilus.v3-provenance-body.v1'||!object(investigator)||b.investigator_provenance_hash!==investigator.hash||b.ledger_anchor!==record.events.at(-1)?.hash||b.model!==p.model)throw Error('Unlinked V3 provenance');
 const flags=closed(b.flags,['risk_aware_planning','enforced_experiment_safety','critic_enabled','prediction_audit_enabled']);
 if(Object.values(flags).some(x=>typeof x!=='boolean')||p.safety_mode!==(flags.enforced_experiment_safety?'simulation_enforced':'simulation_advisory'))throw Error('Invalid V3 mode');
 if(b.planning_limit!==4||!Number.isInteger(b.planning_passes)||b.planning_passes<0||b.planning_passes>4||b.critic_request_limit!==1||typeof b.critic_failure!=='boolean'||typeof b.total_elapsed_s!=='number'||b.total_elapsed_s<0||![null,'low'].includes(b.reasoning_effort))throw Error('Invalid V3 limits');
 let previous:string|null=null,last=0;const events=bounded(b.events,40),counts:Record<string,number>={};let critic:Obj|null=null;
 for(const [i,envelope] of events.entries()){
  const e=closed(envelope,['body_canonical','hash']);text(e.body_canonical,2_000_000);const ev=closed(JSON.parse(e.body_canonical),['index','kind','ledger_anchor','previous_hash','data']);
  const pos=record.events.findIndex(x=>x.hash===ev.ledger_anchor);
  if(hash(e.body_canonical)!==e.hash||ev.index!==i||ev.previous_hash!==previous||pos<last||!kinds.includes(ev.kind))throw Error('Invalid V3 event chain');
  last=pos;previous=e.hash;counts[ev.kind]=(counts[ev.kind]??0)+1;
  const refs=new Set(record.events.slice(0,pos+1).filter(x=>x.type==='observation').map(x=>x.hash)),d=ev.data;
  if(ev.kind==='numerical_plan'){
   closed(d,['schema_version','evidence_refs','fit_names','fit_fingerprint','status','candidate_count','forward_simulations','scales','cost','recommended_ids','rows','qualification']);
   if(d.schema_version!=='nautilus.experiment-plan.v3'||d.candidate_count!==36||bounded(d.rows,36).length!==36||d.forward_simulations<0||d.forward_simulations>144||bounded(d.evidence_refs,20).some(x=>!refs.has(x)))throw Error('Invalid numerical plan');
   const accepted=new Set<string>();
   for(const row of d.rows){closed(row,['candidate_id','name','params','accepted','predictive_margin_m','discrimination','utility','forecast_available','forecast_error','within_budget']);trial(row);if(typeof row.within_budget!=='boolean'||![null,'unavailable_forward_model'].includes(row.forecast_error))throw Error('Invalid forecast qualification');if(typeof row.accepted!=='boolean'||typeof row.forecast_available!=='boolean'||(!row.accepted||!row.within_budget)&&row.utility!==null)throw Error('Unsafe plan');if(row.accepted)accepted.add(row.candidate_id);closed(row.discrimination,['pairs','minimum','mean']);for(const pair of bounded(row.discrimination.pairs,6))closed(pair,['left','right','normalized_rms']);}
   if(bounded(d.recommended_ids,3).some(x=>!accepted.has(x)))throw Error('Unsafe recommendation');
  }else if(ev.kind==='critic_review'){
   const allowed=['status','http_status','usage','latency_s','packet_bytes','packet_sha256','model','reasoning_effort','request_limit','output_limit','token_measurement','error','review','response_id','output_reserved','incomplete_reason'];
   if(!object(d)||Object.keys(d).some(k=>!allowed.includes(k))||!['status','review','usage','latency_s','error','request_limit','output_reserved'].every(k=>Object.hasOwn(d,k))||d.request_limit!==1||(d.packet_bytes??0)>15000||d.output_reserved>2048)throw Error('Invalid critic accounting');
   if(!object(d.usage)||Object.entries(d.usage).some(([k,v])=>!['input_tokens','cached_input_tokens','output_tokens','reasoning_tokens','total_tokens'].includes(k)||typeof v!=='number'||!Number.isInteger(v)||v<0))throw Error('Invalid critic usage');
   if(d.status==='validated')review(d.review,refs);else if(d.status!=='failed'||d.review!==null)throw Error('Missing critic failure');critic=d;
  }else if(ev.kind==='pending_finalization'){
   closed(d,['diagnosis','confidence','ambiguity_statement']);closed(d.diagnosis,['hypothesis','evidence_refs']);if(bounded(d.diagnosis.evidence_refs,20).some(x=>!refs.has(x)))throw Error('Unknown pending reference');
  }else if(ev.kind==='investigator_response'){
   closed(d,['review_hash','proposal','changed','qualification']);closed(d.proposal,['diagnosis','confidence','ambiguity_statement']);
   if(!critic||critic.status!=='validated'||d.review_hash!==hash(JSON.stringify(critic.review,Object.keys(critic.review).sort()).replace(/[\u007f-\uffff]/g,c=>'\\u'+c.charCodeAt(0).toString(16).padStart(4,'0')))||!String(d.proposal.ambiguity_statement).includes('critic:'+d.review_hash))throw Error('Unlinked critic response');
  }else if(ev.kind==='prediction_before'){
   closed(d,['candidate_id','name','params','evidence_refs','leading','alternative','channels','predictions','qualification']);
   trial(d);if(!object(d.predictions)||Object.keys(d.predictions).sort().join()!==[d.leading,d.alternative].sort().join()||bounded(d.evidence_refs,20).some(x=>!refs.has(x)))throw Error('Invalid forecast');
   for(const rows of Object.values(d.predictions))for(const row of bounded(rows,321))closed(row,['time_s','observed_y_m','observed_heading_rad','observed_yaw_rate_radps','port_command_n','starboard_command_n']);
  }else{
   closed(d,['candidate_id','observation_ref','testable','normalized_rms','outcome','rule']);if(!refs.has(d.observation_ref)||!['support','contradiction','inconclusive'].includes(d.outcome)||!counts.prediction_before)throw Error('Invalid prediction comparison');
  }
 }
 if((counts.numerical_plan??0)!==b.planning_passes||(counts.critic_review??0)>1||(counts.pending_finalization??0)!==(counts.critic_review??0)||JSON.stringify(b.critic)!==JSON.stringify(critic)||b.critic_failure!==(critic?.status==='failed'))throw Error('Invalid V3 role counts');
 if(!flags.critic_enabled&&critic||flags.critic_enabled&&p.finalization_origin==='model'&&(!critic||critic.status!=='validated'||!counts.investigator_response))throw Error('Unreviewed V3 finalization');
 return b;
}
export function v3Summary(b:Obj){return {flags:b.flags,planning_passes:b.planning_passes,critic:b.critic,events:b.events.map((e:Obj)=>{const v=JSON.parse(e.body_canonical);return {kind:v.kind,ledger_anchor:v.ledger_anchor,data:v.data};}),limitation:b.scientific_validation};}
