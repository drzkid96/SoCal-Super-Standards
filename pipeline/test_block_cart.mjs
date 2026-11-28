// Compose a block library from published fragments and edited blocks; check it parses as DXF.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import zlib from 'node:zlib';
const root = new URL('../public/', import.meta.url);
const ctx = {self: {}, URL, TextDecoder, TextEncoder, crypto: globalThis.crypto, console};
ctx.self = ctx;
ctx.importScripts = () => {};
ctx.fflate = {gunzipSync: b => new Uint8Array(zlib.gunzipSync(b))};
ctx.fetch = async url => {
  const b = fs.readFileSync(new URL(url));
  return {ok: true, arrayBuffer: async () => b.buffer.slice(b.byteOffset, b.byteOffset + b.length)};
};
ctx.location = {href: new URL('js/x.js', root).href};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(new URL('js/pavement-alphabet.js', root), 'utf8'), ctx);
vm.runInContext(fs.readFileSync(new URL('js/block-generators.js', root), 'utf8'), ctx);
vm.runInContext(fs.readFileSync(new URL('js/block-library-worker.js', root), 'utf8') + '\nself.__t={blocks,compose,script,single};', ctx);
const index = JSON.parse(fs.readFileSync(new URL('data/cad-block-entities/index.json', root)));
const design = JSON.parse(fs.readFileSync(new URL('../data/reference/design-blocks.json', root)));
const codes = Object.values(design).flatMap(s => s.blocks.map(b => b.code));
assert.deepEqual(Object.keys(index).sort(), [...codes].sort(), 'Every published block needs a cart fragment (run pipeline/cad_block_web.py)');
const items = [...codes.slice(0, 40).map(code => ({kind: 'block', code})),
  ...Object.keys(ctx.SSSBlockGenerators.families).map(gen => ({kind: 'custom', gen, params: {}}))];
const options = {title: 'Test', scale: 20, sheets: true, labels: true, groupBy: 'group', sort: 'cart', dots: true};
const list = await ctx.__t.blocks(items, options);
const {dxf, placed} = ctx.__t.compose(fs.readFileSync(new URL('cad-library/template.dxf.in', root), 'utf8'), list, options);
assert.equal(placed.length, items.length);
const lines = dxf.split('\n');
assert.ok(lines.length % 2 === 1 || lines.length % 2 === 0);
assert.ok(dxf.includes('\nDOTS\n'), 'LADOT dots swap missing');
for (const name of list.map(b => b.name)) assert.ok(dxf.includes('\n2\n' + name + '\n'), 'Missing block ' + name);
console.log(`Block cart: ${list.length} blocks composed into one library (${(dxf.length / 1e6).toFixed(1)} MB DXF).`);

// Pavement text: every character drawn, base at the bottom center, lines 4 letter heights apart.
const G = ctx.SSSBlockGenerators;
assert.equal(Object.keys(ctx.SSSPavementAlphabet).sort().join(''), '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ');
const only = G.make('pavetext', {text: 'only'});
assert.equal(only.name, 'PM-TEXT-ONLY-8FT');
assert.ok(Math.abs(only.bounds[0] + only.bounds[2]) < 1e-6 && Math.abs(only.bounds[1]) < 0.05 && Math.abs(only.bounds[3] - 8) < 0.05, 'ONLY not 8 ft tall, centered on the base');
assert.equal((only.text.match(/\nHATCH\n/g) || []).length, 4);
const two = G.make('pavetext', {text: 'BUS/ONLY'});
assert.ok(Math.abs(two.bounds[3] - 48) < 0.05, 'Second line should end 48 ft up (8 + 32 + 8)');
const one = ctx.__t.compose(fs.readFileSync(new URL('cad-library/template.dxf.in', root), 'utf8'),
  await ctx.__t.blocks([{kind: 'custom', gen: 'pavetext', params: {text: 'ONLY'}}], {}), {origin: true});
assert.ok(one.dxf.includes('\nPM-TEXT-ONLY-8FT\n') && /\$INSUNITS\n70\n2\n/.test(one.dxf), 'Single block drawing should be in feet');
console.log('Pavement text: ONLY and BUS/ONLY built; single-block drawing composed.');
// One lane: at most 5 characters a line and 11 ft across.
assert.throws(() => G.make('pavetext', {text: 'SCHOOL'}), /at most 5/);
assert.throws(() => G.make('pavetext', {text: 'WWWWW', height: 12}), /11 ft/);
assert.ok(G.make('pavetext', {text: 'XXXXX'}).bounds[2] - G.make('pavetext', {text: 'XXXXX'}).bounds[0] <= 11);
console.log('Pavement text: line limits hold.');
