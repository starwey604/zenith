import{chromium}from'../hero_head/magazine_study/node_modules/@playwright/test/index.mjs';
import assert from'node:assert/strict';
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader']});
const page=await browser.newPage({viewport:{width:1440,height:1100}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
const v2=process.argv.includes('--v2');
await page.goto(new URL(v2?'viewer_v2.html':'viewer.html',import.meta.url).href);await page.waitForFunction(()=>window.__cameraAssembly?.ready);await page.waitForTimeout(400);
assert.ok((await page.evaluate(()=>window.__cameraAssembly.parts)).includes('REF_ActualCAM1Adapter'));
if(v2){assert.ok((await page.evaluate(()=>window.__cameraAssembly.parts)).includes('REF_FPCRoute_Assumed'));await page.locator('#cable').uncheck();assert.ok(!(await page.evaluate(()=>window.__cameraAssembly.visibleParts())).includes('REF_FPCRoute_Assumed'));await page.locator('#cable').check();}
await page.screenshot({path:v2?'/tmp/camera-lbc3-v2-assembly.png':'/tmp/camera-lbc3-assembly.png',fullPage:true});
await page.locator('#lid').uncheck();await page.locator('#guard').uncheck();await page.locator('#keep').check();await page.locator('#explode').fill('40');await page.waitForTimeout(200);await page.screenshot({path:'/tmp/camera-lbc3-open.png',fullPage:true});
if(v2){await page.locator('#explode').fill('0');await page.locator('[data-view="side"]').click();await page.waitForTimeout(200);await page.screenshot({path:'/tmp/camera-lbc3-v2-cable.png'});}
await page.locator('[data-view="front"]').click();await page.screenshot({path:'/tmp/camera-lbc3-front.png'});
await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.deepEqual(errors,[]);await browser.close();console.log('Actual adapter present; view controls, exploded view, mobile width and JS errors checked.');
