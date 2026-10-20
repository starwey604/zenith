"""Layout budgets for a passive head, dedicated gripper and chassis-side seat.

Standard library only. Dimensions use the actual retained reference mesh bounds;
new parts are layout geometry, not a contact/strength/IK simulation.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from axial_feed import dimensions as axial_dimensions, frame as axial_frame

HERE = Path(__file__).resolve().parent
MESHES = HERE.parent / 'magazine_study/assets/reference_meshes.json'


def box(name, size, at, role='structure'):
    return dict(name=name, shape='box', size=size, at=at, role=role)


def cylinder(name, radius, height, at, role='structure', axis='z'):
    return dict(name=name, shape='cylinder', radius=radius, height=height, at=at, role=role, axis=axis)


def bounds(part):
    if part['shape'] == 'box':
        half = [v / 2 for v in part['size']]
    else:
        half = [part['radius']] * 3
        half['xyz'.index(part['axis'])] = part['height'] / 2
    return [[x - d for x, d in zip(part['at'], half)], [x + d for x, d in zip(part['at'], half)]]


def mesh_bounds(parts, shift=(0, 0, 0)):
    v = [p['vertices'] for p in parts]
    return [[min(min(a[k::3]) for a in v) + shift[k] for k in range(3)],
            [max(max(a[k::3]) for a in v) + shift[k] for k in range(3)]]


def union(boxes):
    return [[min(b[0][k] for b in boxes) for k in range(3)],
            [max(b[1][k] for b in boxes) for k in range(3)]]


def balls(c):
    x, y, z = c['rotor_center_mm']
    r, n = c['radius_mm'], c['slots']
    return [[x, y+r*math.sin(i*2*math.pi/n), z-r*math.cos(i*2*math.pi/n)] for i in range(n)]


def common_parts(c):
    rear = c.get('layout_rear_mm',c['rotor_center_mm'][0] - c['outer_radius_mm'])
    parts = []
    for y in [-62, 62]:
        parts.append(box('骨架纵梁', [110 - rear, 6, 6], [(rear + 110) / 2, y, -40]))
    for x in [rear + 14, 94]:
        for y in [-62, 62]:
            parts.append(cylinder('桌面支脚', 7, 24, [x, y, -58]))
    parts.append(box('视觉桥架', [110, 90, 3], [65, 0, 59], 'electronics'))
    for y in [-47, 47]:
        parts += [box('桥架横梁', [125, 6, 5], [62, y, 53]), box('桥架支柱', [6, 6, 24], [10, y, 42])]
    parts += [box('相机占位', [28, 30, 28], [110, 0, 117], 'electronics'), cylinder('镜头占位', 10, 13, [130, 0, 117], 'electronics', 'x')]
    # The underside is a frame, not a solid metal slab through the launcher.
    for y in [-42, 42]:
        parts.append(box('底部被动框', [110, 6, 5], [-15, y, -50], 'interface'))
    for x in [-67, 37]:
        parts.append(box('底部被动框', [6, 78, 5], [x, 0, -50], 'interface'))
    parts.append(box('框内承力横梁', [8, 78, 5], [-15, 0, -50], 'interface'))
    for x, y in [(-52, -30), (-52, 30), (22, 0)]:
        parts.append(cylinder('三点承压面', 7, 4, [x, y, -54.5], 'interface'))
    for y in [-29, 29]:
        parts += [cylinder('被动拉紧销', 3, 11, [-15, y, -58], 'interface'), cylinder('拉紧销头', 6, 3, [-15, y, -64], 'interface')]
    for x in [-52, 22]:
        parts.append(box('定位键占位', [12, 8, 7], [x, 0, -55], 'interface'))
    for y in [-68, 68]:
        parts += [box('承重耳', [44, 18, 6], [-12, y, 64], 'grasp'), box('承重耳根', [8, 8, 18], [-12, y, 52], 'grasp')]
    return parts


def magazine_parts(c):
    x, y, z = c['rotor_center_mm']
    r = c['outer_radius_mm']
    parts = []
    d=c['axial_metrics'];home=d['home_face_x_mm'];length=d['stage_length_mm']
    parts += [cylinder('轴向后限位板',r+2,3,[x-27.5,0,z],'magazine','x'), cylinder('轴向前限位板',r+2,3,[x+26.5,0,z],'shell','x')]
    parts += [box('二级推送固定壳',[length,24,24],[home-length/2,0,0],'drive'), box('推送尾盖',[3,28,28],[home-length-1.5,0,0],'drive'),box('推送电机占位',[36,28,32],[home-61,30,0],'drive'),box('同步传动预留',[length,6,6],[home-length/2,17,14],'drive')]
    parts.append(cylinder('轴向分度驱动占位',18,30,[x-46,0,z],'drive','x'))
    parts.append(box('断电定位占位',[17,10,13],[x-24,48,88],'drive'))
    for y in [-56,56]:parts.append(box('后板支撑',[6,6,64],[x-28,y,-5]))
    for zz in [-28,28]:parts.append(box('止弹片导向架',[8,66,6],[x+23,0,zz],'structure'))
    # The closed sliding gate is rendered separately as a moving part.
    parts.append(box('常闭止弹片',[3,46,46],[x+23.5,0,0],'gate'))
    parts.append(box('止弹驱动与弹簧占位',[24,18,18],[x+23,56,28],'drive'))
    parts.append(cylinder('直导路占位',25.5,59,[-65.5,0,0],'guide','x'))
    return parts


def feed_route(c):
    # The lowest pocket faces the straight launcher inlet.
    x, _, _ = balls(c)[0]
    return [[x,0,0],[-36,0,0],[-30,0,0]]


def weighted(rows):
    mass = sum(r['kg'] for r in rows)
    return mass, [sum(r['kg'] * r['center_mm'][k] for r in rows) / mass for k in range(3)]


def build():
    cfg = json.loads((HERE / 'config.json').read_text())
    meshes = json.loads(MESHES.read_text())
    retained = [p for p in meshes['launcher'] if (int(p['name'].replace('Ref_', '')) >= 1197 or p['name'] == 'Ref_1187') and p['name'] != 'Ref_1265']
    source_bounds = [mesh_bounds(retained), mesh_bounds(meshes['case'], (25.75, -33.5, 75.5))]
    candidates = []
    for base in cfg['candidates']:
        c = dict(base)
        c['axial_metrics']=axial_dimensions(c,cfg)
        c['layout_rear_mm']=c['axial_metrics']['rear_extent_x_mm']
        c['feed_cycle_cases']=[axial_frame(p,c,cfg) for p in range(101)]
        c['parts'] = common_parts(c) + magazine_parts(c)
        c['ball_centers_mm'] = balls(c)
        c['feed_route_mm'] = feed_route(c)
        # Hull includes a 2 mm outside wall and 25.5 mm outer feed tube.
        route_boxes = [[[p[k] - 25.5 for k in range(3)], [p[k] + 25.5 for k in range(3)]] for p in c['feed_route_mm']]
        rotor_half = [c['rotor_depth_mm']/2,c['outer_radius_mm'],c['outer_radius_mm']]
        center = c['rotor_center_mm']
        rotor_box = [[center[k] - rotor_half[k] for k in range(3)], [center[k] + rotor_half[k] for k in range(3)]]
        b = union(source_bounds + [bounds(p) for p in c['parts']] + route_boxes + [rotor_box])
        size = [b[1][k] - b[0][k] for k in range(3)]
        rows = [dict(r) for r in cfg['common_masses']]
        rows += c['feed_masses']
        rows += c.get('extra_masses',[])
        rows.append(dict(name='专用抓取部位', kg=c['grip_mass_kg'], center_mm=c['grip_point_mm']))
        for i, p in enumerate(c['ball_centers_mm'][:c['ammo']]):
            rows.append(dict(name=f'弹丸{i+1}', kg=cfg['ball_mass_kg'], center_mm=p))
        mass, cg = weighted(rows)
        palm = c['wrist_point_mm']
        delta = [(cg[k] - palm[k]) / 1000 for k in range(3)]
        distances = [math.dist(a, b) for i, a in enumerate(c['ball_centers_mm']) for b in c['ball_centers_mm'][i+1:]]
        rear_foot = c.get('layout_rear_mm',center[0] - c['outer_radius_mm']) + 14
        margin = min(cg[0] - rear_foot, 94 - cg[0], 62 - abs(cg[1]))
        c['mass_rows'] = rows
        c['metrics'] = dict(bounds_mm=b, size_mm=size, bounding_volume_l=math.prod(size)/1e6,
            module_mass_kg=mass, gripper_plus_module_kg=mass+cfg['gripper_mass_kg'], cg_mm=cg,
            horizontal_wrist_gravity_nm=mass*9.81*math.hypot(delta[0],delta[1]),
            any_tilt_wrist_gravity_bound_nm=mass*9.81*math.sqrt(sum(d*d for d in delta)),
            pocket_center_spacing_mm=min(distances), pocket_web_mm=min(distances)-cfg['pocket_diameter_mm'],
            ball_surface_gap_at_max_size_mm=min(distances)-cfg['ball_max_diameter_mm'],
            static_level_support_margin_mm=margin,
            fixed_pose_under_400_mm=max(size)<=400,
            table_outer_fit_fixed_pose=size[0]<=750 and size[1]<=450,
            foot_centers_mm=[[x,y,-70] for x in [rear_foot,94] for y in [-62,62]])
        assert c['metrics']['pocket_web_mm'] >= 3 - 1e-9
        assert margin > 0
        assert c['metrics']['fixed_pose_under_400_mm']
        assert c['ammo'] <= c['slots']
        assert abs(c['feed_route_mm'][-2][0] + 36) < 1e-8
        c['axial_metrics']['single_stage_total_length_mm']=source_bounds[0][1][0]-c['axial_metrics']['single_stage_rod_rear_x_mm']
        c['axial_metrics']['storage_length_margin_mm']=400-size[0]
        candidates.append(c)
    out = dict(schema_version=1, date=cfg['date'], config=cfg, candidates=candidates,
        sources={str(MESHES.relative_to(HERE.parents[2])): hashlib.sha256(MESHES.read_bytes()).hexdigest(),
                 'config_sha256': hashlib.sha256((HERE/'config.json').read_bytes()).hexdigest()},
        checks=dict(pocket_geometry=True, fixed_pose_under_400=True, level_cg_inside_feet=True,
                    source_meshes_in_bounds=True, full_assembly_collision=False, arm_ik=False,
                    feed_contact_simulation=False, locking_strength=False),
        scope='Reference mesh + concept layout. Bounding volume is an AABB, not material volume. Masses are replaceable budgets. Flat static CG support only; no dynamic tabletop stability claim.')
    (HERE/'study.json').write_text(json.dumps(out, ensure_ascii=False, indent=2)+'\n')
    for c in candidates:
        m=c['metrics']
        print(c['id'], ' / '.join([f"{' × '.join(f'{v:.1f}' for v in m['size_mm'])} mm", f"{m['bounding_volume_l']:.2f} L", f"head {m['module_mass_kg']:.3f} kg", f"with gripper {m['gripper_plus_module_kg']:.3f} kg", f"web {m['pocket_web_mm']:.2f} mm"]))


if __name__ == '__main__':
    build()
