"""Plot the W48(2)(CA) callout using the Caltrans W48 sheet and its authorized Series D numeral."""
import argparse
import copy
import hashlib
import io
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np
import pymupdf
from PIL import Image, ImageDraw
from scipy import ndimage

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('papers',type=Path)
    args=parser.parse_args()
    spec=args.papers/'w48-ca.pdf';alphabet=args.papers/'alphabets.pdf'
    for p,expected in [(spec,'a5b63cf8fb86f36fe80c38cfa67267ecf90a9dc7282f654b5088fb9a4f7f6691'),
                       (alphabet,'782d4527947ab90919440ff8fc8420067cb4492e73fbb1b0500dec11592f27a3')]:
        if hashlib.sha256(p.read_bytes()).hexdigest()!=expected:raise ValueError(f'Changed source {p}')
    guide=pymupdf.open(spec);face=guide[0]
    assert '2 to 6 inclusive' in face.get_text()
    code=Image.open(io.BytesIO(guide.extract_image(face.get_images()[0][0])['image'])).convert('L')
    # Rectify the scanned sheet to the printed 30 x 24 inch material frame.
    width,height=1500,1200
    quad=(510,391,501,1315,1653,1310,1662,387)
    source=code.transform((width,height),Image.Transform.QUAD,quad,Image.Resampling.BICUBIC)
    ink=np.asarray(source)<128
    # The black T in the Caltrans original is separate from its black outline. Its interior
    # is bounded independently of the witness lines, threaded mounting holes and dimension text.
    thick=ndimage.binary_erosion(ink,iterations=8)
    components,n=ndimage.label(thick);areas=np.bincount(components.ravel());areas[0]=0
    field=ndimage.binary_fill_holes(ndimage.binary_dilation(components==np.argmax(areas),iterations=8))
    distance=ndimage.distance_transform_edt(~field)
    frame=Image.new('L',(width,height),255)
    ImageDraw.Draw(frame).rounded_rectangle((1,1,width-2,height-2),radius=100,outline=0,width=3)
    out=np.array(frame)
    # The printed margin and border widths are each 1/2 inch.
    outline=(distance>25)&(distance<=50)
    out[outline]=0;out[field]=0
    # Preserve the six actual TRACKS letter outlines; all annotation belongs outside this window.
    text=np.zeros_like(ink);text[594:877,114:1390]=~ink[594:877,114:1390]
    out[text&field]=255

    # Exact Series D numeral, six-inch capital height (Caltrans line 1 = 6D). Keep the original
    # print registration center and baseline; only the variable digit changes.
    nums=pymupdf.open(alphabet)
    page=ET.fromstring(nums[23].get_svg_image(text_as_path=True))
    uses=[e for e in page.iter() if e.tag.endswith('use') and e.get('data-text')=='2'
          and e.get('transform','').startswith('matrix(507.999')]
    assert len(uses)==1
    actual=uses[0];key=actual.get('{http://www.w3.org/1999/xlink}href').lstrip('#')
    glyph=copy.deepcopy(next(e for e in page.iter() if e.get('id')==key))
    colored=ET.Element('svg',{'xmlns':'http://www.w3.org/2000/svg','width':'612','height':'792','viewBox':'0 0 612 792'})
    glyph.set('transform',actual.get('transform'));glyph.set('fill','#000000');colored.append(glyph)
    with pymupdf.open(stream=ET.tostring(colored),filetype='svg') as doc:
        pix=doc[0].get_pixmap(matrix=pymupdf.Matrix(4,4),alpha=True)
        glyph_img=Image.frombytes('RGBA',(pix.width,pix.height),pix.samples).getchannel('A')
    glyph_img=glyph_img.crop(glyph_img.getbbox())
    h=300;w=round(h*glyph_img.width/glyph_img.height)
    glyph_img=glyph_img.resize((w,h),Image.Resampling.LANCZOS)
    im=Image.fromarray(out);im.paste(255,(round((width-w)/2),228),glyph_img)
    target=Path(__file__).resolve().parents[1]/'data/reference/cad-standards/callout-faces/w48ca.png'
    im.save(target)

if __name__=='__main__':main()
