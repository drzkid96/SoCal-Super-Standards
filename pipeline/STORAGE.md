# Site storage

GitHub Pages serves at most 1 GB per site. The build keeps the site under it in two ways.

## Download store: `asset_store.py`

Large files that are only downloaded (bundles, master drawings, big libraries) live as assets of the
`download-store` GitHub Release (2 GB per file, no total limit). After the site is built and tested, the
workflow runs `python pipeline/asset_store.py --upload` on `main` (plan only on pull requests):

1. every file under `dist/downloads/` at or above `minBytes` (4 MB) moves to the store, unless listed in
   `keep`;
2. new or changed files upload (matched by SHA-256; a changed file uploads under a temporary name and
   replaces the old asset, so the link never breaks);
3. every link to the file in the built site is rewritten to the release URL, and the file leaves `dist/`;
4. `dist/data/asset-store.json` records site path, asset URL, bytes and SHA-256.

Rules are in `data/reference/asset-store.json`. `names` sets the file name users receive; asset names
must be unique across the store. Files that page scripts fetch (the sign cart reads individual DWGs)
must stay on Pages: list them in `keep` if they ever grow past the threshold. Source files stay in the
repository; only the published copy moves.

## Size budget: `site_budget.py`

Runs last. Prints the size of each top-level section and of the store to the job summary, warns above
900 MB and fails above 1 GB.

## Next lever

Inline images (figures, regional sheets) cannot move to a release: release files download instead of
display. If images outgrow the budget, publish them from a second Pages repository and point the
image base URL there.
