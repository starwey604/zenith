# 轴向五格直推演示页

只保留当前方案。旧构型的选择过程见[方案演变](../DESIGN_HISTORY.md)，参数和复算见[设计说明](../pick_place_study/README.md)。目录名保留，原访问地址可继续使用。

## 查看

首次检出先按下节重算数据、构建网页。之后可直接打开[pick-place.html](pick-place.html#axial5)，或从仓库根目录启动：

```bash
python3 -m http.server 8773 --bind 127.0.0.1
```

访问 http://127.0.0.1:8773/mechanical/hero_head/magazine_study/ ，会跳到当前方案。真实核心及机箱网格嵌入本地bundle，不需要外部网络。

`*.bundle.js`是可重建的本地产物，不提交。源码、锁定依赖、当前计算快照和验证记录提交到Git；参考网格与CAD使用Git LFS，首次检出需取齐LFS文件。`node_modules/`和截图目录同样只留本地。

## 构建与浏览器检查

本目录执行：

```bash
npm ci
npm run build
npm run check
```

构建前先在仓库根目录重算`pick_place_study/build_study.py`和`feed_geometry_check.py`。检查要求上述8773端口服务器正在运行，本机`/usr/bin/chromium`可用。已有`build:pick-place`、`check:pick-place`别名保留。

- `src/pick-place.js`：三维布局、供弹及夹取落座演示、参数和JSON导出。
- `src/axial-feed-motion.js`：与Python计算一致的推送动作。
- `assets/reference_meshes.json`：当前使用的原发射核心和LBC3机箱网格；来源在JSON内。
- `assets/THREE-LICENSE.txt`：Three.js许可证。
- `pick-place-checks.mjs`：现有浏览器回归检查，结果写到`../pick_place_study/browser-checks.json`；截图只写到`/tmp/`。

界面沿用雾蓝观察区、白色说明区、供弹蓝／承力金／电子青／夹爪紫。动画是动作意向，任务目标未解IK；接触、锁紧和可靠性不由页面证明。
