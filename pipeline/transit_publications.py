"""Fetch only pinned, publicly issued transit guides from their publisher."""
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
import re
from pathlib import Path
from urllib.request import Request,urlopen
import hashlib,json,shutil,tempfile,time
import pymupdf

RTA_KEY = 'riverside-transit'
RTA_ARCHIVE = 'https://web.archive.org/web/20260721072147id_/'

def install_pdf(content, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(content)
            stream.flush()
            temporary.chmod(0o644)
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)


def prepare_riverside(source, target, expected, cached):
    """Resolve the pinned public edition and preserve its exact bytes for exports."""
    content = None
    missing = []
    for path in (cached, target):
        if path.is_file():
            local = path.read_bytes()
            if hashlib.sha256(local).hexdigest() == expected:
                content = local
                continue
        missing.append(path)
    if content is None:
        failures = []
        for url in (source, RTA_ARCHIVE + source):
            try:
                request = Request(url, headers={'User-Agent': 'SoCalStandards publication reader'})
                with urlopen(request, timeout=30) as stream:
                    downloaded = stream.read()
                if hashlib.sha256(downloaded).hexdigest() != expected:
                    raise ValueError('response did not match the August 2015 PDF')
                content = downloaded
                break
            except (OSError, ValueError, EOFError) as exc:
                failures.append(f'{url}: {exc}')
        if content is None:
            raise RuntimeError('Riverside guide could not be restored: ' + ' / '.join(failures))
    for path in missing:
        install_pdf(content, path)


def source_toc(key, doc):
    if key != RTA_KEY:
        return [(n, t, p) for n, t, p in doc.get_toc() if 1 <= p <= len(doc)]

    # The publisher uses chapter-relative page numbers in the printed contents.
    # Physical page 22 is numbered 4.6, before 4.3. Read every footer, never infer an offset.
    pages = {}
    chapter_names = {}
    for n in range(3, len(doc)):
        footer = re.search(r'^–\s*(.+?)\s+(\d+\.\d+)\s*–$', doc[n].get_text(), re.M)
        if not footer or footer[2] in pages:
            raise ValueError(f'Unrecognized Riverside page label at physical page {n + 1}')
        pages[footer[2]] = n + 1
        chapter_names[footer[2]] = footer[1]
    toc = [(1, 'Cover and contents', 1), (2, 'Contents', 2), (2, 'Figures and tables', 3)]
    for line in doc[1].get_text().splitlines():
        entry = re.fullmatch(r'(.+?)\s*\.{2,}\s*(\d+\.\d+)', line.strip())
        if not entry:
            continue
        heading, printed = entry.groups()
        level = 1 if heading.isupper() else 2
        toc.append((level, chapter_names[printed] if level == 1 else heading.rstrip(), pages[printed]))
    chapters = [page for level, _, page in toc if level == 1]
    if len(doc) != 52 or chapters != [1, 4, 7, 12, 20, 28, 30, 41, 42, 43, 44, 47] or len(toc) != 36:
        raise ValueError('Riverside printed contents differ from the verified 52-page edition')
    return toc

def prepare(editions):
    cache=Path('.transit-sources');cache.mkdir(exist_ok=True)
    dest=Path('public/transit-publications');dest.mkdir(exist_ok=True,parents=True)
    hashes=json.loads(Path('data/reference/transit-editions.json').read_text())
    rendering = Lock()
    def fetch(entry):
        key,name,county,title,url=entry
        if key not in hashes:return
        expected=hashes[key]
        raw=cache/(key+'.pdf');out=dest/(key+'.pdf')
        if key == RTA_KEY:
            prepare_riverside(url, out, expected, raw)
            return
        for attempt in range(2):
            try:
                if not raw.exists():
                    with urlopen(Request(url,headers={'User-Agent':'SoCalStandards reference publisher'}),timeout=30) as stream,raw.open('wb') as local:shutil.copyfileobj(stream,local)
                if hashlib.sha256(raw.read_bytes()).hexdigest()!=expected:raise ValueError('Publisher edition differs from indexed edition')
                stamp=cache/(key+'.stamp')
                if out.exists() and stamp.exists() and stamp.read_text()==expected:return
                with rendering, pymupdf.open(raw) as doc:
                    doc.rewrite_images(dpi_threshold=140,dpi_target=110,quality=68,bitonal=False)
                    new=out.with_suffix('.new');doc.save(new,garbage=4,deflate=True,use_objstms=1);new.replace(out)
                stamp.write_text(expected);return
            except Exception as error:
                raw.unlink(missing_ok=True)
                if attempt==1:
                    out.unlink(missing_ok=True)
                    print(f'Publisher PDF unavailable for {name}: {error}',flush=True)
                else:time.sleep(1)
    with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(fetch,editions))
