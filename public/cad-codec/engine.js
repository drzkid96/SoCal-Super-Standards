// SPDX-License-Identifier: GPL-3.0-or-later
import WASI from './vendor/wasi.js';
import {File, OpenFile, PreopenDirectory} from './vendor/fs_mem.js';

let compiledModule;

async function loadModule() {
  const response = await fetch(new URL('./libredwg.wasm.gz', import.meta.url));
  if (!response.ok) throw new Error('The drawing converter could not be loaded (' + response.status + ').');
  let bytes = new Uint8Array(await response.arrayBuffer());
  if (bytes[0] === 0x1f && bytes[1] === 0x8b) {
    const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));
    bytes = new Uint8Array(await new Response(stream).arrayBuffer());
  }
  return WebAssembly.compile(bytes);
}

export async function convertDrawing(bytes, encode) {
  compiledModule ??= loadModule().catch(error => {
    compiledModule = undefined;
    throw error;
  });
  const mod = await compiledModule;
  const dir = new PreopenDirectory('.', new Map([['input', new File(bytes, {readonly:true})]]));
  const wasi = new WASI([], [], [
    new OpenFile(new File([])), new OpenFile(new File([])), new OpenFile(new File([])), dir
  ]);
  const instance = await WebAssembly.instantiate(mod, {wasi_snapshot_preview1:wasi.wasiImport});
  wasi.initialize(instance);
  const status = instance.exports.convert(encode ? 1 : 0);
  const result = dir.dir.contents.get('output')?.data;
  if (status || !result?.length) throw new Error('Drawing conversion failed (LibreDWG code ' + status + ').');
  if (encode && String.fromCharCode(...result.subarray(0, 6)) !== 'AC1015') {
    throw new Error('The converter returned an unexpected DWG format.');
  }
  return result;
}
