"""Rebuild the first camera/LBC3 mechanical prototype in FreeCAD.
Script-parametric BRep parts; camera is drawing-based reference, adapter real STEP.
Original enclosure is never overwritten. Dimensions in mm.
"""
import FreeCAD as A,Part,MeshPart,json,math
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];V=A.Vector
P=dict(m3_clear=3.4,camera_screw_clear=1.8,adapter_board_z=.85,camera_shift_x=2.,camera_raise_z=8.,cable_radius=5.,cable_width=12.,cable_thickness=.3)
OUT=HERE/'exports/v2';OUT.mkdir(parents=True,exist_ok=True)

def box(x0,y0,z0,x1,y1,z1):return Part.makeBox(x1-x0,y1-y0,z1-z0,V(x0,y0,z0))
def cyl(r,h,p,axis=(0,0,1)):return Part.makeCylinder(r,h,V(*p),V(*axis))
def fuse(parts):return parts[0].multiFuse(parts[1:]).removeSplitter() if len(parts)>1 else parts[0]
def holeZ(s,x,y,d,z=-4,h=12):return s.cut(cyl(d/2,h,(x,y,z)))
def bx(s):
 b=s.BoundBox;return [b.XMin,b.YMin,b.ZMin,b.XMax,b.YMax,b.ZMax]
def transformed(s):
 s=s.copy();s.Placement=A.Placement(V(-74,42.25,12.5),A.Rotation(V(0,0,1),-90)).multiply(s.Placement);return s

src=A.openDocument(str(ROOT/'mechanical/lbc3_case_v1/lbc3_case_v1.FCStd'))
ad=Part.Shape();ad.read(str(ROOT/'mechanical/steps/CamAdaptor.step'))
ad.translate(V(39.614,54.239,P['adapter_board_z']))
oldbase=src.getObject('CASE_base').Shape.copy()
# Remove previous wide support; actual bottom-side SMT occupies this volume.
old_ledge=box(29,61,-9.499,50,64,.6)
old_interference=old_ledge.common(ad).Volume
base=oldbase.cut(old_ledge)
for xx in [28,49]:base=base.fuse(box(xx,64.7,-9.5,xx+2,65.2,.6))
base=transformed(base)
# Bottom-only ears: no use of lid screws as robot mounting fasteners.
mounts=[(x,y)for x in [-86,5]for y in [-40,40]]
for x,y in mounts:
 base=base.fuse(box(x-9 if x>0 else x-4,y-6,0,x+5 if x>0 else x+9,y+6,3))
 base=holeZ(base,x,y,P['m3_clear'])
base=base.removeSplitter()
frame=fuse([box(-92,-53.25,-3,36,-43,0),box(-92,43,-3,36,53.25,0),box(-92,-53.25,-3,-80,53.25,0),box(-2,-53.25,-3,10,53.25,0),box(8,-30,-3,36,30,0)])
for x,y in mounts+[(22,-20),(22,20),(30,-20),(30,20)]:frame=holeZ(frame,x,y,P['m3_clear'])
# Two independent holes for mounting the entire module to a head-side bridge.
for x in [-60,-25]:
 for y in [-48,48]:frame=holeZ(frame,x,y,P['m3_clear'])
frame=frame.removeSplitter()
# Camera rear carrier: posts outside PCB keep-out; five small corner lands.
carrier=[box(8,-25,0,26,-15,4),box(8,15,0,26,25,4),box(16,-22,3,19,-18,42),box(16,18,3,19,22,42),box(16,-22,39,19,22,42)]
for y in [-14,14]:
 for z in [8,36]:
  carrier.append(box(16,min(y-2,18 if y>0 else -22),z-2,19,max(y+2,22 if y>0 else -18),z+2))
  carrier.append(cyl(2,1,(19,y,z),(1,0,0)))
for y in [-21,18]:
 wire=Part.makePolygon([V(8,y,4),V(16,y,25),V(16,y,4),V(8,y,4)])
 carrier.append(Part.Face(wire).extrude(V(0,3,0)))
carrier=fuse(carrier)
for y in [-14,14]:
 for z in [8,36]:carrier=carrier.cut(cyl(P['camera_screw_clear']/2,8,(14,y,z),(1,0,0)))
for y in [-20,20]:carrier=holeZ(carrier,22,y,P['m3_clear'])
carrier=carrier.removeSplitter()
# Guard, removable without touching camera location screws. Broad 30x28 aperture.
guard=fuse([box(26,-25,0,36,-15,3),box(26,15,0,36,25,3),box(26,-22,3,45.3,-19,43),box(26,19,3,45.3,22,43),box(43,-22,1,45.3,22,43)])
guard=guard.cut(box(42.9,-15,8,45.4,15,36))
for y in [-20,20]:guard=holeZ(guard,30,y,P['m3_clear'])
guard=guard.removeSplitter()
# Drawing-based camera. Backside connector is separately shown as a keep-out.
pcb=box(20,-16,6,21.6,16,38)
for y in [-14,14]:
 for z in [8,36]:pcb=pcb.cut(cyl(1,3,(19.5,y,z),(1,0,0)))
lens=fuse([box(21.6,-8.5,13.5,30,8.5,30.5),cyl(8.5,12.1,(30,0,22),(1,0,0))])

# V2: align the camera to the actual adapter's FPC centreline.
DY=42.25-((5.123-5.377)/2+39.614)
DX=P['camera_shift_x'];DZ=P['camera_raise_z']
# Translate only upper camera mounting geometry, keeping the feet on the frame.
# Rebuild its taller posts/gussets directly rather than scaling hole pitches.
carrier_parts=[box(10,-25,0,28,-15,4),box(10,15,0,28,25,4),box(18,-22,3,21,-18,50),box(18,18,3,21,22,50),box(18,-22,47,21,22,50)]
for y in [-14,14]:
 for z in [16,44]:
  carrier_parts.append(box(18,min(y-2,18 if y>0 else -22),z-2,21,max(y+2,22 if y>0 else -18),z+2))
  carrier_parts.append(cyl(2,1,(21,y,z),(1,0,0)))
for y in [-21,18]:
 w=Part.makePolygon([V(10,y,4),V(18,y,33),V(18,y,4),V(10,y,4)])
 carrier_parts.append(Part.Face(w).extrude(V(0,3,0)))
# Fixed camera-end cable saddle below the PCB, with support outside the ribbon.
carrier_parts.append(box(17,-22,9,19.5,22,13))
carrier=fuse(carrier_parts)
for y in [-14,14]:
 for z in [16,44]:carrier=carrier.cut(cyl(.9,8,(16,y,z),(1,0,0)))
for y in [-20,20]:carrier=holeZ(carrier,24,y,3.4)
for y in [-9.5,9.5]:carrier=carrier.cut(cyl(.7,2.5,(17.5,y,11),(1,0,0)))
carrier.translate(V(0,DY,0));carrier=carrier.removeSplitter()
guard=fuse([box(28,-30,0,38,-18,3),box(28,18,0,38,30,3),box(28,-22,3,47.3,-19,51),box(28,19,3,47.3,22,51),box(45,-22,1,47.3,22,51)])
guard=guard.cut(box(44.9,-15,16,47.4,15,44))
for y in [-26.5,26.5]:guard=holeZ(guard,32,y,3.4)
guard.translate(V(0,DY,0));guard=guard.removeSplitter()
pcb.translate(V(DX,DY,DZ));lens.translate(V(DX,DY,DZ))
# Replace the frame front panel and fixings, leaving case mounts unchanged.
frame=fuse([box(-92,-53.25,-3,38,-43,0),box(-92,43,-3,38,53.25,0),box(-92,-53.25,-3,-80,53.25,0),box(-2,-53.25,-3,10,53.25,0),box(8,-30,-3,38,33,0)])
for x,y in mounts+[(24,DY-20),(24,DY+20),(32,DY-26.5),(32,DY+26.5),(5,DY-16),(5,DY+16)]+[(x,y)for x in[-60,-25]for y in[-48,48]]:frame=holeZ(frame,x,y,3.4)
frame=frame.removeSplitter()
# Case-exit saddle and replaceable soft-jaw clamp.
exit_saddle=fuse([box(.5,DY-20,0,9,DY-12,3),box(.5,DY+12,0,9,DY+20,3),box(.5,DY-12,2,4.5,DY-8,15.1),box(.5,DY+8,2,4.5,DY+12,15.1),box(0,DY-12,14.1,4,DY+12,15.1)])
exit_jaw=box(0,DY-12,15.9,4,DY+12,17.9)
for y in [DY-9.5,DY+9.5]:
 exit_saddle=exit_saddle.cut(cyl(.7,3,(2,y,12.2)))
 exit_jaw=holeZ(exit_jaw,2,y,1.8,z=15.8,h=2.3)
for y in [DY-16,DY+16]:exit_saddle=holeZ(exit_saddle,5,y,3.4)
exit_saddle=exit_saddle.removeSplitter()
cam_jaw=box(20.5,DY-12,9,21.8,DY+12,13)
for y in [DY-9.5,DY+9.5]:cam_jaw=cam_jaw.cut(cyl(.9,2,(20.3,y,11),(1,0,0)))
# Free cable span: connector insertion lengths are not included.
v=lambda x,z:V(x,DY,z)
edges=[Part.makeLine(v(-9,15.5),v(5,15.5)),Part.Arc(v(5,15.5),v(5+5/math.sqrt(2),10.5+5/math.sqrt(2)),v(10,10.5)).toShape(),Part.makeLine(v(10,10.5),v(10,8)),Part.Arc(v(10,8),v(15,3),v(20,8)).toShape(),Part.makeLine(v(20,8),v(20,14))]
path=Part.Wire(edges)
profile=Part.Wire(Part.makePolygon([V(-9,DY-6,15.35),V(-9,DY+6,15.35),V(-9,DY+6,15.65),V(-9,DY-6,15.65),V(-9,DY-6,15.35)]).Edges)
cable=path.makePipeShell([profile],True,False)
D=A.newDocument('CameraLBC3CableV2')
parts={};refs={}
def add(name,s,color,role='new',transparency=0):
 o=D.addObject('Part::Feature',name);o.Shape=s;o.addProperty('App::PropertyString','SourceRole').SourceRole=role
 if o.ViewObject:o.ViewObject.ShapeColor=color;o.ViewObject.Transparency=transparency
 (parts if role=='new' else refs)[name]=o
 return o
press=box(33,47.2,3.4,46,50.4,8.5)
for x in [34.6,44.4]:press=press.cut(cyl(.85,3.6,(x,48.8,5)))
press=transformed(press.removeSplitter())
add('NEW_AdapterRetainer',press,(.78,.48,.24))
add('REF_AdapterFoamCompressed',transformed(box(34.5,47.2,ad.Solids[0].BoundBox.ZMax,44.4,50.4,3.4)),(.85,.76,.36),'assumed compressed pad')
add('NEW_ExitSaddle',exit_saddle,(.53,.59,.65))
add('NEW_ExitJaw',exit_jaw,(.53,.59,.65))
add('NEW_CameraCableJaw',cam_jaw,(.53,.59,.65))
add('NEW_CommonFrame',frame,(.35,.45,.55))
add('NEW_CaseBaseWithEars',base,(.65,.79,.76))
add('NEW_CameraCarrier',carrier,(.8,.57,.25))
add('NEW_RemovableGuard',guard,(.33,.52,.7))
for o in src.Objects:
 if not hasattr(o,'Shape') or o.Shape.isNull() or o.Name in ['CASE_base','REF_cam1_adapter','REF_AXE630124D','REF_FPC30']:continue
 add(o.Name,transformed(o.Shape),(.48,.69,.65),'existing case/reference',60 if o.Name=='CASE_lid' else 15)
add('REF_ActualCAM1Adapter',transformed(ad),(.23,.58,.25),'actual STEP')
add('REF_CameraPCB',pcb,(.21,.45,.27),'drawing-based envelope')
add('REF_LensEnvelope',lens,(.2,.22,.24),'drawing-based envelope')
add('KEEP_CameraFPCAndFlipLock',box(15,DY-8,14,22,DY+8,20),(.82,.6,.25),'assumed service keep-out',70)
add('KEEP_CameraTriggerPins',box(16,DY+10,20,22,DY+16,29),(.82,.6,.25),'assumed service keep-out',70)
# Adjustable cable clamp pair at the fixed PCB-board side, not on B2B contacts.
# No clamp exported until actual FPC thickness/bend/cover latch are known.
add('REF_FPCRoute_Assumed',cable,(.82,.59,.22),'assumed cable free span')
D.addObject('App::FeaturePython','DesignParameters')
po=D.getObject('DesignParameters')
for k,v in P.items():po.addProperty('App::PropertyFloat',k,'RebuildParameters');setattr(po,k,v);po.setEditorMode(k,1)
po.addProperty('App::PropertyString','RebuildScript').RebuildScript=str(HERE/'build.py')
D.recompute()
checks={}
for n,o in parts.items():
 assert o.Shape.isValid() and len(o.Shape.Solids)==1,(n,len(o.Shape.Solids))
 checks[n]=dict(valid=True,solids=len(o.Shape.Solids),volume_mm3=o.Shape.Volume,bounds_mm=bx(o.Shape))
collisions=[]
realrefs={n:o for n,o in refs.items() if not n.startswith('KEEP_')}
items=list(parts.items())
for i,(n,o) in enumerate(items):
 for m,t in items[i+1:]+list(realrefs.items()):
  v=o.Shape.common(t.Shape).Volume
  if v>1e-5:collisions.append(dict(a=n,b=m,volume_mm3=v))
keep_collisions=[]
for n,o in parts.items():
 for m,t in refs.items():
  if m.startswith('KEEP_'):
   v=o.Shape.common(t.Shape).Volume
   if v>1e-5:keep_collisions.append(dict(a=n,b=m,volume_mm3=v))
adapter_ref_intersections=[]
for n,o in realrefs.items():
 if n in ['REF_ActualCAM1Adapter','REF_FPCRoute_Assumed']:continue
 v=realrefs['REF_ActualCAM1Adapter'].Shape.common(o.Shape).Volume
 if v>1e-5:adapter_ref_intersections.append(dict(other=n,volume_mm3=v))
cable_hits=[]
for n,o in list(parts.items())+list(realrefs.items()):
 if n=='REF_FPCRoute_Assumed':continue
 vol=cable.common(o.Shape).Volume
 if vol>1e-5:cable_hits.append(dict(other=n,volume_mm3=vol))
assert cable.isValid() and len(cable.Solids)==1
# Rigid lid removal, one-mm increments; not a complete hand/tool envelope.
lid_sweep=[]
lid=refs['CASE_lid'].Shape
for dz in range(1,51):
 moved=lid.copy();moved.translate(V(0,0,dz))
 for n,o in list(parts.items())+[("cable",refs['REF_FPCRoute_Assumed'])]:
  vol=moved.common(o.Shape).Volume
  if vol>1e-5:lid_sweep.append(dict(lift_mm=dz,other=n,volume_mm3=vol))
assert not lid_sweep,lid_sweep
# Specified small-tool clearances; guard must be removed for camera work.
tool_hits=[]
tools=[]
for x,ys,z in [(24,[DY-20,DY+20],4),(32,[DY-26.5,DY+26.5],3),(5,[DY-16,DY+16],3)]:
 for y in ys:tools.append((f'M3_{x}_{y}',cyl(2,60,(x,y,z+.05)),set()))
for y in [DY-9.5,DY+9.5]:
 tools.append(('exit_jaw_M1_6',cyl(1.5,40,(2,y,18)),set()))
 tools.append(('camera_jaw_M1_6',cyl(1.5,45,(22,y,11),(1,0,0)),{'NEW_RemovableGuard'}))
for y in [DY-14,DY+14]:
 for z in [16,44]:tools.append(('camera_mount_M1_6',cyl(1.5,45,(23.7,y,z),(1,0,0)),{'NEW_RemovableGuard'}))
for label,tool,exclude in tools:
 for n,o in list(parts.items())+list(realrefs.items()):
  if n in exclude:continue
  vol=tool.common(o.Shape).Volume
  if vol>1e-5:tool_hits.append(dict(tool=label,other=n,volume_mm3=vol))
assert not tool_hits,tool_hits
assert not cable_hits,cable_hits
assert not adapter_ref_intersections,adapter_ref_intersections
assert not collisions,collisions
assert not keep_collisions,keep_collisions
new_ledge_interference=base.common(transformed(ad)).Volume
bounds=Part.makeCompound([o.Shape for o in list(parts.values())+list(realrefs.values())]).BoundBox
report=dict(lid_lift_1_to_50mm_collisions=lid_sweep,tool_access_collisions=tool_hits,tool_check_scope="4mm shaft for selected M3 positions, 3mm shaft for M1.6; no full handles/fastener models; remove guard for camera access",cable=dict(minimum_centerline_radius_mm=5,assumed_width_mm=12,assumed_thickness_mm=.3,free_span_length_mm=path.Length,connector_insertions_included=False,camera_side_exit='from bottom edge, verify with real part',camera_y_offset_mm=DY,collisions=cable_hits,bending_rating_verified=False),parameters=P,new_parts=checks,old_support_adapter_intersection_mm3=old_interference,new_support_adapter_intersection_mm3=new_ledge_interference,adapter_reference_collisions=adapter_ref_intersections,collisions=collisions,assumed_service_keepout_collisions=keep_collisions,
 assembly_bounds_mm=[bounds.XMin,bounds.YMin,bounds.ZMin,bounds.XMax,bounds.YMax,bounds.ZMax],assembly_size_mm=[bounds.XLength,bounds.YLength,bounds.ZLength],
 limitations=['camera rear body and keep-outs need physical verification','adapter bottom Z=0.85 assumed mating datum; actual B2B engagement must be confirmed','cable route and clamps modeled with provisional connector datum, thickness, radius and soft pad assumptions','fastener heads, nuts and washer installation clearance not fully modeled','case base and carrier prototypes need fit and structural/thermal tests','script-driven rebuild, not recovered original parametric history'])
(HERE/'verification_v2.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
D.saveAs(str(HERE/'cad/camera_lbc3_v2.FCStd'))
Part.export(list(parts.values())+list(realrefs.values()),str(HERE/'cad/camera_lbc3_v2.step'))
for n,o in parts.items():
 o.Shape.exportStep(str(OUT/f'{n}.step'))
 if n!='NEW_CommonFrame':
  s=o.Shape.copy()
  if n=='NEW_CameraCarrier':s.rotate(V(0,0,0),V(0,1,0),90)
  elif n=='NEW_RemovableGuard':s.rotate(V(0,0,0),V(0,1,0),-90)
  b=s.BoundBox;s.translate(V(-b.XMin,-b.YMin,-b.ZMin))
  MeshPart.meshFromShape(Shape=s,LinearDeflection=.12,AngularDeflection=.3,Relative=False).write(str(OUT/f'{n}_trial.stl'))
# Save source tessellation for a lightweight, standalone browser inspection.
meshes=[]
for n,o in list(parts.items())+list(refs.items()):
 verts,faces=o.Shape.tessellate(.25)
 meshes.append(dict(name=n,role=o.SourceRole,vertices=[[v.x,v.y,v.z]for v in verts],faces=faces))
(HERE/'cad/view_meshes_v2.json').write_text(json.dumps(meshes,separators=(',',':')))
print(json.dumps(report,ensure_ascii=False,indent=2))
A.closeDocument(src.Name)
