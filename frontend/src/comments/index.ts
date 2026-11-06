import runtime from './frame-runtime.js?raw';
import frameStyle from './frame.css?raw';
import './style.css';
import { contextAppendix, discussionPath, publicUrl, scriptJson, snapshotContext, type DesignContext } from './context.ts';
export type { DesignContext } from './context.ts';

export const TWIKOO_VERSION = '2.0.17';
// Classic UMD script must bypass Vite's JS-module transform during development too.
const sdkUrl = new URL(`${import.meta.env.BASE_URL}vendor/twikoo-2.0.17.min.js`, window.location.origin).href;

export interface CommentsOptions {
  /** Public endpoint only. Never pass Cloudflare/GitHub credentials here. Omit for a disabled, network-free component. */
  envId?: string;
  /** Read at submit time; return only the deliberately public parameter subset. */
  getContext: () => DesignContext;
}
export interface CommentsHandle {
  /** Refresh the visible context after changing selected parts. Does not remount or discard the draft. */
  refreshContext(): void;
  destroy(): void;
}

const mounted = new WeakSet<HTMLElement>();

export function mountComments(host: HTMLElement, options: CommentsOptions): CommentsHandle {
  if (mounted.has(host) || host.childNodes.length) throw new Error('评论挂载点必须是未使用的空容器');
  const initial = snapshotContext(options.getContext());
  const path = discussionPath(initial);
  const endpoint = options.envId ? publicUrl(new URL(options.envId, window.location.origin).href) : undefined;
  const sameOriginDevelopment = endpoint && import.meta.env.DEV && new URL(endpoint).origin === window.location.origin;
  if (endpoint && !sameOriginDevelopment && new URL(endpoint).protocol !== 'https:' && !['localhost', '127.0.0.1', '[::1]'].includes(new URL(endpoint).hostname)) {
    throw new Error('正式评论服务必须使用 HTTPS');
  }
  mounted.add(host);
  const root = document.createElement('section');
  root.className = 'zenith-comments';
  root.innerHTML = `<header><h2>讨论与反馈</h2><p class="zc-context"></p></header>
    <p>无需登录。昵称与评论公开显示；邮箱如填写，仅供管理与回复使用。请勿在正文中填写联系方式。</p>
    <label class="zc-disclosure"><input type="checkbox" checked>附上当前方案版本、选中部件与公开参数</label>
    <details><summary>查看将公开的方案信息</summary><pre class="zc-snapshot"></pre></details>
    <div class="zc-actions"><button type="button">加载评论</button><span role="status" aria-live="polite"></span></div>
    <div class="zc-frame-slot"></div>`;
  host.append(root);
  const contextLine = root.querySelector<HTMLElement>('.zc-context')!;
  const snapshot = root.querySelector<HTMLElement>('.zc-snapshot')!;
  const button = root.querySelector<HTMLButtonElement>('button')!;
  const status = root.querySelector<HTMLElement>('[role=status]')!;
  const disclose = root.querySelector<HTMLInputElement>('input')!;
  const slot = root.querySelector<HTMLElement>('.zc-frame-slot')!;
  let frame: HTMLIFrameElement | undefined;
  let timeout: ReturnType<typeof setTimeout> | undefined;
  let destroyed = false;

  function readContext(): DesignContext {
    const value = snapshotContext(options.getContext());
    if (discussionPath(value) !== path) throw new Error('讨论主题已变化，请在保留草稿后重新挂载评论区');
    return value;
  }
  function refreshContext(): void {
    if (destroyed) return;
    const current = readContext();
    contextLine.textContent = `${current.topic} / ${current.candidate} · ${current.revision}${current.part ? ` · ${current.part}` : ''}`;
    snapshot.textContent = JSON.stringify(current, null, 2);
  }
  refreshContext();
  if (!endpoint) {
    button.disabled = true;
    status.textContent = '评论服务尚未配置，当前不会发送数据。';
  } else status.textContent = '点击后加载评论服务。';

  function failed(message: string): void {
    clearTimeout(timeout);
    // Preserve the frame and any draft. Only explicit retry replaces it.
    status.textContent = message;
    button.textContent = '重新加载（草稿请先复制）';
    button.hidden = false;
    button.disabled = false;
  }
  function receive(event: MessageEvent): void {
    if (destroyed || !frame || event.source !== frame.contentWindow || event.origin !== window.location.origin) return;
    const data = event.data;
    if (data?.channel !== 'zenith-comments-v1') return;
    if (data.type === 'height' && typeof data.height === 'number' && Number.isFinite(data.height)) {
      frame.style.height = `${Math.min(12000, Math.max(300, data.height + 4))}px`;
    } else if (data.type === 'ready') {
      clearTimeout(timeout);
      status.textContent = '';
      button.hidden = true;
    } else if (data.type === 'error') failed(`加载失败：${String(data.message).slice(0, 200)}`);
    else if (data.type === 'context-request' && Number.isSafeInteger(data.id)) {
      try {
        const current = readContext();
        refreshContext();
        frame.contentWindow?.postMessage({ channel: 'zenith-comments-v1', type: 'context-result', id: data.id,
          appendix: disclose.checked ? contextAppendix(current) : '', href: disclose.checked ? current.pageUrl : initial.pageUrl,
        }, window.location.origin);
      } catch (error) {
        frame.contentWindow?.postMessage({ channel: 'zenith-comments-v1', type: 'context-result', id: data.id,
          error: error instanceof Error ? error.message : '无法读取公开方案参数',
        }, window.location.origin);
      }
    }
  }
  window.addEventListener('message', receive);
  function load(): void {
    if (!endpoint || destroyed) return;
    clearTimeout(timeout);
    frame?.remove();
    frame = document.createElement('iframe');
    frame.title = '方案讨论与反馈';
    frame.referrerPolicy = 'no-referrer';
    // Trusted local SDK. Same-origin is intentional: Twikoo needs localStorage for drafts/admin sessions.
    // This isolates styles and lifecycle; it is not a security sandbox for third-party code.
    const config = { envId: endpoint, path, href: initial.pageUrl, sdkUrl,
      version: TWIKOO_VERSION, parentOrigin: window.location.origin };
    frame.srcdoc = `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>${frameStyle}</style></head><body><div id="comments"></div><script>window.__zenithComments=${scriptJson(config)};<\/script><script>${runtime}<\/script></body></html>`;
    slot.append(frame);
    status.textContent = '正在加载评论…';
    button.disabled = true;
    timeout = setTimeout(() => failed('加载超时。请检查服务地址或网络，然后重试。'), 20000);
  }
  button.addEventListener('click', load);
  return {
    refreshContext,
    destroy() {
      destroyed = true;
      clearTimeout(timeout);
      window.removeEventListener('message', receive);
      button.removeEventListener('click', load);
      frame?.remove();
      root.remove();
      mounted.delete(host);
    },
  };
}
