"""Geometry and illustrative sequencing for an axial five-pocket feeder.

This is a packaging and clearance budget. Telescopic transmission, friction,
compliance, tolerances, contact and motor sizing remain unresolved.
"""
from __future__ import annotations
import math


def dimensions(c, cfg):
    p = c['axial']
    ball_r = cfg['ball_diameter_mm'] / 2
    x = c['rotor_center_mm'][0]
    home = p['pusher_home_face_x_mm']
    end = p['handoff_ball_center_x_mm'] - ball_r
    stroke = end - home
    extension = stroke / 2
    overlap = p['stage_length_mm'] - extension
    rear = home - p['stage_length_mm'] - p['rear_cap_mm']
    # Treat the two reference contact wheels as circles in XY; this only locates
    # the unloaded first contact, and is not a rubber deformation model.
    wheel_r = 30
    wheel_half_spacing = 49
    contact = -math.sqrt((wheel_r + ball_r)**2 - wheel_half_spacing**2)
    rear_face = x - 29
    d = dict(home_face_x_mm=home, end_face_x_mm=end, stroke_mm=stroke,
        stage_length_mm=p['stage_length_mm'], each_stage_extension_mm=extension,
        remaining_overlap_mm=overlap, rear_extent_x_mm=rear,
        single_stage_rod_rear_x_mm=home - stroke - p['minimum_overlap_mm'] - p['rear_cap_mm'],
        retracted_tip_to_rear_cover_mm=rear_face-home,
        initial_ball_back_to_home_tip_mm=x-ball_r-home,
        ball_travel_mm=p['handoff_ball_center_x_mm']-x,
        centreline_guide_length_mm=p['guide_end_x_mm']-p['guide_start_x_mm'],
        unloaded_wheel_first_contact_ball_x_mm=contact,
        ball_travel_after_first_wheel_contact_mm=p['handoff_ball_center_x_mm']-contact,
        gate_closed_y_mm=0, gate_open_y_mm=p['gate_travel_mm'],
        gate_clearance_when_open_mm=p['gate_travel_mm']-23-23,
        maximum_pitch_gravity_component_n=cfg['ball_mass_kg']*9.81*math.sin(math.radians(45)),
        notes='Two equal extension stages with assumed downward flange; no actuator product selected. First wheel contact ignores deformation and detailed U-groove profile. Gravity component excludes friction/retention force and is not actuator sizing.')
    assert overlap >= p['minimum_overlap_mm']
    assert d['retracted_tip_to_rear_cover_mm'] >= 4
    assert d['gate_clearance_when_open_mm'] > 0
    assert p['handoff_ball_center_x_mm'] > contact
    return d


def smooth(t):
    t=max(0,min(1,t))
    return t*t*(3-2*t)


def frame(progress, c, cfg):
    """Sensor confirmations are assumed milestones, not simulated feedback."""
    d = dimensions(c,cfg)
    t = max(0,min(1,progress/100))
    stroke, gate, angle, phase, present = 0., 0., 0., 0, True
    if t < .12:
        angle=-72*(1-smooth(t/.12))
    elif t < .23:
        phase=1;gate=smooth((t-.12)/.11)
    elif t < .61:
        phase=2;gate=1.;stroke=d['stroke_mm']*smooth((t-.23)/.38)
    elif t < .70:
        phase=3;gate=1.;stroke=d['stroke_mm'];present=t<.67
    elif t < .88:
        phase=4;gate=1.;present=False;stroke=d['stroke_mm']*(1-smooth((t-.70)/.18))
    elif t < .94:
        phase=5;present=False;gate=1-smooth((t-.88)/.06)
    else:
        phase=6;present=False;angle=72*smooth((t-.94)/.06)
    return dict(progress=progress,phase=phase,stroke_mm=stroke,gate_open_fraction=gate,
        rotor_angle_deg=angle,ball_present=present,
        ball_center_x_mm=max(c['rotor_center_mm'][0],d['home_face_x_mm']+stroke+cfg['ball_diameter_mm']/2),
        pusher_home=stroke<=1e-8,gate_closed=gate<=1e-8,
        indexing_allowed=stroke<=1e-8 and gate<=1e-8,
        confirmations='illustrative assumed milestones; no sensing/contact simulation')
