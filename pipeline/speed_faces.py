"""Shared R2-1 geometry for the chart, individual drawings and sheet legends."""
import json
import re
from pathlib import Path
from zipfile import ZipFile

PACK = Path('data/reference/speed-faces.zip')

def posted(code):
    match = re.fullmatch(r'R2-1[- (]*(15|20|25|30|35|40|45|50|55)\)?', code.strip(), re.I)
    return int(match[1]) if match else None

def value(row):
    if row['code']=='R2-1':
        return 15 if row.get('historicalLegend')=='SPEED LIMIT 15' else 50
    return posted(row['code'])

def preview(speed):
    return f'/figs/cad-blocks/speed-{speed}.webp'

def standardize(row,metadata):
    speed=value(row)
    if speed is None:return
    details=metadata[str(speed)]
    for key in ('bytes','sha256','previewBytes','previewSha256','entityCount','solidHatches'):
        row[key]=details[key]
    row.update(width=24,height=30,sizeStatus='published reference size',sizeBasis='Standardized 24 × 30 in R2-1 panel',
               geometryStatus='Standardized posted speed',sizeCondition='',geometryNote='',
               masterBlockName='R2-1' if row['id']=='official-r2-1' else f'R2-1({speed})')

def write_faces():
    with ZipFile(PACK) as z:
        for speed in range(15,60,5):
            dest=Path('public'+preview(speed));dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(z.read(f'{speed}.webp'))
        Path('public/signs/R2-1.svg').write_bytes(z.read('50.svg'))

def geometry(folder):
    path=folder/'index.json'
    index=json.loads(path.read_text())
    rows=json.loads(Path('public/data/sign-block-options.json').read_text())
    with ZipFile(PACK) as z:
        meta=json.loads(z.read('metadata.json'))
        for row in rows:
            n=value(row)
            if n is None:continue
            m=meta[str(n)]
            (folder/(row['id']+'.dxf.gz')).write_bytes(z.read(f'{n}.dxf.gz'))
            index[row['id']]=dict(name=row['blockName'],bytes=m['geometryBytes'],sha256=m['geometrySha'],entities=m['entityCount'],bounds=m['bounds'])
    path.write_text(json.dumps(index,separators=(',',':')))
