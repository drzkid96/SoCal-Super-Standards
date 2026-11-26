"""Panel-only artwork extracted from the issuing Caltrans sign specification sheets.

Coordinates and graphic indices refer to page 1 of the archived specification at
the indicated agency permalink. The four scanned sheets state their substrate
colors in text, while the other six print the actual color artwork.
"""
import hashlib
import math

import numpy as np
import pymupdf
from PIL import Image
from scipy import ndimage

HOST='https://dot.ca.gov/-/media/dot-media/programs/safety-programs/documents/signs/'
SPECS={
    'r99ca':('R99(CA)','r/r99-r99b-a11y.pdf','PARKING ONLY'),
    'r99cca':('R99C(CA)','r/r99c-a11y.pdf','PARKING ONLY · MINIMUM FINE $250'),
    'sc3ca':('SC3(CA)','sc/f0019306-sc3-a11y.pdf','DETOUR with straight-ahead arrow'),
    'sr4-1ca':('SR4-1(CA)','sr/f0019396-sr4-1-a11y.pdf','SCHOOL · SPEED LIMIT 25 · WHEN CHILDREN ARE PRESENT'),
    'sw24-1ca':('SW24-1(CA)','sw/f0019433-sw24-1-a11y.pdf','School crossing symbol · SCHOOL'),
    'sw24-2ca':('SW24-2(CA)','sw/f0019434-sw24-2-a11y.pdf','School crossing symbol · down-left arrow'),
    'sw24-3ca':('SW24-3(CA)','sw/f0019435-sw24-3-a11y.pdf','School crossing symbol · AHEAD'),
    'w31ca':('W31(CA)','w/f0019474-w31-a11y.pdf','END'),
    'w73aca':('W73A(CA)','w/f0019501-w73a-a11y.pdf','RIGHT LANE TURNS RIGHT AHEAD'),
    'w74ca':('W74(CA)','w/f0019502-w74-a11y.pdf','THRU TRAFFIC MERGE LEFT'),
}
# Graphic indices contain the substrate, border, pictograms, rules, and outlined lettering.
# Additional rectangles contain rendered PDF font glyphs on an otherwise clean field.
VECTORS={
    'r99ca':((219.6,97.2,392.4,356.4),range(68,72),[(226.9,229,385,337)]),
    'r99cca':((219.6,118.8,392.4,464.4),range(18,22),[(226.8,252,385.2,445)]),
    'sr4-1ca':((208.2,93.2,403.8,484.2),range(13,29),[(220,279,393,470)]),
    'sw24-1ca':((198.3,123,414.3,425.3),range(33,45),[(208,353,405,410)]),
    'sw24-2ca':((198.3,123,414.3,425.3),[*range(26,38),88],[]),
    'sw24-3ca':((198.3,123,414.3,425.3),range(33,45),[(208,353,405,410)]),
}
# Each inset border is a complete connected ink shape in the high-resolution print scan.
# The last number is the measured distance from that ink border to the panel cut edge in PDF points.
SCANS={
    'sc3ca':((149,246,447,364),(255,139,37),2.5),
    'w31ca':((144,54,487,395),(255,211,32),4.7),
    'w73aca':((168,120,474,430),(255,211,32),6.2),
    'w74ca':((134,106,505,482),(255,211,32),4.9),
}


def draw_path(page, path):
    shape=page.new_shape()
    for op,*values in path['items']:
        if op=='l':shape.draw_line(*values)
        elif op=='c':shape.draw_bezier(*values)
        elif op=='re':shape.draw_rect(values[0])
        elif op=='qu':shape.draw_quad(values[0])
        else:raise ValueError(f'Unsupported printed path operation {op}')
    shape.finish(color=path['color'], fill=path['fill'],width=path.get('width') or .35,
                 even_odd=bool(path.get('even_odd')),closePath=bool(path.get('closePath')),
                 fill_opacity=path.get('fill_opacity') or 1,stroke_opacity=path.get('stroke_opacity') or 1)
    shape.commit()


def rgb(page,rect,scale):
    pm=page.get_pixmap(matrix=pymupdf.Matrix(scale,scale),clip=rect,alpha=False)
    return Image.frombytes('RGB',(pm.width,pm.height),pm.samples)


def vector_face(slug,document,resolution):
    rect,indices,legend_boxes=VECTORS[slug];rect=pymupdf.Rect(rect)
    page=document[0];paths=page.get_drawings()
    with pymupdf.open() as cleaned:
        art=cleaned.new_page(width=page.rect.width,height=page.rect.height)
        for i in indices:draw_path(art,paths[i])
        for region in legend_boxes:
            region=pymupdf.Rect(region)
            art.show_pdf_page(region,document,0,clip=region)
        return rgb(art,rect,resolution/max(rect.width,rect.height))


def scan_face(slug,document,resolution):
    coords,color,offset=SCANS[slug];rect=pymupdf.Rect(coords)
    scale=5
    im=rgb(document[0],rect,scale).convert('L')
    ink=np.asarray(im)<146
    labels,count=ndimage.label(ink)
    counts=np.bincount(labels.ravel());counts[0]=0
    ring=labels==counts.argmax()
    inner=ndimage.binary_fill_holes(ring)
    if inner.sum()<ink.size*.32:raise ValueError(f'Incomplete printed panel perimeter for {slug}')
    # Select every substantial printed glyph enclosed by the native inset border.
    # The 3/8-inch drill-hole circles and stray scan specks are smaller than a glyph.
    inside_ids=np.unique(labels[inner])
    retain=inside_ids[(inside_ids!=0)&(counts[inside_ids]>35*scale**2)]
    letters=np.isin(labels,retain)&inner
    field=ndimage.distance_transform_edt(~inner)<=offset*scale
    pixels=np.full((*ink.shape,3),255,np.uint8);pixels[field]=color;pixels[letters]=(19,19,18)
    yy,xx=np.where(field)
    out=Image.fromarray(pixels[yy.min():yy.max()+1,xx.min():xx.max()+1])
    # A few of the agency's legacy sheet scans are tilted. Level the two
    # horizontal diamond vertices in the printed border before thumbnailing.
    if slug!='sc3ca':
        y,x=np.where(ring);lo=x.min();hi=x.max()
        left=y[x<lo+4].mean();right=y[x>hi-4].mean()
        angle=math.degrees(math.atan2(right-left,hi-lo))
        if abs(angle)>.1:
            out=out.rotate(angle,resample=Image.Resampling.BICUBIC,expand=True,fillcolor='white')
            pigment=np.asarray(out)
            cy,cx=np.where((pigment.max(axis=2)-pigment.min(axis=2)>45)|(pigment.max(axis=2)<155))
            out=out.crop((cx.min(),cy.min(),cx.max()+1,cy.max()+1))
        # These three sheets specify square panels rotated 45 degrees. Compensate
        # for small scan stretch after leveling the native border.
        return out.resize((resolution,resolution),Image.Resampling.LANCZOS)
    out.thumbnail((resolution,resolution),Image.Resampling.LANCZOS)
    return out


def from_spec(slug,pdf,resolution=1400):
    with pymupdf.open(pdf) as source:
        return (vector_face if slug in VECTORS else scan_face)(slug,source,resolution)

NAMES={
    'r99ca':'Accessible parking','r99cca':'Accessible parking with minimum fine','sc3ca':'Detour straight ahead',
    'sr4-1ca':'School speed limit when children are present','sw24-1ca':'School crossing',
    'sw24-2ca':'School crossing with diagonal arrow','sw24-3ca':'School crossing ahead',
    'w31ca':'End','w73aca':'Right lane turns right ahead','w74ca':'Thru traffic merge left',
}


def corrected_metadata(slug):
    code,url,legend=SPECS[slug]
    category=('regulatory' if slug.startswith('r99') else 'work zone' if slug=='sc3ca' else 'school' if slug.startswith('s') else 'warning')
    if slug.startswith('r99'):colors='White legend on blue'
    elif slug.startswith('sw'):colors='Black legend and border on fluorescent yellow-green'
    elif slug=='sr4-1ca':colors='Black legend on white with a fluorescent yellow-green SCHOOL panel'
    else:colors=('Black legend and border on orange' if slug=='sc3ca' else 'Black legend and border on yellow')
    return dict(name=NAMES[slug],descriptor=NAMES[slug]+' '+category+' sign',caption=legend,legend_ocr=legend,
                colors=colors,source='Caltrans sign specification '+code,sourceUrl=HOST+url)


def prepare_issued(slug, pdf, asset, out, key, resolution):
    if not pdf.is_file():raise FileNotFoundError(f'Download {HOST+SPECS[slug][1]} to {pdf}')
    im=from_spec(slug,pdf,max(1400,resolution));pixels=np.asarray(im)
    # These isolated faces use actual publisher inks. Orange construction sheets and
    # fluorescent school signs have black glyphs and need no red-slash separation.
    if slug.startswith('r99'):
        ink=pixels.mean(axis=2)<191
    else:
        ink=pixels.max(axis=2)<155
        field=(pixels.max(axis=2)-pixels.min(axis=2)>45)|ink
        silhouette=ndimage.binary_fill_holes(field)
        ink |= silhouette & ~ndimage.binary_erosion(silhouette,iterations=max(1,round(max(ink.shape)*.0013)))
    Image.fromarray(np.where(ink,0,255).astype('uint8')).save(out)
    im.thumbnail((850,850),Image.Resampling.LANCZOS)
    asset.parent.mkdir(parents=True,exist_ok=True);im.save(asset,'WEBP',lossless=True,method=6)
    info=corrected_metadata(slug)
    return dict(id='official-'+key,drawing='official-standard',code=SPECS[slug][0],outlineMask=str(out.resolve()),
        sourceKind='current issued sign artwork',sourceUrl=info['sourceUrl'],referenceTitle=info['source'],
        referenceLegend=info['caption'],referenceColors=info['colors'],
        referenceAsset='/signs/ca/'+slug+'.webp',referenceType='issued-specification-panel',
        referenceSha256=hashlib.sha256(pdf.read_bytes()).hexdigest(),resolution=[ink.shape[1],ink.shape[0]],
        notes='Panel isolated from the Caltrans sign specification. The printed example provides the legend and orientation.')
