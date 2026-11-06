import { test, expect } from '@playwright/test';

test('真实 SDK：按需加载、匿名提交、当前参数、隐私开关及移动端', async ({ page }) => {
  const requests: Record<string, unknown>[] = [];
  const submitted: Record<string, unknown>[] = [];
  let rejectSubmit = false;
  await page.route('**/twikoo', async route => {
    const body = route.request().postDataJSON() as Record<string, unknown>;
    requests.push(body);
    let response: unknown = { code: 0 };
    if (body.event === 'GET_CONFIG') response = { code: 0, config: {
      VERSION: '2.0.17', DISPLAYED_FIELDS: 'nick,mail', REQUIRED_FIELDS: 'nick',
      SHOW_EMOTION: 'false', SHOW_IMAGE: 'false', HIGHLIGHT: 'false', LIMIT_LENGTH: '4000',
      COMMENT_PLACEHOLDER: '请输入反馈', GRAVATAR_CDN: 'https://avatar.invalid',
    }};
    if (body.event === 'COMMENT_GET') response = { code: 0, data: submitted.map((item, index) => ({
      id: `test-${index}`, nick: item.nick, comment: item.comment, created: Date.now(), replies: [],
    })), count: submitted.length, more: false };
    if (body.event === 'COMMENT_SUBMIT') {
      if (rejectSubmit) response = { code: 1000, message: '测试服务拒绝了本次提交' };
      else {
        submitted.push(body);
        response = { code: 0, id: `test-${submitted.length - 1}` };
      }
    }
    await route.fulfill({ json: response });
  });
  // No avatar, OwO, IP lookup or other external service is needed for this acceptance test.
  await page.route(/^https?:\/\/(?!127\.0\.0\.1:5185)/, route => route.abort());
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('/');
  await expect(page.getByRole('button', { name: '加载评论', exact: true })).toBeDisabled();
  expect(await page.locator('iframe').count()).toBe(0);
  expect(requests.length).toBe(0);
  await page.locator('[name=endpoint]').fill('http://127.0.0.1:5185/twikoo');
  await page.getByRole('button', { name: '使用此服务' }).click();
  expect(requests.length).toBe(0);
  await page.getByRole('button', { name: '加载评论', exact: true }).click();
  const frame = page.frameLocator('iframe');
  await expect(frame.locator('.tk-send')).toBeVisible();
  await frame.getByPlaceholder('必填', { exact: true }).fill('机械同学');
  await frame.locator('textarea').fill('建议增加触点盒检修空间。');
  // Context changes after typing must not remount the SDK or lose the draft.
  await page.locator('#part').selectOption('F1 / FIRE+');
  await page.locator('#clearance').fill('50');
  await page.locator('#clearance').dispatchEvent('change');
  await expect(frame.locator('textarea')).toHaveValue('建议增加触点盒检修空间。');
  await frame.locator('.tk-send').click();
  await expect.poll(() => submitted.length).toBe(1);
  expect(submitted[0].url).toBe('/zenith-discussions/dock/rear-guided-v1');
  expect(submitted[0].comment).toContain('zenith.design-context.v1');
  expect(submitted[0].comment).toContain('F1 / FIRE+');
  expect(submitted[0].comment).toContain('50');
  expect(submitted[0].mail).toBe('');
  await expect(frame.locator('.tk-comment').first()).toContainText('建议增加触点盒检修空间');
  await page.getByLabel('附上当前方案版本、选中部件与公开参数').uncheck();
  await frame.locator('textarea').fill('第二条不附参数。');
  await frame.locator('.tk-send').click();
  await expect.poll(() => submitted.length).toBe(2);
  expect(submitted[1].comment).not.toContain('zenith.design-context.v1');
  rejectSubmit = true;
  await frame.locator('textarea').fill('提交失败也要保留这份草稿。');
  await frame.locator('.tk-send').click();
  await expect(frame.locator('.tk-error__message')).toHaveText('测试服务拒绝了本次提交');
  expect(submitted.length).toBe(2);
  await expect(frame.locator('textarea')).toHaveValue('提交失败也要保留这份草稿。');
  rejectSubmit = false;
  await frame.locator('.tk-send').click();
  await expect.poll(() => submitted.length).toBe(3);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: '/tmp/zenith-comments-mobile.png', fullPage: true });
  await page.setViewportSize({ width: 1200, height: 900 });
  await page.screenshot({ path: '/tmp/zenith-comments-desktop.png', fullPage: true });
  expect(errors).toEqual([]);
  // Remount destroys the iframe and its state; an unconfigured mount cannot submit.
  await page.locator('[name=endpoint]').fill('');
  await page.getByRole('button', { name: '使用此服务' }).click();
  await expect(page.locator('iframe')).toHaveCount(0);
  await expect(page.getByRole('button', { name: '加载评论', exact: true })).toBeDisabled();
});

test('SDK 文件加载失败可显式重试，不伪报提交成功', async ({ page }) => {
  await page.route('**/vendor/twikoo-*.js', route => route.abort());
  await page.goto('/');
  await page.locator('[name=endpoint]').fill('http://127.0.0.1:5185/twikoo');
  await page.getByRole('button', { name: '使用此服务' }).click();
  await page.getByRole('button', { name: '加载评论', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('文件加载失败');
  await expect(page.getByRole('button', { name: '重新加载（草稿请先复制）' })).toBeEnabled();
});
