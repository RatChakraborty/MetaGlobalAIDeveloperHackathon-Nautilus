import type {Visual,Investigation,Observation} from './records.ts';
export type InspectionMode='bow'|'stern'|'port'|'starboard'|'underside'|'three-quarter'|'close';
export const INSPECTION_MODES:InspectionMode[]=['bow','stern','port','starboard','underside','three-quarter','close'];
export type CameraMode='chase'|'onboard'|'top'|'free'|InspectionMode;
export const CAMERA_MODES:CameraMode[]=['chase','onboard','top','free',...INSPECTION_MODES];
// Fixed vehicle-relative inspection views. Offsets are in the vehicle frame: f = forward, s = port side, y = up.
// Eye and target are offsets from the vehicle origin in world units; they never alter recorded pose.
export function inspectionView(mode:InspectionMode,heading:number){
 const f={x:Math.cos(heading),z:-Math.sin(heading)},s={x:-f.z,z:f.x};
 const at=(a:number,b:number,y:number)=>({x:f.x*a+s.x*b,y,z:f.z*a+s.z*b});
 switch(mode){
  case 'bow':return {eye:at(3,0,.6),target:at(.4,0,0)};
  case 'stern':return {eye:at(-3,0,.6),target:at(-.4,0,0)};
  case 'port':return {eye:at(0,3,.6),target:at(0,0,0)};
  case 'starboard':return {eye:at(0,-3,.6),target:at(0,0,0)};
  case 'underside':return {eye:at(1.5,0,-1.2),target:at(0,0,0)};
  case 'three-quarter':return {eye:at(2.2,2.2,1.6),target:at(0,0,0)};
  case 'close':return {eye:at(1.2,.9,.5),target:at(.5,0,0)};
  default:throw Error('Not an inspection mode');
 }
}
export function cameraMode(value:string):CameraMode{if(!CAMERA_MODES.includes(value as CameraMode))throw Error('Unknown camera mode');return value as CameraMode;}
export function interpolatePose(rows:Visual['samples'],time:number){
 if(!rows.length||!Number.isFinite(time))throw Error('Finite time and recorded poses required');
 let lo=0,hi=rows.length-1;const t=Math.max(rows[0].time_s,Math.min(time,rows[hi].time_s));
 while(lo<hi){const mid=Math.ceil((lo+hi)/2);if(rows[mid].time_s<=t)lo=mid;else hi=mid-1;}
 const a=rows[lo],b=rows[Math.min(lo+1,rows.length-1)],alpha=b.time_s===a.time_s?0:(t-a.time_s)/(b.time_s-a.time_s);
 if(alpha===0)return {...a};
 const angle=Math.atan2(Math.sin(b.heading_rad-a.heading_rad),Math.cos(b.heading_rad-a.heading_rad));
 return {time_s:t,x_m:a.x_m+(b.x_m-a.x_m)*alpha,y_m:a.y_m+(b.y_m-a.y_m)*alpha,heading_rad:Math.atan2(Math.sin(a.heading_rad+angle*alpha),Math.cos(a.heading_rad+angle*alpha))};
}
export function displayPose(pose:Visual['samples'][number],exaggeration:number){if(!Number.isFinite(exaggeration)||exaggeration<1||exaggeration>10)throw Error('Lateral scale must be between 1 and 10');return {x:pose.x_m,y:0,z:-pose.y_m*exaggeration,heading:pose.heading_rad};}
export function advanceClock(time:number,previousMs:number,nowMs:number,speed:number,end:number){return Math.min(end,Math.max(0,time+Math.max(0,nowMs-previousMs)/1000*speed));}
export function alignVisualization(visual:Visual,observations:{time_s:number}[]){if(visual.samples.length!==observations.length||visual.samples.some((s,i)=>s.time_s!==observations[i].time_s))throw Error('Visualization timestamps differ from public observations');return visual;}
export function synchronizedPoses(primary:Visual,reference:Visual,time:number){return {primary:interpolatePose(primary.samples,time),reference:interpolatePose(reference.samples,time)};}
export function breach(pose:Visual['samples'][number],reference:Visual['reference']){return reference?Math.abs(pose.y_m)>reference.cable_half_width_m:null;}

export function compatibleReference(primary:Visual,reference:Visual){if(!primary.reference||!reference.reference||primary.reference.cable_length_m!==reference.reference.cable_length_m||primary.reference.cable_half_width_m!==reference.reference.cable_half_width_m)throw Error('Comparison requires matching recorded cable and corridor dimensions');return reference;}

export function matchingEpisode(record:Investigation,visual:Visual){
 if(record.file.run_id!==visual.run_id)throw Error('Public command run mismatch');
 const episodes=record.events.filter(e=>e.type==='observation');
 const episode=visual.episode_ref?episodes.find(e=>e.hash===visual.episode_ref):episodes.length===1?episodes[0]:null;
 if(!episode){if(visual.episode_ref)throw Error('Unknown visualization episode');return null;}
 alignVisualization(visual,episode.observations!);return episode;
}
export type CommandSource={run_id:string;episode_ref:string;rows:Observation[]};
export function commandSource(record:Investigation,visual:Visual):CommandSource|null{const e=matchingEpisode(record,visual);return e?{run_id:record.file.run_id,episode_ref:e.hash,rows:e.observations!}:null;}
export function commandsAt(source:CommandSource|null,time:number){if(!source||!Number.isFinite(time)||time<source.rows[0].time_s||time>source.rows.at(-1)!.time_s)return null;let lo=0,hi=source.rows.length-1;while(lo<hi){const mid=Math.ceil((lo+hi)/2);if(source.rows[mid].time_s<=time)lo=mid;else hi=mid-1;}return source.rows[lo];}
