import { mountComments, type DesignContext } from './index.ts';

/** Common page footer. The renderer remains independent of comment loading/failure. */
export function attachPageComments(getContext: () => DesignContext): void {
  const main = document.querySelector('main');
  if (!main) throw new Error('页面缺少 main 评论挂载位置');
  const host = document.createElement('div');
  host.className = 'zc-page-discussion';
  host.id = 'discussion';
  main.append(host);
  const handle = mountComments(host, { envId: import.meta.env.VITE_TWIKOO_ENV_ID?.trim() || undefined, getContext });
  let queued = false;
  const refresh = (event: Event) => {
    if (host.contains(event.target as Node) || queued) return;
    queued = true;
    queueMicrotask(() => { queued = false; handle.refreshContext(); });
  };
  // Read after the page's own handlers; never remount the SDK when a parameter changes.
  for (const type of ['input', 'change', 'click']) main.addEventListener(type, refresh);
  window.addEventListener('pagehide', event => {
    if (event.persisted) return; // Preserve drafts when entering the back/forward cache.
    for (const type of ['input', 'change', 'click']) main.removeEventListener(type, refresh);
    handle.destroy();
  });
}

/** Explicit public-state whitelist, not location.search (which may contain unrelated information). */
export function designPageUrl(parameters: Record<string, string | number | boolean> = {}): string {
  const url = new URL(location.pathname, location.origin);
  for (const [key, value] of Object.entries(parameters)) url.searchParams.set(key, String(value));
  return url.href;
}
