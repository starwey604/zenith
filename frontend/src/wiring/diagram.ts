import { circuitColors, circuitLabels, type Selection, routes } from './model';
import type { Circuit } from '../dock/model';
const esc=(s:string)=>s.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;');
function label(x:number,y:number,text:string,cls='wire-label'){return `<text class="${cls}" x="${x}" y="${y}">${esc(text)}</text>`;}
function node(x:number,y:number,w:number,title:string,sub:string,h=58){return `<g class="device"><rect x="${x}" y="${y}" width="${w}" height="${h}" rx="5"/>${label(x+14,y+24,title,'device-title')}${label(x+14,y+45,sub,'device-sub')}</g>`;}
function path(d:string,caption?:[number,number,string],cls='wire'){return `<path class="${cls}" d="${d}"/>${caption?label(...caption):''}`;}
function port(y:number,ids:string,title:string){return `<g class="connector"><rect x="350" y="${y-29}" width="130" height="58" rx="5"/>${label(365,y-4,ids,'port-id')}${label(365,y+17,title,'device-sub')}</g>`;}
function lane(id:Circuit,body:string,selection:Selection,offset=0){const r=routes[id];return `<g data-route="${id}" class="lane ${selection!=='all'&&selection!==id&&!(id==='FIRE'&&selection==='CTRL')?'muted':''}" style="--wire:${circuitColors[id]}"><rect class="lane-bg" x="8" y="${r.y}" width="1264" height="${r.height}" rx="3"/>${label(26,r.y+26,id==='FIRE'?'发射电源＋自有 CAN':circuitLabels[id],'lane-title')}<g transform="translate(0 ${offset})">${body}</g></g>`;}
export function diagram(selection:Selection,focus:boolean){
 const crop=focus&&selection!=='all'?routes[selection]:null;
 return `<svg xmlns="http://www.w3.org/2000/svg" id="wiring-svg" viewBox="0 ${crop?crop.y-4:0} 1280 ${crop?crop.height+8:940}" role="img" aria-labelledby="wiring-title wiring-description">
 <title id="wiring-title">底盘与可拆头的接线图</title><desc id="wiring-description">Mini PC 电源经 A1/A2 直连 LBC3 顶板；Ammo-Booster 经 F1/F2、自有 CAN 经 C1/C2 一起进入同一块动力分电＋CAN分线板，输出两路电调电源及三路CAN，分别连接两块C620和LBC3。</desc>
 <rect class="canvas-bg" x="0" y="0" width="1280" height="940"/>
 ${label(26,31,'底盘 / 车侧托架','column-title')}${label(350,31,'盲插触点','column-title')}${label(520,31,'可拆发射头','column-title')}
 ${label(26,54,'供弹驱动留在车上','column-sub')}${label(350,54,'功能编号沿用底座图','column-sub')}${label(520,54,'电脑、测速、两块电调随头拆装','column-sub')}
 <path class="boundary" d="M332 65V930 M498 65V930"/>
 ${lane('FIRE',`
 ${path('M260 148H350 M480 148H520')}
 ${path('M765 140H840 M765 230H840')}
 ${path('M1000 148H1100',[1008,133,'三相＋传感器'])}${path('M1000 238H1100',[1008,223,'三相＋传感器'])}
 ${path('M80 177V210')}
 ${node(30,119,230,'Ammo-Booster','发射电源 / 车侧接通控制')}${port(148,'F1 / F2','FIRE 正 / 回流')}
 <g class="device" data-shared-board="power-can"><rect x="520" y="119" width="245" height="260" rx="5"/>
 ${label(534,145,'动力分电＋CAN 分线板','device-title')}
 ${label(534,183,'两路电调电源输出','device-sub')}${label(534,208,'FIRE 正 / 回流','device-sub')}
 <path d="M534 240H750" class="boundary"/>
 ${label(534,281,'三路 CAN 分线输出','device-sub')}${label(534,306,'同一条自有 CAN 总线','device-sub')}
 ${label(534,359,'不接 Mini PC 电源','device-sub')}</g>
 ${node(840,119,160,'C620 左','电源＋CAN')}${node(840,209,160,'C620 右','电源＋CAN')}
 ${node(1100,119,150,'M3508 左','摩擦轮驱动')}${node(1100,209,150,'M3508 右','摩擦轮驱动')}
 ${node(30,210,230,'车载供弹驱动','分度 / 推送 / 止弹，同受断电',58)}
 <g data-route="CTRL" style="--wire:${circuitColors.CTRL}">
 ${path('M260 338H350 M480 338H520',undefined,'signal')}
 ${path('M765 180H810V164H840',undefined,'signal')}
 ${path('M765 270H810V254H840',undefined,'signal')}
 ${path('M765 345H840',undefined,'signal')}
 ${node(30,309,230,'车侧自有控制 CAN','与裁判 CAN 分开')}${port(338,'C1 / C2','CAN_H / CAN_L')}
 ${node(840,316,160,'LBC3','顶板 CAN 接口')}
 </g>
 ${label(520,400,'一块板：两路电调电源＋三路 CAN；LBC3 供电仍走下方 Mini PC','wire-label')}`,selection)}
 ${lane('AUX',`
 ${path('M260 355H350 M480 355H520 M690 355H790')}${path('M950 355H1025',[963,342,'MIPI'])}${path('M1120 384V405')}
 ${node(30,326,230,'Mini PC 接口','24 V / 回流，独立于发射电源')}${port(355,'A1 / A2','Mini PC 24 V')}
 ${node(520,326,170,'LBC3 顶板','24 V 输入')}${node(790,326,160,'LBC3','顶板供电')}
 ${node(1025,326,225,'CAM1 转接板','头内排线，不跨盲插')}${node(1025,405,225,'摄像头','MIPI 连接',58)}
 ${label(520,418,'保护与降压由顶板处理；图中不另设模块','wire-label')}
 ${label(520,443,'MIPI 两端固定，顶板插头预留拔插空间','wire-label')}`,selection,130)}
 ${lane('REF',`
 ${path('M260 550H350 M480 550H520 M735 550H1000')}
 ${node(30,521,230,'裁判主链路 → 车侧保护','独立供电保护 / CAN 故障切离')}${port(550,'R1–R4','裁判四芯')}
 ${node(520,521,215,'头侧四线保护','电源及 CAN 任意两针误接')}${node(1000,521,250,'大测速 SM11','12 V / GND / 裁判 CAN')}
 ${label(762,535,'四芯航空线','wire-label')}
 ${label(30,622,'R1 棕 GND   /   R2 橙 CAN_L   /   R3 红 12 V   /   R4 黄 CAN_H','wire-label')}
 ${label(700,622,'标准四芯测试端与盲插端共用保护路径','wire-label')}`,selection,130)}
 ${lane('PRESENT',`
 ${path('M260 944H350 M480 944H600',undefined,'signal')}
 ${node(30,915,230,'车侧在位检测','低能量检测源 / 返回')}${port(944,'D1 / D2','去程 / 返回')}
 ${node(600,915,250,'无源短接片 / 识别电阻','头侧触点盒内')}
 ${label(900,937,'不依赖 LBC3 启动','wire-label')}${label(900,962,'锁紧反馈单独留在车侧','wire-label')}`,selection,-80)}
 </svg>`;
}
