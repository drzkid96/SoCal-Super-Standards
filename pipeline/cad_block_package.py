"""Publish only the verified sign-block deliverables, as one reproducible release package."""
import hashlib
import json
import lzma
import math
from pathlib import Path, PurePosixPath
import re
from collections import defaultdict
import zipfile
import subprocess
import speed_faces
import sign_cells

SOURCE = Path('data/reference/cad-block-downloads')
PUBLIC = Path('public/downloads/sign-blocks')
INDEX = 'manifest.json'
REFERENCE = 'CA-FHWA-SIGN-STANDARDS-REFERENCE.zip'
# The master's header named no dimension style (a null handle AutoCAD reports on open). ODA File
# Converter's audit sets it to Standard; this patch turns the built master into the audited one.
MASTER_FIX = {'file': 'master-fix.patch.zst',
              'from': 'b53069b6924038350abd08a0c1e584fba29d905fd329daedfc8aa64894145889',
              'to': 'ec617d7fd64bc24859c944a043f37307f78ed016d5e9f0b611a59ad113e8d80a'}
# Sign legends re-lettered in FHWA Standard Alphabets and chart-matched faces (reletter_signs.py),
# carried into the master contact sheet's block definitions.
MASTER_LETTERING = {'file': 'lettering-master.patch.zst',
                    'from': 'ec617d7fd64bc24859c944a043f37307f78ed016d5e9f0b611a59ad113e8d80a',
                    'to': '0fb9eda213b8e2376d9af787ee7e1aea87c9e58f340b5f5a073126612a02e05d'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def dump(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def filename(value, suffix):
    path = PurePosixPath(value)
    if (not value or path.is_absolute() or '..' in path.parts or '\\' in value or
        str(path) != value or not value.lower().endswith(suffix)):
        raise ValueError(f'Invalid CAD download path {value!r}')
    return value


def member(bundle, path, data):
    info = zipfile.ZipInfo(path, (1980, 1, 1, 0, 0, 0))
    info.external_attr = 0o100644 << 16
    bundle.writestr(info, data, zipfile.ZIP_DEFLATED, compresslevel=9)


def dwg(file):
    data = file.read_bytes()
    if not re.match(rb'AC10[0-9]{2}', data[:6]):
        raise ValueError(f'Expected a native DWG in {file}')
    return data


def preview_path(record):
    webpath=record['preview'].removeprefix('/')
    name=filename(webpath,'.webp')
    parts=PurePosixPath(name).parts
    if len(parts)!=3 or parts[:2]!=('figs','cad-blocks'):
        raise ValueError(f'Invalid block preview path {name}')
    return name, 'previews/'+parts[-1]


def pin(path):
    data=path.read_bytes()
    return {'file':path.name,'bytes':len(data),'sha256':sha(data)}


def checked(data, record, label):
    if len(data)!=record['bytes'] or sha(data)!=record['sha256']:
        raise ValueError(f'Wrong file size or SHA-256 for {label}')
    return data


def clean_path(file):
    """Web-safe download path: lower-case kebab folders; file names keep the sign code's own case (W4-2l
    is the left version) with spaces and brackets turned into hyphens
    ('individual/Regulatory/Reference size unknown/R28D(CA)(MOD) [3346 title details 3].dwg' ->
    'individual/regulatory/size-unknown/R28D-CA-MOD-3346-title-details-3.dwg')."""
    parts = PurePosixPath(file).parts
    folders = ['size-unknown' if p == 'Reference size unknown' else re.sub(r'[^a-z0-9]+', '-', p.lower()).strip('-')
               for p in parts[:-1]]
    stem = PurePosixPath(parts[-1]).stem
    name = re.sub(r'[^A-Za-z0-9]+', '-', stem).strip('-')
    return '/'.join(folders + [name + PurePosixPath(parts[-1]).suffix.lower()])


def fix_master(data, public):
    """Apply MASTER_FIX, then MASTER_LETTERING, each when the master is the one it was made from."""
    for step in (MASTER_FIX, MASTER_LETTERING):
        patch = SOURCE/step['file']
        if not patch.exists() or sha(data) != step['from']:
            continue
        base = public/'master-fix.base'
        base.write_bytes(data)
        try:
            fixed = subprocess.run(['zstd', '-dc', '--long=27', '--patch-from='+str(base), str(patch)], capture_output=True, check=True).stdout
        finally:
            base.unlink(missing_ok=True)
        if sha(fixed) != step['to']:
            raise ValueError('Master patch ' + step['file'] + ' did not reproduce its drawing')
        data = fixed
    return data


def family_of(record):
    parts=PurePosixPath(record['file']).parts
    names={'Regulatory','Warning','Guide','School','Object markers','Temporary traffic control','Local and other'}
    if len(parts)>2 and parts[1] in names:
        return parts[1]
    code=record['code'].upper()
    for prefix,group in [('R','Regulatory'),('W','Warning'),('SW','Warning'),('D','Guide'),('G','Guide'),('OM','Object markers')]:
        if re.match(re.escape(prefix)+r'\d',code):return group
    return 'Local and other'


def package(folder, dest=SOURCE, preview_dir=None):
    """Track a standalone master and one independently replaceable archive per sign family."""
    manifest=json.loads((folder/INDEX).read_text())
    master=filename(manifest['master'],'.dwg')
    bundle=filename(manifest['bundle'],'.zip')
    if '/' in master or '/' in bundle or not manifest['records']:
        raise ValueError('Invalid master, download bundle or empty CAD inventory')
    dest.mkdir(parents=True,exist_ok=True)
    previous=json.loads((dest/'release.json').read_text()) if (dest/'release.json').exists() else {}
    data=dwg(folder/master)
    if manifest.get('masterSha256') and manifest['masterSha256'].lower()!=sha(data):
        raise ValueError('Master DWG differs from the reviewed release')
    compressed_master=dest/(master+'.xz')
    compressed=lzma.compress(data,format=lzma.FORMAT_XZ,preset=6)
    if lzma.decompress(compressed)!=data:raise ValueError('Master compression failed its round trip')
    compressed_master.write_bytes(compressed)
    manifest.update(masterBytes=len(data),masterSha256=sha(data))
    groups=defaultdict(list)
    ids=set()
    files={master.casefold()}
    for rec in manifest['records']:
        key=rec['id']
        name=filename(rec['file'],'.dwg')
        if (not rec['code'].strip() or not key or key in ids or name.casefold() in files or
            PurePosixPath(name).parts[0]!='individual' or rec.get('roundTrip') is False):
            raise ValueError(f'Unverified, duplicate or invalid drawing {key} at {name}')
        for axis in ('width','height'):
            if not isinstance(rec.get(axis),(float,int)) or not math.isfinite(rec[axis]) or rec[axis]<=0:
                raise ValueError(f'Invalid {axis} for {key}')
        files.add(name.casefold())
        ids.add(key)
        groups[family_of(rec)].append(rec)
    parts=[]
    for family,records in sorted(groups.items()):
        path=dest/(family.lower().replace(' ','-')+'.zip')
        temp=path.with_suffix('.tmp')
        with zipfile.ZipFile(temp,'w') as out:
            for rec in sorted(records,key=lambda r:r['file']):
                data=dwg(folder/rec['file'])
                if rec.get('sha256') and rec['sha256'].lower()!=sha(data):
                    raise ValueError(f'Geometry checksum changed for {rec["id"]}')
                rec.update(sha256=sha(data),bytes=len(data))
                member(out,rec['file'],data)
                if rec.get('preview'):
                    webpath,name=preview_path(rec)
                    preview_file=preview_dir/PurePosixPath(webpath).name if preview_dir else Path('public')/webpath
                    preview=preview_file.read_bytes()
                    if rec.get('previewSha256') and rec['previewSha256'].lower()!=sha(preview):
                        raise ValueError(f'Geometry preview checksum changed for {rec["id"]}')
                    if name.casefold() in files or preview[:4]!=b'RIFF' or preview[8:12]!=b'WEBP':
                        raise ValueError(f'Duplicate or invalid preview {name}')
                    files.add(name.casefold())
                    rec.update(previewBytes=len(preview),previewSha256=sha(preview))
                    member(out,name,preview)
        temp.replace(path)
        parts.append(dict(family=family,records=len(records),**pin(path)))
    release={'version':2,'master':dict(encoding='xz',**pin(compressed_master)),'families':parts}
    if (folder/REFERENCE).is_file():
        if not zipfile.is_zipfile(folder/REFERENCE):raise ValueError('Invalid standards reference archive')
        (dest/REFERENCE).write_bytes((folder/REFERENCE).read_bytes())
        manifest['standardReference']=pin(dest/REFERENCE)
        release['standardReference']=manifest['standardReference']
    if (folder/'README.txt').is_file():
        (dest/'README.txt').write_bytes((folder/'README.txt').read_bytes())
        release['readme']=pin(dest/'README.txt')
    (dest/INDEX).write_bytes(dump(manifest))
    release['manifest']=pin(dest/INDEX)
    temp=dest/'release.tmp'
    temp.write_bytes(dump(release))
    temp.replace(dest/'release.json')
    live={part['file'] for part in parts}
    for part in previous.get('families',[]):
        name=filename(part['file'],'.zip')
        if '/' not in name and name not in live and (dest/name).exists():
            checked((dest/name).read_bytes(),part,name)
            (dest/name).unlink()
    old_master=dest/master
    if old_master.is_file():
        checked(old_master.read_bytes(),{'bytes':manifest['masterBytes'],'sha256':manifest['masterSha256']},master)
        old_master.unlink()
    return release


def hydrate(source=SOURCE, public=PUBLIC):
    """Verify each release packet and generate the complete, ordered one-click archive."""
    release=json.loads((source/'release.json').read_text())
    manifest=json.loads(checked((source/INDEX).read_bytes(),release['manifest'],INDEX))
    master=filename(manifest['master'],'.dwg')
    bundle=filename(manifest['bundle'],'.zip')
    if release['version']!=2 or '/' in master or '/' in bundle:
        raise ValueError('Unsupported CAD release')
    speed_faces.write_faces()
    with zipfile.ZipFile(speed_faces.PACK) as speeds:
        speed_meta=json.loads(speeds.read('metadata.json'))
        faces={n:(speeds.read(f'{n}.dwg'),speeds.read(f'{n}.webp')) for n in range(15,60,5)}
    for rec in manifest['records']:speed_faces.standardize(rec,speed_meta)
    groups=defaultdict(list)
    for rec in manifest['records']:
        groups[family_of(rec)].append(rec)
    if set(groups)!={part['family'] for part in release['families']}:
        raise ValueError('Sign families and manifest differ')
    public.mkdir(parents=True,exist_ok=True)
    previous=json.loads((public/INDEX).read_text()) if (public/INDEX).exists() else {}
    temp=public/(bundle+'.tmp')
    with zipfile.ZipFile(temp,'w') as out:
        storage=release['master']
        if storage.get('encoding')=='xz':
            if storage['file']!=master+'.xz':raise ValueError('Unexpected compressed master path')
            data=lzma.decompress(checked((source/storage['file']).read_bytes(),storage,storage['file']),format=lzma.FORMAT_XZ)
        elif not storage.get('encoding') and storage['file']==master:
            data=checked(dwg(source/master),storage,master)
        else:raise ValueError('Unsupported master storage format')
        checked(data,{'bytes':manifest['masterBytes'],'sha256':manifest['masterSha256']},master)
        if not re.match(rb'AC10[0-9]{2}',data[:6]):raise ValueError('Invalid native master drawing')
        base_master=public/(master+'.base')
        base_master.write_bytes(data)
        try:
            data=subprocess.run(['zstd','-dc','--patch-from='+str(base_master),str(source/'speed-master.patch.zst')],capture_output=True,check=True).stdout
        finally:
            base_master.unlink(missing_ok=True)
        data=fix_master(data,public)
        manifest.update(masterBytes=len(data),masterSha256=sha(data))
        (public/master).write_bytes(data)
        # the master is its own download (20 MB); the bundle holds the individual drawings only
        written=set()
        for part in sorted(release['families'],key=lambda r:r['family']):
            name=filename(part['file'],'.zip')
            if '/' in name:raise ValueError('Unexpected package directory '+name)
            archive=source/name
            checked(archive.read_bytes(),part,name)
            records=groups[part['family']]
            expected={r['file'] for r in records}|{preview_path(r)[1] for r in records if r.get('preview')}
            with zipfile.ZipFile(archive) as packed:
                if len(records)!=part['records'] or sorted(expected)!=sorted(packed.namelist()):
                    raise ValueError('Unexpected contents in '+name)
                for rec in sorted(records,key=lambda r:r['file']):
                    file=filename(rec['file'],'.dwg')
                    speed=speed_faces.value(rec)
                    data=checked(faces[speed][0] if speed else packed.read(file),rec,file)
                    data=sign_cells.apply(rec,data)
                    if not re.match(rb'AC10[0-9]{2}',data[:6]):raise ValueError('Invalid native DWG '+file)
                    web=clean_path(file)
                    n=1
                    while web.casefold() in written:   # 'R9-3B (L)' and 'R9-3B-L' are different drawings
                        n+=1
                        web=re.sub(r'(-\d+)?\.dwg$','',web) if n>2 else web[:-4]
                        web=f'{web}-{n}.dwg'
                    written.add(web.casefold())
                    dest=public/web
                    dest.parent.mkdir(parents=True,exist_ok=True)
                    dest.write_bytes(data)
                    member(out,web,data)
                    rec['file']=web
                    if rec.get('preview'):
                        webpath,file=preview_path(rec)
                        data=checked(faces[speed][1] if speed else packed.read(file),{'bytes':rec['previewBytes'],'sha256':rec['previewSha256']},file)
                        if data[:4]!=b'RIFF' or data[8:12]!=b'WEBP':raise ValueError('Invalid geometry preview '+file)
                        dest=public.parent.parent/webpath
                        dest.parent.mkdir(parents=True,exist_ok=True)
                        dest.write_bytes(data)
                        member(out,file,data)
        if release.get('standardReference'):
            data=checked((source/REFERENCE).read_bytes(),release['standardReference'],REFERENCE)
            (public/REFERENCE).write_bytes(data)
            member(out,REFERENCE,data)
        if release.get('readme'):
            member(out,'README.txt',checked((source/'README.txt').read_bytes(),release['readme'],'README.txt'))
        member(out,INDEX,dump(manifest))
    spec=sign_cells.cells()[1]
    if spec:
        manifest.update(basepoint='lower-left corner of its '+' × '.join(f'{v:g}' for v in spec['cell'])+' in legend cell',
                        individualFormat='one sign block INSERT at 0,0 and one MTEXT sign code (ROMANS), face fitted to the cell',
                        cell=spec)
    temp.replace(public/bundle)
    full=pin(public/bundle)
    manifest.update(bundleBytes=full['bytes'],bundleSha256=full['sha256'])
    (public/INDEX).write_bytes(dump(manifest))
    live_files={r['file'] for r in manifest['records']}
    live_previews={r['preview'] for r in manifest['records'] if r.get('preview')}
    for old in previous.get('records',[]):
        name=filename(old['file'],'.dwg')
        if PurePosixPath(name).parts[0]=='individual' and name not in live_files:
            (public/name).unlink(missing_ok=True)
        if old.get('preview') and old['preview'] not in live_previews:
            (public.parent.parent/preview_path(old)[0]).unlink(missing_ok=True)
    return manifest


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cleaned_output',type=Path)
    parser.add_argument('--previews',type=Path,help='Directory of reviewed geometry-derived WebP files')
    args=parser.parse_args()
    print(json.dumps(package(args.cleaned_output,preview_dir=args.previews),indent=2))
