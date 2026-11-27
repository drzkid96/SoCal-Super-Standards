// The PDF sign chart writer: vector faces, even-odd holes, table flow and page counts.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import zlib from 'node:zlib';

globalThis.self = globalThis;
self.location = {href: 'file:///site/js/sign-cart-worker.js'};
vm.runInThisContext(fs.readFileSync('node_modules/fflate/umd/index.js', 'utf8'));
for (const file of ['public/js/sign-legend-dxf.js', 'public/js/sign-legend-pdf.js']) vm.runInThisContext(fs.readFileSync(file, 'utf8'));

// A 30 x 30 square face with a square hole, an arc-edged loop and one line.
const square = (x0, y0, x1, y1) => ['92', '2', '72', '0', '73', '1', '93', '4', '10', x0, '20', y0, '10', x1, '20', y0, '10', x1, '20', y1, '10', x0, '20', y1, '97', '0'];
const hatch = ['0', 'HATCH', '8', '0', '10', '0', '20', '0', '30', '0', '2', 'SOLID', '70', '1', '71', '0', '91', '3',
  ...square(-15, -15, 15, 15), ...square(-5, -5, 5, 5),
  '92', '1', '93', '2', '72', '2', '10', '10', '20', '10', '40', '2', '50', '0', '51', '180', '73', '1', '72', '1', '10', '8', '20', '10', '11', '12', '21', '10', '97', '0',
  '75', '0', '76', '1', '98', '0'];
const text = [...hatch, '0', 'LINE', '8', '0', '10', '-15', '20', '-15', '30', '0', '11', '15', '21', '15', '31', '0'].join('\n');
const shapes = self.SSSLegendPDF.shapes(text);
assert.equal(shapes.fills.length, 1);
assert.equal(shapes.fills[0].length, 3, 'outer loop, hole and arc loop');
assert.ok(shapes.fills[0][2].length > 10, 'arc edges are sampled');
assert.equal(shapes.strokes.length, 1);

const records = Array.from({length: 31}, (_, i) => ({id: 's' + i, code: i === 3 ? 'R2-1(25) "BROADWAY ↑"' : 'W' + i, blockName: 'W' + i}));
const defs = new Map(records.map(r => [r.id, {entry: {bounds: [-15, -15, 15, 15]}, text}]));
const groups = [{label: 'SS-1', records: records.slice(0, 20)}, {label: 'SS-2', records: records.slice(20)}];
const pdf = self.SSSLegendPDF.create(records, groups, defs, {columns: 4, rows: 3, title: 'Test chart', page: 'letter-portrait'});
const raw = Buffer.from(pdf).toString('latin1');
assert.ok(raw.startsWith('%PDF-1.4') && raw.trimEnd().endsWith('%%EOF'));
const pages = Number(raw.match(/\/Type \/Pages \/Kids \[[^\]]*\] \/Count (\d+)/)[1]);
const tables = self.SSSLegendDXF.tables(groups, {columns: 4, rows: 3});
assert.deepEqual(tables.map(t => t.records.length), [12, 8, 11]);
assert.ok(pages >= 1 && pages <= tables.length);
const streams = [...raw.matchAll(/stream\n([\s\S]*?)\nendstream/g)].map(m => zlib.inflateSync(Buffer.from(m[1], 'latin1')).toString('latin1'));
const all = streams.join('\n');
assert.ok(all.includes(' f*'), 'hatches fill even-odd');
assert.ok(all.includes('(TEST CHART)'), 'custom title');
assert.ok(all.includes('BROADWAY ^'), 'non-Latin symbols map to plain text');
assert.ok(!/[^\x00-\xff]/.test(all));
const offset = Number(raw.match(/startxref\n(\d+)/)[1]);
assert.equal(raw.slice(offset, offset + 4), 'xref');
console.log(`PDF sign chart: ${pages} sheet(s), ${tables.length} tables, ${pdf.length} bytes`);
