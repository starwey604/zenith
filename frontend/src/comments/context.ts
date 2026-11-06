/** Only explicitly supplied public design data enters a comment. Never serialize location or app state wholesale. */
export interface DesignContext {
  topic: string;
  candidate: string;
  revision: string;
  pageUrl: string;
  part?: string;
  parameters?: Record<string, string | number | boolean | null>;
}

function text(value: unknown, name: string, max = 160): string {
  if (typeof value !== 'string' || !value.trim() || value.length > max) {
    throw new Error(`${name} 不能为空，且不能超过 ${max} 字符`);
  }
  return value.trim();
}

export function publicUrl(value: string): string {
  const url = new URL(value);
  if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password) {
    throw new Error('页面地址必须是无凭据的 HTTP(S) 地址');
  }
  return url.href;
}

/** Revision and slider changes stay in one discussion. Topic/candidate identifiers must remain stable. */
export function discussionPath(context: Pick<DesignContext, 'topic' | 'candidate'>): string {
  const id = /^[a-z0-9][a-z0-9_-]{0,79}$/;
  if (!id.test(context.topic) || !id.test(context.candidate)) {
    throw new Error('topic / candidate 请使用稳定的小写英文、数字、短横线或下划线 ID');
  }
  return `/zenith-discussions/${context.topic}/${context.candidate}`;
}

export function snapshotContext(input: DesignContext): DesignContext {
  discussionPath(input);
  const result: DesignContext = {
    topic: input.topic, candidate: input.candidate,
    revision: text(input.revision, '版本'), pageUrl: publicUrl(input.pageUrl),
  };
  if (input.part !== undefined) result.part = text(input.part, '部件');
  if (input.parameters !== undefined) {
    const entries = Object.entries(input.parameters);
    if (entries.length > 40) throw new Error('公开参数不能超过 40 项');
    result.parameters = Object.fromEntries(entries.map(([key, value]) => {
      text(key, '参数名', 80);
      if (typeof value === 'string') text(value, '参数值', 240);
      else if (typeof value === 'number' ? !Number.isFinite(value) : value !== null && typeof value !== 'boolean') {
        throw new Error('公开参数只接受有限数值、短文本、布尔值或 null');
      }
      return [key, value];
    }));
  }
  return result;
}

export function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, char => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[char]!));
}

/** Twikoo onSubmit receives rendered HTML, not Markdown. Keep the snapshot visible and exportable in the body. */
export function contextAppendix(context: DesignContext): string {
  const snapshot = { schema: 'zenith.design-context.v1', ...snapshotContext(context) };
  return `<details><summary>提交时的方案参数 · ${escapeHtml(snapshot.revision)}${snapshot.part ? ` · ${escapeHtml(snapshot.part)}` : ''}</summary><pre><code>${escapeHtml(JSON.stringify(snapshot, null, 2))}</code></pre></details>`;
}

/** Safe embedding into a script element in srcdoc. */
export function scriptJson(value: unknown): string {
  return JSON.stringify(value).replace(/[<>&\u2028\u2029]/g, char => `\\u${char.charCodeAt(0).toString(16).padStart(4, '0')}`);
}
