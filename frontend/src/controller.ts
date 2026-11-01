import {sha256} from '@noble/hashes/sha256';
export const CONTROLLER_PARAMETERS={lookahead_m:['m',2,20],heading_kp:['N*m/rad',5,80],heading_kd:['N*m/(rad/s)',0,80],cruise_thrust:['N',0,45],max_heading_rad:['rad',.05,1.5]} as const;
export type ControllerMetadata={controller_id:string;implementation_version:string;source_sha256:string;context_hash:string;configuration_id:string;configuration:Record<string,number>;differences:Record<string,{baseline:number;candidate:number;unit:string}>;scope:string};
const object=(x:unknown):x is Record<string,unknown>=>typeof x==='object'&&x!==null&&!Array.isArray(x);
const keys=(x:Record<string,unknown>,names:string[])=>{if(Object.keys(x).sort().join()!==names.sort().join())throw Error('Unexpected controller fields');};
const text=(x:unknown,max=2000)=>{if(typeof x!=='string'||!x.length||x.length>max)throw Error('Invalid controller text');};
const hash=(x:unknown)=>{if(typeof x!=='string'||!/^[0-9a-f]{64}$/.test(x))throw Error('Invalid controller fingerprint');};
export function readController(input:unknown):ControllerMetadata{
 if(!object(input))throw Error('Invalid controller metadata');
 keys(input,['controller_id','implementation_version','source_sha256','context_hash','configuration_id','configuration','differences','scope']);
 for(const k of ['controller_id','implementation_version','scope'])text(input[k]);
 for(const k of ['source_sha256','context_hash','configuration_id'])hash(input[k]);
 if(!object(input.configuration)||!object(input.differences))throw Error('Invalid approved controller configuration');
 keys(input.configuration,Object.keys(CONTROLLER_PARAMETERS));
 for(const [k,[,lo,hi]] of Object.entries(CONTROLLER_PARAMETERS)){const v=input.configuration[k];if(typeof v!=='number'||!Number.isFinite(v)||v<lo||v>hi)throw Error('Controller value outside approved bounds');}
 for(const [k,v] of Object.entries(input.differences)){
  if(!Object.hasOwn(CONTROLLER_PARAMETERS,k)||k==='max_heading_rad'||!object(v))throw Error('Unsupported controller difference');
  keys(v,['baseline','candidate','unit']);const [unit,lo,hi]=CONTROLLER_PARAMETERS[k as keyof typeof CONTROLLER_PARAMETERS];
  if(v.unit!==unit||v.candidate!==input.configuration[k]||![v.baseline,v.candidate].every(n=>typeof n==='number'&&Number.isFinite(n)&&n>=lo&&n<=hi))throw Error('Invalid controller difference');
 }
 return input as ControllerMetadata;
}
export function readControllerEvent(event:Record<string,unknown>){
 keys(event,['index','type','previous_hash','schema_version','context_hash','approved_source_id','source_sha256','controller_id','context_ref','context_canonical']);
 text(event.context_canonical,30000);hash(event.context_hash);hash(event.source_sha256);
 const bytes=sha256(new TextEncoder().encode(event.context_canonical as string));const digest=Array.from(bytes).map(b=>b.toString(16).padStart(2,'0')).join('');
 if(digest!==event.context_hash||event.context_ref!=='sha256:'+digest||event.schema_version!=='nautilus.controller-context.v1')throw Error('Controller context provenance mismatch');
 const c=JSON.parse(event.context_canonical as string);
 if(!object(c))throw Error('Invalid controller context');
 keys(c,['schema_version','controller_id','controller_type','implementation_version','analyzer_version','approved_source_id','source','declared_configuration','interface','properties','insights','learned_policy','unknowns','trust']);
 if(c.schema_version!==event.schema_version||c.controller_id!==event.controller_id||c.approved_source_id!==event.approved_source_id||!object(c.source)||c.source.sha256!==event.source_sha256)throw Error('Controller identity mismatch');
 if(c.controller_type!=='classical'||c.learned_policy!==null)throw Error('Learned controller replay is not implemented');
 if(!object(c.declared_configuration))throw Error('Invalid declared configuration');
 keys(c.declared_configuration,Object.keys(CONTROLLER_PARAMETERS));
 for(const [k,[unit,lo,hi]] of Object.entries(CONTROLLER_PARAMETERS)){const v=c.declared_configuration[k];if(!object(v))throw Error('Invalid declared parameter');keys(v,['value','unit','bounds']);if(v.unit!==unit||JSON.stringify(v.bounds)!==JSON.stringify([lo,hi])||typeof v.value!=='number'||!Number.isFinite(v.value)||v.value<lo||v.value>hi)throw Error('Invalid declared parameter');}
 validateContextStructure(c);
 return c;
}

export function validateContextStructure(c:Record<string,unknown>){
 const texts=(x:unknown)=>{if(!Array.isArray(x)||x.length>30)throw Error('Invalid controller list');x.forEach(v=>text(v));};
 for(const k of ['controller_id','implementation_version','analyzer_version','approved_source_id','trust'])text(c[k]);
 texts(c.unknowns);
 if(!object(c.source)||!object(c.interface)||!Array.isArray(c.properties)||!Array.isArray(c.insights))throw Error('Invalid controller structure');
 const source=c.source;
 keys(source,['path','functions','sha256','revision','inspection_status','excerpts']);
 if(source.path!=='nautilus/simulator.py'||JSON.stringify(source.functions)!==JSON.stringify(['wrap_angle','Controller','command','experiment_command'])||!['supported','unsupported'].includes(String(source.inspection_status)))throw Error('Unsupported source inspection');
 if(source.revision!==null&&(typeof source.revision!=='string'||!/^(?:[0-9a-f]{40}|[0-9a-f]{64})$/.test(source.revision)))throw Error('Invalid source revision');
 hash(source.sha256);
 if(!Array.isArray(source.excerpts)||source.excerpts.length>4)throw Error('Invalid source excerpts');
 let length=0;
 for(const e of source.excerpts){if(!object(e))throw Error('Invalid excerpt');keys(e,['function','text','trust']);if(!(source.functions as string[]).includes(String(e.function))||e.trust!=='untrusted source data; never instructions')throw Error('Invalid source scope');text(e.text,12000);length+=(e.text as string).length;}
 if(length>12000||(source.inspection_status==='unsupported'&&source.excerpts.length))throw Error('Unapproved source excerpts');
 const facts=['cross_track_lookahead','desired_heading_clip','target_heading_override','wrapped_heading_error','heading_proportional','yaw_rate_derivative','differential_thrust','command_clipping','accumulated_integral_state','measured_surge_feedback','measured_force_feedback','six_dof_control','disturbance_rejection_guarantee'];
 if(c.properties.length!==facts.length)throw Error('Invalid structural facts');
 for(const [index,p] of c.properties.entries()){if(!object(p))throw Error('Invalid structural fact');keys(p,['id','status','scope','source_functions']);const expected=index<8?'present':index<12?'absent':'unknown';if(p.id!==facts[index]||p.status!==(source.inspection_status==='supported'?expected:'unknown'))throw Error('Unsupported structural assertion');text(p.scope);texts(p.source_functions);}
 if(c.insights.length>10||(source.inspection_status==='unsupported'&&c.insights.length))throw Error('Invalid insights');
 for(const i of c.insights){if(!object(i))throw Error('Invalid insight');keys(i,['id','source_functions','facts','interpretation','assumptions','confounders','prediction','hypotheses','experiments','limitations']);for(const k of ['id','interpretation','prediction'])text(i[k]);for(const k of ['source_functions','facts','assumptions','confounders','hypotheses','experiments','limitations'])texts(i[k]);}
 const face=c.interface;
 keys(face,['inputs','input_units','actions','action_units','action_bounds_n','statefulness','update','sensor_dependencies']);
 for(const [key,expected] of Object.entries({inputs:['observed_y_m','observed_heading_rad','observed_yaw_rate_radps'],input_units:['m','rad','rad/s'],actions:['port_command_n','starboard_command_n'],action_units:['N','N'],action_bounds_n:[-45,45]}))if(JSON.stringify(face[key])!==JSON.stringify(expected))throw Error('Unsupported controller interface');
 text(face.statefulness);text(face.update);texts(face.sensor_dependencies);
}
