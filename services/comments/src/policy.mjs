import { createHash } from 'node:crypto';

export const defaults = {
  SITE_NAME: 'Zenith 结构工作台', SITE_URL: 'https://zenith.silkenkite.ink',
  DISPLAYED_FIELDS: 'nick,mail', REQUIRED_FIELDS: 'nick',
  SHOW_EMOTION: 'false', SHOW_IMAGE: 'false', HIGHLIGHT: 'false', SHOW_UA: 'false', SHOW_REGION: 'false',
  LIMIT_LENGTH: '4000', LIMIT_PER_MINUTE: '3', LIMIT_PER_MINUTE_ALL: '20',
  AKISMET_KEY: '',
  COMMENT_PLACEHOLDER: '指出你看到的问题或建议。评论提交后直接公开。',
};

/** Same two-stage hash as Twikoo's own browser + setPassword implementation, not a new auth scheme. */
export function initialConfig(password) {
  if (typeof password !== 'string' || password.length < 16) throw new Error('Initial administrator password must contain at least 16 characters.');
  const md5 = value => createHash('md5').update(value).digest('hex');
  return { ...defaults, ADMIN_PASS: md5(md5(password)) };
}

export function allowedOrigin(request, allowed) {
  const origin = request.headers.get('Origin');
  if (!origin) return null; // Non-browser APIs still use Twikoo's normal authorization.
  if (!allowed.split(',').map(value => value.trim()).includes(origin)) throw new Error('Origin not allowed');
  return origin;
}

export function validateSubmission(body) {
  if (body.event !== 'COMMENT_SUBMIT') return;
  if (typeof body.url !== 'string' || !/^\/zenith-discussions\/(head\/vehicle-feed|gripper\/dual-purpose-comparison|dock\/rear-guided|wiring\/head-interface)$/.test(body.url)) {
    throw new Error('未知讨论主题');
  }
  if (typeof body.nick !== 'string' || !body.nick.trim() || body.nick.length > 80) throw new Error('请填写 1–80 字的昵称');
  if (typeof body.comment !== 'string' || !body.comment.trim() || body.comment.length > 24000) throw new Error('评论为空或过长');
}
