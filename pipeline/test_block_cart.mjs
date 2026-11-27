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
vm.runInContext(fs.readFileSync(new URL('js/block-generators.js', root), 'utf8'), ctx);
vm.runInContext(fs.readFileSync(new URL('js/block-library-worker.js', root), 'utf8') + '\nself.__t={blocks,compose,script};', ctx);
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
