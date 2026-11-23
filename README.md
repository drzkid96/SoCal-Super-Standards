# SoCal Super Standards

Searchable traffic engineering standards for Southern California: CA MUTCD 2026, federal MUTCD, LADOT, FHWA, ADA, and design guides. Every rule links back to its source page.

Live site: https://drzkid96.github.io/SoCal-Super-Standards/

## How it works
- `pipeline/` Python scripts turn the official PDFs into site content and structured data (each record keeps its source document and page).
- `src/content/docs/` generated and hand-written pages (Astro + Starlight).
- `data/` structured JSON (sections, figures, signs, markings) used by the site and, later, by AI search.
- `public/figs/` figure snips from public-domain / non-copyrighted sources only.
- Source PDFs are not committed; see the Sources page for official links.

## Build
```
npm install
python3 -I pipeline/extract_camutcd.py path/to/camutcd-2026-all.pdf .
npx astro build
```
Pushing to `main` deploys to GitHub Pages.

### Rebuilding the reference site

Install `pymupdf`, `pillow`, and `lxml` in the project Python environment. Run `python pipeline/manual_art.py` to prepare missing original chart pages, then run `npm ci` and `npm run build`. Astro prepares the editorial pages and tracked catalog in a staging directory. The published drawing catalog is sourced from `data/catalog/details.json`. Edit the source catalog and curated Markdown when updating drawings. Run `node pipeline/test_calculations.mjs` and `python3 pipeline/check_links.py` after building.

Pages deployment first runs `python pipeline/import_boe.py` (requires lxml) to traverse BOE’s official section tree and include nested provisions, tables, illustrations and document links. Run that command locally to refresh the BOE collection. Heavy civil sections are filtered by section title and ancestry. City-hosted attachments open at their original URLs.

The BOE section archive at `data/reference/boe-street-design.zip` is checked in so local builds include the same manual as the deployed site. The Pages build refreshes it against City sources. For FHWA Releases 5 and 6, run `python pipeline/render_fhwa_sheets.py .fhwa-releases` with PyMuPDF and Pillow before a local build to include the full-width sheet previews. Each sign entry also links to its official source. The rendering command verifies the three source PDFs against their reviewed checksums.

To refresh California provision metadata, supply the individual chapter PDFs and both official contents PDFs to `pipeline/index_pdf_sources.py`. The small provision number beside each paragraph opens the Caltrans source page.
