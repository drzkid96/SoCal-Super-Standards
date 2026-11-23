"""Recover missing numbered California provisions from chapter PDFs and repair their section anchors.

Usage: python pipeline/recover_provisions.py CHAPTER_PDF_DIRECTORY
Preserves figure galleries, editorial notes and existing section cross-references.
"""
import html
import json
import re
import sys
from pathlib import Path

import pymupdf
from index_pdf_sources import horizontal_strokes, span_runs, SECTION, PN

BASE='/SoCal-Super-Standards'
DOCS=Path('src/content/docs/ca-mutcd')
INDEX=Path('data/ca-mutcd/sections.json')
LABELS={'Standard':'std','Guidance':'gui','Support':'sup','Option':'opt'}
def anchor(s):return re.sub(r'[().]','',s.lower())


def extract(pdf, chapter, wanted):
    results={}
    section=number=label=None
    for page in pdf:
        raw=page.get_text()
        if re.match(r'\s*(?:Figure|Table)\s+\d[A-Z]-\d',raw) or re.search(r'Chapter [^\n]+\((Figures|Tables)\)',raw):continue
        if not re.search(r'Section\s+\d[A-Z]\.\d|^\s*\d{2}[a-z]?\s*$',raw,re.M):continue
        strokes=horizontal_strokes(page)
        for block in page.get_text('rawdict',flags=pymupdf.TEXTFLAGS_RAWDICT & ~pymupdf.TEXT_PRESERVE_IMAGES)['blocks']:
            for line in block.get('lines',[]):
                if not 38<line['bbox'][1]<730:continue
                spans=[(s,''.join(c['c'] for c in s['chars'])) for s in line['spans']]
                while spans and not spans[0][1].strip():spans.pop(0)
                if not spans:continue
                first,text=spans[0]
                content=''.join(t for _,t in spans).strip()
                heading=SECTION.match(content)
                if heading and (first['size']>=11.5 or first['size']>=10.5 and first['flags']&16 and first['origin'][0]<40) and first['origin'][0]<100:
                    section=heading[1].replace(' ','')
                    number=label=None
                    if section in wanted:
                        m=re.search(r'Page\s+(\d+)\s*$',raw)
                        printed=int(m[1]) if m else chapter['first']+page.number
                        results.setdefault(section,{'title':content[heading.end():].strip(), 'page':printed,'paragraphs':{}})
                    continue
                if section not in wanted:continue
                if content.rstrip(':') in LABELS:
                    label=content.rstrip(':');number=None;continue
                if first['size']<9 and first['origin'][0]<95 and PN.fullmatch(text.strip()):
                    number=text.strip();spans=spans[1:]
                    if number in results[section]['paragraphs']:raise ValueError(f'Duplicate official number {section} {number}')
                    results[section]['paragraphs'][number]=[label,[]]
                if number and spans:
                    chunks=[]
                    for s,t in spans:
                        for deleted,run in span_runs(s,strokes):
                            t=html.escape(run,quote=False)
                            if deleted:t='<del data-pagefind-ignore>'+t+'</del>'
                            if s['color']==255:t='<span class="ca">'+t+'</span>'
                            chunks.append(t)
                    results[section]['paragraphs'][number][1].append(''.join(chunks))
    return results


def main():
    directory=Path(sys.argv[1])
    index=json.loads(INDEX.read_text())
    by_number={s['num']:s for s in index}
    chapters=json.loads(Path('data/ca-mutcd/chapters.json').read_text())
    for ch in chapters:
        code=ch['code'];p=DOCS/(code.lower()+'.md')
        ref=Path('data/reference/provisions')/(code.lower()+'.json')
        if not ref.exists():continue
        official=json.loads(ref.read_text());source=p.read_text()
        chunks=re.split(r'(?=\n<span id="[^"]+" class="anchor"></span>\n\n## )',source)
        prefix=chunks[0];sections={}
        for chunk in chunks[1:]:
            m=re.search(r'\n## (\d[A-Z]\.\d+(?:\(CA\))?)\b',chunk)
            if m:sections[re.search(r'\n## (\d[A-Z]\.\d+(?:\(CA\))?)',chunk)[1]]=chunk
        if not sections:continue
        wanted=set()
        for sec,para in official.items():
            if sec not in sections:wanted.add(sec)
        # A missing heading can leave the end of its preceding section incomplete.
        seq=list(official)
        for i,sec in enumerate(seq):
            if i and sec not in sections:wanted.add(seq[i-1])
        if not wanted:continue
        with pymupdf.open(directory/(code+'.pdf')) as pdf:recovered=extract(pdf,ch,wanted)
        for sec in wanted:
            r=recovered[sec];sid=anchor(sec);title=by_number.get(sec,{}).get('title') or r['title']
            if not title:raise ValueError(sec+' has no title')
            old=sections.get(sec,'')
            meta=re.search(r'<div class="secmeta">.*?</div>',old)
            # Preserve visual references tied to this section, including table annotations.
            remnants=re.sub(r'<div class="prov [^"]+">.*?\n</div>','',old,flags=re.S)
            extras=remnants.split(meta[0],1)[-1].strip() if meta else ''
            header=(f'\n<span id="{sid}" class="anchor"></span>\n\n## {sec} {title}\n\n'+
                    (meta[0] if meta else f'<div class="secmeta">Section {sec} · manual page {r["page"]}</div>')+'\n')
            body=[];group=None
            for n,(lbl,lines) in r['paragraphs'].items():
                if not lbl:raise ValueError(f'Missing official provision label: {sec} {n}')
                if group!=lbl:
                    if group:body.append('</div>')
                    body.append(f'<div class="prov {LABELS[lbl]}"><div class="prov-label">{lbl}</div>');group=lbl
                body.append(f'<p><span class="pn">{n}</span> '+re.sub(r'\s+',' ',' '.join(lines)).strip()+'</p>')
            if group:body.append('</div>')
            sections[sec]=header+'\n'+'\n'.join(body)+'\n'+extras+'\n'
            if sec not in by_number:
                item=dict(num=sec,title=title,page=r['page'],anchor=sid,ca_changes=any('class="ca"' in x or '<del' in x for x in body),chapter=code,url=f'{BASE}/ca-mutcd/{code.lower()}/#{sid}')
                index.append(item);by_number[sec]=item
        def order(sec):return int(re.search(r'\.(\d+)',sec)[1]),sec
        ordered=sorted(sections,key=lambda sec:(by_number.get(sec,{}).get('page',99999),order(sec)))
        toc='<details class="sec-toc" open><summary>Sections in this chapter</summary><ul>'+''.join(f'<li><a href="#{anchor(sec)}">{html.escape(sec+" "+by_number[sec]["title"])}</a></li>' for sec in ordered if sec in by_number)+'</ul></details>'
        prefix=re.sub(r'<details class="sec-toc".*?</details>',lambda _:toc,prefix,count=1,flags=re.S)
        p.write_text(prefix+''.join(sections[sec] for sec in ordered))
        print(code,len(wanted),'sections recovered')
    INDEX.write_text(json.dumps(index,indent=1,ensure_ascii=False)+'\n')

if __name__=='__main__':main()
