import {readRecord,readVisual} from './records.ts';
import {alignVisualization,compatibleReference} from './replay-math.ts';
export type DemoFetch=(url:string)=>Promise<{ok:boolean;json():Promise<unknown>}>;
export async function loadDemo(enabled:boolean,fetcher:DemoFetch,base:string){
 if(!enabled)return null;
 const prefix=base.replace(/\/?$/,'/')+'demo/';
 const [primary,primaryVisual,reference,referenceVisual]=await Promise.all(['disturbance.public.json','disturbance.visualization.json','reference.public.json','reference.visualization.json'].map(async name=>{const response=await fetcher(prefix+name);if(!response.ok)throw Error('Demonstration unavailable; open local records instead.');return response.json();}));
 const record=await readRecord(primary),referenceRecord=await readRecord(reference);
 const observations=record.events.filter(e=>e.type==='observation').at(-1)?.observations??[],referenceObservations=referenceRecord.events.filter(e=>e.type==='observation').at(-1)?.observations??[];
 const visual=alignVisualization(readVisual(primaryVisual,record.file.run_id),observations);
 const compared=compatibleReference(visual,alignVisualization(readVisual(referenceVisual,referenceRecord.file.run_id),referenceObservations));
 return {record,visual,referenceRecord,referenceVisual:compared};
}
