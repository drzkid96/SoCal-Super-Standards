'use strict';
// Builds one combined AutoCAD library from the block cart: every selected block (and edited block) as a
// named block, laid out by group inside 24 x 36 sheet frames at the chosen plan scale, with labels and a
// title strip; encoded to DWG in the browser (LibreDWG). The ZIP also holds the original DWG of every
// block (dynamic grips intact) and SSS-ASSEMBLE.scr, which inserts those originals in AutoCAD at the
// same positions.
importScripts('../vendor/atlas/fflate.js', 'block-generators.js');

const root = new URL('../', self.location.href);
const hex = buf => Array.from(new Uint8Array(buf), b => b.toString(16).padStart(2, '0')).join('');
const n = v => (Math.round(v * 1e6) / 1e6).toString();
const tag = (...p) => p.map(String).join('\n') + '\n';
const cad = s => Array.from(String(s).replace(/[\r\n\t]/g, ' ')).map(ch => ch.charCodeAt(0) > 127 ? '?' : ch).join('');

async function get(url, sha) {
  const r = await fetch(url);
  if (!r.ok) throw Error('Could not load ' + url.pathname.split('/').pop() + '. Try again.');
  const buf = await r.arrayBuffer();
  if (sha && hex(await crypto.subtle.digest('SHA-256', buf)) !== sha) throw Error('A drawing changed. Refresh the page and try again.');
  return new Uint8Array(buf);
}

async function blocks(items, options) {
  const index = JSON.parse(new TextDecoder().decode(await get(new URL('data/cad-block-entities/index.json', root))));
  const out = [];
  let signIndex, signOptions;
  for (const item of items) {
    if (item.kind === 'sign') {        // a sign face at true size (drawn in inches, placed in a feet drawing)
      signIndex ??= JSON.parse(new TextDecoder().decode(await get(new URL('data/cad-sign-entities/index.json', root))));
      signOptions ??= new Map(JSON.parse(new TextDecoder().decode(await get(new URL('data/sign-block-options.json', root)))).map(r => [r.id, r]));
      const meta = signIndex.records?.[item.id] || signIndex[item.id], rec = signOptions.get(item.id);
      if (!meta || !rec) throw Error('A selected sign is no longer published. Remove it and try again.');
      const raw = await get(new URL('data/cad-sign-entities/' + encodeURIComponent(item.id) + '.dxf.gz', root), meta.sha256);
      const text = new TextDecoder('windows-1252').decode(fflate.gunzipSync(raw)).replace(/\n62\n7\n/g, '\n');
      out.push({name: 'SN-' + String(rec.code).toUpperCase().replace(/[^A-Z0-9]+/g, '-').replace(/^-|-$/g, ''), text, bounds: meta.bounds,
        layer: 'P-SIGN', group: 'Signs', label: rec.code, scale: 1 / 12, file: rec.file ? 'sign-blocks/' + rec.file : null});
      continue;
    }
    if (item.kind === 'custom') {
      const made = self.SSSBlockGenerators.make(item.gen, item.params);
      out.push({name: made.name, text: options.dots ? self.SSSBlockGenerators.dotsFor(made.text) : made.text, bounds: made.bounds, layer: 'P-PMARK', group: 'Edited blocks',
        label: made.name, scale: 1, file: null});
      continue;
    }
    const meta = index[item.code];
    if (!meta) throw Error(item.code + ' is no longer published. Remove it and try again.');
    const raw = await get(new URL('data/cad-block-entities/' + encodeURIComponent(item.code) + '.dxf.gz', root), meta.sha256);
    let text = new TextDecoder('windows-1252').decode(fflate.gunzipSync(raw));
    if (options.dots) text = self.SSSBlockGenerators.dotsFor(text);
    const scale = meta.units === 'in' ? options.scale : 1;    // plotted-inch symbols insert at the plan scale
    out.push({name: item.code, text, bounds: meta.bounds, layer: meta.layer, group: meta.group, label: item.code,
      scale, file: meta.file, dynamic: meta.dynamic});
  }
  return out;
}

function compose(template, list, options) {
  let next = 0x400;
  const handle = () => (next++).toString(16).toUpperCase();
  const records = [], defs = [], model = [];
  const ent = (type, layer, sub, ...a) => tag(0, type, 5, handle(), 330, '17', 100, 'AcDbEntity', 8, layer, 100, sub, ...a);
  const mtext = (value, x, y, h, layer, attach) => ent('MTEXT', layer, 'AcDbMText', 10, n(x), 20, n(y), 30, 0, 40, n(h), 41, 0, 71, attach, 72, 1, 1, cad(value), 7, 'ROMANS');
  const line = (x, y, ex, ey, layer) => ent('LINE', layer, 'AcDbLine', 10, n(x), 20, n(y), 30, 0, 11, n(ex), 21, n(ey), 31, 0);
  const seen = new Set();
  for (const b of list) {
    if (seen.has(b.name)) continue;
    seen.add(b.name);
    const bh = handle();
    records.push(tag(0, 'BLOCK_RECORD', 5, bh, 330, '9', 100, 'AcDbSymbolTableRecord', 100, 'AcDbBlockTableRecord', 2, cad(b.name), 340, '0'));
    defs.push(tag(0, 'BLOCK', 5, handle(), 330, bh, 100, 'AcDbEntity', 8, '0', 100, 'AcDbBlockBegin', 2, cad(b.name), 70, 0, 10, 0, 20, 0, 30, 0, 3, cad(b.name), 1, ''));
    const lines = b.text.replace(/\n$/, '').split('\n');
    for (let i = 0; i < lines.length; i += 2) {
      defs.push(tag(lines[i].trim(), lines[i + 1]));
      if (lines[i].trim() === '0') defs.push(tag(5, handle(), 330, bh));
    }
    defs.push(tag(0, 'ENDBLK', 5, handle(), 330, bh, 100, 'AcDbEntity', 8, '0', 100, 'AcDbBlockEnd'));
  }
  // Layout: groups in order, each in its own run of 36 x 24 in sheet frames at the plan scale.
  const k = options.scale, W = 36 * k, H = 24 * k, margin = 1 * k, titleH = 1.25 * k, gap = 0.6 * k, text = 0.1 * k;
  const groups = [];
  for (const b of list) {
    const g = options.groupBy === 'none' ? 'Blocks' : b.group;
    let entry = groups.find(x => x.name === g);
    if (!entry) groups.push(entry = {name: g, items: []});
    entry.items.push(b);
  }
  if (options.sort === 'code') for (const g of groups) g.items.sort((a, b) => a.label.localeCompare(b.label));
  const placed = [], sheetGroup = [];
  let sheet = 0;
  for (const g of groups) {
    let x = 0, y = 0, rowH = 0;
    const newSheet = () => { sheet++; sheetGroup[sheet] = g.name; x = margin; y = H - margin - 1.5 * k; rowH = 0; };
    newSheet();
    for (const b of g.items) {
      const [x0, y0, x1, y1] = b.bounds, w = (x1 - x0) * b.scale, h = (y1 - y0) * b.scale;
      const cellW = Math.max(w, (options.labels ? b.label.length * text * 0.75 : 0)) + gap;
      if (x > margin && x + cellW > W - margin) { x = margin; y -= rowH + gap; rowH = 0; }
      if (y - h - 2 * text < margin + titleH && !(x === margin && y === H - margin - 1.5 * k)) newSheet();
      const ox = (sheet - 1) * (W + 4 * k);
      const ix = ox + x - x0 * b.scale, iy = y - y1 * b.scale;
      model.push(ent('INSERT', b.layer, 'AcDbBlockReference', 2, cad(b.name), 10, n(ix), 20, n(iy), 30, 0, 41, n(b.scale), 42, n(b.scale), 43, n(b.scale)));
      if (options.labels) model.push(mtext(b.label, ox + x + w / 2, y - h - 0.6 * text, text, b.layer + '-TEXT', 2));
      placed.push({b, x: ix, y: iy});
      x += cellW;
      rowH = Math.max(rowH, h + 2 * text);
    }
  }
  if (options.sheets) for (let i = 1; i <= sheet; i++) {
    const ox = (i - 1) * (W + 4 * k);
    for (const [a1, b1, c1, d1] of [[0, 0, W, 0], [W, 0, W, H], [W, H, 0, H], [0, H, 0, 0], [0, titleH, W, titleH]])
      model.push(line(ox + a1, b1, ox + c1, d1, 'G-SHEET'));
    model.push(mtext((options.title || 'SSS BLOCK LIBRARY').toUpperCase() + '  ·  ' + String(sheetGroup[i]).toUpperCase(), ox + 0.3 * k, titleH / 2, 0.3 * k, 'G-SHEET-TEXT', 4));
    model.push(mtext('PLAN SCALE 1" = ' + k + "'  ·  SHEET " + i + ' OF ' + sheet + '  ·  SOCAL SUPER STANDARDS', ox + W - 0.3 * k, titleH / 2, 0.18 * k, 'G-SHEET-TEXT', 6));
  }
  const xmax = Math.max(1, sheet) * (W + 4 * k), ymax = H;
  const values = {RECORDS: records.join(''), BLOCKS: defs.join(''), ENTITIES: model.join(''), NEXT: handle(), COUNT: records.length + 2,
    EXTMINX: 0, EXTMINY: 0, LIMMINX: 0, LIMMINY: 0, EXTMAXX: xmax, EXTMAXY: ymax, LIMMAXX: xmax, LIMMAXY: ymax, ZERO: 0,
    CENTERX: xmax / 2, CENTERY: ymax / 2, VHEIGHT: Math.max(ymax, xmax / 1.4) * 1.05};
  const dxf = template.replace(/@([A-Z]+)@(\n?)/g, (_, key, nl) => {
    if (!Object.hasOwn(values, key)) throw Error('Unknown template field ' + key);
    return String(values[key]) + (['RECORDS', 'BLOCKS', 'ENTITIES'].includes(key) ? '' : nl);
  });
  return {dxf, placed};
}

function script(placed, options) {
  const out = ['; SSS-ASSEMBLE.scr  ·  inserts the original drawings (dynamic grips intact) at the library positions',
    '; Start a new drawing (feet) saved in this unzipped folder, then run SCRIPT and pick this file.', '-LAYER', 'M', 'P-PMARK', ''];
  for (const {b, x, y} of placed) {
    if (!b.file) continue;
    out.push('-LAYER', 'M', b.layer, '');
    out.push('-INSERT', '"individual\\' + b.file.replace(/\//g, '\\') + '"', n(x) + ',' + n(y), n(b.scale), '', '0');
  }
  out.push('ZOOM', 'E');
  return out.join('\r\n') + '\r\n';
}

async function build({items, options}) {
  const list = await blocks(items, options);
  if (!list.length) throw Error('The cart is empty.');
  const template = new TextDecoder().decode(await get(new URL('cad-library/template.dxf.in', root)));
  const {dxf, placed} = compose(template, list, options);
  const {encodeDwg} = await import('../cad-codec/codec.js');
  const dwg = await encodeDwg(dxf);
  const stem = ((options.title || 'SSS-BLOCK-LIBRARY').toUpperCase().replace(/[^A-Z0-9]+/g, '-').replace(/^-|-$/g, '')) || 'SSS-BLOCK-LIBRARY';
  const files = {[stem + '.dwg']: dwg, [stem + '.dxf']: new TextEncoder().encode(dxf), 'SSS-ASSEMBLE.scr': new TextEncoder().encode(script(placed, options))};
  let done = 0;
  const originals = list.filter(b => b.file);
  for (const b of originals) {
    files['individual/' + b.file] = await get(new URL('downloads/' + b.file.split('/').map(encodeURIComponent).join('/'), root));
    self.postMessage({progress: ++done, total: originals.length});
  }
  files['README.txt'] = new TextEncoder().encode(
    stem + '.dwg: every selected block in one drawing, one 24 x 36 sheet frame per group at 1" = ' + options.scale + "'.\r\n" +
    'Blocks combined here are static (AutoCAD 2000). For dynamic grips, start a drawing in this folder and run SCRIPT SSS-ASSEMBLE.scr:\r\n' +
    'it inserts the original drawings from individual\\ at the same positions.\r\n');
  return fflate.zipSync(files, {level: 4, mtime: new Date(1980, 0, 1)});
}

self.onmessage = async ({data}) => {
  try {
    const zip = await build(data);
    self.postMessage({buffer: zip.buffer}, [zip.buffer]);
  } catch (error) {
    self.postMessage({error: error.message || 'The library could not be built.'});
  }
};
