import * as T from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { layout } from './layout';
import { packing, type Mode, type Layer, type View, type Simulation } from './state';

const C = { frame: '#5c91b1', dark: '#425969', gold: '#df9b44', purple: '#987ab1', steel: '#8ea3af', board: '#398c85' };
const mat = (color: string, opacity = 1) => new T.MeshStandardMaterial({ color, roughness: .55, metalness: .22, transparent: opacity < 1, opacity, depthWrite: opacity === 1 });
function box(g: T.Object3D, size: number[], pos: number[], color: string, opacity = 1) {
  const m = new T.Mesh(new T.BoxGeometry(...size as [number, number, number]), mat(color, opacity));
  m.position.set(...pos as [number, number, number]); g.add(m); return m;
}
function cylinder(g: T.Object3D, r: number, len: number, pos: number[], color: string, axis: 'X' | 'Y' | 'Z' = 'Z', opacity = 1) {
  const m = new T.Mesh(new T.CylinderGeometry(r, r, len, 48), mat(color, opacity));
  if (axis === 'Z') m.rotation.x = Math.PI / 2;
  if (axis === 'X') m.rotation.z = Math.PI / 2;
  m.position.set(...pos as [number, number, number]); g.add(m); return m;
}
function tube(g: T.Object3D, outer: number, inner: number, len: number, pos: number[], color: string, opacity = 1) {
  const s = new T.Shape(); s.absarc(0, 0, outer, 0, Math.PI * 2, false);
  const h = new T.Path(); h.absarc(0, 0, inner, 0, Math.PI * 2, true); s.holes.push(h);
  const geom = new T.ExtrudeGeometry(s, { depth: len, bevelEnabled: false, curveSegments: 40 });
  geom.rotateY(Math.PI / 2); geom.translate(-len / 2, 0, 0);
  const m = new T.Mesh(geom, mat(color, opacity)); m.position.set(...pos as [number, number, number]); g.add(m); return m;
}
function wire(g: T.Object3D, points: number[][], radius: number, color: string) {
  const curve = new T.CatmullRomCurve3(points.map(p => new T.Vector3(...p as [number, number, number])));
  const m = new T.Mesh(new T.TubeGeometry(curve, 32, radius, 6, false), mat(color)); g.add(m); return m;
}
function edges(mesh: T.Mesh, opacity = .23) {
  const e = new T.LineSegments(new T.EdgesGeometry(mesh.geometry, 40), new T.LineBasicMaterial({ color: '#1b3f55', transparent: true, opacity }));
  mesh.add(e);
}
function plateShape(radius: number, holes: { x: number; y: number; r: number }[], depth: number) {
  const s = new T.Shape(); s.absarc(0, 0, radius, 0, Math.PI * 2, false);
  for (const p of holes) { const h = new T.Path(); h.absarc(p.x, p.y, p.r, 0, Math.PI * 2, true); s.holes.push(h); }
  const geom = new T.ExtrudeGeometry(s, { depth, curveSegments: 48, bevelEnabled: false }); geom.rotateY(Math.PI / 2); return geom;
}
export class WorkbenchScene {
  scene = new T.Scene();
  camera: T.PerspectiveCamera;
  renderer: T.WebGLRenderer;
  controls: OrbitControls;
  root = new T.Group();
  rotating = new T.Group();
  head = new T.Group();
  layers = new Map<Layer, T.Group>();
  registry: { object: T.Object3D; layer: Layer }[] = [];
  wheels: T.Group[] = [];
  rotor = new T.Group();
  magazine = new T.Group();
  loadingHatch = new T.Group();
  loadingBall = new T.Mesh();
  loadingGuide = new T.Group();
  retentionPlates: T.Mesh[] = [];
  retentionXray = false;
  drive = new T.Group();
  dock = new T.Group();
  vision = new T.Group();
  launcher = new T.Group();
  support = new T.Group();
  fixed = new T.Group();
  ballMeshes: T.Mesh[] = [];
  movingBall: T.Mesh;
  rod: T.Mesh;
  pusherTip: T.Mesh;
  sleeve = new T.Group();
  gate = new T.Group();
  hooks: T.Group[] = [];
  grip = new T.Group();
  annotations = new T.Group();
  flowGuides = new T.Group();
  selectionBox: T.Box3Helper;
  selected: Layer | null = null;
  mode: Mode = 'assembly';
  xray = false;
  lid = true;
  showDimensions = false;
  ready = false;
  private cap = 0;
  private originals = new Map<T.MeshStandardMaterial, { opacity: number; transparent: boolean; depthWrite: boolean }>();
  private bounds = new T.Box3();
  private width = 1;
  private height = 1;
  private picking = new T.Raycaster();
  private pointerDown = [0, 0];
  private active = true;
  private lastTick = 0;
  private visionParts: T.Object3D[] = [];
  private resizeObserver: ResizeObserver;
  private simulation: Simulation;
  onSelect: (layer: Layer) => void = () => {};
  onTick: () => void = () => {};
  constructor(private host: HTMLElement, simulation: Simulation) {
    this.simulation = simulation;
    this.scene.background = new T.Color('#edf3f6');
    this.camera = new T.PerspectiveCamera(34, 1, 1, 8000); this.camera.up.set(0, 0, 1);
    this.renderer = new T.WebGLRenderer({ antialias: true, alpha: false });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 1.75));
    this.renderer.outputColorSpace = T.SRGBColorSpace;
    this.renderer.toneMapping = T.ACESFilmicToneMapping; this.renderer.toneMappingExposure = 1.15;
    this.renderer.localClippingEnabled = true;
    this.renderer.domElement.setAttribute('aria-label', '可旋转的重装头部与车侧供弹三维装配');
    this.renderer.domElement.tabIndex = 0;
    this.host.append(this.renderer.domElement);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true; this.controls.dampingFactor = .09;
    this.controls.minDistance = 70; this.controls.maxDistance = 1800; this.controls.maxPolarAngle = Math.PI * .93;
    this.scene.add(new T.HemisphereLight(0xffffff, 0x7e929c, 2.5));
    const key = new T.DirectionalLight(0xfffaf0, 3.3); key.position.set(120, -220, 420); this.scene.add(key);
    const fill = new T.DirectionalLight(0xd3eafa, 2); fill.position.set(-200, 180, 130); this.scene.add(fill);
    this.root.add(this.rotating, this.fixed); this.scene.add(this.root);
    this.rotating.position.set(...layout.pitchPivot);
    const local = new T.Group(); local.position.set(-layout.pitchPivot[0], 0, -layout.pitchPivot[2]);
    this.rotating.add(local); local.add(this.head, this.magazine, this.drive, this.dock, this.support);
    this.head.add(this.vision, this.launcher);
    this.layers.set('launcher', this.launcher); this.layers.set('vision', this.vision);
    this.layers.set('magazine', this.magazine); this.layers.set('drive', this.drive);
    this.layers.set('dock', this.dock); this.layers.set('support', this.support);
    this.tag(this.launcher, 'launcher'); this.tag(this.vision, 'vision'); this.tag(this.magazine, 'magazine');
    this.tag(this.drive, 'drive'); this.tag(this.dock, 'dock'); this.tag(this.support, 'support'); this.tag(this.fixed, 'support');
    this.buildHead(); this.buildDock(); this.buildSupport();
    box(this.drive, [156, 32, 29], [-242, 0, -5], C.purple);
    for (const y of [-12, 12]) cylinder(this.drive, 3, 154, [-242, y, 14], C.steel, 'X');
    box(this.drive, [28, 24, 30], [-308, 0, -4], C.dark);
    this.rod = cylinder(this.drive, 4, 8, [-160, 0, 0], C.steel, 'X');
    this.pusherTip = cylinder(this.drive, 8, 4, [-157, 0, 0], C.gold, 'X');
    const s = new T.SphereGeometry(21.25, 32, 20); this.movingBall = new T.Mesh(s, mat('#edb348'));
    this.drive.add(this.movingBall); this.movingBall.visible = false;
    tube(this.sleeve, 26, 23, 20, [-89, 0, 0], C.gold); this.dock.add(this.sleeve);
    box(this.gate, [3, 51, 52], [-90, 0, 0], C.purple, .78); this.drive.add(this.gate);
    box(this.drive, [26, 22, 28], [-94, 43, 20], C.purple); // stop-gate actuator placeholder
    const grid = new T.GridHelper(650, 26, 0xb4c7d2, 0xd9e3e9); grid.rotation.x = Math.PI / 2; grid.position.set(-70, 0, -157); this.scene.add(grid);
    const axes = new T.AxesHelper(42); axes.position.set(183, -126, -154); this.scene.add(axes);
    local.add(this.annotations, this.flowGuides);
    this.flowGuides.add(new T.ArrowHelper(new T.Vector3(1, 0, 0), new T.Vector3(-149, 0, 0), 341, '#bd812b', 10, 5));
    this.selectionBox = new T.Box3Helper(new T.Box3(), new T.Color('#d29032')); this.selectionBox.visible = false; this.scene.add(this.selectionBox);
    this.resizeObserver = new ResizeObserver(() => this.resize()); this.resizeObserver.observe(this.host);
    this.resize(); this.setView('iso');
    this.renderer.domElement.addEventListener('pointerdown', e => { this.pointerDown = [e.clientX, e.clientY]; });
    this.renderer.domElement.addEventListener('pointerup', e => this.pick(e));
    this.renderer.domElement.addEventListener('webglcontextlost', e => {
      e.preventDefault(); this.active = false; this.host.dispatchEvent(new CustomEvent('scene-error', { detail: '图形上下文已丢失，请刷新页面恢复三维视图。' }));
    });
    document.addEventListener('visibilitychange', () => { this.lastTick = 0; });
    requestAnimationFrame(t => this.animate(t));
  }
  private tag(object: T.Object3D, layer: Layer) { object.userData.layer = layer; this.registry.push({ object, layer }); }
  private buildHead() {
    // Entire head-side bottom frame follows the detachable head.
    for (const y of [-76, 76]) { const b = box(this.launcher, [143, 12, 7], [12, y, -77], C.dark); edges(b); }
    box(this.launcher, [8, 152, 7], [-55, 0, -77], C.dark);
    box(this.launcher, [8, 152, 7], [79, 0, -77], C.dark);
    for (const [x, y] of [[-50, -70], [-50, 70], [80, 0]]) box(this.launcher, [18, 18, 6], [x, y, -81], C.steel);
    // New motor mounting bridges, not the old 3510 mount.
    for (const y of [-49, 49]) {
      box(this.launcher, [54, 50, 4], [0, y, 38], C.steel);
      for (const x of [-24, 24]) box(this.launcher, [4, 8, 111], [x, y > 0 ? 76 : -76, -19], C.steel);
    }
    tube(this.launcher, 26, 23, 42, [-46, 0, 0], '#678b9c', .65);
    // SM11 support and electronics, above/below the line of fire.
    for (const y of [-44, 44]) {
      box(this.launcher, [75, 5, 4], [95, y, -24], C.steel);
      box(this.launcher, [5, 5, 51], [60, y, -50], C.dark);
    }
    for (const y of [-86, 86]) {
      const ear = new T.Group(); this.launcher.add(ear);
      box(ear, [42, 9, 5], [5, y, 8], C.gold);
      box(ear, [6, 9, 23], [-13, y, 20], C.gold);
      box(ear, [6, 9, 23], [23, y, 20], C.gold);
      box(ear, [42, 9, 5], [5, y, 32], C.gold);
    }
    for (const y of [-57, 57]) {
      box(this.vision, [117, 4, 4], [36, y, 60], C.steel);
      for (const x of [-12, 87]) box(this.vision, [4, 4, 19], [x, y, 51], C.steel);
    }
    // Reserved head-side protection/control board, not an extra dev board.
    box(this.launcher, [58, 42, 11], [9, 0, -61], C.board, .6);
    for (const y of [-57, 57]) wire(this.launcher, [[46, y, -40], [25, y, -38], [18, y, 12], [4, y > 0 ? 49 : -49, 28]], 1.6, '#323d47');
    box(this.launcher, [62, 23, 5], [-6, -62, -78.5], C.dark);
    for (const y of [-66, -58]) for (let j = 0; j < 6; j++) box(this.launcher, [j < 2 ? 7 : 4, 4, 1], [-29 + j * 9, y, -81.5], '#cba352');
    for (const y of [-84, 84]) cylinder(this.launcher, 3, 14, [35, y, -75.5], C.steel, 'X');
    // Optional visual tool only, never treated as real arm geometry.
    for (const y of [-97, 97]) {
      box(this.grip, [54, 7, 38], [5, y, 34], C.purple, .55);
      box(this.grip, [24, 15, 6], [5, y > 0 ? 90 : -90, 26.5], C.purple);
      box(this.grip, [77, 7, 10], [-27.5, y, 55], C.purple, .55);
    }
    box(this.grip, [32, 200, 16], [-60, 0, 62], C.purple, .55);
    cylinder(this.grip, 25, 8, [-60, 0, 74], C.purple);
    this.head.add(this.grip);
  }
  private buildDock() {
    for (const y of [-76, 76]) box(this.dock, [167, 17, 9], [7, y, -94], C.frame);
    for (const x of [-70, 80]) box(this.dock, [12, 169, 9], [x, 0, -94], C.frame);
    for (const [x, y] of [[-50, -70], [-50, 70], [80, 0]]) box(this.dock, [21, 21, 7], [x, y, -87.5], C.steel);
    box(this.dock, [7, 14, 8], [-48, -64, -80], C.gold);
    cylinder(this.dock, 4, 8, [-48, 64, -80], C.gold);
    for (const y of [-92, 92]) {
      const hook = new T.Group(); hook.position.set(35, y, -95); this.dock.add(hook); this.hooks.push(hook);
      box(hook, [9, 6, 23], [0, 0, 10], C.gold);
      box(hook, [9, 20, 5], [0, y > 0 ? -7 : 7, 25], C.gold);
      cylinder(this.dock, 5, 14, [35, y, -95], C.dark, 'Y');
    }
    box(this.dock, [38, 24, 20], [35, 0, -106], C.purple);
    cylinder(this.dock, 3, 184, [35, 0, -97], C.steel, 'Y');
    box(this.dock, [62, 23, 8], [-6, -62, -92], C.dark);
    for (const y of [-66, -58]) for (let j = 0; j < 6; j++) cylinder(this.dock, j < 2 ? 2 : 1.2, 8, [-29 + j * 9, y, -86], '#cba352');
  }
  private buildSupport() {
    for (const y of [-91, 91]) {
      box(this.support, [270, 10, 12], [-58, y, -111], C.frame);
      box(this.fixed, [58, 16, 67], [-30, y, -118], '#6c8c9f');
      cylinder(this.fixed, 23, 19, [-30, y, -112], C.dark, 'Y');
    }
    cylinder(this.support, 12, 202, [-30, 0, -112], C.steel, 'Y');
    box(this.fixed, [128, 222, 9], [-30, 0, -152], '#b5c8d2');
    box(this.fixed, [45, 32, 45], [-30, 123, -112], C.purple);
  }
  async load(onProgress: (percent: number) => void) {
    const loader = new GLTFLoader(); let done = 0;
    const load = async (name: string) => {
      const gltf = await loader.loadAsync(`${import.meta.env.BASE_URL}models/${name}.glb`);
      const obj = new T.Group(); gltf.scene.rotation.x = Math.PI / 2; obj.add(gltf.scene);
      onProgress(++done / 6); return obj;
    };
    const [left, right, motor, sm11, c620, vision] = await Promise.all(['wheel-left', 'wheel-right', 'm3508-body', 'sm11', 'c620', 'vision-v2'].map(load));
    left.position.y = -49; right.position.y = 49; this.launcher.add(left, right); this.wheels = [left, right];
    for (const y of [-49, 49]) { const m = motor.clone(true); m.position.set(0, y, 22.1); this.launcher.add(m); }
    this.launcher.add(sm11);
    for (const y of [-57, 57]) { const c = c620.clone(true); c.position.set(50, y, -42); this.head.add(c); this.tag(c, 'drive'); }
    vision.position.set(...layout.camera); this.vision.add(vision);
    vision.traverse(o => { if (['CASE_lid', 'NEW_RemovableGuard', 'REF_CameraPCB', 'REF_LensEnvelope', 'NEW_CameraCableJaw', 'REF_FPCRoute_Assumed'].includes(o.name)) this.visionParts.push(o); });
    this.scene.traverse(o => {
      if (!(o instanceof T.Mesh)) return;
      const materials = Array.isArray(o.material) ? o.material : [o.material];
      for (const m of materials) if (m instanceof T.MeshStandardMaterial) {
        if (o.name === 'CASE_lid') { m.opacity = .65; m.transparent = true; m.depthWrite = false; }
        this.originals.set(m, { opacity: m.opacity, transparent: m.transparent, depthWrite: m.depthWrite });
      }
    });
    this.ready = true; this.update();
  }
  private rebuildMagazine(capacity: number) {
    // Dispose only the dynamic subassembly, not CAD assets shared elsewhere.
    for (const child of [...this.magazine.children]) {
      child.traverse(o => { if (o instanceof T.Line) { o.geometry.dispose(); (o.material as T.Material).dispose(); } if (o instanceof T.Mesh) { o.geometry.dispose(); const ms = Array.isArray(o.material) ? o.material : [o.material]; ms.forEach(m => { this.originals.delete(m); if (m instanceof T.MeshBasicMaterial) m.map?.dispose(); m.dispose(); }); } });
      this.magazine.remove(child);
    }
    this.retentionPlates = [];
    const { radius, diameter } = packing(capacity); const outer = diameter / 2;
    this.rotor = new T.Group(); this.rotor.position.set(-145, 0, radius); this.magazine.add(this.rotor);
    const holes = Array.from({ length: capacity }, (_, i) => ({ x: radius * Math.cos(i * 2 * Math.PI / capacity), y: radius * Math.sin(i * 2 * Math.PI / capacity), r: 23 }));
    const body = new T.Mesh(plateShape(outer, holes, 50), mat('#c9b98e')); this.rotor.add(body); edges(body, .3);
    cylinder(this.rotor, 16, 56, [25, 0, 0], C.dark, 'X');
    this.ballMeshes = [];
    for (let i = 0; i < capacity; i++) {
      const b = new T.Mesh(new T.SphereGeometry(21.25, 24, 16), mat('#eab448'));
      b.position.set(25, holes[i].y, -holes[i].x); this.rotor.add(b); this.ballMeshes.push(b);
    }
    // Fixed covers: forward firing aperture, rear pushrod hole and upper service port.
    for (const [x, aperture] of [[-93, 23.5], [-149, 8.5]]) {
      const openings = [{ x: radius, y: 0, r: aperture }];
      if (x === -149) openings.push({ x: -radius, y: 0, r: layout.loadingPortDiameter / 2 });
      const cover = new T.Mesh(plateShape(outer + 3, openings, 3), mat(x === -149 ? '#487e9d' : '#365e7a'));
      cover.name = x === -149 ? 'fixed-rear-retainer' : 'fixed-front-retainer';
      cover.position.set(x, 0, radius); this.magazine.add(cover); edges(cover, .65);
      this.retentionPlates.push(cover);
      this.surfaceLabel(cover, x === -149 ? '固定后挡板' : '固定前挡板', [x === -149 ? -.2 : 3.2, 0, 38], x === -149, 120);
    }
    // Manual top-rear port: hinge opens away from the axial hand/ball approach.
    tube(this.magazine, 26, layout.loadingPortDiameter / 2, 5, [-151, 0, 2 * radius], C.gold);
    this.loadingHatch = new T.Group(); this.loadingHatch.name = 'loading-hatch';
    this.loadingHatch.position.set(-156, 0, 2 * radius + layout.loadingHingeZOffset);
    this.magazine.add(this.loadingHatch);
    box(this.loadingHatch, [3, 54, 54], [0, 0, -27], C.gold);
    this.surfaceLabel(this.loadingHatch, '装填盖', [-1.7, 0, -27], true, 40);
    box(this.loadingHatch, [8, 20, 5], [-5, 0, -48], C.gold); // captive latch / handle intent
    cylinder(this.magazine, 3, 60, [-156, 0, 2 * radius + 27], C.steel, 'Y');
    this.loadingBall = new T.Mesh(new T.SphereGeometry(21.25, 32, 20), mat('#eab448'));
    this.magazine.add(this.loadingBall);
    this.loadingGuide = new T.Group(); this.magazine.add(this.loadingGuide);
    this.loadingGuide.add(new T.ArrowHelper(new T.Vector3(1, 0, 0), new T.Vector3(-260, 0, 2 * radius), 95, C.gold, 10, 5));
    // Rear axle support: keep frame behind the fixed back plate, not in the moving pockets.
    box(this.magazine, [10, 190, 12], [-159, 0, radius], C.frame);
    cylinder(this.magazine, 6, 16, [-151, 0, radius], C.steel, 'X');
    for (const y of [-91, 91]) box(this.magazine, [10, 8, radius + 104], [-159, y, (radius - 104) / 2], C.frame);
    box(this.magazine, [34, 34, 32], [-168, 0, radius], C.purple); // index drive
    this.magazine.traverse(o => {
      if (o instanceof T.Mesh && o.material instanceof T.MeshStandardMaterial) {
        const m = o.material; this.originals.set(m, { opacity: m.opacity, transparent: m.transparent, depthWrite: m.depthWrite });
      }
    });
    this.cap = capacity; this.buildDimensions();
  }
  // Surface names are viewer annotations, not fabrication markings.
  private surfaceLabel(parent: T.Object3D, text: string, pos: number[], rear: boolean, width: number) {
    const canvas = document.createElement('canvas'); canvas.width = 512; canvas.height = 128;
    const ctx = canvas.getContext('2d')!;
    ctx.font = '600 96px sans-serif'; ctx.fillStyle = '#ffffff'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText(text, 256, 64);
    const texture = new T.CanvasTexture(canvas); texture.colorSpace = T.SRGBColorSpace;
    const mesh = new T.Mesh(new T.PlaneGeometry(width, width * 128 / 512), new T.MeshBasicMaterial({ map: texture, transparent: true, depthWrite: false }));
    mesh.rotation.set(Math.PI / 2, 0, rear ? -Math.PI / 2 : Math.PI / 2, 'ZXY');
    mesh.position.set(...pos as [number, number, number]); parent.add(mesh);
  }
  private label(text: string) {
    const c = document.createElement('canvas'); c.width = 512; c.height = 80;
    const ctx = c.getContext('2d')!; ctx.font = '500 48px sans-serif'; ctx.fillStyle = '#38596c'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText(text, 256, 40);
    const texture = new T.CanvasTexture(c); texture.colorSpace = T.SRGBColorSpace;
    const sprite = new T.Sprite(new T.SpriteMaterial({ map: texture, depthTest: false, transparent: true })); sprite.scale.set(156, 29, 1); return sprite;
  }
  private buildDimensions() {
    this.annotations.traverse(o => { if (o instanceof T.Line) { o.geometry.dispose(); (o.material as T.Material).dispose(); } if (o instanceof T.Sprite) { o.material.map?.dispose(); o.material.dispose(); } });
    this.annotations.clear(); const { diameter, radius } = packing(this.cap);
    const pts = [[-154, -diameter / 2, radius], [-154, diameter / 2, radius]].map(p => new T.Vector3(...p as [number, number, number]));
    const line = new T.Line(new T.BufferGeometry().setFromPoints(pts), new T.LineBasicMaterial({ color: '#53798e', depthTest: false })); this.annotations.add(line);
    const label = this.label(`弹盘 Ø${diameter.toFixed(1)} mm`); label.position.set(-158, 0, radius + 34); this.annotations.add(label);
    const axis = this.label('X 炮口方向'); axis.position.set(202, 0, -20); this.annotations.add(axis);
  }
  setMode(mode: Mode) { this.mode = mode; this.setView(mode === 'loading' ? 'rear' : mode === 'feed' ? 'side' : 'iso'); this.updateMaterials(); }
  setView(view: View) {
    const focus = this.mode === 'loading' ? new T.Vector3(-120, 0, packing(this.simulation.capacity).radius + 20) : this.mode === 'vision' ? new T.Vector3(49, 0, 87) : this.mode === 'dock' ? new T.Vector3(0, 0, 25) : new T.Vector3(-72, 0, 28);
    let d = this.mode === 'loading' ? 660 : this.mode === 'vision' ? 350 : this.mode === 'dock' ? 820 : 880;
    if (this.width / this.height < 1.2) d *= 1.2;
    const offsets = { rear: new T.Vector3(-1.6, -.65, .65), iso: new T.Vector3(.94, -1.35, .85), side: new T.Vector3(0, -1.7, .12), front: new T.Vector3(1.75, 0, .12), top: new T.Vector3(0, -.001, 1.75) };
    this.camera.position.copy(focus).add(offsets[view].clone().multiplyScalar(d / 1.7)); this.controls.target.copy(focus); this.controls.update();
  }
  setLayer(layer: Layer, visible: boolean) {
    for (const r of this.registry) if (r.layer === layer) r.object.visible = visible;
    if (this.selected === layer && !visible) this.selectionBox.visible = false;
  }
  select(layer: Layer | null) {
    this.selected = layer; this.selectionBox.visible = layer !== null;
    // Material selection uses emissive only; normal and x-ray opacities stay stable.
    this.scene.traverse(o => { if (o instanceof T.Mesh) { const m = o.material; if (m instanceof T.MeshStandardMaterial) m.emissive.set('#000000'); } });
    for (const r of this.registry) if (r.layer === layer) r.object.traverse(o => { if (o instanceof T.Mesh && o.material instanceof T.MeshStandardMaterial) o.material.emissive.set('#122d3c'); });
  }
  setXray(value: boolean) { this.xray = value; this.updateMaterials(); }
  setRetentionXray(value: boolean) { this.retentionXray = value; this.updateMaterials(); }
  setLid(value: boolean) { this.lid = value; }
  private updateMaterials() {
    this.scene.traverse(o => {
      if (!(o instanceof T.Mesh)) return;
      const m = o.material; if (!(m instanceof T.MeshStandardMaterial)) return;
      const original = this.originals.get(m); if (!original) return;
      let p = original.opacity;
      // Structural cutaway, not geometric sectioning: keep feed balls and path opaque.
      if (this.retentionXray && this.retentionPlates.includes(o)) p = .18;
      if (this.xray && o !== this.loadingBall && o !== this.movingBall && !this.ballMeshes.includes(o)) p = Math.min(p, .22);
      if (m.transparent !== (p < 1)) m.needsUpdate = true;
      m.opacity = p; m.transparent = p < 1; m.depthWrite = p >= 1;
    });
  }
  private pick(e: PointerEvent) {
    if (Math.hypot(e.clientX - this.pointerDown[0], e.clientY - this.pointerDown[1]) > 5) return;
    const r = this.renderer.domElement.getBoundingClientRect();
    this.picking.setFromCamera(new T.Vector2((e.clientX - r.left) / r.width * 2 - 1, -(e.clientY - r.top) / r.height * 2 + 1), this.camera);
    const hits = this.picking.intersectObjects(this.root.children, true);
    for (const hit of hits) {
      let o: T.Object3D | null = hit.object; let visible = true;
      for (let q: T.Object3D | null = o; q; q = q.parent) if (!q.visible) visible = false;
      if (!visible) continue;
      while (o && !o.userData.layer) o = o.parent;
      if (o) { this.onSelect(o.userData.layer); return; }
    }
  }
  update() {
    const s = this.simulation;
    if (s.capacity !== this.cap) { this.rebuildMagazine(s.capacity); this.updateMaterials(); }
    this.rotating.rotation.y = -s.pitch * Math.PI / 180;
    this.head.position.z = s.phase === 0 ? 105 : 0;
    this.head.position.z += this.mode === 'vision' ? 0 : s.explode * 45;
    this.vision.position.z = this.mode === 'vision' ? 0 : s.explode * 55;
    this.vision.position.x = this.mode === 'vision' ? 0 : s.explode * 22;
    for (const o of this.visionParts) {
      // CAD meshes are local Y-up at this level; +Y is design +Z.
      const e = this.mode === 'vision' ? s.explode : 0;
      o.position.set(0, 0, 0);
      if (o.name === 'CASE_lid') o.position.y = 55 * e;
      if (o.name === 'NEW_RemovableGuard') o.position.x = 50 * e;
      if (o.name === 'REF_CameraPCB' || o.name === 'REF_LensEnvelope') o.position.x = 24 * e;
      if (o.name === 'NEW_CameraCableJaw') o.position.x = 12 * e;
      if (o.name === 'REF_FPCRoute_Assumed') o.visible = s.explode === 0;
    }
    this.magazine.position.x = -s.explode * 55;
    this.drive.position.x = -s.explode * 95;
    this.dock.position.z = -s.explode * 35;
    this.grip.visible = this.mode === 'dock' && s.phase < 3;
    this.grip.position.z = 0;
    for (let i = 0; i < this.hooks.length; i++) this.hooks[i].rotation.x = s.phase >= 2 ? 0 : (i === 0 ? 1 : -1) * .85;
    this.sleeve.position.x = s.phase >= 3 ? layout.sleeveTravel : 0;
    const pose = s.pose;
    this.rotor.rotation.x = -s.indexTurns * Math.PI * 2 / s.capacity;
    for (let i = 0; i < this.ballMeshes.length; i++) this.ballMeshes[i].visible = s.slots[i] && !(s.running && !s.seeking && i === s.activeSlot) && !(s.handling === 'remove' && i === s.loadingSlot);
    this.loadingHatch.rotation.y = s.hatchOpen ? layout.loadingHatchAngle * Math.PI / 180 : 0;
    this.loadingBall.visible = s.handling === 'insert' || s.handling === 'remove';
    const progress = s.handling === 'remove' ? 1 - s.handlingProgress : s.handlingProgress;
    this.loadingBall.position.set(layout.loadingApproachX + (layout.magazineX - layout.loadingApproachX) * progress, 0, 2 * packing(s.capacity).radius);
    this.loadingGuide.visible = this.mode === 'loading' && s.hatchOpen && !s.handling;
    this.movingBall.visible = s.feedBallVisible;
    const tip = layout.pusherRest + (layout.pusherEnd - layout.pusherRest) * pose.push;
    const ballX = Math.max(layout.magazineX, tip + 21.25);
    this.movingBall.position.set(pose.segment === 2 ? layout.handoff + (190 - layout.handoff) * pose.exit : ballX, 0, 0);
    this.pusherTip.position.x = tip - 2;
    this.rod.scale.y = (8 + tip - layout.pusherRest) / 8;
    this.rod.position.x = (tip - 165) / 2;
    this.gate.position.z = s.running ? pose.gate * 54 : 0;
    this.annotations.visible = this.showDimensions && ['assembly', 'feed'].includes(this.mode) && this.magazine.visible;
    this.flowGuides.visible = this.mode === 'feed';
    for (const r of this.registry) r.object.traverse(o => { if (o.name === 'CASE_lid') o.visible = this.lid; });
    this.scene.updateMatrixWorld(true);
    if (this.selected) {
      this.bounds.makeEmpty();
      for (const r of this.registry) if (r.layer === this.selected && r.object.visible) this.bounds.union(new T.Box3().setFromObject(r.object));
      this.selectionBox.box.copy(this.bounds); this.selectionBox.visible = !this.bounds.isEmpty();
    }
  }
  getHeadBounds() {
    const old = this.rotating.rotation.y; const hz = this.head.position.z;
    const vx = this.vision.position.x, vz = this.vision.position.z;
    this.rotating.rotation.y = 0; this.head.position.z = 0; this.vision.position.set(0, 0, 0); this.grip.visible = false;
    this.root.updateMatrixWorld(true);
    const b = new T.Box3().setFromObject(this.launcher).union(new T.Box3().setFromObject(this.vision));
    for (const r of this.registry) if (r.layer === 'drive' && r.object.parent === this.head) b.union(new T.Box3().setFromObject(r.object));
    const v = new T.Vector3(); b.getSize(v);
    this.rotating.rotation.y = old; this.head.position.z = hz; this.vision.position.set(vx, 0, vz); this.update();
    return v.toArray();
  }
  screenshot() {
    this.renderer.render(this.scene, this.camera);
    return this.renderer.domElement.toDataURL('image/png');
  }
  private resize() {
    this.width = Math.max(1, this.host.clientWidth); this.height = Math.max(1, this.host.clientHeight);
    this.renderer.setSize(this.width, this.height); this.camera.aspect = this.width / this.height; this.camera.updateProjectionMatrix();
  }
  private animate(t: number) {
    if (!this.active) return;
    requestAnimationFrame(time => this.animate(time));
    const dt = this.lastTick ? Math.min(.08, (t - this.lastTick) / 1000) : 0; this.lastTick = t;
    this.simulation.tick(dt); this.update();
    if (this.simulation.phase === 4) this.wheels.forEach((w, i) => { w.rotation.z += dt * (i === 0 ? 1 : -1) * (this.simulation.playing ? 5 : 0); });
    this.controls.update(); this.renderer.render(this.scene, this.camera); this.onTick();
  }
}
