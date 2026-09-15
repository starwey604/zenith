"""Analytic straight-slot/bayonet geometry, not contact-force physics."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import numpy as np


REQUIRED = {
    "guide": ("lead_cone_half_angle_rad", "lead_cone_depth_m", "mouth_radius_m",
              "key_start_angle_rad", "key_width_m"),
    "pins_and_slots": ("pin_count", "pin_circle_radius_m", "pin_radius_m",
                       "straight_slot_width_m", "straight_slot_length_m", "stop_depth_m",
                       "turn_channel_width_m", "turn_channel_axial_min_m", "turn_channel_axial_max_m",
                       "lock_turn_angle_rad", "turn_direction_sign", "shoulder_overlap_m"),
    "tolerances": ("axis_lateral_error_m", "axis_angle_error_rad", "key_phase_error_rad",
                   "seat_depth_error_m", "lock_angle_error_rad", "collision_margin_m"),
}


@dataclass(frozen=True)
class Bayonet:
    data: dict

    @classmethod
    def load(cls, path: str | Path) -> "Bayonet":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        missing = [f"{group}.{field}" for group, fields in REQUIRED.items()
                   for field in fields if data.get(group, {}).get(field) is None]
        if missing:
            raise ValueError("missing_input: " + ", ".join(missing))
        if data.get("mechanism") != "straight_slot_bayonet" or data.get("assembly_mode") != "table_supported_flange_turn":
            raise ValueError("unsupported interface/mode")
        p, g, t = data["pins_and_slots"], data["guide"], data["tolerances"]
        if not isinstance(p["pin_count"], int) or p["pin_count"] < 1 or p["turn_direction_sign"] not in (-1, 1):
            raise ValueError("invalid pin count or turn direction")
        if not 0 < g["lead_cone_half_angle_rad"] < np.pi / 2:
            raise ValueError("guide cone half-angle must be between 0 and pi/2")
        if g["lead_cone_depth_m"] <= 0 or g["mouth_radius_m"] <= 0 or g["key_width_m"] <= 0:
            raise ValueError("invalid guide dimensions")
        if any(value < 0 for value in t.values()) or any(key not in t for key in REQUIRED["tolerances"]):
            raise ValueError("tolerances must be nonnegative")
        if any(p[key] <= 0 for key in ("pin_circle_radius_m", "pin_radius_m", "straight_slot_width_m",
                                       "straight_slot_length_m", "stop_depth_m", "turn_channel_width_m",
                                       "lock_turn_angle_rad", "shoulder_overlap_m")):
            raise ValueError("invalid nonpositive bayonet dimension")
        if not 0 < p["stop_depth_m"] <= p["straight_slot_length_m"]:
            raise ValueError("stop must be within straight slot")
        if not 0 < p["lock_turn_angle_rad"] < np.pi:
            raise ValueError("current bayonet phase representation requires turn < pi")
        if g["mouth_radius_m"] <= p["stop_depth_m"] * np.tan(g["lead_cone_half_angle_rad"]):
            raise ValueError("guide cone envelope closes before stop")
        if not p["turn_channel_axial_min_m"] <= p["stop_depth_m"] <= p["turn_channel_axial_max_m"]:
            raise ValueError("stop must meet turn channel")
        if p["straight_slot_width_m"] < 2 * p["pin_radius_m"] + 2 * t["collision_margin_m"]:
            raise ValueError("pin cannot fit straight slot with margin")
        if p["turn_channel_width_m"] < 2 * p["pin_radius_m"] + 2 * t["collision_margin_m"]:
            raise ValueError("pin cannot fit turn channel with margin")
        if g["key_width_m"] < 2 * p["pin_radius_m"] + 2 * t["collision_margin_m"]:
            raise ValueError("pin cannot fit key entrance")
        return cls(data)

    @property
    def stop_m(self) -> float:
        return float(self.data["pins_and_slots"]["stop_depth_m"])

    @property
    def lock_angle_rad(self) -> float:
        p = self.data["pins_and_slots"]
        return float(p["turn_direction_sign"] * p["lock_turn_angle_rad"])

    def check_pose(self, relative: np.ndarray, phase: str) -> tuple[bool, str, dict]:
        """T_D_M: mouth at z=0, insertion along -z, positive angle about +z."""
        p, g, t = self.data["pins_and_slots"], self.data["guide"], self.data["tolerances"]
        s = -float(relative[2, 3])
        theta = float(np.arctan2(relative[1, 0], relative[0, 0]))
        lateral = float(np.linalg.norm(relative[:2, 3]))
        tilt = float(np.arccos(np.clip(relative[2, 2], -1, 1)))
        metrics = {"depth_m": s, "phase_rad": theta, "lateral_m": lateral, "tilt_rad": tilt,
                   "shoulder_overlap_m": float(p["shoulder_overlap_m"])}
        if lateral > t["axis_lateral_error_m"] or tilt > t["axis_angle_error_rad"]:
            return False, "axis_misaligned", metrics
        # Central-pilot entrance envelope. The real nose radius is unknown;
        # this is only a lateral-centre bound, not a contact solution.
        cone_radius = g["mouth_radius_m"] - max(0.0, s) * np.tan(g["lead_cone_half_angle_rad"])
        if cone_radius < 0 or lateral > cone_radius:
            return False, "cone_interference", metrics
        start = float(g["key_start_angle_rad"])
        angle_from_key = theta - start
        pin_sweep = p["pin_circle_radius_m"] * abs(np.sin(angle_from_key))
        tilt_sweep = p["pin_circle_radius_m"] * abs(np.sin(tilt))
        straight_clearance = (p["straight_slot_width_m"] / 2
                              - p["pin_radius_m"] - t["collision_margin_m"])
        key_clearance = g["key_width_m"] / 2 - p["pin_radius_m"] - t["collision_margin_m"]
        channel_clearance = (p["turn_channel_width_m"] / 2
                             - p["pin_radius_m"] - t["collision_margin_m"])
        if phase in ("approach", "cone_align", "key_align"):
            if s > t["seat_depth_error_m"]:
                return False, "premature_insert", metrics
            if s < -g["lead_cone_depth_m"]:
                return False, "outside_guide", metrics
            if phase == "key_align" and abs(angle_from_key) > t["key_phase_error_rad"]:
                return False, "key_misaligned", metrics
            if phase == "key_align" and lateral + pin_sweep + tilt_sweep > key_clearance:
                return False, "key_interference", metrics
        elif phase == "straight_insert":
            if not -t["seat_depth_error_m"] <= s <= self.stop_m + t["seat_depth_error_m"]:
                return False, "slot_depth", metrics
            if abs(angle_from_key) > t["key_phase_error_rad"]:
                return False, "premature_turn", metrics
            if lateral + pin_sweep + tilt_sweep > straight_clearance:
                return False, "slot_interference", metrics
        elif phase in ("bayonet_turn", "locked"):
            if not p["turn_channel_axial_min_m"] <= s <= p["turn_channel_axial_max_m"]:
                return False, "premature_turn", metrics
            signed = p["turn_direction_sign"] * angle_from_key
            if not -t["lock_angle_error_rad"] <= signed <= p["lock_turn_angle_rad"] + t["lock_angle_error_rad"]:
                return False, "outside_turn_channel", metrics
            if lateral + tilt_sweep > channel_clearance:
                return False, "slot_interference", metrics
            if phase == "locked" and abs(signed - p["lock_turn_angle_rad"]) > t["lock_angle_error_rad"]:
                return False, "not_locked", metrics
            if phase == "locked" and p["shoulder_overlap_m"] <= t["collision_margin_m"]:
                return False, "no_shoulder_coverage", metrics
        else:
            raise ValueError(f"unknown phase: {phase}")
        return True, "ok", metrics

    def straight_pull_allowed(self, relative: np.ndarray) -> bool:
        """Shape proxy: a locked pin cannot exit axially without reverse rotation."""
        valid, _, _ = self.check_pose(relative, "locked")
        return not valid
