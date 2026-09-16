# Willow 0907 运动学参考

`Willow_0907_URDF.urdf` 是本机 `/home/ww/codings/Willow_0907_URDF/urdf/Willow_0907_URDF.urdf` 的原样副本，SHA-256 为 `d199ed3754aaa6ef4b704b3be130f8ae4c6ce3f655ce6e73edffffd6b8efa721`。源文件由 SolidWorks to URDF Exporter 生成。

本工作区只从该文件读取六个旋转关节的串联关系、`origin`、`axis` 和关节限位。URDF 引用的 STL 未复制进来，运动学筛选也不会加载视觉或碰撞网格。场景中的连杆胶囊半径仍是明确标注的设计假设。

URDF 中六个关节采用相同的 `effort` 和 `velocity` 数值，本轮不将其解释为实测执行器能力，也不进行动力学计算。
