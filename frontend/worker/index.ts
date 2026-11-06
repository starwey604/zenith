interface Fetcher { fetch(request: Request): Promise<Response> }
interface Env { ASSETS: Fetcher; COMMENTS_SERVICE: Fetcher }

/** Only the reserved comments path reaches the independent backend. All existing assets keep their entry points. */
export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    if (url.pathname === '/api/comments' || url.pathname.startsWith('/api/comments/')) {
      const target = new URL('https://zenith-comments.internal');
      target.pathname = url.pathname.slice('/api/comments'.length) || '/';
      target.search = url.search;
      return env.COMMENTS_SERVICE.fetch(new Request(target, request));
    }
    return env.ASSETS.fetch(request);
  },
};
