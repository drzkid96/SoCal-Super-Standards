"""Typeset city equations and resolve numbered illustrations against the actual source artwork."""
from collections import defaultdict
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote, urlsplit
from lxml import etree, html

NUMBER = r'\d{3}[A-Z]?(?:\.\d+[A-Z]?)*(?:-\d+|\(\d+\))?'
FILENAME = re.compile(r'\bfig(?:ure)?\.?\s+(?:E\s*)?('+NUMBER+r')(?=\s|\.|$)', re.I)
REFERENCE = re.compile(r'\b(?:fig(?:ure)?s?\.?\s+(?:E\s*)?|E\s+)('+NUMBER+r')(?![\w-]|\.\d)', re.I)
EQUATION = re.compile(r'(?<!\\)\$([^$\n]+?)(?<!\\)\$')
EXCLUDED = {'a','math','annotation','script','code','pre','nav','figcaption','h1','h2','h3','h4','h5','h6','sup'}


def text_nodes(document):
    for node in document.xpath('.//text()'):
        parent = node.getparent()
        container = parent.getparent() if node.is_tail else parent
        if container is not None and not any(el.tag in EXCLUDED for el in (container, *container.iterancestors())):
            yield node


def substitute(node, matches):
    """Replace disjoint ranges in a text or tail node while retaining surrounding inline elements."""
    if not matches:
        return
    owner = node.getparent()
    parent = owner.getparent() if node.is_tail else owner
    index = parent.index(owner)+1 if node.is_tail else 0
    setattr(owner, 'tail' if node.is_tail else 'text', node[:matches[0][0]])
    for i, (_, end, element) in enumerate(matches):
        parent.insert(index+i, element)
        element.tail = node[end:matches[i+1][0] if i+1<len(matches) else None]


def math_matches(text):
    # Expense examples also contain dollar signs. A mathematical operation or a
    # TeX command distinguishes the city's actual delimited equations from prices.
    return [m for m in EQUATION.finditer(text) if '=' in m[1] or re.search(r'\\(?:frac|sqrt|times)\b',m[1])]


def typeset(documents):
    nodes = [(node, math_matches(node)) for doc in documents.values() for node in text_nodes(doc) if '$' in node]
    formulas = list(dict.fromkeys(m[1] for _,matches in nodes for m in matches))
    if not formulas:
        return
    output = subprocess.run(['node',str(Path(__file__).with_name('boe_math.mjs'))],input=json.dumps(formulas),
                            text=True,capture_output=True)
    if output.returncode:
        raise ValueError('Could not typeset BOE equations: '+output.stderr)
    markup = dict(zip(formulas,json.loads(output.stdout),strict=True))
    for node,matches in nodes:
        replacements = []
        for m in matches:
            equation = html.fragment_fromstring(markup[m[1]])
            equation.set('class','boe-equation')
            equation.set('data-source-tex',m[1])
            equation.find('.//annotation').set('data-pagefind-ignore','')
            replacements.append((m.start(),m.end(),equation))
        substitute(node,replacements)


def footnotes(doc):
    for label in doc.xpath('.//*[self::p or self::h2 or self::h3 or self::h4][normalize-space(.)="Footnotes"]'):
        following = label.xpath('following-sibling::*[normalize-space(.)][1]')
        if not following or following[0].tag!='ol':
            continue
        notes = {}
        number = int(following[0].get('start','1'))
        for item in following[0].findall('li'):
            number = int(item.get('value',number))
            anchor = item.get('id') or f'boe-note-{number}'
            item.set('id',anchor)
            notes[str(number)] = (anchor, ' '.join(item.text_content().split()))
            number += 1
        for sup in doc.xpath('.//sup[not(ancestor::math) and not(ancestor::ol[preceding-sibling::*[normalize-space(.)="Footnotes"]])]'):
            n = sup.text_content().strip()
            if n not in notes or len(sup) or sup.xpath('ancestor::a'):
                continue
            anchor,note = notes[n]
            sup.text = None
            link = etree.SubElement(sup,'a',href='#'+anchor,title=note)
            link.set('aria-label',f'Footnote {n}: {note}')
            link.text = n


BLOCKS = {'p','li','td','dd','blockquote'}


def thumbnails(wanted):
    """Show each cited drawing as a small linked preview under the paragraph that cites it."""
    for block,figures in wanted.items():
        strip = html.Element('div')
        strip.set('class','boe-fig-strip')
        for code,(target,(src,alt)) in figures.items():
            link = etree.SubElement(strip,'a',href=target)
            link.set('class','boe-fig-thumb')
            link.set('aria-label',f'Go to Figure E {code}')
            image = etree.SubElement(link,'img',src=src,alt=alt or f'Figure E {code}')
            image.set('loading','lazy')
            label = etree.SubElement(link,'span')
            label.text = f'Fig. E {code}'
        if block.tag in ('p','blockquote'):
            block.addnext(strip)
        else:
            block.append(strip)


def prepare(documents):
    # The Drupal export uses formatting-only spans even in the middle of figure numbers.
    sources = defaultdict(dict)
    thumbs = defaultdict(dict)
    for url,doc in documents.items():
        for span in doc.xpath('.//span[not(@*)]'):
            span.drop_tag()
        for image in doc.xpath('.//img[@src]'):
            src = image.get('src')
            if not src.startswith(('https://','http://')):
                continue
            name = unquote(urlsplit(src).path).rsplit('/',1)[-1].replace('_',' ')
            match = FILENAME.search(name)
            if not match:
                continue
            code = match[1].upper()
            figure = next(image.iterancestors('figure'),image)
            if url in sources[code]:
                continue
            anchor = figure.get('id') or 'boe-figure-'+re.sub(r'[^a-z0-9]+','-',code.lower()).strip('-')
            figure.set('id',anchor)
            sources[code][url] = url+'#'+anchor
            thumbs[code][url] = (src, ' '.join((image.get('alt') or '').split()))
            caption = figure.find('figcaption')
            if caption is not None:
                caption.text = f'Figure E {code} · '+(caption.text or '')
            if not image.xpath('ancestor::a'):
                link = html.Element('a',href=src)
                image.addprevious(link)
                link.tail,image.tail = image.tail,None
                link.append(image)
    typeset(documents)
    for url,doc in documents.items():
        footnotes(doc)
        if '/e-664-median-left-turn-lanes-' in url:
            source = doc.xpath('.//p[@class="boe-source"]/a/@href')[0]
            for eq in doc.xpath('.//span[@data-source-tex]'):
                if eq.get('data-source-tex').replace(' ','') != r'L=\frac{1ft.}{Left-turnvehiclesperhr.}':
                    continue
                note = html.Element('p')
                note.set('class','boe-reading-note')
                note.text = 'Source note. BOE prints the 80-second rule as this fraction. The units shown do not yield a length. '
                link = etree.SubElement(note,'a',href=source)
                link.text = 'Read the original section.'
                eq.getparent().addnext(note)
            for marker in doc.xpath('.//sup/a[@href="#boe-note-1"]'):
                if 'no longer in use' in marker.get('title',''):
                    marker.tail = ' '
                    notice = html.Element('a',href='#boe-note-1')
                    notice.set('class','boe-legacy-note')
                    notice.text = 'Legacy reference'
                    marker.getparent().addnext(notice)

        wanted = {}
        for node in list(text_nodes(doc)):
            matches = []
            for m in REFERENCE.finditer(node):
                code = m[1].upper()
                # Bare E numbers are often sections. Only interpret one as a
                # figure when it continues a list introduced as figures.
                if m[0][0].upper()=='E' and not re.search(r'\bfig(?:ure)?s?\.?\s+[^.;:!?]{0,120}$', re.sub(r'(?<=\d)\.(?=\d)','_',node[:m.start()]),re.I):
                    continue
                locations = sources.get(code,{})
                target = locations.get(url) or (next(iter(locations.values())) if len(locations)==1 else None)
                if target:
                    link = html.Element('a',href=target)
                    link.set('class','boe-figure-ref')
                    link.text=m[0]
                    matches.append((m.start(),m.end(),link))
                    cited = next(u for u in (url,*locations) if locations.get(u)==target)
                    owner = node.getparent().getparent() if node.is_tail else node.getparent()
                    block = next((el for el in (owner,*owner.iterancestors()) if el.tag in BLOCKS),None)
                    if block is not None:
                        wanted.setdefault(block,{}).setdefault(code,(target,thumbs[code][cited]))
            substitute(node,matches)
        thumbnails(wanted)
