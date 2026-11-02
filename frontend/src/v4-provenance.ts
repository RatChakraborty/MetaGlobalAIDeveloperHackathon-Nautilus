import {sha256} from '@noble/hashes/sha256';
import type {Investigation} from './records.ts';
type Obj=Record<string,any>;
const object=(v:unknown):v is Obj=>!!v&&typeof v==='object'&&!Array.isArray(v);
const closed=(v:unknown,k:string[])=>{if(!object(v)||Object.keys(v).sort().join()!==[...k].sort().join())throw Error('Unexpected V4 fields');return v;};
const hash=(s:string)=>Array.from(sha256(new TextEncoder().encode(s))).map(x=>x.toString(16).padStart(2,'0')).join('');
export function publicOnly(v:unknown){if(Array.isArray(v))v.forEach(publicOnly);else if(object(v)){for(const [k,x] of Object.entries(v)){if(/private|oracle|ground_truth|injected|credential|authorization|seed/i.test(k)||['faults','plant','truth'].includes(k))throw Error('Nonpublic V4 content');publicOnly(x);}}else if(typeof v==='number'&&!Number.isFinite(v))throw Error('Nonfinite V4 content');}
const shapes:Record<string,string[]>={safety_policy:['policy','policy_id','trial','predictive_margin_m','screen'],approval_request:['binding','state','audit'],approval_decision:['binding','state','audit'],execution:['policy','approval_request_id','observation_ref','execution','containment'],joint_fit:['schema_version','hypothesis','components','parameter_order','starts','parameter_start_cost','local_sensitivity_matrix','singular_values','rank','condition','conditional_correlation','coupled_directions','residuals','bound_hits','score_rule','elapsed_s','evidence_refs'],rejected_conclusion:['proposal','reason'],host_assessment:['proposal','assessment'],pending_finalization:['proposal'],critic_review:['entry'],investigator_response:['review_hash','proposal'],provider_dispatch:['role','transport_kind','request_number','max_output_tokens','request_bytes','previous_response_id'],provider_response:['role','entry']};
const policies=['simulation_enforced','simulation_operator_approved','simulation_advisory'];
export function readV4(input:unknown,record:Investigation):Obj{
 const e=closed(input,['schema_version','body_canonical','hash']);if(e.schema_version!=='nautilus.v4-provenance.v1'||typeof e.body_canonical!=='string'||new TextEncoder().encode(e.body_canonical).length>4_000_000||hash(e.body_canonical)!==e.hash)throw Error('Invalid V4 envelope');
 const b=closed(JSON.parse(e.body_canonical),['schema_version','session_id','policy','policy_id','joint_enabled','ledger_anchor','events','status']);publicOnly(b);
 if(b.schema_version!=='nautilus.v4-provenance-body.v1'||!policies.includes(b.policy)||typeof b.joint_enabled!=='boolean'||b.ledger_anchor!==record.events.at(-1)?.hash||!['RUNNING','AWAITING_OPERATOR','COMPLETED','FAILED'].includes(b.status)||!Array.isArray(b.events)||b.events.length>256)throw Error('Invalid V4 lifecycle');
 if(b.policy_id!==hash(JSON.stringify({mode:b.policy,offline_simulation_only:true,version:'v4.safety.1'})))throw Error('Invalid V4 policy identity');
 let prev:string|null=null,last=0;
 for(const [i,item] of b.events.entries()){
  const v=closed(item,['body_canonical','hash']);if(typeof v.body_canonical!=='string'||hash(v.body_canonical)!==v.hash)throw Error('Invalid V4 event hash');
  const ev=closed(JSON.parse(v.body_canonical),['index','kind','ledger_anchor','previous_hash','data']),idx=record.events.findIndex(e=>e.hash===ev.ledger_anchor);
  if(ev.index!==i||ev.previous_hash!==prev||idx<last||!shapes[ev.kind])throw Error('Invalid V4 event linkage');last=idx;prev=v.hash;const d=closed(ev.data,shapes[ev.kind]);publicOnly(d);
  const refs=new Set(record.events.slice(0,idx+1).filter(e=>e.type==='observation').map(e=>e.hash));
  if(ev.kind.startsWith('approval_')){
   const a=closed(d.binding,['schema_version','session_id','request_id','epoch','experiment','experiment_sha256','screen','screen_sha256','policy_id','budget','expires_at']);
   if(a.session_id!==b.session_id||a.policy_id!==b.policy_id||!['AWAITING_OPERATOR','APPROVED','DENIED','CANCELLED','EXPIRED','EXECUTING','COMPLETED','FAILED'].includes(d.state)||!Array.isArray(d.audit)||d.audit.length>8)throw Error('Invalid recorded approval');for(const row of d.audit)closed(row,['state','reason','at']);
  }else if(ev.kind==='joint_fit'){
   if(d.schema_version!=='nautilus.joint-fit.v4'||!Array.isArray(d.components)||d.components.length!==2||!Array.isArray(d.parameter_order)||d.parameter_order.length!==2||![0,1,2].includes(d.rank)||![1,2].includes(d.starts)||d.parameter_start_cost!==2*d.starts||!Array.isArray(d.local_sensitivity_matrix)||d.local_sensitivity_matrix.length>10000||d.local_sensitivity_matrix.some((r:unknown)=>!Array.isArray(r)||r.length!==2)||!Array.isArray(d.evidence_refs)||d.evidence_refs.some((x:string)=>!refs.has(x)))throw Error('Invalid V4 joint diagnostics');
  }else if(ev.kind==='execution'&&!refs.has(d.observation_ref))throw Error('Unknown executed observations');
 }
 return b;
}
export function v4Summary(b:Obj){return {policy:b.policy,status:b.status,joint_enabled:b.joint_enabled,approval_notice:'Replay records cannot authorize experiments. Only the trusted local operator CLI can resolve requests. Human approval is not safety certification.',events:b.events.map((e:Obj)=>{const v=JSON.parse(e.body_canonical),d=structuredClone(v.data);if(d.local_sensitivity_matrix){d.sensitivity_rows=d.local_sensitivity_matrix.length;delete d.local_sensitivity_matrix;}return {kind:v.kind,ledger_anchor:v.ledger_anchor,data:d};})};}
export function readV4Evaluation(input:unknown):Obj{
 const b=closed(input,['schema_version','development_only','planned','attempted','completed','policies','metrics','generation_gates','api_requests','source_fingerprint','manifest_fingerprint']);publicOnly(b);
 if(b.schema_version!=='nautilus.evaluation-summary.v4'||b.development_only!==true||!Number.isInteger(b.planned)||b.planned<1||b.planned>100||b.attempted>b.planned||b.completed>b.attempted||b.api_requests!==0||!Array.isArray(b.policies)||b.policies.length>7||!object(b.metrics))throw Error('Invalid offline V4 evaluation');
 for(const p of b.policies){
  if(!['passive','exhaustive','sequential_residual','fixed','random','greedy','zero_test'].includes(p)||!object(b.metrics[p]))throw Error('Unknown evaluation policy');
  const m=closed(b.metrics[p],['attempted','terminal_scored','infrastructure_or_unscored','valid_completion','host_termination','exact','partial','extra_attribution','incomplete_attribution','incorrect_set','family_exact','abstain','correct_abstention_under_finite_criterion','unnecessary_abstention_under_finite_criterion','primary_eligible','primary_exact','primary_wilson95','unconditional_exact_wilson95','mean_cause_precision','mean_cause_recall','parameter_tolerance_assessed','parameter_tolerance_passed','fits','parameter_starts','experiments','simulation_s','excursions','fit_failures','elapsed_s','by_stratum','by_difficulty']);
  if(m.attempted!==b.attempted||m.terminal_scored>b.attempted||m.exact>m.terminal_scored||m.primary_exact>m.primary_eligible)throw Error('Inconsistent evaluation denominators');
  if(!object(m.by_stratum)||!object(m.by_difficulty))throw Error('Missing evaluation breakdown');
  for(const group of Object.values(m.by_stratum).concat(Object.values(m.by_difficulty))){const g=closed(group,['cases','exact']);if(!Number.isInteger(g.cases)||g.cases<0||!Number.isInteger(g.exact)||g.exact<0||g.exact>g.cases)throw Error('Invalid stratum counts');}
 }
 if(Object.keys(b.metrics).some(k=>!b.policies.includes(k)&&!['paired_all','paired_primary'].includes(k)))throw Error('Unexpected evaluation metrics');
 return b;
}
