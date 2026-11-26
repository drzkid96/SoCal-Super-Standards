"""Recover the four actual BMP CONTENTS streams in the FP DWG's embedded OLE sign faces."""
import io
import re
import struct
from PIL import Image


def bitmap_contents(entity):
    compound=entity.binary_data()
    signature=bytes.fromhex('D0CF11E0A1B11AE1')
    start=compound.index(signature)
    data=compound[start:]
    u32=lambda offset: struct.unpack_from('<I',data,offset)[0]
    sector=1<<struct.unpack_from('<H',data,30)[0]
    offset=lambda index:(index+1)*sector
    count=u32(44)
    if count>109:raise ValueError('Source requires extended DIFAT')
    fat=[]
    for n in struct.unpack_from('<109I',data,76)[:count]:
        fat.extend(struct.unpack_from(f'<{sector//4}I',data,offset(n)))
    def stream(n):
        seen=set();chunks=[]
        while n<0xfffffffa:
            if n in seen or n>=len(fat):raise ValueError('Invalid compound sector chain')
            seen.add(n);chunks.append(data[offset(n):offset(n)+sector]);n=fat[n]
        return b''.join(chunks)
    directory=stream(u32(48))
    for n in range(0,len(directory),128):
        entry=directory[n:n+128]
        name=entry[:struct.unpack_from('<H',entry,64)[0]].decode('utf-16-le').rstrip('\0')
        size=struct.unpack_from('<Q',entry,120)[0]
        if entry[66]==2 and name=='CONTENTS' and size>=u32(56):
            bmp=stream(struct.unpack_from('<I',entry,116)[0])[:size]
            if bmp[:2]==b'BM':return Image.open(io.BytesIO(bmp)).convert('L')
    raise ValueError(f'No embedded source bitmap in {entity.dxf.handle}')


def extract(lib, work, ole_labels):
    out=work/'masks';out.mkdir(exist_ok=True)
    records=[]
    for label,handle in ole_labels.items():
        original=bitmap_contents(lib.entities[handle])
        # This sign is white-on-neutral or black-on-neutral artwork. Crop the native
        # empty bitmap border against the first/last actual printed ink.
        ink=original.point(lambda value:255 if value<105 else 0)
        bb=ink.getbbox()
        if not bb:raise ValueError(f'Empty embedded sign: {handle}')
        mask=ink.crop(bb).point(lambda value:255-value)
        path=out/f'fp-ole-{handle.lower()}.png';mask.save(path)
        raw=lib.texts[label]
        m=re.search(r'(\d+)"\s*[xX]\s*(\d+)"',raw)
        if not m:raise ValueError(f'Missing embedded sign dimensions at {label}')
        code='EXCEPT BUSES (CUSTOM)' if label=='1B2CF' else raw.splitlines()[0]
        key=f'fp-signs-ole-{handle.lower()}'
        records.append(dict(id=key,drawing=lib.key,code=code,block=lib.name,recordHandle=lib.model.block_record_handle,
                    blockHandle=lib.doc.blocks.get(lib.name).block.dxf.handle,space='Model',use='placed',sourceKind='embedded bitmap',
                    labelHandle=label,handle=handle,mask=str(path.resolve()),verifiedSize=[int(m[1]),int(m[2])],
                    sizeReference='FP sign library printed label '+label+': '+m.group(),
                    note=f'Vector contours from the actual {original.width}×{original.height} pixel bitmap embedded as OLE object {handle}.'))
    return records
