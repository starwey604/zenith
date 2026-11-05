"""Camera + existing case layout arithmetic, not final manufacturing dimensions."""
from pathlib import Path
import json,math
HERE=Path(__file__).resolve().parent
out={
 'date':'2026-11-05','source':'references/camera.pdf, page 1, visually read',
 'camera':{'model':'DECXIN-3478V1','pcb_wh_mm':[32,32],'pcb_t_mm':1.6,'mount_pitch_mm':[28,28],'mount_hole_d_mm':2,'total_depth_mm':22.1,'total_depth_tolerance_mm':.2,'front_depth_callout_mm':20.3,'front_depth_tolerance_mm':.2,'lens_front_d_mm':17,'fpc_pins':22,'fpc_pitch_mm':.5,'fpc_contact':'bottom contact, flip lock','header':'3PIN 1.25, STRB/TRG/GND','fov_deg':{'H':112,'V':82.6,'D':123},'power_connector_pin1_label':'3.3V'},
 'layout':{'frame':'X lens forward, Y left, Z up, mm','case_bbox_mm':[[-81,-49.25,0],[0,49.25,34]],'case_transform_from_existing':'X=y-74; Y=42.25-x; Z=z+12.5 (rotation about Z -90deg)',
 'camera_pcb_back_x_mm':20,'camera_axis_yz_mm':[0,22],'camera_pcb_bbox_mm':[[20,-16,6],[21.6,16,38]],'camera_holes_yz_mm':[[-14,8],[-14,36],[14,8],[14,36]],'lens_front_x_mm':42.1,
 'planning_bbox_mm':[[-85,-53.25,-3],[45.3,53.25,41]],'planning_size_mm':[130.3,106.5,44],
 'cable_bay_mm':20,'notes':'20mm bay, frame allowance and guard are design assumptions; final cable length, minimum bend radius, connector body/lock and fastener head clearances not specified by this drawing.'},
 'guard':{'forward_extension_mm':3,'minimum_aperture_mm_conservative_using_17mm_lens_disc':[17+6*math.tan(math.radians(56)),17+6*math.tan(math.radians(41.3))],'proposed_aperture_mm':[30,28],'note':'Outer lens disc is a conservative geometric proxy, not measured entrance pupil. Check full image for vignetting.'},
 'unresolved':['Camera mass and backside component/connector height','Camera hole tolerances and component keep-outs around holes','22P camera to LBC3 CAM1 pin mapping and actual cable type','22.1 total versus 20.3 front-depth difference is 1.8, not PCB1.6; use total22.3 max for packaging and ask supplier for exact datum','Final fit with SM11 and magnetic keep-out regions','Actual lens position/entrance pupil, guard vignetting, cooling and loaded rigidity']}
(HERE/'layout.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
assert out['layout']['camera_pcb_bbox_mm'][0][2]>0
assert all(a>b for a,b in zip(out['guard']['proposed_aperture_mm'],out['guard']['minimum_aperture_mm_conservative_using_17mm_lens_disc']))
print('Planning envelope:',out['layout']['planning_size_mm'],'mm; guard opening:',out['guard'])
