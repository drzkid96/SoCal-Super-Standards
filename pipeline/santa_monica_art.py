"""Publish readable original pages of Santa Monica's TTCP requirements and supplement."""
from html import escape
from pathlib import Path
from time import sleep
from urllib.request import Request, urlopen

BASE = '/SoCal-Super-Standards'
DIRECTORY = Path('public/figs/santa-monica/ttcp')
CACHE = Path('.santa-monica-art')
DOCUMENTS = {
    'requirements': ('Review and submission requirements', 'https://www.santamonica.gov/media/Document%20Library/Process%20Explainers/How%20to%20Submit%20a%20Temporary%20Traffic%20Control%20Plan/TTCP%20Review%20%26%20Submission%20Requirements.pdf', 14),
    'supplement': ('Traffic Control Plan Supplement', 'https://www.santamonica.gov/media/Document%20Library/Process%20Explainers/How%20to%20Obtain%20a%20Roadway%20Closure%20Permit/Traffic%20Control%20Plan%20Supplement%202022.pdf', 1),
}

def obtain(name, url, pages):
    import fitz

    cached = CACHE / (name + '.pdf')
    for attempt in range(3):
        try:
            if cached.exists():
                data = cached.read_bytes()
            else:
                with urlopen(Request(url, headers={'User-Agent': 'SoCal-Super-Standards'}), timeout=25) as reply:
                    data = reply.read()
            with fitz.open(stream=data, filetype='pdf') as document:
                if len(document) != pages:
                    raise ValueError(f'{name} has {len(document)} pages; expected {pages}.')
                if name == 'requirements' and '10/16/2026' not in document[0].get_text():
                    raise ValueError('Santa Monica changed the edition of its TTCP requirements.')
            cached.write_bytes(data)
            return data
        except (OSError, RuntimeError, ValueError):
            cached.unlink(missing_ok=True)
            if attempt == 2:
                raise
            sleep(2 ** attempt)

def render():
    import fitz
    from PIL import Image

    CACHE.mkdir(exist_ok=True)
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    for name, (_, url, pages) in DOCUMENTS.items():
        with fitz.open(stream=obtain(name, url, pages), filetype='pdf') as document:
            for index, page in enumerate(document, 1):
                scale = 1900 / page.rect.width
                pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), colorspace=fitz.csRGB, alpha=False)
                with Image.frombytes('RGB', (pix.width, pix.height), pix.samples) as image:
                    image.save(DIRECTORY / f'{name}-{index:02d}.webp', lossless=True, method=3)
        print(f'Rendered {pages} original Santa Monica {name} pages.')

def insert_previews(path):
    text = path.read_text()
    for name, (title, url, pages) in DOCUMENTS.items():
        marker = f'<!-- preview-ttcp-{name} -->'
        if marker not in text:
            continue
        sheets = [DIRECTORY / f'{name}-{i:02d}.webp' for i in range(1, pages + 1)]
        if not all(sheet.exists() for sheet in sheets):
            continue
        figures = []
        for i, sheet in enumerate(sheets, 1):
            src = BASE + '/' + sheet.relative_to('public').as_posix()
            label = f'{title}, page {i} of {pages}'
            figures.append(f'<figure class="mfig"><span id="sheet-ttcp-{name}-{i}"></span>'
                           f'<a href="{src}"><img loading="lazy" src="{src}" alt="{escape(label)}"></a>'
                           f'<figcaption>{escape(label)} · <a href="{url}#page={i}">Open city PDF</a></figcaption></figure>')
        layout = 'multi' if pages > 1 else 'single'
        html = '<div class="mfig-inline ' + layout + '">' + ''.join(figures) + '</div>'
        text = text.replace(marker, html)
    path.write_text(text)

if __name__ == '__main__':
    render()
