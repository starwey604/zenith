// Real local workerd + D1, never points at a remote database and never uses the owner's password.
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';

const state = mkdtempSync(join(tmpdir(), 'zenith-comments-smoke-'));
const password = 'zenith-local-smoke-only-password';
const token = createHash('md5').update(password).digest('hex');
const server = spawn(process.execPath, ['node_modules/wrangler/bin/wrangler.js', 'dev', '--ip', '127.0.0.1', '--port', '5191', '--persist-to', state, '--var', `INITIAL_ADMIN_PASSWORD:${password}`], { detached: true, stdio: ['ignore', 'pipe', 'pipe'] });
let logs = '';
for (const stream of [server.stdout, server.stderr]) stream.on('data', chunk => { logs += chunk; });
const endpoint = 'http://127.0.0.1:5191/';
async function call(event, fields = {}, accessToken = 'local-anonymous-smoke') {
  const response = await fetch(endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json', Origin: 'http://127.0.0.1:5191' }, body: JSON.stringify({ event, ...fields, accessToken }) });
  const body = await response.json();
  assert.equal(response.status, 200, JSON.stringify(body));
  return body;
}
try {
  let ready = false;
  for (let attempt = 0; attempt < 120; attempt++) {
    try { const response = await fetch(`${endpoint}health`); if (response.ok) { ready = true; break; } } catch {}
    if (server.exitCode !== null) throw new Error(`Local workerd exited: ${logs}`);
    await delay(500);
  }
  assert.ok(ready, `Local workerd did not become healthy: ${logs.slice(-5000)}`);
  const config = await call('GET_CONFIG');
  assert.equal(config.config.VERSION, '2.0.17');
  assert.ok(!JSON.stringify(config).includes('ADMIN_PASS'));
  assert.ok(!JSON.stringify(config).includes(password));
  assert.equal((await call('LOGIN', { password: token })).code, 0);
  assert.notEqual((await call('LOGIN', { password: 'wrong' })).code, 0);
  assert.notEqual((await call('SET_PASSWORD', { password: 'attacker' })).code, 0);
  const url = '/zenith-discussions/dock/rear-guided';
  const submitted = await call('COMMENT_SUBMIT', { url, nick: '本地验收', ua: 'Zenith local smoke', comment: '<p>本地 D1 读写验收</p><script>alert(1)</script><img src=x onerror=alert(1)>' });
  assert.equal(submitted.code, 0, submitted.message);
  assert.ok(submitted.id);
  const published = await call('COMMENT_GET', { url }, 'another-local-reader');
  assert.ok(published.data.some(item => item.id === submitted.id), 'New comments must be immediately visible to another visitor');
  const admin = await call('COMMENT_GET_FOR_ADMIN', { page: 1, per: 20, type: 'ALL' }, token);
  assert.equal(admin.code, 0, admin.message);
  const row = admin.data.find(item => item._id === submitted.id);
  assert.ok(row, 'Persisted comment is retrievable by its ID');
  assert.ok(!row.comment.includes('<script>'));
  assert.ok(!row.comment.includes('onerror='));
  assert.equal(row.isSpam, false);
  assert.equal((await call('COMMENT_SET_FOR_ADMIN', { id: submitted.id, set: { isSpam: true } }, token)).code, 0);
  const hidden = await call('COMMENT_GET', { url }, 'another-local-reader');
  assert.ok(!hidden.data.some(item => item.id === submitted.id), 'Administrators can still hide individual comments');
  assert.equal((await call('COMMENT_SET_FOR_ADMIN', { id: submitted.id, set: { isSpam: false } }, token)).code, 0);
  const visible = await call('COMMENT_GET', { url }, 'another-local-reader');
  assert.ok(visible.data.some(item => item.id === submitted.id));
  const origin = await fetch(endpoint, { method: 'OPTIONS', headers: { Origin: 'https://untrusted.invalid' } });
  assert.equal(origin.status, 403);
  assert.ok(!origin.headers.has('Access-Control-Allow-Origin'));
  assert.notEqual((await call('COMMENT_SUBMIT', { url: '/wrong', nick: 'x', comment: 'x', ua: 'test' })).code, 0);
  assert.equal((await call('COMMENT_DELETE_FOR_ADMIN', { id: submitted.id }, token)).code, 0);
  console.log('PASS: real workerd/D1 initialization, native admin login, takeover rejection, immediate publication, sanitization, administrative hide/restore, origin restriction and deletion.');
} finally {
  try { process.kill(-server.pid, 'SIGTERM'); } catch {}
  await new Promise(resolve => { if (server.exitCode !== null) return resolve(); server.once('close', resolve); setTimeout(resolve, 3000).unref(); });
  rmSync(state, { recursive: true, force: true });
}
