import { contacts, circuitLabels, circuitColors, type Circuit } from '../dock/model.ts';
export { contacts, circuitLabels, circuitColors };
export type Selection = 'all' | Circuit;
export const circuitOrder: Circuit[] = ['FIRE','AUX','REF','CTRL'];
export interface Route { title:string; path:string; wires:string; assembly:string; y:number; height:number }
export const routes: Record<Circuit,Route> = {
  FIRE:{title:'电源与 CAN 共用一块分配板',path:'Ammo-Booster → F1/F2 → 动力分电＋CAN 分线板 → 两块 C620 → 两个 M3508',wires:'入口及每路电调电源：正、回流各一根。电调至电机：三相线＋传感器线。',assembly:'两路 C620 电源分别成对布线，端子附近固定；不经过电脑顶板。车载分度、推送、止弹执行器也受 Ammo-Booster 断电控制，不穿头部触点。',y:70,height:410},
  AUX:{title:'Mini PC 24 V 直达顶板',path:'Mini PC 接口 → A1/A2 → LBC3 顶板 24 V 输入 → LBC3 / 相机',wires:'跨底座只有 24 V 正与回流两根。相机经 CAM1 转接板与 MIPI 排线接入，全部留在头内。',assembly:'电脑支路保护和降压由顶板承担，不另画外置模块；A1/A2 不接动力分电板。给顶板插头留拔插空间，MIPI 两端设线夹。',y:480,height:190},
  REF:{title:'四芯裁判线有自己的保护路径',path:'车内裁判链路 → 车侧故障保护 → R1–R4 → 头侧四线保护 → 大测速 SM11',wires:'R1 棕 GND；R2 橙 CAN_L；R3 红 12 V；R4 黄 CAN_H。R2/R4 双绞。',assembly:'保留可访问的标准四芯测试接口，与盲插端共用保护路径。车侧故障切离与头侧任意两针 ≤30 V 误接保护均须实现；REF_GND 不并到动力或电脑回流。',y:670,height:180},
  CTRL:{title:'LBC3 分开车侧与电机两条 CAN',path:'车侧控制 CAN → C1/C2 → LBC3 CAN A；LBC3 CAN B → 动力分电＋CAN 分线板 → 左 / 右 C620',wires:'C1 CAN_H、C2 CAN_L 双绞，直达 LBC3 顶板 CAN A。独立 CAN B 另用一对 H/L 接分电板，收发器集成在顶板上；参考地或隔离随原理图确定，C0 仍为未接线预留。',assembly:'A/B 需两路独立 CAN 控制器及收发器，由 LBC3 软件处理命令与反馈；不是同一总线的两个插座。CAN A 为底盘—LBC3 点对点；CAN B 在分电板上分给两块 C620，走线沿主干、控制短支线，每段总线只在物理两端终端匹配。LBC3 电源仍来自 Mini PC。',y:70,height:410},
};
export function isSelection(value:string|null):value is Selection { return value==='all'||circuitOrder.includes(value as Circuit); }
export function routeContacts(circuit:Circuit){return contacts.filter(c=>c.circuit===circuit);}
export function exportCsv(){
 const rows=[['逻辑号_非腔位号','功能','分区','车侧来源','头侧去向','官方四芯对应','说明'],...contacts.map(c=>[c.id,c.name,circuitLabels[c.circuit],c.vehicle,c.head,c.official??'',c.note])];
 return '\uFEFF'+rows.map(row=>row.map(s=>'"'+s.replaceAll('"','""')+'"').join(',')).join('\r\n');
}
