import {chromium} from '@playwright/test';
import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';

const published=JSON.parse(await readFile(new URL('../pick_place_study/study.json',import.meta.url)));
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader']});
const page=await browser.newPage({viewport:{width:1440,height:1080}}),errors=[],failed=[];
page.on('pageerror',e=>errors.push(e.message));page.on('response',r=>{if(r.status()>=400)failed.push(r.url());});
await page.goto('http://127.0.0.1:8773/mechanical/hero_head/magazine_study/pick-place.html');
await page.waitForFunction(()=>window.__pickPlace?.ready);await page.waitForTimeout(200);
assert.deepEqual(published.candidates.map(c=>c.id),['axial5']);
assert.equal(await page.locator('#comparison-body tr').count(),1);
for(const c of published.candidates){
 const actual=await page.evaluate(()=>({mass:window.__pickPlace.metrics(),bounds:window.__pickPlace.geometryBounds(),state:window.__pickPlace.state}));
 assert.equal(actual.state.id,c.id);assert.ok(Math.abs(actual.mass.total-c.metrics.module_mass_kg)<1e-10);
 for(let k=0;k<3;k++){assert.ok(actual.bounds[k]<=c.metrics.size_mm[k]+.02,`${c.id} actual mesh exceeds dimension ${k}`);assert.ok(actual.bounds[k]>c.metrics.size_mm[k]-2,`${c.id} missing geometry in dimension ${k}`);assert.ok(Math.abs(actual.mass.cg[k]-c.metrics.cg_mm[k])<1e-9);}
 assert.ok(c.metrics.pocket_center_spacing_mm>=published.config.ball_max_diameter_mm);
}
const initial=await page.locator('#size-value').textContent();const before=await page.evaluate(()=>window.__pickPlace.metrics().total);
await page.selectOption('#ammo','3');assert.equal(await page.locator('#size-value').textContent(),initial);
assert.ok(Math.abs(before-await page.evaluate(()=>window.__pickPlace.metrics().total)-.089)<1e-10);
await page.locator('#core-mass').fill('1350');assert.ok(Math.abs(await page.evaluate(()=>window.__pickPlace.metrics().total)-(before-.089+.15))<1e-10);
await page.locator('#core-mass').fill('1200');await page.selectOption('#ammo','5');
await page.locator('[data-mode="transfer"]').click();
const frames=await page.evaluate(()=>Array.from({length:1001},(_,i)=>window.__pickPlace.frame(i/10)));
assert.ok(frames.slice(250,940).every(f=>f.open===0));assert.equal(frames[940].lock,1);assert.equal(frames[1000].head[2],380);assert.ok(frames[1000].gripper[2]>frames[1000].head[2]+150);
for(let i=1;i<frames.length;i++)assert.ok(Math.hypot(...frames[i].head.map((v,k)=>v-frames[i-1].head[k]))<5,'head path jump');
await page.locator('#play').click();await page.waitForTimeout(320);assert.ok(+(await page.locator('#progress').inputValue())>0);await page.locator('#play').click();
await page.locator('#progress').evaluate(e=>{e.value=99;e.dispatchEvent(new Event('input'));});assert.match(await page.locator('#motion-phase').textContent(),/退出/);
const [download]=await Promise.all([page.waitForEvent('download'),page.locator('#export').click()]);
const exported=JSON.parse(await readFile(await download.path(),'utf8'));assert.equal(exported.trajectory.length,101);assert.equal(exported.trajectory[100].wrist_target_pose_mm[2][2],-1);
assert.ok(await page.locator('#feed-mode-button').isVisible());
const axial=published.candidates.find(c=>c.id==='axial5');
const feedCases=await page.evaluate(()=>Array.from({length:101},(_,i)=>window.__pickPlace.feedFrame(i)));
for(let i=0;i<feedCases.length;i++)for(const [key,value]of Object.entries(feedCases[i])){const expected=axial.feed_cycle_cases[i][key];if(typeof value==='number')assert.ok(Math.abs(value-expected)<1e-8,`axial sequence ${i} ${key}`);else assert.equal(value,expected);}
await page.locator('#feed-mode-button').click();await page.locator('#last-round').click();
await page.locator('#feed-pitch').evaluate(e=>{e.value=45;e.dispatchEvent(new Event('input'));});
await page.locator('#feed-progress').evaluate(e=>{e.value=61;e.dispatchEvent(new Event('input'));});
const feedSnapshot=await page.evaluate(()=>window.__pickPlace.feedSnapshot());
assert.equal(feedSnapshot.visibleBalls,1);assert.ok(Math.abs(feedSnapshot.ball0[0]+8)<1e-8);assert.ok(Math.abs(feedSnapshot.tipFaceX+29.25)<1e-8);assert.equal(feedSnapshot.gateY,52);assert.ok(Math.abs(feedSnapshot.pitchDeg-45)<1e-8);assert.match(await page.locator('#feed-interlock').textContent(),/禁止/);
await page.screenshot({path:'/tmp/axial5-last-round-45.png',fullPage:true});
await page.locator('#feed-progress').evaluate(e=>{e.value=100;e.dispatchEvent(new Event('input'));});assert.match(await page.locator('#feed-interlock').textContent(),/允许/);assert.equal((await page.evaluate(()=>window.__pickPlace.feedSnapshot())).visibleBalls,0);
await page.locator('#feed-play').click();await page.waitForTimeout(320);assert.ok(+(await page.locator('#feed-progress').inputValue())>0);await page.locator('#feed-play').click();
const [feedDownload]=await Promise.all([page.waitForEvent('download'),page.locator('#export').click()]);const feedExport=JSON.parse(await readFile(await feedDownload.path(),'utf8'));assert.equal(feedExport.feed_cycle.length,101);assert.equal(feedExport.feed_cycle_initial_ammo,1);
await page.setViewportSize({width:390,height:844});await page.screenshot({path:'/tmp/axial5-mobile.png',fullPage:true});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await page.setViewportSize({width:1440,height:1080});
await page.locator('[data-mode="underside"]').click();await page.screenshot({path:'/tmp/pick-place-underside.png'});
await page.locator('[data-mode="layout"]').click();await page.screenshot({path:'/tmp/pick-place-desktop.png',fullPage:true});
await page.setViewportSize({width:390,height:844});await page.screenshot({path:'/tmp/pick-place-mobile.png',fullPage:true});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
await page.goto(new URL('pick-place.html',import.meta.url).href);await page.waitForFunction(()=>window.__pickPlace?.ready);assert.deepEqual(published.candidates.map(c=>c.id),['axial5']);
assert.equal(await page.locator('#comparison-body tr').count(),1);
await page.goto('http://127.0.0.1:8773/mechanical/hero_head/magazine_study/');await page.waitForFunction(()=>window.__pickPlace?.ready);assert.match(page.url(),/pick-place\.html#axial5$/);
assert.deepEqual(errors,[]);assert.deepEqual(failed,[]);
const result={candidates:published.candidates.length,mesh_bounds_within_published:true,python_js_mass_and_cg_agree:true,ammo_changes_mass_not_geometry:true,release_after_lock:true,trajectory_export:true,animation:true,axial_101_frames_python_js_agree:true,axial_last_ball_pitch45:true,axial_feed_export:true,mobile_no_overflow:true,file_url:true,page_errors:errors,failed_requests:failed};
await writeFile(new URL('../pick_place_study/browser-checks.json',import.meta.url),JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify(result));await browser.close();
