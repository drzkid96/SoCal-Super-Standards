# SoCal Super Standards

Searchable traffic engineering standards for Southern California: CA MUTCD 2026, federal MUTCD, LADOT, FHWA, ADA, and design guides. Every rule links back to its source page.

Live site: https://drzkid96.github.io/SoCal-Super-Standards/

## How it works
- `pipeline/` Python scripts turn the official PDFs into site content and structured data (each record keeps its source document and page).
- `src/content/docs/` generated and hand-written pages (Astro + Starlight).
- `data/` structured JSON for sections, figures, signs, markings, and the site search catalog.
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

### Municipal standards map and source snapshots

Open the municipal standards map from the home page or a jurisdiction profile. Select one of 209 municipalities directly on the home page, or click a county in its static map. The geographic index also supports filtering by county. Each city has an official website and its directory source in the places index. The indexed standards collections identify their issuing agencies. An intersection search accepts two street names and an optional city, for example `Holly St & Arroyo Pkwy, Pasadena`. A single street name opens its intersecting streets. The map accepts latitude and longitude, works with local boundary data, and links the selected place, road ownership category, and stop operators to the standards catalog. Street and USGS aerial basemaps are optional network layers.

The first Pages build compiles the seven counties from public agency sources. Later builds restore the compiled databases from the Actions cache, keyed by the importer and pinned editions. Opening an article or the home page does not load the map engine or the geographic databases. The map loads regional boundaries and uses a worker to open SQLite partitions by county or bounding box. No server process or API key is required.

The stable discovery endpoint is `api/v2/index.json`. It lists the authority directory, design topics, publication hierarchy, and site SQLite index. The geographic manifest gives file names, sizes, counts, source editions, and partition bounds. Within the site index, join `agency_reference` and `agency_topic_reference` to `reference` by URL. The layer and SQL documentation is available at `map/data/`.

For a new geographic release install GDAL (including `ogr2ogr`), `pyshp==2.3.1`, and `shapely>=2,<3`. Run `python pipeline/atlas/compile.py` before `npm run build`. Set `SSS_ATLAS_CACHE` to reuse a local source directory. The compiler verifies the pinned Census county files and FHWA archive members, checks ArcGIS object IDs for complete responses, and checks SQLite integrity before packaging. Agency boundaries use state identifiers. Intersections use shared Census topology nodes, and the state highway and HPMS ownership inventories remain separate. Source editions can differ. The release is an index for design research and permitting coordination.

The City of Pasadena GIS supplement covers named in-city centerlines. It includes the city street classification and source record ID. Inspect `api/v2/road-context.json` for the edition, extent and GeoJSON file. Routine builds use the reviewed snapshot. Refresh that source with `python pipeline/atlas/supplement.py --refresh`.

The compiler also runs `pipeline/atlas/operator_feeds.py`. It pairs each multi-operator record with native GTFS trips and stop times, retaining the original feed group when the stop location or route set differs.
