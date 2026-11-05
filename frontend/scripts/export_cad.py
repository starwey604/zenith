"""FreeCADCmd: export existing CAD to self-contained, Y-up glTF 2.0 binaries.
No CAD regeneration is needed for a normal npm build. Source files stay read-only.
Run in FreeCAD: exec(compile(open(path).read(),path,'exec'), {'__file__':path})
"""
from pathlib import Path
import json, struct, shutil
import FreeCAD as App
import Part

HERE=Path(__file__).resolve().parents[1]
ROOT=HERE.parent
OUT=HERE/'public/models'
OUT.mkdir(parents=True,exist_ok=True)

def mesh(shape,name,color,transform=lambda v:(v.x,v.y,v.z)):
    vs,fs=shape.tessellate(0.6)
    return {'name':name,'vertices':[transform(v) for v in vs],'faces':fs,'color':color}

def glb(name,parts,source):
    data=bytearray();views=[];accessors=[];materials=[];meshes=[];nodes=[]
    def add(values,fmt,component,kind,count,minmax=None,target=None):
        while len(data)%4:data.append(0)
        off=len(data);data.extend(struct.pack('<'+fmt*len(values),*values))
        views.append({'buffer':0,'byteOffset':off,'byteLength':len(data)-off,**({'target':target} if target else {})})
        a={'bufferView':len(views)-1,'componentType':component,'count':count,'type':kind}
        if minmax:a.update(min=minmax[0],max=minmax[1])
        accessors.append(a);return len(accessors)-1
    for p in parts:
        # Design uses Z-up mm. glTF uses Y-up; the viewer restores Z-up on import.
        vs=[(round(v[0],4),round(v[2],4),round(-v[1],4)) for v in p['vertices']]
        if not vs:continue
        pos=add([c for v in vs for c in v],'f',5126,'VEC3',len(vs),
                ([min(v[i] for v in vs) for i in range(3)],[max(v[i] for v in vs) for i in range(3)]),34962)
        idx=add([i for f in p['faces'] for i in f],'I',5125,'SCALAR',len(p['faces'])*3,target=34963)
        col=p['color'].lstrip('#');srgb=[int(col[i:i+2],16)/255 for i in [0,2,4]]
        rgb=[v/12.92 if v<=0.04045 else ((v+.055)/1.055)**2.4 for v in srgb]
        materials.append({'name':p['name'],'pbrMetallicRoughness':{'baseColorFactor':rgb+[1], 'metallicFactor':0.15,'roughnessFactor':0.6},'doubleSided':True})
        meshes.append({'name':p['name'],'primitives':[{'attributes':{'POSITION':pos},'indices':idx,'material':len(materials)-1}]})
        nodes.append({'name':p['name'],'mesh':len(meshes)-1})
    j={'asset':{'version':'2.0','generator':'Zenith FreeCAD mesh exporter'},'scene':0,'scenes':[{'nodes':list(range(len(nodes)))}],
       'nodes':nodes,'meshes':meshes,'materials':materials,'buffers':[{'byteLength':len(data)}],
       'bufferViews':views,'accessors':accessors,'extras':{'source':source,'units':'mm','sourceFrame':'Z-up; exported Y-up'}}
    jb=json.dumps(j,ensure_ascii=False,separators=(',',':')).encode();jb+=b' '*((-len(jb))%4);data+=b'\0'*((-len(data))%4)
    result=struct.pack('<III',0x46546c67,2,12+8+len(jb)+8+len(data))+struct.pack('<I4s',len(jb),b'JSON')+jb+struct.pack('<I4s',len(data),b'BIN\0')+data
    (OUT/(name+'.glb')).write_bytes(result)
    print(name,len(parts),'parts',len(result),'bytes')

def read(name):
    s=Part.Shape();s.read(str(ROOT/'mechanical/steps/RM'/name));return s

launcher=App.openDocument(str(ROOT/'mechanical/hero_head/cad/launcher_reference.FCStd'))
for side,ids,y in [('left',[1204,1205],-49),('right',[1206,1207],49)]:
    parts=[]
    for n in ids:
        obj=launcher.getObject('Ref_'+str(n))
        parts.append(mesh(obj.Shape,obj.Label,'#8797a1' if n in [1204,1206] else '#27343d',lambda v:(v.x,v.y-y,v.z)))
    glb('wheel-'+side,parts,'mechanical/hero_head/cad/launcher_reference.FCStd; original Jiao Long wheels')
motor=read('M3508_motor_body_only_derived.step')
glb('m3508-body',[mesh(motor,'M3508_body_reference','#465d6e')],'mechanical/steps/RM/M3508_motor_body_only_derived.step; gearbox/shaft fit unresolved')
s=read('RoboMaster_大测速模块_SM11_2020.STEP')
parts=[mesh(x,'SM11_'+str(i),'#718c9b' if i<4 else '#53616a',lambda v:(v.z-66.764+45,v.x+21.526,v.y-69.666)) for i,x in enumerate(s.Solids) if i<27]
glb('sm11',parts,'mechanical/steps/RM/RoboMaster_大测速模块_SM11_2020.STEP; body/sight, original cable paths omitted')
s=read('C620无刷电机调速器.STEP')
parts=[mesh(x,'C620_'+str(i),'#273943' if i in [1,2] else '#acb9ba',lambda v:(v.x+1.7,v.z,-v.y)) for i,x in enumerate(s.Solids) if i<18]
glb('c620',parts,'mechanical/steps/RM/C620无刷电机调速器.STEP; fixed connectors included, wires rerouted in concept')
parts=[]
for p in json.loads((ROOT/'mechanical/camera_lbc3_study/cad/view_meshes_v2.json').read_text()):
    n=p['name']
    if n.startswith('KEEP_'):continue
    color='#df9b44' if 'FPCRoute' in n else '#214d66' if 'Guard' in n else '#668993' if 'Frame' in n else '#c1b28a' if 'Carrier' in n else '#263c4b' if 'Lens' in n else '#398c85' if ('Adapter' in n or 'board' in n) else '#8cabae'
    parts.append({'name':n,'vertices':p['vertices'],'faces':p['faces'],'color':color})
glb('vision-v2',parts,'mechanical/camera_lbc3_study/cad/camera_lbc3_v2.FCStd; includes dimensional placeholders')
# Downloads are local assets, never runtime links outside this frontend.
D=HERE/'public/downloads';D.mkdir(exist_ok=True)
for src,dst in [
 ('mechanical/steps/RM/C620无刷电机调速器.STEP','c620.step'),
 ('mechanical/steps/RM/M3508_official_with_gearbox.stp','m3508-official.stp'),
 ('mechanical/steps/RM/RoboMaster_大测速模块_SM11_2020.STEP','sm11-2020.step'),
 ('mechanical/camera_lbc3_study/cad/camera_lbc3_v2.FCStd','camera-lbc3-v2.FCStd'),
 ('mechanical/camera_lbc3_study/cad/camera_lbc3_v2.step','camera-lbc3-v2.step'),
 ('mechanical/hero_head/cad/launcher_reference.FCStd','jiao-long-launcher-reference.FCStd')]:
    shutil.copyfile(ROOT/src,D/dst)
print('Asset export complete')
