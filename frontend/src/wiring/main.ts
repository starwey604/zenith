import '../style.css';
import './style.css';
import { attachPageComments, designPageUrl } from '../comments/page';
import './svg.css';
import { contacts,circuitLabels,circuitColors,circuitOrder,routes,isSelection,routeContacts,exportCsv,type Selection } from './model';
import { diagram } from './diagram';
const $=<T extends HTMLElement=HTMLElement>(q:string)=>document.querySelector<T>(q)!;
const requested=new URLSearchParams(location.search).get('circuit');
let selection:Selection=isSelection(requested)?requested:'all';
let focused=new URLSearchParams(location.search).get('focus')==='1';
$('#app').innerHTML=`
<header class="app-header"><a class="brand" href="/"><span class="brand-mark">Z</span><strong>Zenith</strong><span class="brand-divider"></span><span>结构工作台</span></a><nav class="header-actions"><a href="/">头部总装</a><a href="/gripper.html">双用途夹爪</a><a href="/dock.html">底座与线束</a><strong aria-current="page">整头接线</strong><a href="/protection.html">接口保护板</a></nav></header>
<main class="w-page">
<div class="w-heading"><div><h1>从底盘到头，每根线都有去处</h1><p>电脑走 Mini PC，摩擦轮走 Ammo-Booster。车侧 CAN 直达 LBC3；另一独立 CAN 经分电板连接两块 C620。</p></div><div class="w-downloads"><button id="download-wiring">下载接线图 SVG</button><button id="download-csv">下载触点 CSV</button></div></div>
<section class="w-sheet" aria-label="整头接线工作区">
<div class="w-toolbar"><nav aria-label="选择接线支路"><button data-circuit="all" aria-pressed="true">全图</button>${circuitOrder.map(c=>`<button data-circuit="${c}" aria-pressed="false"><i style="background:${circuitColors[c]}"></i>${circuitLabels[c]}</button>`).join('')}</nav><label><input type="checkbox" id="focus-route"/>仅看所选支路</label></div>
<div class="w-strip"><span>实线＝成束电源 / 设备连接　虚线＝CAN 通信</span><span>一条线表示一束线，芯数见接线表</span></div>
<div id="diagram-scroll" class="w-diagram-scroll" tabindex="0" aria-label="接线图，可横向滚动"><div id="diagram"></div></div>
<div class="w-sheet-footer"><span>横向查看完整路径；选择支路可高亮或单独展开。</span><a href="/dock.html?mode=contacts&contact=A1">对照实际触点位置</a></div>
</section>
<section id="route-detail" class="w-detail" aria-live="polite"></section>
<section class="w-table-section"><div class="w-section-heading"><h2>跨底座的 ${contacts.length} 项功能</h2><p>两对电源、裁判四芯与车侧 CAN。点击编号，查看底座接触面与焊尾空间。</p></div><div class="w-table-scroll"><table><thead><tr><th>触点</th><th>功能</th><th>来自底盘</th><th>进入头后</th></tr></thead><tbody>${contacts.map(c=>`<tr data-row-circuit="${c.circuit}"><td><a href="/dock.html?mode=contacts&contact=${c.id}" style="--wire:${circuitColors[c.circuit]}">${c.id}</a></td><td><strong>${c.name}</strong>${c.official?`<small>官方四芯 ${c.official}</small>`:''}</td><td>${c.vehicle}</td><td>${c.head}</td></tr>`).join('')}</tbody></table></div></section>
<section class="w-notes"><article><h2>机械布线时保留这些空间</h2><ul><li>两路电源分别成对固定。电脑回流不经过电机大电流路径，不以框架代替导线。</li><li>REF_CAN、车侧 CAN A、电机 CAN B 各自双绞；电机相线避开MIPI、信号焊尾和测速线。</li><li>触点盒浮动处留服务弯，固定点放在托架上；俯仰与yaw活动处另留运动线束余量。</li><li>C620电源、CAN、三相及传感器接头均可检修；不把接头压在摩擦轮、弹路或锁钩下。</li></ul><a href="/dock.html?mode=harness&contact=A1">查看焊尾、弯曲与线夹空间</a></article><article><h2>这一版接线的约定</h2><p>Mini PC 24 V 直接进LBC3顶板，保护与降压由顶板处理。Ammo-Booster电源与LBC3独立的CAN B接入同一块普通分电板，再接两块C620；车侧CAN A不接此板。不另画削波、泄放或电脑保护模块。</p><p>裁判四芯仍保留车侧与<a href="/protection.html">头侧保护板</a>；车载供弹驱动留在Ammo-Booster支路。头上没有电池、图传或新增STM32板。</p><p>本图确定连接关系，不指定线径、插头型号或长度。电调瞬态处理能力与顶板输入耐受需结合实际硬件确认；普通分电板本身没有被赋予吸收回馈的功能。</p></article></section>
<details class="w-reference"><summary>接线依据与待定接口</summary><p>触点编号、用途与底座图保持一致。LBC3顶板支持24 V及保护分工按本轮确认方案绘制。</p><p>依据仓库2027机器人制作规范V1.0.0：S113/表3-4对应供电接口，S114要求发射执行器随Ammo-Booster断电，S145约束裁判四芯故障。车侧四芯任意两线短接时裁判系统仍正常；头侧任意两针接入不超过30 V的正负电源时允许离线但不得损坏。</p><p>C620与M3508连接参考<a href="https://rm-static.djicdn.com/tem/17348/RoboMaster%20C620%20Brushless%20DC%20Motor%20Speed%20Controller%20V1.01.pdf" target="_blank" rel="noreferrer">官方C620手册</a>；实际顶板接头、分电板端子和线束长度待实物确定。C0仍是控制参考地预留，不在10项已接功能内；顶板需提供两路独立CAN控制器及收发器，软件负责两段命令与反馈。每段总线按物理两端配置终端，布线参考 <a href="https://www.analog.com/en/resources/app-notes/an-1123.html" target="_blank" rel="noreferrer">ADI CAN实施指南</a>；参考地/隔离与接头随原理图落实。</p></details>
</main>`;
function render(){
 document.querySelectorAll<HTMLButtonElement>('[data-circuit]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.circuit===selection)));
 $<HTMLInputElement>('#focus-route').disabled=selection==='all';$<HTMLInputElement>('#focus-route').checked=focused;
 $('#diagram').innerHTML=diagram(selection,focused);
 document.querySelectorAll<HTMLElement>('[data-row-circuit]').forEach(row=>row.classList.toggle('selected',row.dataset.rowCircuit===selection));
 $('#route-detail').innerHTML=selection==='all'?`<div><h2>两条 CAN，在 LBC3 处分开</h2><p>C1/C2直达LBC3的CAN A；独立CAN B再接分电板，与F1/F2电源分别布线到两块C620。A1/A2单独供电脑顶板。</p></div><div><h3>先选支路，再对照触点</h3><p>上方按支路高亮，下方直接跳到对应触点。CAM1、相机和电机线都留在头内，不再占用底座触点。</p></div>`:(()=>{const r=routes[selection];return `<div><h2>${r.title}</h2><p class="w-path">${r.path}</p><div class="w-contact-links">${routeContacts(selection).map(c=>`<a href="/dock.html?mode=contacts&contact=${c.id}">${c.id} · ${c.name}</a>`).join('')}</div></div><div><h3>这束线怎么接</h3><p>${r.wires}</p><p>${r.assembly}</p></div>`;})();
 history.replaceState(null,'',`${location.pathname}?${new URLSearchParams({circuit:selection,focus:focused?'1':'0'})}`);
}
document.querySelectorAll<HTMLButtonElement>('[data-circuit]').forEach(b=>b.onclick=()=>{selection=b.dataset.circuit as Selection;render();});
$<HTMLInputElement>('#focus-route').onchange=e=>{focused=(e.target as HTMLInputElement).checked;render();};
function download(name:string,body:string,type:string){const url=URL.createObjectURL(new Blob([body],{type}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
$('#download-csv').onclick=()=>download('zenith-head-wiring.csv',exportCsv(),'text/csv;charset=utf-8');
$('#download-wiring').onclick=()=>{
 const svg=$<HTMLElement>('#wiring-svg').cloneNode(true) as unknown as SVGElement;
 const css=document.createElementNS('http://www.w3.org/2000/svg','style');css.textContent=svgStyle;svg.prepend(css);
 download('zenith-head-wiring.svg',new XMLSerializer().serializeToString(svg),'image/svg+xml;charset=utf-8');
};
// Embedded export styles keep the downloaded schematic legible without the website.
import svgStyle from './svg.css?inline';
render();
attachPageComments(() => ({ topic: 'wiring', candidate: 'head-interface', revision: 'wiring-v0.2',
  part: selection === 'all' ? '整头接线' : routes[selection].title,
  pageUrl: designPageUrl({ circuit: selection, focus: focused ? '1' : '0' }),
  parameters: { circuit: selection, focused },
}));
