import * as THREE from 'three';
export function researchVehicle(software:boolean,reference=false){
 const group=new THREE.Group(),rotors:THREE.Group[]=[],lights:THREE.SpotLight[]=[];
 const material=(color:number,metalness=.15,roughness=.55)=>software?new THREE.MeshLambertMaterial({color}):new THREE.MeshStandardMaterial({color,metalness,roughness});
 const yellow=material(reference?0x8eaebc:0xd8b861,.28,.44),metal=material(0x85989b,.75,.32),dark=material(0x172c32,.5,.38),glass=material(0x426d7b,.6,.18),light=new THREE.MeshBasicMaterial({color:0xcce5d5});
 function mesh(geometry:THREE.BufferGeometry,m:THREE.Material,x=0,y=0,z=0){const object=new THREE.Mesh(geometry,m);object.position.set(x,y,z);object.castShadow=!reference;object.receiveShadow=true;group.add(object);return object;}
 const hull=mesh(new THREE.CapsuleGeometry(.34,1.7,6,software?12:24),yellow);hull.rotation.z=-Math.PI/2;
 for(const x of [-.73,.6]){const ring=mesh(new THREE.TorusGeometry(.346,.025,6,20),metal,x);ring.rotation.y=Math.PI/2;}
 const bow=mesh(new THREE.SphereGeometry(.31,16,10),dark,1.02);bow.scale.set(.55,1,1);
 const lens=mesh(new THREE.CylinderGeometry(.115,.115,.1,16),glass,1.21,.02);lens.rotation.z=-Math.PI/2;
 mesh(new THREE.BoxGeometry(.52,.14,.36),dark,.1,.4);mesh(new THREE.CylinderGeometry(.07,.07,.19,12),metal,-.3,.46);
 for(const z of [-.53,.53]){
  const brace=mesh(new THREE.BoxGeometry(1.55,.06,.06),metal,-.18,-.26,z);brace.rotation.x=.06;
  const support=mesh(new THREE.BoxGeometry(.09,.38,.05),metal,-.75,-.08,z);
  const guard=mesh(new THREE.TorusGeometry(.235,.055,8,20),dark,-.86,-.06,z);guard.rotation.y=Math.PI/2;
  const rotor=new THREE.Group();rotor.position.set(-.86,-.06,z);rotors.push(rotor);group.add(rotor);
  const hub=new THREE.Mesh(new THREE.SphereGeometry(.075,8,6),metal);rotor.add(hub);
  for(let i=0;i<3;i++){const blade=new THREE.Mesh(new THREE.BoxGeometry(.035,.35,.075),metal);blade.rotation.x=i*Math.PI/3;rotor.add(blade);}
  const strut=mesh(new THREE.BoxGeometry(.04,.47,.025),metal,-.9,-.06,z);strut.rotation.x=.6;
  mesh(new THREE.BoxGeometry(1.8,.055,.055),dark,-.05,-.48,z);
  const lamp=mesh(new THREE.CylinderGeometry(.09,.1,.16,12),metal,.88,-.18,z*.68);lamp.rotation.z=-Math.PI/2;
  const bulb=mesh(new THREE.CircleGeometry(.075,12),light,.975,-.18,z*.68);bulb.rotation.y=Math.PI/2;
  if(!software&&!reference){const spot=new THREE.SpotLight(0xc8e5db,24,20,.45,.65,1.5);spot.position.set(1,-.15,z*.68);const target=new THREE.Object3D();target.position.set(8,-2,z*.68);group.add(target,spot);spot.target=target;if(z<0){spot.castShadow=true;spot.shadow.mapSize.set(512,512);spot.shadow.bias=-.001;}lights.push(spot);}
 }
 for(const x of [-.5,.05,.5])for(const z of [-.25,.25])mesh(new THREE.SphereGeometry(.022,6,4),metal,x,.29,z);
 const fin=mesh(new THREE.BoxGeometry(.4,.35,.035),yellow,-1.03,.31);fin.rotation.z=.2;
 const washGeometry=new THREE.BufferGeometry(),washPositions=new Float32Array(20*3);washGeometry.setAttribute('position',new THREE.BufferAttribute(washPositions,3));
 const wash=new THREE.Points(washGeometry,new THREE.PointsMaterial({color:0xa5c9c5,size:.025,transparent:true,opacity:.22,depthWrite:false}));wash.visible=!reference;group.add(wash);
 return {group,update(time:number,effects:boolean){rotors.forEach((r,i)=>r.rotation.x=time*12*(i?1:-1));wash.visible=effects&&!reference;lights.forEach(l=>l.visible=effects);for(let i=0;i<20;i++){const phase=(time*.4+i/20)%1;washPositions.set([-1-phase*1.5,-.06+Math.sin(i*3.7)*phase*.13,(i%2?-.53:.53)+Math.cos(i*7.1)*phase*.12],i*3);}washGeometry.attributes.position.needsUpdate=true;}};
}
