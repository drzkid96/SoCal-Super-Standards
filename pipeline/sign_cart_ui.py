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
    if rec['sizeStatus']=='Reference size unknown':return ''
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
    label=' · '.join(filter(None,(dims,variant(rec)))) if descriptive else (dims or 'Select DWG')
    return (f'<label class="sign-check"><input type="checkbox" data-cart-select="{ESC(rec["id"])}" '
            f'aria-label="Select {ESC(rec["code"])} · {ESC(label)}">'
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

def posted_speed(rec):
    code=rec['code']
    printed=re.fullmatch(r'SPEED LIMIT (\d{1,2})',str(rec.get('historicalLegend','')),re.I)
    suffix=re.fullmatch(r'R2-1(?:[- (]| ?MPH )*(\d{2})\)?',code,re.I)
    return int(suffix[1]) if suffix else int(printed[1]) if code=='R2-1' and printed else None

def write_options(records):
    options=[]
    for r in records:
        speed=posted_speed(r)
        code=f'R2-1({speed})' if speed else r['code']
        options.append(dict(id=r['id'],code=code,name=r.get('description') or r['code'],blockName=r['blockName'],file=r['file'],width=r['width'],
                            height=r['height'],sizeStatus=r['sizeStatus'],sizeLabel=format_size(r),variant=variant(r),
                            preview=r.get('preview',''),aliases=r['aliases'],signUrl=r['signUrl'],sha256=r['sha256'],bytes=r['bytes']))
    Path('public/data/sign-block-options.json').write_text(json.dumps(options,ensure_ascii=False,separators=(',',':'))+'\n')

def chart_tiles(content,by_url):
    seen=set()
    speed_records={}
    for group in by_url.values():
        for rec in group:
            value=posted_speed(rec)
            if value:
                speed_records.setdefault(value,{})[rec['id']]=rec
    def speed_tiles():
        result=[]
        for speed,records in sorted(speed_records.items()):
            main=min(records.values(),key=lambda r:(r['sourceDrawing']!='official-standard',not format_size(r),r['id']))
            code=f'R2-1({speed})'
            aliases='|'.join(sorted({code,'R2-1',f'R2-1-{speed}',*(a for r in records.values() for a in r['aliases'])}))
            name=f'Speed limit {speed} mph'
            result.append(f'<div class="sign-tile"><a data-dwg="1" class="scard" href="{ESC(main["signUrl"])}" data-code="{code}" '
                          f'data-cad="1" data-aliases="{ESC(aliases)}" data-name="{name.lower()}" data-cat="regulatory" data-ca="ca">'
                          f'<span class="simg"><img loading="lazy" decoding="async" src="{BASE}{ESC(main["preview"])}" alt=""></span>'
                          f'<span class="scode">R2-1 ({speed})</span><span class="sname">{name}</span></a>'
                          f'<div class="sign-tile-pick">{checkbox(main)}</div></div>')
        return ''.join(result)
    # Group directional spellings only when base, direction and modifiers agree.
    spelling=re.compile(r'([A-Z]+\d+(?:-\d+)+)(?:-(LEFT|RIGHT)|\((LEFT|RIGHT|LT|RT|L|R)\)|([LR]))((?:\([^()]+\))*)$',re.I)
    groups={}
    for url,records in by_url.items():
        for rec in records:
            m=spelling.fullmatch(rec['code'].replace(' ',''))
            if m:
                base,dash,paren,suffix,rest=m.groups()
                key=(base.upper(),(dash or paren or suffix)[0].upper(),rest.upper())
                groups.setdefault(key,{}).setdefault(url,[]).append(rec)
    redirects={}
    aliases={}
    for (base,hand,rest),urls in groups.items():
        if len(urls)<2:continue
        canonical=base+'('+hand+')'+rest
        primary=min(urls,key=lambda url:(not any(r['code'].upper()==canonical and r['signUrl']==url for r in urls[url]),url))
        # An official record may carry other variants. Preserve mixed-use routes.
        for url,records in urls.items():
            if url==primary or len(records)!=len(by_url[url]):continue
            redirects[url]=primary
            by_url[primary]=list({r['id']:r for r in by_url[primary]+records}.values())
            aliases.setdefault(primary,set()).update(a for r in records for a in [r['code'],*r['aliases']])
    def tile(match):
        card=match[0]
        url=unescape(re.search(r' href="([^"]+)"',card)[1])
        if url in redirects:return ''
        if url in aliases:
            old=re.search(r' data-aliases="([^"]*)"',card)
            names=aliases[url]|(set(unescape(old[1]).split('|')) if old else set())
            attribute=' data-aliases="'+ESC('|'.join(sorted(names)))+'"'
            card=card.replace(old[0],attribute,1) if old else card.replace(' href=',attribute+' href=',1)
        choices=by_url.get(url)
        if not choices:return card
        seen.update(r['id'] for r in choices)
        choices=[r for r in choices if not posted_speed(r)]
        if not choices:return ''
        choices=sorted(choices,key=lambda r:(r['sourceDrawing']!='official-standard',r['sizeStatus']=='Reference size unknown',bool(r.get('observationIds')),r['id']))
        main=choices[0]
        if url in aliases and main.get('preview'):
            card=re.sub(r'(<span class="simg"><img[^>]*? src=")[^"]+',lambda m:m[1]+ESC(BASE+main['preview']),card,count=1)
        card=card.replace('class="scard','data-dwg="1" class="scard',1)
        if 'class="simg"' not in card and main.get('preview'):
            art=f'<span class="simg"><img loading="lazy" decoding="async" src="{BASE}{ESC(main["preview"])}" alt=""></span>'
            card=card.replace('><span','>'+art+'<span',1)
        if not main.get('description') and main.get('historicalLegend') and isinstance(main['historicalLegend'],str):
            legend='<span class="sname">'+ESC(main['historicalLegend'])+'</span>'
            if 'class="sname"' in card:
                card=re.sub(r'<span class="sname">[^<]*</span>',lambda _:legend,card)
            else:
                card=card.replace('</a>',legend+'</a>')
        alt=''
        if len(choices)>1:
            alt=(f'<details class="sign-variants"><summary>{len(choices)-1} more variant'+('s' if len(choices)>2 else '')+'</summary>'
                 +''.join(checkbox(r,True) for r in choices[1:])+'</details>')
        return '<div class="sign-tile">'+card+'<div class="sign-tile-pick">'+checkbox(main)+alt+'</div></div>'+(speed_tiles() if url==BASE+'/signs/r2-1/' else '')
    content=re.sub(r'<a class="scard[^"]*"[^>]*>[\s\S]*?</a>',tile,content)
    missing={r['id'] for rs in by_url.values() for r in rs}-seen
    if missing:raise ValueError('Native drawings absent from sign chart: '+', '.join(sorted(missing)[:10]))
    return content
