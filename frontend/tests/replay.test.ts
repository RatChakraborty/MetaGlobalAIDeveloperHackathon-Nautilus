import {test} from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';
import {interpolatePose,displayPose,advanceClock,synchronizedPoses,cameraMode,alignVisualization,breach,compatibleReference} from '../src/replay-math.ts';
import {disposeScene,selectRenderer} from '../src/scene-resources.ts';
import {researchVehicle} from '../src/vehicle.ts';
import {trajectoryMarkup} from '../src/trajectory.ts';
import type {Visual} from '../src/records.ts';
const visual:Visual={schema_version:'nautilus.visualization-only.v1',run_id:'unit-test',label:'test only',reference:{cable_length_m:110,cable_half_width_m:1.5,source:'test fixture'},samples:[{time_s:0,x_m:0,y_m:0,heading_rad:3.1},{time_s:2,x_m:4,y_m:2,heading_rad:-3.1}]};
test('interpolation preserves exact endpoints, wraps heading on shortest arc and never extrapolates',()=>{const original=JSON.stringify(visual);assert.deepEqual(interpolatePose(visual.samples,0),visual.samples[0]);assert.deepEqual(interpolatePose(visual.samples,2),visual.samples[1]);const middle=interpolatePose(visual.samples,1);assert.equal(middle.x_m,2);assert.equal(middle.y_m,1);assert.ok(Math.abs(Math.abs(middle.heading_rad)-Math.PI)<1e-12);assert.deepEqual(interpolatePose(visual.samples,-5),visual.samples[0]);assert.deepEqual(interpolatePose(visual.samples,9),visual.samples[1]);assert.equal(JSON.stringify(visual),original);assert.throws(()=>interpolatePose([],0));assert.throws(()=>interpolatePose(visual.samples,NaN));});
test('positive and negative heading interpolation use the correct shortest direction',()=>{for(const sign of [-1,1]){const rows=[{...visual.samples[0],heading_rad:sign*.2},{...visual.samples[1],heading_rad:sign*.6}];assert.ok(Math.abs(interpolatePose(rows,1).heading_rad-sign*.4)<1e-12);}});
test('clock uses elapsed timestamps at any frame cadence and stops at recorded end',()=>{assert.equal(advanceClock(5,1000,1750,2,20),6.5);let t=5;for(let i=0;i<15;i++)t=advanceClock(t,1000+i*50,1050+i*50,2,20);assert.ok(Math.abs(t-6.5)<1e-12);assert.equal(advanceClock(19,0,4000,4,20),20);assert.equal(advanceClock(5,2000,1000,1,20),5);});
test('unequal-duration references interpolate on elapsed seconds and hold their own endpoints',()=>{const reference={...visual,samples:[{time_s:0,x_m:10,y_m:0,heading_rad:0},{time_s:1,x_m:20,y_m:0,heading_rad:0}]};const a=synchronizedPoses(visual,reference,.5);assert.equal(a.primary.x_m,1);assert.equal(a.reference.x_m,15);assert.equal(synchronizedPoses(visual,reference,2).reference.x_m,20);assert.equal(compatibleReference(visual,reference),reference);assert.throws(()=>compatibleReference(visual,{...reference,reference:null}));});
test('exaggeration changes only rendered cross-track coordinates, never physical breach or source samples',()=>{const original=JSON.stringify(visual),pose=interpolatePose(visual.samples,1.75);const a=displayPose(pose,1),b=displayPose(pose,5);assert.equal(b.z,a.z*5);assert.equal(a.x,b.x);assert.equal(a.heading,b.heading);assert.equal(b.y,0);assert.equal(breach(pose,visual.reference),true);assert.equal(breach(pose,null),null);assert.equal(JSON.stringify(visual),original);assert.throws(()=>displayPose(pose,0));});
test('camera modes and optional overlays remain independent of evidence',()=>{for(const mode of ['chase','onboard','top','free'])assert.equal(cameraMode(mode),mode);assert.throws(()=>cameraMode('physical-camera'));const html=trajectoryMarkup(null);assert.match(html,/No compatible 3D recording loaded/);assert.match(html,/not investigator evidence/);assert.match(html,/not a verified repair/);assert.match(html,/No actual-force, current, velocity/);assert.doesNotMatch(html,/actual RPM/);assert.equal(alignVisualization(visual,[{time_s:0},{time_s:2}]),visual);assert.throws(()=>alignVisualization(visual,[{time_s:0},{time_s:1}]));});
test('unavailable hardware selects a software renderer without swallowing fallback failure',()=>{const fallback={kind:'svg'};assert.equal(selectRenderer(()=>{throw Error('GPU unavailable');},()=>fallback).renderer,fallback);assert.equal(selectRenderer(()=>fallback,()=>{throw Error('unused');}).software,false);assert.throws(()=>selectRenderer(()=>{throw Error('GPU');},()=>{throw Error('fallback');}),/fallback/);});
test('scene disposal releases shared resources once and animated model keeps its recorded root pose',()=>{const vehicle=researchVehicle(true);vehicle.group.position.set(3,0,-2);vehicle.group.rotation.y=.4;vehicle.update(10,true);assert.deepEqual(vehicle.group.position.toArray(),[3,0,-2]);assert.equal(vehicle.group.rotation.y,.4);const scene=new THREE.Scene(),geometry=new THREE.BoxGeometry(),texture=new THREE.DataTexture(new Uint8Array(4),1,1),material=new THREE.MeshStandardMaterial({map:texture});let geometries=0,materials=0,textures=0;geometry.addEventListener('dispose',()=>geometries++);material.addEventListener('dispose',()=>materials++);texture.addEventListener('dispose',()=>textures++);scene.add(new THREE.Mesh(geometry,material),new THREE.Mesh(geometry,material));disposeScene(scene);assert.equal(geometries,1);assert.equal(materials,1);assert.equal(textures,1);assert.equal(scene.children.length,0);disposeScene(vehicle.group);assert.equal(vehicle.group.children.length,0);});


test('empty viewer explains the spatial limitation, while a matching recording enables camera controls',()=>{
 const empty=trajectoryMarkup(null);
 assert.match(empty,/no x-position/);
 assert.match(empty,/aria-describedby="tracking-explanation"/);
 assert.match(empty,/Vehicle orientation alone does not establish a fault/);
 assert.match(empty,/id="camera-mode"[^>]*disabled/);
 const loaded=trajectoryMarkup(visual);
 assert.doesNotMatch(loaded,/id="camera-mode"[^>]*disabled/);
 assert.match(loaded,/Reset view/);
 assert.match(loaded,/Advanced viewer controls/);
 assert.match(loaded,/Recorded simulation visualization — not investigator evidence/);
});
