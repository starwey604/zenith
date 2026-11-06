import {test} from 'node:test';
import assert from 'node:assert/strict';
import {contacts as dockContacts} from '../src/dock/model.ts';
import {contacts,routeContacts,exportCsv,isSelection,routes} from '../src/wiring/model.ts';
import {readFileSync} from 'node:fs';
test('接线与底座共享触点：Mini PC直达顶板，LBC3隔开两段CAN',()=>{
 assert.equal(contacts,dockContacts);
 assert.deepEqual(routeContacts('AUX').map(c=>[c.id,c.name,c.x,c.y]),[['A1','MINIPC_24V',-24,91],['A2','MINIPC_RETURN',-24,109]]);
 assert.match(contacts.find(c=>c.id==='A1')!.head,/LBC3 顶板 24 V 输入/);
 assert.match(contacts.find(c=>c.id==='F1')!.head,/动力分电＋CAN 分线板/);
 assert.equal(routeContacts('REF').length,4);assert.equal(contacts.length,10);
 assert.match(routes.CTRL.wires,/收发器集成在顶板上/);assert.match(routes.CTRL.assembly,/两路独立 CAN 控制器及收发器/);assert.match(contacts.find(c=>c.id==='C1')!.head,/LBC3 顶板 CAN A · H/);assert.match(routes.FIRE.assembly,/车载/);
});
test('导出保留10项，静态机械表与前端名称一致',()=>{
 const csv=exportCsv();assert.equal(csv.split('\r\n').length,11);assert.match(csv,/MINIPC_24V/);assert.doesNotMatch(csv,/AUX\+/);
 const mechanical=readFileSync(new URL('../../mechanical/hero_head/vehicle_feed/contact_functions.csv',import.meta.url),'utf8');
 for(const c of contacts)assert.ok(mechanical.includes(`"${c.id}","${c.name}"`));
 assert.doesNotMatch(csv,/PRESENT|D1|D2/);assert.doesNotMatch(mechanical,/PRESENT|D1|D2/);
 assert.equal(isSelection('PRESENT'),false);assert.equal(isSelection('all'),true);assert.equal(isSelection('AUX'),true);assert.equal(isSelection('<script>'),false);
});
