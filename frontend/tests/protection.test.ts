import {test} from 'node:test';
import assert from 'node:assert/strict';
import {pins,parts,isPart,pinY} from '../src/protection/model.ts';
test('保护板沿用四芯功能号与官方线序，不增加检测触点',()=>{
 assert.deepEqual(pins.map(p=>p.id).sort(),['R1','R2','R3','R4']);
 assert.deepEqual(pins.map(p=>p.official?.split(' · ')[0]),['3','1','2','4']);
 assert.equal(new Set(pins.map(p=>pinY[p.id])).size,4);
});
test('区分候选电源器件和已选CAN保护器',()=>{
 assert.match(parts.U1.title,/TPS26630/);assert.match(parts.U1.title,/候选/);
 assert.match(parts.CAN.title,/TMUX7462F/);assert.match(parts.CAN.text,/S1/);assert.match(parts.CAN.text,/DR 置高/);assert.match(parts.CAN.next,/VFP\/VFN/);assert.match(parts.Q2.text,/不串/);
 assert.equal(isPart('CAN'),true);assert.equal(isPart('constructor'),false);assert.equal(isPart('<script>'),false);
});
