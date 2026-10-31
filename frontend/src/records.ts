import {sha256} from '@noble/hashes/sha256';
export const CHANNELS=['time_s','observed_y_m','observed_heading_rad','observed_yaw_rate_radps','port_command_n','starboard_command_n'] as const;
export type Observation=Record<typeof CHANNELS[number],number>;
export type Event={index:number;type:string;previous_hash:string|null;observations?:Observation[];report?:Fit;[key:string]:unknown};
export type Fit={hypothesis:string;parameters:Record<string,number>;weighted_rmse?:number;physical_wrms?:number;command_wrms?:number;penalized_score?:number;converged:boolean;warnings?:string[];evidence_refs?:string[];[key:string]:unknown};
export type RecordFile={schema_version:'nautilus.public-investigation.v1';run_id:string;source_kind:string;disclosure:string;recorded_conclusion?:{diagnosis?:{hypothesis?:string|null;evidence_refs?:string[]};confidence?:string;stop_reason?:string}|null;ledger:{hash:string;body_canonical:string}[]};
export type Investigation={file:RecordFile;events:(Event&{hash:string})[]};
export type Visual={schema_version:'nautilus.visualization-only.v1';run_id:string;label:string;reference?:{cable_length_m:number;cable_half_width_m:number;source:string}|null;samples:{time_s:number;x_m:number;y_m:number;heading_rad:number}[]};
const hex=(bytes:Uint8Array)=>Array.from(bytes).map(b=>b.toString(16).padStart(2,'0')).join('');
const object=(x:unknown):x is Record<string,unknown>=>typeof x==='object'&&x!==null&&!Array.isArray(x);
export async function readRecord(input:unknown):Promise<Investigation>{
 if(!object(input)||input.schema_version!=='nautilus.public-investigation.v1'||typeof input.run_id!=='string'||typeof input.source_kind!=='string'||typeof input.disclosure!=='string'||!Array.isArray(input.ledger)||!input.ledger.length)throw Error('Unsupported investigation record');
 if(Object.keys(input).some(k=>!['schema_version','run_id','source_kind','disclosure','ledger','recorded_conclusion'].includes(k)))throw Error('Unexpected top-level data; use the public exporter');
 const events:Investigation['events']=[];const refs=new Set<string>();let previous:string|null=null;
 for(const [index,item] of input.ledger.entries()){
  if(!object(item)||typeof item.hash!=='string'||typeof item.body_canonical!=='string')throw Error('Invalid ledger envelope');
  const hash=hex(sha256(new TextEncoder().encode(item.body_canonical)));
  const event:Event=JSON.parse(item.body_canonical);
  assertPublic(event);
  if(!['observation','fit','operator_note','safety','finalized','rejected','fit_failure','request'].includes(event.type))throw Error('Unsupported evidence event');
  if(event.type==='fit'&&(!object(event.report)||typeof event.report.hypothesis!=='string'||!object(event.report.parameters)||typeof event.report.converged!=='boolean'))throw Error('Invalid numerical fit report');
  if(hash!==item.hash||event.index!==index||event.previous_hash!==previous)throw Error('Evidence chain verification failed');
  if(event.type==='observation'){
   if(!Array.isArray(event.observations)||event.observations.length<2)throw Error('Missing observation channels');
   let last=-Infinity;
   for(const row of event.observations){if(Object.keys(row).sort().join()!==[...CHANNELS].sort().join()||!CHANNELS.every(k=>Number.isFinite(row[k]))||row.time_s<=last)throw Error('Invalid public observations');last=row.time_s;}
   if(event.observations[0].time_s!==0)throw Error('Episode reset missing');refs.add(hash);
  }
  const fitRefs=event.report?.evidence_refs??event.evidence_refs;
  if(fitRefs!==undefined&&(!Array.isArray(fitRefs)||fitRefs.some(r=>!refs.has(r))))throw Error('Unknown fit evidence reference');
  if(event.type==='finalized'){
   const d=event.diagnosis as {evidence_refs?:string[]};
   if(!d||!Array.isArray(d.evidence_refs)||d.evidence_refs.some(r=>!refs.has(r)))throw Error('Unknown conclusion reference');
  }
  events.push({...event,hash});previous=hash;
 }
 if(!refs.size)throw Error('No public observation episodes');
 if(input.recorded_conclusion){assertPublic(input.recorded_conclusion);const c=input.recorded_conclusion as {diagnosis?:{evidence_refs?:string[]}};if(!Array.isArray(c.diagnosis?.evidence_refs)||c.diagnosis.evidence_refs.some(r=>!refs.has(r)))throw Error('Unknown conclusion reference');}
 return {file:input as unknown as RecordFile,events};
}
export function readVisual(input:unknown,runId:string):Visual{
 if(!object(input)||input.schema_version!=='nautilus.visualization-only.v1'||input.run_id!==runId||!Array.isArray(input.samples)||input.samples.length<2)throw Error('Visualization file does not match this run');
 if(Object.keys(input).some(k=>!['schema_version','run_id','label','samples','reference'].includes(k)))throw Error('Unexpected visualization fields');
 if(input.reference!=null){const ref=input.reference;if(!object(ref)||Object.keys(ref).sort().join()!==['cable_length_m','cable_half_width_m','source'].sort().join()||typeof ref.source!=='string'||![ref.cable_length_m,ref.cable_half_width_m].every(v=>typeof v==='number'&&Number.isFinite(v)&&v>0))throw Error('Invalid recorded reference dimensions');}
 let previous=-Infinity;
 for(const row of input.samples){if(!object(row)||Object.keys(row).sort().join()!==['heading_rad','time_s','x_m','y_m'].sort().join()||!['time_s','x_m','y_m','heading_rad'].every(k=>typeof row[k]==='number'&&Number.isFinite(row[k]))||Number(row.time_s)<=previous)throw Error('Invalid planar trajectory');previous=Number(row.time_s);}
 return input as unknown as Visual;
}
export function fitsAt(events:Investigation['events'],index:number){const fits=new Map<string,Fit>();for(const event of events.slice(0,index+1)){if(event.type==='observation')fits.clear();if(event.type==='fit'&&event.report)fits.set(event.report.hypothesis,event.report);}return [...fits.values()];}
export function sampleAt<T extends {time_s:number}>(rows:T[],time:number):T{let lo=0,hi=rows.length-1;while(lo<hi){const mid=Math.ceil((lo+hi)/2);if(rows[mid].time_s<=time)lo=mid;else hi=mid-1;}return rows[lo];}

function assertPublic(value:unknown){if(Array.isArray(value))value.forEach(assertPublic);else if(object(value))for(const [key,item] of Object.entries(value)){if(['private','oracle','injected','ground_truth'].some(token=>key.toLowerCase().includes(token))||['truth','faults','plant','controller','correct','true_excursion','true_final_speed_mps'].includes(key))throw Error('Private evaluator content is not public evidence');assertPublic(item);}}

export function parameterUnit(key:string):string{return ({current_y:'m/s',heading_bias_rad:'rad',actuator_tau_s:'s',thrust_deadzone_n:'N',lookahead_m:'m',heading_kp:'N·m/rad',port_efficiency:'1',starboard_efficiency:'1',common_thrust_scale:'1',drag_surge_scale:'1',drag_sway_scale:'1',drag_yaw_scale:'1',uniform_drag_scale:'1'} as Record<string,string>)[key]??'n/a';}

export function planarPose(rows:Visual['samples'],time:number){const sample=sampleAt(rows,time);return {x:sample.x_m,y:0,z:-sample.y_m,heading:sample.heading_rad};}
