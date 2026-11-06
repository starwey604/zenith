import twikoo, { getD1Database, type CloudflareEnvLike, type ExecutionContextLike } from '../.upstream/packages/server-cloudflare/dist/index.js';
import { allowedOrigin, initialConfig, validateSubmission } from './policy.mjs';

interface Env extends CloudflareEnvLike { ALLOWED_ORIGINS: string; INITIAL_ADMIN_PASSWORD?: string }
const initializing = new WeakMap<object, Promise<void>>();

async function initialized(env: Env): Promise<void> {
  if (!env.DB) throw new Error('D1 binding missing');
  const running = initializing.get(env.DB);
  if (running) return running;
  const task = (async () => {
    const db = getD1Database(env);
    await db.init();
    const config = await db.getConfig();
    if (config?.ADMIN_PASS) return;
    if (!config) {
      const stored = await env.DB!.prepare('SELECT value FROM config LIMIT 1').first<{ value: string }>();
      if (stored?.value) throw new Error('Existing administrator configuration is invalid; refusing to overwrite it');
    }
    // No public first-user password setup. Only the owner's Worker secret can initialize this database.
    if (!env.INITIAL_ADMIN_PASSWORD) throw new Error('管理员尚未初始化；请由站长配置 INITIAL_ADMIN_PASSWORD');
    await db.saveConfig(initialConfig(env.INITIAL_ADMIN_PASSWORD));
  })().catch(error => { initializing.delete(env.DB!); throw error; });
  initializing.set(env.DB, task);
  return task;
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json;charset=utf-8', 'Cache-Control': 'no-store' } });
}

/** Bound request parsing before handing the unchanged API contract to Twikoo. */
async function payload(request: Request): Promise<Record<string, unknown>> {
  const reader = request.body?.getReader();
  if (!reader) throw new Error('请求缺少 JSON');
  const chunks: Uint8Array[] = []; let size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read(); if (done) break;
      size += value.length;
      if (size > 32768) { await reader.cancel(); throw new Error('请求超过 32 KiB'); }
      chunks.push(value);
    }
  } finally { reader.releaseLock(); }
  const bytes = new Uint8Array(size); let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
  const result: unknown = JSON.parse(new TextDecoder().decode(bytes));
  if (!result || typeof result !== 'object' || Array.isArray(result)) throw new Error('请求必须是 JSON 对象');
  return result as Record<string, unknown>;
}

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContextLike): Promise<Response> {
    let origin: string | null;
    try { origin = allowedOrigin(request, env.ALLOWED_ORIGINS); }
    catch { return json({ code: 1000, message: 'Origin not allowed' }, 403); }
    const cors = (response: Response) => {
      const headers = new Headers(response.headers);
      headers.delete('Access-Control-Allow-Origin');
      if (origin) headers.set('Access-Control-Allow-Origin', origin);
      headers.set('Vary', 'Origin'); headers.set('Cache-Control', 'no-store');
      headers.set('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
      headers.set('Access-Control-Allow-Headers', 'Content-Type');
      return new Response(response.body, { status: response.status, headers });
    };
    if (request.method === 'OPTIONS') return cors(new Response(null, { status: 204 }));
    if (!['GET', 'POST'].includes(request.method)) return cors(json({ message: 'Method not allowed' }, 405));
    if (request.method === 'GET' && new URL(request.url).pathname !== '/health') {
      return cors(json({ service: 'zenith-comments', engine: 'twikoo', version: '2.0.17', health: '/health' }));
    }
    try { await initialized(env); }
    catch (error) {
      console.error('Comment initialization failed:', error instanceof Error ? error.message : 'Unknown');
      return cors(json({ code: 1000, message: '评论服务尚未就绪，请稍后重试或联系站长。' }, 503));
    }
    if (request.method === 'GET') return cors(json({ service: 'zenith-comments', ready: true, database: 'D1', version: '2.0.17' }));
    let body: Record<string, unknown>;
    try { body = await payload(request); validateSubmission(body); }
    catch (error) { return cors(json({ code: 1000, message: error instanceof Error ? error.message : '请求格式不正确' })); }
    // Reconstruct after bounded parsing; CF headers/properties needed by upstream are retained.
    const forwarded = new Request(request, { body: JSON.stringify(body) });
    return cors(await twikoo.fetch(forwarded, env, ctx));
  },
};
