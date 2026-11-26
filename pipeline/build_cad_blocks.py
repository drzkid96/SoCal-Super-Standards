"""Build self-contained native DWGs from reviewed sign faces and size evidence."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from collections import Counter,defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import unicodedata
from zipfile import ZipFile,ZIP_DEFLATED

import ezdxf
from ezdxf.fonts import fonts
from ezdxf.math import Matrix44
from ezdxf.lldxf.validator import is_valid_block_name
from cad_blocks.geometry import diamond_blank_bounds, drawing_context, record, get_bounds, scaled_marks, write_geometry, restore_native_knockouts
from cad_blocks.masks import read_mask
from cad_sign_catalog import designation_key

def read(p):
    return json.loads(p.read_text())
def save(p,obj):
    tmp=p.with_suffix('.tmp')
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=1)+'\n');tmp.replace(p)
def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
def native_name(s):
    s=unicodedata.normalize('NFKD',s.translate(str.maketrans({'–':'-','—':'-','“':'','”':'','"':'','×':'x'}))).encode('ascii','ignore').decode()
    s=re.sub(r'[<>/\\:;?*|=]', '-', s).strip() or 'Unnumbered source sign'
    if not is_valid_block_name(s):raise ValueError('Illegal native name '+s)
    return s
REVIEWED_VARIANTS = Path('data/reference/plan-examples/cad-source-variants.json')
RENDER_REPAIRS = Path('data/reference/plan-examples/cad-render-repairs.json')

def category(code):
    code=code.upper().strip()
    code=re.sub(r'^CAL[- _](?=[RGWS][0-9])','',code)
    if re.match(r'^(?:W2[0-4]|G20|M4-8|M4-9|NWZ|PCMS|TC|CW)',code):return 'Temporary traffic control'
    if re.match(r'^R(?:[0-9]|S[0-9])',code):return 'Regulatory'
    if re.match(r'^(?:W|SW)[0-9]',code):return 'Warning'
    if re.match(r'^(?:D|G|M|E|I)[0-9]',code):return 'Guide'
    if re.match(r'^(?:S|SR)[0-9]',code):return 'School'
    if re.match(r'^OM',code):return 'Object markers'
    if re.match(r'^C[0-9]',code):return 'Temporary traffic control'
    return 'Local and other'

def series_label(series):
    return {'official-standard':'Issued standard','fp-signs':'FP sign library','mutcd-standard-signs':'MUTCD CAD library',
            'geo':'GEO','pico':'Pico','3346-title-details':'3346 title details','3346-signs-1-13':'3346 sheets 1-13',
            '3346-signs-14-15':'3346 sheets 14-15'}.get(series,series)

def new_doc():
    d=ezdxf.new('R2000');d.units=1
    d.header['$MEASUREMENT']=0;d.header['$LUNITS']=2;d.header['$LUPREC']=3
    return d
def choose_size(r,standards,bounds,marks):
    x0,y0,x1,y1=bounds;w,h=x1-x0,y1-y0
    if w<=0 or h<=0:raise ValueError('Invalid sign-face bounds')
    native=r.get('verifiedSize') or r.get('physicalSizeInches') or r.get('sizeInches')
    st=standards.get(designation_key(r['code']),{})
    if r.get('publisherPlateSize'):
        return (*r['publisherPlateSize'],'published reference size',r.get('publisherSizeBasis','published overall panel width and height'),False)
    if r.get('verifiedBoundsInches'):
        return (*r['verifiedBoundsInches'],'source dimensions',r.get('verifiedBoundsBasis','observed source plate dimensions'),False)
    if native:
        nw,nh=map(float,native)
        if len(marks)>0 and abs(nw-nh)<.01:
            from shapely.geometry import MultiPoint
            points=[((v.x-x0)/w,(v.y-y0)/h) for m in marks for p in m.paths for v in p.control_vertices()
                    if x0-w*.015<=v.x<=x1+w*.015 and y0-h*.015<=v.y<=y1+h*.015]
            hull=MultiPoint(points).convex_hull if points else None
            if hull is not None and .461<hull.area<.59 and all(min(abs(a-.5),abs(b-.5))<.105 for a,b in hull.simplify(.055).exterior.coords):
                return nw*math.sqrt(2),nh*math.sqrt(2),'source dimensions','diamond side lengths',False
        if abs(math.log((w/h)/(nw/nh)))>.12:
            return 1.,h/w,'Reference size unknown','Recorded dimensions conflict with the aspect ratio of the drawn face; original proportions retained at 1 inch width',True
        return nw,nh,'source dimensions','source drawing dimension note',False
    if st.get('size') and not r.get('historicalLegend') and not r.get('assembly') and r.get('sourceKind')!='block template':
        nominal=list(map(float,st['size']));basis=st.get('sizeBasis')
        dims=st.get("nominalBounds")
        if dims:
            dims=list(map(float,dims))
        elif basis in {'width-height','diameter'}:
            dims=nominal[:2]
        elif basis=='diamond-side-lengths':
            dims=[v*math.sqrt(2) for v in nominal[:2]]
        elif basis=='triangle-sides' and len(set(nominal))==1:
            dims=[nominal[0],nominal[0]*math.sqrt(3)/2]
        if dims and len(dims)==2:
            sw,sh=dims
            if abs(math.log((w/h)/(sw/sh)))<.165:
                return sw,sh,'published reference size',basis,False
    scale=1/w
    return w*scale,h*scale,'Reference size unknown', 'Normalized to 1 inch face width; physical size unverified',True
def cmd(args):
    result=subprocess.run([str(a) for a in args],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=360)
    if result.returncode:raise ValueError(' '.join(map(str,args))+' '+result.stdout.decode(errors='replace')[-400:])
def encode_job(item,bin_dir,tmp,out):
    id=item['id'];dxf=tmp/(id+'.dxf');dwg=out/item['file'];dwg.parent.mkdir(parents=True,exist_ok=True)
    cmd([bin_dir/'dxf2dwg','-a','r2000','--overwrite','-o',dwg,dxf])
    rt=tmp/(id+'.roundtrip.dxf');cmd([bin_dir/'dwg2dxf','-y','-o',rt,dwg])
    if dwg.read_bytes()[:6]!=b'AC1015':raise ValueError('Not an AutoCAD 2000 DWG: '+id)
    d=ezdxf.readfile(rt)
    if d.units!=1:raise ValueError('Incorrect units: '+id)
    standalone=item.get('standaloneModelspace',False)
    b=d.modelspace() if standalone else d.blocks[item['blockName']]

    count=Counter(e.dxftype() for e in b)
    if not count['HATCH']:raise ValueError('Missing filled geometry: '+id)
    if any(e.dxf.get('color',256)!=7 or e.dxf.hasattr('true_color') for e in b):raise ValueError('Sign face has an inheritable or colored entity: '+id)
    base=d.header.get('$INSBASE',(0,0,0)) if standalone else b.block.dxf.base_point
    if any(abs(x)>1.e-7 for x in base):raise ValueError('Invalid block insertion base')
    if standalone:
        if list(b.query('INSERT')) or any(not block.name.startswith('*') for block in d.blocks):
            raise ValueError('External sign drawing contains a nested reference: '+id)
    elif not any(e.dxf.name==b.name and e.dxf.insert.isclose((0,0,0)) for e in d.modelspace().query('INSERT')):
        raise ValueError('Missing modelspace insertion')
    if any(h.dxf.pattern_name!='SOLID' for h in b.query('HATCH')):raise ValueError('Unexpected hatch pattern')
    # Independent DWG decoder must also accept the file and recover the named block.
    independent=tmp/(id+'.dxfrw.dxf')
    cmd([bin_dir/'dxfrw-dwg2dxf',dwg,'-o',independent,'-y'])
    cross=ezdxf.readfile(independent)
    cb=cross.modelspace() if standalone else cross.blocks[item['blockName']]
    if len(cb.query('HATCH'))!=count['HATCH']:raise ValueError('Independent hatch count mismatch: '+id)
    if any(e.dxf.get('color',256)!=7 for e in cb):raise ValueError('Independent reader found an inheritable entity color: '+id)

    item.update(sha256=digest(dwg),bytes=dwg.stat().st_size,solidHatches=count['HATCH'],entityCount=sum(count.values()),roundTrip=True)
    return item

def draw_assembly(target,doc,ctx,parts,rect,width,height):
    """Build each independently reviewed panel before placing it in its original assembly."""
    x0,y0,x1,y1=rect
    scale=min(width/(x1-x0),height/(y1-y0))
    for part in parts:
        native=record(doc,ctx,part)
        bounds=get_bounds(native,part)
        a,b,c,d=bounds
        sw,sh=(c-a)*scale,(d-b)*scale
        temp=new_doc()
        panel=temp.modelspace()
        write_geometry(panel,scaled_marks(native,bounds,sw,sh),sw,sh,
                       ink_extent=part.get('minimumAddedInkY'),join_dangling=part.get('joinArrowContours',False))
        tr=Matrix44.translate((a+c-x0-x1)*scale/2,(b+d-y0-y1)*scale/2,0)
        for e in panel:
            placed=e.copy()
            placed.transform(tr)
            target.add_entity(placed)


def package_master(master,model,rows,unresolved,bin_dir,tmp,out):
    cellw=max(48,max(r['width'] for r in rows)*1.28);cellh=max(53,max(r['height'] for r in rows)*1.3+10)
    import itertools
    cols=max(6,min(24,int(math.sqrt(len(rows)))))
    line=0
    master.layers.new('CATALOG LABELS')
    master.layers.new('CATALOG DIVIDERS')
    labels={'layer':'CATALOG LABELS','color':7}
    for group,entries in itertools.groupby(rows,lambda r:category(r['code'])):
        group_y=-(line-.5)*cellh
        model.add_text(group.upper(),height=3.2,dxfattribs={**labels,'insert':(-cellw*.43,group_y)})
        model.add_line((-cellw*.43,group_y-1),(cellw*(cols-.56),group_y-1),dxfattribs={'layer':'CATALOG DIVIDERS','color':7})
        group_rows=list(entries)
        for i,r in enumerate(group_rows):
            x=(i%cols)*cellw
            y=-(line+i//cols)*cellh
            preview_scale=min(cellw*.66/max(r['width'],.001),cellh*.67/max(r['height'],.001)) if r['sizeStatus']=='Reference size unknown' else 1.
            model.add_blockref(r['masterBlockName'],(x,y),dxfattribs={'xscale':preview_scale,'yscale':preview_scale,'zscale':preview_scale})
            model.add_text(r['code'],height=min(2.3,cellw*.75/max(len(r['code']),1)*1.2),dxfattribs={**labels,'insert':(x-cellw*.43,y-cellh*.42)})
            model.add_text(series_label(r['sourceDrawing'])+' / '+r['sizeStatus'],height=1.25,dxfattribs={**labels,'insert':(x-cellw*.43,y-cellh*.46)})
            if r['sizeStatus']!='Reference size unknown':
                model.add_text(f"{r['width']:g} x {r['height']:g} in",height=1.15,dxfattribs={**labels,'insert':(x-cellw*.43,y-cellh*.49)})
        line+=(len(group_rows)+cols-1)//cols+1
    model.add_text('SIGN BLOCK CATALOG',height=6,dxfattribs={**labels,'insert':(-cellw*.43,.8*cellh)})
    master.set_modelspace_vport(height=max(line*cellh,cellw*cols*.7)*1.08,center=((cols-1)*cellw/2,-(line-2)*cellh/2))
    master_dxf=tmp/'master.dxf';master.saveas(master_dxf)
    cmd([bin_dir/'dxf2dwg','-a','r2000','--overwrite','-o',out/'master.dwg',master_dxf])
    check=tmp/'master.check.dxf';cmd([bin_dir/'dwg2dxf','-y','-o',check,out/'master.dwg'])
    mcheck=ezdxf.readfile(check)
    if mcheck.units!=1 or len(mcheck.modelspace().query('INSERT'))!=len(rows):raise ValueError('Master DWG failed round trip')
    for r in rows:
        name=r['masterBlockName']
        if len(mcheck.blocks[name].query('HATCH'))!=r['solidHatches']:raise ValueError('Master symbol lost geometry: '+name)
    del mcheck

    index={'version':2,'units':'inches','basepoint':'geometric center of the sign face','format':'AutoCAD 2000 DWG','individualFormat':'WBLOCK-style direct modelspace geometry',
           'master':'master.dwg','bundle':'blocks.zip','masterSha256':digest(out/'master.dwg'),'records':rows,'unresolved':unresolved}
    save(out/'manifest.json',index)
    (out/'README.txt').write_text(
        'SIGN BLOCK CATALOG\n\nEach individual AutoCAD 2000 drawing contains direct sign-face geometry in modelspace, with its geometric center at the insertion origin. Insert the drawing externally to create a block named for its file. One drawing unit is one inch. Filled paths use editable SOLID hatches with open counters.\n\n'
        'Start with master.dwg to browse the contact sheet. Use the individual drawings for insertion at original size. The master enlarges reference-size previews only. Separate rows preserve source variants and historic legends. The manifest identifies each source drawing, source handle and sizing condition.\n\n'
        'Reference size unknown folders contain symbols normalized to a 1.000-inch face width. The original physical dimensions are unknown. Source dimensions come from the drawing. Published dimensions give the cited application or road class.\n\n'
        'The chart prints the source designation exactly. DWG-forbidden characters are transliterated in native block names. Source and size qualifiers distinguish separate blocks sharing a designation, including when several are inserted into one plan.\n', encoding='utf-8')
    with ZipFile(out/'blocks.zip','w',compression=ZIP_DEFLATED,compresslevel=6) as z:
        for fn in ['master.dwg','manifest.json','README.txt']+[r['file'] for r in rows]:z.write(out/fn,fn)
    print('Validated',len(rows),'DWGs and the master drawing; skipped',len(unresolved),flush=True)

def merge_batches(batch_dirs,wd,bin_dir,tmp,out):
    from itertools import chain
    batches=[(sub,read(sub/'manifest.json')) for sub in batch_dirs]
    unresolved=list(chain.from_iterable(index['unresolved'] for _,index in batches))
    selected={}
    for sub,index in batches:
        for r in index['records']:
            old_ids={r['id'],*(o['id'] for o in r['observations'] if o['sourceDrawing']==r['sourceDrawing'])}
            for old_id in old_ids:
                old=selected.pop(old_id,None)
                if old:
                    r['observations'].extend(o for o in old[1]['observations'] if o not in r['observations'])
            selected[r['id']]=(sub,r)
    source=list(selected.values())
    source.sort(key=lambda item:(item[1]['sourceDrawing']!='official-standard', bool(item[1].get('observationIds')),item[1]['id']))
    master=new_doc()
    model=master.modelspace()
    counts=Counter()
    used_filenames=set()
    seen={}
    rows=[]
    issued={}
    sizes={}
    reencode=[]
    prior={}
    if (out/'manifest.json').is_file():
        prior={r['id']:r for r in read(out/'manifest.json')['records'] if r.get('standaloneModelspace')}
    variants=read(REVIEWED_VARIANTS)
    metadata=read(RENDER_REPAIRS)
    publication=wd/'block-inputs'/'official-faces.json'
    allowed={r['id'] for r in read(publication)} if publication.is_file() else set()
    supplement=wd/'block-inputs'/'official-callout-faces.json'
    callouts={r['id']:r for r in read(supplement)} if supplement.is_file() else {}
    allowed.update(callouts)
    redirected=defaultdict(list)
    historic_twins={'mutcd-sheet-r3-17-107b4':'fp-signs-75f3'}
    for sub,r in source:
        for o in callouts.get(r['id'],{}).get('sourceObservations',[]):
            if o not in r['observations']:r['observations'].append(o)
        code=r['code'].casefold()
        if metadata.get(r['id'],{}).get('aliases'):
            r['aliases']=list(dict.fromkeys(r.get('aliases',[])+metadata[r['id']]['aliases']))
        if r['id']=='geo-g27-4b1d':
            r['note']='Unnumbered Interstate shield. The original drawing has a route-number attribute. This external block contains the blank graphic.'
        if 'historic' in r.get('sourceKind','') and r['sourceDrawing']=='official-standard':r['geometryStatus']='historical issued artwork'
        if r['id'] in historic_twins:
            redirected[historic_twins[r['id']]].extend(r['observations'])
            continue
        if r['sourceDrawing']=='official-standard':
            if not r.get('observationIds') and allowed and r['id'] not in allowed:continue
            if r.get('observationIds') and code in issued and all(abs(r[k]-issued[code][k])<.001 for k in ('width','height')):
                continue
            if code not in issued:issued[code]=r
            sizes[(code,r['width'],r['height'])]=r
        else:
            canon=issued.get(code)
            if canon:
                field=sizes.get((code,r['width'],r['height']),canon)
                for observation in r['observations']:
                    if observation not in field['observations']:field['observations'].append(observation)
                if r['id'] not in variants:continue
                r['currentArtworkId']=canon['id']
                r['geometryStatus']='documented source variant'
                r['historicalLegend']=variants[r['id']]['legend']
                r['note']='Source legend: '+r['historicalLegend']+'. '+(r.get('note') or '')
        k=(designation_key(r['code']),r['width'],r['height'],r['geometryFingerprint'])
        if k in seen:
            seen[k]['observations'].extend(o for o in r['observations'] if o not in seen[k]['observations'])
            continue
        seen[k]=r
        if not r.get('nominalPanelInches') and r['sizeStatus']!='Reference size unknown':
            if 'diamond' in r['sizeBasis']:
                r['nominalPanelInches']=[round(v/math.sqrt(2),3) for v in (r['width'],r['height'])]
            elif r['sizeBasis']=='triangle-sides' and r['code'].upper()=='R1-2':
                r['nominalPanelInches']=[r['width']]*3
            elif r['sizeBasis'] in {'width-height','diameter','published overall panel width and height','source drawing dimension note'}:
                r['nominalPanelInches']=[r['width'],r['height']]
        rows.append(r)
        d=ezdxf.readfile(wd/'block-stage'/sub.name/(r['id']+'.dxf'))
        b=d.blocks[r['blockName']]
        base=native_name(r['code']).strip('. ') or 'Unnumbered sign'
        counts[base.upper()]+=1
        n=counts[base.upper()]
        suffix=(f"{r['width']:g} x {r['height']:g} in" if r.get('observationIds')
                else series_label(r['sourceDrawing'])+' '+str(n))
        name=base if n==1 else base+' ['+suffix+']'
        r['file']='/'.join(['individual',category(r['code'])]+(['Reference size unknown'] if r['sizeStatus']=='Reference size unknown' else [])+[name+'.dwg'])
        if r['file'].casefold() in used_filenames:raise ValueError('Repeated standalone filename '+r['file'])
        used_filenames.add(r['file'].casefold())
        r['blockName']=r['masterBlockName']=name
        r['preview']='/figs/cad-blocks/'+r['id']+'.webp'
        r['standaloneModelspace']=True
        mb=master.blocks.new(name)
        mb.block_record.dxf.units=1
        # WBLOCK layout: geometry directly in modelspace, with no nested sign
        # definition. AutoCAD derives the external block's name from the filename.
        standalone=new_doc()
        standalone.header['$INSBASE']=(0,0,0)
        geometry=standalone.modelspace()
        for ent in b:
            if ent.dxftype()=='POLYLINE':
                # Sign geometry is planar. The source writer can emit 3D POLYLINE
                # chains for straight edges next to SPLINEs. A native lightweight
                # polyline stores the exact same XY/bulge sequence without SEQEND
                # linkage that some R2000 modelspace readers misinterpret.
                points=[(v.dxf.location.x,v.dxf.location.y,v.dxf.get('bulge',0)) for v in ent.vertices]
                for space in (geometry,mb):space.add_lwpolyline(points,format='xyb',close=ent.is_closed,dxfattribs={'color':7})
            else:
                geometry.add_entity(ent.copy())
                mb.add_entity(ent.copy())
        standalone.set_modelspace_vport(height=max(r['width'],r['height'])*1.22,center=(0,0))
        previous=prior.get(r['id'])
        # Vector repairs can add a true knockout or fill after the outline
        # fingerprint is computed. Cache against the finished source block too.
        r['sourceBlockSha256']=r['sha256']
        matching=previous and all(previous.get(f)==r.get(f) for f in (
            'sourceBlockSha256','geometryFingerprint','width','height','file','masterBlockName'))
        existing=out/r['file']
        if matching and existing.is_file() and digest(existing)==previous['sha256']:
            for field in ('sha256','bytes','entityCount','solidHatches','roundTrip'):r[field]=previous[field]
        else:
            standalone.saveas(tmp/(r['id']+'.dxf'))
            reencode.append(r)
    def sort_key(r):
        from re import split
        return (category(r['code']),[int(x) if x.isdigit() else x for x in split(r'(\d+)',r['code'].lower())],
                r['sourceDrawing']!='official-standard',bool(r.get('observationIds')),r['sourceDrawing'],r['id'])
    for r in rows:
        if r['id'] in redirected:r['observations'].extend(o for o in redirected[r['id']] if o not in r['observations'])
    rows.sort(key=sort_key)
    if len({r['blockName'].casefold() for r in rows})!=len(rows):raise ValueError('Different individual drawings share an internal symbol')
    with ThreadPoolExecutor(max_workers=4) as pool:
        for _ in pool.map(lambda row:encode_job(row,bin_dir,tmp,out),reencode):
            pass
    package_master(master,model,rows,unresolved,bin_dir,tmp,out)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--bin',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--sources',nargs='*')
    parser.add_argument('--aggregate',nargs='+',type=Path)
    parser.add_argument('--sample',nargs='*')
    parser.add_argument('--workers',type=int,default=6)
    parser.add_argument('--font-folder',type=Path)
    args=parser.parse_args()
    wd=args.work;out=args.out;out.mkdir(exist_ok=True,parents=True)
    tmp=wd/'block-stage'/out.name;tmp.mkdir(exist_ok=True,parents=True)
    if args.aggregate:
        merge_batches(args.aggregate,wd,args.bin,tmp,out);return
    if args.font_folder:fonts.font_manager.scan_folder(args.font_folder)
    standards_file=wd/'standards'/'sign-standards.json'
    standards=read(standards_file) if standards_file.is_file() else {}
    if 'records' in standards:standards=standards['records']
    if isinstance(standards,list):standards={designation_key(r['code']):r for r in standards}
    records=read(Path('data/reference/plan-examples/cad-sign-art.json'))
    for f in sorted((wd/'block-inputs').glob('*.json')):
        more=read(f)
        records.extend(more if isinstance(more,list) else more['records'])
    selections={}
    for r in records:
        previous=selections.get(r['id'],{})
        selections[r['id']]={**previous,**r}
        if previous.get('mask') and not r.get('mask'):selections[r['id']]['mask']=previous['mask']
    records=list(selections.values())
    mask_archive=Path('data/reference/plan-examples/cad-render-masks.zip')
    if mask_archive.exists():
        with ZipFile(mask_archive) as package:
            mask_dir=wd/'block-stage'/'reviewed-masks'
            mask_dir.mkdir(parents=True,exist_ok=True)
            masks={}
            for evidence in json.loads(package.read('manifest.json')):
                data=package.read(evidence['mask'])
                if hashlib.sha256(data).hexdigest()!=evidence['sha256']:raise ValueError('Source mask hash mismatch')
                target=mask_dir/(evidence['id']+'.png')
                target.write_bytes(data)
                masks[evidence['id']]=str(target)
            for r in records:
                if r['id'] in masks:r['mask']=masks[r['id']]
    variants=read(REVIEWED_VARIANTS)
    repairs=read(RENDER_REPAIRS)
    reviewed=read(Path('data/reference/plan-examples/cad-reviewed-size-options.json'))
    issued_sizes=Path('data/reference/plan-examples/verified-publisher-panel-sizes.json')
    if issued_sizes.is_file():reviewed.update(read(issued_sizes))
    staged=wd/'standards'/'verified-additional-sizes.json'
    if staged.is_file():reviewed.update(read(staged))
    for r in records:
        if 'outlineMask' in r:r['mask']=r['outlineMask']
        r.update(repairs.get(r['id'],{}))
        measure=reviewed.get(r['id'])
        if measure:
            r.update(publisherPlateSize=measure['nominalBounds'],nominalPanelInches=measure.get('size'),publisherPlateSource=measure['source'],
                     publisherSizeBasis=measure['sizeBasis'],publisherPlateCondition=measure['condition'])
            if measure.get('calibrateDiamond'):r['calibrateDiamond']=True
            if measure.get('notes'):r['notes']=measure['notes']
            if measure.get('outlineMask'):r['mask']=measure['outlineMask']
            elif measure.get('sourceMask'):
                src=Path(measure['sourceMask'])
                if digest(src)!=measure['sourceMaskSha256']:raise ValueError('Archived sign mask changed: '+r['id'])
                r['mask']=str(src)
            if measure.get('sourceKind'):r['sourceKind']=measure['sourceKind']
            if measure.get('artworkSourceUrl'):r['sourceUrl']=measure['artworkSourceUrl']
            if measure.get('artworkSourceSha256'):r['referenceSha256']=measure['artworkSourceSha256']

        if r['id'] in variants:r['historicalLegend']=variants[r['id']]['legend']
    # These title legends were copied onto two paper layouts and three unused
    # definitions. The source's ordering distinguishes repeat codes in each legend.
    ordinals=Counter()
    for r in records:
        family=next((s for s in ('3346-title-', '3346-legacy-') if r['id'].startswith(s)),None)
        if family:
            ordinal_key=(family,r['block'],r['code'].casefold())
            ordinals[ordinal_key]+=1
            r['copyFingerprint']=f"{family}{r['code'].casefold()}/{ordinals[ordinal_key]}"

    candidates={r['id']:r for r in records}
    if args.sources:records=[r for r in records if r['drawing'] in args.sources]
    if args.sample:records=[r for r in records if r['id'] in args.sample or r['code'] in args.sample]
    captured={}
    group=defaultdict(list)
    for r in records:group[r['drawing']].append(r)
    allblocks=[];master=new_doc();model=master.modelspace()
    catalog_counts=Counter();unresolved=[]
    for series,subset in group.items():
        source=wd/'all-sources'/(series+'.dxf')
        doc=ezdxf.readfile(source) if any(not r.get('mask') for r in subset) else None
        ctx=drawing_context(doc) if doc else None
        for r in subset:
            id=r['id']
            if not re.fullmatch('[a-zA-Z0-9_.-]+',id):raise ValueError('Unsafe file id: '+id)
            if r.get('mask'):
                marks,rect=read_mask(r['mask'])
            else:
                marks=record(doc,ctx,r)
                rect=get_bounds(marks,r)
            width,height,status,authority,reference=choose_size(r,standards,rect,marks)
            if r.get('calibrateDiamond'):rect=diamond_blank_bounds(marks,rect)
            transformed=scaled_marks(marks,rect,width,height)
            # Collapse exact face copies across drawing layouts. Curves are sampled
            # at the same normalized tolerance independent of source-paper units.
            tokens=[]
            for mark in transformed:
                curves=[]
                for pp in mark.paths:
                    pts=tuple((round(v.x/width,4),round(v.y/height,4)) for v in pp.flattening(max(width,height)/450,segments=3))
                    if pts:curves.append(min(pts,tuple(reversed(pts))))
                if curves:tokens.append((mark.fill,mark.white,tuple(sorted(curves))))
            fingerprint=hashlib.sha256(repr((sorted(tokens),r.get('assemblyComponents',[]))).encode()).hexdigest() if r.get('assemblyComponents') else hashlib.sha256(repr(sorted(tokens)).encode()).hexdigest()
            signature=(designation_key(r['code']),round(width,3),round(height,3),r.get('copyFingerprint') or fingerprint)
            observation={'id':id,'sourceDrawing':series,'sourceHandle':r.get('handle',r.get('recordHandle','')),'space':r.get('space',''),'code':r['code']}
            if signature in captured:
                captured[signature]['observations'].append(observation)
                continue
            name=native_name(r['code'])
            single=new_doc();b=single.blocks.new(name);b.block_record.dxf.units=1
            if r.get('assemblyComponents'):
                parts=[candidates[k] for k in r['assemblyComponents']]
                draw_assembly(b,doc,ctx,parts,rect,width,height)
            else:
                write_geometry(b,transformed,width,height,solid_symbol=not r.get('mask'),ink_extent=r.get('minimumAddedInkY'),join_dangling=r.get('joinArrowContours',False))
            if r.get('knockoutRings'):restore_native_knockouts(b,transformed,width,height)
            if not b.query('HATCH'):
                unresolved.append({'id':id,'code':r['code'],'sourceDrawing':series,'sourceHandle':r.get('handle',''),'reason':'No positive closed sign geometry'});continue
            single.modelspace().add_blockref(name,(0,0));single.set_modelspace_vport(height=max(width,height)*1.22,center=(0,0))
            single.saveas(tmp/(id+'.dxf'))
            catalog_counts[name.upper()]+=1;n=catalog_counts[name.upper()]
            master_name=name if n==1 else name+' ['+r['drawing']+' '+str(n)+']'
            m=master.blocks.new(master_name);m.block_record.dxf.units=1
            for e in b:m.add_entity(e.copy())
            allblocks.append(dict(id=id,code=r['code'],blockName=name,masterBlockName=master_name,
                file='individual/'+('reference-size-unknown/' if reference else '')+id+'.dwg',width=round(width,4),height=round(height,4),sizeStatus=status,
                sizeBasis=authority,sourceDrawing=series,sourceHandle=r.get('handle') or r.get('recordHandle') or '',
                sourceKind=r.get('sourceKind','block'),geometryFingerprint=fingerprint,
                nominalPanelInches=r.get('nominalPanelInches') or r.get('verifiedSize') or r.get('sizeInches'),
                geometryStatus=('current issued artwork' if series=='official-standard' else 'reconciled source variant' if r.get('textOverrides') else 'traced source face' if r.get('mask') else 'source vector'),
                sourceUrl=r.get('sourceUrl'),referenceTitle=r.get('referenceTitle'),aliases=r.get('aliases',[]),
                assembly=bool(r.get('assembly')),componentOf=r.get('componentOf'),componentRole=r.get('componentRole'),historicalLegend=r.get('historicalLegend'),sourceImage=r.get('sourceImage'),referenceAsset=r.get('referenceAsset'),
                referenceSha256=r.get('referenceSha256'),observationIds=r.get('observationIds',[]),
                note=r.get('note') or r.get('notes',''),basepoint=[0,0,0],observations=[observation,*r.get('sourceObservations',[])],
                sizeReference=((r.get('publisherPlateSource') or standards.get(designation_key(r['code']),{}).get('source')) if status=='published reference size' else r.get('sizeReference') or r.get('sizeEvidence')),
                sizeCondition=((r.get('publisherPlateCondition') or standards.get(designation_key(r['code']),{}).get('condition')) if status=='published reference size' else None)))
            captured[signature]=allblocks[-1]
        print(series,len(subset),'selections processed;',len(allblocks),'cumulative blocks',flush=True)
    rows=sorted(allblocks,key=lambda q:(designation_key(q['code']),q['sourceDrawing'],q['id']))
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        rows=list(pool.map(lambda r:encode_job(r,args.bin,tmp,out),rows))
    if not rows:raise ValueError('No sign face survived validation')
    package_master(master,model,rows,unresolved,args.bin,tmp,out)
if __name__=='__main__':main()
