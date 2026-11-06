import '../style.css';
import './style.css';
import { attachPageComments, designPageUrl } from '../comments/page';
import { candidates, tasks, geometry, poseAt, budget, type Candidate, type Task } from './model';
import { GripperScene } from './scene';
const $ = <T extends HTMLElement = HTMLElement>(q: string) => document.querySelector<T>(q)!;
const params = new URLSearchParams(location.search);
let candidate: Candidate = params.get('candidate') === 'angular' ? 'angular' : 'parallel';
let task: Task = ['ore', 'store'].includes(params.get('task') ?? '') ? params.get('task') as Task : 'head';
const rawStep = Number(params.get('step') ?? '2');
let progress = Number.isFinite(rawStep) ? Math.max(0, Math.min(4, rawStep)) : 2;
let playing = false;
$('#app').innerHTML = `
<header class="app-header"><a class="brand" href="/"><span class="brand-mark">Z</span><strong>Zenith</strong><span class="brand-divider"></span><span>结构工作台</span></a><nav class="header-actions"><a href="/">头部总装</a><span aria-current="page">双用途夹爪</span><a href="/dock.html">底座与线束</a><a href="/wiring.html">整头接线</a><a href="/protection.html">接口保护板</a></nav></header>
<main class="gripper-page">
  <div class="g-heading"><div><h1>一副夹爪，两种承载方式</h1><p>软垫夹矿，承力槽扣头。先把抓取、承重和退出看清楚。</p></div><span class="g-revision">结构意向 v0.1 · 尺寸单位 mm</span></div>
  <div class="g-candidates" role="group" aria-label="夹爪候选">${Object.entries(candidates).map(([id,c]) => `<button data-candidate="${id}" aria-pressed="${candidate === id}"><span class="g-candidate-icon">${id === 'parallel' ? '⇥ ⇤' : '↘ ↙'}</span><span><strong>${c.title}</strong><small>${c.subtitle}</small></span><span class="g-choice">${id === 'parallel' ? 'A' : 'B'}</span></button>`).join('')}</div>
  <div class="g-workspace">
    <section class="g-visual" aria-label="夹爪动作演示">
      <nav class="g-tasks" aria-label="抓取任务">${Object.entries(tasks).map(([id,t]) => `<button data-task="${id}" aria-pressed="${task === id}">${t.title}</button>`).join('')}</nav>
      <div class="g-stage">
        <div id="gripper-viewport"></div>
        <div class="g-viewbar"><div role="group" aria-label="观察视角"><button data-view="iso" aria-pressed="true">立体</button><button data-view="front" aria-pressed="false">正视</button><button data-view="side" aria-pressed="false">侧视</button><button data-view="detail" aria-pressed="false">近看接口</button></div><label><input type="checkbox" id="forces" checked/>载荷方向</label></div>
        <div class="g-scene-note"><span>参数化结构示意</span><span>拖动旋转 · 滚轮缩放</span></div>
        <div id="g-error" role="alert" hidden></div>
      </div>
      <div class="g-legend"><span><i style="background:#8098aa"></i>刚性骨架</span><span><i style="background:#368d83"></i>软接触垫</span><span><i style="background:#d79935"></i>承力接口</span><span><i style="background:#4e85a9"></i>固定支座</span><span><i style="background:#9b7cae"></i>驱动占位</span></div>
      <div class="g-timeline">
        <div class="g-motion-title"><h2 id="task-title"></h2><button id="play" class="primary">播放动作</button></div>
        <div id="g-steps" class="g-steps" role="group" aria-label="动作阶段"></div>
        <label class="g-scrub">动作进度<input id="progress" aria-label="动作进度" type="range" min="0" max="4" step="0.01" value="${progress}"/><output id="gap"></output></label>
        <p id="step-note" aria-live="polite"></p>
        <p class="g-evidence">动作演示使用工具端平移，不含六轴臂逆解、碰撞求解或接触力仿真。</p>
      </div>
    </section>
    <aside class="g-inspector">
      <div class="g-panel"><h2 id="candidate-title"></h2><p id="candidate-description"></p><p class="g-decision" id="candidate-tradeoff"></p></div>
      <div class="g-panel"><h2>同一指尖，不换工具</h2>
        <svg class="g-section" viewBox="0 0 300 240" role="img" aria-label="夹头闭合位正视剖面：金色承力肩置于两指槽内，下托唇承重，头部颈宽64毫米，肩宽86毫米。软垫位于上方。">
          <path d="M45 18h24v157H45zm186 0h24v157h-24z" fill="#8098aa"/>
          <path d="M69 25h8v95h-8zm154 0h8v95h-8z" fill="#368d83"/>
          <path d="M45 150h48v16H45zm162 0h48v16h-48zM45 118h38v10H45zm172 0h38v10h-38z" fill="#d79935"/>
          <path d="M83 130h134v19H83zm17 19h100v55H100z" fill="#e9bb68" stroke="#ad7428"/>
          <path d="M100 205h100M100 200v10m100-10v10M83 223h134M83 218v10m134-10v10" stroke="#54768b" fill="none"/>
          <text x="150" y="195" text-anchor="middle">颈宽 64</text><text x="150" y="238" text-anchor="middle">肩宽 86</text>
          <path d="M150 153v26m-5-6 5 6 5-6" stroke="#a76c17" stroke-width="2" fill="none"/>
          <text x="150" y="54" text-anchor="middle" fill="#26796d">软垫夹矿</text><text x="150" y="102" text-anchor="middle">上限位</text><path d="M115 106 80 122m105-16 35 16" stroke="#748996"/>
          <text x="150" y="143" text-anchor="middle" fill="#694515">头部承力肩</text>
        </svg>
        <p class="g-small">夹头闭合位剖面。下托唇接住肩部；前后挡边限制轴向滑移。硬接触区避开夹矿软垫。</p>
      </div>
      <div class="g-panel g-dimensions"><h2>第一版几何参数</h2><dl><div><dt>张开净距</dt><dd>112 mm</dd></div><div><dt>夹矿 / 夹头净距</dt><dd>65 / 80 mm</dd></div><div><dt>头部承力肩厚</dt><dd>12 mm</dd></div><div><dt>下托唇内伸</dt><dd>8 mm</dd></div></dl><p class="g-small">这些数值用于比较包络，尚未加入制造公差。能量单元按规则主要尺寸简化；头部外形、驱动与底座为占位。</p></div>
    </aside>
  </div>
  <section class="g-bottom">
    <article class="g-budget"><h2>夹紧力与腕部预算</h2><p>比较纯摩擦夹头的代价，判断为什么需要承力肩。</p>
      <div class="g-inputs"><label>头部质量 <input id="mass" type="range" min="1.5" max="2.8" step="0.05" value="2.5"/><output id="mass-out">2.50 kg</output></label><label>重心偏距 <input id="offset" type="range" min="0" max="100" step="5" value="50"/><output id="offset-out">50 mm</output></label><label>摩擦系数 <select id="friction"><option value="0.3">0.3 · 较低</option><option value="0.5" selected>0.5 · 比较基准</option><option value="0.7">0.7 · 较高</option></select></label></div>
      <div class="g-numbers"><div><span>纯摩擦，每指夹紧力</span><strong id="jaw-force"></strong></div><div><span>偏心设计弯矩</span><strong id="moment"></strong></div><div><span>腕部总负载预算</span><strong id="payload"></strong></div></div>
      <p id="payload-note" class="g-budget-note"></p><details><summary>计算假设与受力边界</summary><p>加速度 3 m/s²，载荷系数 2。每指法向力 N = 2m(g+a)/(2μ)；偏心弯矩 M = 2m(g+a)e。夹爪、转接件与线束合计暂留 0.45 kg。额定 3 kg 仅作质量对照，不替代腕部允许弯矩。</p><p>承力肩转移了对摩擦的依赖，指根弯曲、槽口接触、撑开力和断电保持仍需设计。这里的力不是电机扭矩，也不是有限元仿真结果。</p></details>
    </article>
    <article class="g-next"><h2>先看这三个地方</h2><ol><li><strong>夹头时，抓取座要靠近重心</strong><p>抓取座连接主框架，不连接相机壳。上方 / 后上方位置还需与相机、供弹接头联合布局。</p></li><li><strong>存矿时，留出松爪的缺口</strong><p>两端托住能量单元，中段留空；先卸载，再张开，最后退出。</p></li><li><strong>对开爪要补偿接触角</strong><p>切到 B 看同一动作。其槽口按夹头位对齐，夹矿位的指面角度变化是下一轮特化重点。</p></li></ol></article>
  </section>
  <details class="g-sources"><summary>开源构型与规则依据</summary><p>两种候选是基于以下构型特征重新搭建的参数示意，未导入上游夹爪 CAD。</p><ul><li><a href="https://github.com/Toyota/yubi-hw" target="_blank" rel="noreferrer">Toyota YUBI</a>：机器人端单电机齿轮同步对开，不采用手持端载荷数据。</li><li><a href="https://github.com/pollen-robotics/PincOpen" target="_blank" rel="noreferrer">PincOpen</a>：平行指与模块化指尖参考；本页 A 是直线导向示意，不是原版多连杆复刻。</li><li><a href="https://bbs.robomaster.com/article/1947243?source=11" target="_blank" rel="noreferrer">港科大 ENTERPRIZE RM2026</a>：金属齿轮与刚性轴系参考。</li><li><a href="https://bbs.robomaster.com/article/1882734?source=1" target="_blank" rel="noreferrer">五邑 IMCA RM2026</a>：丝杆增力与适形接触参考。</li><li>仓库 2027 超级对抗赛规则 V1.0.0：印刷页45、59–60、85–88。能量单元 400±50 g，长150±1 mm，大端Ø95±1、小端Ø80±1；轴向拔出额外阻力至多10 N，装配回正力矩至多0.3 N·m。</li></ul></details>
</main>`;
let scene: GripperScene | undefined;
function save() { history.replaceState(null, '', `${location.pathname}?${new URLSearchParams({ candidate, task, step: progress.toFixed(2) })}`); }
function viewButtons(view = 'iso') { document.querySelectorAll<HTMLElement>('[data-view]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.view === view))); }
let stamp = '';
function render(saveUrl = true) {
  if (scene) { scene.candidate = candidate; scene.update(progress); }
  const step = Math.min(4, Math.floor(progress + .001));
  const key = `${candidate}/${task}/${step}/${playing}`;
  if (key !== stamp) {
    stamp = key;
    document.querySelectorAll<HTMLElement>('[data-candidate]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.candidate === candidate)));
    document.querySelectorAll<HTMLElement>('[data-task]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.task === task)));
    $('#candidate-title').textContent = candidates[candidate].title; $('#candidate-description').textContent = candidates[candidate].description; $('#candidate-tradeoff').textContent = candidates[candidate].tradeoff;
    $('#task-title').textContent = tasks[task].title;
    // Keep stage buttons stable while scrubbing so keyboard focus is preserved.
    if ($('#g-steps').dataset.task !== task) { $('#g-steps').dataset.task = task; $('#g-steps').innerHTML = tasks[task].labels.map((s,i) => `<button data-step="${i}" aria-pressed="false"><span>${i + 1}</span>${s}</button>`).join(''); }
    document.querySelectorAll<HTMLElement>('[data-step]').forEach(b => b.setAttribute('aria-pressed', String(Number(b.dataset.step) === step)));
    $('#step-note').textContent = tasks[task].notes[step]; $('#play').textContent = playing ? '暂停' : progress >= 4 ? '重新播放' : '播放动作';
  }
  $<HTMLInputElement>('#progress').value = String(progress); $('#gap').textContent = `参考净距 ${poseAt(task, progress).gap.toFixed(0)} mm`;
  if (saveUrl) save();
}
try {
  scene = new GripperScene($('#gripper-viewport')); scene.setTask(task); scene.candidate = candidate; scene.update(progress);
  scene.onTick = dt => { if (!playing) return; progress = Math.min(4, progress + dt * .5); if (progress === 4) { playing = false; save(); } render(false); };
} catch (e) { $('#g-error').hidden = false; $('#g-error').textContent = `三维视图未能启动：${(e as Error).message}。请启用 WebGL 2 / 硬件加速后重试。`; $<HTMLButtonElement>('#play').disabled = true; }
render();
document.querySelectorAll<HTMLElement>('[data-candidate]').forEach(b => b.onclick = () => { playing = false; candidate = b.dataset.candidate as Candidate; render(); });
document.querySelectorAll<HTMLElement>('[data-task]').forEach(b => b.onclick = () => { playing = false; task = b.dataset.task as Task; progress = 0; scene?.setTask(task); viewButtons(); render(); });
$('#g-steps').onclick = e => { const b = (e.target as HTMLElement).closest<HTMLElement>('[data-step]'); if (!b) return; playing = false; progress = Number(b.dataset.step); render(); };
$<HTMLInputElement>('#progress').oninput = e => { playing = false; progress = Number((e.target as HTMLInputElement).value); render(); };
$('#play').onclick = () => { if (progress >= 4) progress = 0; playing = !playing; if (playing && scene?.closeup) { scene.view('iso'); viewButtons(); } render(); };
document.querySelectorAll<HTMLElement>('[data-view]').forEach(b => b.onclick = () => { scene?.view(b.dataset.view as 'iso' | 'front' | 'side' | 'detail'); viewButtons(b.dataset.view); });
$<HTMLInputElement>('#forces').onchange = e => { if (scene) { scene.forces = (e.target as HTMLInputElement).checked; scene.update(progress); } };
function updateBudget() {
  const mass = Number($<HTMLInputElement>('#mass').value), offset = Number($<HTMLInputElement>('#offset').value), friction = Number($<HTMLSelectElement>('#friction').value);
  const b = budget(mass, offset, friction); $('#mass-out').textContent = `${mass.toFixed(2)} kg`; $('#offset-out').textContent = `${offset} mm`;
  $('#jaw-force').textContent = `${b.perJaw.toFixed(1)} N`; $('#moment').textContent = `${b.moment.toFixed(2)} N·m`; $('#payload').textContent = `${b.payload.toFixed(2)} kg`;
  $('#payload-note').textContent = b.payload > 3 ? `超过 3 kg 额定负载 ${(b.payload - 3).toFixed(2)} kg，需减重或重新选臂。` : `距 3 kg 额定负载还余 ${(3 - b.payload).toFixed(2)} kg；夹爪总成暂按 0.45 kg 预算，实际质量待设计。`;
  $('#payload-note').classList.toggle('over', b.payload > 3);
}
for (const id of ['mass', 'offset', 'friction']) $(`#${id}`).addEventListener('input', updateBudget);
updateBudget();
window.addEventListener('pagehide', () => scene?.dispose());
declare global { interface Window { __gripper: { scene?: GripperScene; candidate: () => Candidate; task: () => Task; progress: () => number; playing: () => boolean; geometry: typeof geometry } } }
window.__gripper = { scene, candidate: () => candidate, task: () => task, progress: () => progress, playing: () => playing, geometry };
attachPageComments(() => ({ topic: 'gripper', candidate: 'dual-purpose-comparison', revision: 'gripper-v0.1',
  part: `${candidates[candidate].title} / ${tasks[task].title}`,
  pageUrl: designPageUrl({ candidate, task, step: progress }),
  parameters: { candidate, task, step: progress, massKg: Number($<HTMLInputElement>('#mass').value),
    offsetMm: Number($<HTMLInputElement>('#offset').value), friction: Number($<HTMLSelectElement>('#friction').value) },
}));
