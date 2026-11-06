# Zenith 评论后端

访问任一结构页底部的“加载评论”，填写昵称和正文即可提交，评论立即公开，无需审核。管理员仍可在评论框的小齿轮中登录，隐藏或删除个别评论。

## 部署对象与当前接入

- Worker：`zenith-comments`，独立于静态前端 `zenith`。
- D1 实际名称：`zenith`（用户创建时的名称）。ID：`0bbc6296-4e75-4295-ae4d-70e248901ad2`。
- 调试地址：`https://zenith-comments.moonbite233.workers.dev`。
- 正式浏览器入口：前端发布后使用 `https://zenith.silkenkite.ink/api/comments`，由 `COMMENTS_SERVICE` 服务绑定转发；不增加域名、不改变既有域名绑定。
- 健康检查：`GET /health`。200 且 `ready:true` 才表示 D1 和管理员配置可用；管理员未初始化时返回 503，公开设密也不会放行。

前端和后端分别发布。只发布本 Worker，不会更新线上 HTML 或启用前端代理。对应 CI 为 `.github/workflows/comments.yml`（Node.js 26）和原有 `deploy.yml`（前端 Node.js 22）。本目录不包含任何真实管理员密码。

## 首次设置管理员密码

已经登录 Wrangler 后，在本目录运行：

```bash
npm run admin:password
```

按 Wrangler 提示输入**至少 16 字符的独立密码**。它保存为 Cloudflare secret `INITIAL_ADMIN_PASSWORD`，不会进入浏览器、GitHub Variables 或代码。首次健康检查会按 Twikoo 原生的浏览器/服务端双重 MD5 契约初始化 D1；这里不另造认证协议。公开请求无法抢先设置首个密码。已有管理员密码不被部署或 secret 更新覆盖。

之后用这个原始密码登录评论框的小齿轮；改密用 Twikoo 已登录的管理界面。`INITIAL_ADMIN_PASSWORD`只用于空库初始化，不是“强制改密”接口，也不能通过反复更新它重置现有密码。密码遗失时由 Cloudflare 账号所有者处理 D1/配置恢复，勿清空评论库。

若 `/health` 持续 503，查看 `npx wrangler tail zenith-comments` 的初始化错误；密码不够长时重新执行上面命令。数据库读取失败或存在无法解析的配置时拒绝覆盖，不把读取故障当成首次注册。

## 构建与发布

```bash
npm ci
npm install --global pnpm@12.5.1  # 缺少 pnpm 时执行
npm run build
npm test
npm run smoke
npm run check
npm run deploy
```

`build`获取官方 Twikoo **2.0.17**，固定提交 `b13ef7c018b0cb1bb4b9ac82d98728322ae5e79b`；用上游 lockfile 安装过滤依赖、上游发布脚本注入版本，然后构建官方 Cloudflare 适配器。上游尚未发布该适配器到 npm，因此不依赖不存在的 npm 包。检出与构建产物保存在忽略的 `.upstream/`，不把第三方源码和 node_modules 纳入仓库。不改前端 SDK 的版本或前端 Node 基线。

`smoke`临时启动真正的workerd和本地D1，用固定**本地测试密码**验证初始化、登录、拒绝抢注、评论直接公开、HTML消毒、管理员隐藏/恢复、删除及来源限制。它固定使用本机5191端口和临时状态目录，不会读取远端管理员密码或操作线上评论。

上游来源与许可证见[官方仓库](https://github.com/twikoojs/twikoo/tree/2.0.17/packages/server-cloudflare)（MIT）。上游修改应通过升级固定版本交付，不直接修补忽略目录后当作稳定实现。

## 当前防滥用与数据语义

- 评论提交限制到四个已接入的稳定讨论键；昵称必填、最多80字符；HTTP请求最多32 KiB，HTML正文最多24000字符。上游另按转换后的正文文本限制4000字符。
- 默认`AKISMET_KEY`为空，不启用人工审核或外部Akismet；新评论提交后直接向其他访客显示。管理员仍可单独隐藏评论；取消强制审核不会批量公开已有隐藏记录。
- 上游频率窗口实际为**10分钟**，尽管配置名为 `LIMIT_PER_MINUTE`。当前取值3/全站20；2.0.17 使用 `count > limit` 判断，串行情况下第4条/第21条仍会被接受，后续才拒绝。不是严格的分布式防刷配额。
- CORS只允许配置中的正式域名和明确本地开发来源。没有Origin的API调用仍走原生鉴权；CORS不是登录机制。尚未启用Turnstile/Cap、邮件、图床和付费AI审核；当前保留长度和频率限制，管理员可事后处理垃圾评论。
- SDK保留匿名uid、草稿、管理会话的原有语义。公开接口不能返回管理员密码；管理员数据可能包含邮箱/IP/UA，不能作为公开GPT抓取源。
- 备份、导出和后续同步保留评论ID、父子关系与审核状态。完整增量导出、GitHub Issue 映射和 GPT 定时任务仍未实现；不要把最近100条接口当作完整变更日志。

恢复时优先回滚 Worker 版本或使用 D1 恢复能力，保留数据库。`wrangler.toml`只绑定已有数据库，不会每次部署重新创建库。静态页面回滚不会删除评论。

## 2026-11-06 接入验证

独立Worker已部署，所有者通过secret完成管理员初始化；线上`/health`返回200、`ready:true`、版本2.0.17。没有读取管理员原始密码。

初始接入时，真实浏览器从本地接线页经同源Vite代理提交一次匿名验收评论，云端返回`code:0`与评论ID。远端D1查询确认稳定主题为`/zenith-discussions/wiring/head-interface`、当时配置下`isSpam=1`（待审核），正文包含`zenith.design-context.v1`。该自动验收记录随后被清理。之后按用户要求取消强制审核，当前行为为提交后直接公开。

取消审核后，线上再次提交一条匿名测试评论，使用不同匿名身份立即从公开API读到该评论；提示文案同步改为“评论提交后直接公开”。本地workerd/D1测试同时确认新评论直接公开，管理员仍可单独隐藏、恢复或删除。自动验收记录随后清理，已有隐藏评论未批量公开。

前端25项单测、组件浏览器测试、四入口接入测试和Wrangler打包检查通过。正式前端的`/api/comments`服务绑定尚待这批前端代码发布；本次未提交或推送工作区中其他任务的改动。
