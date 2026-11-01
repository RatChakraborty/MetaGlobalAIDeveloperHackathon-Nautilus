import * as THREE from 'three';
import {commandsAt,type CommandSource} from './replay-math.ts';
export function commandEncoding(value:number){if(!Number.isFinite(value))throw Error('Finite commanded thrust required');return {sign:value<0?-1:1,length:Math.min(1.6,Math.abs(value)*.035),visible:Math.abs(value)>.001};}
export function commandedArrows(){
 const group=new THREE.Group(),direction=new THREE.Vector3();
 const arrows=[-.53,.53].map((z,i)=>{const a=new THREE.ArrowHelper(new THREE.Vector3(1,0,0),new THREE.Vector3(-.86,-.06,z),1,i?0xf1c675:0x91eee1,.18,.10);a.line.geometry=a.line.geometry.clone();a.cone.geometry=a.cone.geometry.clone();(a.line.material as THREE.LineBasicMaterial).fog=false;(a.cone.material as THREE.MeshBasicMaterial).fog=false;group.add(a);return a;});
 group.visible=false;
 return {group,arrows,update(source:CommandSource|null,time:number,enabled:boolean){const row=commandsAt(source,time);group.visible=enabled&&!!row;if(!row)return;[row.port_command_n,row.starboard_command_n].forEach((value,i)=>{const state=commandEncoding(value),a=arrows[i];a.visible=state.visible;direction.set(state.sign,0,0);a.setDirection(direction);a.setLength(state.length,Math.min(.18,state.length*.3),Math.min(.1,state.length*.2));});}};
}
