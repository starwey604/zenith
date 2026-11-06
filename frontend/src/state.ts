export type Mode = 'assembly' | 'loading' | 'feed' | 'dock' | 'vision';
export type View = 'iso' | 'side' | 'front' | 'top' | 'rear';
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
  slots: boolean[] = Array(12).fill(true);
  loading = false;
  hatchOpen = false;
  handling: 'insert' | 'remove' | 'index' | null = null;
  handlingTime = 0;
  private step = 0;
  private shotCounted = false;
  seeking = false;
  private mod(n: number) { return ((n % this.capacity) + this.capacity) % this.capacity; }
  get running() { return this.time > 0; }
  get busy() { return this.running || this.handling !== null; }
  get remaining() { return this.slots.slice(0, this.capacity).filter(Boolean).length; }
  get ready() { return this.phase === 4 && this.remaining > 0 && this.explode === 0 && !this.loading && !this.hatchOpen; }
  get pose() { return this.seeking ? { segment: 5, push: 0, gate: 0, exit: 0, index: clamp(this.time / .85), ballOut: true } : cyclePose(this.time); }
  get handlingProgress() { return clamp(this.handlingTime / .85); }
  get indexTurns() { return this.step + (this.handling === 'index' ? this.handlingProgress : this.running ? this.pose.index : 0); }
  get activeSlot() { return this.mod(this.step); }
  get loadingSlot() { return this.mod(this.step + this.capacity / 2); }
  get feedBallVisible() { return this.running && !this.seeking && !this.pose.ballOut; }
  setPhase(phase: number) {
    if (this.loading) return;
    this.cancelCycle(); this.phase = Math.max(0, Math.min(4, Math.round(phase)));
    this.explode = 0; this.pitch = 0;
  }
  setCapacity(n: 10 | 12) {
    this.cancelCycle(); this.capacity = n; this.resetInventory(!this.loading);
  }
  // Kept for callers that explicitly request a fully loaded simulation fixture.
  refill() { this.cancelCycle(); this.resetInventory(true); }
  private resetInventory(full: boolean) {
    this.slots = Array(this.capacity).fill(full); this.fired = 0; this.step = 0;
    this.hatchOpen = false; this.handling = null; this.handlingTime = 0;
  }
  emptyExample() { if (!this.loading || this.busy) return false; this.resetInventory(false); return true; }
  setLoading(enabled: boolean) {
    if (this.handling || (!enabled && this.hatchOpen)) return false;
    this.cancelCycle(); this.loading = enabled;
    if (enabled) { this.pitch = 0; this.explode = 0; }
    return true;
  }
  toggleHatch() {
    if (!this.loading || this.busy) return false;
    this.hatchOpen = !this.hatchOpen; return true;
  }
  handle(action: 'insert' | 'remove' | 'index') {
    if (!this.loading || this.busy) return false;
    if (action !== 'index' && !this.hatchOpen) return false;
    if (action === 'insert' && this.slots[this.loadingSlot]) return false;
    if (action === 'remove' && !this.slots[this.loadingSlot]) return false;
    this.handling = action; this.handlingTime = 0; return true;
  }
  private cancelCycle() {
    // Finish the indexed position only when the ball has already left.
    if (this.running && this.shotCounted) this.step++;
    this.time = 0; this.playing = false; this.continuous = false; this.seeking = false;
  }
  setExplode(value: number) { if (this.loading) return; this.cancelCycle(); this.explode = clamp(value); }
  start(continuous = false) {
    if (!this.ready || this.busy) return false;
    this.seeking = !this.slots[this.activeSlot]; this.shotCounted = false;
    this.time = .00001; this.playing = true; this.continuous = continuous; return true;
  }
  pause() { this.playing = false; }
  resume() { if (this.running) this.playing = true; }
  tick(dt: number) {
    if (this.handling) {
      this.handlingTime = Math.min(.85, this.handlingTime + Math.max(0, dt));
      if (this.handlingTime >= .85) {
        if (this.handling === 'index') this.step++;
        else this.slots[this.loadingSlot] = this.handling === 'insert';
        this.handling = null; this.handlingTime = 0;
      }
      return;
    }
    if (!this.playing || !this.running) return;
    const duration = this.seeking ? .85 : cycleDuration;
    this.time = Math.min(duration, this.time + Math.max(0, dt));
    if (!this.seeking && this.pose.ballOut && !this.shotCounted) {
      this.slots[this.activeSlot] = false; this.fired++; this.shotCounted = true;
    }
    if (this.time >= duration) {
      const again = (this.seeking || this.continuous) && this.remaining > 0;
      const continuous = this.continuous;
      this.step++; this.time = 0; this.playing = false; this.continuous = false; this.seeking = false;
      if (again) this.start(continuous);
    }
  }
}
