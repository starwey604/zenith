import { test } from 'node:test';
import assert from 'node:assert/strict';
import { contextAppendix, discussionPath, scriptJson, snapshotContext } from '../src/comments/context.ts';
const base = { topic: 'dock', candidate: 'rear-guided-v1', revision: 'v1', pageUrl: 'https://zenith.silkenkite.ink/dock.html' };
test('讨论键只取稳定主题和候选 ID，不随版本、参数和部件变化', () => {
  assert.equal(discussionPath(base), '/zenith-discussions/dock/rear-guided-v1');
  assert.equal(discussionPath({...base, revision: 'v2'}), discussionPath(base));
  assert.throws(() => discussionPath({...base, topic: '../dock'}));
});
test('公开快照复制明确字段，不收集隐式应用状态', () => {
  const source = {...base, secret: 'never-export', parameters: { clearanceMm: 41, enabled: true, note: '前侧', missing: null }};
  const snapshot = snapshotContext(source);
  source.parameters.clearanceMm = 50;
  assert.equal(snapshot.parameters?.clearanceMm, 41);
  assert.ok(!JSON.stringify(snapshot).includes('never-export'));
  assert.throws(() => snapshotContext({...base, parameters: { clearance: Infinity }}));
  assert.throws(() => snapshotContext({...base, pageUrl: 'javascript:alert(1)'}));
  assert.throws(() => snapshotContext({...base, pageUrl: 'https://name:password@example.com'}));
});
test('上下文追加到 HTML 正文时转义，srcdoc 配置不能闭合 script', () => {
  const hostile = {...base, part: '</code></pre><img src=x onerror=alert(1)>', parameters: { material: '<script>bad()</script>' }};
  const appendix = contextAppendix(hostile);
  assert.ok(appendix.includes('zenith.design-context.v1'));
  assert.ok(appendix.includes('&lt;img'));
  assert.ok(!appendix.includes('<script>'));
  const embedded = scriptJson({ value: '</script><script>bad()</script>\u2028' });
  assert.ok(!embedded.includes('<'));
  assert.equal(JSON.parse(embedded).value, '</script><script>bad()</script>\u2028');
});
