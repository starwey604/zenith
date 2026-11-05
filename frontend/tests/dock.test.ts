import { test } from 'node:test';
import assert from 'node:assert/strict';
import { contacts, capture, dockPose, defaults, wireBudget, contactDiagram } from '../src/dock/model.ts';
test('12项功能分区与裁判四芯映射保持独立',()=>{
  assert.equal(contacts.length,12);assert.equal(new Set(contacts.map(c=>c.id)).size,12);
  assert.deepEqual(contacts.filter(c=>c.circuit==='REF').map(c=>[c.id,c.name,c.official?.split(' · ')[0]]),[['R1','REF_GND','1'],['R2','REF_CAN_L','2'],['R3','REF_12V','3'],['R4','REF_CAN_H','4']]);
  assert.equal(contacts.filter(c=>c.circuit==='CTRL').length,2);
});
test('偏航与平移共同消耗入口余量，入口外不强行落座',()=>{
  assert.equal(capture({dx:6,dy:4,yaw:2}).inside,true);
  const a={dx:18,dy:0,yaw:0};assert.equal(capture(a).inside,false);
  const p=dockPose(5,a,true);assert.equal(p.p,0);assert.equal(p.fire,false);assert.equal(p.lift,70);
  assert.ok(capture({dx:0,dy:0,yaw:8}).yMargin<capture({dx:0,dy:0,yaw:0}).yMargin);
});
test('落座接触、锁紧、辅助上电、Ammo许可顺序',()=>{
  const a={dx:0,dy:0,yaw:0};
  for(let t=0;t<5;t+=.05){const p=dockPose(t,a,true);assert.equal(p.fire,false);if(t<2){assert.equal(p.present,false);assert.equal(p.locked,false);}if(t<4)assert.equal(p.aux,false);assert.ok(p.compression>=0&&p.compression<=2);}
  assert.equal(dockPose(2,a,true).present,true);assert.equal(dockPose(2,a,true).locked,false);
  assert.equal(dockPose(5,a,false).fire,false);assert.equal(dockPose(5,a,true).fire,true);
  assert.equal(dockPose(5,a,true).sleeve,12);
});
test('焊尾、热缩、中心线弯曲与净空分别累计',()=>{
  const b=wireBudget(defaults);assert.equal(b.straight,20);assert.equal(b.radius,16);assert.equal(b.depth,41);assert.equal(b.side,21);
  assert.ok(wireBudget({...defaults,powerOD:6}).depth>b.depth);
  assert.ok(wireBudget({...defaults,sleeve:20}).depth>b.depth);
});
test('头车接触面镜像不更改功能编号',()=>{
  for(const c of contacts){const a=contactDiagram(c,false),b=contactDiagram(c,true);assert.equal(a.x+b.x,320);assert.equal(a.y,b.y);}
});
