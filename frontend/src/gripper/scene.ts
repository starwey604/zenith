import * as T from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { poseAt, type Candidate, type Task } from './model';
const C = { metal: '#8098aa', dark: '#29465a', pad: '#368d83', gold: '#d79935', purple: '#9b7cae', blue: '#4e85a9', ore: '#d4bca0' };
function box(g: T.Object3D, size: number[], p: number[], color: string) {
  const m = new T.Mesh(new T.BoxGeometry(...size as [number, number, number]), new T.MeshStandardMaterial({ color, roughness: .58, metalness: .22 }));
  m.position.set(...p as [number, number, number]); g.add(m);
  m.add(new T.LineSegments(new T.EdgesGeometry(m.geometry), new T.LineBasicMaterial({ color: '#234356', transparent: true, opacity: .18 })));
  return m;
}
function cylinder(g: T.Object3D, r: number, h: number, p: number[], color: string, axis = 'Y') {
  const m = new T.Mesh(new T.CylinderGeometry(r, r, h, 40), new T.MeshStandardMaterial({ color, roughness: .5, metalness: .3 }));
  m.position.set(...p as [number, number, number]); if (axis === 'Z') m.rotation.x = Math.PI / 2; if (axis === 'X') m.rotation.z = Math.PI / 2; g.add(m); return m;
}
function ring(g: T.Object3D, outer: number, inner: number, depth: number, z: number, color: string) {
  const shape = new T.Shape(); shape.absarc(0, 0, outer, 0, Math.PI * 2, false);
  const hole = new T.Path(); hole.absarc(0, 0, inner, 0, Math.PI * 2, true); shape.holes.push(hole);
  const mesh = new T.Mesh(new T.ExtrudeGeometry(shape, { depth, bevelEnabled: false, curveSegments: 40 }), new T.MeshStandardMaterial({ color, roughness: .7 }));
  mesh.position.z = z; g.add(mesh); return mesh;
}
function gear(g: T.Object3D, x: number) {
  const q = new T.Group(); q.position.set(x, 95, -22); g.add(q);
  cylinder(q, 36, 8, [0, 0, 0], C.metal, 'Z');
  for (let i = 0; i < 24; i++) { const a = i * Math.PI / 12; const tooth = box(q, [8, 7, 8], [Math.cos(a) * 38, Math.sin(a) * 38, 0], C.metal); tooth.rotation.z = a; }
  cylinder(q, 7, 14, [0, 0, 0], C.gold, 'Z'); return q;
}
export class GripperScene {
  renderer: T.WebGLRenderer; camera = new T.PerspectiveCamera(35, 1, 1, 3000); controls: OrbitControls;
  scene = new T.Scene(); world = new T.Group(); tool = new T.Group(); object = new T.Group(); fixtures = new T.Group();
  fingers: T.Group[] = []; gears: T.Group[] = []; parallelDrive = new T.Group(); angularDrive = new T.Group();
  task: Task = 'head'; candidate: Candidate = 'parallel'; progress = 2; closeup = false; forces = true;
  forceArrow = new T.ArrowHelper(new T.Vector3(0, -1, 0), new T.Vector3(0, -80, 10), 80, 0xc47a22, 14, 8);
  labels: { node: HTMLElement; anchor: T.Vector3; owner: T.Object3D; kinds?: Task[] }[] = [];
  private forceLabel!: HTMLElement;
  private observer: ResizeObserver; private frame = 0; private last = 0;
  onTick: (dt: number) => void = () => {};
  constructor(private host: HTMLElement) {
    this.scene.background = new T.Color('#edf3f6');
    this.renderer = new T.WebGLRenderer({ antialias: true }); this.renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
    this.renderer.outputColorSpace = T.SRGBColorSpace; this.renderer.toneMapping = T.ACESFilmicToneMapping;
    this.renderer.domElement.setAttribute('aria-label', '双用途夹爪三维示意，可拖动旋转和滚轮缩放'); this.renderer.domElement.tabIndex = 0; host.append(this.renderer.domElement);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement); this.controls.enableDamping = true; this.controls.minDistance = 170; this.controls.maxDistance = 1600;
    this.scene.add(new T.HemisphereLight(0xffffff, 0x8a9ca6, 3)); const light = new T.DirectionalLight(0xfff8ec, 3); light.position.set(160, 400, 300); this.scene.add(light);
    this.world.position.y = 170; this.scene.add(this.world); this.world.add(this.tool, this.object, this.fixtures); this.object.add(this.forceArrow);
    const floor = new T.GridHelper(1100, 22, '#beced9', '#dce6ec'); floor.position.y = 0; this.scene.add(floor);
    this.makeTool(); this.setTask('head'); this.view('iso');
    this.label('刚性指根', [65, 90, 18], this.tool);
    this.label('软垫夹矿', [-58, 10, 20], this.tool);
    this.label('承力槽 / 托唇', [78, -30, 20], this.tool);
    this.label('被动抓取座', [-12, -46, 26], this.object, ['head']);
    this.label('载荷方向', [0, 0, 0], this.forceArrow); this.forceLabel = this.labels.at(-1)!.node;
    this.observer = new ResizeObserver(() => this.resize()); this.observer.observe(host); this.resize();
    const animate = (time: number) => { this.frame = requestAnimationFrame(animate); const dt = this.last ? Math.min((time - this.last) / 1000, .1) : 0; this.last = time; this.onTick(dt); this.controls.update(); this.updateLabels(); this.renderer.render(this.scene, this.camera); }; this.frame = requestAnimationFrame(animate);
  }
  private label(text: string, p: number[], owner: T.Object3D, kinds?: Task[]) {
    const node = document.createElement('span'); node.className = 'g-label'; node.textContent = text; this.host.append(node); this.labels.push({ node, anchor: new T.Vector3(...p as [number, number, number]), owner, kinds });
  }
  private updateLabels() {
    this.scene.updateMatrixWorld();
    for (const l of this.labels) { const p = l.owner.localToWorld(l.anchor.clone()).project(this.camera); l.node.hidden = (!!l.kinds && !l.kinds.includes(this.task)) || p.z > 1 || p.z < -1 || Math.abs(p.x) > .92 || Math.abs(p.y) > .9;
      if (l.node === this.forceLabel) l.node.hidden ||= !this.forceArrow.visible;
      l.node.style.left = `${(p.x + 1) * this.host.clientWidth / 2}px`; l.node.style.top = `${(1 - p.y) * this.host.clientHeight / 2}px`; }
  }
  private clear(g: T.Group) {
    for (const child of [...g.children]) { if (child === this.forceArrow) continue; child.traverse(o => { if (o instanceof T.Mesh || o instanceof T.LineSegments) { o.geometry.dispose(); const ms = Array.isArray(o.material) ? o.material : [o.material]; ms.forEach(m => m.dispose()); } }); g.remove(child); }
  }
  private makeTool() {
    box(this.tool, [166, 15, 54], [0, 112, 0], C.dark);
    cylinder(this.tool, 27, 14, [0, 145, 0], C.metal); box(this.tool, [42, 22, 40], [0, 130, 0], C.dark);
    this.tool.add(this.parallelDrive, this.angularDrive);
    cylinder(this.parallelDrive, 5, 156, [0, 102, 0], C.gold, 'X');
    for (const z of [-20, 20]) cylinder(this.parallelDrive, 4, 162, [0, 99, z], C.metal, 'X');
    // Segmented rings indicate a screw envelope, not a fabricated thread profile.
    for (let x = -73; x <= 73; x += 5) cylinder(this.parallelDrive, 5.8, 1.3, [x, 102, 0], C.gold, 'X');
    box(this.parallelDrive, [30, 30, 38], [96, 102, 0], C.purple);
    this.gears = [-40, 40].map(x => gear(this.angularDrive, x)); box(this.angularDrive, [45, 45, 38], [-40, 95, -48], C.purple);
    for (const side of [-1, 1]) {
      const finger = new T.Group(); this.tool.add(finger); this.fingers.push(finger);
      box(finger, [12, 150, 32], [side * 10, 30, 0], C.metal);
      box(finger, [4, 60, 28], [side * 2, 10, 0], C.pad);
      box(finger, [24, 8, 32], [side * 4, -36, 0], C.gold);
      box(finger, [18, 6, 32], [side * 7, -17, 0], C.gold);
      for (const y of [65, -2]) cylinder(finger, 3, 14, [side * 10, y, 0], C.dark, 'X');
      box(finger, [22, 19, 48], [side * 10, 100, 0], C.dark);
    }
  }
  setTask(task: Task) {
    this.task = task; this.clear(this.object); this.clear(this.fixtures);
    if (task === 'head') {
      box(this.object, [160, 10, 130], [0, -140, 0], C.dark);
      box(this.object, [160, 8, 85], [0, -68, -12], C.metal);
      for (const s of [-1, 1]) {
        box(this.object, [8, 68, 130], [s * 76, -105, 0], C.metal);
        cylinder(this.object, 36, 20, [s * 43, -109, 0], '#34444d'); cylinder(this.object, 21, 28, [s * 43, -85, 0], C.metal);
      }
      const muzzle = new T.Group(); muzzle.position.set(0, -111, 65); this.object.add(muzzle); ring(muzzle, 29, 22, 40, 0, C.dark);
      box(this.object, [42, 25, 42], [0, -64, 64], C.blue); cylinder(this.object, 10, 8, [0, -64, 88], C.dark, 'Z');
      box(this.object, [64, 32, 36], [0, -48, 0], C.gold); box(this.object, [86, 12, 42], [0, -26, 0], C.gold);
      // Front/back flanges constrain sliding along the grasp feature, not only gravity.
      for (const z of [-22, 22]) box(this.object, [86, 22, 4], [0, -27, z], C.gold);
      box(this.fixtures, [195, 12, 180], [-130, -151, 0], '#b8c5ce');
      box(this.fixtures, [195, 12, 180], [130, -151, 0], C.blue);
      for (const x of [40, 220]) box(this.fixtures, [10, 24, 140], [x, -133, 0], C.blue);
      for (const x of [70, 190]) cylinder(this.fixtures, 5, 12, [x, -139, -45], C.gold);
    } else {
      ring(this.object, 32.5, 20, 90, -40, C.ore); ring(this.object, 47.5, 20, 40, -75, C.ore); ring(this.object, 40, 20, 25, 50, C.ore);
      for (let n = 0; n < 8; n++) { const a = n * Math.PI / 4; const rib = box(this.object, [4, 3, 75], [Math.cos(a) * 31, Math.sin(a) * 31, 5], '#b49b7d'); rib.rotation.z = a; }
      if (task === 'ore') { box(this.fixtures, [130, 130, 12], [0, 0, -100], C.blue); cylinder(this.fixtures, 19, 77, [0, 0, -55.5], C.metal, 'Z'); }
      else {
        box(this.fixtures, [155, 9, 200], [0, -62, 0], C.blue);
        // Supports only at the end flanges; central finger corridor stays clear.
        for (const z of [-60, 62]) {
          const radius = z < 0 ? 47.5 : 40;
          box(this.fixtures, [62, 10, 18], [0, -radius - 5, z], C.blue);
          for (const x of [-53, 53]) box(this.fixtures, [10, 42, 18], [x, -37, z], C.blue);
          box(this.fixtures, [22, 62 - radius, 18], [0, -(radius + 62) / 2, z], C.blue);
        }
      }
    }
    this.update(this.progress); this.view('iso');
  }
  update(progress: number) {
    this.progress = progress; const pose = poseAt(this.task, progress); this.tool.position.set(...pose.tool); this.object.position.set(...pose.object);
    this.parallelDrive.visible = this.candidate === 'parallel'; this.angularDrive.visible = this.candidate === 'angular';
    this.fingers.forEach((f, i) => {
      const sign = i === 0 ? -1 : 1;
      if (this.candidate === 'parallel') { f.position.set(sign * pose.gap / 2, 0, 0); f.rotation.z = 0; }
      else {
        const theta = sign * Math.asin((pose.gap - 80) / 190);
        // Rotate whole finger about (±40, 95), keeping the head-capture datum unchanged.
        f.rotation.z = theta; f.position.set(sign * 40 + 95 * Math.sin(theta), 95 - 95 * Math.cos(theta), 0); this.gears[i].rotation.z = theta;
      }
    });
    this.forceArrow.visible = this.forces && pose.captured;
    this.forceArrow.position.set(this.task === 'head' ? -110 : 65, this.task === 'head' ? -55 : 0, this.task === 'ore' ? 80 : 30);
    if (this.forceLabel) this.forceLabel.textContent = this.task === 'ore' ? '轴向拔出阻力' : '重力 / 惯性载荷';
    this.forceArrow.setDirection(new T.Vector3(0, this.task === 'ore' ? 0 : -1, this.task === 'ore' ? -1 : 0));
    this.forceArrow.setLength(this.task === 'head' ? 70 : 55, 12, 7);
  }
  view(view: 'iso' | 'front' | 'side' | 'detail') {
    this.closeup = view === 'detail';
    const p = poseAt(this.task, this.progress);
    const target = view === 'detail' ? new T.Vector3(...p.tool).add(new T.Vector3(0, 150, 0)) : new T.Vector3(0, 205, this.task === 'ore' ? 25 : 0);
    const offset = view === 'detail' ? [125, 50, 245] : view === 'front' ? [0, 20, 850] : view === 'side' ? [850, 20, 0] : [490, 310, 650];
    this.controls.target.copy(target); this.camera.position.copy(target).add(new T.Vector3(...offset as [number, number, number])); this.controls.update();
  }
  private resize() { const w = this.host.clientWidth, h = this.host.clientHeight; this.camera.aspect = w / h; this.camera.zoom = Math.min(1, this.camera.aspect); this.camera.updateProjectionMatrix(); this.renderer.setSize(w, h); }
  dispose() { cancelAnimationFrame(this.frame); this.observer.disconnect(); this.controls.dispose(); this.renderer.dispose(); }
}
