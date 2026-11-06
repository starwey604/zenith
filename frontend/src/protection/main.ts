import '../style.css';
import './style.css';
import './svg.css';
import svgStyle from './svg.css?inline';
import { attachPageComments, designPageUrl } from '../comments/page';
import { parts, isPart, type Part } from './model';
import { boardDiagram } from './diagram';
import { mountingDiagram, mountingDimensions, mountingLocator, mountingSchemes, isMounting, type Mounting } from './mounting';
const $=<T extends HTMLElement=HTMLElement>(q:string)=>document.querySelector<T>(q)!;
const query=new URLSearchParams(location.search);
const requested=query.get('part');
const requestedMount=query.get('mount');
let mounting:Mounting=isMounting(requestedMount)?requestedMount:'integrated';
let selected:Part=isPart(requested)?requested:'U1';
$('#app').innerHTML=`<header class="app-header"><a class="brand" href="/"><span class="brand-mark">Z</span><strong>Zenith</strong><span class="brand-divider"></span><span>结构工作台</span></a><nav class="header-actions"><a href="/">头部总装</a><a href="/gripper.html">双用途夹爪</a><a href="/dock.html">底座与线束</a><a href="/wiring.html">整头接线</a><strong aria-current="page">接口保护板</strong></nav></header>
<main class="p-page"><div class="p-heading"><div><h1>四线进，四线出：头侧裁判接口保护板</h1><p>触点与保护集成在同一块可拆 PCB 上，放在头下侧边的裁判触点盒内。电源走反接与过压保护，CAN 使用 TMUX7462F 进行双线误接保护。</p></div><button id="download-board">下载布局 SVG</button></div>
<section class="p-mounting" id="mounting" aria-label="保护板安装方案"><div class="p-mount-intro"><div><h2>把保护电路放到触点背面，省掉输入短线</h2><p>接触件朝下，器件朝头内；绝缘支座承托载板。保护后才引出四芯线到 SM11，不改官方测速本体。</p></div><div class="p-locator">${mountingLocator}</div></div><div class="p-sheet"><div class="p-toolbar"><nav class="p-mount-controls" aria-label="安装结构对比">${Object.entries(mountingSchemes).map(([id,v])=>`<button data-mount="${id}" aria-pressed="false">${v.title}</button>`).join('')}</nav><button id="download-mounting">下载安装剖面 SVG</button></div><div class="p-mount-scroll" tabindex="0" aria-label="安装剖面，可横向滚动"><div id="mount-diagram"></div></div><div class="p-mount-detail"><p id="mount-detail" aria-live="polite"></p><p><strong>省的是头侧输入段：</strong>车侧弹针背后、FIRE / MiniPC / 自有 CAN 的线束，以及去测速的输出线仍需留空。板框与总厚度等元件排布、支撑和插头确定后再收紧。</p><div class="p-mount-actions"><a href="/dock.html?mode=harness&contact=R3">在底座三维中看安装位置</a><span>剖面展开显示对接关系，不代表实际间隙。</span></div></div></div></section>
${mountingDimensions()}
<h2 class="p-layout-heading">电气路径：触点输入 → 保护 → 测速</h2><section class="p-sheet" aria-label="保护板布局"><div class="p-toolbar"><span>布局意向 · 正常供电路径</span><nav aria-label="查看保护器件">${Object.keys(parts).map(id=>`<button data-select="${id}" aria-pressed="false">${id==='CAN'?'U2 · CAN':id}</button>`).join('')}</nav></div><div class="p-scroll" tabindex="0" aria-label="保护板示意图，可横向滚动"><div id="board"></div></div><div class="p-foot">点击器件查看用途。U2 已选 TMUX7462F；U1 与外置 MOS 继续选型。图中 S1/D1、S2/D2 是芯片信号名，不是接头编号；供电、阈值与封装在原理图阶段细化。</div></section>
<section class="p-detail" aria-live="polite" id="part-detail"></section>
<div class="p-notes"><section><h2>机械安装留这三处空间</h2><ul><li><strong>接触面：</strong>R1–R4 焊脚 / 板内铜连接直达保护电路，输入无短线；接触件周围设绝缘承托。</li><li><strong>板体：</strong>触点载板由支座承托并固定，装头载荷由底座承力件承担；邮票口焊点不承担对接压力。</li><li><strong>输出侧：</strong>保护后四芯线保留插拔与服务弯空间，SM11 原接头可拔插，侧盖可拆；标准测试接口与盲插端共用保护路径。</li></ul><a href="/dock.html?mode=harness&contact=R3">查看触点焊尾与线束留空</a></section><section><h2>这块板保护什么</h2><p>按 S145，头侧四芯任意两针接入不超过 30 V 的外部电源，裁判模块允许离线，但不能损坏。电源反接只是其中一种情况，CAN 线也可能接到外部电源。</p><p>车侧接口短接时还需保证车内裁判系统正常，另由车侧保护段承担。本页画的是头侧板；不增加 MCU、ADC 或串口状态上传。</p><a href="/wiring.html?circuit=REF&focus=1">返回整头裁判四芯路径</a></section></div>
<section class="p-next"><h2>先验证电路，再收紧板子</h2><p>优先自制专用板；有原理图的模块或评估板用于台架验证。CAN 已选 TMUX7462F，先核对供电与阈值配置、正常通信和故障断开，再冻结器件封装和板框。当前尚未完成 S145 故障测试。</p></section>
<details class="p-reference"><summary>规则与器件依据</summary><p>仓库《RoboMaster 2027 机甲大师高校系列赛机器人制作规范手册 V1.0.0（20261015）》第76页，S145、图3-36；触点用途共用底座页数据。</p><p><a href="https://www.ti.com/lit/ds/symlink/tps2663.pdf" target="_blank" rel="noreferrer">TI TPS2663 数据手册</a>：过压关断选型见第19–20页，外置 Q1 / Q2 参考图8-7见第21页。电源区仅表达功能关系，实际栅极、地、采样与配置网络按参考电路绘制。</p><p><a href="https://www.ti.com/lit/ds/symlink/tmux7462f.pdf" target="_blank" rel="noreferrer">TI TMUX7462F 数据手册</a>：S 端具备上电及掉电故障保护，正常通信双向；DR 置高时故障 D 端高阻。供电与故障阈值配置网络另行展开。</p><p><a href="https://www.robomaster.com/zh-CN/products/components/detail/2597" target="_blank" rel="noreferrer">SM11 官方参数</a>：12 V、最大17 W，对应约1.42 A；限流设置还需核对启动电流。</p></details></main>`;
function render(){
 $('#board').innerHTML=boardDiagram(selected);
 const p=parts[selected];
 $('#part-detail').innerHTML=`<div><span>${p.role}</span><h2>${p.title}</h2></div><div><p>${p.text}</p><p>${p.next}</p>${p.source?`<a href="${p.source}" target="_blank" rel="noreferrer">查看芯片参考电路</a>`:''}</div>`;
 document.querySelectorAll<HTMLButtonElement>('[data-select]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.select===selected)));
 document.querySelectorAll<SVGElement>('[data-part]').forEach(el=>{el.onclick=()=>choose(el.dataset.part as Part);el.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();const id=el.dataset.part as Part;choose(id);document.querySelector<SVGElement>(`[data-part="${id}"]`)?.focus();}};});
 history.replaceState(null,'',`/protection.html?${new URLSearchParams({part:selected,mount:mounting})}${location.hash}`);
}
function choose(id:Part){selected=id;render();}
document.querySelectorAll<HTMLButtonElement>('[data-select]').forEach(b=>b.onclick=()=>choose(b.dataset.select as Part));
function downloadSvg(selector:string,name:string){
 const svg=$(selector).cloneNode(true) as unknown as SVGElement;
 const style=document.createElementNS('http://www.w3.org/2000/svg','style');style.textContent=svgStyle;svg.prepend(style);
 const url=URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(svg)],{type:'image/svg+xml;charset=utf-8'}));
 const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
};
$('#download-board').onclick=()=>downloadSvg('#protection-svg','zenith-referee-protection-layout.svg');
$('#download-mounting').onclick=()=>downloadSvg('#mounting-svg',`zenith-protection-mounting-${mounting}.svg`);
function renderMounting(){
 $('#mount-diagram').innerHTML=mountingDiagram(mounting);
 $('#mount-detail').textContent=mountingSchemes[mounting].detail;
 document.querySelectorAll<HTMLElement>('[data-mount]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.mount===mounting)));
 render();
}
document.querySelectorAll<HTMLElement>('[data-mount]').forEach(b=>b.onclick=()=>{mounting=b.dataset.mount as Mounting;renderMounting();});
renderMounting();
attachPageComments(()=>({topic:'protection',candidate:'referee-head-board',revision:'protection-layout-v0.3',part:parts[selected].title,pageUrl:designPageUrl({part:selected,mount:mounting}),parameters:{part:selected,mount:mounting}}));
