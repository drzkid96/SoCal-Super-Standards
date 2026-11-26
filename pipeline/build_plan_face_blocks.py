import json,gzip,hashlib,zipfile,subprocess,re,tempfile
from pathlib import Path
import ezdxf,numpy as np,contourpy
from PIL import Image
from io import BytesIO
rows=json.load(open('public/data/plan-signs.json'));native=[r for r in json.load(open('public/data/sign-block-options.json')) if not r['id'].startswith('plan-face-')]
norm=lambda s:re.sub(r'[^A-Z0-9]','',s.upper())
known={norm(k) for r in native for k in [r['code'],*r['aliases']]};names={r['blockName'].upper() for r in native}
sha=lambda b:hashlib.sha256(b).hexdigest()
bin=next(Path('.fp-chatgpt').rglob('dxf2dwg')).resolve()
out=[];idx={}
with zipfile.ZipFile('data/reference/plan-face-blocks.zip','w',zipfile.ZIP_DEFLATED) as z,tempfile.TemporaryDirectory() as temp:
 for r in rows:
  if not r['faces'] or norm(r['code']) in known:continue
  face=r['faces'][0];key='plan-face-'+face['id'];code=r['code'].replace(' (','(')
  if code.upper() in names:continue
  im=Image.open('public'+face['image']).convert('L')
  ink=np.where(np.array(im).min(axis=1)<185)[0]
  if not len(ink):continue
  # Each indexed specimen has a continuous face silhouette, then a gap and printed callout(s).
  face_rows=np.split(ink,np.where(np.diff(ink)>1)[0]+1)[0]
  im=im.crop((0,max(0,int(face_rows[0])-1),im.width,min(im.height,int(face_rows[-1])+2)))
  box=im.point(lambda n:255 if n<185 else 0).getbbox()
  if not box:continue
  im=im.crop(box);width,height=im.size
  v=np.pad(255-np.array(im),1);cont=contourpy.contour_generator(z=v,fill_type='OuterOffset')
  lines,offsets=cont.filled(90,260)
  doc=ezdxf.new('R2000');doc.units=1;space=doc.modelspace();entities=[]
  for poly,cuts in zip(lines,offsets):
   hatch=space.add_hatch(color=7)
   for j,(lo,hi) in enumerate(zip(cuts,cuts[1:])):
    pts=[((x-1-width/2)/width,(height/2-y+1)/width) for x,y in poly[lo:hi-1]]
    if len(pts)>=3:hatch.paths.add_polyline_path(pts,is_closed=True,flags=1 if j==0 else 0)
   if not hatch.paths:space.delete_entity(hatch);continue
  f=Path(temp)/'sign.dxf';w=f.with_suffix('.dwg');doc.saveas(f);subprocess.run([str(bin),'-y','-o',str(w),str(f)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  nativebytes=w.read_bytes(); pairs=list(zip(*[iter(f.read_text().splitlines())]*2));start=pairs.index(('  2','ENTITIES'))+1;part=[]
  for k,val in pairs[start:]:
   if val=='ENDSEC' and int(k)==0:break
   if int(k) not in (5,330):part.extend((k,val))
  geom=gzip.compress(('\n'.join(part)+'\n').encode(),mtime=0);idx[key]=dict(name=code,sha256=sha(geom),bytes=len(geom),entities=len(space),bounds=[-.5,-height/width/2,.5,height/width/2])
  file='individual/Plan legends/'+code+'.dwg';preview='/figs/cad-blocks/'+key+'.webp';buf=BytesIO();im.save(buf,'WEBP',lossless=True)
  z.writestr(file,nativebytes);z.writestr(preview[1:],buf.getvalue());z.writestr('geometry/'+key+'.dxf.gz',geom)
  out.append(dict(id=key,code=code,blockName=code,file=file,width=1,height=height/width,sizeStatus='Reference size unknown',aliases=r['aliases'],signUrl=r['url'],sourceDrawing='Plan legend',preview=preview,sha256=sha(nativebytes),bytes=len(nativebytes),description='Plan legend reproduction',matchStatus='Plan legend reproduction'))
 z.writestr('records.json',json.dumps(out));z.writestr('geometry.json',json.dumps(idx))
print(len(out))
