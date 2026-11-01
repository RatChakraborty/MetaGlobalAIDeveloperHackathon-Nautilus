import {sha256} from '@noble/hashes/sha256';
import type {Investigation} from './records.ts';
const object=(v:unknown):v is Record<string,unknown>=>typeof v==='object'&&v!==null&&!Array.isArray(v);
const closed=(v:unknown,keys:string[])=>{if(!object(v)||Object.keys(v).sort().join()!==[...keys].sort().join())throw Error('Unexpected Muse provenance fields');return v;};
const nonnegative=(v:unknown,integer=false)=>{if(typeof v!=='number'||!Number.isFinite(v)||v<0||(integer&&!Number.isInteger(v)))throw Error('Invalid Muse accounting');};
const text=(v:unknown,max=100)=>{if(typeof v!=='string'||!v.length||v.length>max)throw Error('Invalid Muse text');};
const hash=(s:string)=>Array.from(sha256(new TextEncoder().encode(s))).map(x=>x.toString(16).padStart(2,'0')).join('');
const tools=['propose_hypothesis','request_experiment','get_fit_report','finalize','unknown'];
const reasons=['model_finalized','model_call_limit','wall_deadline','action_limit','output_token_limit','request_byte_limit','provider_error','model_mismatch','incomplete_response','provider_token_overrun','input_token_limit','no_tool_call','parallel_calls_rejected','call_id_collision','invalid_call_limit'];
export type MuseProvenance={provider:string;model:string;model_requests:{latency_s:number;usage:Record<string,number>;status:string;function_calls:number}[];actions:{call_id:string;name:string;accepted:boolean;ledger_before:string;ledger_after:string}[];termination_reason:string;finalization_origin:string;retries:number;errors:string[];elapsed_s:number;[key:string]:unknown};
export function readMuseProvenance(input:unknown,record:Investigation):MuseProvenance{
 const root=closed(input,['schema_version','body_canonical','hash']);
 if(root.schema_version!=='nautilus.muse-provenance.v1'||typeof root.body_canonical!=='string'||root.body_canonical.length>200000||hash(root.body_canonical)!==root.hash)throw Error('Invalid Muse provenance hash');
 const b=closed(JSON.parse(root.body_canonical),['provider','model','initial_observation_ref','ledger_anchor','model_requests','actions','errors','retries','termination_reason','finalization_origin','elapsed_s','output_tokens_reserved','request_bytes','remaining','configuration_evaluation','cost']);
 const hashes=record.events.map(e=>e.hash),last=record.events.at(-1)!;
 if(b.provider!=='meta'||b.initial_observation_ref!==hashes[0]||b.ledger_anchor!==last.hash||last.type!=='finalized'||b.configuration_evaluation!=='disabled')throw Error('Muse provenance does not match investigation');
 text(b.model);if(!reasons.includes(String(b.termination_reason))||!['model','host'].includes(String(b.finalization_origin))||(b.finalization_origin==='model')!==(b.termination_reason==='model_finalized'))throw Error('Invalid Muse termination');
 if(b.finalization_origin==='host'&&(last.confidence!=='abstain'||typeof last.stop_reason!=='string'||!last.stop_reason.startsWith('HOST-ENFORCED ABSTENTION:')))throw Error('Host abstention must be explicit');
 for(const k of ['elapsed_s','output_tokens_reserved','request_bytes','retries'])nonnegative(b[k],k!=='elapsed_s');
 if(!Array.isArray(b.model_requests)||b.model_requests.length>32||!Array.isArray(b.actions)||b.actions.length>128)throw Error('Invalid Muse counts');
 for(const request of b.model_requests){const r=closed(request,['latency_s','usage','status','function_calls']);nonnegative(r.latency_s);nonnegative(r.function_calls,true);if(!['completed','incomplete','error'].includes(String(r.status))||!object(r.usage)||Object.keys(r.usage).some(k=>!['input_tokens','output_tokens','total_tokens'].includes(k)))throw Error('Invalid Muse usage');Object.values(r.usage).forEach(v=>nonnegative(v,true));}
 const ids=new Set();let previous=0;
 for(const action of b.actions){const a=closed(action,['call_id','name','accepted','ledger_before','ledger_after']);text(a.call_id,20000);if(ids.has(a.call_id)||!tools.includes(String(a.name))||typeof a.accepted!=='boolean')throw Error('Invalid Muse action');ids.add(a.call_id);const before=hashes.indexOf(String(a.ledger_before)),after=hashes.indexOf(String(a.ledger_after));if(before<previous||after<before)throw Error('Invalid Muse action chain');previous=after;}
 if(b.finalization_origin==='model'){const a=b.actions.at(-1);if(!a||a.name!=='finalize'||a.accepted!==true||a.ledger_after!==last.hash)throw Error('Missing model finalization');}
 const remaining=closed(b.remaining,['fit_calls','optimization_attempts','experiments','time_s']);Object.values(remaining).forEach(v=>nonnegative(v));
 if(!Array.isArray(b.errors)||b.errors.some(e=>typeof e!=='string'||!(/^(http_[0-9]{3}|credential_echo|network_or_timeout|credential_unavailable|malformed_response|response_size_limit|request_size_limit|provider_error)$/.test(e))))throw Error('Invalid Muse errors');
 const cost=closed(b.cost,['currency','amount','limitation']);if(cost.currency!==null||cost.amount!==null||cost.limitation!=='No verified provider tariff; token/request ceilings bound usage, not a dollar estimate.')throw Error('Unsupported cost claim');
 return b as MuseProvenance;
}
export function museSummary(p:MuseProvenance){return {provider:p.provider,model:p.model,model_requests:p.model_requests.length,tool_calls:p.model_requests.reduce((n,r)=>n+r.function_calls,0),unique_action_attempts:p.actions.length,host_finalization_actions:p.finalization_origin==='host'?1:0,actions:p.actions.map(a=>({name:a.name,accepted:a.accepted})),usage:p.model_requests.map(r=>r.usage),latency_s:p.model_requests.map(r=>r.latency_s),termination:p.termination_reason,finalization_origin:p.finalization_origin,retries:p.retries,errors:p.errors,limitation:'Hash linkage detects inconsistency, not authentic model authorship. No full hidden reasoning is recorded.'};}
