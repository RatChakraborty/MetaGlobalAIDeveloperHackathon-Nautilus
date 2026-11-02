/** V6 control-lab recommendation panel.
 * Structure and cross-field consistency are validated here; canonical artifact
 * hashing is established by the trusted Python exporter. Nothing is executed. */
import {escapeText as esc} from './supervisor.ts';
export const SCHEMA='nautilus.control-lab-recommendation.v1';
export const SCOPE='Engineering recommendation from matched offline simulation; not a deployed repair, safety certificate or diagnosis evidence.';
export const PARAMETERS={lookahead_m:{unit:'m',bounds:[2,20]},heading_kp:{unit:'N*m/rad',bounds:[5,80]},heading_kd:{unit:'N*m/(rad/s)',bounds:[0,80]},cruise_thrust:{unit:'N',bounds:[0,45]},max_heading_rad:{unit:'rad',bounds:[.05,1.5]}} as const;
export const DIFFABLE=['lookahead_m','heading_kp','heading_kd','cruise_thrust'] as const;
type Parameter=keyof typeof PARAMETERS;
export type ControlLab=Record<string,any>;
const object=(v:unknown):v is Record<string,any>=>v!==null&&typeof v==='object'&&!Array.isArray(v);
function closed(v:unknown,keys:string[],label='control-lab artifact'):Record<string,any>{if(!object(v)||Object.keys(v).sort().join()!==[...keys].sort().join())throw Error('Invalid '+label+' fields');return v;}
const diffable=(name:unknown):Parameter=>{const key=parameter(name);if(!(DIFFABLE as readonly string[]).includes(key))throw Error('Unsupported control-lab difference');return key;};
const num=(v:unknown)=>{if(typeof v!=='number'||!Number.isFinite(v))throw Error('Invalid control-lab number');return v;};
const text=(v:unknown,limit=1000)=>{if(typeof v!=='string'||!v.trim()||v.length>limit)throw Error('Invalid control-lab text');return v;};
const hex=(v:unknown)=>{if(typeof v!=='string'||!/^[a-f0-9]{64}$/.test(v))throw Error('Invalid control-lab reference');return v;};
const strings=(v:unknown,label:string)=>{if(!Array.isArray(v)||!v.length||v.length>200||v.some(x=>typeof x!=='string'||!x))throw Error('Invalid '+label);return v as string[];};
const parameter=(name:unknown):Parameter=>{if(typeof name!=='string'||!Object.hasOwn(PARAMETERS,name))throw Error('Unsupported control-lab parameter');return name as Parameter;};
const within=(name:Parameter,value:unknown)=>{const [low,high]=PARAMETERS[name].bounds;const n=num(value);if(n<low||n>high)throw Error('Control-lab value outside approved bounds');return n;};
export function readControlLab(value:unknown):ControlLab{
 const v=closed(value,['schema_version','investigation_id','created_from','evidence_refs','controller','proposal','approved_differences','evaluation_conditions','baseline','candidate','robustness','recommendation','unresolved_risks','human_review','patch','limitations','scope','artifact_hash']);
 if(v.schema_version!==SCHEMA)throw Error('Unsupported control-lab schema');
 if(v.scope!==SCOPE)throw Error('Control-lab scope changed: a recommendation is not a deployed repair');
 text(v.investigation_id,200);text(v.created_from,100);hex(v.artifact_hash);
 strings(v.evidence_refs,'evidence references').forEach(hex);
 const controller=closed(v.controller,['policy_id','implementation_version','source_sha256','policy_hash','configuration_id','baseline_configuration'],'controller identity');
 text(controller.policy_id);text(controller.implementation_version);[controller.source_sha256,controller.policy_hash,controller.configuration_id].forEach(hex);
 const baselineConfig=closed(controller.baseline_configuration,Object.keys(PARAMETERS),'baseline configuration');
 for(const name of Object.keys(PARAMETERS) as Parameter[])within(name,baselineConfig[name]);
 const differences=v.approved_differences;
 if(!object(differences)||Object.keys(differences).length>1)throw Error('Invalid approved differences');
 for(const [key,change] of Object.entries(differences)){
  const name=diffable(key),entry=closed(change,['baseline','candidate','unit'],'approved difference');
  const [low,high]=PARAMETERS[name].bounds;
  if(entry.unit!==PARAMETERS[name].unit||entry.baseline!==baselineConfig[name])throw Error('Approved difference does not match the baseline');
  const candidate=num(entry.candidate);if(candidate<low||candidate>high||candidate===entry.baseline)throw Error('Approved difference is out of bounds or unchanged');
  const proposal=v.proposal;
  if(!object(proposal))throw Error('Approved difference requires a validated proposal');
  closed(proposal,['parameter','value','rationale','evidence_refs','expected_effect'],'proposal');
  if(proposal.parameter!==name||proposal.value!==candidate)throw Error('Proposal differs from the approved difference');
  text(proposal.rationale);text(proposal.expected_effect,500);
  const refs=strings(proposal.evidence_refs,'proposal evidence');refs.forEach(ref=>{if(!v.evidence_refs.includes(ref))throw Error('Proposal evidence is not public');});
 }
 if(!Object.keys(differences).length&&v.proposal!==null)throw Error('No approved difference may accompany a proposal');
 const robustness=closed(v.robustness,['cases','per_scenario','gates','decision','decision_reasons','failures','limitations'],'robustness record');
 if(!Array.isArray(robustness.cases)||!robustness.cases.length)throw Error('Invalid robustness cases');
 if(robustness.decision!=='accept'&&robustness.decision!=='reject')throw Error('Invalid robustness decision');
 if(robustness.decision==='accept'&&!Object.keys(differences).length)throw Error('Accepted recommendation requires an approved change');
 if(!Array.isArray(robustness.gates)||!robustness.gates.length)throw Error('Declared gates required');
 for(const gate of robustness.gates){closed(gate,['id','passed','observed','threshold','description'],'gate');text(gate.id);text(gate.description,500);num(gate.observed);num(gate.threshold);if(typeof gate.passed!=='boolean')throw Error('Invalid gate result');}
 if(!Array.isArray(robustness.per_scenario))throw Error('Invalid per-scenario results');
 for(const row of robustness.per_scenario){closed(row,['scenario_id','rms_difference_m'],'scenario result');text(row.scenario_id);num(row.rms_difference_m);}
 if(!Array.isArray(robustness.decision_reasons)||robustness.decision_reasons.some((x:unknown)=>typeof x!=='string'))throw Error('Invalid decision reasons');
 const recommendation=closed(v.recommendation,['decision','reasons','model_recommendation','agreement','authority'],'recommendation');
 if(recommendation.decision!==robustness.decision)throw Error('Recommendation must follow the host rule');
 text(recommendation.authority,300);
 if(recommendation.model_recommendation!==null){const model=closed(recommendation.model_recommendation,['recommendation','rationale'],'model recommendation');text(model.rationale);if(!['accept','reject','further_testing'].includes(model.recommendation))throw Error('Unsupported model recommendation');}
 const human=closed(v.human_review,['status','performed','checklist'],'human review');
 if(human.status!=='required'||human.performed!==false)throw Error('Human review must remain required and unperformed');
 strings(human.checklist,'human review checklist');
 const patch=closed(v.patch,['status','diff','certified','sandbox','checks','notes'],'patch record');
 if(!['not_attempted','review_only','unavailable'].includes(patch.status))throw Error('Patch execution is not implemented');
 if(patch.certified!==false)throw Error('A controller patch cannot be certified here');
 strings(v.unresolved_risks,'unresolved risks');strings(v.limitations,'limitations');
 for(const side of ['baseline','candidate'] as const){const body=closed(v[side],['aggregate'],'aggregate metrics');if(!object(body.aggregate))throw Error('Invalid aggregate metrics');}
 return v;
}
const fmt=(value:unknown,digits=3)=>typeof value==='number'&&Number.isFinite(value)?value.toFixed(digits):'n/a';
const signed=(value:unknown)=>typeof value==='number'&&Number.isFinite(value)?(value>0?'+':'')+value.toFixed(3):'n/a';
export function controlLabMarkup(lab:ControlLab|null):string{
 if(!lab)return `<section class="control-lab"><h3>V6 control lab</h3><p class="muted">No engineering recommendation loaded. A recommendation is simulation evidence, not a deployed repair.</p><label class="button secondary">Open control-lab recommendation<input id="control-lab-file" type="file" accept=".json,application/json"></label></section>`;
 const differences=lab.approved_differences as Record<string,any>,change=Object.entries(differences)[0];
 const proposal=lab.proposal,aggregate=(side:'baseline'|'candidate')=>lab[side].aggregate;
 const model=lab.recommendation.model_recommendation;
 const rows=[['mean_rms_cross_track_m','Mean cross-track RMS · m'],['worst_case_max_abs_cross_track_m','Worst-case maximum · m'],['worst_case_fraction_outside_corridor','Worst-case outside fraction'],['completed_missions','Completed missions'],['worst_case_command_saturation_fraction','Worst-case saturation'],['mean_effort_proxy_n_s','Mean effort proxy · N·s']];
 return `<section class="control-lab"><h3>V6 control lab · engineering recommendation</h3>
 <p>${esc(lab.robustness.decision==='accept'?'Accepted on the development suite by the predeclared rule':'Rejected on the development suite by the predeclared rule')} · ${esc(lab.recommendation.decision)} · human review ${esc(lab.human_review.status)}</p>
 <p class="muted">${esc(lab.scope)}</p>
 <p class="muted">${esc(lab.evaluation_conditions?.decision_qualification??'')} ${esc(lab.evaluation_conditions?.screening_exposure?.statement??'')}</p>
 <div class="table-wrap"><table><thead><tr><th>Policy</th><th>Value</th><th>Unit</th></tr></thead><tbody>${(Object.entries(lab.controller.baseline_configuration) as [string,number][]).map(([key,value])=>`<tr><td>${esc(key)}</td><td>${esc(String(value))}</td><td>${esc((PARAMETERS as any)[key]?.unit??'n/a')}</td></tr>`).join('')}</tbody></table></div>
 ${change?`<p><b>Proposed change:</b> ${esc(change[0])} ${esc(String(change[1].baseline))} → ${esc(String(change[1].candidate))} ${esc(change[1].unit)}</p><p><b>Reason:</b> ${esc(proposal.rationale)}</p><p><b>Expected effect:</b> ${esc(proposal.expected_effect)}</p>`:'<p>No controller change is recommended for this evaluation.</p>'}
 <div class="table-wrap"><table><thead><tr><th>Metric</th><th>Baseline</th><th>Candidate</th><th>Difference</th></tr></thead><tbody>${rows.map(([key,label])=>`<tr><td>${esc(label)}</td><td>${fmt(aggregate('baseline')[key],key==='completed_missions'?0:3)}</td><td>${fmt(aggregate('candidate')[key],key==='completed_missions'?0:3)}</td><td>${signed((aggregate('candidate')[key]??0)-(aggregate('baseline')[key]??0))}</td></tr>`).join('')}</tbody></table></div>
 <h4>Per-scenario robustness</h4><div class="table-wrap"><table><thead><tr><th>Scenario</th><th>RMS difference · m</th><th>Decision</th></tr></thead><tbody>${(lab.robustness.cases as any[]).map(row=>`<tr><td>${esc(row.scenario_id)}</td><td>${signed(row.differences?.rms_cross_track_m)}</td><td>${row.candidate?.mission_success?'completed':'duration cap'} / baseline ${row.baseline?.mission_success?'completed':'duration cap'}</td></tr>`).join('')}</tbody></table></div>
 <h4>Declared gates</h4><ul class="control-gates">${(lab.robustness.gates as any[]).map(gate=>`<li><span class="${gate.passed?'verified':'failed'}">${gate.passed?'pass':'fail'}</span> ${esc(gate.id)} · observed ${esc(String(gate.observed))} · threshold ${esc(String(gate.threshold))}</li>`).join('')}</ul>
 ${model?`<p>Model recommendation: ${esc(model.recommendation)} · ${esc(lab.recommendation.agreement?'agrees with':'differs from')} the host rule. ${esc(model.rationale)}</p>`:'<p>No model recommendation recorded.</p>'}
 <p class="muted">${esc((lab.robustness.limitations as string[]).join(' '))}</p>
 <h4>Unresolved risks</h4><ul>${(lab.unresolved_risks as string[]).map(risk=>`<li>${esc(risk)}</li>`).join('')}</ul>
 <p class="muted">Patch: ${esc(lab.patch.status)}${lab.patch.certified?' · certified':''}. ${esc((lab.patch.notes as string[]).join(' '))}</p>
 <div class="workbench-actions"><button class="button secondary" id="download-control-diff" ${change?'':'disabled'}>Configuration diff JSON</button><button class="button secondary" id="control-lab-file-button" disabled>3D comparison uses stored runs</button></div>
 <p class="muted">Compare in 3D is available only through a validated baseline/candidate export pair; this panel never invents trajectories and never executes a patch.</p>
 <label class="button secondary">Open another control-lab recommendation<input id="control-lab-file" type="file" accept=".json,application/json"></label></section>`;
}
export function controlLabDiff(lab:ControlLab){
 return {schema_version:'nautilus.configuration-diff.v1',investigation_id:lab.investigation_id,
  controller:{policy_id:lab.controller.policy_id,source_sha256:lab.controller.source_sha256,policy_hash:lab.controller.policy_hash},
  baseline_configuration:lab.controller.baseline_configuration,approved_differences:lab.approved_differences,
  decision:lab.recommendation.decision,human_review:lab.human_review.status,artifact_hash:lab.artifact_hash,
  scope:'Review artifact only; applying it is a separate human decision. Not a deployed repair.'};
}
