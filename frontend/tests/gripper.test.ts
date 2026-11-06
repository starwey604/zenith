import { test } from 'node:test';
import assert from 'node:assert/strict';
import { poseAt, budget } from '../src/gripper/model.ts';
test('夹头接近后闭合，落座后张开，最后退爪', () => {
  assert.equal(poseAt('head', .5).tool[1], 0);
  assert.equal(poseAt('head', .5).gap, 112);
  assert.equal(poseAt('head', 1).gap, 80);
  assert.deepEqual(poseAt('head', 2).tool, poseAt('head', 2).object);
  assert.equal(poseAt('head', 3.5).gap, 112);
  assert.equal(poseAt('head', 3.5).tool[1], 0);
  assert.equal(poseAt('head', 4).object[1], 0);
  assert.equal(poseAt('head', 4).tool[1], 100);
});
test('取矿先轴向拔出；存矿先卸载再松爪', () => {
  assert.equal(poseAt('ore', 1).gap, 65);
  assert.equal(poseAt('ore', 3).object[2], 120);
  assert.equal(poseAt('ore', 3).object[1], 0);
  assert.equal(poseAt('store', 2).object[1], 0);
  assert.equal(poseAt('store', 2).gap, 65);
  assert.equal(poseAt('store', 3).gap, 112);
  assert.deepEqual(poseAt('store', 3).object, poseAt('store', 4).object);
});
test('初步力预算保留每指和总负载口径', () => {
  const b = budget(2.5, 50, .5);
  assert.ok(Math.abs(b.perJaw - 64.05) < 1e-9);
  assert.ok(Math.abs(b.moment - 3.2025) < 1e-9);
  assert.equal(b.payload, 2.95);
  assert.ok(budget(2.5, 50, .3).perJaw > b.perJaw);
});
