"""Rebuild the first camera/LBC3 mechanical prototype in FreeCAD.
Script-parametric BRep parts; camera is drawing-based reference, adapter real STEP.
Original enclosure is never overwritten. Dimensions in mm.
"""
import FreeCAD as A,Part,MeshPart,json,math
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];V=A.Vector
P=dict(m3_clear=3.4,camera_screw_clear=1.8,adapter_board_z=.85)

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

D=A.newDocument('CameraLBC3Prototype')
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
add('KEEP_CameraFPCAndFlipLock',box(13,-8,6,20,8,12),(.82,.6,.25),'assumed service keep-out',70)
add('KEEP_CameraTriggerPins',box(14,10,12,20,16,21),(.82,.6,.25),'assumed service keep-out',70)
# Adjustable cable clamp pair at the fixed PCB-board side, not on B2B contacts.
# No clamp exported until actual FPC thickness/bend/cover latch are known.
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
 if n=='REF_ActualCAM1Adapter':continue
 v=realrefs['REF_ActualCAM1Adapter'].Shape.common(o.Shape).Volume
 if v>1e-5:adapter_ref_intersections.append(dict(other=n,volume_mm3=v))
assert not adapter_ref_intersections,adapter_ref_intersections
assert not collisions,collisions
assert not keep_collisions,keep_collisions
new_ledge_interference=base.common(transformed(ad)).Volume
bounds=Part.makeCompound([o.Shape for o in list(parts.values())+list(realrefs.values())]).BoundBox
report=dict(parameters=P,new_parts=checks,old_support_adapter_intersection_mm3=old_interference,new_support_adapter_intersection_mm3=new_ledge_interference,adapter_reference_collisions=adapter_ref_intersections,collisions=collisions,assumed_service_keepout_collisions=keep_collisions,
 assembly_bounds_mm=[bounds.XMin,bounds.YMin,bounds.ZMin,bounds.XMax,bounds.YMax,bounds.ZMax],assembly_size_mm=[bounds.XLength,bounds.YLength,bounds.ZLength],
 limitations=['camera rear body and keep-outs need physical verification','adapter bottom Z=0.85 assumed mating datum; actual B2B engagement must be confirmed','no FPC routing or clamp is frozen','fastener heads, nuts and washer installation clearance not fully modeled','case base and carrier prototypes need fit and structural/thermal tests','script-driven rebuild, not recovered original parametric history'])
(HERE/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
D.saveAs(str(HERE/'cad/camera_lbc3_v1.FCStd'))
Part.export(list(parts.values())+list(realrefs.values()),str(HERE/'cad/camera_lbc3_v1.step'))
for n,o in parts.items():
 o.Shape.exportStep(str(HERE/'exports'/f'{n}.step'))
 if n!='NEW_CommonFrame':
  s=o.Shape.copy()
  if n=='NEW_CameraCarrier':s.rotate(V(0,0,0),V(0,1,0),90)
  elif n=='NEW_RemovableGuard':s.rotate(V(0,0,0),V(0,1,0),-90)
  b=s.BoundBox;s.translate(V(-b.XMin,-b.YMin,-b.ZMin))
  MeshPart.meshFromShape(Shape=s,LinearDeflection=.12,AngularDeflection=.3,Relative=False).write(str(HERE/'exports'/f'{n}_trial.stl'))
# Save source tessellation for a lightweight, standalone browser inspection.
meshes=[]
for n,o in list(parts.items())+list(refs.items()):
 verts,faces=o.Shape.tessellate(.25)
 meshes.append(dict(name=n,role=o.SourceRole,vertices=[[v.x,v.y,v.z]for v in verts],faces=faces))
(HERE/'cad/view_meshes.json').write_text(json.dumps(meshes,separators=(',',':')))
print(json.dumps(report,ensure_ascii=False,indent=2))
A.closeDocument(src.Name)
