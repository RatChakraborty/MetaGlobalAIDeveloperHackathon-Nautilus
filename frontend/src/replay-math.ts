import type {Visual} from './records.ts';
export type CameraMode='chase'|'onboard'|'top'|'free';
export const CAMERA_MODES:CameraMode[]=['chase','onboard','top','free'];
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
