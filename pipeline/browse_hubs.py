"""Generate compact directories and treatment comparisons from the reference catalogs."""
import json
import re
from html import escape
from pathlib import Path

from current_catalog import BASE
from regional_reader import slug


# Publication names in the catalog can be long. These link labels retain the issuer and edition.
GUIDE_GROUPS = (
    ('Standards and operator guides', '', 'Manuals, standard plans and transit operator publications.', (
        ('ca-mutcd', 'California MUTCD 2026', ''),
        ('mutcd', 'Federal MUTCD, 11th edition, Revision 1', ''),
        ('caltrans/standard-plans-2026', 'Caltrans standard plans', ''),
        ('transit', 'Transit agency design guides', ''),
    )),
    ('Federal design guidance', 'full-documents-on-this-site-complete-text--figures', 'Read the indexed chapters and original figures.', (
        ('fhwa/step-uncontrolled-crossings', 'FHWA STEP · Uncontrolled pedestrian crossings', 'fhwa/step-uncontrolled-crossings/p0023'),
        ('ada/curb-ramps', 'U.S. Access Board · Ramps and curb ramps', 'ada/curb-ramps/p0009'),
        ('fhwa/interchange-design-promptlist', 'FHWA Missouri Division · Interchange Design Promptlist', ''),
    )),
    ('California street design', 'governing-california-digests-with-official-figures', 'Design values, official figures and publisher links.', (
        ('bulletins/caltrans-hdm-ch1000', 'Caltrans HDM Chapter 1000 · Bicycle transportation', ''),
        ('bulletins/caltrans-dib-94', 'Caltrans DIB 94 · Complete streets', 'bulletins/dib-94/fig-5a-bike-selection'),
        ('bulletins/caltrans-dib-89-02', 'Caltrans DIB 89-02 · Separated bikeways', ''),
        ('bulletins/bikeway-design-comparison', 'California and AASHTO bikeway design comparison', ''),
    )),
    ('National design references', 'national-design-references-key-values--governing-ca-crosswalk--chapter-index', 'Chapter indexes, design excerpts and publisher links.', (
        ('guides/nacto-urban-bikeway', 'NACTO Urban Bikeway Design Guide, 3rd edition', 'nacto/protected-corner'),
        ('guides/nacto-urban-street', 'NACTO Urban Street Design Guide', 'nacto/bus-bulb'),
        ('guides/aashto-bike-guide', 'AASHTO Guide for the Development of Bicycle Facilities, 5th edition', ''),
        ('guides/cpbs-plts', 'CPBS Pedestrian Level of Traffic Stress', ''),
    )),
)


def frontmatter(path):
    source=path.read_text()
    head, _, body = source.partition('\n---\n')
    filters = re.findall(r'<span hidden data-pagefind-filter="[^"]+"></span>', body)
    return head+'\n---\n'+'\n'.join(filters)+'\n\n'


def directory_pages(root):
    guide=root/'guides/index.md'
    rows=[]
    for name, alias, description, items in GUIDE_GROUPS:
        links=[]
        for path,title,thumbnail in items:
            image=(f'<img src="{BASE}/thumbs/figs/{thumbnail}.webp" alt="" width="72" height="54" loading="lazy">' if thumbnail else '')
            links.append(f'<a href="{BASE}/{path}/">{image}<span>{escape(title)}</span></a>')
        anchor=f'<span id="{alias}"></span>' if alias else ''
        rows.append(f'<section>{anchor}<h2 id="{slug(name)}">{escape(name)}</h2><p>{description}</p><div class="guide-list">{"".join(links)}</div></section>')
    head=re.sub(r'^title:.*$', 'title: Design guides', frontmatter(guide), flags=re.M)
    guide.write_text(head+'<div class="guide-directory">'+''.join(rows)+'</div>\n')

    topic=root/'topics/index.md'
    groups=json.loads(Path('data/topics.json').read_text())
    cards=[]
    for group in groups:
        links=''.join(f'<a href="{BASE}/topics/{t["slug"]}/">{escape(t["name"])}</a>' for t in group['topics'])
        cards.append('<section><h2 id="'+slug(group['group'])+'">'+escape(group['group'])+'</h2><div>'+links+'</div></section>')
    topic.write_text(frontmatter(topic)+'<div class="design-topic-directory">'+''.join(cards)+'</div>\n')
    return groups


def treatments(application):
    sections=re.split(r'^### (.+)$',application,flags=re.M)
    chunks=[sections[0]]
    figures=[]
    def finish_figures():
        if figures:
            chunks.append('<div class="treatment-comparison">'+''.join(figures)+'</div>');figures.clear()
    for i in range(1,len(sections),2):
        heading,body=sections[i].strip(),sections[i+1].strip()
        anchor=f'treatment-{(i+1)//2}'
        figure=re.fullmatch(r'(<figure class="type-example">.*?</figure>)',body,re.S)
        if figure:
            # Primary heading remains addressable while the figure caption carries its visible title.
            text_slug=re.sub(r'[^\w\s-]','',heading.lower()).replace(' ','-')
            figures.append(f'<div id="{anchor}"><span id="{escape(text_slug)}"></span>{figure[1]}</div>')
        else:
            finish_figures()
            chunks.append(f'<span id="{anchor}"></span>\n\n### {heading}\n\n{body}')
    finish_figures()
    return '\n\n'.join(chunks)+'\n'
