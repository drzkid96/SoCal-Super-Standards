"""Publish legend-only drawings separately from the dimensioned native collection."""
import json
import speed_faces
import sign_cells
from cad_block_package import clean_path
from pathlib import Path
from zipfile import ZipFile

PACK = Path('data/reference/plan-face-blocks.zip')

def publish():
    rows=[]
    for pack in (PACK,Path('data/reference/additional-sign-blocks.zip')):
        rows.extend(publish_pack(pack))
    Path('public/data/plan-face-options.json').write_text(json.dumps(rows))
    return rows

def publish_pack(pack):
    with ZipFile(pack) as archive, ZipFile(speed_faces.PACK) as speeds:
        metadata=json.loads(speeds.read('metadata.json'))
        rows=json.loads(archive.read('records.json'))
        for row in rows:
            n=speed_faces.value(row)
            if n:speed_faces.standardize(row,metadata)
            web=clean_path(row['file'])
            for member,destination in [(row['file'],Path('public/downloads/sign-blocks')/web), (row['preview'][1:],Path('public')/row['preview'][1:])]:
                destination.parent.mkdir(parents=True,exist_ok=True)
                data=speeds.read(str(n)+destination.suffix) if n else archive.read(member)
                if destination.suffix=='.dwg':data=sign_cells.apply(row,data)
                destination.write_bytes(data)
            row['file']=web
        return rows

def publish_geometry():
    folder=Path('public/data/cad-sign-entities')
    path=folder/'index.json'
    for pack in (PACK,Path('data/reference/additional-sign-blocks.zip')):
        add_geometry(pack,folder,path)
    speed_faces.geometry(folder)

def add_geometry(pack,folder,path):
    with ZipFile(pack) as archive:
        index=json.loads(path.read_text())
        extra=json.loads(archive.read('geometry.json'))
        for key in extra:
            name=key+'.dxf.gz'
            (folder/name).write_bytes(archive.read('geometry/'+name))
        path.write_text(json.dumps(index|extra,separators=(',',':')))
