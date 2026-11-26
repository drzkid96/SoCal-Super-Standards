"""Publish legend-only drawings separately from the dimensioned native collection."""
import json
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
    with ZipFile(pack) as archive:
        rows=json.loads(archive.read('records.json'))
        for row in rows:
            for member,destination in [(row['file'],Path('public/downloads/sign-blocks')/row['file']), (row['preview'][1:],Path('public')/row['preview'][1:])]:
                destination.parent.mkdir(parents=True,exist_ok=True)
                destination.write_bytes(archive.read(member))
        return rows

def publish_geometry():
    folder=Path('public/data/cad-sign-entities')
    path=folder/'index.json'
    for pack in (PACK,Path('data/reference/additional-sign-blocks.zip')):
        add_geometry(pack,folder,path)

def add_geometry(pack,folder,path):
    with ZipFile(pack) as archive:
        index=json.loads(path.read_text())
        extra=json.loads(archive.read('geometry.json'))
        for key in extra:
            name=key+'.dxf.gz'
            (folder/name).write_bytes(archive.read('geometry/'+name))
        path.write_text(json.dumps(index|extra,separators=(',',':')))
