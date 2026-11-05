import {sha256} from '@noble/hashes/sha256';
import type {InvestigationHandoff} from './studio-handoff.ts';
import type {Observation,SimulationRequest} from './simulation-api.ts';
export type EngineeringContext={body_canonical:string;hash:string};
export type EngineeringEvidence={schema_version:string;session_id:string;actor:string;protocol_fingerprint:string;ledger_head:string;
 episodes:{evidence_ref:string;trace_hash:string;sample_count:number;observations:Observation[];sampling:string}[];
 hypotheses:InvestigationHandoff['hypotheses'];outcome:{kind:string;selected:string|null;competitive:string[];reasons:string[]};
 actions:{evidence_ref:string;type:string;actor:string;experiment:Record<string,unknown>|null}[];limitations:string[]};
const digest=(text:string)=>Array.from(sha256(new TextEncoder().encode(text))).map(b=>b.toString(16).padStart(2,'0')).join('');
export function readEngineeringContext(value:EngineeringContext):EngineeringEvidence{
 if(!value||Object.keys(value).sort().join()!=='body_canonical,hash'||typeof value.body_canonical!=='string'||value.body_canonical.length>50000||digest(value.body_canonical)!==value.hash)throw Error('Invalid engineering evidence hash');
 const b=JSON.parse(value.body_canonical) as EngineeringEvidence;
 if(Object.keys(b).sort().join()!==['schema_version','session_id','actor','protocol_fingerprint','ledger_head','episodes','hypotheses','outcome','actions','limitations'].sort().join()||b.schema_version!=='nautilus.engineering-context.v1'||!['deterministic_baseline','meta_muse'].includes(b.actor)||!/^[a-f0-9]{64}$/.test(b.session_id)||!Array.isArray(b.episodes)||!b.episodes.length||b.episodes.length>3)throw Error('Unsupported engineering evidence');
 if(b.session_id!==digest(JSON.stringify({actor:b.actor,head:b.ledger_head,protocol:b.protocol_fingerprint})))throw Error('Engineering session identity mismatch');
 const fields=['time_s','observed_y_m','observed_heading_rad','observed_yaw_rate_radps','port_command_n','starboard_command_n'].sort().join();
 for(const ep of b.episodes){if(Object.keys(ep).sort().join()!==['evidence_ref','trace_hash','sample_count','observations','sampling'].sort().join()||ep.observations.length<2||ep.observations.length>32)throw Error('Invalid public episode');let last=-1;for(const r of ep.observations){if(Object.keys(r).sort().join()!==fields||Object.values(r).some(v=>typeof v!=='number'||!Number.isFinite(v))||r.time_s<=last)throw Error('Six ordered public channels required');last=r.time_s;}}
 return b;
}
export function engineeringHandoff(context:EngineeringContext):InvestigationHandoff{
 const b=readEngineeringContext(context),refs=b.episodes.map(e=>e.evidence_ref);
 return {schema_version:'nautilus.studio-handoff.v1',reproducibility:{run_id:b.session_id,source_kind:b.actor,ledger_head:b.ledger_head,events:b.actions.length},observations:{episodes:refs.length,evidence_refs:refs,max_abs_observed_y_m:Math.max(...b.episodes.flatMap(e=>e.observations.map(r=>Math.abs(r.observed_y_m))))},hypotheses:b.hypotheses.slice(0,4),conclusion:{diagnosis:b.outcome.selected,confidence:b.outcome.kind,ambiguity_statement:(b.outcome.reasons??[]).join('; ').slice(0,200),evidence_refs:refs,status:'recorded_conclusion_not_proof'},limitations:b.limitations};
}
export type EngineeringBinding={context:EngineeringContext;request:SimulationRequest;publicEvidence?:Record<string,unknown>};
