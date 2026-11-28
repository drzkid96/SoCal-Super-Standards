import re,json,html
from pathlib import Path
from sign_releases import prepare as prepare_fhwa_layouts
import shs_layouts
from boe_snapshot import CATALOG as BOE_CATALOG, restore as restore_boe
from current_catalog import prepare as prepare_current
from manual_art import illustration_url
from sign_import_runtime import hydrate as hydrate_sign_import
import shutil
hydrate_sign_import()
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
 provision_urls={s['num']:s['url'] for s in json.loads(Path('data',manual,'sections.json').read_text())}
 for path in (root/manual).glob('*.md'):
  src=path.read_text()
  def link(m):
   target=illustration_url(manual, m[1], m[2])
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
  table=re.search(r'## Sizes and layout dimensions.*?(<table class="dims">.*?</table>)',s,re.S)
  layout=shs_layouts.section(sign['slug'],sign['code'],table[1] if table else '',href) or layout
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
current_details = prepare_current(root, look, retired)
from ladot_drawings import prepare as prepare_ladot_drawings, sheet_label
ladot_sets=prepare_ladot_drawings(root,current_details,look)
from ladot_dwg import hydrate as hydrate_ladot_cad, link_pages as link_ladot_cad
hydrate_ladot_cad()
link_ladot_cad(root)
Path('public/data/lookup.json').write_text(json.dumps(look))
ladot_originals={
 'mpp-531':'https://ladot.lacity.gov/sites/default/files/2023-02/mpp_531_02212023.pdf',
 'mpp-521':'https://ladot.lacity.gov/sites/default/files/documents/traffic-signal-design-guidelines_0.pdf',
 'red-book':'https://ladot.lacity.gov/sites/default/files/2026-04/red-book-2026.pdf',
}
for path in root.rglob('*.md'):
 s=path.read_text()
 # A blank line ends the HTML block before Markdown starts the next sheet heading.
 if 'class="dfig"' in s:
  s=re.sub(r'(?<=\S)\n(?=### (?:Sheet \d+ of \d+|Page \d+\b))','\n\n',s)
 # Full sheet scans are readable in the article. Navigation thumbnails keep their smaller assets.
 s=re.sub(r'(<figure\b[^>]*class="mfig"[^>]*>.*?<img\b[^>]*?\bsrc="[^"]*)/thumbs/figs/',r'\1/figs/',s,flags=re.S)
 for key in ('bike','crosswalks'):s=s.replace('/markings/#'+key+'"','/markings/#cat-'+key+'"').replace('/markings/#'+key+')','/markings/#cat-'+key+')')
 if 'class="dwg-head"' in s:
  signs=re.search(r'<h2>Signs on this drawing</h2><div class="tsigns">.*?</div>',s,re.S)
  if signs:s=s[:signs.start()]+s[signs.end():]+'\n\n'+signs[0]+'\n'
  s=re.sub(r'(<figure class="dfig redraw">.*?</figure>)<details class="orig"><summary>.*?</summary>(<figure class="dfig">.*?</figure>)\s*</details>',r'\2',s,flags=re.S)
  figures=re.compile(r'<figure class="dfig"><a href="([^"]+)".*?</figcaption></figure>', re.S)
  drawer=re.search(r'<span class="dwg-num">([^<]+)</span><span class="dwg-src">([^<]+)</span>',s)
  count=sum(1 for _ in figures.finditer(s))
  if drawer and count:
   numbers=iter(range(1,count+1))
   def sheet_caption(match):
    i=next(numbers)
    scan=match[1]
    page=re.search(r'/p0*(\d+)\.',scan)
    direct=scan
    for manual,pdf in ladot_originals.items():
     if page and '/ladot/'+manual+'/' in scan:
      direct=pdf+'#page='+page[1]
      break
    role=sheet_label(manual,drawer[1],i,count).lower() if direct!=scan else f'sheet {i} of {count}'
    citation=f'{html.unescape(drawer[2])}. Drawing {html.unescape(drawer[1])}, {role}. '+(f'Page {page[1]}. ' if page else '')
    label='Agency PDF · p. '+page[1] if direct!=scan else 'Open source scan'
    actions=f'<span class="sheet-source-actions"><a href="{direct}">{label}</a><button type="button" class="agency-copy" data-url="{direct}" data-citation="{html.escape(citation)}">Copy sheet citation</button></span>'
    figure=match[0].replace('<figure class="dfig">',f'<figure id="sheet-{i}" class="dfig">',1)
    return figure.replace('</figcaption>',actions+'</figcaption>')
   s=figures.sub(sheet_caption,s)
   sheet=1;lines=[]
   for line in s.splitlines():
    f=re.search(r'id="sheet-(\d+)"',line)
    if f:sheet=int(f[1])
    line=re.sub(r'<li value="(\d+)">',lambda m:f'<li id="sheet-{sheet}-note-{m[1]}" value="{m[1]}">',line)
    lines.append(line)
   s='\n'.join(lines)+'\n'
 if s!=path.read_text():path.write_text(s)

from detail_reader import enrich
enrich(root, current_details, look)
from topic_reader import render as render_topic_pages
render_topic_pages(root,current_details)
from current_catalog import save, PUBLIC
from boe_navigation import build as build_boe_navigation
build_boe_navigation(root, look)
save(PUBLIC/"details.json",current_details)
Path("public/data/lookup.json").write_text(json.dumps(look))
from santa_monica_art import insert_previews
insert_previews(root/'santa-monica/standard-plans.md')
from regional_reader import build as build_regions
build_regions(root, look)
# Manual entry points follow the published chapter sequence in both editions.
for manual,other in [('mutcd','ca-mutcd'),('ca-mutcd','mutcd')]:
    path=root/manual/'index.md'
    front=path.read_text().split('---',2)[1]
    chapters=json.loads(Path('data',manual,'chapters.json').read_text())
    chapters=[c for c in chapters if (root/manual/(c['code'].lower()+'.md')).exists()]
    counterpart='California MUTCD' if other=='ca-mutcd' else 'Federal MUTCD'
    lines=['---',front.strip(),'---','',f'[Read Chapter 1A · General]({base}/{manual}/1a/) · [Open the {counterpart}]({base}/{other}/)','']
    part=None
    for chapter in chapters:
        code=chapter['code']
        if part!=code[0]:
            part=code[0]
            lines.extend(['',f'## Part {part}',''])
        lines.append(f'- [{code} · {chapter["title"]}]({base}/{manual}/{code.lower()}/)')
    path.write_text('\n'.join(lines)+'\n')
from cad_sign_catalog import build as build_cad_sign_catalog
build_cad_sign_catalog(root,look)
from cad_blocks.web_entities import SOURCE as cad_entity_source, source_parts as cad_entity_parts, hydrate as hydrate_cad_entities
if cad_entity_parts() or cad_entity_source.is_file():
    hydrate_cad_entities()
    from plan_face_blocks import publish_geometry
    publish_geometry()
from plan_examples import build as build_plan_examples
build_plan_examples(root, look)
save(PUBLIC/"lookup.json",look)
from workbench import build as build_workbench
build_workbench(root,look)
from atlas_site import prepare as prepare_atlas, finish as finish_atlas
atlas_profiles=prepare_atlas(root,look)
from printed_citations import repair as repair_printed_citations
repair_printed_citations(root, current_details)
save(PUBLIC/"details.json",current_details)
from reference_presentation import build as simplify_reference_pages
simplify_reference_pages(root)
from project_photos import place
place(root)
from publication_layout import build as build_publication_layout
build_publication_layout(root, ladot_sets)
from article_layout import build as prepare_editorial_articles
prepare_editorial_articles(root, current_details)
from design_blocks import build as build_design_blocks
build_design_blocks(root, look)
from dynamic_families import package as package_dynamic_families
package_dynamic_families()
from declutter import build as declutter
declutter(root)
from search_catalog import build as build_search_catalog
build_search_catalog(root, look, current_details)
finish_atlas(root,atlas_profiles)
