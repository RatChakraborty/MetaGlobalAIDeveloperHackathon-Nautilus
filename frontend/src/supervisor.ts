import {sha256} from '@noble/hashes/sha256';
import type {Investigation,Visual,Observation} from './records.ts';
import {alignVisualization,matchingEpisode} from './replay-math.ts';
export type SupervisorEvent={id:string;type:string;disclosure:'public-derived'|'visualization-only';run_id:string;episode_ref:string;episode_index:number;investigation_index:number;time_s:number;source_field:string;rule:string;derivation_version:string;threshold:number|null;supporting_value:number;units:string;rule_source_ref:string;description:string};
export type SupervisorLog={events:SupervisorEvent[];rules:Record<string,unknown>;raw:unknown};
export const DESCRIPTIONS={observed_cross_track_warning:'Observed lateral analysis warning; not a verified physical corridor breach.',command_saturation:'Requested command reached the declared limit; not measured actuator saturation.',guard_stop:'Recorded enforced guard intervention; physical vehicle stopping is not established.',corridor_breach:'Recorded simulator-truth corridor entry; visualization only, never investigator evidence.'};
export const escapeText=(v:unknown)=>String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
export const object=(v:unknown):v is Record<string,unknown>=>typeof v==='object'&&v!==null&&!Array.isArray(v);
export function closed(v:unknown,keys:string[]){if(!object(v)||Object.keys(v).sort().join()!==[...keys].sort().join())throw Error('Unexpected derived-event fields');return v;}
const number=(v:unknown):v is number=>typeof v==='number'&&Number.isFinite(v);
const digest=(v:string)=>Array.from(sha256(new TextEncoder().encode(v))).map(b=>b.toString(16).padStart(2,'0')).join('');
function unpack(item:unknown,record:Investigation,visualOnly:boolean):SupervisorEvent{
 const packed=closed(item,['id','body_canonical']);if(typeof packed.body_canonical!=='string'||digest(packed.body_canonical)!==packed.id)throw Error('Derived-event hash mismatch');
 const v=closed(JSON.parse(packed.body_canonical),['type','disclosure','run_id','episode_ref','episode_index','investigation_index','time_s','source_field','rule','derivation_version','threshold','supporting_value','units','rule_source_ref','description']);
 if(v.run_id!==record.file.run_id||v.derivation_version!=='nautilus.supervisor.v1'||v.disclosure!==(visualOnly?'visualization-only':'public-derived')||typeof v.type!=='string'||!Object.hasOwn(DESCRIPTIONS,v.type)||v.description!==DESCRIPTIONS[v.type as keyof typeof DESCRIPTIONS]||!number(v.time_s)||!number(v.supporting_value)||(v.threshold!==null&&!number(v.threshold)))throw Error('Invalid derived-event scope or values');
 const episodes=record.events.filter(e=>e.type==='observation'),ep=episodes[Number(v.episode_index)];if(!Number.isInteger(v.episode_index)||!ep||ep.hash!==v.episode_ref||ep.index!==v.investigation_index||!ep.observations?.some(r=>r.time_s===v.time_s))throw Error('Derived event has no matching discrete episode sample');
 return {...v,id:packed.id} as SupervisorEvent;
}
export function readSupervisor(input:unknown,record:Investigation):SupervisorLog{
 const v=closed(input,['schema_version','run_id','source_head','rules','declared_command_limit_n','events']);
 if(v.schema_version!=='nautilus.supervisor-events.v1'||v.run_id!==record.file.run_id||v.source_head!==record.events.at(-1)?.hash||!Array.isArray(v.events))throw Error('Supervisor source mismatch');
 const rules=closed(v.rules,['version','warning_m','rearm_m','saturation_tolerance_n','saturation_rearm_n']);
 if(rules.version!=='nautilus.analysis-thresholds.v1'||!['warning_m','rearm_m','saturation_tolerance_n','saturation_rearm_n'].every(k=>number(rules[k]))||Number(rules.rearm_m)<0||Number(rules.rearm_m)>=Number(rules.warning_m)||Number(rules.warning_m)>10||Number(rules.saturation_tolerance_n)<0||Number(rules.saturation_tolerance_n)>=Number(rules.saturation_rearm_n)||Number(rules.saturation_rearm_n)>1)throw Error('Invalid analysis thresholds');
 const contextEvent=record.events.find(e=>e.type==='controller_context'),context=contextEvent?JSON.parse(contextEvent.context_canonical as string):null;
 const bounds=context?.interface.action_bounds_n,limit=bounds&&bounds[0]===-bounds[1]?bounds[1]:null;if(v.declared_command_limit_n!==limit)throw Error('Command limit lacks declared provenance');
 const episodes=record.events.filter(e=>e.type==='observation'),samples=new Map(episodes.map(e=>[e.hash,new Map(e.observations!.map(r=>[r.time_s,r]))]));
 const events=v.events.map(item=>unpack(item,record,false));const ids=new Set<string>();let previous:SupervisorEvent|null=null;
 for(const e of events){if(ids.has(e.id))throw Error('Duplicate derived event');ids.add(e.id);if(previous&&(e.investigation_index<previous.investigation_index||(e.investigation_index===previous.investigation_index&&(e.time_s<previous.time_s||(e.time_s===previous.time_s&&e.source_field<previous.source_field)))))throw Error('Derived event order mismatch');previous=e;const row=samples.get(e.episode_ref)!.get(e.time_s)!;
  if(e.type==='observed_cross_track_warning'){if(e.source_field!=='observed_y_m'||e.rule!=='observed-warning.v1'||e.rule_source_ref!==rules.version||e.threshold!==rules.warning_m||e.supporting_value!==row.observed_y_m||Math.abs(row.observed_y_m)<Number(rules.warning_m)||e.units!=='m')throw Error('Warning does not match observed evidence');}
  else if(e.type==='command_saturation'){if(!['port_command_n','starboard_command_n'].includes(e.source_field)||limit===null||e.threshold!==limit||e.rule!=='command-limit.v1'||e.rule_source_ref!==contextEvent?.hash||e.units!=='N'||e.supporting_value!==row[e.source_field as keyof Observation]||Math.abs(e.supporting_value)<limit-Number(rules.saturation_tolerance_n))throw Error('Saturation lacks recorded command support');}
  else if(e.type==='guard_stop'){const execution=episodes[e.episode_index].execution as Record<string,unknown>|undefined;if(execution?.mode!=='simulation_enforced'||execution.guard_intervened!==true||execution.stop_reason!=='observed_guard'||execution.guard_time_s!==e.time_s||e.supporting_value!==e.time_s||e.threshold!==null||e.rule!=='recorded-guard.v1'||e.source_field!=='execution.guard_time_s'||e.rule_source_ref!==e.episode_ref||e.units!=='s')throw Error('Actual guard intervention not established');}
  else throw Error('Truth markers cannot enter public supervisor evidence');
 }
 return {events,rules,raw:input};
}
export function readVisualEvents(input:unknown,record:Investigation,visual:Visual):SupervisorEvent[]{
 const v=closed(input,['schema_version','run_id','episode_ref','visual_canonical','events']);const ep=matchingEpisode(record,visual);if(!ep||v.schema_version!=='nautilus.visualization-events.v1'||v.run_id!==record.file.run_id||v.episode_ref!==ep.hash||typeof v.visual_canonical!=='string'||!Array.isArray(v.events))throw Error('Visualization event source mismatch');
 const source=closed(JSON.parse(v.visual_canonical),['samples','reference']);if(!Array.isArray(source.samples)||source.samples.length!==visual.samples.length||source.samples.some((s,i)=>!object(s)||['time_s','x_m','y_m','heading_rad'].some(k=>s[k]!==visual.samples[i][k as keyof Visual['samples'][number]]))||JSON.stringify(source.reference===null?null:source.reference&&object(source.reference)?[source.reference.cable_length_m,source.reference.cable_half_width_m,source.reference.source]:null)!==JSON.stringify(visual.reference?[visual.reference.cable_length_m,visual.reference.cable_half_width_m,visual.reference.source]:null))throw Error('Visualization companion poses changed');
 const events=v.events.map(item=>unpack(item,record,true)),seen=new Set<string>();let last=-Infinity;
 for(const e of events){const row=visual.samples.find(r=>r.time_s===e.time_s);if(seen.has(e.id)||e.time_s<last||e.episode_ref!==ep.hash||e.type!=='corridor_breach'||e.source_field!=='y_m'||e.rule!=='truth-corridor-entry.v1'||e.rule_source_ref!=='recorded-corridor'||e.units!=='m'||e.threshold!==visual.reference?.cable_half_width_m||!row||e.supporting_value!==row.y_m||Math.abs(row.y_m)<=e.threshold)throw Error('Truth marker lacks recorded support');seen.add(e.id);last=e.time_s;}
 return events;
}
export function eventsMarkup(events:SupervisorEvent[],scope:string){return `<p>${escapeText(scope)}</p>${events.length?events.map(e=>`<button class="button secondary" data-supervisor="${e.id}" title="${escapeText(e.disclosure)} · evidence ${escapeText(e.episode_ref)} · event ${e.id}">${escapeText(e.type)} · episode ${e.episode_index+1} · ${e.time_s} s · ${escapeText(e.source_field)} · ${e.threshold===null?'recorded intervention':`${e.threshold} ${escapeText(e.units)}`}</button><p class="muted">${escapeText(e.description)}</p>`).join(''):'<p>No recorded events in this companion.</p>'}`;}
export function eventNavigation(event:SupervisorEvent,record:Investigation,visual:Visual|null){
 const ep=record.events.find(e=>e.hash===event.episode_ref&&e.index===event.investigation_index&&e.type==='observation');
 if(event.run_id!==record.file.run_id||!ep?.observations?.some(r=>r.time_s===event.time_s))throw Error('Event navigation source mismatch');
 return {index:ep.index,time:event.time_s,trajectory:!!visual&&matchingEpisode(record,visual)?.hash===ep.hash};
}
