import * as T from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import study from '../../pick_place_study/study.json';
import references from '../assets/reference_meshes.json';
import {feedFrame,feedPhases} from './axial-feed-motion.js';

const $=id=>document.getElementById(id), cfg=study.config;
const palette={structure:'#546b7b',interface:'#b4873e',grasp:'#d99937',electronics:'#619b98',magazine:'#427bbd',shell:'#80a5cd',drive:'#50657a',claw:'#82609e',core:'#a5b3bd',gate:'#b4873e',guide:'#80a5cd'};
const state={id:'axial5',mode:'layout',view:'iso',ammo:5,coreMass:1.2,gripperMass:.24,progress:0,playing:false,feedProgress:0,feedPlaying:false,feedPitch:0};
let renderer,scene,camera,orbit,head,gripper,seat,environment,table,body,labels=[],last=0;
const materialCache=new Map();
function material(color,opacity=1){const key=color+opacity;if(!materialCache.has(key))materialCache.set(key,new T.MeshStandardMaterial({color,roughness:.69,metalness:.12,transparent:opacity<1,opacity,depthWrite:opacity===1,side:T.DoubleSide}));return materialCache.get(key);}
function mesh(parent,geometry,color,at=[0,0,0],opacity=1){const m=new T.Mesh(geometry,material(color,opacity));m.position.set(...at);parent.add(m);return m;}
function box(parent,size,at,color,opacity=1){return mesh(parent,new T.BoxGeometry(...size),color,at,opacity);}
function cylinder(parent,r,h,at,color,axis='z',opacity=1){const m=mesh(parent,new T.CylinderGeometry(r,r,h,40),color,at,opacity);if(axis==='z')m.rotation.x=Math.PI/2;if(axis==='x')m.rotation.z=-Math.PI/2;return m;}
function rod(parent,a,b,r,color){const p=new T.Vector3(...a),q=new T.Vector3(...b),d=q.clone().sub(p);const m=mesh(parent,new T.CylinderGeometry(r,r,d.length(),16),color,p.clone().add(q).multiplyScalar(.5).toArray());m.quaternion.setFromUnitVectors(new T.Vector3(0,1,0),d.normalize());return m;}
function line(parent,points,color){const m=new T.Line(new T.BufferGeometry().setFromPoints(points.map(p=>new T.Vector3(...p))),new T.LineBasicMaterial({color}));parent.add(m);return m;}
function refMesh(p,parent,color,at=[0,0,0]){const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(p.vertices,3));g.setIndex(p.triangles);g.computeVertexNormals();return mesh(parent,g,color,at);}
function disc(parent,r,holes,depth,at,color,opacity=1,vertical=false){const s=new T.Shape();s.absarc(0,0,r,0,Math.PI*2,false);for(const [x,y,hr]of holes){const h=new T.Path();h.absarc(x,y,hr,0,Math.PI*2,true);s.holes.push(h);}const m=mesh(parent,new T.ExtrudeGeometry(s,{depth,bevelEnabled:false,curveSegments:36}),color,at,opacity);if(vertical)m.rotation.x=Math.PI/2;return m;}
function xDisc(parent,r,holes,depth,at,color,opacity=1){const m=disc(parent,r,holes,depth,at,color,opacity);m.rotation.y=Math.PI/2;return m;}
class Route extends T.Curve{constructor(points){super();this.points=points.map(p=>new T.Vector3(...p));this.ds=[0];for(let i=1;i<this.points.length;i++)this.ds.push(this.ds.at(-1)+this.points[i].distanceTo(this.points[i-1]));}getPoint(t,out=new T.Vector3()){const d=T.MathUtils.clamp(t,0,1)*this.ds.at(-1);let i=1;while(i<this.ds.length-1&&this.ds[i]<d)i++;return out.lerpVectors(this.points[i-1],this.points[i],(d-this.ds[i-1])/(this.ds[i]-this.ds[i-1]||1));}}
const current=()=>study.candidates.find(c=>c.id===state.id);
function mass(c,ammo=c.ammo){const rows=c.mass_rows.filter(r=>!r.name.startsWith('弹丸')).map(r=>({...r,kg:r.name==='发射核心与测速'?state.coreMass:r.kg}));for(let i=0;i<ammo;i++)rows.push({name:`弹丸${i+1}`,kg:cfg.ball_mass_kg,center_mm:c.ball_centers_mm[i]});const total=rows.reduce((s,r)=>s+r.kg,0);const cg=[0,1,2].map(k=>rows.reduce((s,r)=>s+r.kg*r.center_mm[k],0)/total);return{rows,total,cg,payload:total+state.gripperMass};}
function clear(g){if(!g)return;g.traverse(o=>o.geometry?.dispose());g.clear();}
function sphere(parent,r,at,color){return mesh(parent,new T.SphereGeometry(r,24,16),color,at);}

function makeHead(c){
  const group=new T.Group(),shells=new T.Group(),routing=new T.Group(),ballGroup=new T.Group(),coreMeshes=[];let axial=null;group.add(shells,routing,ballGroup);
  for(const p of references.launcher){const id=+p.name.replace('Ref_','');if(id<1197&&id!==1187||id===1265)continue;const m=refMesh(p,group,[1204,1205,1206,1207].includes(id)?'#394958':palette.core);m.userData.originalMaterial=m.material;coreMeshes.push(m);}
  for(const p of references.case)refMesh(p,group,p.name==='CASE_lid'?'#80b0ab':palette.electronics,[25.75,-33.5,75.5]);
  for(const p of c.parts){const target=p.role==='shell'?shells:group,color=palette[p.role];
    if(['轴向后限位板','轴向前限位板','常闭止弹片','直导路占位'].includes(p.name))continue;
    const opacity=p.role==='shell'?.20:1;
    const m=p.shape==='box'?box(target,p.size,p.at,color,opacity):cylinder(target,p.radius,p.height,p.at,color,p.axis,opacity);m.name=p.name;
  }
  const [x,y,z]=c.rotor_center_mm, r=c.outer_radius_mm;
  if(c.kind==='axial'){
    const d=c.axial_metrics,rotor=new T.Group();rotor.position.set(x,0,z);group.add(rotor);
    const holes=Array.from({length:c.slots},(_,i)=>[c.radius_mm*Math.cos(i*2*Math.PI/c.slots),c.radius_mm*Math.sin(i*2*Math.PI/c.slots),23]);
    xDisc(rotor,r,holes,c.rotor_depth_mm,[-c.rotor_depth_mm/2,0,0],palette.magazine,.8);
    cylinder(rotor,5,c.rotor_depth_mm+5,[0,0,0],palette.drive,'x');
    xDisc(shells,r+2,[[42,0,14]],3,[x-29,0,z],palette.magazine,.27);
    xDisc(shells,r+2,[[42,0,23]],3,[x+25,0,z],palette.magazine,.20);
    xDisc(shells,25.5,[[0,0,23]],56,[-92,0,0],palette.shell,.18);
    const stage1=box(group,[d.stage_length_mm,16,16],[d.home_face_x_mm-d.stage_length_mm/2,0,0],palette.drive,.65);
    const stage2=cylinder(group,4,d.stage_length_mm-4,[d.home_face_x_mm-d.stage_length_mm/2-2,0,0],palette.grasp,'x');
    const tip=cylinder(group,6,4,[d.home_face_x_mm-2,0,0],palette.grasp,'x');
    const gate=box(group,[3,46,46],[x+23.5,0,0],palette.grasp);
    const lead=cylinder(group,1.5,d.stage_length_mm-8,[d.home_face_x_mm-d.stage_length_mm/2,-10,0],palette.grasp,'x');
    const sync=new T.Group();group.add(sync);const hi=d.home_face_x_mm-8,lo=d.home_face_x_mm-d.stage_length_mm+8;
    line(sync,[[lo,5,-3],[hi,5,-3],[hi,5,3],[lo,5,3],[lo,5,-3]],palette.grasp);
    for(const xx of [lo,hi])cylinder(sync,3,2,[xx,5,0],palette.grasp,'y');
    axial={rotor,stage1,stage2,tip,gate,sync,lead};
  }
  const route=new Route(c.feed_route_mm);
  mesh(routing,new T.TubeGeometry(route,100,1.25,8,false),'#bd7d25');
  for(const t of [.28,.66]){const p=route.getPoint(t),next=route.getPoint(Math.min(1,t+.015));routing.add(new T.ArrowHelper(next.sub(p).normalize(),p,13,'#bd7d25',6,4));}
  for(let i=0;i<c.slots;i++){const b=sphere(ballGroup,cfg.ball_diameter_mm/2,c.ball_centers_mm[i],'#e1a64b');b.userData.slot=i;}
  // The old launcher entry supports/gate must be redrawn in this working zone.
  const zone=new T.LineSegments(new T.EdgesGeometry(new T.BoxGeometry(72,58,65)),new T.LineDashedMaterial({color:'#bd7d25',dashSize:4,gapSize:3}));zone.position.set(-60,0,4);zone.computeLineDistances();group.add(zone);
  const b=c.metrics.bounds_mm, helper=new T.Box3Helper(new T.Box3(new T.Vector3(...b[0]),new T.Vector3(...b[1])),'#5a83a5');group.add(helper);
  const cg=sphere(group,3,[0,0,0],'#aa455e');
  group.userData={shells,routing,balls:ballGroup,helper,cg,axial,coreMeshes};
  return group;
}

function makeGripper(c){
  const g=new T.Group(),w=c.wrist_point_mm,grip=c.grip_point_mm;
  const palmWidth=216;
  box(g,[42,palmWidth,18],[w[0],0,w[2]],palette.claw);
  cylinder(g,22,12,[w[0],0,w[2]+15],palette.claw);
  const jaws=[];
  for(const sign of [-1,1]){
    const jaw=new T.Group();jaw.userData.sign=sign;g.add(jaw);
    const outside=86,foot=75,footWidth=30;
    const bottom=grip[2]-7,top=w[2]-10;
    box(jaw,[18,8,top-bottom],[grip[0],sign*outside,(bottom+top)/2],palette.claw);
    box(jaw,[18,footWidth,6],[grip[0],sign*foot,bottom],palette.claw);
    box(jaw,[32,20,12],[w[0],sign*outside,w[2]-13],palette.claw);
    jaws.push(jaw);
  }
  g.userData={jaws};return g;
}

function makeSeat(){
  const g=new T.Group();
  for(const y of [-42,42])box(g,[118,8,7],[-15,y,-67],palette.structure);
  for(const x of [-70,40])box(g,[8,78,7],[x,0,-67],palette.structure);
  for(const [x,y]of[[-52,-30],[-52,30],[22,0]])cylinder(g,9,5,[x,y,-59],palette.grasp);
  for(const x of [-52,22])box(g,[17,16,8],[x,0,-61],palette.structure);
  const hooks=[];
  for(const y of [-29,29]){const h=new T.Group();h.position.set(-31,y,-78);g.add(h);
    box(h,[21,5,7],[8,0,4],palette.claw);box(h,[7,5,14],[16,0,10],palette.claw);hooks.push(h);
  }
  rod(g,[-31,-46,-78],[-31,46,-78],4,palette.claw);
  box(g,[30,25,20],[-31,57,-78],palette.claw); // Vehicle-side actuator, not selected hardware.
  box(g,[19,17,5],[20,-20,-62],'#587e89');
  for(const y of [-62,62])box(g,[43,7,45],[-15,y,-88],palette.structure);
  cylinder(g,14,142,[-15,0,-104],palette.structure,'y');
  box(g,[122,139,7],[-15,0,-114],palette.structure);
  cylinder(g,64,12,[-15,0,-124],'#788f9e');
  cylinder(g,24,20,[-15,83,-104],palette.claw,'y');
  g.userData={hooks};return g;
}

function makeEnvironment(){
  const g=new T.Group();
  // Actual table outline: 750×450 with 50 mm chamfers, straight edges 650/350.
  const outline=[[-325,-225],[325,-225],[375,-175],[375,175],[325,225],[-325,225],[-375,175],[-375,-175]];
  const s=new T.Shape();outline.forEach(([x,y],i)=>i?s.lineTo(x,y):s.moveTo(x,y));s.closePath();
  table=new T.Group();table.position.set(-430,0,0);g.add(table);
  mesh(table,new T.ExtrudeGeometry(s,{depth:400,bevelEnabled:false}), '#a8b6be',[0,0,0],.20);
  line(table,[...outline,outline[0]].map(([x,y])=>[x,y,400]),'#8c9faa');
  body=box(g,[360,360,250],[300,0,125],'#96acb8',.22);
  for(const x of [178,422])for(const y of [-152,152])cylinder(g,42,28,[x,y,49],'#647b8b','y',.65);
  const route=[[-290,0,470],[-290,0,675],[300,0,675],[300,0,380]];
  const dashed=new T.Line(new T.BufferGeometry().setFromPoints(route.map(p=>new T.Vector3(...p))),new T.LineDashedMaterial({color:'#9174a6',dashSize:9,gapSize:6}));dashed.computeLineDistances();g.add(dashed);
  const grid=new T.GridHelper(1800,36,'#b3c4cf','#d6e1e8');grid.rotation.x=Math.PI/2;grid.position.z=-1;g.add(grid);
  return g;
}

const phaseNotes=[
 ['接近抓取点','张爪从上方接近。工作台只提供平面，不假设有固定头部的夹具。'],
 ['闭爪并捕获承重肩','指尖台阶承受重力，防转面限制转动；此处没有计算夹紧力和接触应力。'],
 ['竖直离台','先提起205 mm，再横向搬运。这个抬升值是比较假设，后续与杆长一起优化。'],
 ['搬运到车侧上方','保持头部水平，夹爪与头一起移动；路径只是腕部目标，还没有六轴IK。'],
 ['向下导入、落座','定位键找正，三点承压面接触。夹爪保持闭合，浮动触点不承受头部重量。'],
 ['车侧锁紧并确认','主动双钩拉紧头下被动销，机械防退保持。必须确认锁止与电气连接后才松爪。'],
 ['开爪、向上退出','载荷已交给安装座。夹爪张开后上退；机械臂后续收臂路线尚未求解。']
];
const smooth=t=>t*t*(3-2*t), mix=(a,b,t)=>a+(b-a)*smooth(T.MathUtils.clamp(t,0,1));
function frame(p){
 const t=p/100;let x=-290,z=470,gripOffset=0,open=24,phase=0,lock=0;
 if(t<.15){gripOffset=mix(130,0,t/.15);}
 else if(t<.25){phase=1;open=mix(24,0,(t-.15)/.1);}
 else if(t<.43){phase=2;open=0;z=mix(470,675,(t-.25)/.18);}
 else if(t<.65){phase=3;open=0;z=675;x=mix(-290,300,(t-.43)/.22);}
 else if(t<.85){phase=4;open=0;x=300;z=mix(675,380,(t-.65)/.2);}
 else if(t<.94){phase=5;open=0;x=300;z=380;lock=smooth((t-.85)/.09);}
 else{phase=6;x=300;z=380;lock=1;open=mix(0,24,(t-.94)/.022);gripOffset=mix(0,160,(t-.962)/.038);}
 return{phase,head:[x,0,z],gripper:[x,0,z+gripOffset],open,lock};
}
function motion(){
  if(!head)return;
  const c=current();let f=frame(state.progress);
  if(state.mode!=='transfer')f={phase:0,head:[0,0,0],gripper:[0,0,0],open:0,lock:1};
  head.position.set(...f.head);gripper.position.set(...f.gripper);
  head.rotation.set(0,state.mode==='feed'?-T.MathUtils.degToRad(state.feedPitch):0,0);
  for(const jaw of gripper.userData.jaws)jaw.position.y=jaw.userData.sign*f.open;
  seat.position.set(...(state.mode==='transfer'?[300,0,380]:[0,0,0]));
  seat.userData.hooks.forEach(h=>h.rotation.y=T.MathUtils.degToRad(-58*(1-f.lock)));
  $('progress').value=state.progress;$('progress-label').textContent=`${Math.round(state.progress)}%`;
  $('motion-phase').textContent=phaseNotes[f.phase][0];$('phase-note').textContent=phaseNotes[f.phase][1];
  if(state.mode==='transfer')$('model-subtitle').textContent='目标轨迹示意，未解六轴IK／接触／碰撞';
  head.userData.balls.children.forEach((b,i)=>b.visible=i<state.ammo);
  head.userData.cg.position.set(...mass(c,state.ammo).cg);
  if(c.kind==='axial')applyFeed();
}

function visibility(){if(!head)return;const feed=state.mode==='feed';head.userData.shells.visible=$('show-shell').checked;head.userData.routing.visible=$('show-route').checked;head.userData.helper.visible=$('show-envelope').checked;gripper.visible=$('show-gripper').checked&&!['underside','feed'].includes(state.mode);seat.visible=$('show-seat').checked&&!feed;environment.visible=state.mode==='transfer';for(const m of head.userData.coreMeshes)m.material=feed?material('#a5b3bd',.18):m.userData.originalMaterial;head.traverse(o=>{if(o.name==='二级推送固定壳')o.material=material(palette.drive,feed?.15:1);});}
function setView(view=state.view){
  if(!camera)return;state.view=view;
  const transfer=state.mode==='transfer',target=transfer?new T.Vector3(-70,0,420):new T.Vector3(state.mode==='feed'?-65:-30,0,43);
  const dirs=state.mode==='underside'?{iso:[400,-550,-480],side:[0,-700,-280],top:[0,0,-800]}:{iso:[480,-730,470],side:[0,-900,0],top:[.1,0,900]};
  camera.up.set(...(view==='top'?[1,0,0]:[0,0,1]));camera.position.copy(target).add(new T.Vector3(...dirs[view]));
  camera.zoom=transfer?.53:state.mode==='feed'?1.05:1.25;camera.updateProjectionMatrix();orbit.target.copy(target);orbit.update();
  document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('selected',b.dataset.view===view));
}
function setMode(mode){if(mode==='feed'&&current().kind!=='axial')mode='layout';state.mode=mode;stop();stopFeed();$('motion-controls').hidden=mode!=='transfer';$('feed-controls').hidden=mode!=='feed';document.querySelectorAll('[data-mode]').forEach(b=>{b.classList.toggle('selected',b.dataset.mode===mode);b.setAttribute('aria-pressed',String(b.dataset.mode===mode));});$('view-note').textContent=mode==='transfer'?'灰色为400 mm工作台和360 mm底盘占位，位置可调整。紫色路径是搬运目标，不是机械臂求解结果。':mode==='underside'?'从下方观察：金色为头侧被动件，紫色为车侧双钩与驱动占位。钩形和内部传动尚待细化。':mode==='feed'?'原轮组与固定壳半透明显示，观察推头、止弹片和球的交接。台架按这一动作链验证；此处未计算接触力。':'拖动旋转，滚轮缩放。夹爪和车侧安装座不计入头部包络。';if(head){motion();visibility();makeLabels();setView('iso');}$('model-subtitle').textContent=mode==='transfer'?'目标轨迹示意，未解六轴IK／接触／碰撞':mode==='underside'?'底部功能布置；钩形、公差及传动尚待细化':mode==='feed'?'主动送球动作意向；反馈状态是演示假设':'真实发射核心与机箱；其余为布局几何';}
function makeLabels(){labels=[];$('model-labels').replaceChildren();const c=current();const add=(text,p,color,target='head')=>{const el=document.createElement('span');el.className='part-label';el.textContent=text;el.style.borderColor=color;$('model-labels').append(el);labels.push({el,p:new T.Vector3(...p),target});};
 if(state.mode==='feed'){add('二级伸缩与同步传动',[-198,0,0],palette.grasp);add('轴向五格盘',c.rotor_center_mm,palette.magazine);add('前端常闭止弹片',[-96.5,0,0],palette.grasp);add('摩擦轮接管区',[-8,0,0],palette.magazine);}
 else if(state.mode==='underside'){add('三点承压／定位键',[-52,0,-56],palette.grasp);add('被动拉紧销',[-15,-29,-64],palette.grasp);add('车侧双钩与执行器',[-31,57,-78],palette.claw,'seat');add('浮动电接头占位',[20,-20,-62],palette.electronics,'seat');}
 else{add(`${c.slots}槽 · 装${state.ammo}发`,c.rotor_center_mm,palette.magazine);add('两侧承重耳',c.grip_point_mm,palette.grasp);add('现有机箱＋相机',[95,0,117],palette.electronics);if(state.mode==='layout')add('底部落座锁紧',[-30,-30,-57],palette.claw);}
}
function projectLabels(){if(!head)return;const w=$('model-host').clientWidth,h=$('model-host').clientHeight,placed=[];for(const l of labels){const p=(l.target==='seat'?seat:head).localToWorld(l.p.clone()).project(camera);const ew=l.el.offsetWidth,eh=l.el.offsetHeight;let x=T.MathUtils.clamp((p.x+1)/2*w,ew/2+8,w-ew/2-8),y=T.MathUtils.clamp((1-p.y)/2*h,92,h-32);for(const q of placed)if(Math.abs(q.x-x)<(q.w+ew)/2+4&&Math.abs(q.y-y)<eh+7)y=q.y+eh+7;placed.push({x,y,w:ew});l.el.style.left=x+'px';l.el.style.top=Math.min(y,h-30)+'px';l.el.style.display=p.z<-1||p.z>1?'none':'block';}}
function stop(){state.playing=false;$('play').textContent='播放取放';$('play').setAttribute('aria-pressed','false');}
function stopFeed(){state.feedPlaying=false;$('feed-play').textContent='播放推送';$('feed-play').setAttribute('aria-pressed','false');}

function applyFeed(){
 const c=current();if(!head?.userData.axial)return;
 const d=c.axial_metrics,a=head.userData.axial;
 const f=state.mode==='feed'?feedFrame(state.feedProgress,c,cfg):{phase:0,stroke_mm:0,gate_open_fraction:0,rotor_angle_deg:0,ball_present:true,ball_center_x_mm:c.rotor_center_mm[0],indexing_allowed:true};
 a.stage1.position.x=d.home_face_x_mm-d.stage_length_mm/2+f.stroke_mm/2;
 a.stage2.position.x=d.home_face_x_mm-d.stage_length_mm/2-2+f.stroke_mm;
 a.tip.position.x=d.home_face_x_mm-2+f.stroke_mm;
 a.sync.position.x=f.stroke_mm/2;a.gate.position.y=c.axial.gate_travel_mm*f.gate_open_fraction;
 a.rotor.rotation.x=T.MathUtils.degToRad(f.rotor_angle_deg);
 head.userData.balls.children.forEach((b,i)=>{const ang=i*2*Math.PI/c.slots+T.MathUtils.degToRad(f.rotor_angle_deg);b.position.set(c.rotor_center_mm[0],c.radius_mm*Math.sin(ang),c.rotor_center_mm[2]-c.radius_mm*Math.cos(ang));if(i===0&&f.phase>=2)b.position.x=f.ball_center_x_mm;b.visible=i<state.ammo&&(i!==0||f.ball_present);});
 $('feed-progress').value=state.feedProgress;$('feed-progress-label').textContent=`${Math.round(state.feedProgress)}%`;
 $('feed-phase').textContent=feedPhases[f.phase][0];$('feed-note').textContent=feedPhases[f.phase][1];
 $('feed-stroke').textContent=f.stroke_mm.toFixed(1)+' mm';$('feed-gate').textContent=f.gate_open_fraction<.001?'已关闭':f.gate_open_fraction>.999?'已打开':'移动中';$('feed-interlock').textContent=f.indexing_allowed?'允许分度':'禁止分度';
 $('feed-pitch-label').textContent=state.feedPitch+'°';
 drawAxialSection(c,f);
}

function svgElement(svg,tag,attrs,text){const n=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const[k,v]of Object.entries(attrs))n.setAttribute(k,v);if(text!=null)n.textContent=text;svg.append(n);return n;}
function drawAxialSection(c,f){
 const svg=$('axial-section');svg.replaceChildren();const s=1.55,X=x=>68+(x+250)*s,Z=z=>205-z*s;
 const el=(tag,a,t)=>svgElement(svg,tag,a,t),rect=(x,z,w,h,fill,stroke=fill)=>el('rect',{x:X(x),y:Z(z+h),width:w*s,height:h*s,fill,stroke,'stroke-width':1.1});
 const d=c.axial_metrics,L=d.stage_length_mm,home=d.home_face_x_mm,stroke=f.stroke_mm,x=c.rotor_center_mm[0];
 rect(-37,-26,95,52,'#dbe5ed','#a8bac8');rect(58,-18,89,36,'#dbe5ed','#a8bac8');rect(-37,-23,68,46,'#ffffff');
 rect(x-c.rotor_depth_mm/2,-27,c.rotor_depth_mm,138,'#dae8f7','#427bbd');rect(x-c.rotor_depth_mm/2,-23,c.rotor_depth_mm,46,'#ffffff','#78a1ca');
 rect(home-L,-12,L,24,'#c9d5df','#50657a');rect(home-L+stroke/2,-8,L,16,'#8da8bd','#50657a');
 rect(home-L+stroke,-4,L-4,8,'#d9a450','#a77c35');rect(home+stroke-4,-6,4,12,'#be882a');
 for(const zz of [-25.5,23])rect(-92,zz,56,2.5,'#afc8dd','#6c98bc');
 if(f.gate_open_fraction<.99)rect(-98,-23,3,46,'#d4a254','#aa7730');else el('line',{x1:X(-96.5),y1:Z(-25),x2:X(-96.5),y2:Z(25),stroke:'#4c8d7c','stroke-width':2,'stroke-dasharray':'4 4'});
 const [cx,cz]=[X(f.ball_center_x_mm),Z(0)];
 if(f.phase>=1&&f.ball_present&&state.ammo>0)el('circle',{cx,cy:cz,r:cfg.ball_diameter_mm/2*s,fill:'#e7b86c',stroke:'#ba852d','stroke-width':1.5});
 el('line',{x1:X(d.unloaded_wheel_first_contact_ball_x_mm),y1:Z(-28),x2:X(d.unloaded_wheel_first_contact_ball_x_mm),y2:Z(32),stroke:'#6b8193','stroke-width':1.3,'stroke-dasharray':'5 4'});
 const text=(x,y,t,anchor='middle')=>el('text',{x,y,'text-anchor':anchor},t);
 text(X(home-L/2),Z(24),'电机／一级套管');text(X(x),Z(100),'五格盘 · 转轴沿炮口');
 text(X(-64),Z(35),'短直导路');text(X(34),Z(54),'摩擦轮接管');
 text(X(-96.5),Z(-39),f.gate_open_fraction>.99?'止弹片已让开':'出口常闭止弹');
 text(30,24,'XZ剖视；只画发射工位，分度过程见三维盘面','start');
 text(770,24,feedPhases[f.phase][0],'end');
 el('line',{x1:X(home),y1:Z(-55),x2:X(d.end_face_x_mm),y2:Z(-55),stroke:'#9a792c','stroke-width':1.2});
 for(const xx of [home,d.end_face_x_mm])el('line',{x1:X(xx),y1:Z(-51),x2:X(xx),y2:Z(-59),stroke:'#9a792c','stroke-width':1.2});
 text(X((home+d.end_face_x_mm)/2),Z(-70),`推头总行程 ${d.stroke_mm.toFixed(1)} mm，球心从 −120 mm 主动送至 −8 mm`);
}

function updateAxialDetails(){
 const c=current(),active=c.kind==='axial';$('feed-mode-button').hidden=!active;$('axial-method').hidden=!active;
 if(!active)return;const d=c.axial_metrics,m=mass(c,state.ammo);
 $('axial-stroke').textContent=d.stroke_mm.toFixed(1)+' mm';$('axial-overlap').textContent=d.each_stage_extension_mm.toFixed(1)+' / '+d.remaining_overlap_mm.toFixed(1)+' mm';$('axial-margin').textContent=d.storage_length_margin_mm.toFixed(1)+' mm';
 $('axial-length-tradeoff').textContent=`在同样后退净空和25 mm搭接假设下，单级杆式总长约${Math.ceil(d.single_stage_total_length_mm)} mm；两级布局约${Math.ceil(c.metrics.size_mm[0])} mm。外接头与公差空间仍紧。头部约${m.total.toFixed(3)} kg，含当前夹爪约${m.payload.toFixed(3)} kg，质量不是实测。`;
 drawAxialSection(c,feedFrame(state.mode==='feed'?state.feedProgress:12,c,cfg));
}

function updateProjections(){
 const c=current(),b=c.metrics.bounds_mm,ns='http://www.w3.org/2000/svg';
 for(const [id,top]of [['projection-side',false],['projection-top',true]]){
  const svg=$(id);svg.replaceChildren();const low=top?b[0][1]:b[0][2],high=top?b[1][1]:b[1][2];const scale=Math.min(350/(b[1][0]-b[0][0]),150/(high-low));const ox=35-b[0][0]*scale,oy=180+low*scale;
  if(top&&c.kind==='axial'){
   const el=(tag,a,t)=>svgElement(svg,tag,a,t),cy=102,s=1.06;
   el('circle',{cx:210,cy,r:(c.outer_radius_mm+2)*s,fill:'#d9e6f3',stroke:'#427bbd','stroke-width':1.5});
   for(const p of c.ball_centers_mm.slice(0,state.ammo))el('circle',{cx:210+p[1]*s,cy:cy-(p[2]-42)*s,r:cfg.ball_diameter_mm/2*s,fill:'#e7b86c',stroke:'#ca963d'});
   el('circle',{cx:210,cy:cy+42*s,r:23*s,fill:'none',stroke:'#478d7e','stroke-width':2.5});
   el('line',{x1:236,y1:cy+42*s,x2:296,y2:cy+42*s,stroke:'#478d7e'});
   el('text',{x:300,y:cy+42*s+4,'font-size':11},'入口工位');
   el('text',{x:210,y:211,'text-anchor':'middle'},'YZ盘面 · Ø138 mm五格盘');continue;
  }
  const el=(tag,attrs,text)=>{const n=document.createElementNS(ns,tag);for(const[k,v]of Object.entries(attrs))n.setAttribute(k,v);if(text!=null)n.textContent=text;svg.append(n);return n;};
  const rect=(x,y,w,h,fill,stroke=fill)=>el('rect',{x:ox+x*scale,y:oy-(y+h)*scale,width:w*scale,height:h*scale,fill,stroke,'stroke-width':1.2,rx:1});
  const circle=(x,y,r,fill,stroke)=>el('circle',{cx:ox+x*scale,cy:oy-y*scale,r:r*scale,fill,stroke:stroke||fill,'stroke-width':1.1});
  rect(b[0][0],low,b[1][0]-b[0][0],high-low,'none','#a7bacb');
  rect(-86.7,top?-79:-32,234.4,top?158:76,'#cbd5de','#a2b3c0');
  rect(18.75,top?-40.5:63,98.5,top?81:34,'#8eb7b2','#619b98');
  const [x,,z]=c.rotor_center_mm,r=c.outer_radius_mm;
  if(c.kind==='axial'){
   rect(x-c.rotor_depth_mm/2,z-r,c.rotor_depth_mm,2*r,'#d9e6f3','#427bbd');
   rect(c.axial_metrics.home_face_x_mm-c.axial_metrics.stage_length_mm,-12,c.axial_metrics.stage_length_mm,24,'#8fa9bd','#50657a');
   rect(-95,-25.5,59,51,'none','#7aa2c4');
  }
  for(const p of c.parts.filter(p=>p.role==='grasp'&&p.shape==='box'))rect(p.at[0]-p.size[0]/2,p.at[top?1:2]-p.size[top?1:2]/2,p.size[0],p.size[top?1:2],'#d99937');
  if(!top)rect(-70,-56,110,6,'#b4873e');
  const cg=mass(c,state.ammo).cg;circle(cg[0],cg[top?1:2],3,'#aa455e');
  el('text',{x:210,y:211,'text-anchor':'middle'},`长 ${Math.ceil(c.metrics.size_mm[0])} mm · ${top?'宽':'高'} ${Math.ceil(c.metrics.size_mm[top?1:2])} mm`);
 }
 $('projection-top-caption').textContent='盘面：仅入口一格轴向推出';
 $('projection-note').textContent='左侧是推头收拢占位，右侧是YZ盘面。分格盘不再占头部后上方，但推送驱动拉长尾部。';
}

function updateDetails(){
 const c=current(),m=mass(c,state.ammo),size=c.metrics.size_mm.map(Math.ceil).join(' × ');
 $('candidate-tag').textContent=c.tag;$('candidate-title').textContent=c.title;$('candidate-why').textContent=c.why;
 for(const key of ['reuse','tradeoff','next'])$('candidate-'+key).textContent=c[key];
 $('model-title').textContent=c.title;$('model-subtitle').textContent='真实发射核心与机箱；其余为布局几何';
 $('size-value').textContent=size;$('volume-value').textContent=c.metrics.bounding_volume_l.toFixed(2)+' L';$('mass-value').textContent=m.total.toFixed(3)+' kg';$('payload-value').textContent=m.payload.toFixed(3)+' kg';
 const diff=cfg.rated_endpoint_mass_kg-m.payload;
 $('payload-note').textContent=`按3 kg额定末端质量比较，${diff>=0?'尚余':'超出'}约${Math.round(Math.abs(diff)*1000)} g；还需核实允许重心和弯矩。车侧锁紧、pitch/yaw及电机不在夹起的头内。`;
 $('mass-breakdown').replaceChildren();for(const r of m.rows.filter(r=>!r.name.startsWith('弹丸')).concat([{name:`实际弹丸 ${state.ammo} 发`,kg:state.ammo*cfg.ball_mass_kg}])){const row=document.createElement('div');row.className='mass-row';const a=document.createElement('span'),b=document.createElement('span');a.textContent=r.name;b.textContent=(r.kg*1000).toFixed(0)+' g';row.append(a,b);$('mass-breakdown').append(row);}
 const d=m.cg.map((v,i)=>(v-c.wrist_point_mm[i])/1000),horizontal=m.total*9.81*Math.hypot(d[0],d[1]),bound=m.total*9.81*Math.hypot(...d);
 $('grip-moment').textContent=`预算重心 (${m.cg.map(v=>v.toFixed(1)).join(', ')}) mm；相对所画腕部TCP，水平搬运重力静矩 ${horizontal.toFixed(2)} N·m，任意倾角静矩上界 ${bound.toFixed(2)} N·m。只含头部重力，不含夹爪偏心、加速、冲击或各关节负载，不能据此选电机。`;
 updateBudget();updateProjections();updateAxialDetails();if(head){makeLabels();motion();}
}
function updateBudget(){
 const c=current(),m=mass(c,state.ammo),tr=document.createElement('tr');
 for(const value of [c.title,`${c.slots} / ${state.ammo}`,c.metrics.size_mm.map(Math.ceil).join(' × '),c.metrics.bounding_volume_l.toFixed(2),m.total.toFixed(3),m.payload.toFixed(3),c.metrics.pocket_web_mm.toFixed(2)]){const td=document.createElement('td');td.textContent=value;tr.append(td);}
 $('comparison-body').replaceChildren(tr);
}
function select(id){state.id=id;state.ammo=current().ammo;state.progress=0;state.feedProgress=0;state.feedPitch=0;stop();stopFeed();const c=current();$('feed-pitch').value=0;$('ammo').replaceChildren();for(let n=0;n<=c.ammo;n++){const option=document.createElement('option');option.value=n;option.textContent=n+' 发';$('ammo').append(option);}$('ammo').value=state.ammo;if(scene){clear(head);clear(gripper);if(head)scene.remove(head);if(gripper)scene.remove(gripper);head=makeHead(c);gripper=makeGripper(c);scene.add(head,gripper);}updateDetails();setMode(state.mode);history.replaceState(null,'','#'+id);}

function init(){
 scene=new T.Scene();scene.background=new T.Color('#edf3f7');const host=$('model-host');
 renderer=new T.WebGLRenderer({antialias:true,preserveDrawingBuffer:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.outputColorSpace=T.SRGBColorSpace;renderer.toneMapping=T.ACESFilmicToneMapping;renderer.toneMappingExposure=1.12;renderer.domElement.setAttribute('aria-label','可旋转的头部、夹爪和底部安装座三维概念布局');host.append(renderer.domElement);
 camera=new T.OrthographicCamera(-380,380,260,-260,1,6000);camera.up.set(0,0,1);orbit=new OrbitControls(camera,renderer.domElement);orbit.enableDamping=true;orbit.minZoom=.22;orbit.maxZoom=3;
 scene.add(new T.HemisphereLight('#ffffff','#8b9faf',2.1));const key=new T.DirectionalLight('#fffdf6',2.8);key.position.set(200,-450,850);scene.add(key);const fill=new T.DirectionalLight('#e5efff',1.2);fill.position.set(-400,300,350);scene.add(fill);
 seat=makeSeat();scene.add(seat);environment=makeEnvironment();scene.add(environment);
 const resize=()=>{const w=host.clientWidth,h=host.clientHeight;renderer.setSize(w,h,false);const extent=w<480?300:265;camera.left=-extent*w/h;camera.right=extent*w/h;camera.top=extent;camera.bottom=-extent;camera.updateProjectionMatrix();};new ResizeObserver(resize).observe(host);resize();
 select(study.candidates.some(c=>c.id===location.hash.slice(1))?location.hash.slice(1):'axial5');setMode('layout');
 $('page-status').textContent='轴向五格直推 · 真实核心网格';
 window.__pickPlace={ready:true,state,study,metrics:()=>mass(current(),state.ammo),frame,feedSnapshot:()=>({visibleBalls:head.userData.balls.children.filter(b=>b.visible).length,ball0:head.userData.balls.children[0].position.toArray(),tipFaceX:head.userData.axial.tip.position.x+2,gateY:head.userData.axial.gate.position.y,pitchDeg:-T.MathUtils.radToDeg(head.rotation.y)}),feedFrame:p=>feedFrame(p,study.candidates.find(c=>c.id==='axial5'),cfg),select,setMode,geometryBounds:()=>{head.updateMatrixWorld();const b=new T.Box3();head.traverse(o=>{if(o.isMesh&&!o.userData.skipBounds){o.geometry.computeBoundingBox();const local=o.geometry.boundingBox.clone().applyMatrix4(o.matrixWorld);b.union(local);}});return b.getSize(new T.Vector3()).toArray();}};
 const animate=now=>{requestAnimationFrame(animate);const dt=Math.min((now-last)/1000,.06);last=now;if(state.playing){state.progress=Math.min(100,state.progress+dt*9);motion();if(state.progress>=100)stop();}if(state.feedPlaying){state.feedProgress=Math.min(100,state.feedProgress+dt*9);applyFeed();if(state.feedProgress>=100)stopFeed();}orbit.update();scene.updateMatrixWorld();projectLabels();renderer.render(scene,camera);};requestAnimationFrame(animate);
}

document.querySelectorAll('[data-mode]').forEach(b=>b.onclick=()=>setMode(b.dataset.mode));document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>setView(b.dataset.view));
for(const id of ['show-shell','show-route','show-envelope','show-gripper','show-seat'])$(id).onchange=visibility;
$('ammo').onchange=e=>{state.ammo=+e.target.value;updateDetails();};
for(const [id,key]of[['core-mass','coreMass'],['gripper-mass','gripperMass']])$(id).addEventListener('input',e=>{if(!e.target.checkValidity()||!e.target.value)return;state[key]=+e.target.value/1000;updateDetails();});
$('progress').oninput=e=>{stop();state.progress=+e.target.value;motion();};$('rewind').onclick=()=>{stop();state.progress=0;motion();};$('play').onclick=()=>{if(state.playing){stop();return;}if(state.progress>=100)state.progress=0;state.playing=true;$('play').textContent='暂停取放';$('play').setAttribute('aria-pressed','true');};
$('feed-progress').oninput=e=>{stopFeed();state.feedProgress=+e.target.value;applyFeed();};$('feed-pitch').oninput=e=>{state.feedPitch=+e.target.value;motion();};$('feed-rewind').onclick=()=>{stopFeed();state.feedProgress=0;applyFeed();};$('feed-play').onclick=()=>{if(state.feedPlaying){stopFeed();return;}if(state.feedProgress>=100)state.feedProgress=0;state.feedPlaying=true;$('feed-play').textContent='暂停推送';$('feed-play').setAttribute('aria-pressed','true');};$('last-round').onclick=()=>{stopFeed();state.ammo=1;state.feedProgress=0;$('ammo').value=1;updateDetails();};$('open-feed-demo').onclick=()=>{setMode('feed');$('model-host').scrollIntoView({block:'center',behavior:matchMedia('(prefers-reduced-motion:reduce)').matches?'instant':'smooth'});};
$('export').onclick=()=>{const c=current(),trajectory=Array.from({length:101},(_,i)=>{const f=frame(i),w=c.wrist_point_mm.map((v,k)=>v+f.gripper[k]);return{progress:i,phase:phaseNotes[f.phase][0],head_translation_mm:f.head,head_rotation_xyz_deg:[0,0,0],wrist_target_position_mm:w,wrist_target_pose_mm:[[1,0,0,w[0]],[0,-1,0,w[1]],[0,0,-1,w[2]],[0,0,0,1]],gripper_opening_offset_per_jaw_mm:f.open,lock_progress:f.lock};});const out={date:study.date,candidate:c,current_mass_budget:mass(c,state.ammo),gripper_mass_kg:state.gripperMass,trajectory,wrist_frame_assumption:'Flange +Z points down, +X toward muzzle, +Y opposite head +Y. Must calibrate against actual gripper CAD.',limits:'Task target poses only, using an assumed flange frame. No solved IK, collision, contact forces or joint dynamics. Seat/head/table placement assumptions are adjustable.'};if(c.kind==='axial'){out.feed_cycle=Array.from({length:101},(_,p)=>feedFrame(p,c,cfg));out.feed_cycle_initial_ammo=state.ammo;out.feed_pitch_deg=state.feedPitch;out.feed_scope='Illustrative milestone sequence. Not firmware or contact simulation.';}const url=URL.createObjectURL(new Blob([JSON.stringify(out,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=`pick-place-${c.id}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
document.addEventListener('visibilitychange',()=>{if(document.hidden){stop();stopFeed();}});window.addEventListener('hashchange',()=>{const id=location.hash.slice(1);if(study.candidates.some(c=>c.id===id)&&id!==state.id)select(id);});
try{init();}catch(error){console.error(error);$('render-error').hidden=false;$('page-status').textContent='三维未启动；参数数据仍可查看';scene=null;head=null;select('axial5');window.__pickPlace={ready:false,error:String(error),study};}
