import { contacts } from '../dock/model.ts';
export const pins = ['R3','R1','R2','R4'].map(id=>contacts.find(c=>c.id===id)!);
export const parts = {
  U1:{title:'U1 · TPS26630 / TPS26631 候选',role:'电源保护核心',text:'采用 TPS2663 系列的可调过压关断路线，结合外置 MOS 实现反接保护，并设置限流与启动斜率。12 V 支路的关断阈值须按 SM11 允许输入范围设定，不使用默认高压阈值。',next:'下一步：确认具体子型号、封装、启动电流及保护阈值。',source:'https://www.ti.com/lit/ds/symlink/tps2663.pdf'},
  Q1:{title:'Q1 · 外置 N 沟道功率 MOS',role:'反接 / 反向电流阻断',text:'与 U1 内部 MOS 形成背靠背结构。正常供电电流经过 Q1；故障时由保护电路关断。Q1 的型号尚未选定。',next:'按故障耐压、导通损耗及瞬态工况选择，靠近 U1 放置。',source:'https://www.ti.com/lit/ds/symlink/tps2663.pdf'},
  Q2:{title:'Q2 · 小信号 MOS',role:'Q1 栅极快速下拉',text:'按 TPS2663 参考电路连接 BGATE、DRV 与 IN_SYS，帮助 Q1 在反接或反向电流故障时快速关断。它不串在测速的主供电路径里。',next:'具体型号与栅极控制走线按 U1 参考电路确定。',source:'https://www.ti.com/lit/ds/symlink/tps2663.pdf'},
  CAN:{title:'U2 · TMUX7462F',role:'已选定 · 裁判 CAN 双线误接保护',text:'使用四通道保护器中的两路：R2（CAN_L）接 S1，D1 接 SM11 CAN_L；R4（CAN_H）接 S2，D2 接 SM11 CAN_H。S 端朝外部触点，D 端朝测速，正常信号可双向通过。每路检测到越过故障阈值的电压时自动断开；DR 置高，选择故障时 D 端高阻。另两路不接入本次信号路径。',next:'下一步：确定封装、VDD/VSS 供电和 VFP/VFN 故障阈值，核对正常 CAN 共模范围、串联压降、掉电与故障恢复，再做 S145 全部误接组合测试。±60 V 是器件 S 端故障耐受，不是正常通信范围。',source:'https://www.ti.com/lit/ds/symlink/tmux7462f.pdf'},
} as const;
export type Part = keyof typeof parts;
export function isPart(value:string|null):value is Part {return value!==null&&Object.hasOwn(parts,value);}
export const pinY:Record<string,number>={R3:235,R1:345,R2:465,R4:535};
