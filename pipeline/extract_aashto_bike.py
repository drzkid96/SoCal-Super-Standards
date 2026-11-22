"""Extract full text, tables, and direct figure images from a licensed AASHTO GBF-5 (2024) PDF.

Usage:
  python3 -I pipeline/extract_aashto_bike.py /path/to/GBF-5.pdf [--errata /path/to/GBF-5-Errata.pdf]

Outputs:
  src/content/docs/aashto/bike-guide/index.md
  src/content/docs/aashto/bike-guide/ch-01.md .. ch-16.md
  public/figs/aashto/gbf-5/fig-X-Y.webp   (direct cropped figure images from the PDF)
  data/docs/aashto__bike-guide.json       (page & figure metadata for details.json / topics)

After running, rebuild derived pages and verify accuracy:
  python3 -I pipeline/build_refcards.py
  python3 -I pipeline/build_topics.py
  python3 -I pipeline/build_index.py
  python3 -I pipeline/build_supersede.py
  python3 -I pipeline/build_previews.py
  python3 -I pipeline/check_bike_refs.py
"""
import argparse, html, json, os, re, sys
import pymupdf
from PIL import Image

BASE = "/SoCal-Super-Standards"
esc = lambda t: html.escape(str(t), quote=False)


def locate_chapter_pages(doc, gbf):
    """Map printed 'X-PP' page labels in GBF-5 to 1-based PDF page indices."""
    label_to_pdf = {}
    rx_hdr = re.compile(r"(?:^|\s)(\d{1,2}-\d{1,3})(?:\s|$)")
    for idx in range(len(doc)):
        pg = doc[idx]
        # Header/footer bands (top 12% and bottom 12%) hold printed 'X-PP' page numbers
        h = pg.rect.height
        w = pg.rect.width
        top = pg.get_text("text", clip=pymupdf.Rect(0, 0, w, h * 0.12))
        bot = pg.get_text("text", clip=pymupdf.Rect(0, h * 0.88, w, h))
        for m in rx_hdr.finditer(top + "\n" + bot):
            lbl = m.group(1)
            ch = int(lbl.split("-")[0])
            if 1 <= ch <= 16 and lbl not in label_to_pdf:
                label_to_pdf[lbl] = idx + 1
    return label_to_pdf


def crop_figure(pg, fig_num, out_path):
    """Locate 'Figure X-Y:' caption on the page and crop the figure + caption region directly from the PDF."""
    hits = pg.search_for(f"Figure {fig_num}:") or pg.search_for(f"Figure {fig_num}")
    r = pg.rect
    if hits:
        cap = hits[0]
        # Figure typically sits directly above its caption (or fills the column/page width)
        # Find nearest previous heading/caption or top margin to bound the graphic cleanly
        y0 = max(r.y0 + 48, cap.y0 - r.height * 0.52)
        y1 = min(r.y1 - 36, cap.y1 + 22)
        clip = pymupdf.Rect(r.x0 + 28, y0, r.x1 - 28, y1)
    else:
        clip = pymupdf.Rect(r.x0 + 28, r.y0 + 48, r.x1 - 28, r.y1 - 36)
    pix = pg.get_pixmap(dpi=180, clip=clip)
    im = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    im.save(out_path, "WEBP", quality=85)


def main():
    ap = argparse.ArgumentParser(description="Extract AASHTO GBF-5 chapters and direct figures.")
    ap.add_argument("pdf", help="Path to licensed AASHTO GBF-5 (2024) PDF")
    args = ap.parse_args()

    if not os.path.exists(args.pdf):
        sys.exit(f"PDF not found: {args.pdf}")

    gbf = json.load(open("data/aashto_gbf5.json"))
    doc = pymupdf.open(args.pdf)
    label_to_pdf = locate_chapter_pages(doc, gbf)
    print(f"Opened {args.pdf}: {len(doc)} pages, mapped {len(label_to_pdf)} printed chapter-page labels")

    errata_by_page = {}
    for er in gbf["errata"]:
        errata_by_page.setdefault(er["page"], []).append(er)

    figs_by_page = {}
    for fig in gbf["figures"]:
        figs_by_page.setdefault(fig["page"], []).append(fig)

    out_dir = "src/content/docs/aashto/bike-guide"
    fig_dir = "public/figs/aashto/gbf-5"
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(fig_dir, exist_ok=True)

    extracted_figs = 0
    ch_records = []

    for ch in gbf["chapters"]:
        cnum = ch["num"]
        c_labels = sorted(
            [(int(lbl.split("-")[1]), lbl, pno) for lbl, pno in label_to_pdf.items() if lbl.startswith(f"{cnum}-")],
            key=lambda x: x[0],
        )
        if not c_labels:
            print(f"  WARNING: no pages mapped for Chapter {cnum}")
            continue
        parts = []
        for _, lbl, pno in c_labels:
            pg = doc[pno - 1]
            parts.append(f'<span id="p{lbl}" class="anchor"></span>\n\n### Page {lbl}\n')
            if lbl in errata_by_page:
                for er in errata_by_page[lbl]:
                    parts.append(
                        f'<div class="note-box"><b>December 2024 Errata ({esc(er["section"])}):</b> '
                        f'{esc(er["corrected"])} (replaces: {esc(er["stale"])}).</div>\n'
                    )
            for fig in figs_by_page.get(lbl, []):
                fname = f'fig-{fig["num"].lower()}.webp'
                crop_figure(pg, fig["num"], f"{fig_dir}/{fname}")
                extracted_figs += 1
                parts.append(
                    f'<figure class="dfig"><a href="{BASE}/figs/aashto/gbf-5/{fname}">'
                    f'<img loading="lazy" src="{BASE}/figs/aashto/gbf-5/{fname}" alt="AASHTO GBF-5 Figure {esc(fig["num"])}"></a>'
                    f'<figcaption>Figure {esc(fig["num"])}: {esc(fig["title"])} (GBF-5 p. {esc(lbl)}).</figcaption></figure>\n'
                )
            # Clean body text (skip header/footer bands)
            r = pg.rect
            body = pg.get_text("text", clip=pymupdf.Rect(0, r.height * 0.08, r.width, r.height * 0.92)).strip()
            if body:
                paras = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
                parts.append('<div class="dtext">' + "\n".join(f"<p>{esc(p)}</p>" for p in paras) + "</div>\n")

        cslug = f"ch-{cnum:02d}"
        md = (
            f'---\ntitle: "AASHTO Bike Guide Ch. {cnum}: {ch["title"].replace(chr(34), chr(39))}"\n'
            f'description: "AASHTO Guide for the Development of Bicycle Facilities, 5th Edition (2024), Chapter {cnum}: {ch["title"].replace(chr(34), chr(39))}."\n'
            f'sidebar:\n  order: {cnum}\n---\n\n'
            f'<div class="srcbar">AASHTO Guide for the Development of Bicycle Facilities, 5th Edition (Dec 2024) &middot; Chapter {cnum} &middot; National guidance (in CA, HDM Ch. 1000, DIB 89-02 &amp; CA MUTCD 2026 govern)</div>\n\n'
            + "\n".join(parts)
        )
        open(f"{out_dir}/{cslug}.md", "w").write(md)
        ch_records.append({"chapter": cnum, "slug": cslug, "title": ch["title"], "pages": len(c_labels)})

    print(f"Extracted {len(ch_records)} chapters and {extracted_figs} direct figures to {fig_dir}/")


if __name__ == "__main__":
    main()
