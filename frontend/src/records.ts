import {readController,readControllerEvent,type ControllerMetadata} from './controller.ts';
import {sha256} from '@noble/hashes/sha256';
export const CHANNELS=['time_s','observed_y_m','observed_heading_rad','observed_yaw_rate_radps','port_command_n','starboard_command_n'] as const;
export type Observation=Record<typeof CHANNELS[number],number>;
export type Event={index:number;type:string;previous_hash:string|null;observations?:Observation[];report?:Fit;[key:string]:unknown};
export type Fit={hypothesis:string;parameters:Record<string,number>;weighted_rmse?:number;physical_wrms?:number;command_wrms?:number;penalized_score?:number;converged:boolean;warnings?:string[];evidence_refs?:string[];[key:string]:unknown};
export type RecordFile={schema_version:'nautilus.public-investigation.v1'|'nautilus.public-investigation.v2';run_id:string;source_kind:string;disclosure:string;recorded_conclusion?:{diagnosis?:{hypothesis?:string|null;evidence_refs?:string[]};confidence?:string;stop_reason?:string}|null;ledger:{hash:string;body_canonical:string}[]};
export type Investigation={file:RecordFile;events:(Event&{hash:string})[]};
export type Visual={schema_version:'nautilus.visualization-only.v1'|'nautilus.visualization-only.v2'|'nautilus.visualization-only.v3';episode_ref?:string;controller?:ControllerMetadata;run_id:string;label:string;reference?:{cable_length_m:number;cable_half_width_m:number;source:string}|null;samples:{time_s:number;x_m:number;y_m:number;heading_rad:number}[]};
const hex=(bytes:Uint8Array)=>Array.from(bytes).map(b=>b.toString(16).padStart(2,'0')).join('');
const object=(x:unknown):x is Record<string,unknown>=>typeof x==='object'&&x!==null&&!Array.isArray(x);
export async function readRecord(input:unknown):Promise<Investigation>{
 if(!object(input)||!['nautilus.public-investigation.v1','nautilus.public-investigation.v2'].includes(String(input.schema_version))||typeof input.run_id!=='string'||typeof input.source_kind!=='string'||typeof input.disclosure!=='string'||!Array.isArray(input.ledger)||!input.ledger.length)throw Error('Unsupported investigation record');
 if(Object.keys(input).some(k=>!['schema_version','run_id','source_kind','disclosure','ledger','recorded_conclusion'].includes(k)))throw Error('Unexpected top-level data; use the public exporter');
 const events:Investigation['events']=[];const refs=new Set<string>();let previous:string|null=null;let hasContext=false;
 for(const [index,item] of input.ledger.entries()){
  if(!object(item)||typeof item.hash!=='string'||typeof item.body_canonical!=='string')throw Error('Invalid ledger envelope');
  const hash=hex(sha256(new TextEncoder().encode(item.body_canonical)));
  const event:Event=JSON.parse(item.body_canonical);
  assertPublic(event);
  if(event.type==='controller_context'){if(input.schema_version!=='nautilus.public-investigation.v2'||hasContext||events.some(e=>!['observation','operator_note'].includes(e.type)))throw Error('Invalid controller initialization event');assertPublic(readControllerEvent(event));hasContext=true;}
  if(!['controller_context','observation','fit','operator_note','safety','finalized','rejected','fit_failure','request'].includes(event.type))throw Error('Unsupported evidence event');
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
 if(!object(input)||!['nautilus.visualization-only.v1','nautilus.visualization-only.v2','nautilus.visualization-only.v3'].includes(String(input.schema_version))||input.run_id!==runId||!Array.isArray(input.samples)||input.samples.length<2)throw Error('Visualization file does not match this run');
 if(Object.keys(input).some(k=>!['schema_version','run_id','label','samples','reference',...(input.schema_version==='nautilus.visualization-only.v2'?['controller']:input.schema_version==='nautilus.visualization-only.v3'?['controller','episode_ref']:[])].includes(k)))throw Error('Unexpected visualization fields');
 if(input.reference!=null){const ref=input.reference;if(!object(ref)||Object.keys(ref).sort().join()!==['cable_length_m','cable_half_width_m','source'].sort().join()||typeof ref.source!=='string'||![ref.cable_length_m,ref.cable_half_width_m].every(v=>typeof v==='number'&&Number.isFinite(v)&&v>0))throw Error('Invalid recorded reference dimensions');}
 if(input.schema_version==='nautilus.visualization-only.v2'||input.schema_version==='nautilus.visualization-only.v3'&&input.controller!==undefined)readController(input.controller);
 if(input.schema_version==='nautilus.visualization-only.v3'&&(typeof input.episode_ref!=='string'||!input.episode_ref))throw Error('Explicit episode reference required');
 let previous=-Infinity;
 for(const row of input.samples){if(!object(row)||Object.keys(row).sort().join()!==['heading_rad','time_s','x_m','y_m'].sort().join()||!['time_s','x_m','y_m','heading_rad'].every(k=>typeof row[k]==='number'&&Number.isFinite(row[k]))||Number(row.time_s)<=previous)throw Error('Invalid planar trajectory');previous=Number(row.time_s);}
 return input as unknown as Visual;
}
export function fitsAt(events:Investigation['events'],index:number){const fits=new Map<string,Fit>();for(const event of events.slice(0,index+1)){if(event.type==='observation')fits.clear();if(event.type==='fit'&&event.report)fits.set(event.report.hypothesis,event.report);}return [...fits.values()];}
export function sampleAt<T extends {time_s:number}>(rows:T[],time:number):T{let lo=0,hi=rows.length-1;while(lo<hi){const mid=Math.ceil((lo+hi)/2);if(rows[mid].time_s<=time)lo=mid;else hi=mid-1;}return rows[lo];}

function assertPublic(value:unknown){if(Array.isArray(value))value.forEach(assertPublic);else if(object(value))for(const [key,item] of Object.entries(value)){if(['private','oracle','injected','ground_truth'].some(token=>key.toLowerCase().includes(token))||['truth','faults','plant','controller','correct','true_excursion','true_final_speed_mps'].includes(key))throw Error('Private evaluator content is not public evidence');assertPublic(item);}}

export function parameterUnit(key:string):string{return ({current_y:'m/s',heading_bias_rad:'rad',actuator_tau_s:'s',thrust_deadzone_n:'N',lookahead_m:'m',heading_kp:'N·m/rad',port_efficiency:'1',starboard_efficiency:'1',common_thrust_scale:'1',drag_surge_scale:'1',drag_sway_scale:'1',drag_yaw_scale:'1',uniform_drag_scale:'1'} as Record<string,string>)[key]??'n/a';}

export function planarPose(rows:Visual['samples'],time:number){const sample=sampleAt(rows,time);return {x:sample.x_m,y:0,z:-sample.y_m,heading:sample.heading_rad};}

export function bindController(visual:Visual,record:Investigation){
 const c=visual.controller;if(!c)return visual;
 const event=record.events.find(e=>e.type==='controller_context');
 if(!event||visual.run_id!==record.file.run_id||c.context_hash!==event.context_hash||c.controller_id!==event.controller_id||c.source_sha256!==event.source_sha256)throw Error('Visualization controller differs from public provenance');
 const context=JSON.parse(event.context_canonical as string);
 if(c.implementation_version!==context.implementation_version||Object.entries(c.configuration).some(([k,v])=>context.declared_configuration[k]?.value!==v))throw Error('Visualization configuration differs from approved context');
 return visual;
}
