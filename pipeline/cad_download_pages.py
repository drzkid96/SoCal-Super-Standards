"""CAD download index and per-designation actions, generated from the released DWGs."""
from collections import defaultdict
from html import escape
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import quote
from zipfile import ZipFile

from cad_sign_catalog import LIBRARIES, designation_key, slug
from cad_block_package import PUBLIC as BLOCK_FILES, dump, hydrate
from current_catalog import BASE
import sign_cart_ui as cart

CATALOG = BASE+'/signs/cad/'
ASSETS = BASE+'/downloads/sign-blocks/'
CSS = f'<link rel="stylesheet" href="{BASE}/js/cad-downloads.css">'
ESC = lambda value: escape(str(value), quote=True)


def file_url(path):
    return ASSETS+quote(path)


def size(n):
    return f'{n / 1048576:.1f} MB' if n >= 1048576 else f'{max(1, round(n / 1024)):,} KB'


def source(rec):
    return rec.get('sourceLabel') or rec.get('sourceDrawing') or rec.get('source') or ''

def is_geometry_observation(observation):
    return not observation.get('relationship','').casefold().startswith('plan designation')


def dims(rec, units):
    return f'{rec["width"]:.4f}'.rstrip('0').rstrip('.')+' × '+f'{rec["height"]:.4f}'.rstrip('0').rstrip('.')+' '+('in' if units=='inches' else units)


def sort_key(value):
    return tuple((1,int(x)) if x.isdigit() else (0,x.casefold()) for x in re.split(r'(\d+)',value))


def download(file, label, n, save_as=''):
    attr='download'+(f'="{ESC(save_as)}"' if save_as else '')
    return f'<a class="cad-download" {attr} href="{ESC(file_url(file))}">{ESC(label)} <small>{size(n)}</small></a>'


def page(root, url):
    return root/(url.removeprefix(BASE+'/').split('#')[0].rstrip('/')+'.md')


def after_sign_face(body):
    start=re.search(r'<div class="(?:sdetail|mfig-grid)">',body)
    if not start:return body.find('\n---',3)+4
    depth=0
    for tag in re.finditer(r'</?div\b[^>]*>',body[start.start():]):
        depth+=-1 if tag[0].startswith('</') else 1
        if not depth:return start.start()+tag.end()
    raise ValueError('Unclosed sign face container')


def mark(rec):
    key=str(rec['id'])
    if re.fullmatch(r'[a-zA-Z0-9._~-]+',key):
        return 'block-'+key
    return 'block-'+slug(key)+'-'+hashlib.sha256(key.encode()).hexdigest()[:10]


def data_row(rec, units, standalone=False):
    title=ESC(rec['code'])
    if not standalone:
        title=f'<a href="{ESC(rec["signUrl"])}">{title}</a>'
    form=ESC(rec['blockName'])
    block=f' · inserted block <code>{form}</code>' if rec['blockName']!=rec['code'] else ''
    normalized=bool(re.search(r'unknown|unverified|normalized',rec.get('sizeStatus',''),re.I))
    dims_label=('Normalized block ' if normalized else '')+ESC(dims(rec,units))
    if rec.get('publishedSides'):
        nominal=' × '.join(f'{value:g}' for value in rec['publishedSides'])
        dims_label=f'{ESC(nominal)} in published sides · CAD bounds '+dims_label
    size_status=ESC(rec.get('sizeStatus') or '')
    labels=[dims_label,size_status,ESC(rec['matchStatus'])]
    geometry=rec.get('geometryStatus') or ''
    if geometry and geometry not in ('current issued artwork','documented source variant'):
        labels.append(ESC(geometry))
    if rec.get('sourceDrawing')!='official-standard' and source(rec):labels.append(ESC(source(rec)))
    labels=[label for label in labels if label]
    desc=ESC(rec.get('description',''))
    cites=[]
    if rec.get('sourceUrl'):
        cites.append('<a href="'+ESC(rec['sourceUrl'])+'">'+ESC(rec.get('referenceTitle') or 'Publisher reference')+'</a>')
    if rec.get('sizeTableUrl'):
        cites.append('<a href="'+ESC(rec['sizeTableUrl'])+'">Published size table</a>')
    if rec.get('currentArtworkUrl'):
        cites.append(f'<a href="{ESC(rec["currentArtworkUrl"])}">Current issued artwork</a>')
    context='<p class="cad-cite">'+' · '.join(cites)+'</p>' if cites else ''
    if standalone:
        # Drawing provenance and conversion logs belong to the CAD catalog.
        # The working sign page only needs the variant, actual usable size and download.
        context=''
        labels=[('Legend drawing' if normalized else dims_label)]
        if not normalized and size_status and rec.get('sizeStatus')!='published reference size':
            labels.append(size_status)
        if rec.get('historicalLegend') and rec.get('geometryStatus')!='Standardized posted speed':
            labels.append('Historical legend')
        if block:
            labels.append('CAD block <code>'+form+'</code>')
    body=(f'<div><strong class="cad-code">{title}</strong> <span class="cad-name">{desc}</span>'
          '<div class="cad-spec">'+' · '.join(labels)+'</div>'+context+'</div>')
    preview=''
    if rec.get('preview'):
        url=BASE+'/'+quote(rec['preview'].lstrip('/'))
        preview=(f'<a class="cad-preview" href="{ESC(url)}" aria-label="Open geometry preview for {ESC(rec["code"])}">'
                 f'<img loading="lazy" decoding="async" width="84" height="72" src="{ESC(url)}" alt=""></a>')
    return preview+body+'<div class="cad-file-action">'+checkbox_for_details(rec)+download(rec['file'],'DWG',rec['bytes'])+'</div>'

def checkbox_for_details(rec):
    return (f'<label class="sign-check sign-row-check"><input type="checkbox" data-cart-select="{ESC(rec["id"])}" '
            f'aria-label="Select {ESC(rec["code"])} · {ESC(cart.variant(rec))} · {ESC(cart.format_size(rec))}"><span>Select</span></label>')


def options(values):
    return ''.join(f'<option value="{ESC(v)}">{ESC(v)}</option>' for v in sorted(set(filter(None,values)),key=sort_key))


def build(root, lookup):
    release=hydrate()
    records=write_pages(root,lookup,release)
    (BLOCK_FILES/'manifest.json').write_bytes(dump(release))
    return records


def write_pages(root, lookup, release):
    plan_rows=json.loads(Path('public/data/plan-signs.json').read_text())
    official={designation_key(k):v for k,v in json.loads(Path('public/data/signs-index.json').read_text()).items()}
    plans={designation_key(alias):r for r in plan_rows for alias in r['aliases']}
    source_names={d['source']:d['name'] for s in plan_rows for d in s.get('drawings',[]) if d.get('name')}
    source_names['official-standard']='Issued sign reference'
    records=sorted(release['records'],key=lambda r:(sort_key(r['code']),r.get('sourceKind')!='current issued sign artwork',sort_key(r['id'])))
    blocks={r['id']:r for r in records}
    standards={}
    if release.get('standardReference'):
        with ZipFile(BLOCK_FILES/release['standardReference']['file']) as archive:
            index=json.loads(archive.read('sign-standards.json'))['records']
            standards={designation_key(row['code']):row for row in index.values()}
    units=release['units']
    by_url=defaultdict(list)
    by_code=defaultdict(list)
    for rec in records:
        key=designation_key(rec['code'])
        table=standards.get(key,{})
        bounds=table.get('nominalBounds') or []
        if (rec.get('sizeStatus')=='published reference size' and rec.get('sizeBasis')==table.get('sizeBasis')
                and len(bounds)==2 and all(abs(a-b)<0.01 for a,b in zip(bounds,(rec['width'],rec['height'])))):
            rec['sizeTableUrl']=table['source']['url']
            if table.get('sizeBasis') in ('diamond-side-lengths','triangle-sides'):
                rec['publishedSides']=table['size']
        plan=plans.get(key)
        src=rec.get('sourceDrawing')
        rec['sourceLabel']=source_names.get(src,src or '')
        observations=rec.get('observations',[])
        origins={src,*(obs.get('sourceDrawing') for obs in observations if is_geometry_observation(obs))}
        citations={obs['sourceDrawing'] for obs in observations if obs.get('sourceDrawing') and not is_geometry_observation(obs)}
        rec['sourceLabels']=sorted(source_names.get(k,k) for k in origins if k)
        rec['calloutSources']=sorted(source_names.get(k,k) for k in citations)
        std=official.get(key)
        url=plan['url'] if plan else std['url'] if std else CATALOG+'code-'+slug(key)+'/'
        current=blocks.get(rec.get('currentArtworkId'))
        if current:rec['currentArtworkUrl']=CATALOG+'#'+mark(current)
        if plan and plan.get('withdrawal'):kind='Withdrawn in California'
        elif rec.get('sourceKind')=='current issued sign artwork':kind='From issued artwork'
        elif rec.get('geometryStatus')=='historical issued artwork':kind='From historical issued artwork'
        elif rec.get('historicalLegend') and rec.get('geometryStatus')!='Standardized posted speed':kind='Documented source variant'
        elif std:kind='Source CAD · cataloged designation'
        elif plan and plan.get('modified'):kind='Modified designation'
        elif plan and plan.get('baseOfficial'):kind='Plan variant'
        else:kind='Source designation'
        rec['signUrl']=url
        rec['recordUrl']=CATALOG+'#'+mark(rec)
        rec['matchStatus']=kind
        if std and not rec.get('description'):
            title=std.get('descriptor','')
            rec['description']=title if kind=='From issued artwork' else ('Catalog reference · '+title if title else '')
        aliases=rec.get('aliases') or []
        rec['aliases']=list(dict.fromkeys([rec['code'],*aliases,*(plan['aliases'] if plan else [])]))
        by_url[url].append(rec);by_code[key].append(rec)
        alias_urls={plans[designation_key(alias)]['url'] for alias in aliases if designation_key(alias) in plans}
        rec['aliasSignUrls']=sorted(alias_urls-{url})
        for alternate in rec['aliasSignUrls']:by_url[alternate].append(rec)
        search_kind='CAD from issued artwork' if rec.get('sourceKind')=='current issued sign artwork' else 'CAD block'
        search_size='physical size unknown' if rec.get('sizeStatus')=='Reference size unknown' else dims(rec,units)
        if rec.get('publishedSides'):search_size=' × '.join(f'{n:g}' for n in rec['publishedSides'])+' in sides'
        label=' · '.join([rec['code'],search_kind,source(rec),search_size])
        for alias in rec['aliases']:
            results=lookup.setdefault('CAD '+alias.upper(),[])
            pair=[label,rec['recordUrl']]
            if pair not in results:results.append(pair)
        if not plan and not std:
            for alias in rec['aliases']:
                pair=[rec['code']+' · CAD source designation',url]
                if pair not in lookup.setdefault(alias.upper(),[]):lookup[alias.upper()].append(pair)
    from plan_face_blocks import publish
    supplemental=publish()
    for row in supplemental:by_url[row["signUrl"]].append(row)
    for url, variants in by_url.items():
        dest=page(root,url)
        if not dest.is_file():
            if not url.startswith(CATALOG) or '#' in url:raise ValueError('Missing sign destination '+url)
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_text('---\ntitle: '+json.dumps(variants[0]['code']+' · CAD sign block')+'\n---\n')
        md=dest.read_text()
        entries=['<div class="cad-local-row">'+data_row(r,units,True)+'</div>' for r in variants]
        parts=''.join(entries[:2])
        if len(entries)>2:
            parts+='<details class="cad-more-local"><summary>'+str(len(entries)-2)+' more block variants</summary>'+''.join(entries[2:])+'</details>'
        primary=' id="cad-files" data-primary-cad' if '#' not in url else ''
        summary=(f'<section class="cad-local"{primary} aria-label="CAD block downloads"><header><b>CAD sign block'
                 +('s' if len(variants)>1 else '')+'</b> · <a href="'+CATALOG+'">All CAD blocks</a></header>'+parts+'</section>')
        if '#' in url:
            anchor=url.split('#')[1]
            h=re.search(r'<h[23]\b[^>]*\bid="'+re.escape(anchor)+r'"[^>]*>.*?</h[23]>',md,re.S)
            if not h:raise ValueError('Missing variant anchor '+url)
            pos=h.end()
        else:
            pos=after_sign_face(md)
        if CSS not in md:summary=CSS+'\n'+cart.shell()+'\n'+summary
        dest.write_text(md[:pos]+'\n\n'+summary+'\n\n'+md[pos:])
    count=len(records)
    rows=[]
    frequent={k:i for i,k in enumerate(('R1-1','R1-2','R2-1','W11-2','R3-17','R10-15','W3-1'))}
    def browse_order(rec):
        issued=rec.get('sourceKind')=='current issued sign artwork'
        return (not issued,frequent.get(designation_key(rec['code']),len(frequent)) if issued else len(frequent),
                sort_key(rec['code']),bool(rec.get('observationIds')),sort_key(rec['id']))
    for r in sorted(records,key=browse_order):
        text=' '.join([r['code'],r['blockName'],*r['aliases'],str(r.get('description','')),str(source(r)),str(r.get('sizeStatus','')),str(r.get('geometryStatus',''))])
        attrs={'id':mark(r),'data-code':r['code'],'data-width':r['width'],'data-height':r['height'],'data-availability':'dwg','data-query':text,'data-keys':'|'.join(designation_key(a) for a in r['aliases']),
               'data-source':source(r),'data-sources':'|'.join(r['sourceLabels']),'data-status':r.get('sizeStatus') or '','data-kind':r['matchStatus']}
        if r.get('publishedSides'):
            attrs['data-published-width'],attrs['data-published-height']=r['publishedSides'][:2]
        props=' '.join(f'{k}="{ESC(v)}"' for k,v in attrs.items())
        rows.append(f'<li {props}>'+data_row(r,units)+'</li>')
    reference=release.get('standardReference')
    example_files=[('LADOT-SIGN-LEGEND-EXAMPLE.zip','Two-sign legend'),('LADOT-SIGN-LEGEND-THREE-TABLES.zip','Three-table legend'),
                   ('LADOT-SIGN-LEGEND-IMPORTED-SHEETS.zip','Legend from imported sheets')]
    examples=[f'<a download href="{BASE}/downloads/sign-legend-examples/{name}">{label} (ZIP)</a>' for name,label in example_files
              if (Path('public/downloads/sign-legend-examples')/name).is_file()]
    standard_link=(f'<p><a download href="{ESC(file_url(reference["file"]))}">California and federal sign size references (ZIP, {size(reference["bytes"])})</a></p>' if reference else '')
    legend_examples='<p id="legend-examples">'+' · '.join(examples)+'</p>' if examples else ''
    source_links=' · '.join(f'<a href="{BASE}/signs/cad/sources/{key}/">{ESC(name)}</a>' for key,(name,_) in LIBRARIES.items()
                           if (root/'signs/cad/sources'/(key+'.md')).exists())
    bulk=(download(release['master'],'Master DWG',release['masterBytes'],'SOCAL-SIGN-CATALOG.dwg')+' '+
          download(release['bundle'],'All individual drawings · ZIP',release['bundleBytes'],'SOCAL-SIGN-BLOCKS.zip'))
    controls=(f'<form class="cad-find" hidden><label>Search blocks<input type="search" name="q" placeholder="Sign code, description or size (24 × 24)"></label>'
              '<details class="cad-filter-options"><summary>Filters</summary><div class="cad-filter-grid">'
              f'<label>Drawing source<select name="source"><option value="">All sources</option>{options([label for r in records for label in r["sourceLabels"]])}</select></label>'
              f'<label>Size basis<select name="size"><option value="">All sizes</option>{options([r.get("sizeStatus") for r in records])}</select></label>'
              f'<label>Designation<select name="kind"><option value="">All designations</option>{options([r["matchStatus"] for r in records])}</select></label>'
              '</div></details><button type="reset" hidden>Clear</button></form>')
    about=f'{len(by_code):,} designations · {count:,} individual DWGs'
    if release.get('format'):about+=' · '+ESC(release['format'])
    usage=(f'Drawing units · {ESC(units)}. Insertion point · {ESC(release["basepoint"])}. '
           'Each individual drawing holds one sign block and its code as MTEXT, sized to the LADOT plan sign legend cell. '
           'The master contains the true-size named blocks for browsing and detail work. '
           'Published sizes identify the application cited in the record. Source dimensions come from the original drawing. '
           '“Reference size unknown” blocks use a normalized 1-inch face width. Verify the physical size with the issuing agency before using them at scale.')
    body=(CSS+f'\n\n<section class="cad-library" data-cad-downloads><div class="sign-library-actions"><a class="sign-chart-back" href="{BASE}/signs/">Browse sign chart</a>'+cart.shell()+f'</div><div class="cad-bulk">{bulk}</div>'
          f'{controls}<p class="cad-count" role="status" aria-live="polite">{about}</p>'
          '<ul class="cad-records">'+''.join(rows)+'</ul>'
          '<div class="cad-paging" hidden><button type="button" data-prev>Previous</button><button type="button" data-next>Next</button></div>'+
          f'<details class="cad-source-list"><summary>Sources, examples and size notes</summary>{legend_examples}<p>{usage}</p><p>{source_links}</p>{standard_link}</details></section>'
          f'\n\n<script src="{BASE}/js/cad-downloads.js" defer></script>\n'
          f'<link rel="stylesheet" href="{BASE}/js/block-cart.css">\n<script src="{BASE}/js/pavement-alphabet.js" defer></script>\n<script src="{BASE}/js/block-generators.js" defer></script>\n'
          f'<script src="{BASE}/js/block-cart.js" defer></script>\n')
    index=root/'signs/cad/index.md';index.parent.mkdir(parents=True,exist_ok=True)
    index.write_text('---\ntitle: CAD sign block downloads\ntableOfContents: false\n---\n\n'+body)
    chart=root/'signs/index.md'
    content=chart.read_text()
    content=cart.chart_tiles(content,by_url)
    content=content.replace('<option value="cad">Seen in CAD</option>','<option value="dwg">Native DWG available</option><option value="cad">Seen in CAD</option>')
    start=content.index('<div class="sfilter')
    actions=(f'<div class="sign-chart-actions">{cart.shell()}<a class="chart-import" href="{BASE}/signs/?import=1">Import PDF or screenshot</a>'
             '<label class="sign-check"><input type="checkbox" id="chart-dwg-only"><span>DWGs only</span></label>'
             '<details class="sign-bulk-options"><summary>All drawings</summary>'
             f'<div>{bulk}<a href="{CATALOG}">CAD files and sources</a>'
             +(f'<a href="{CATALOG}#legend-examples">Example legends</a>' if examples else '')+'</div></details></div>')
    chart.write_text((content[:start]+actions+'\n'+content[start:]).replace('title: Sign Library','title: Sign chart',1))
    cart.write_options(records+supplemental)
    for query in ('CAD sign downloads','CAD sign blocks','DWG sign library','sign block library','master sign drawing'):
        lookup.setdefault(query.upper(),[]).insert(0,['CAD sign block downloads',CATALOG])
    return records
