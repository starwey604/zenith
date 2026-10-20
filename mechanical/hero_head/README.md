# 2027 重装头部：轴向五格主动直推

当前主线：**专用侧耳夹爪＋六轴臂搬运＋头下定位锁紧＋车侧承载与俯仰**。供弹采用 YZ 盘面五个独立格位，最低格正对入口，推头沿炮口 X 方向把球送入摩擦轮接管区。头部保留居中的 LBC3 与相机，无图传、无电池。

- [三维布局、供弹与取放演示](magazine_study/pick-place.html#axial5)
- [参数、尺寸、质量口径与复现](pick_place_study/README.md)
- [方案演变与本次清理说明](DESIGN_HISTORY.md)
- [通用六轴运动学工具](../../scripts/arm_design_study/README.md)

当前约 393×158×201 mm；五发头部质量预算 2.7375 kg，含 240 g夹爪约 2.9775 kg。几何占位和质量预算还未闭合成可制造设计；末弹直推、伸缩传动、保持件及底部锁紧是下一步细化重点。

## 目录

| 路径 | 内容 |
|---|---|
| `pick_place_study/` | 当前方案参数、预算／动作计算、结果和验证 |
| `magazine_study/` | 当前单方案网页、源码、真实参考网格和构建依赖；沿用原目录名以保持访问地址 |
| `cad/` | 发射核心实体参考与一个参数化重绘试件 |
| `scripts/` | 原 STEP 来源检查、导入、核心提取、试件重绘和网页网格导出 |
| `reports/` | 来源、核心坐标／尺寸和重绘试件验证记录 |

## 交龙参考及 FreeCAD 基础

原文件 `~/文档/HERO.STEP`，184,775,157 字节；头信息为 SolidWorks 2020、2021-08-27 导出、AP214。来源及 SHA-256 见 [source_manifest.json](reports/source_manifest.json)，中文产品名见 [source_products.csv](reports/source_products.csv)。原 STEP 未修改。原作者发布入口：[交龙 HERO 开源帖](https://bbs.robomaster.com/article/8480?source=4.)。后续仍需核对原说明、二维图与具体发布许可，不能将参考设计声明为本项目原创。

- [launcher_reference.FCStd](cad/launcher_reference.FCStd)：63 个原版零件实体的发射核心参考，不是完整头部或参数化重绘。坐标变换和选择范围见 [launcher_reference.json](reports/launcher_reference.json)。当前网页只显示其中实际保留的轮组、轮座和测速子集，入口局部仍需重画。
- [wheel_ring_parametric.FCStd](cad/wheel_ring_parametric.FCStd)：Spreadsheet → 完全约束 Sketch → PartDesign Pad 的环形试件。外径60、内径46.002、厚18 mm；恢复原参数后双向布尔差体积为0，改为外径62 mm的体积检查通过。结果见 [parametric_pilot.json](reports/parametric_pilot.json)。内径是源几何值，不是加工公差。
- 原两轮直径60 mm、轴间距98 mm，静态圆外缘间隙38 mm；不能把球径与此间隙之差直接当作实际压缩量。STEP没有可信的材料与质量信息。
- 整车 FreeCAD 导入缓存已删除，需要时可从原 STEP重新生成。保留发射核心实体与网页网格，不依赖整车缓存即可继续当前设计。

坐标：X朝测速出口，Y沿两轮中心连线，Z沿轮轴；原点取两外环实体质心中点。该坐标不等于机械臂法兰坐标。

### 重建参考

仓库根目录运行 `python3 mechanical/hero_head/scripts/inspect_source.py`，生成临时 Unicode STEP 副本；再用 FreeCAD运行 `scripts/import_reference.py`。在 FreeCAD Python控制台执行 `extract_launcher.py`、`build_wheel_pilot.py`，最后 `export_study_meshes.py`。脚本所在目录为 `mechanical/hero_head/scripts/`，输出路径由脚本定义。重新保存前请保留手工修改的文档。

当前保留 FreeCAD 工作流，无需为本次整理安装插件。LBC3 原机箱位于 [../lbc3_case_v1](../lbc3_case_v1/)，网页使用其真实参考网格。
