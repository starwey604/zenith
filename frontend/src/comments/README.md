# 给方案留下可追溯的反馈

总装、双用途夹爪、底座和整头接线页末尾都有“讨论与反馈”。点击“加载评论”后才加载本地 Twikoo SDK 并请求评论服务。访客填写昵称和正文即可评论，邮箱选填；提交前可以查看或取消附带公开方案参数。

## 启用真实评论

组件已接入四个页面。独立后端配置和运维说明在 [`services/comments`](../../../services/comments/README.md)，绑定用户提供的 D1。正式入口采用现有域名下的 `/api/comments` 服务转发；前端发布后生效，不要求访客直连 `workers.dev`。先确认后端 `/health` 返回200及 `ready:true`，再开放提交。

### 需要什么账号

- **Cloudflare：沿用现有账号。** 独立评论 Worker 和 D1 已有明确配置，不需要新的域名注册或新的账号。前端仍托管静态资源，仅评论路径进入服务绑定。
- **Twikoo：不用注册平台账号。** 所有者通过后端目录的 `npm run admin:password` 设置至少16字符的初始密码；未初始化时不接受公开设密。之后在评论框的小齿轮登录管理。密码不要交给前端或写进仓库。
- **MongoDB、腾讯云、Vercel、邮件服务：此路线均不需要。** 邮件提醒可以以后再开。
- **人机验证：** 当前未启用验证码。以后可用同一Cloudflare账号创建Turnstile widget，不需另注册账号；站点key与服务端secret必须一起配置并验证服务端校验。Twikoo 2的内嵌Cap也是候选。

后端复用[Twikoo 官方 Workers + D1 适配器](https://github.com/twikoojs/twikoo/tree/2.0.17/packages/server-cloudflare)，固定2.0.17，使用独立Node.js 26构建流程；前端Node.js 22基线不变。

后端初始管理配置应包括：

```text
DISPLAYED_FIELDS = nick,mail
REQUIRED_FIELDS = nick
SHOW_EMOTION = false
HIGHLIGHT = false
LIMIT_LENGTH = 4000
AKISMET_KEY =
```

评论提交后直接公开，无需人工审核；管理员仍可隐藏或删除个别评论。不配置图片上传、邮件或付费服务。来源限制、长度上限和上游频率限制已在后端实现；尚未启用验证码。CORS不是认证或严格防刷配额。频率窗口的具体语义见后端文档。

### 本地配置

在 `frontend/.env.local` 设置公开地址后重启 Vite：

```dotenv
VITE_TWIKOO_ENV_ID=/api/comments
```

本地 Vite 会把该路径代理到独立评论后端；正式 Worker 通过服务绑定转发。它不是密钥。Vite会把值编译进浏览器文件；管理员密码、Cloudflare Token、GitHub Token 和验证码 secret 一律不放到 `VITE_*`。

### CI 配置

工作流已从 GitHub Repository Variables 读取同名变量：

```bash
gh variable set VITE_TWIKOO_ENV_ID --repo starwey604/zenith --body /api/comments
```

该Repository Variable已配置，下一次构建生效。仅在Cloudflare控制台设置运行时变量不会修改已构建的浏览器文件。变量为空时，页面明确显示服务未配置，按钮禁用且不会加载SDK。

## 接一个新页面

在页面 DOM 创建完成后调用；返回值只包含可公开的设计数据：

```ts
import { attachPageComments, designPageUrl } from './comments/page';

attachPageComments(() => ({
  topic: 'dock',
  candidate: 'rear-guided',
  revision: 'dock-layout-v0.1',
  part: selectedContact,
  pageUrl: designPageUrl({ mode, contact: selectedContact }),
  parameters: { wireClearanceMm: 41 },
}));
```

`topic/candidate`组成稳定讨论键，与域名、页面文件名、版本和滑块值无关。五页分别使用 `head/vehicle-feed`、`gripper/dual-purpose-comparison`、`dock/rear-guided`、`wiring/head-interface`、`protection/referee-head-board`。夹爪 A/B 共用比较讨论，所选构型写入参数；切换构型不会丢掉草稿或重新挂载。

页面交互后更新可见快照；提交时再次读取最新参数，不使用首次加载时的旧值。参数只接受不超过 40 项的扁平公开值。页面链接从明确字段建立，不复制任意 `location.search`。链接仅恢复该页面已经支持的状态；完整提交参数仍保留在评论正文中，不声称页面已有每个参数的 URL 恢复能力。

独立宿主也可以使用 `mountComments(emptyElement, { envId, getContext })`，通过 `refreshContext()`更新说明、`destroy()`移除 iframe。改变讨论键需要显式重新挂载，先保留草稿。Twikoo 的草稿与管理会话使用同源 localStorage；建议一页一个评论实例，避免多个实例或标签页竞争同一份上游草稿。

## 保存什么，后续怎么读

提交前钩子接收 Twikoo 已渲染的 HTML，附加一个可展开的方案参数区，包含 `zenith.design-context.v1` JSON。内容统一转义，参数不会作为 HTML 执行。使用正文是为了不依赖不同后端版本对额外字段的保存行为。取消附带参数时不追加该区。

这部分是访客提交的描述，**不能作为可信的设备状态、身份或自动执行指令**。昵称未验证；邮箱、IP、UA等字段按 Twikoo 后端的收集与访问策略处理，不把管理员导出数据直接公开或同步 GitHub。

后续程序可以按官方 API 读取可见评论及正文。**完整增量事件接口、隐藏/删除同步、GitHub Issue 映射和 GPT 定时任务尚未实现**；`getRecentComments`有数量上限，不能当作不会漏数据的增量接口。后续导出应另设只读权限，保留评论 ID、回复关系和变更游标。

## 独立验收

不依赖正式后端，在 `frontend/` 执行：

```bash
node --experimental-strip-types --test tests/comments.test.ts
npx vite build --config src/comments/vite.config.mjs
npx playwright test --config src/comments/playwright.config.mjs
```

测试使用真实本地 Twikoo 2.0.17 SDK 和模拟 HTTP 后端，覆盖匿名提交、提交时参数、关闭附带信息、草稿保持、加载失败和手机布局；不把模拟响应当作云端持久化验证。四页接入另由 `npx playwright test tests/comments.spec.ts` 检查。

手动查看独立组件：`npx vite --config src/comments/vite.config.mjs`，访问 `http://127.0.0.1:5184`。这张验收页不属于正式构建入口。

SDK 保存在 `frontend/public/vendor/`，固定2.0.17，保留MIT许可；开发与正式构建均原样提供经典脚本，不经过Vite的JS模块转换，不会运行时下载CDN。iframe隔离上游的全局样式、单实例Vue状态和生命周期；它保持同源以支持草稿，不是执行不可信第三方脚本的安全沙箱。未来如增加严格CSP，要同步处理srcdoc中的脚本和样式策略。
