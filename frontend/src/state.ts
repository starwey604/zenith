export type Mode = 'assembly' | 'feed' | 'dock' | 'vision';
export type View = 'iso' | 'side' | 'front' | 'top';
export type Layer = 'launcher' | 'vision' | 'magazine' | 'drive' | 'dock' | 'support';
export const phases = [
  { title: '垂直落头', text: '头部底座向下落座。车侧弹路套缩回，不横挡下降通道；夹爪由侧耳承载。' },
  { title: '定位落座', text: '三个承压面落稳，定位键限制平移与转动。触点盒受护边保护，不承担头部重量。' },
  { title: '独立锁紧', text: '车侧锁钩拉紧头下被动销。定位与承载交给底座，随后夹爪才能退出。' },
  { title: '伸套接通', text: '车侧套管沿炮口轴线伸出12 mm，接入头后短导路。接缝对中后才允许开门。' },
  { title: '允许供弹', text: '锁紧、弹路接通与轮组就绪后，单格直推。推头退净、闸门关闭后再分度。' },
] as const;
export const cycleDuration = 5;
export const cycleNames = ['开止弹门', '直推入轮', '轮组接管', '推头退净', '关闭止弹门', '弹盘分度'] as const;
export function packing(capacity: number) {
  const radius = 49 / (2 * Math.sin(Math.PI / capacity));
  return { radius, diameter: 2 * (radius + 27), ballDiameter: 42.5, pocketDiameter: 46, diskThickness: 50 };
}
const clamp = (x: number) => Math.min(1, Math.max(0, x));
export function cyclePose(t: number) {
  const segment = t < .45 ? 0 : t < 1.9 ? 1 : t < 2.35 ? 2 : t < 3.75 ? 3 : t < 4.15 ? 4 : 5;
  const push = t < .45 ? 0 : t < 1.9 ? clamp((t - .45) / 1.45) : t < 2.35 ? 1 : 1 - clamp((t - 2.35) / 1.4);
  const gate = t < .45 ? clamp(t / .45) : t < 3.75 ? 1 : 1 - clamp((t - 3.75) / .4);
  return { segment, push, gate, exit: clamp((t - 1.9) / .45), index: clamp((t - 4.15) / .85), ballOut: t >= 2.35 };
}
export class Simulation {
  capacity: 10 | 12 = 12;
  phase = 4;
  fired = 0;
  pitch = 0;
  explode = 0;
  playing = false;
  continuous = false;
  time = 0;
  private baseFired = 0;
  get running() { return this.time > 0; }
  get remaining() { return this.capacity - this.fired; }
  get ready() { return this.phase === 4 && this.remaining > 0 && this.explode === 0; }
  get pose() { return cyclePose(this.time); }
  get indexTurns() { return this.running ? this.baseFired + this.pose.index : this.fired; }
  get activeSlot() { return this.running ? this.baseFired : this.fired; }
  get feedBallVisible() { return this.running && !this.pose.ballOut; }
  setPhase(phase: number) {
    this.cancelCycle(); this.phase = Math.max(0, Math.min(4, Math.round(phase)));
    this.explode = 0; this.pitch = 0;
  }
  setCapacity(n: 10 | 12) { this.cancelCycle(); this.capacity = n; this.fired = 0; }
  refill() { this.cancelCycle(); this.fired = 0; }
  private cancelCycle() { this.time = 0; this.playing = false; this.continuous = false; }
  setExplode(value: number) { this.cancelCycle(); this.explode = clamp(value); }
  start(continuous = false) {
    if (!this.ready || this.running) return false;
    this.baseFired = this.fired; this.time = .00001; this.playing = true; this.continuous = continuous; return true;
  }
  pause() { this.playing = false; }
  resume() { if (this.running) this.playing = true; }
  tick(dt: number) {
    if (!this.playing || !this.running) return;
    this.time = Math.min(cycleDuration, this.time + Math.max(0, dt));
    if (this.pose.ballOut) this.fired = this.baseFired + 1;
    if (this.time >= cycleDuration) {
      const again = this.continuous && this.remaining > 0;
      this.time = 0; this.playing = false; this.continuous = false;
      if (again) this.start(true);
    }
  }
}
