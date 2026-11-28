# CAD blocks: how they are built

Signs, pavement markings and signals. Every published static DWG is AutoCAD 2000 (AC1015), opens
as block references (never loose geometry), and is read back by LibreDWG and LibreCAD libdxfrw
before it is published. Dynamic blocks are AutoCAD 2018 (AC1032), written by ODA File Converter.

## Tools (local builds)

- LibreDWG `dxf2dwg` / `dwg2dxf` and LibreCAD `libdxfrw` `dwg2dxf`, pinned in the dxf-to-dwg skill.
- `ezdxf`, `shapely`, `pymupdf`.
- ODA File Converter 27.10 (`dpkg -i` the .deb; headless with `xvfb-run -a`, needs `libopengl0`):
  DWG and DXF in any version, dynamic block objects kept.
- cadkit (`cargo install cadkit-cli`): reads MicroStation DGN v7 and v8 (`cadkit info`, `cadkit
  convert --dxf-version r2018`; a sheet's figures can sit in its second model, `--model 1` for SVG).

## Signs: `sign_cells.py`

```
python3 pipeline/sign_cells.py build --libredwg <dir> --libdxfrw <libdxfrw dwg2dxf>
```

- One block INSERT at 0,0, the lower-left corner of the 1.025 x 1.2 in LADOT legend cell, plus
  one MTEXT code (ROMANS, bottom center, 0.095 in, shrunk to fit 0.96 in).
- Faces are scaled to fit 0.92 x 0.86 in, centered at (0.5125, 0.745). Units: plotted inches.
- Output: `data/reference/sign-cells.zip`; publishing swaps these in by record id.

### Sign lettering: `reletter_signs.py`, `chart_faces.py`, `fhwa_alphabets.py`, `sign_spelling.py`

- Faces whose chart artwork matches (aspect, overlap, same words and numbers on a re-read) are rebuilt
  from the SHS chart; other legend lines are read (OCR consensus, at least two agreeing readings),
  spell-checked against the sign vocabulary (`pip install wordfreq`) and redrawn in FHWA Standard
  Alphabets (`data/reference/fhwa-alphabets/*.pfa`, from the FHWA Alphabets PDF). Symbols, unreadable
  lines and parts of words are left as drawn.
- `python3 pipeline/reletter_signs.py --dump new.json` writes nothing; review every changed face before
  `--write`. Readings can differ between runs: publish a reviewed run (`run_pack(..., use=...)`).
- After writing: `sign_cells.refresh(ids, ...)`, `center_sign_legends.refresh_previews(ids)`, and a new
  master patch (`MASTER_LETTERING` in `cad_block_package.py`, applied after `MASTER_FIX`).

## Pavement markings

```
python3 pipeline/marking_blocks.py --pdf <Caltrans 2026 Standard Plans PDF> --libredwg <dir>
python3 pipeline/plan_marking_blocks.py --dxf <plan drawing as DXF> --libredwg <dir>
python3 pipeline/striping_blocks.py --libredwg <dir>
python3 pipeline/marking_library.py --libredwg <dir>
```

- True size in feet. One INSERT per drawing on layer `P-PMARK`; block geometry is a SOLID hatch
  plus its outline on layer 0, ByBlock; green fields keep ACI 3.
- Base point: the middle of an arrow's tail; the bottom center of words and symbols; top center of
  yield line triangles. Arrows point +Y; words read bottom to top for the approaching driver.
- Caltrans figures are matched by the width, height and area printed with them (`SHEETS` in
  `marking_blocks.py`, in each sheet's reading order). Unmatched figures stay out and are listed
  in `data/reference/marking-blocks-report.json`.
- Plan-drawing blocks are flattened at the scale they are placed at in the plan, then checked
  against a stated size (`SHAPES` in `plan_marking_blocks.py`).
- Striping: every Caltrans detail in `striping_db.py` becomes `CT-DET-<n>`, one full repeat along
  +X from the start of the reference line, stripes in marking colors (yellow 2, white 7, black
  contrast 250), 4 in markers; broken lines also go to `SSS-CALTRANS-STRIPING.lin` (feet).
- `SSS-PMARK-LIBRARY.dwg` collects every block for the Blocks palette Libraries tab (striping one
  detail per row). The same script renders `SSS-PMARK-LIBRARY.webp` from the DWG as read back, on
  pavement gray (#2e2e2e, dark enough that ACI 7 draws white).
- Colored fields under a white marking (`FIELDS`, the ISA's blue ACI 5 square) are their own hatch,
  written first so the white marking draws over them.
- `marking_blocks.py` replaces only its own `CT-A24*` catalog rows; striping `CT-DET-*` and plan
  `PM-*` rows stay. After changing `striping_db.py`, also run `python3 pipeline/build_linetypes.py`
  (line type pages and data).

## From Caltrans DGN (cadkit)

```
cadkit dump --json 2026_a24f.dgn > a24f.json
python3 pipeline/crosswalk_blocks.py --json a24f.json --libredwg <dir>
cadkit dump --json 2026__es-01a.dgn > es01a.json     (and es-01b, es-01c)
python3 pipeline/signal_blocks.py --json es01a.json es01b.json es01c.json --libredwg <dir>
```

- Individual 2026 Standard Plan DGNs download from the Caltrans DGN page (links on the page, e.g.
  `/-/media/dot-media/programs/design/documents/2026-dgn-files/2026__es-01b.dgn`).
- `cadkit convert` to DXF writes only the first model; read every model from `cadkit dump --json`.
- A24F: the crosswalks are in model 1 at Caltrans's example dimensions (bars 1 to 2 ft, spacing 1 to
  5 ft vary by the notes). Longitudinal lines on the ladder and diagonal are drawn by their outer
  edge only and end in break-line cells: build the band from the outer edge to the bar ends. Label
  breaks leave gaps in bar edges: bridge collinear gaps under 0.8 ft before forming faces.
- ES-1A to ES-1C place the Caltrans cell library (CTCELLIB; N = new, E = existing) with each
  description on the cell's row. The sheet model is 50 units per plotted inch (border 32.5 x 21 in,
  text 0.14 in = 7 units). Symbols publish at plotted inches, base point at the cell origin, layer 0
  ByBlock, inserted at the drawing scale. Unnamed cells take their name from the description and the
  NEW / EXISTING column. Descriptions that are symbols or sit on another row are in `OVERRIDE`.

## Names and layers (every family)

- `CT-<sheet>-<item>`: official Caltrans geometry (A24A to A24F, DET, ES-1A to ES-1C).
- Plan-library blocks from LA plan sets: `PM-` pavement markings, `SG-` signals, `SN-` signs, `SV-` survey
  and site features, then a descriptive item; `-DYN` marks a dynamic block; sub-blocks `<prefix>-SUB-<item>`.
- File name = block name; one-block files insert at 0,0. Sign files keep their source block names (they
  match the master and the legend export); their paths are cleaned by `cad_block_package.clean_path`
  (lower-case kebab folders, no spaces or brackets, numbered when two clean to one).
- Insert layers: P-SIGN, P-PMARK, P-STRP, P-SIGNAL, E-SITE (labels on `<layer>-TEXT`). Inside blocks:
  0 ByBlock, green fields ACI 3, non-plotting geometry on Defpoints, states on E-, P-, R-, A- plus
  PMARK, SIGNAL, SIGN or SITE (P- layers white).
- Routes: signs/cad, markings/cad, signals/cad (signals, electrical, sign posts, survey symbols).

## Plan-library blocks: `plan_blocks.py`

```
python3 pipeline/plan_blocks.py --source westwood-ss=<S&S DWG> --source westwood-ts=<signal DWG> \
                                --source westwood-survey=<survey DWG> --libredwg <dir>
```

- ODA writes each source as DXF with every dynamic object as an ACAD_PROXY_OBJECT that keeps its bytes
  and owned handles. Each source is cut once to a trimmed library (the survey DXF is 106 MB), then each
  block and the source's library DWG are cut from that. Dynamic files are AutoCAD 2018 (the source
  version, where ODA restores proxies as native objects), static ones AutoCAD 2000.
- Add a block: one row in `SOURCES` (source block, standard name, label, page group). A layer the map
  does not know stops the build: add it to `STATE`, `TO_ZERO`, `NO_PLOT`, `GREEN` or `ALIASES`.
- Merging: identical definitions (geometry, nested blocks, dynamic bytes) publish once; a same-named
  block that differs keeps the first source's version (reported).
- One library per source drawing (SSS-STRIPING-PLAN-LIBRARY, SSS-SIGNAL-PLAN-LIBRARY,
  SSS-SURVEY-LIBRARY): dynamic data from two drawings cannot be merged outside AutoCAD.
- Stripped from every file: Civil 3D and Map dictionaries, page setups, material records, named views,
  ACDSDATA, unused styles, linetypes and application names, the survey's GEODATA (a block library has no
  project location) and empty nested blocks.
- Checks: proxy bytes per kept block unchanged, LibreDWG decodes native evaluation graphs and no proxies,
  model space holds block references only.
- `SSS-CAD-TOOLS.lsp` (`SSSDYNEXPORT`) stays for drawings handled in AutoCAD.
- Static blocks drawn in place at state plane coordinates (the left turn calming pieces) get their base
  point moved to the bottom center; polylines collapsed to one point are dropped. Dynamic blocks are
  never edited this way (their actions can point at vertices).
- Rebuilding re-encodes every file with a new timestamp: keep only new files and the libraries
  (`git checkout` the unchanged individual DWGs) so the repository does not grow for nothing.

## SSS CAD standard (every marking and signal block)

Rules live in `cad_standard.py`; `cad_normalize.py` applies them to every static block and is idempotent.
- Geometry on layer 0, color, linetype and lineweight ByLayer, so the insert layer (P-PMARK, P-SIGNAL,
  P-SIGN, E-SITE) sets how it plots. White is index 7 and prints black. Never exploded.
- Green field: FHWA IA-14 box centroid at luminance 21 = RGB 60, 144, 2, index 74 fallback. Red field:
  FHWA IA-22 box centroid at luminance 12 (IA-22 sets none) = RGB 157, 71, 58, index 13. True color needs
  AutoCAD 2004 or later, so marking and signal blocks are AutoCAD 2018 (ODA File Converter, read back by
  LibreDWG and libdxfrw). Sign blocks stay AutoCAD 2000.
- Field hatches have a frame on NOPLOT (plot off); their old plotting outlines move there.
- Placement: travel +Y; base on the reference line (limit line, crosswalk line, panel start) at the lane's
  left line. Words and legends centered in an 11 ft lane; STOP and WAIT HERE 8 ft before the line, KEEP
  CLEAR and BUS ONLY 8 ft past it (LADOT S-517.0, Westwood plans); arrows with the point 20 ft before the
  line (CA MUTCD 3B.20); bike symbols centered in a 5 ft bike lane; green panels and crossing dashes at the
  upstream corner on the bike lane line; sharrows 11 ft from the curb face (9E.09); crosswalks at the curb
  corner; striping details at the start of the reference line. Each card states its rule.
- Libraries (`block_libraries.py`, and the plan libraries in `plan_blocks.py`): one 24 x 36 in sheet per
  group (ARCH D, the Westwood TS-1 sheet), border, title line, one viewport at a standard scale.

Order after any block change: builder(s) → `cad_normalize.py` → `block_libraries.py` → `block_previews.py`
→ `cad_block_web.py` → `cad_audit.py`.

## Block cart and editor

- `cad_block_web.py` writes each block as AutoCAD 2000 DXF group codes (no handles) to
  `public/data/cad-block-entities/` with `index.json`; `test_block_cart.mjs` fails if a published block has none.
- `block-cart.js` (cards' Add buttons, side cart, layout options), `block-library-worker.js` (combined DXF
  from `public/cad-library/template.dxf.in`, sheet frames per group at the plan scale, LibreDWG wasm encode,
  ZIP with originals and SSS-ASSEMBLE.scr), `block-generators.js` (crosswalk, green bike crossing, green
  panel, limit line, pavement text; LADOT dots hatch at scale 10 as on the Westwood plans).
- Pavement text uses the FHWA elongated alphabet (`pavement_alphabet.py` → `public/js/pavement-alphabet.js`,
  Pavement Markings 10-1 to 10-7; the source U stops 4 grid squares short and its stems are extended).
  Letter pitch is the Caltrans A24D/A24E pitch (height / 4.8), base at the bottom center of the first line,
  lines 4 letter heights apart. The editor's Download DWG builds one block at 0,0 on P-PMARK.
- Library and single-block drawings are in feet (`$INSUNITS` 2).
- Browser-combined blocks are AutoCAD 2000 and static; the script reinserts the originals for grips.

## Dynamic families: `dynamic_families.py`, `dynamic_source.py` and `SSS-DYNBUILD.lsp` (v2)

How dynamic blocks are made and kept up:
- A family merges published variants that share one placement rule (all lane arrows, all words, each
  sign's directions, R2-1 speeds, Caltrans ES-1 new and existing pairs). Never mix rules: one base point
  serves every state. Every other static marking and signal block is a family of one (rotation only).
- Markings carry three conditions per variant (LADOT Drafting Standards for Striping and Signal Plans,
  2005, p. 10): PROPOSED filled, EXISTING outline only, REMOVE dashed outline.
- Array families (`ARRAYS`): crosswalks (Caltrans A24F basic, continental, ladder, triple four; bars start
  one gap from the curb) and green bike crossings (5 to 8 ft; 2 ft dash every 8 ft, first dash at the
  line). A length grip arrays the unit block and stretches the full-length lines; rotation turns all.
- `python3 pipeline/dynamic_families.py` writes the family list; `python3 pipeline/dynamic_source.py
  --libredwg <dir> --libdxfrw <path>` writes `SSS-DYNAMIC-SOURCE.dwg`: every state as a block, the family
  list as XRECORDs (SSS_DYNAMIC), a review sheet with every state and an empty slot per family. The
  same face published twice (shape and line style) is one state.
- In AutoCAD: open the source drawing, APPLOAD `SSS-DYNBUILD.lsp`, `SSSDYNTEST` then `SSSDYNBUILD`.
  Per family: states placed at 0,0 as nested inserts (lines exploded once), -BLOCK, -BEDIT, visibility,
  length + array/stretch, flip (arrows), rotation (includes the other grips), layers back to 0, BSAVE,
  then a copy at the review slot is checked through its dynamic properties: PASS or FAIL in
  `SSS-DYNBUILD.log`. Extra prompts a release adds take their default and are logged.
- Publish: the user sends back the saved drawing; cut each family out with `plan_blocks.cut` (keeps
  the dynamic data byte for byte) and publish; never re-author parameters outside AutoCAD.
 `composed_blocks.py`

`python3 pipeline/composed_blocks.py --libredwg <dir>` writes blocks the plans draw as loose geometry
or typed text:
- Green bike crossing dashes, one per lane width the plan uses (5, 6, 6.5, 7, 8 ft): 2 ft green dash
  with the bike lane line segment on each edge, repeated every 8 ft along the path (ARRAYPATH).
- Two-line legends (KEEP CLEAR, BUS ONLY, WAIT HERE) from the published Caltrans word blocks, first
  word nearest the driver, 4 x the letter height between lines (CA MUTCD 3B.20 low-speed minimum).
Run `marking_library.py` and `block_previews.py` after it.

## Page pictures: `block_previews.py`

`python3 pipeline/block_previews.py [--only CODE ...]` converts each published marking and signal DWG with
ODA (dynamic blocks show their saved state) and writes an SVG to `public/block-previews/<route>/`.
Markings: pavement gray, field colors, green fields behind symbols. Signals: black on white. Only the
block is drawn (no base point marker). The page build stops when a block has no picture.

`python3 pipeline/block_info.py` writes `data/reference/block-info.json` (base point in words, visibility
states from the DWG's dynamic-block data via LibreDWG `dwgread`, filled area per plotted color and state);
the card pop-up shows it. Run it with `block_previews.py`.

## Audit: `cad_audit.py`

`python3 pipeline/cad_audit.py --libredwg <dir>` reads every published DWG back and checks version, block
references only, file = block name, layers, units, header styles, zero-length lines, repeated vertices,
empty blocks and path names. Run it after any change; only `sign-blocks/master.dwg` (a source drawing)
may report findings.

## Lessons

- Header references must resolve. ezdxf names dimension style ISO-25 without defining it;
  `r2000_document()` sets Standard. A dangling style became a null handle in every DWG.
- Fail the build on any `dxf2dwg` warning.
- Caltrans marking sheets are rotated 270 degrees: visual up is +x of the unrotated page.
  Outline stroke width differs by sheet (0.48 or 0.72 pt); grids are 0.12 pt with a `<n> GRID` note.
- Roman numerals on those sheets use a symbol font: `Î` = I, `Ï` = V.
- Printed areas run 4 to 9 percent above the traced outline area; size must match within 0.06 ft.
- Several grid notes can sit near a figure; pick the one whose scale makes the figure agree with
  the dimensions printed beside it (the bike lane arrow is on a 6 in grid next to 1 ft grids).
- Fill needs two readings: nesting (holes cut only their parent, so a bike frame crossing a wheel
  joins) and even-odd (Type VIII's overlapping heads). Keep the one closer to the printed area,
  and hatch the resulting region, not the raw loops.
- Numerals print in pairs with one area; match digits by size in reading order and check the pair.
- Wind hatch rings by nesting depth (outer counterclockwise, holes clockwise) so counters and
  wheel rings stay open in every renderer.
- libdxfrw `dwg2dxf` does not overwrite an existing output file: read back into a fresh path, or a
  stale file passes for the new one.
- Plan-set blocks are often drawn at display scale and placed at a fraction of it (words at 1/3,
  bike symbols stretched). Bake the placed scale in.
- PyMuPDF reports a single straight stroke with a zero-area Rect, and Rect union drops empty
  rects. Build figure boxes from stroke points (LEFT is drawn only with straight lines).
- Dimension and extension lines share the grid stroke weight. A grid needs at least four lines
  each way; dashed centerlines are never grid (Type V's centerline gave a false scale).
- No grid (Type V), or a grid note that disagrees with every printed dimension both ways (ISA:
  drawn on a 4 1/2 in grid, noted 6 in): scale by the figure's own dimensions (text within 30 pt).
  With a grid drawn, pick the dimension that makes the grid a whole half inch; otherwise the
  largest that fits both sides. Then check against further printed dimensions or the area.
- A printed dimension or area can be wrong. Publish on independent evidence and say so in
  `SHEETS`: Type II (L) is 6'-9" (its halves equal Type II (B) and the through head; printed
  7'-0"), the bike symbol without rider is 5.2 ft2 (printed 7, the rider symbol's value), the ISA
  white area is 7.1 ft2 (printed 9; checked on four dimensions instead).
- Caltrans and LA-area CAD symbol libraries are MicroStation DGN v8 and .cel; cadkit reads them.
  ODA File Converter does not read DGN.

## Still open

- Every A24A to A24E figure is published (57 entries). Striping details 36 to 36B are the
  channelizing line only; gore layouts follow the plan.
- ES-1C pull boxes, vaults, cameras, message signs and the HAR antenna are drawn as loose elements,
  not cells, so they are not published yet. ES-1B conduit line types are line samples, left out.
- The full CTCELLIB.cel is behind a page this workspace cannot reach; the ES sheets carry its
  traffic electrical cells.
- `sign-blocks/master.dwg` keeps its source drawing's insert on layer 0 and a few zero-length lines;
  its header dimension style is fixed by `master-fix.patch.zst` (ODA audit, applied in hydrate).
- Left out of the Westwood drawings: RR and RxR (Caltrans RXR covers them), the signal plan's BUS
  word (24 ft tall, not a standard size), the bollard and trash can icons (elevations, not plan symbols),
  dimension arrows, AutoTURN paths, bus stop layouts tied to locations, match lines and note flags.
- Westwood survey and signal-plan symbols whose abbreviation was not certain (GP, WF, BK1, BSL, NEW ML,
  20ML R) are left out until named.
