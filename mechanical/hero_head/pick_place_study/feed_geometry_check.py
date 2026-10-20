"""Inspect potential trapping in the concept feed centreline; no contact model."""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
source = HERE / 'study.json'
study = json.loads(source.read_text())
rows = []
for c in study['candidates']:
    points = c['feed_route_mm']
    length = sum(math.dist(a, b) for a, b in zip(points, points[1:]))
    angles = []
    for pitch in [-15, 0, 15, 30, 45]:
        t = math.radians(pitch)
        # +pitch raises the muzzle (+head X), regardless of viewer conventions.
        heights = [p[0]*math.sin(t) + p[2]*math.cos(t) for p in points]
        angles.append(dict(pitch_deg=pitch,
            centreline_exit_above_lowest_point_mm=max(0, heights[-1]-min(heights)),
            final_segment_uphill=pitch>0))
    rows.append(dict(id=c['id'], route_length_mm=length,
        centreline_bend_radius_mm=None, pitches=angles,
        feed_actuation_coverage='Axial pusher follows the single ball to an assumed wheel-handoff centre at X=-8 mm; contact/drive implementation remains unresolved.'))
out = dict(date=study['date'], source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
    candidates=rows,
    interpretation='The axial line is uphill when the muzzle is raised. A following pusher is required; no gravity-only transport is assumed. This is a geometric review, not a jam probability or contact/rolling simulation.')
(HERE/'feed_review.json').write_text(json.dumps(out, ensure_ascii=False, indent=2)+'\n')
for row in rows:
    print(row['id'], 'centreline length', round(row['route_length_mm'],2), 'mm; +45deg exit rise', round(row['pitches'][-1]['centreline_exit_above_lowest_point_mm'],2), 'mm')
