import {readRecord,CHANNELS,parameterUnit,type Investigation} from './records.ts';
import {readHostEvaluation,type HostEvaluation} from './post-evaluation.ts';
import {readSupervisor,type SupervisorLog} from './supervisor.ts';
import {CONTROLLER_PARAMETERS} from './controller.ts';
const unavailable='Not available in the recorded investigation';
const data=(v:unknown)=>JSON.stringify(v??unavailable).replace(/[^\p{L}\p{N} .,\-]/gu,c=>'&#'+c.codePointAt(0)+';');
const line=(label:string,v:unknown)=>'- '+label+': '+data(v)+'\n';
function context(record:Investigation){const e=record.events.find(e=>e.type==='controller_context');return e?JSON.parse(e.context_canonical as string):null;}
export function configurationDiff(record:Investigation,host:HostEvaluation|null){
 if(!host?.proposal)return null;
 const p=host.proposal,ctx=context(record),comparison=host.comparison as (HostEvaluation['comparison']&{approved_differences?:Record<string,{baseline:number;candidate:number;unit:string}>;baseline:{configuration_id?:string;controller_id?:string};candidate:{configuration_id?:string}})|null;
 const change=comparison?.approved_differences?.[p.parameter],declared=ctx?.declared_configuration[p.parameter];
 const before=comparison?(change?.baseline??null):(declared?.value??null);
 return {schema_version:'nautilus.config-diff.v1',investigation_id:record.events.at(-1)!.hash,
  controller_id:comparison?.baseline.controller_id??ctx?.controller_id??null,
  baseline_configuration_fingerprint:comparison?.baseline.configuration_id??null,
  baseline_source:comparison?'approved_host_evaluation':declared?'declared_controller_context':'not_recorded',
  parameter:p.parameter,baseline_value:before,candidate_value:p.value,
  units:CONTROLLER_PARAMETERS[p.parameter as keyof typeof CONTROLLER_PARAMETERS][0],rationale:p.rationale,evidence_refs:p.evidence_refs,
  host_status:host.status,evaluated:!!comparison,candidate_configuration_fingerprint:comparison?.candidate.configuration_id??null,
  conditions:comparison?.conditions??[],limitations:[...host.limitations,...(comparison?.limitations??[]),...(before===null?['Baseline value is unavailable; no before-value is invented.']:[])],
  operator_review_required:true,deployment_ready:false};
}
function residuals(value:unknown){
 if(!Array.isArray(value))return null;
 return value.map(episode=>{if(!Array.isArray(episode))throw Error('Invalid recorded residual diagnostics');return episode.map(channel=>{if(!channel||typeof channel!=='object')throw Error('Invalid residual channel');return Object.fromEntries(['mean','rms','lag1'].map(k=>{const n=channel[k];if(n!==null&&(typeof n!=='number'||!Number.isFinite(n)))throw Error('Invalid recorded residual value');return [k,n];}));});});
}
function markdown(record:Investigation,host:HostEvaluation|null,supervisor:SupervisorLog|null){
 const ctx=context(record),conclusion=record.file.recorded_conclusion??record.events.filter(e=>e.type==='finalized').at(-1);
 let out='# Nautilus investigation report\n\n';
 out+=line('Investigation reference',record.events.at(-1)?.hash)+line('Run',record.file.run_id)+line('Observation source',record.file.source_kind)+line('Available public channels',CHANNELS);
 out+=line('Controller',ctx?{controller_id:ctx.controller_id,implementation_version:ctx.implementation_version,source_sha256:ctx.source.sha256,source_revision:ctx.source.revision,context_hash:record.events.find(e=>e.type==='controller_context')?.context_hash}:null);
 out+=line('Declared assumptions and unknowns',ctx?.unknowns)+ '\n## Recorded evidence\n\n';
 let episodes=0,fits=0;
 for(const e of record.events){
  if(e.type==='observation'){episodes++;const rows=e.observations!;out+=line('Observed episode',{episode:episodes,evidence_ref:e.hash,samples:rows.length,local_end_s:rows.at(-1)!.time_s,max_abs_observed_y_m:rows.reduce((m,r)=>Math.max(m,Math.abs(r.observed_y_m)),0)});
   if(e.execution){const execution=e.execution as Record<string,unknown>;out+=line('Recorded execution',Object.fromEntries(['mode','guard_intervened','would_guard_trigger_s','guard_time_s','stop_reason','elapsed_s','observed_excursion','fallback','fallback_safety','stopped_vehicle'].filter(k=>Object.hasOwn(execution,k)).map(k=>[k,execution[k]])));}
  }
  if(e.type==='operator_note')out+=line('Operator note (untrusted data)',e.text);
  if(e.type==='fit'&&e.report){fits++;const f=e.report;for(const k of ['weighted_rmse','physical_wrms','command_wrms','penalized_score']){const v=f[k];if(v!==undefined&&v!==null&&(typeof v!=='number'||!Number.isFinite(v)))throw Error('Invalid recorded fit metric');}for(const [k,v] of Object.entries(f.parameters))if(parameterUnit(k)!=='n/a'&&(typeof v!=='number'||!Number.isFinite(v)))throw Error('Invalid recorded fit parameter');out+=line('Requested numerical fit',{hypothesis:f.hypothesis,parameters:Object.fromEntries(Object.entries(f.parameters).filter(([k])=>parameterUnit(k)!=='n/a')),method:f.method??null,weighted_rmse:f.weighted_rmse??null,physical_wrms:f.physical_wrms??null,command_wrms:f.command_wrms??null,penalized_score:f.penalized_score??null,converged:f.converged,status:f.status??null,evidence_refs:f.evidence_refs??e.evidence_refs??null});out+=line('Fit warnings (untrusted data)',f.warnings??null);
   const ident=f.identifiability;out+=line('Identifiability',ident&&typeof ident==='object'?Object.fromEntries(Object.entries(ident).filter(([k,v])=>['scaled_norm','rank','condition','qualification'].includes(k)&&(typeof v==='number'||typeof v==='string'||v===null))):null);out+=line('Residual diagnostics',residuals(f.residual_diagnostics));
  }
  if(e.type==='safety'){const screen=e.screen as Record<string,unknown>;out+=line('Recorded predictive safety decision',screen?Object.fromEntries(['accepted','mode','would_reject_enforced','qualification','uncertainty'].filter(k=>Object.hasOwn(screen,k)).map(k=>[k,screen[k]])):null);}
  if(e.type==='fit_failure')out+=line('Recorded fit failure',{template:e.template,method:e.method,reason:e.reason});
 }
 if(!fits)out+=line('Hypothesis fits',null);
 out+='\n## Derived supervisor events\n\nDerived interpretations of existing observations; not independent measurements.\n\n';
 out+=supervisor?line('Analysis rules',supervisor.rules)+line('Public events',supervisor.events.map(e=>({id:e.id,type:e.type,episode:e.episode_index+1,time_s:e.time_s,evidence_ref:e.episode_ref,source_field:e.source_field,threshold:e.threshold,units:e.units,supporting_value:e.supporting_value,description:e.description}))):line('Supervisor event companion',null);
 out+='\n## Investigator conclusion\n\n';out+=line('Recorded conclusion',conclusion?{diagnosis:conclusion.diagnosis??null,confidence:conclusion.confidence??null,stop_reason:conclusion.stop_reason??(conclusion as Record<string,unknown>).ambiguity_statement??null}:null);
 const summary=(conclusion as Record<string,unknown>|undefined)?.numerical_summary;out+=line('Recorded numerical alternatives under tested models',summary&&typeof summary==='object'?Object.fromEntries(Object.entries(summary).filter(([k])=>['kind','status','selected','competitive'].includes(k))):null);
 out+='\n## Proposed configuration change\n\n';out+=line('Accepted recorded proposal (untrusted rationale)',host?.proposal??null)+line('Host status',host?{status:host.status,reason:host.reason,budget:host.budget}:null);
 if(host?.comparison){const c=host.comparison;out+='\n## Measured simulation comparison\n\nVisualization-only metrics, not investigator evidence.\n\n';out+=line('Scenario',c.scenario_id);
  const keys=['rms_cross_track_m','max_abs_cross_track_m','outside_corridor_samples','fraction_outside_corridor','samples','elapsed_s','completion_time_s','termination','reached_cable_end','mission_success','command_saturation_fraction'];
  for(const name of ['baseline','candidate'] as const)out+=line(name+' metrics',Object.fromEntries(keys.map(k=>[k,c[name].metrics[k]])));
  out+=line('Measured differences',Object.fromEntries(keys.filter(k=>Object.hasOwn(c.metric_differences,k)).map(k=>[k,c.metric_differences[k]])))+line('Run references',host.run_references)+line('Conditions',c.conditions)+line('Limitations',c.limitations);
 }else out+=line('Measured comparison',null);
 out+='\n## Scientific and deployment limitations\n\nNumerical fit is not proven physical cause. Investigator conclusions are claims, not private evaluator truth. Public observations differ from visualization-only simulator truth. Requested commands are not measured actuator force. Scenario-specific improvement is not a verified repair. Offline simulation advice does not guarantee hardware safety. Hash linkage does not establish authentic authorship. Operator review is required before any configuration use.\n';
 return out;
}
export async function buildInvestigationArtifacts(publicInput:unknown,hostInput:unknown=null,supervisorInput:unknown=null){
 const record=await readRecord(publicInput),host=hostInput===null?null:readHostEvaluation(hostInput,record),supervisor=supervisorInput===null?null:readSupervisor(supervisorInput,record);
 const diff=configurationDiff(record,host);
 return {report:{filename:'investigation_report.md',mime:'text/plain;charset=utf-8',content:markdown(record,host,supervisor)},config:diff?{filename:'config_diff.json',mime:'application/json',content:JSON.stringify(diff,null,2)+'\n'}:null};
}
export function prepareArtifactLink(button:HTMLElement,artifact:{filename:string;mime:string;content:string},doc:Document=document,urls:Pick<typeof URL,'createObjectURL'|'revokeObjectURL'>=URL){
 const url=urls.createObjectURL(new Blob([artifact.content],{type:artifact.mime})),a=doc.createElement('a');a.href=url;a.download=artifact.filename;a.id=button.id;a.className=button.className;a.textContent=button.textContent;button.replaceWith(a);return ()=>urls.revokeObjectURL(url);
}
