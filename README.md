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
