"""Architecture screening only: pocket packing, mass bookkeeping, ammo gravity.
Run from any directory; stdlib only. Not a contact or reliability simulation.
"""
import json, math
from pathlib import Path
HERE=Path(__file__).resolve().parent
cfg=json.loads((HERE.parent/'pick_place_study/config.json').read_text())
common=sum(r['kg'] for r in cfg['common_masses'])
rows=[]
for n in [6,10,12,15]:
    # 46 mm hole + 3 mm nominal minimum web, 27 mm radial allowance
    r=49/(2*math.sin(math.pi/n));outer=r+27
    rows.append(dict(slots=n,center_radius_mm=r,rotor_outer_diameter_mm=2*outer,
        ammunition_kg=n*cfg['ball_mass_kg'],
        approximate_combined_height_mm=max(131,2*r+27)+70))
# Illustrative vehicle pitch axis at X=-30,Z=0; magazine plane X=-120.
# Fire lowest pocket, index next down, with all remaining balls constrained.
loads=[]
for n in [10,12]:
    r=next(v['center_radius_mm'] for v in rows if v['slots']==n)
    values=[]
    for remaining in range(n+1):
        for deg in range(-15,46):
            a=math.radians(deg)
            torque=sum(cfg['ball_mass_kg']*9.81*((-120+30)*math.cos(a)-(r-r*math.cos(2*math.pi*i/n))*math.sin(a))/1000 for i in range(remaining))
            values.append(abs(torque))
    loads.append(dict(slots=n,ammo_only_max_pitch_gravity_nm=max(values),pitch_axis_xz_mm=[-30,0],pitch_range_deg=[-15,45]))
out=dict(date='2026-11-05',requirement=dict(source='https://bbs.robomaster.com/wiki/20204847/1970940?source=7',target_distance_m=3,target_rotation_rps_min_exclusive=.4,accuracy='Report hit rate, not ten guaranteed hits',manual_intervention=False,cadence='not specified on criteria page',minimum_test_shots=10,planning_capacity=12,installation_shot_inclusion='unconfirmed'),
    mass=dict(old_five_round_with_gripper_kg=2.9775,old_budget_plus_five_balls_only_kg=2.9775+5*cfg['ball_mass_kg'],
        common_head_budget_kg=common,ears_kg=.055,new_passive_feed_interface_assumed_kg=.12,
        transported_empty_head_budget_kg=common+.055+.12,with_gripper_kg=common+.055+.12+cfg['gripper_mass_kg'],
        interface_sensitivity_head_kg=[common+.055+x for x in [.08,.18]],
        notes='Reuses old launcher/core/frame/electronics budgets; no weighed or assigned-material mass. All ammo, indexing and pusher drives stay vehicle-side. Vehicle feed and pitch hardware must be budgeted separately.'),
    circular_packing=rows,ammo_pitch_loads=loads,
    rear_sweep_example=dict(pitch_axis_height_mm=380,chassis_deck_height_mm=250,rear_corner_relative_axis_xz_mm=[-215,-14],pitch_deg=45,corner_height_mm=380+(-215-14)/math.sqrt(2),minimum_axis_height_for_10mm_deck_clearance=260+(215+14)/math.sqrt(2),scope='One corner at one pose using old layout heights, not full collision validation.'),
    scope='Pocket geometry and ammo-only quasistatic gravity. Does not include rotor/motor/pusher/head mass in pitch load, feed contact, firing dynamics, CAD collisions, IK, stowage or rule approval.')
(HERE/'results.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(out,ensure_ascii=False,indent=2))
