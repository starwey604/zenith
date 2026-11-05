# 重装头部外购件资料收集

当前车载储弹＋可拆头方案及此前五格打样背景的[资料需求清单](../../mechanical/hero_head/PROTOTYPE_INPUTS.md)及[可填写表](../../mechanical/hero_head/prototype_parts.csv)。

优先放入：实际42 mm测速模块；实际摩擦轮、电机、轮芯/轴套与电调；MIPI相机、镜头及排线；队里现有小型执行器和传动件图纸。按清单编号建子目录即可，例如：

```text
HH-01_speed_monitor/
HH-02_flywheel_motor/
HH-03_flywheel_assembly/
HH-05_camera/
HH-06_lens/
HH-09_pusher_drive/
```

命名建议：`厂家_完整型号_版本.step`、`厂家_完整型号_安装图.pdf`。有原生文件可附Parasolid/SolidWorks等，最好同时导出STEP；运动件附收拢/伸出状态，接插件附配对件。

同目录附简短`source.txt`或说明：来源/下载地址、取得日期、准确型号及版本、单位、质量（厂家/实称）、是否与现有实物相符、是否允许在本仓库分享。不确定的尺寸或代用模型请标注，避免按真件开孔。

本目录目前只存收集说明；已收到的SM11、M3508、C620和CamAdaptor模型位于`mechanical/steps/`，相机图位于`references/camera.pdf`。相机＋LBC3固定结构已有`mechanical/camera_lbc3_study/`的V2模型，不必重复收集。标准螺钉等不用逐一收STEP，确定标准/型号后由模型生成。
