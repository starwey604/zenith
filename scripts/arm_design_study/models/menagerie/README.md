# 六轴参考模型来源

本目录复制了 [MuJoCo Menagerie](https://github.com/google-deepmind/mujoco_menagerie) 提交 `8161bba264d7fa7c99ca301e91e7fb44737676ad` 中的五个模型目录：`ufactory_lite6`、`unitree_z1`、`universal_robots_ur10e`、`trossen_wx250s`、`agilex_piper`。各目录包含原有的 `LICENSE`、`README.md`、XML 和模型资源。XML、网格与预览图片由 Git LFS 跟踪，许可证和说明文字由普通 Git 跟踪。

本工作区从每份 MJCF 的零位关节锚点、轴向、限位和法兰参考体提取六轴运动学。WidowX 250 与 PiPER 文件还含夹爪关节；这里只取六个旋转臂关节。模型资源用于复现 MJCF 加载，并不表示厂商对这些派生臂长候选作了认证。任务中的工具长度、粗碰撞半径和安装位置仍来自 `configs/benchmark.six_axis_v2.synthetic.json` 的合成假设。
