// Runs only inside the component-owned iframe. The SDK and all Vue/global styles die with this frame.
(() => {
  const config = window.__zenithComments;
  const send = (type, data = {}) => parent.postMessage({ channel: 'zenith-comments-v1', type, ...data }, config.parentOrigin);
  const pending = new Map();
  let nextId = 0;
  window.addEventListener('message', event => {
    if (event.source !== parent || event.origin !== config.parentOrigin) return;
    const message = event.data;
    if (message?.channel !== 'zenith-comments-v1' || message.type !== 'context-result') return;
    const request = pending.get(message.id);
    if (!request) return;
    clearTimeout(request.timeout);
    pending.delete(message.id);
    if (message.error) request.reject(new Error(message.error));
    else request.resolve(message);
  });
  const requestContext = () => new Promise((resolve, reject) => {
    const id = ++nextId;
    const timeout = setTimeout(() => {
      pending.delete(id);
      reject(new Error('读取方案参数超时，请保留草稿后重试'));
    }, 5000);
    pending.set(id, { resolve, reject, timeout });
    send('context-request', { id });
  });
  new ResizeObserver(() => send('height', { height: document.documentElement.scrollHeight })).observe(document.body);
  const script = document.createElement('script');
  script.src = config.sdkUrl;
  script.onerror = () => send('error', { message: '评论组件文件加载失败，请重试。' });
  script.onload = async () => {
    try {
      if (window.twikoo?.version !== config.version) throw new Error('评论组件版本不匹配');
      await window.twikoo.init({
        envId: config.envId, el: '#comments', path: config.path, href: config.href,
        lang: 'zh-CN', // Simplified Chinese is embedded in the pinned SDK (no locale CDN request).
        onSubmit: async payload => {
          const snapshot = await requestContext();
          payload.url = config.path;
          payload.href = snapshot.href;
          payload.comment += snapshot.appendix;
        },
      });
      send('ready');
    } catch (error) {
      send('error', { message: error instanceof Error ? error.message : '评论组件初始化失败' });
    }
  };
  document.head.append(script);
})();
