import re,json,html
from pathlib import Path
from sign_releases import prepare as prepare_fhwa_layouts
from boe_snapshot import CATALOG as BOE_CATALOG, restore as restore_boe
import shutil
source = Path('src/content/docs')
root = Path('.standards/docs')
shutil.copytree(source, root, dirs_exist_ok=True)
for old in root.rglob('*'):
 if old.is_file() and not (source / old.relative_to(root)).exists():old.unlink()
boe_folder=root/'boe/street-design'
if not BOE_CATALOG.exists() or len(list(boe_folder.glob('*.md'))) <= 1:
 restore_boe(boe_folder)
ref=Path('data/reference')
base='/SoCal-Super-Standards'
urls=json.loads((ref/'ca-chapter-urls.json').read_text())
def revision_text(style, text):
 value=html.escape(text.strip())
 if style & 2:value='<span class="ca">'+value+'</span>'
 if style & 1:value='<del data-pagefind-ignore>'+value+'</del>'
 return value

for manual in ('ca-mutcd','mutcd'):
 items=json.loads((ref/(manual+'-items.json')).read_text())
 provision_urls={s['num']:s['url'] for s in json.loads(Path('data',manual,'sections.json').read_text())}
 chapters={c['code']:c['first'] for c in json.load(open('data/'+manual+'/chapters.json'))}
 anchors={}
 for path in (root/manual).glob('*.md'):
  src=path.read_text()
  def dest(m):
   kind,num=m.groups();kind=kind.rstrip('s');num=num.replace(' ','');owner=num.split('-')[0];pg=items.get(kind+' '+num)
   if pg and owner in chapters:
    if manual=='ca-mutcd' and owner in urls:return urls[owner]+'#page='+str(pg-chapters[owner]+1)
    image=f'/figs/{manual}/p{pg:04}.webp'
    if Path('public'+image).is_file():return base+image
    return 'https://mutcd.fhwa.dot.gov/pdfs/11th_Editionr1/mutcd11theditionr1.pdf#search='+kind+'%20'+num
   return None
  def link(m):
   target=dest(m)
   return '<a href="'+target+'">'+m[1]+' '+m[2]+'</a>' if target else m[1]+' '+m[2]
  src=re.sub(r'<a href="#fig-[^"]+">(Figures?|Tables?)\s+(\d[A-Z]-\d+(?:\s*\(CA\))?)</a>',link,src)
  if manual=='ca-mutcd' and path.stem.upper() in urls:
   code=path.stem.upper(); file=ref/'provisions'/(path.stem+'.json');records=json.loads(file.read_text()) if file.exists() else {}
   sect=''; lines=[]; seen={}
   for line in src.splitlines():
    sm=re.match(r'## (\d[A-Z]\.\d+(?:\(CA\))?)',line)
    if sm:sect=sm[1]
    m=re.fullmatch(r'<p><span class="pn">([^<]*)</span> (.*)</p>',line)
    if m:
     n,body=m.groups()
     seen[sect,n]=seen.get((sect,n),0)+1
     key=n if seen[sect,n]==1 else f'{n}-{seen[sect,n]}'
     entry=records.get(sect,{}).get(key)
     page=entry[0] if isinstance(entry,list) else entry
     url=urls[code]+('#page='+str(page) if page else '')
     if isinstance(entry,list):
      # Use whole PDF text runs so a strike cannot split an HTML attribute or mark an earlier repeated word.
      body=' '.join(revision_text(style,wording) for style,wording in entry[1] if wording.strip())
     if not page and ('class="ca"' in body or not records):
      body='Consult the official chapter for the marked-up provision.'
     line=f'<p id="{sect.lower().replace(".","").replace("(","").replace(")","")}-p{key}"><a class="pn" data-pagefind-ignore href="{url}" aria-label="Official source, paragraph {n}">{n}</a> {body}</p>'
    lines.append(line)
   src='\n'.join(lines)+'\n'
  def section_link(m):
   num=m[1]
   return f'<a href="{provision_urls[num]}">Section {num}</a>' if num in provision_urls else f'Section {num}'
  src=re.sub(r'<a href="#">Section (\d[A-Z]\.\d+(?:\(CA\))?)</a>',section_link,src)
  if src!=path.read_text():path.write_text(src)

def load(path):return json.loads(Path(path).read_text())

shs='https://mutcd.fhwa.dot.gov/kno-shs_2024-release-status/pdf/2024_SHS_Releases_1-4-Regulatory_Warning_TTC_School_Signs.pdf'
for sign in load('data/signs/signs.json'):
 path=root/'signs'/(sign['slug']+'.md')
 if not path.exists():continue
 s=path.read_text().replace(', row: .','.')
 if sign['source'].startswith('FHWA') and sign.get('pdf_page'):
  href=shs+'#page='+str(sign['pdf_page'])
  layout='## Official sign layout\n\n<a href="'+href+'">Open the FHWA dimensioned drawing and fabrication notes for '+html.escape(sign['code'])+'</a>\n\n'
  if '## Sizes and layout' in s:s=re.sub(r'## Sizes and layout.*?(?=\n## |\n<!--|\Z)',lambda _:layout,s,flags=re.S)
  else:s=s.replace('## Governing sections',layout+'## Governing sections',1)
 path.write_text(s)

retired=load('data/ca_deleted_signs.json')
look=load('data/catalog/lookup.json')
prepare_fhwa_layouts(root,look)
look.setdefault('6B.08',[]).insert(0,['CA MUTCD 6B.08 Tapers',base+'/ca-mutcd/6b/#6b08'])
for key, entries in list(look.items()):
 look[key]=[pair for pair in entries if not re.search(r'/line-types/#detail-option [12]$',pair[1])]
 if not look[key]:del look[key]
boe_catalog=Path('public/data/boe-sections.json')
if boe_catalog.exists():
 for section in load(boe_catalog):
  code=re.match(r'^E[ -]*(\d+(?:\.\d+)*)\b',section['title'],re.I)
  if code:
   keys = ['E'+code[1]]
   group = re.match(r'^E\s*(\d{3})[-–](\d{3})\b', section['title'])
   if group and 0 < int(group[2])-int(group[1]) <= 10:
    keys = ['E'+str(n) for n in range(int(group[1]),int(group[2])+1)]
   for key in keys:look.setdefault(key,[]).append(['LA BOE '+section['title'], section['url']])
out=['---','title: California retired sign codes','---','','Caltrans · '+retired['date']+' · [Official deletion notice]('+retired['source']+')','']
for code,name in retired['codes'].items():
 anchor=re.sub('[^a-z0-9]','',code.lower())
 target=base+'/signs/retired/#'+anchor
 out.append(f'<p id="{anchor}"><b>{html.escape(code)}</b> · {html.escape(name)} · Deleted by Caltrans on {retired["date"]}. <a href="{retired["source"]}">Official notice</a></p>')
 look.setdefault(code.upper().replace(' ',''),[]).insert(0,[f'{code} · {name} · Caltrans deleted {retired["date"]}',target])
(root/'signs/retired.md').write_text('\n'.join(out))
Path('public/data/lookup.json').write_text(json.dumps(look))
Path('public/data/retired.json').write_text(json.dumps(retired))
shutil.copyfile('data/catalog/details.json','public/data/details.json')
for path in root.rglob('*.md'):
 s=path.read_text()
 for key in ('bike','crosswalks'):s=s.replace('/markings/#'+key+'"','/markings/#cat-'+key+'"').replace('/markings/#'+key+')','/markings/#cat-'+key+')')
 if 'class="dwg-head"' in s:
  signs=re.search(r'<h2>Signs on this drawing</h2><div class="tsigns">.*?</div>',s,re.S)
  if signs:s=s[:signs.start()]+s[signs.end():]+'\n\n'+signs[0]+'\n'
  s=re.sub(r'(<figure class="dfig redraw">.*?</figure>)<details class="orig"><summary>.*?</summary>(<figure class="dfig">.*?</figure>)\s*</details>',r'\2<details><summary>Redrawn reference diagram</summary>\1</details>',s,flags=re.S)
  scans=re.findall(r'<figure class="dfig"><a href="([^"]+)"',s)
  drawer=re.search(r'<span class="dwg-num">([^<]+)</span><span class="dwg-src">([^<]+)</span>',s)
  if drawer and scans:
   tools=[]
   for i,scan in enumerate(scans,1):
    page=re.search(r'/p0*(\d+)\.',scan)
    direct=scan
    if '/ladot/mpp-531/' in scan and page:direct='https://ladot.lacity.gov/sites/default/files/2023-02/mpp_531_02212023.pdf#page='+page[1]
    citation=f'{html.unescape(drawer[2])}. Drawing {html.unescape(drawer[1])}, sheet {i} of {len(scans)}. '+(f'Page {page[1]}. ' if page else '')
    tools.append(f'<div><a href="#sheet-{i}">Sheet {i}</a> · <a href="{direct}">Open {"official PDF" if direct!=scan else "source scan"}</a> · <button type="button" class="agency-copy" data-url="{direct}" data-citation="{html.escape(citation)}">Copy agency citation</button></div>')
    s=s.replace(f'<figure class="dfig"><a href="{scan}"',f'<figure id="sheet-{i}" class="dfig"><a href="{scan}"',1)
   s=s.replace('<div class="dwg-summary">','<nav aria-label="Drawing sheets">' + ''.join(tools)+'</nav>\n\n<div class="dwg-summary">',1) if '<div class="dwg-summary">' in s else s.replace('## Sheet','\n<nav aria-label="Drawing sheets">' + ''.join(tools)+'</nav>\n\n## Sheet',1)
   sheet=1;lines=[]
   for line in s.splitlines():
    f=re.search(r'id="sheet-(\d+)"',line)
    if f:sheet=int(f[1])
    line=re.sub(r'<li value="(\d+)">',lambda m:f'<li id="sheet-{sheet}-note-{m[1]}" value="{m[1]}">',line)
    lines.append(line)
   s='\n'.join(lines)+'\n'
 if s!=path.read_text():path.write_text(s)
