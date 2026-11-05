import { test, expect } from '@playwright/test';
import { readFile } from 'node:fs/promises';

test('总装、单球循环、对接、视觉和本地下载', async ({ page }) => {
  const errors: string[] = []; page.on('pageerror', e => errors.push(e.message));
  const missing: string[] = []; page.on('response', r => { if (r.status() >= 400) missing.push(r.url()); });
  await page.goto('/'); await page.waitForFunction(() => window.__workbench?.ready);
  await expect(page.locator('#scene-error')).toBeHidden();
  await expect(page.locator('#single-shot')).toBeEnabled();
  expect(await page.evaluate(() => window.__workbench.scene.renderer.info.render.triangles)).toBeGreaterThan(100000);
  expect(await page.evaluate(() => window.__workbench.headSize[1])).toBeLessThan(190); // excludes placeholder gripper
  await page.screenshot({ path: '/tmp/zenith-workbench-assembly.png', fullPage: true });
  for (const view of ['side', 'front', 'top', 'iso']) await page.locator(`[data-view="${view}"]`).click();
  // Actual canvas picking: nearest visible wheel ring, projected from world coordinates.
  await page.locator('[data-view="side"]').click();
  const point = await page.evaluate(async () => {
    const camera = window.__workbench.scene.camera;
    const p = camera.position.clone().set(0, -79, 0).project(camera);
    const r = document.querySelector('canvas')!.getBoundingClientRect();
    return { x: r.left + (p.x + 1) * r.width / 2, y: r.top + (1 - p.y) * r.height / 2 };
  });
  await page.mouse.click(point.x, point.y);
  await expect(page.locator('[data-part="launcher"]')).toHaveAttribute('aria-pressed', 'true');
  await page.locator('[data-layer="drive"]').uncheck();
  expect(await page.evaluate(() => window.__workbench.scene.registry.filter(r => r.layer === 'drive').every(r => !r.object.visible))).toBe(true);
  await page.locator('#show-all').click();
  await page.locator('#capacity').selectOption('10'); await expect(page.locator('#disk-diameter')).toContainText('212.6');
  await page.locator('#pitch').fill('45'); await expect(page.locator('#pitch-value')).toHaveText('45°');
  await page.locator('#pitch').fill('0');
  await page.locator('#explode').fill('50'); await expect(page.locator('#single-shot')).toBeDisabled();
  await page.locator('#explode').fill('0'); await page.locator('#dimensions').check();
  await page.locator('[data-mode="feed"]').click();
  await page.locator('#single-shot').click(); await expect(page.locator('#single-shot')).toBeDisabled();
  await page.waitForTimeout(400); await page.locator('#pause-feed').click();
  const paused = await page.evaluate(() => window.__workbench.sim.time); await page.waitForTimeout(300);
  expect(await page.evaluate(() => window.__workbench.sim.time)).toBe(paused);
  await page.screenshot({ path: '/tmp/zenith-workbench-feed.png', fullPage: true });
  await page.locator('#pause-feed').click(); await page.waitForFunction(() => !window.__workbench.sim.running);
  await expect(page.locator('#fired')).toHaveText('1'); await expect(page.locator('#remaining')).toHaveText('9');
  await page.locator('#refill').click(); await page.locator('#auto-feed').click();
  // Complete the ten logical cycles without waiting fifty wall-clock seconds.
  await page.evaluate(() => { for (let i = 0; i < 10; i++) window.__workbench.sim.tick(5); });
  await expect(page.locator('#remaining')).toHaveText('0'); await expect(page.locator('#cycle-status')).toContainText('弹盘已空');
  await page.locator('[data-mode="dock"]').click();
  await expect(page.locator('#pitch')).toBeDisabled();
  expect(await page.evaluate(() => window.__workbench.scene.head.position.z)).toBe(105);
  for (let i = 1; i < 5; i++) {
    await page.locator(`[data-phase="${i}"]`).click();
    await expect(page.locator(`[data-phase="${i}"]`)).toHaveAttribute('aria-pressed', 'true');
  }
  expect(await page.evaluate(() => window.__workbench.scene.sleeve.position.x)).toBe(12);
  await page.screenshot({ path: '/tmp/zenith-workbench-dock.png', fullPage: true });
  await page.locator('[data-mode="vision"]').click(); await page.locator('#lid').uncheck();
  expect(await page.evaluate(() => { let shown = false; window.__workbench.scene.vision.traverse(o => { if (o.name === 'CASE_lid') shown = o.visible; }); return shown; })).toBe(false);
  await page.locator('#explode').fill('35'); await page.screenshot({ path: '/tmp/zenith-workbench-vision.png', fullPage: true });
  const dl = page.waitForEvent('download'); await page.locator('#capture').click(); const download = await dl;
  const image = await readFile((await download.path())!); expect(image.readUInt32BE(0)).toBe(0x89504e47); expect(image.length).toBeGreaterThan(15000);
  await page.locator('[data-part="drive"]').click();
  const c620 = page.locator('a[href="downloads/c620.step"]'); await expect(c620).toBeVisible();
  const response = await page.request.get(await c620.getAttribute('href') as string); expect(response.status()).toBe(200); expect((await response.body()).length).toBeGreaterThan(6e6);
  expect((await page.request.get('/downloads/design-parameters.json')).status()).toBe(200);
  expect(errors).toEqual([]); expect(missing).toEqual([]);
});

test('手机布局与可分享参数', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/?mode=assembly&capacity=10&pitch=17&part=launcher'); await page.waitForFunction(() => window.__workbench?.ready);
  await expect(page.locator('#capacity')).toHaveValue('10'); await expect(page.locator('#pitch-value')).toHaveText('17°');
  await expect(page.locator('[data-part="launcher"]')).toHaveAttribute('aria-pressed', 'true');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: '/tmp/zenith-workbench-mobile.png', fullPage: true });
  await page.locator('[data-mode="dock"]').click(); await page.locator('[data-phase="3"]').click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await expect(page.locator('#phase-description')).toContainText('12 mm');
});
