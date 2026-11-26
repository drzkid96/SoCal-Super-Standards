"""Extract the sign designation links from the pinned Caltrans specification index HTML."""
import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urljoin

DIR=Path(__file__).resolve().parent
CODE=re.compile(r'[A-Z]+\d[.\dA-Z-]*(?: (?:GRID|LT|RT))?(?:\([SU]\))?\s*(?:\(CA\))?(?: ABO| One Post| Two Posts)?',re.I)
FAMILY=re.compile(r'(?:PREP-Series \(CA\) \[[12]-line\]|RS-Series Grids \[MUTCD\]|PS-Series Grids \(CA\))',re.I)
class SpecificationLinks(HTMLParser):
    def __init__(self,url):
        super().__init__()
        self.base=url
        self.href=None
        self.parts=[]
        self.signs=[]
    def handle_starttag(self,tag,attrs):
        if tag=='a':
            self.href=dict(attrs).get('href')
            self.parts=[]
    def handle_data(self,data):
        if self.href:
            self.parts.append(data)
    def handle_endtag(self,tag):
        if tag!='a' or not self.href:
            return
        url=urljoin(self.base,self.href)
        label=' '.join(''.join(self.parts).split())
        self.href=None
        if not url.lower().endswith('.pdf'):
            return
        for code in re.sub(r'\s*\(PDF\)\s*$', '',label,flags=re.I).split(' & '):
            if CODE.fullmatch(code) or FAMILY.fullmatch(code):
                self.signs.append([code,url])

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('html',type=Path)
    args=p.parse_args()
    receipt=json.loads((DIR/'sources/retrieval.json').read_text())['caltransSpecifications']
    source=args.html.read_bytes()
    if hashlib.sha256(source).hexdigest()!=receipt['sha256']:
        raise ValueError('Specification index bytes do not match the pinned source')
    links=SpecificationLinks(receipt['url'])
    links.feed(source.decode('utf-8'))
    target=DIR/'sources/caltrans-specifications.json'
    target.write_text(json.dumps(links.signs,ensure_ascii=False,separators=(',',':'))+'\n')
    print(f'{len(links.signs)} exact specification entries')

if __name__=='__main__':
    main()
