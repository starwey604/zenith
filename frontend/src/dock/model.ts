export type Mode = 'mechanical' | 'contacts' | 'harness';
export type Circuit = 'FIRE' | 'AUX' | 'REF' | 'CTRL' | 'PRESENT';
export interface Contact { id: string; name: string; circuit: Circuit; x: number; y: number; color: string; vehicle: string; head: string; note: string; official?: string }
export const circuitColors: Record<Circuit,string> = { FIRE: '#bb5251', AUX: '#c08227', REF: '#34877b', CTRL: '#397fb1', PRESENT: '#8b6ca8' };
export const contacts: Contact[] = [
  { id:'F1',name:'FIRE+',circuit:'FIRE',x:-42,y:91,color:'#bc4444',vehicle:'Ammo-Booster → 发射支路保护 / 开关',head:'两块 C620 电源正',note:'24 V 级意向；独立功率触点。电流、触点温升与导体截面待定。' },
  { id:'F2',name:'FIRE_RETURN',circuit:'FIRE',x:-42,y:109,color:'#584a4a',vehicle:'发射电源回路',head:'两块 C620 电源回路',note:'与 F1 成对走线，不以承力框架或 REF_GND 作为回流。' },
  { id:'A1',name:'AUX+',circuit:'AUX',x:-24,y:91,color:'#c08028',vehicle:'辅助电源 → 独立保护支路',head:'头侧 DC/DC → LBC3 与相机',note:'电压按最终架构；不默认跨接口远送大电流 5 V。' },
  { id:'A2',name:'AUX_RETURN',circuit:'AUX',x:-24,y:109,color:'#746143',vehicle:'辅助电源回路',head:'电脑辅助电源回路',note:'与 A1 成对布线；与 FIRE / REF 的连接关系在原理图中确定。' },
  { id:'R1',name:'REF_GND',circuit:'REF',x:3,y:91,color:'#8e6145',official:'1 · 棕 · GND',vehicle:'车侧裁判保护段回流',head:'头侧裁判保护 → SM11 GND',note:'不得随意并到动力地、电脑地或安装金属。' },
  { id:'R2',name:'REF_CAN_L',circuit:'REF',x:15,y:91,color:'#d78335',official:'2 · 橙 · CAN_L',vehicle:'车侧裁判故障隔离段 CAN_L',head:'头侧总线保护 → SM11 CAN_L',note:'与 R4 构成裁判 CAN 双绞对；焊尾尽量短。' },
  { id:'R3',name:'REF_12V',circuit:'REF',x:27,y:91,color:'#c54b4b',official:'3 · 红 · 12 V',vehicle:'裁判独立受保护 12 V 支路',head:'反接 / 过压保护 → SM11 12 V',note:'需覆盖 S145 持续误接；TVS 或保险丝不能单独完成全部保护。' },
  { id:'R4',name:'REF_CAN_H',circuit:'REF',x:39,y:91,color:'#c4a42e',official:'4 · 黄 · CAN_H',vehicle:'车侧裁判故障隔离段 CAN_H',head:'头侧总线保护 → SM11 CAN_H',note:'与 R2 双绞；这是裁判 CAN，不与自有 CTRL_CAN 直接合并。' },
  { id:'C1',name:'CTRL_CAN_H',circuit:'CTRL',x:3,y:109,color:'#438bbb',vehicle:'自有控制 CAN_H',head:'电脑 / 电调控制链路 CAN_H',note:'与 C2 双绞；跨供电域的隔离及参考地尚待电气定义。' },
  { id:'C2',name:'CTRL_CAN_L',circuit:'CTRL',x:15,y:109,color:'#345577',vehicle:'自有控制 CAN_L',head:'电脑 / 电调控制链路 CAN_L',note:'本页保留 C0 备用参考地空间，不默认总线只用两根线就够。' },
  { id:'D1',name:'PRESENT_LOOP_A',circuit:'PRESENT',x:27,y:109,color:'#9266ac',vehicle:'受保护低能量检测源',head:'无源短接片 / 识别电阻一端',note:'设计为最后接通、最先断开；不依赖电脑启动。' },
  { id:'D2',name:'PRESENT_LOOP_B',circuit:'PRESENT',x:39,y:109,color:'#66507e',vehicle:'在位检测返回',head:'无源短接片 / 识别电阻另一端',note:'在位环路不等于机械锁到位；锁紧传感器留在车侧。' },
];
export const layout = {
  headHalfX:74,headHalfY:58,mouthHalfX:88,mouthHalfY:72,
  throatHalfX:76,throatHalfY:60,guideTop:62,guideBottom:28,
  supportZ:20,pinPitch:90,pinDiameter:8,receiverDiameter:8.2,
  floatingTravel:.8,compression:2,headContactZ:26,vehicleTailZ:10,headTailZ:44,
  boxX:108,boxY:42,
};
export interface Alignment { dx:number; dy:number; yaw:number }
export function capture(a:Alignment) {
  const r=a.yaw*Math.PI/180;
  const x=Math.abs(a.dx)+layout.headHalfX*Math.abs(Math.cos(r))+layout.headHalfY*Math.abs(Math.sin(r));
  const y=Math.abs(a.dy)+layout.headHalfX*Math.abs(Math.sin(r))+layout.headHalfY*Math.abs(Math.cos(r));
  return { xMargin:layout.mouthHalfX-x,yMargin:layout.mouthHalfY-y,inside:x<=layout.mouthHalfX&&y<=layout.mouthHalfY };
}
export const stages = [
  {title:'入口对准',note:'先用喇叭口接住位置误差。下方检查只判断平面投影是否进入口部，不保证摩擦条件下能自行滑正。'},
  {title:'粗导向',note:'斜面逐步收拢位置；腕部需要限力 / 顺应。动画按可顺应条件演示，不能让刚性位置控制硬压进去。'},
  {title:'精定位落座',note:'圆销约束 X/Y，菱形销约束偏航；三处承压面定义高度与倾角。导向口此时退让，触点压缩不承重。'},
  {title:'独立拉紧',note:'双侧拉钩把底框压向三处承压面。锁到位单独检测；保持机构需断电不释放，不能仅靠电机堵转。'},
  {title:'辅助上电',note:'落座、锁到位、PRESENT 稳定后，才接通受保护的 AUX / REF 支路。图中反馈均为流程假设。'},
  {title:'接通弹路',note:'弹路套独立伸出。Ammo-Booster 允许且所有条件满足时，才许可 FIRE；轮速就绪后才能推球。'},
];
export function dockPose(progress:number,a:Alignment,ammo:boolean) {
  const valid=capture(a).inside;
  const p=valid?Math.max(0,Math.min(5,progress)):0;
  const lift=p<1?70-42*p:p<2?28*(2-p):0;
  const residual=p<2?Math.pow(1-p/2,2):0;
  const seated=p>=2,locked=p>=3,present=seated,aux=p>=4&&locked&&present,sleeve=Math.max(0,Math.min(1,p-4))*12;
  return {p,lift,dx:a.dx*residual,dy:a.dy*residual,yaw:a.yaw*residual,compression:Math.max(0,2-lift),locked,present,seated,aux,fire:p>=5&&aux&&ammo,sleeve,lock:Math.max(0,Math.min(1,p-2))};
}
export interface Harness { powerOD:number; signalOD:number; solder:number; sleeve:number; radiusFactor:number; clearance:number }
export const defaults:Harness={powerOD:4,signalOD:1.5,solder:8,sleeve:12,radiusFactor:4,clearance:3};
export function wireBudget(h:Harness,od=h.powerOD) {
  // Disjoint reserved segments: solder tail, insulated straight, quarter-circle centerline, clearance.
  const straight=h.solder+h.sleeve,radius=h.radiusFactor*od;
  return { straight,radius,depth:straight+radius+od/2+h.clearance,side:radius+od/2+h.clearance,arc:Math.PI*radius/2 };
}
export function contactDiagram(c:Pick<Contact,'x'|'y'>,headView:boolean) {
  return {x:160+(headView?-c.x:c.x)*2.2,y:96-(c.y-100)*2.2};
}
