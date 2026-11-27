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
- Westwood survey and signal-plan symbols whose abbreviation was not certain (GP, WF, BK1, BSL, NEW ML,
  20ML R) are left out until named.
