import { pins, pinY, type Part } from './model.ts';
const text=(x:number,y:number,s:string,cls='label')=>`<text x="${x}" y="${y}" class="${cls}">${s}</text>`;
function chip(id:Part,x:number,y:number,w:number,h:number,title:string,sub:string,selected:Part){
 return `<g data-part="${id}" role="button" tabindex="0" aria-label="查看 ${id} ${title}" aria-pressed="${id===selected}" class="chip ${id===selected?'selected':''}"><rect x="${x}" y="${y}" width="${w}" height="${h}" rx="7"/>${text(x+16,y+27,id,'ref')}${text(x+16,y+57,title,'chip-title')}${text(x+16,y+83,sub,'sub')}</g>`;
}
export function boardDiagram(selected:Part){return `<svg xmlns="http://www.w3.org/2000/svg" id="protection-svg" viewBox="0 0 1200 700" role="img" aria-labelledby="board-title board-desc">
<title id="board-title">头侧裁判四芯保护板布局意向</title><desc id="board-desc">左侧四线输入，右侧四线输出到 SM11。正常电源经 Q1 和 U1 向右供电，GND 向左回流；CAN L 与 H 分别经 U2 TMUX7462F 的 S1/D1 和 S2/D2 双向通信，S 端接外部触点，D 端接测速。布局与路径为功能示意，芯片和封装未全部定型。</desc>
<defs>${[['power','#bd4b45'],['return','#876345'],['can','#39877c']].map(([id,c])=>`<marker id="arrow-${id}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10Z" fill="${c}"/></marker>`).join('')}</defs>
<rect class="canvas" width="1200" height="700"/>
<rect class="pcb" x="210" y="50" width="780" height="585" rx="18"/>
${[[230,90],[970,90],[230,615],[970,615]].map(([x,y])=>`<circle class="mount" cx="${x}" cy="${y}" r="7"/>`).join('')}
${text(260,105,'头侧独立保护板 · 元件面','board-name')}${text(260,130,'器件排布意向 / 板框与孔位待定','sub')}
${text(20,85,'四线 INPUT','heading')}${text(20,112,'来自头侧裁判触点','sub')}
${text(1020,85,'四线 OUTPUT','heading')}${text(1020,112,'接大测速 SM11','sub')}
${text(260,180,'电源区','zone')}${text(260,410,'裁判 CAN 区','zone')}
<path class="divider" d="M250 380H950"/>
<path class="power trace" d="M180 235H340 M480 235H550 M790 235H1020"/>
${['M280 235H325','M495 235H535','M830 235H900'].map(d=>`<path class="power flow" d="${d}" marker-end="url(#arrow-power)"/>`).join('')}
${text(810,205,'正常供电 →','power-label')}
<path class="return trace" d="M1020 345H180"/>
${['M910 345H840','M530 345H470','M325 345H275'].map(d=>`<path class="return flow" d="${d}" marker-end="url(#arrow-return)"/>`).join('')}
${text(480,370,'GND 回流 ← · 不借用动力地或框架','sub')}
<path class="control" d="M410 190V170H550 M550 155H520V210H550"/>
${text(445,185,'栅极控制','sub')}
${chip('Q1',340,190,140,110,'N-MOS','型号待定',selected)}
${chip('U1',550,190,240,110,'TPS26630 / 31','候选 · eFuse',selected)}
${chip('Q2',550,65,240,105,'小信号 MOS','栅极下拉 · 型号待定',selected)}
<rect class="passive" x="810" y="260" width="130" height="55" rx="4"/>${text(823,282,'R / C 配置区','label')}${text(823,303,'阈值 / 软启动','sub')}
<path class="control" d="M790 278H810"/>
${text(270,325,'Q1＋U1 内置 MOS：背靠背保护','sub')}
<path class="can trace" d="M180 465H520 M820 465H1020 M180 535H520 M820 535H1020"/>
${[465,535].flatMap(y=>['M325 '+y+'H465','M850 '+y+'H950']).map(d=>`<path class="can signal" d="${d}" marker-start="url(#arrow-can)" marker-end="url(#arrow-can)"/>`).join('')}
<g data-part="CAN" role="button" tabindex="0" aria-label="查看 U2 TMUX7462F" aria-pressed="${selected==='CAN'}" class="chip ${selected==='CAN'?'selected':''}">
<rect x="520" y="405" width="300" height="185" rx="7"/>
${text(536,432,'U2 · TMUX7462F','chip-title')}
${[[1,465],[2,535]].map(([channel,y])=>`<g data-channel="${channel}"><path class="can trace" d="M520 ${y}H820"/><circle class="switch-node" cx="625" cy="${y}" r="4"/><circle class="switch-node" cx="715" cy="${y}" r="4"/>${text(536,y-10,`S${channel}`,'ref')}${text(780,y-10,`D${channel}`,'ref')}${text(610,y+23,'正常导通 ↔','sub')}</g>`).join('')}
${text(536,578,'供电 / 阈值配置：待定','sub')}</g>
${text(315,435,'外部触点 → S 端','sub')}${text(840,435,'D 端 → SM11','sub')}
${pins.map(c=>[false,true].map(out=>{const x=out?1020:20,y=pinY[c.id];return `<g class="port" data-pin="${out?'out':'in'}-${c.id}"><rect x="${x}" y="${y-34}" width="160" height="68" rx="5"/><circle cx="${out?x:x+160}" cy="${y}" r="5" fill="${c.color}"/>${text(x+13,y-8,`${c.id} · ${c.name.replace('REF_','')}`,'port-title')}${text(x+13,y+18,`官方 ${c.official}`,'sub')}</g>`;}).join('')).join('')}
${text(260,610,'CAN 箭头表示通信方向；红 / 棕箭头表示正常供电与回流方向','sub')}
${text(20,670,'按电源 / 信号分区展开四线；R1–R4 沿用底座功能号，实际接头腔位另定。','label')}
</svg>`;}
