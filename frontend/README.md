# 重装结构工作台

打开总装，点选右侧结构或模型，查看部件来源和接口说明。切到“供弹”可送一发或连续演示；切到“对接”逐步查看落座、锁紧和伸套接通；“视觉组件”独立查看相机＋LBC3 V2。

## 本地运行

在本目录执行（Node.js 22.12或更新版本；CI使用根目录`.node-version`指定的Node 22）：

```bash
npm ci
npm run dev
```

浏览器访问终端给出的5173端口地址。同一局域网可用这台机器的IP访问。开发服务器默认监听全部网卡，勿在不可信网络长期开放。

```bash
npm run build          # 检查GLB/下载件，生成布局参数，类型检查，输出dist/
npm run check:dist     # 检查生产资源和Workers单文件大小限制
npm run deploy:check   # Wrangler本地打包检查，不发布
npm run preview        # 用4173端口检查生产构建
npm test               # 单球状态、库存、互锁和10/12发循环
npm run test:browser   # 先build；实际浏览器检查页面、动画、选取和下载
```

浏览器检查优先使用系统Chromium，也可设`CHROMIUM_PATH`。无系统浏览器时安装Playwright浏览器：`npx playwright install chromium`。测试使用软件WebGL兼容无GPU的CI环境。

## 怎么看这套结构

- **总装**：车侧单盘有序储弹，仓与头共用俯仰托架；机械臂只搬运可拆头。10/12发可切换，俯仰范围−15°～+45°。
- **供弹**：最低格与入口同轴。开门→推到轮组接管→出球→退净→关门→分度；可暂停、继续或装满重来。每发演示5秒，不代表实际射速。
- **对接**：头下降时套管缩回；底座承载、独立拉紧后，再伸套12 mm。拆头需清空接缝和关门。夹爪、锁紧驱动与触点为功能占位。
- **视觉组件**：相机在测速上方，电脑与相机共刚性底架。可隐藏上盖及分解观察，分解时排线隐藏；分解不表示连着排线的实际拆装轨迹。

工作区切换会应用相应显示预设，并停止当前动画。复选框始终显示当前图层状态；“全部显示”恢复完整装配。点选结构后，可在详情下载原参考CAD。保存图片仅导出三维画布；分享地址保留工作区、容量、俯仰与所选结构，不保存任意旋转后的相机姿态。

## 哪些来自实物参考，哪些仍在设计

| 内容 | 当前来源与含义 |
|---|---|
| 摩擦轮 | 用户确认交龙同款；取原参考Ref_1204～1207，不重用旧3510电机 |
| M3508 | 用户指定；当前显示去减速箱本体参考，轴端、轮芯与新座的配合还需设计。下载为官方完整带减速箱原件，文件名与说明保留两者区别 |
| C620 | 用户提供STEP；头侧2块，显示本体与固定接头，移除原软线姿态后画总装线缆意向 |
| SM11 | 已有2020版STEP；保留测速本体和瞄准器，原线缆姿态未沿用 |
| 相机＋LBC3 | 独立V2结构与实际CamAdaptor；相机按尺寸图建外形，部分插头/风扇为尺寸参考 |
| 仓、推杆、分度、止弹、底座、托架 | 前端生成的自制结构意向；执行器没有库存型号，以紫色占位，不是可购买器件规格 |

`public/models/manifest.json`记录CAD来源、显示子集、尺寸单位和三角面数；它和布局下载JSON由`predev`/`build`生成，不纳入版本。用户已确认提供的厂家模型允许公开展示。交龙原参考保留来源身份，整套网页不将参考设计声明为本项目原创。

底部头部外形为当前静态布置的轴对齐包络，不含夹爪、弹盘和车侧托架；新座、侧耳及保护板占位计入，紧固件和插头未完整展开。质量未实称。此页面没有整车/真实六轴臂模型，不能据此判断整车收纳、可达性或受力合格。V2组件原有的几何检查不等于新整头总装已完成干涉或实球接触验证。

本轮默认车侧pitch轴为X=−30、Z=−112 mm，放在头下承载框下方；这与此前计算中使用过的Z=−70 mm示例不同。切勿把当前布局与旧力矩表当成同一候选。下载的布局JSON保留当前基准；底盘、实际轴承与驱动接入后再联合校核。

## 更新模型

正常`npm ci && npm run build`不需要FreeCAD。已经导出的6个GLB和CAD下载件均在`public/`，构建不访问仓库外路径或CDN。

CAD修改后，在FreeCAD/FreeCADCmd中执行：

```python
p = '/home/ww/codings/zenith/frontend/scripts/export_cad.py'
exec(compile(open(p).read(), p, 'exec'), {'__file__': p})
```

它读取已有源模型，重新输出GLB及复制下载件，不覆盖源CAD。再运行`npm run build`生成来源清单和布局参数。GLB采用glTF标准Y-up，导入后恢复本工程Z-up毫米坐标；不把STEP直接塞进浏览器解析。

- `src/layout.ts`：本轮共用布局基准；修改后检查`scene.ts`内相关座、导路和孔位，不能只改一处就认为整套参数化闭合。
- `src/scene.ts`：Three.js场景、CAD资产、占位件、渲染与拾取。
- `src/state.ts`：与渲染分开的装配状态与供弹循环。
- `src/catalog.ts`：各结构说明、来源及下载。
- `src/main.ts`、`src/style.css`：控制与响应式界面。

## 推送main后部署到Cloudflare Worker

参考[`rm_course`的部署工作流](https://github.com/starwey604/rm_course/blob/main/.github/workflows/deploy.yml)与[Wrangler配置](https://github.com/starwey604/rm_course/blob/main/wrangler.toml)，采用同样的纯Workers静态资源路径，保留本工程的npm锁文件。配置位于`frontend/wrangler.toml`，Worker名为`zenith`，资源目录为`dist/`。

### 设置GitHub Secrets

在任何已登录`gh`的终端运行，按提示粘贴值，不把Token写进命令参数或仓库：

```bash
gh secret set CLOUDFLARE_API_TOKEN --repo starwey604/zenith
gh secret set CLOUDFLARE_ACCOUNT_ID --repo starwey604/zenith
```

第一项是有Worker部署权限的Cloudflare **API Token**，可沿用`rm_course`同类权限并限制到目标账户；第二项是对应的Cloudflare账户ID，不是Zone ID。官方设置说明见[Workers GitHub Actions](https://developers.cloudflare.com/workers/ci-cd/external-cicd/github-actions/)。

### 发布与域名

提交并推送到`main`后，[部署工作流](../.github/workflows/deploy.yml)依次安装依赖、运行供弹状态测试、构建并检查资源、执行浏览器检查、Wrangler dry-run，通过后部署。PR只做检查；手动运行也仅允许main发布：

```bash
gh workflow run deploy.yml --repo starwey604/zenith --ref main
```

首次成功部署后，由用户在Cloudflare的`Workers & Pages → zenith → Settings → Domains & Routes → Add → Custom Domain`添加 **`zenith.silkenkite.ink`**。域名不写进`routes`，后续CI只更新Worker代码和静态资源，保留控制台域名设置。自定义域名操作见[Cloudflare说明](https://developers.cloudflare.com/workers/configuration/routing/custom-domains/)。

完整产物位于`frontend/dist/`。GLB与CAD按需请求，CAD不参与首屏下载；当前三维GLB合计约4.2 MB，CAD下载合计约42 MB。文件名带内容指纹的JS/CSS长期缓存；稳定文件名的模型与CAD每次请求重新验证，避免模型更新后仍显示旧版。

CI只拉取`frontend/public/downloads/*.FCStd`的Git LFS实体，不下载机械源文件与全部规则PDF。构建会拒绝未拉取的LFS指针。新检出仓库若禁用了LFS自动下载，在仓库根目录执行：

```bash
git lfs pull --include='frontend/public/downloads/*.FCStd' --exclude=''
```

Wrangler固定为4.156.0，兼容日期为2026-10-23，均与参考仓库一致。`npm run deploy`会真的发布，手动使用前先完成`npm run build && npm run check:dist`并通过Wrangler的正常认证流程；`npm run deploy:check`只做本地打包。
