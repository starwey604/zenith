import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { initialConfig, allowedOrigin, validateSubmission } from '../src/policy.mjs';
test('initial password uses Twikoo native hash contract; raw password is not stored', () => {
  const password = 'local-test-only-password';
  const config = initialConfig(password);
  const browserToken = createHash('md5').update(password).digest('hex');
  assert.equal(config.ADMIN_PASS, createHash('md5').update(browserToken).digest('hex'));
  assert.ok(!JSON.stringify(config).includes(password));
  assert.equal(config.AKISMET_KEY, '');
  assert.throws(() => initialConfig('short'));
});
test('CORS checks exact origins; non-browser APIs do not become anonymous admins', () => {
  assert.equal(allowedOrigin(new Request('https://test', { headers: { Origin: 'https://zenith.silkenkite.ink' } }), 'https://zenith.silkenkite.ink'), 'https://zenith.silkenkite.ink');
  assert.throws(() => allowedOrigin(new Request('https://test', { headers: { Origin: 'https://zenith.silkenkite.ink.evil.test' } }), 'https://zenith.silkenkite.ink'));
  assert.equal(allowedOrigin(new Request('https://test'), ''), null);
});
test('only actual page topics accept comments; other Twikoo operations retain their own validation', () => {
  validateSubmission({ event: 'COMMENT_GET' });
  const valid = { event: 'COMMENT_SUBMIT', url: '/zenith-discussions/dock/rear-guided', nick: '机械同学', comment: '<p>测试</p>' };
  validateSubmission(valid);
  assert.throws(() => validateSubmission({ ...valid, url: '/elsewhere' }));
  assert.throws(() => validateSubmission({ ...valid, nick: '' }));
  assert.throws(() => validateSubmission({ ...valid, comment: 'x'.repeat(24001) }));
});
