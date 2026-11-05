import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Simulation, packing, cyclePose } from '../src/state.ts';
test('10/12格排布满足49 mm中心距，容纳46 mm孔', () => {
  for (const n of [10, 12]) {
    const p = packing(n);
    assert.ok(Math.abs(2 * p.radius * Math.sin(Math.PI / n) - 49) < 1e-8);
    assert.ok(p.pocketDiameter > p.ballDiameter);
  }
  assert.ok(Math.abs(packing(12).diameter - 243.32146) < .001);
});
test('未接通、未就绪及分解时禁止开始供弹', () => {
  const s = new Simulation();
  for (let i = 0; i < 4; i++) { s.setPhase(i); assert.equal(s.start(), false); }
  s.setPhase(4); s.setExplode(.5); assert.equal(s.start(), false);
  s.setExplode(0); assert.equal(s.start(), true); assert.equal(s.start(), false);
});
test('推头退净、闸门关闭后才分度', () => {
  for (let t = 0; t <= 5; t += .01) {
    const p = cyclePose(t);
    if (p.index > 0) { assert.equal(p.push, 0); assert.equal(p.gate, 0); assert.equal(p.ballOut, true); }
  }
});
test('出球只扣一次库存，退杆完成再进入下一格', () => {
  const s = new Simulation(); s.start(); s.tick(2.34);
  assert.equal(s.fired, 0); assert.equal(s.indexTurns, 0);
  s.tick(.02); assert.equal(s.fired, 1); assert.equal(s.indexTurns, 0);
  s.tick(1); assert.equal(s.fired, 1);
  s.tick(2); assert.equal(s.running, false); assert.equal(s.fired, 1); assert.equal(s.indexTurns, 1);
});
test('10发与12发连续演示均打空并停止，不出现负库存', () => {
  for (const n of [10, 12] as const) {
    const s = new Simulation(); s.setCapacity(n); assert.equal(s.start(true), true);
    for (let i = 0; i < n; i++) s.tick(5);
    assert.equal(s.fired, n); assert.equal(s.remaining, 0); assert.equal(s.playing, false); assert.equal(s.start(), false);
    s.tick(20); assert.equal(s.fired, n);
    s.refill(); assert.equal(s.remaining, n); assert.equal(s.start(), true);
  }
});
test('暂停、继续、容量切换及落座状态切换同步清理动作', () => {
  const s = new Simulation(); s.start(true); s.tick(1); s.pause(); const time = s.time;
  s.tick(1); assert.equal(s.time, time); s.resume(); s.tick(1); assert.ok(s.time > time);
  s.setCapacity(10); assert.equal(s.running, false); assert.equal(s.playing, false); assert.equal(s.fired, 0);
  s.start(true); s.tick(2.4); assert.equal(s.fired, 1);
  s.setPhase(1); assert.equal(s.running, false); assert.equal(s.indexTurns, 1); assert.equal(s.start(), false);
});
test('装填口逐格装退弹：开盖可点动，关盖不装弹，处理结束才修改库存', () => {
  for (const n of [10, 12] as const) {
    const s = new Simulation(); s.setCapacity(n); s.setLoading(true); s.emptyExample();
    assert.equal(s.remaining, 0); assert.equal(s.loadingSlot, n / 2);
    assert.equal(s.handle('insert'), false); s.toggleHatch();
    assert.equal(s.start(), false);
    assert.equal(s.setLoading(false), false);
    assert.equal(s.handle('insert'), true); s.tick(.4); assert.equal(s.remaining, 0);
    assert.equal(s.toggleHatch(), false); assert.equal(s.emptyExample(), false); assert.equal(s.handle('index'), false);
    s.tick(.5); assert.equal(s.remaining, 1); assert.equal(s.fired, 0);
    assert.equal(s.handle('insert'), false);
    assert.equal(s.handle('remove'), true); s.tick(1); assert.equal(s.remaining, 0); assert.equal(s.fired, 0);
    assert.equal(s.hatchOpen, true); assert.equal(s.handle('index'), true); s.tick(.4);
    assert.ok(s.indexTurns > 0 && s.indexTurns < 1); assert.equal(s.toggleHatch(), false);
    s.tick(.5); assert.equal(s.loadingSlot, n / 2 + 1);
    assert.equal(s.hatchOpen, true); assert.equal(s.handling, null); s.tick(10); assert.equal(s.loadingSlot, n / 2 + 1);
    s.toggleHatch(); assert.equal(s.handle('index'), true); s.tick(1); assert.equal(s.hatchOpen, false);
  }
});
test('逐格装满10/12格后可连续打空；部分装填越过空格但不虚增发数', () => {
  for (const n of [10, 12] as const) for (const count of [2, n]) {
    const s = new Simulation(); s.setCapacity(n); s.setLoading(true); s.emptyExample();
    s.toggleHatch();
    for (let i = 0; i < count; i++) {
      s.handle('insert'); s.tick(1); s.handle('index'); s.tick(1);
      assert.equal(s.hatchOpen, true);
    }
    assert.equal(s.setLoading(false), false); s.toggleHatch();
    assert.equal(s.remaining, count); assert.equal(s.fired, 0);
    assert.equal(s.setLoading(false), true); assert.equal(s.start(true), true);
    for (let i = 0; i < n * 3; i++) {
      if (s.seeking) { assert.equal(s.pose.push, 0); assert.equal(s.pose.gate, 0); assert.equal(s.feedBallVisible, false); }
      s.tick(5);
    }
    assert.equal(s.remaining, 0); assert.equal(s.fired, count); assert.equal(s.running, false);
  }
});
test('容量切换在装填模式使用空仓，保留普通供弹模式的满仓示例契约', () => {
  const s = new Simulation(); s.setLoading(true); s.setCapacity(10);
  assert.equal(s.remaining, 0); assert.equal(s.slots.length, 10); assert.equal(s.hatchOpen, false);
  s.setLoading(false); s.setCapacity(12); assert.equal(s.remaining, 12);
});
test('部分装填的单发命令只越过空格，不变成连续发射', () => {
  const s = new Simulation(); s.setLoading(true); s.emptyExample();
  s.toggleHatch();
  for (let i = 0; i < 2; i++) {
    s.handle('insert'); s.tick(1); s.handle('index'); s.tick(1);
  }
  s.toggleHatch();
  s.setLoading(false); s.start();
  for (let i = 0; i < 24; i++) s.tick(5);
  assert.equal(s.fired, 1); assert.equal(s.remaining, 1); assert.equal(s.running, false);
});
