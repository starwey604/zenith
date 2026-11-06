import { test, expect } from '@playwright/test';

test('四个入口均接入讨论，当前部件与参数刷新；未配置不请求后端', async ({ page }) => {
  for (const [path, topic] of [['/', 'head'], ['/gripper.html', 'gripper'], ['/dock.html', 'dock'], ['/wiring.html', 'wiring']]) {
    await page.goto(path);
    const discussion = page.locator('#discussion');
    await expect(discussion.getByRole('heading', { name: '讨论与反馈' })).toBeVisible();
    await expect(discussion.locator('.zc-context')).toContainText(topic);
    await expect(discussion.locator('iframe')).toHaveCount(0);
    // Empty configuration is an intentional disabled state, not a fake submission form.
    if (await discussion.getByRole('button', { name: '加载评论', exact: true }).isDisabled()) {
      await expect(discussion.getByRole('status')).toContainText('尚未配置');
    } else await expect(discussion.getByRole('status')).toContainText('点击后加载');
  }
  await page.getByRole('button', { name: '自有 CAN', exact: true }).click();
  await expect(page.locator('#discussion .zc-snapshot')).toContainText('CTRL');
  await page.goto('/dock.html?mode=contacts&contact=R2');
  await expect(page.locator('#discussion .zc-context')).toContainText('R2');
  await page.locator('[data-contact=F1]').click();
  await expect(page.locator('#discussion .zc-context')).toContainText('F1');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator('#discussion').scrollIntoViewIfNeeded();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: '/tmp/zenith-comments-integrated-mobile.png', fullPage: true });
});
