"""Extract kinematics from local MJCF assets, without stepping dynamics."""
from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
import mujoco

from .frames import inverse, transform
from .sixr import SixR


WORKSPACE = Path(__file__).resolve().parents[3]
XARM_XML = WORKSPACE / "GoodGoodArmDayDayUp_Release/assets/xarm6/mujoco/dual_xarm6_learning_selected_750_scene.xml"
UR5E_XML = WORKSPACE / "imitation_learning_lerobot/imitation_learning_lerobot/assets/universal_robots_ur5e/ur5e.xml"
UR5E_CLASSES = UR5E_XML.with_name("ur5e_classes.xml")


def _ur5e_authored_limits() -> tuple[np.ndarray, np.ndarray]:
    """The local XML omits compiler angle=radian; authored 6.28319 is radian."""
    root = ET.parse(UR5E_CLASSES).getroot()
    classes = {node.attrib.get("class"): node for node in root.iter("default")}
    general = classes["ur5e"].find("joint")
    elbow = classes["size3_limited"].find("joint")
    if general is None or elbow is None:
        raise ValueError("UR5e authored joint ranges missing")
    def pair(node):
        return np.array([float(value) for value in node.attrib["range"].split()])
    return pair(general), pair(elbow)


def load_local(name: str) -> SixR:
    """Both reference files are existing local assets, not certified vendor CAD."""
    if name == "xarm6":
        xml, base, flange = XARM_XML, "left_base", "left_link6"
        joints = [f"left_joint_{i}" for i in range(1, 7)]
    elif name == "ur5e":
        xml, base, flange = UR5E_XML, "ur5e_base", "flange"
        joints = ["shoulder_pan_joint", "shoulder_lift_joint", "elbow_joint",
                  "wrist_1_joint", "wrist_2_joint", "wrist_3_joint"]
    else:
        raise ValueError(f"unknown local robot: {name}")
    if not xml.exists():
        raise FileNotFoundError(f"reference model missing: {xml}")
    model = mujoco.MjModel.from_xml_path(str(xml))
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)  # zero pose only; no mj_step
    base_id = model.body(base).id
    flange_id = model.body(flange).id
    base_pose = transform(data.xmat[base_id].reshape(3, 3), data.xpos[base_id])
    home_world = transform(data.xmat[flange_id].reshape(3, 3), data.xpos[flange_id])
    world_to_base = inverse(base_pose)
    axes, points, limits = [], [], []
    ur_general, ur_elbow = _ur5e_authored_limits() if name == "ur5e" else (None, None)
    for name_j in joints:
        joint_id = model.joint(name_j).id
        if model.jnt_type[joint_id] != mujoco.mjtJoint.mjJNT_HINGE:
            raise ValueError(f"{name_j} is not a hinge")
        axes.append(world_to_base[:3, :3] @ data.xaxis[joint_id])
        points.append((world_to_base @ np.r_[data.xanchor[joint_id], 1.0])[:3])
        if name == "ur5e":
            # MuJoCo converted the omitted compiler angle="radian" ranges from
            # degrees. For design screening use the radian values the file's
            # class definitions plainly author; keep this override explicit.
            limits.append(ur_elbow if name_j == "elbow_joint" else ur_general)
        elif model.jnt_limited[joint_id]:
            limits.append(model.jnt_range[joint_id])
        else:
            limits.append((-2 * np.pi, 2 * np.pi))
    return SixR(name, np.asarray(axes), np.asarray(points), world_to_base @ home_world,
                np.asarray(limits), f"local MJCF: {xml}; UR5e limit override from {UR5E_CLASSES}" if name == "ur5e" else f"local MJCF: {xml}")


def compare_mjcf_fk(name: str, q: np.ndarray) -> tuple[float, float]:
    """Return POE/MJCF flange position and rotation mismatch at q."""
    arm = load_local(name)
    if name == "xarm6":
        xml, base, flange = XARM_XML, "left_base", "left_link6"
        joints = [f"left_joint_{i}" for i in range(1, 7)]
    else:
        xml, base, flange = UR5E_XML, "ur5e_base", "flange"
        joints = ["shoulder_pan_joint", "shoulder_lift_joint", "elbow_joint",
                  "wrist_1_joint", "wrist_2_joint", "wrist_3_joint"]
    model = mujoco.MjModel.from_xml_path(str(xml))
    data = mujoco.MjData(model)
    for joint, angle in zip(joints, q):
        data.qpos[model.joint(joint).qposadr[0]] = angle
    mujoco.mj_forward(model, data)
    base_id, flange_id = model.body(base).id, model.body(flange).id
    base_pose = transform(data.xmat[base_id].reshape(3, 3), data.xpos[base_id])
    actual = np.linalg.inv(base_pose) @ transform(data.xmat[flange_id].reshape(3, 3), data.xpos[flange_id])
    predicted = arm.fk(q)
    return float(np.linalg.norm(actual[:3, 3] - predicted[:3, 3])), float(np.linalg.norm(actual[:3, :3] - predicted[:3, :3]))
