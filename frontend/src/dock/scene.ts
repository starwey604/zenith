import * as T from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { contacts, layout, defaults, dockPose, wireBudget, type Mode, type Alignment, type Harness } from './model';
const colors={base:'#5687a5',head:'#8fa4b1',guide:'#b6c9d5',gold:'#d5a049',datum:'#3d8c7e',lock:'#526c7f',purple:'#9b7cae'};
function material(color:string,opacity=1){return new T.MeshStandardMaterial({color,roughness:.55,metalness:.18,transparent:opacity<1,opacity,depthWrite:opacity===1});}
function mesh(g:T.Object3D,geom:T.BufferGeometry,p:number[],color:string,opacity=1){const m=new T.Mesh(geom,material(color,opacity));m.position.set(...p as [number,number,number]);g.add(m);return m;}
function box(g:T.Object3D,size:number[],p:number[],color:string,opacity=1){return mesh(g,new T.BoxGeometry(...size as [number,number,number]),p,color,opacity);}
function cylinder(g:T.Object3D,r:number,h:number,p:number[],color:string,axis='Z'){const m=mesh(g,new T.CylinderGeometry(r,r,h,32),p,color);if(axis==='Z')m.rotation.x=Math.PI/2;if(axis==='X')m.rotation.z=Math.PI/2;return m;}
function outline(g:T.Object3D,size:number[],p:number[],color:string){const geom=new T.BoxGeometry(...size as [number,number,number]);const line=new T.LineSegments(new T.EdgesGeometry(geom),new T.LineBasicMaterial({color,transparent:true,opacity:.7}));geom.dispose();line.position.set(...p as [number,number,number]);g.add(line);return line;}
function annulus(g:T.Object3D,outer:number,inner:number,depth:number,p:number[],color:string){const s=new T.Shape();s.absarc(0,0,outer,0,Math.PI*2,false);const h=new T.Path();h.absarc(0,0,inner,0,Math.PI*2,true);s.holes.push(h);return mesh(g,new T.ExtrudeGeometry(s,{depth,bevelEnabled:false,curveSegments:24}),p,color);}
function plate(g:T.Object3D){const s=new T.Shape();s.moveTo(-74,-58);s.lineTo(74,-58);s.lineTo(74,58);s.lineTo(-74,58);s.closePath();for(const x of [-45,45]){const h=new T.Path();h.absarc(x,0,4.1,0,Math.PI*2,true);s.holes.push(h);}return mesh(g,new T.ExtrudeGeometry(s,{depth:8,bevelEnabled:false,curveSegments:24}),[0,0,20],colors.head);}
function tube(g:T.Object3D,points:T.Vector3[],radius:number,color:string){const path=new T.CurvePath<T.Vector3>();for(let i=1;i<points.length;i++)path.add(new T.LineCurve3(points[i-1],points[i]));return mesh(g,new T.TubeGeometry(path,Math.max(36,points.length*2),radius,8,false),[0,0,0],color);}
function dispose(g:T.Group){g.traverse(o=>{if(o instanceof T.Mesh||o instanceof T.LineSegments){o.geometry.dispose();(Array.isArray(o.material)?o.material:[o.material]).forEach(m=>m.dispose());}});g.clear();}
export class DockScene {
  renderer:T.WebGLRenderer;camera=new T.PerspectiveCamera(35,1,1,3000);controls:OrbitControls;scene=new T.Scene();
  fixed=new T.Group();head=new T.Group();headFrame=new T.Group();headBox=new T.Group();carBox=new T.Group();headWires=new T.Group();carWires=new T.Group();keepouts=new T.Group();headKeepouts=new T.Group();hooks:T.Group[]=[];pins:T.Mesh[]=[];sleeve=new T.Group();
  mode:Mode='mechanical';alignment:Alignment={dx:6,dy:4,yaw:2};progress=2;ammo=false;headView=false;cutaway=false;wires=true;envelopes=true;selected='F1';isolate=false;harness:Harness={...defaults};
  onTick:(dt:number)=>void=()=>{};onSelect:(id:string)=>void=()=>{};
  private floor!:T.GridHelper;private selection=new T.Box3Helper(new T.Box3(),0x24769d);
  private observer:ResizeObserver;private raf=0;private last=0;private markers:{node:HTMLElement;point:T.Vector3;owner:T.Object3D;mode:Mode[]}[]=[];private pick=new T.Raycaster();private down=[0,0];
  constructor(private host:HTMLElement){
    this.scene.background=new T.Color('#edf3f6');this.camera.up.set(0,0,1);this.renderer=new T.WebGLRenderer({antialias:true});this.renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));this.renderer.outputColorSpace=T.SRGBColorSpace;this.renderer.toneMapping=T.ACESFilmicToneMapping;
    this.renderer.domElement.setAttribute('aria-label','底座导向、定位、锁紧与电触点线束三维示意');this.renderer.domElement.tabIndex=0;host.append(this.renderer.domElement);
    this.controls=new OrbitControls(this.camera,this.renderer.domElement);this.controls.enableDamping=true;this.controls.minDistance=65;this.controls.maxDistance=1600;
    this.scene.add(new T.HemisphereLight(0xffffff,0x7d909c,3));const light=new T.DirectionalLight(0xfff7e7,3);light.position.set(100,-180,400);this.scene.add(light);
    this.scene.add(this.fixed,this.head,this.carBox,this.carWires,this.keepouts);this.head.add(this.headFrame,this.headBox,this.headWires,this.headKeepouts);
    const grid=new T.GridHelper(800,32,0xc6d4de,0xdde6ec);grid.rotation.x=Math.PI/2;grid.position.z=-75;this.scene.add(grid,this.selection);this.floor=grid;
    this.mechanics();this.connector(this.carBox,false);this.connector(this.headBox,true);this.makeWires();
    this.mark('喇叭口粗导向',[-90,-30,63],this.fixed,['mechanical']);this.mark('三点承压',[55,-42,20],this.fixed,['mechanical']);this.mark('圆销 / 菱形销',[0,0,40],this.fixed,['mechanical']);this.mark('独立触点盒',[0,103,31],this.carBox,['mechanical']);
    this.mark('头侧焊尾与线夹',[-35,105,82],this.head,['harness']);this.mark('车侧检修空间',[-35,135,-35],this.carWires,['harness']);
    this.mark('接触面 · 电流等级待选型',[0,100,30],this.carBox,['contacts']);
    this.observer=new ResizeObserver(()=>this.resize());this.observer.observe(host);this.resize();this.update();this.view('iso');
    this.renderer.domElement.addEventListener('pointerdown',e=>this.down=[e.clientX,e.clientY]);
    this.renderer.domElement.addEventListener('pointerup',e=>{if(Math.hypot(e.clientX-this.down[0],e.clientY-this.down[1])>5)return;const rect=this.renderer.domElement.getBoundingClientRect();this.pick.setFromCamera(new T.Vector2((e.clientX-rect.left)/rect.width*2-1,-(e.clientY-rect.top)/rect.height*2+1),this.camera);const hits=this.pick.intersectObjects([this.headBox,this.carBox,this.headWires,this.carWires],true);for(const hit of hits){let visible=true;for(let o:T.Object3D|null=hit.object;o;o=o.parent)visible&&=o.visible;if(visible&&hit.object.userData.contactId){this.onSelect(hit.object.userData.contactId);break;}}});
    const animate=(time:number)=>{this.raf=requestAnimationFrame(animate);const dt=this.last?Math.min((time-this.last)/1000,.1):0;this.last=time;this.onTick(dt);this.controls.update();this.scene.updateMatrixWorld();for(const m of this.markers){const p=m.owner.localToWorld(m.point.clone()).project(this.camera);m.node.hidden=!m.mode.includes(this.mode)||!m.owner.visible||p.z>1||Math.abs(p.x)>.9||Math.abs(p.y)>.85;m.node.style.left=`${(p.x+1)*host.clientWidth/2}px`;m.node.style.top=`${(1-p.y)*host.clientHeight/2}px`;}this.renderer.render(this.scene,this.camera);};this.raf=requestAnimationFrame(animate);
  }
  private mark(text:string,point:number[],owner:T.Object3D,mode:Mode[]){const node=document.createElement('span');node.className='d-label';node.textContent=text;this.host.append(node);this.markers.push({node,point:new T.Vector3(...point as [number,number,number]),owner,mode});}
  private mechanics(){
    box(this.fixed,[184,154,8],[0,0,4],colors.base);
    for(const x of[-40,40])box(this.fixed,[14,40,8],[x,87,4],colors.base);
    for(const [x,y]of[[-55,-42],[55,-42],[0,48]])cylinder(this.fixed,10,12,[x,y,14],colors.datum);
    // Coarse ramps flare outward; final 2 mm clearance prevents them defining a second datum.
    const ramp=(inner:number,outer:number,length:number)=>{const s=new T.Shape();s.moveTo(inner,28);s.lineTo(inner+6,28);s.lineTo(outer+6,62);s.lineTo(outer,62);s.closePath();const geom=new T.ExtrudeGeometry(s,{depth:length,bevelEnabled:false});geom.rotateX(Math.PI/2);geom.translate(0,length/2,0);return geom;};
    for(const sign of[-1,1]){const xg=mesh(this.fixed,ramp(76,88,32),[0,-30,0],colors.guide);xg.scale.x=sign;const yg=mesh(this.fixed,ramp(60,72,16),[-67,0,0],colors.guide);yg.rotation.z=sign*Math.PI/2;}
    cylinder(this.fixed,4,23,[-45,0,23.5],colors.gold);const cone=mesh(this.fixed,new T.CylinderGeometry(1.5,4,5,32),[-45,0,37.5],colors.gold);cone.rotation.x=Math.PI/2;
    // Diamond pin is relieved along the X baseline; Y faces retain the anti-yaw constraint.
    box(this.fixed,[5,8,23],[45,0,23.5],colors.gold);const top=mesh(this.fixed,new T.ConeGeometry(4,5,4),[45,0,37.5],colors.gold);top.rotation.x=Math.PI/2;top.scale.x=.625;
    for(const x of[-45,45]){cylinder(this.fixed,7,5,[x,0,10.5],colors.lock);annulus(this.headFrame,8,4.1,4,[x,0,28],colors.gold);}
    plate(this.headFrame);for(const x of[-68,68])box(this.headFrame,[8,100,30],[x,0,43],colors.head);
    outline(this.headFrame,[148,116,90],[0,0,73],'#9babb5');
    for(const x of[-40,40])box(this.headFrame,[12,34,10],[x,74,33],colors.head);
    for(const sign of[-1,1]){const h=new T.Group();h.position.set(sign*90,20,10);this.fixed.add(h);box(h,[8,16,24],[0,0,9],colors.lock);box(h,[30,16,6],[-sign*11,0,21],colors.lock);cylinder(h,4,22,[0,0,0],colors.gold,'Y');this.hooks.push(h);box(this.fixed,[24,30,24],[sign*92,20,-8],colors.purple);}
    const receiver=annulus(this.headFrame,27,22,16,[-74,0,55],colors.head);receiver.rotation.y=Math.PI/2;
    this.fixed.add(this.sleeve);const tube=annulus(this.sleeve,27,22,22,[-108,0,55],colors.base);tube.rotation.y=Math.PI/2;
  }
  private connector(g:T.Group,head:boolean){
    if(head){box(g,[42,42,11],[-33,100,32.5],'#536f80');box(g,[62,42,11],[23,100,32.5],'#536f80');box(g,[108,42,6],[0,100,41],'#536f80');}
    else box(g,[108,42,16],[0,100,16],'#345870');
    // Keying pocket and insulated power/signal wall. Grey C0 is reserve volume, not a wired contact.
    if(!head){box(g,[4,42,12],[-10,100,26],colors.head);box(g,[14,14,8],[-56,82,18],colors.lock);cylinder(g,3,12,[-58,82,26],colors.gold);}
    else annulus(g,6,3.5,12,[-58,82,26],colors.head);
    outline(g,[14,24,18],[64,100,head?35:17],'#977eaa');
    for(const c of contacts){const power=c.circuit==='FIRE'||c.circuit==='AUX';const z=head?26:28-(c.circuit==='PRESENT'?.8:0);let pad:T.Mesh;
      if(head)pad=box(g,[power?10:8,power?10:8,1],[c.x,c.y,z+.5],colors.gold);
      else {cylinder(g,power?3.6:2.3,7,[c.x,c.y,22],'#8098aa');pad=cylinder(g,power?3:1.8,3,[c.x,c.y,z-1.5],colors.gold);pad.userData.freeZ=z;this.pins.push(pad);}
      pad.userData.contactId=c.id;
    }
    for(const x of[-48,48])for(const y of[83,117]){cylinder(g,2.7,5,[x,y,head?43:11],colors.head);}
    if(!head){outline(g,[109.6,43.6,18],[0,100,17],'#678c9f');}
  }
  makeWires(){
    dispose(this.headWires);dispose(this.carWires);dispose(this.keepouts);dispose(this.headKeepouts);
    for(const head of[false,true])for(const c of contacts){
      const g=head?this.headWires:this.carWires,sign=head?1:-1,dir=head?-1:1,origin=head?layout.headTailZ:layout.vehicleTailZ;
      const od=(c.circuit==='FIRE'||c.circuit==='AUX')?this.harness.powerOD:this.harness.signalOD,b=wireBudget(this.harness,od);
      const group=new T.Group();g.add(group);group.userData.contactId=c.id;
      cylinder(group,od*.38,this.harness.solder,[c.x,c.y,origin+sign*this.harness.solder/2],'#bd9b69');
      const shrink=cylinder(group,od/2+.7,b.straight,[c.x,c.y,origin+sign*b.straight/2],'#65717b');(shrink.material as T.MeshStandardMaterial).transparent=true;(shrink.material as T.MeshStandardMaterial).opacity=.6;
      const pts=[new T.Vector3(c.x,c.y,origin+sign*this.harness.solder),new T.Vector3(c.x,c.y,origin+sign*b.straight)];
      for(let i=1;i<=24;i++){const angle=i/24*Math.PI/2;pts.push(new T.Vector3(c.x,c.y+dir*b.radius*(1-Math.cos(angle)),origin+sign*(b.straight+b.radius*Math.sin(angle))));}
      pts.push(new T.Vector3(c.x,c.y+dir*(b.radius+26),origin+sign*(b.straight+b.radius)));
      tube(group,pts,od/2,c.color);
      const cuff=mesh(group,new T.TorusGeometry(od/2+1.2,1,8,16),[c.x,c.y+dir*(b.radius+14),origin+sign*(b.straight+b.radius)],colors.base);cuff.rotation.x=Math.PI/2;
      group.traverse(o=>o.userData.contactId=c.id);
    }
    const b=wireBudget(this.harness);outline(this.keepouts,[layout.boxX+4,layout.boxY+b.side+30,b.depth],[0,100+b.side/2+15,layout.vehicleTailZ-b.depth/2],'#ac7f45');
    outline(this.headKeepouts,[layout.boxX+4,layout.boxY+b.side+30,b.depth],[0,100-b.side/2-15,layout.headTailZ+b.depth/2],'#ac7f45');
    this.update();
  }
  update(){
    const p=dockPose(this.progress,this.alignment,this.ammo);this.floor.visible=this.mode!=='contacts';
    this.head.position.set(this.mode==='mechanical'?p.dx:0,this.mode==='mechanical'?p.dy:0,this.mode==='mechanical'?p.lift:this.mode==='harness'?70:0);this.head.rotation.z=this.mode==='mechanical'?p.yaw*Math.PI/180:0;
    this.fixed.visible=this.mode==='mechanical';this.headFrame.visible=this.mode==='mechanical'&&!this.cutaway;this.headBox.visible=this.mode!=='contacts'||this.headView;this.carBox.visible=this.mode!=='contacts'||!this.headView;
    this.headWires.visible=this.wires&&this.mode==='harness';this.carWires.visible=this.wires&&this.mode==='harness';this.keepouts.visible=this.envelopes&&this.mode==='harness';this.headKeepouts.visible=this.keepouts.visible;
    this.hooks.forEach((h,i)=>h.rotation.y=(i===0?-1:1)*(1-p.lock)*Math.PI*.35);this.sleeve.position.x=p.sleeve;
    for(const pin of this.pins){const free=pin.userData.freeZ as number;const face=this.mode==='mechanical'?layout.headContactZ+p.lift:free;pin.position.z=Math.min(free,face)-1.5;}
    for(const root of[this.carBox,this.headBox,this.carWires,this.headWires])root.traverse(o=>{if(o instanceof T.Mesh&&o.userData.contactId){const m=o.material as T.MeshStandardMaterial;const selected=o.userData.contactId===this.selected;m.emissive.set(selected?'#8d6228':'#000000');m.emissiveIntensity=selected?.35:0;o.visible=!this.isolate||selected||root===this.carBox||root===this.headBox;}});
    this.scene.updateMatrixWorld();this.selection.visible=this.mode==='contacts';const face=this.headView?this.headBox:this.carBox;face.traverse(o=>{if(o instanceof T.Mesh&&o.userData.contactId===this.selected)this.selection.box.setFromObject(o).expandByScalar(1);});
  }
  view(view:'iso'|'top'|'side'='iso'){
    let target:T.Vector3,offset:T.Vector3;
    if(this.mode==='contacts'){target=new T.Vector3(0,100,26);offset=new T.Vector3(0,this.headView?.1:-.1,this.headView?-230:230);}
    else if(this.mode==='harness'){target=new T.Vector3(0,105,50);offset=view==='side'?new T.Vector3(420,0,0):view==='top'?new T.Vector3(0,-.1,470):new T.Vector3(300,360,220);}
    else{target=new T.Vector3(0,20,65);offset=view==='top'?new T.Vector3(0,-.1,500):view==='side'?new T.Vector3(500,0,20):new T.Vector3(300,330,240);}
    this.controls.target.copy(target);this.camera.position.copy(target).add(offset);this.controls.update();
  }
  private resize(){this.camera.aspect=this.host.clientWidth/this.host.clientHeight;this.camera.zoom=Math.min(1,this.camera.aspect);this.camera.updateProjectionMatrix();this.renderer.setSize(this.host.clientWidth,this.host.clientHeight);}
  dispose(){cancelAnimationFrame(this.raf);this.observer.disconnect();this.controls.dispose();this.scene.traverse(o=>{if(o instanceof T.Mesh||o instanceof T.LineSegments){o.geometry.dispose();(Array.isArray(o.material)?o.material:[o.material]).forEach(m=>m.dispose());}});this.renderer.dispose();}
}
