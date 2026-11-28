---
title: CAD
description: Sign, pavement marking, signal and survey blocks as DWG, block editors, the block cart, sheet template, plot style, line types and AutoCAD routines.
tableOfContents: false
---

<link rel="stylesheet" href="/SoCal-Super-Standards/js/block-cart.css">
<script src="/SoCal-Super-Standards/js/pavement-alphabet.js" defer></script>
<script src="/SoCal-Super-Standards/js/block-generators.js" defer></script>
<script src="/SoCal-Super-Standards/js/block-cart.js" defer></script>

<nav class="cad-tabs" aria-label="CAD"><a href="/SoCal-Super-Standards/cad/" aria-current="page">CAD home</a><a href="/SoCal-Super-Standards/signs/cad/">Sign blocks</a><a href="/SoCal-Super-Standards/markings/cad/">Pavement marking blocks</a><a href="/SoCal-Super-Standards/signals/cad/">Signal and survey blocks</a><a href="/SoCal-Super-Standards/cad/#tools">Templates and tools</a></nav>

<p class="landing-lede">Every block is an AutoCAD 2000 DWG that opens in any release. Pick blocks from a library, add them to the cart, and download one drawing with all of them.</p>

<h2 id="libraries">Block libraries</h2>

<div class="cad-hub-grid">
<a class="cad-hub-card" href="/SoCal-Super-Standards/signs/cad/"><img src="/SoCal-Super-Standards/signs/R1-1.svg" alt="" loading="lazy"><strong>Sign blocks</strong><span>Legend-cell blocks in FHWA lettering, a legend builder and a PDF sign chart</span></a>
<a class="cad-hub-card" href="/SoCal-Super-Standards/markings/cad/"><img src="/SoCal-Super-Standards/block-previews/markings/cad/CT-A24C-BIKE-SYMBOL.svg" alt="" loading="lazy"><strong>Pavement marking blocks</strong><span>Caltrans arrows, words, symbols and crosswalks at true size, with proposed, existing and remove states</span></a>
<a class="cad-hub-card" href="/SoCal-Super-Standards/signals/cad/"><img src="/SoCal-Super-Standards/block-previews/signals/cad/SG-VEHICLE-HEAD-RYG-DYN.svg" alt="" loading="lazy"><strong>Signal and survey blocks</strong><span>Caltrans ES-1 electrical symbols, LA signal plan blocks and survey symbols</span></a>
<a class="cad-hub-card" href="/SoCal-Super-Standards/details/?agency=LADOT"><img src="/SoCal-Super-Standards/thumbs/figs/ladot/mpp-531/p0168.webp" alt="" loading="lazy"><strong>LADOT standard drawings</strong><span>Every MPP 531, MPP 521 and Red Book drawing as a DWG, one layout per sheet</span></a>
</div>

<h2 id="make">Make a block</h2>

<div class="cad-make">
<button type="button" data-block-editor="pavetext"><strong>Pavement text</strong><span>Any legend, up to 5 characters a line, in FHWA elongated letters</span></button>
<button type="button" data-block-editor="crosswalk"><strong>Crosswalks and bike crossings</strong><span>Crosswalks, green bike crossings, green panels and limit lines to your dimensions</span></button>
<a href="/SoCal-Super-Standards/signs/?cart=1"><strong>Sign legend</strong><span>A plan legend table from the signs you select, in sign-code order</span></a>
<button type="button" onclick="window.SSSBlockCart&&SSSBlockCart.open()"><strong>Block cart</strong><span>One drawing with every block you added, a sheet per group at your plan scale</span></button>
</div>

<h2 id="tools">Templates and tools</h2>

| File | Use |
|---|---|
| [SSS-ARCH-D-SHEET.dwt](/SoCal-Super-Standards/downloads/cad-tools/SSS-ARCH-D-SHEET.dwt) | 24 x 36 in sheet template (feet) with the SSS layers, NOPLOT and a title strip |
| [SSS-PLAN-BLACK.ctb](/SoCal-Super-Standards/downloads/cad-tools/SSS-PLAN-BLACK.ctb) | Plot style: every color plots black |
| [SSS-CALTRANS-STRIPING.lin](/SoCal-Super-Standards/downloads/cad-tools/SSS-CALTRANS-STRIPING.lin) | Line types for every broken Caltrans striping detail, in feet |
| [SSS-DYNBUILD.zip](/SoCal-Super-Standards/downloads/cad-tools/SSS-DYNBUILD.zip) | Builds every dynamic block family in AutoCAD from one drawing: visibility states (proposed, existing, remove), rotation at the base point, array grips for crosswalks and bike crossings |
| [SSS-CAD-TOOLS.lsp](/SoCal-Super-Standards/downloads/cad-tools/SSS-CAD-TOOLS.lsp) | SSSDYNEXPORT: copies a drawing's dynamic blocks into a clean library with a CSV of their properties |

<details class="cad-more"><summary>Use the libraries in AutoCAD</summary>

- **Blocks palette:** BLOCKSPALETTE, Libraries tab, then browse to a library DWG (or its folder). Drag a block in; it lands on its base point.
- **DesignCenter:** ADCENTER, open a library DWG, Blocks, drag or double-click. Right-click the drawing and choose Create Tool Palette for a palette of the whole library.
- **Tool palettes:** drag blocks from DesignCenter onto a palette. Set each tool's layer to the family layer (P-PMARK, P-SIGNAL, P-SIGN).
- **Sheets:** every library opens with one 24 x 36 layout per block group, ready to plot with SSS-PLAN-BLACK.ctb.

</details>

<details class="cad-more"><summary>Layers and colors</summary>

| Item | Standard |
|---|---|
| Block geometry | Layer 0, color, line type and lineweight ByLayer. Insert on the family layer; never explode |
| Family layers | P-PMARK, P-STRP, P-SIGN, P-SIGNAL (proposed), E- existing, R- remove, A- abandon |
| White markings | Index color 7, prints black |
| Green-colored pavement | RGB 60, 144, 2 (#3C9002), index 74 · FHWA Interim Approval IA-14, center of the daytime color box |
| Red-colored pavement | RGB 157, 71, 58 (#9D473A), index 13 · FHWA Interim Approval IA-22, center of the daytime color box |
| Non-plotting frames | NOPLOT (plot off) around every colored field hatch |

Sources: [FHWA IA-14](https://mutcd.fhwa.dot.gov/resources/interim_approval/ia14) · [FHWA IA-22](https://mutcd.fhwa.dot.gov/resources/interim_approval/ia22/index.htm) · [CA MUTCD Chapter 3H](/SoCal-Super-Standards/ca-mutcd/3h/)

</details>
