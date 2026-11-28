---
title: CAD resources
description: Block libraries, sheet template, plot style, line types, AutoCAD routines, layers and colors used by every SoCal Super Standards drawing.
tableOfContents: false
---

<link rel="stylesheet" href="/SoCal-Super-Standards/js/block-cart.css">
<script src="/SoCal-Super-Standards/js/block-generators.js" defer></script>
<script src="/SoCal-Super-Standards/js/block-cart.js" defer></script>

<div class="block-tools"><button type="button" onclick="window.SSSBlockCart&&SSSBlockCart.open()">Open block cart</button><button type="button" data-block-editor="crosswalk">Block editor</button></div>

<div class="block-grid cad-resource-grid">
<figure class="block-card"><a href="/SoCal-Super-Standards/signs/cad/"><img src="/SoCal-Super-Standards/signs/R1-1.svg" alt="" loading="lazy" /></a><figcaption><strong>Sign blocks</strong><span>Legend-cell blocks, legend builder, PDF sign chart</span><a href="/SoCal-Super-Standards/signs/cad/">Open</a></figcaption></figure>
<figure class="block-card"><a href="/SoCal-Super-Standards/markings/cad/"><img src="/SoCal-Super-Standards/block-previews/markings/cad/CT-A24C-BIKE-SYMBOL.svg" alt="" loading="lazy" /></a><figcaption><strong>Pavement markings</strong><span>True-size blocks with placement base points</span><a href="/SoCal-Super-Standards/markings/cad/">Open</a></figcaption></figure>
<figure class="block-card"><a href="/SoCal-Super-Standards/signals/cad/"><img src="/SoCal-Super-Standards/block-previews/signals/cad/SG-VEHICLE-HEAD-RYG-DYN.svg" alt="" loading="lazy" /></a><figcaption><strong>Signals and survey</strong><span>Caltrans ES-1 symbols, LA plan and survey blocks</span><a href="/SoCal-Super-Standards/signals/cad/">Open</a></figcaption></figure>
<figure class="block-card"><a href="/SoCal-Super-Standards/details/?agency=LADOT"><img src="/SoCal-Super-Standards/thumbs/figs/ladot/mpp-531/p0168.webp" alt="" loading="lazy" /></a><figcaption><strong>LADOT standard drawings</strong><span>Every MPP 531, MPP 521 and Red Book drawing as a DWG, one layout per sheet</span><a href="/SoCal-Super-Standards/details/?agency=LADOT">Open</a></figcaption></figure>
</div>

## Downloads

| File | Use |
|---|---|
| [SSS-ARCH-D-SHEET.dwt](/SoCal-Super-Standards/downloads/cad-tools/SSS-ARCH-D-SHEET.dwt) | 24 x 36 in sheet template (feet) with the SSS layers, NOPLOT and a title strip |
| [SSS-PLAN-BLACK.ctb](/SoCal-Super-Standards/downloads/cad-tools/SSS-PLAN-BLACK.ctb) | Plot style: every color plots black |
| [SSS-CALTRANS-STRIPING.lin](/SoCal-Super-Standards/downloads/cad-tools/SSS-CALTRANS-STRIPING.lin) | Line types for every broken Caltrans striping detail, in feet |
| [SSS-DYNBUILD.zip](/SoCal-Super-Standards/downloads/cad-tools/SSS-DYNBUILD.zip) | Builds the dynamic block families in AutoCAD: visibility states, rotation and flips at the base point |
| [SSS-CAD-TOOLS.lsp](/SoCal-Super-Standards/downloads/cad-tools/SSS-CAD-TOOLS.lsp) | SSSDYNEXPORT: copies a drawing's dynamic blocks into a clean library with a CSV of their properties |

## Block cart and editor

- **Add** on any marking or signal card puts the block in the cart; signs in your sign legend can ride along.
- **Download library** gives one DWG with every block, one 24 x 36 sheet frame per group at your plan scale, codes under the blocks, your title, plus each original drawing and SSS-ASSEMBLE.scr, which inserts the originals (dynamic grips intact) at the same spots.
- **Block editor** makes crosswalks, green bike crossings, green panels and limit lines to your dimensions, with green as a solid fill or the LADOT dots hatch.

## Use the libraries

- **Blocks palette:** BLOCKSPALETTE, Libraries tab, then browse to a library DWG (or its folder). Drag a block in; it lands on its base point.
- **DesignCenter:** ADCENTER, open a library DWG, Blocks, drag or double-click. Right-click the drawing and choose Create Tool Palette for a palette of the whole library.
- **Tool palettes:** drag blocks from DesignCenter onto a palette. Set each tool's layer to the family layer (P-PMARK, P-SIGNAL, P-SIGN).
- **Sheets:** every library opens with one 24 x 36 layout per block group, ready to plot with SSS-PLAN-BLACK.ctb.

## Layers and colors

| Item | Standard |
|---|---|
| Block geometry | Layer 0, color, line type and lineweight ByLayer. Insert on the family layer; never explode |
| Family layers | P-PMARK, P-STRP, P-SIGN, P-SIGNAL (proposed), E- existing, R- remove, A- abandon |
| White markings | Index color 7, prints black |
| Green-colored pavement | RGB 60, 144, 2 (#3C9002), index 74 · FHWA Interim Approval IA-14, center of the daytime color box |
| Red-colored pavement | RGB 157, 71, 58 (#9D473A), index 13 · FHWA Interim Approval IA-22, center of the daytime color box |
| Non-plotting frames | NOPLOT (plot off) around every colored field hatch |

Sources: [FHWA IA-14](https://mutcd.fhwa.dot.gov/resources/interim_approval/ia14) · [FHWA IA-22](https://mutcd.fhwa.dot.gov/resources/interim_approval/ia22/index.htm) · [CA MUTCD Chapter 3H](/SoCal-Super-Standards/ca-mutcd/3h/)
