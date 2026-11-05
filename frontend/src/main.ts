import './style.css';
import { Simulation, packing, phases, cycleNames, type Mode, type View, type Layer } from './state';
import { catalog, modeText } from './catalog';
import { WorkbenchScene } from './scene';
const icons = {
  cube: '<path d="m12 3 9 5v8l-9 5-9-5V8Zm0 9 9-4M12 12 3 8m9 4v9"/>',
  feed: '<circle cx="8" cy="8" r="4"/><circle cx="17" cy="16" r="4"/><path d="M4 16h6m-3-3 3 3-3 3M14 8h6"/>',
  dock: '<path d="M5 3v7h14V3M3 17h18M7 17v4m10-4v4M12 3v10m-3-3 3 3 3-3"/>',
  camera: '<path d="M3 7h5l2-3h4l2 3h5v13H3Z"/><circle cx="12" cy="13" r="4"/>',
  reset: '<path d="M4 10a8 8 0 1 1 1 8M4 4v6h6"/>',
  share: '<path d="M9 9 16 5M9 15l7 4"/><circle cx="6" cy="12" r="4"/><circle cx="19" cy="4" r="3"/><circle cx="19" cy="20" r="3"/>',
  download: '<path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5"/>',
  play: '<path d="m8 4 12 8-12 8Z"/>',
};
const icon = (key: keyof typeof icons) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[key]}</svg>`;
const $ = <T extends HTMLElement = HTMLElement>(q: string) => document.querySelector<T>(q)!;
const sim = new Simulation();
let mode: Mode = 'assembly';
let selected: Layer = 'magazine';
const params = new URLSearchParams(location.search);
const initialMode = params.get('mode'); if (['assembly', 'feed', 'dock', 'vision'].includes(initialMode ?? '')) mode = initialMode as Mode;
if (params.get('capacity') === '10') sim.capacity = 10;
const p = Number(params.get('pitch') ?? '0'); sim.pitch = Number.isFinite(p) ? Math.max(-15, Math.min(45, p)) : 0;
if (catalog.some(c => c.id === params.get('part'))) selected = params.get('part') as Layer;
const names: { mode: Mode; label: string; icon: keyof typeof icons }[] = [
  { mode: 'assembly', label: '总装', icon: 'cube' }, { mode: 'feed', label: '供弹', icon: 'feed' }, { mode: 'dock', label: '对接', icon: 'dock' }, { mode: 'vision', label: '视觉组件', icon: 'camera' },
];
$('#app').innerHTML = `
<header class="app-header"><a class="brand" href="./" aria-label="Zenith结构工作台首页"><span class="brand-mark">Z</span><strong>Zenith</strong><span class="brand-divider"></span><span>重装结构工作台</span></a><div class="header-actions"><span class="version">2027 · 方案 v0.1</span><button id="share" class="text-button">${icon('share')}<span>分享视图</span></button><button id="capture" class="text-button">${icon('camera')}<span>保存图片</span></button></div></header>
<main>
<div class="workspace-heading"><div><h1 id="mode-title"></h1><p id="mode-subtitle"></p></div><nav class="mode-tabs" aria-label="工作区">${names.map(n => `<button data-mode="${n.mode}" aria-pressed="false">${icon(n.icon)}${n.label}</button>`).join('')}</nav></div>
<div class="workspace">
<section class="visual-workspace" aria-label="三维结构与动作演示">
  <div class="viewport-wrap">
    <div class="viewport-top"><div class="view-buttons" role="group" aria-label="观察方向"><button data-view="iso" aria-pressed="true">立体</button><button data-view="side" aria-pressed="false">侧视</button><button data-view="front" aria-pressed="false">炮口正视</button><button data-view="top" aria-pressed="false">俯视</button></div><button id="reset-view" class="icon-button" title="复位视角" aria-label="复位视角">${icon('reset')}</button></div>
    <div id="viewport"><div id="loading" role="status"><span class="loading-orbit"></span><strong id="load-label">载入CAD参考…</strong><div class="loading-track"><i id="load-bar"></i></div></div></div>
    <div id="scene-error" class="scene-error" role="alert" hidden></div>
    <div class="viewport-bottom"><p id="viewport-hint"></p><span class="axis-key"><i>X</i> 炮口　<i>Y</i> 左　<i>Z</i> 上</span></div>
    <div class="legend"><span><i style="background:#5c91b1"></i>车侧承载</span><span><i style="background:#df9b44"></i>弹路</span><span><i style="background:#987ab1"></i>执行器占位</span></div>
  </div>
  <div class="control-strip">
    <label class="select-control">弹盘容量 <select id="capacity"><option value="10">10发</option><option value="12">12发</option></select></label>
    <label class="range-control">俯仰 <input id="pitch" aria-label="共托架俯仰角" type="range" min="-15" max="45" step="1" value="0"/><output id="pitch-value">0°</output></label>
    <label class="range-control explode-control">分解 <input id="explode" aria-label="结构分解程度" type="range" min="0" max="100" value="0"/><output id="explode-value">0%</output></label>
    <div class="toggles"><label><input id="xray" type="checkbox"/>透视</label><label><input id="dimensions" type="checkbox"/>尺寸</label><label id="lid-label" hidden><input id="lid" type="checkbox" checked/>上盖</label></div>
  </div>
  <section id="motion-panel" class="motion-panel">
    <div class="motion-heading"><h2 id="motion-title">单球供弹</h2><span id="cycle-status" role="status">已落座，等待推送</span></div>
    <div id="feed-controls"><div class="feed-actions"><button id="single-shot" class="primary">${icon('play')}送一发</button><button id="auto-feed">连续演示</button><button id="pause-feed" hidden>暂停</button><button id="refill">重新装满</button><div class="ammo"><strong id="remaining">12</strong><span>/ <span id="ammo-total">12</span> 发剩余</span><span class="shot-count">已发 <b id="fired">0</b></span></div></div><ol id="cycle-steps" class="cycle-steps">${cycleNames.map((n, i) => `<li data-cycle="${i}"><span>${i + 1}</span>${n}</li>`).join('')}</ol></div>
    <div id="dock-controls" hidden><div class="dock-steps">${phases.map((n, i) => `<button data-phase="${i}" aria-pressed="false"><span>${i + 1}</span>${n.title}</button>`).join('')}</div><p id="phase-description"></p></div>
    <div id="vision-controls" hidden><p>共底架固定电脑与相机，护框独立拆卸。用上方“上盖”查看内部，或拖动“分解”观察零件关系。</p><a class="download-link" href="downloads/camera-lbc3-v2.step" download>${icon('download')}视觉组件 STEP</a></div>
    <p class="motion-note" id="motion-note">动作节奏为示意；推力、球体接触和连续可靠性等待实物台架验证。</p>
  </section>
</section>
<aside class="inspector" aria-label="结构与零件详情">
  <div class="panel-heading"><h2>结构</h2><button id="show-all" class="quiet-button">全部显示</button></div>
  <div class="part-tree">${catalog.map(c => `<div class="part-row" data-row="${c.id}"><input type="checkbox" checked data-layer="${c.id}" aria-label="显示${c.name}"/><button data-part="${c.id}" aria-pressed="false"><i style="background:${c.color}"></i><span><strong>${c.name}</strong><small>${c.short}</small></span><span class="row-arrow">›</span></button></div>`).join('')}</div>
  <article id="part-details" class="part-details"></article>
  <div class="scope-note"><h3>当前交付边界</h3><p>整头布置与动作示意。真实件保留来源，自制件与未选型驱动分别标注；质量、整车收纳与六轴臂轨迹待真实总装接入。</p><a href="downloads/design-parameters.json" download>下载布局参数</a></div>
</aside>
</div>
<footer class="data-strip"><div><span>弹盘外径</span><strong id="disk-diameter">243.3 <small>mm</small></strong></div><div><span>可拆头当前外形</span><strong id="head-size">加载中</strong></div><div><span>储弹归属</span><strong>车侧共俯仰托架</strong></div><div class="data-status"><span class="status-dot"></span>几何布局版<span class="data-status-note">质量待实称</span></div></footer>
</main><div id="toast" role="status" hidden></div><dialog id="share-dialog"><form method="dialog"><h2>分享当前视图</h2><p>复制这个地址，保留工作区、容量、俯仰和所选结构。</p><input id="share-url" readonly aria-label="当前视图地址"/><button class="primary">关闭</button></form></dialog>`;
let scene: WorkbenchScene;
let uiStamp = '';
let headSize: number[] = [];
let toastTimer: ReturnType<typeof setTimeout>;
function toast(message: string) { const el = $('#toast'); el.textContent = message; el.hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => el.hidden = true, 3200); }
function storeView() {
  const q = new URLSearchParams({ mode, capacity: String(sim.capacity), pitch: String(sim.pitch), part: selected });
  history.replaceState(null, '', `${location.pathname}?${q}`);
}
function selectPart(id: Layer) {
  selected = id; scene?.select(id);
  const c = catalog.find(x => x.id === id)!;
  document.querySelectorAll<HTMLButtonElement>('[data-part]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.part === id)));
  $('#part-details').innerHTML = `<div class="part-kind"><i style="background:${c.color}"></i>${c.kind}</div><h2>${c.name}</h2><p>${c.description}</p><ul>${c.notes.map(n => `<li>${n}</li>`).join('')}</ul><details><summary>模型与设计依据</summary><ul class="sources">${c.sources.map(s => `<li>${s}</li>`).join('')}</ul></details>${c.downloads ? `<div class="download-list">${c.downloads.map(d => `<a href="downloads/${d.path}" download>${icon('download')}${d.label}</a>`).join('')}</div>` : ''}`;
  storeView();
}
function setMode(next: Mode, initial = false) {
  mode = next;
  if (!initial) {
    sim.setExplode(0); $('#explode-value').textContent = '0%'; $<HTMLInputElement>('#explode').value = '0';
    if (next === 'dock') sim.setPhase(0); else if (sim.phase !== 4) sim.setPhase(4);
  }
  scene?.setMode(next);
  // Workspaces apply a readable layer preset; checkboxes always reflect the scene.
  document.querySelectorAll<HTMLInputElement>('[data-layer]').forEach(c => {
    const layer = c.dataset.layer as Layer;
    c.checked = next === 'vision' ? layer === 'vision' : next === 'feed' ? layer !== 'vision' : next === 'dock' ? !['magazine', 'drive'].includes(layer) : true;
    scene?.setLayer(layer, c.checked);
  });
  const t = modeText[next]; $('#mode-title').textContent = t.title; $('#mode-subtitle').textContent = t.subtitle; $('#viewport-hint').textContent = t.hint;
  document.querySelectorAll<HTMLButtonElement>('[data-mode]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.mode === next)));
  $('#feed-controls').hidden = next === 'dock' || next === 'vision';
  $('#dock-controls').hidden = next !== 'dock'; $('#vision-controls').hidden = next !== 'vision'; $('#lid-label').hidden = next !== 'vision';
  $<HTMLInputElement>('#dimensions').disabled = next === 'vision' || next === 'dock';
  $('#motion-title').textContent = next === 'dock' ? '装头与接通顺序' : next === 'vision' ? '独立维护' : '单球供弹';
  $('#motion-note').textContent = next === 'dock' ? '拆头前先清空接缝、关门、退套，再解锁。夹爪与触点为功能占位。' : next === 'vision' ? '分解时隐藏排线，观察零件关系；不表示实际拆装轨迹。' : '动作节奏为示意；推力、球体接触和连续可靠性等待实物台架验证。';
  $<HTMLInputElement>('#xray').checked = next === 'feed'; scene?.setXray(next === 'feed');
  const defaultPart: Record<Mode, Layer> = { assembly: 'magazine', feed: 'magazine', dock: 'dock', vision: 'vision' };
  selectPart(initial ? selected : defaultPart[next]); updateStatic(); updateUI(true);
  document.querySelectorAll<HTMLButtonElement>('[data-view]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.view === (next === 'feed' ? 'side' : 'iso'))));
}
function updateStatic() {
  $('#disk-diameter').innerHTML = `${packing(sim.capacity).diameter.toFixed(1)} <small>mm</small>`;
  $<HTMLSelectElement>('#capacity').value = String(sim.capacity); $('#ammo-total').textContent = String(sim.capacity);
  $<HTMLInputElement>('#pitch').value = String(sim.pitch); $('#pitch-value').textContent = `${sim.pitch}°`;
  if (headSize.length) $('#head-size').innerHTML = `${headSize.map(x => x.toFixed(0)).join(' × ')} <small>mm</small>`;
}
function updateUI(force = false) {
  const stamp = [sim.fired, sim.running, sim.playing, sim.remaining, sim.pose.segment, sim.phase, sim.explode].join('/'); if (!force && stamp === uiStamp) return; uiStamp = stamp;
  $('#remaining').textContent = String(sim.remaining); $('#fired').textContent = String(sim.fired);
  $<HTMLButtonElement>('#single-shot').disabled = !scene?.ready || !sim.ready || sim.running;
  $<HTMLButtonElement>('#auto-feed').disabled = !scene?.ready || !sim.ready || sim.running;
  $('#pause-feed').hidden = !sim.running; $('#pause-feed').textContent = sim.playing ? '暂停' : '继续';
  let status = sim.explode > 0 ? '分解观察中，复原后可演示' : sim.running ? `${sim.playing ? '' : '已暂停 · '}${cycleNames[sim.pose.segment]}` : sim.remaining === 0 ? '弹盘已空，可重新装满' : sim.phase === 4 ? '已落座，等待推送' : phases[sim.phase].title;
  if (mode === 'vision') status = 'V2共底架组件';
  if (mode === 'dock') status = phases[sim.phase].title;
  $('#cycle-status').textContent = status;
  document.querySelectorAll<HTMLElement>('[data-cycle]').forEach(el => el.classList.toggle('active', sim.running && +el.dataset.cycle! === sim.pose.segment));
  document.querySelectorAll<HTMLButtonElement>('[data-phase]').forEach(b => b.setAttribute('aria-pressed', String(+b.dataset.phase! === sim.phase)));
  $('#phase-description').textContent = phases[sim.phase].text;
  $<HTMLInputElement>('#pitch').disabled = sim.phase < 2 || sim.running || mode === 'vision';
  $<HTMLInputElement>('#explode').disabled = sim.running;
}
function error(message: string) { $('#loading').hidden = true; $('#scene-error').hidden = false; $('#scene-error').textContent = message; }
try {
  scene = new WorkbenchScene($('#viewport'), sim); scene.onSelect = selectPart; scene.onTick = () => updateUI();
  $('#viewport').addEventListener('scene-error', e => error((e as CustomEvent).detail));
  scene.load(percent => { $('#load-bar').style.width = `${percent * 100}%`; $('#load-label').textContent = `载入CAD参考 ${Math.round(percent * 100)}%`; }).then(() => {
    $('#loading').hidden = true; headSize = scene.getHeadBounds(); updateStatic(); updateUI(true); scene.select(selected);
    // Newly imported children inherit their workspace group except C620, tagged separately.
    document.querySelectorAll<HTMLInputElement>('[data-layer]').forEach(c => scene.setLayer(c.dataset.layer as Layer, c.checked));
    window.__workbench = { ready: true, sim, scene, mode: () => mode, headSize, get selected() { return selected; } };
  }).catch(e => error(`模型加载失败：${e.message}。请刷新重试；本地请用 npm run dev 或 npm run preview 打开。`));
} catch (e) { error(`无法初始化三维视图：${(e as Error).message}。请启用浏览器硬件加速，并确认支持WebGL 2。`); }
setMode(mode, true);
$('#capacity').addEventListener('change', e => { sim.setCapacity(Number((e.target as HTMLSelectElement).value) as 10 | 12); updateStatic(); storeView(); updateUI(true); });
$('#pitch').addEventListener('input', e => { sim.pitch = Number((e.target as HTMLInputElement).value); updateStatic(); storeView(); });
$('#explode').addEventListener('input', e => { const v = Number((e.target as HTMLInputElement).value); sim.setExplode(v / 100); $('#explode-value').textContent = `${v}%`; updateUI(true); });
$('#xray').addEventListener('change', e => scene?.setXray((e.target as HTMLInputElement).checked));
$('#dimensions').addEventListener('change', e => { if (scene) scene.showDimensions = (e.target as HTMLInputElement).checked; });
$('#lid').addEventListener('change', e => scene?.setLid((e.target as HTMLInputElement).checked));
$('#single-shot').addEventListener('click', () => { sim.start(); updateUI(true); });
$('#auto-feed').addEventListener('click', () => { sim.start(true); updateUI(true); });
$('#pause-feed').addEventListener('click', () => { if (sim.playing) sim.pause(); else sim.resume(); updateUI(true); });
$('#refill').addEventListener('click', () => { sim.refill(); updateUI(true); });
document.querySelectorAll<HTMLButtonElement>('[data-mode]').forEach(b => b.addEventListener('click', () => setMode(b.dataset.mode as Mode)));
document.querySelectorAll<HTMLButtonElement>('[data-part]').forEach(b => b.addEventListener('click', () => selectPart(b.dataset.part as Layer)));
document.querySelectorAll<HTMLInputElement>('[data-layer]').forEach(c => c.addEventListener('change', () => scene?.setLayer(c.dataset.layer as Layer, c.checked)));
document.querySelectorAll<HTMLButtonElement>('[data-view]').forEach(b => b.addEventListener('click', () => { scene?.setView(b.dataset.view as View); document.querySelectorAll('[data-view]').forEach(el => el.setAttribute('aria-pressed', String(el === b))); }));
document.querySelectorAll<HTMLButtonElement>('[data-phase]').forEach(b => b.addEventListener('click', () => { sim.setPhase(Number(b.dataset.phase)); updateStatic(); updateUI(true); }));
$('#reset-view').addEventListener('click', () => { scene?.setView('iso'); document.querySelectorAll<HTMLButtonElement>('[data-view]').forEach(el => el.setAttribute('aria-pressed', String(el.dataset.view === 'iso'))); });
$('#show-all').addEventListener('click', () => { document.querySelectorAll<HTMLInputElement>('[data-layer]').forEach(c => { c.checked = true; scene?.setLayer(c.dataset.layer as Layer, true); }); });
$('#share').addEventListener('click', async () => {
  storeView(); try { await navigator.clipboard.writeText(location.href); toast('当前视图地址已复制'); }
  catch { $<HTMLInputElement>('#share-url').value = location.href; $<HTMLDialogElement>('#share-dialog').showModal(); $<HTMLInputElement>('#share-url').select(); }
});
$('#capture').addEventListener('click', () => { if (!scene?.ready) return toast('模型载入后可保存图片'); const a = document.createElement('a'); a.href = scene.screenshot(); a.download = `zenith-${mode}-${sim.capacity}rounds.png`; a.click(); });
declare global { interface Window { __workbench: { ready: boolean; sim: Simulation; scene: WorkbenchScene; mode: () => Mode; selected: Layer; headSize: number[] }; } }
