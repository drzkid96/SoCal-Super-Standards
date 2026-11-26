"""Select verified sign blocks from the chart, CAD search, or sign record."""
from html import escape, unescape
from pathlib import Path
import json
import re

from current_catalog import BASE

CSS=f'<link rel="stylesheet" href="{BASE}/js/sign-cart.css">'
SCRIPTS=''.join(f'<script defer src="{BASE}/js/{name}.js"></script>' for name in ('sign-cart-zip','sign-cart'))
ESC=lambda value:escape(str(value),quote=True)

def format_size(rec):
    if rec['sizeStatus']=='Reference size unknown':return 'Size unknown'
    sides=rec.get('publishedSides')
    if sides and len(set(sides))==1:return f'{sides[0]:g} in sides'
    return f'{rec["width"]:g} × {rec["height"]:g} in'

def variant(rec):
    label=rec.get('historicalLegend')
    if isinstance(label,str) and label:return label
    if rec['sourceDrawing']=='official-standard':
        return 'Issued layout' if rec.get('geometryStatus')!='historical issued artwork' else 'Historical layout'
    return rec.get('sourceLabel') or rec['sourceDrawing']

def checkbox(rec,descriptive=False):
    dims=format_size(rec)
    label=dims+' · '+variant(rec) if descriptive else dims
    return (f'<label class="sign-check"><input type="checkbox" data-cart-select="{ESC(rec["id"])}" '
            f'aria-label="Select {ESC(rec["code"])} · {ESC(dims)} · {ESC(variant(rec))}">'
            f'<span>{ESC(label)}</span></label>')

def shell():
    return (CSS+'<div class="sign-cart-shell" data-sign-cart hidden><button class="sign-cart-open" type="button" '
            'data-cart-open aria-haspopup="dialog">Selected signs <strong data-cart-count>0</strong></button>'
            '<dialog class="sign-cart-dialog" data-cart-dialog aria-labelledby="sign-cart-title"><header>'
            '<h2 id="sign-cart-title">Selected signs</h2><button type="button" data-cart-close aria-label="Close selected signs">Close</button>'
            '</header><div class="sign-cart-workspace"><figure class="legend-preview" data-legend-preview hidden>'
            '<figcaption data-legend-caption></figcaption><div class="legend-frame"><div class="legend-grid" data-legend-grid></div></div>'
            '<div class="legend-nav" data-legend-nav hidden><button type="button" data-legend-prev aria-label="Previous table">←</button>'
            '<button type="button" data-legend-next aria-label="Next table">→</button></div></figure>'
            '<div class="legend-order"><p data-cart-order-label>Legend order</p><ul data-cart-items></ul></div></div>'
            '<p data-cart-status role="status" aria-live="polite"></p><footer>'
            '<button type="button" data-cart-clear>Clear selection</button><button type="button" data-cart-download>Download sign legend</button>'
            '</footer></dialog></div>'+SCRIPTS)

def write_options(records):
    options=[]
    for r in records:
        code=r['code']
        speed=re.fullmatch(r'R2-1(?:[- (]| ?MPH )*(15|20|25|30|35|40|45|50|55|60|65|70|75|80|85)\)?',code,re.I)
        printed=re.fullmatch(r'SPEED LIMIT (\d+)',str(r.get('historicalLegend','')),re.I)
        if speed or (code=='R2-1' and printed):
            code='R2-1('+str((speed or printed)[1])+')'
        options.append(dict(id=r['id'],code=code,name=r.get('description') or r['code'],blockName=r['blockName'],file=r['file'],width=r['width'],
                            height=r['height'],sizeStatus=r['sizeStatus'],sizeLabel=format_size(r),variant=variant(r),
                            preview=r.get('preview',''),aliases=r['aliases'],signUrl=r['signUrl'],sha256=r['sha256'],bytes=r['bytes']))
    Path('public/data/sign-block-options.json').write_text(json.dumps(options,ensure_ascii=False,separators=(',',':'))+'\n')

def chart_tiles(content,by_url):
    seen=set()
    speeds=set()
    def tile(match):
        card=match[0]
        url=unescape(re.search(r' href="([^"]+)"',card)[1])
        choices=by_url.get(url)
        if not choices:return card
        seen.update(r['id'] for r in choices)
        choices=sorted(choices,key=lambda r:(r['sourceDrawing']!='official-standard',r['sizeStatus']=='Reference size unknown',bool(r.get('observationIds')),r['id']))
        main=choices[0]
        # Source drawings often repeat the very same speed face under alternate names.
        speed=next((m[1] for r in choices for a in [r['code'],*r['aliases']]
                    if (m:=re.fullmatch(r'R2-1(?:[- (]| ?MPH )*(15|20|25|30|35|40|45|50|55|60|65|70|75|80|85)\)?',a,re.I))),None)
        if speed and main['code']!='R2-1':
            if speed in speeds:return ''
            speeds.add(speed)
            choices=[main]
            card=re.sub(r'(<span class="scode">).*?(</span>)',r'\g<1>R2-1 ('+speed+r')\2',card,count=1)
            card=re.sub(r'(<span class="sname">).*?(</span>)',r'\g<1>Speed limit '+speed+r' mph\2',card,count=1)
        card=card.replace('class="scard','data-dwg="1" class="scard',1)
        if 'class="simg"' not in card and main.get('preview'):
            art=f'<span class="simg"><img loading="lazy" decoding="async" src="{BASE}{ESC(main["preview"])}" alt=""></span>'
            card=card.replace('><span','>'+art+'<span',1)
        if not main.get('description') and main.get('historicalLegend') and isinstance(main['historicalLegend'],str):
            card=re.sub(r'<span class="sname">[^<]*</span>','<span class="sname">'+ESC(main['historicalLegend'])+'</span>',card)
        alt=''
        if len(choices)>1:
            alt=(f'<details class="sign-variants"><summary>{len(choices)-1} more variant'+('s' if len(choices)>2 else '')+'</summary>'
                 +''.join(checkbox(r,True) for r in choices[1:])+'</details>')
        return '<div class="sign-tile">'+card+'<div class="sign-tile-pick">'+checkbox(main)+alt+'</div></div>'
    content=re.sub(r'<a class="scard[^"]*"[^>]*>[\s\S]*?</a>',tile,content)
    missing={r['id'] for rs in by_url.values() for r in rs}-seen
    if missing:raise ValueError('Native drawings absent from sign chart: '+', '.join(sorted(missing)[:10]))
    return content
