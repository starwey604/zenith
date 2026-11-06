import { test } from 'node:test';
import assert from 'node:assert/strict';
import worker from '../worker/index.ts';
test('仅转发精确评论前缀；静态入口和相似路径保持原有语义', async () => {
  const forwarded: Request[] = [], assets: Request[] = [];
  const env = {
    COMMENTS_SERVICE: { async fetch(request: Request) { forwarded.push(request); return new Response('comments'); } },
    ASSETS: { async fetch(request: Request) { assets.push(request); return new Response('asset'); } },
  };
  const request = new Request('https://zenith.silkenkite.ink/api/comments?test=1', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{"event":"GET_CONFIG"}' });
  assert.equal(await (await worker.fetch(request, env)).text(), 'comments');
  assert.equal(forwarded[0].url, 'https://zenith-comments.internal/?test=1');
  assert.equal(await forwarded[0].text(), '{"event":"GET_CONFIG"}');
  await worker.fetch(new Request('https://zenith.silkenkite.ink/api/comments/health'), env);
  assert.equal(forwarded[1].url, 'https://zenith-comments.internal/health');
  for (const path of ['/', '/gripper.html', '/dock.html', '/wiring.html', '/api/comments-unrelated', '/assets/model.glb']) {
    assert.equal(await (await worker.fetch(new Request(`https://zenith.silkenkite.ink${path}`), env)).text(), 'asset');
  }
  assert.equal(assets.length, 6);
});
