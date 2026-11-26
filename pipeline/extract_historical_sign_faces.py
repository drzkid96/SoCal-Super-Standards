"""Recover two historical issuing-agency layouts from the pinned FHWA and Caltrans PDFs."""
import argparse
import hashlib
import io
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np
import pymupdf
from PIL import Image,ImageDraw
from scipy import ndimage

SOURCES={'guide-2004.pdf':'eb0d9cf3c728146dfb386d59fb805a7aa4c178783cd3fa04d9f85a0524d4f246',
         'g96ca.pdf':'aec8cee9b928daf0d199d8b867acc4ece5a061db83c220db79e60e45ecb39ba3'}

def hospital(file,output):
    doc=pymupdf.open(file)
    page=doc[73];frame,field=page.get_drawings()[:2]
    assert 'D9-13a' in page.get_text() and field['even_odd'] and abs(frame['rect'].width/frame['rect'].height-2)<.0001
    x,y=frame['rect'].x0,frame['rect'].y0
    svg=ET.Element('svg',{'xmlns':'http://www.w3.org/2000/svg','viewBox':'0 0 360 180','width':'360','height':'180'})
    def xy(pt):return f'{pt.x-x:.4f} {pt.y-y:.4f}'
    for drawn,attrs in [(frame,{'fill':'white','stroke':'black','stroke-width':'0.6'}),(field,{'fill':'black','fill-rule':'evenodd'})]:
        cmds=[];end=None
        for seg in drawn['items']:
            if seg[0] not in ('l','c'):raise ValueError(seg[0])
            if end is None or abs(seg[1]-end)>.005:
                if end is not None:cmds.append('Z')
                cmds.append('M'+xy(seg[1]))
            cmds.append(('L' if seg[0]=='l' else 'C')+' '.join(xy(p) for p in seg[2:]))
            end=seg[-1]
        cmds.append('Z')
        ET.SubElement(svg,'path',{'d':' '.join(cmds),**attrs})
    original=ET.fromstring(page.get_svg_image(text_as_path=True))
    definitions={e.get('id'):e for e in original.iter() if e.get('id')}
    letters=[u for u in original.iter() if u.tag.endswith('use') and u.get('fill')=='#ffffff'
             and u.get('transform','').startswith('matrix(210.398') and ',250.9679)' in u.get('transform','')]
    if ''.join(e.get('data-text','') for e in letters)!='HOSPITAL':
        raise ValueError('Unexpected SHS D9-13a lettering')
    for use in letters:
        glyph=definitions[use.get('{http://www.w3.org/1999/xlink}href')[1:]]
        ET.SubElement(svg,'path',{'d':glyph.get('d'),'fill':'white','transform':f'translate({-x} {-y}) '+use.get('transform')})
    output.write_bytes(ET.tostring(svg,encoding='utf-8'))

def light_rail(file,output):
    pdf=pymupdf.open(file)
    scan=Image.open(io.BytesIO(pdf.extract_image(pdf[0].get_images()[0][0])['image'])).convert('L')
    assert scan.size==(2572,3317)
    # Sheet coordinates in the original CCITT scan, with the material edge at x=718..1934, y=637..1852.
    # Extract only the printed train; external dimension lines never enter the crop.
    raw=np.asarray(scan)>127
    white=np.zeros(raw.shape,dtype=bool)
    white[737:1765,989:1668]=raw[737:1765,989:1668]
    # Remove isolated scan speckles and the dimension centerline ticks in the windshield.
    labels,n=ndimage.label(white);area=np.bincount(labels.ravel());area[0]=0
    white=np.isin(labels,np.flatnonzero(area>350))
    white[1216:1270,1301:1358]=False
    cut=Image.fromarray(np.where(white[637:1853,718:1934],255,0).astype('uint8')).resize((1800,1800),Image.Resampling.LANCZOS)
    # The conventional stock is a 24-inch square with 1/2-inch white perimeter, 1.5-inch outer corners.
    im=Image.new('L',(1800,1800),255);pen=ImageDraw.Draw(im)
    pen.rounded_rectangle((1,1,1798,1798),radius=round(1.5*75),outline=0,width=3)
    margin=round(.5*75)
    pen.rounded_rectangle((margin,margin,1799-margin,1799-margin),radius=round(75*(1.5-.5)),fill=0)
    im.paste(255,mask=cut.point(lambda v:255 if v>127 else 0));im.save(output)

def main():
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('input',type=Path);args=cli.parse_args()
    out=Path(__file__).resolve().parents[1]/'data/reference/cad-standards/callout-faces';out.mkdir(exist_ok=True)
    for name,expected in SOURCES.items():
        if hashlib.sha256((args.input/name).read_bytes()).hexdigest()!=expected:raise ValueError('Unverified source '+name)
    hospital(args.input/'guide-2004.pdf',out/'d9-13a.svg')
    light_rail(args.input/'g96ca.pdf',out/'g96ca.png')
if __name__=='__main__':main()
