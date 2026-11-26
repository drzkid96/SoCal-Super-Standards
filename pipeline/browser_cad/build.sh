#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Rebuild the browser CAD worker from the pinned upstream source on x86-64 Linux.
set -euo pipefail
work="${1:-$(mktemp -d)}"
repo="$(cd "$(dirname "$0")/../.." && pwd)"
out="$repo/public/cad-codec"
work="$(mkdir -p "$work" && cd "$work" && pwd)"
cd "$work"
revision=cd50d4c0798d924d1756f6ba6f417b7d3c898b0f
fetch() {
  local url="$1" filename="$2" sha="$3"
  if ! test -f "$filename"; then curl --fail --location "$url" --output "$filename"; fi
  echo "$sha  $filename" | sha256sum --check --status
}
fetch "https://codeload.github.com/LibreDWG/libredwg/tar.gz/$revision" libredwg.tar.gz aaa56c9f2e77ffc0fde8408ab6931f4ae71e35f681e6b8d3277763f6b3e63c9e
fetch https://github.com/WebAssembly/wasi-sdk/releases/download/wasi-sdk-25/wasi-sdk-25.0-x86_64-linux.tar.gz wasi-sdk.tar.gz 52640dde13599bf127a95499e61d6d640256119456d1af8897ab6725bcf3d89c
fetch https://registry.npmjs.org/@bjorn3/browser_wasi_shim/-/browser_wasi_shim-0.4.2.tgz browser-wasi.tgz 9c0281520d0e99f027ec7c1c79b4036c0f8168ed9bf98aba19db4737a1333782
tar -xzf libredwg.tar.gz
tar -xzf wasi-sdk.tar.gz
mkdir -p shim
tar -xzf browser-wasi.tgz -C shim
sdk="$work/wasi-sdk-25.0-x86_64-linux"
src="$work/libredwg-$revision"
build="$work/build"
cmake -S "$src" -B "$build" -DCMAKE_TOOLCHAIN_FILE="$sdk/share/cmake/wasi-sdk.cmake" \
  -DCMAKE_BUILD_TYPE=MinSizeRel -DCMAKE_C_FLAGS='-Oz -w -ffunction-sections -fdata-sections -D_WASI_EMULATED_SIGNAL -D_WASI_EMULATED_MMAN' \
  -DCMAKE_EXE_LINKER_FLAGS='-lwasi-emulated-mman -lwasi-emulated-signal' -DHAVE_SYS_MMAN_H:INTERNAL=0 \
  -DENABLE_LTO=OFF -DBUILD_SHARED_LIBS=OFF -DLIBREDWG_LIBONLY=ON -DLIBREDWG_DISABLE_JSON=ON \
  -DDISABLE_WERROR=ON -DBUILD_TESTING=OFF
cmake --build "$build" --parallel "${JOBS:-4}"
"$sdk/bin/clang" -Oz -Wno-ignored-attributes -I"$build/src" -I"$src/include" -I"$src/src" \
  -c "$repo/pipeline/browser_cad/codec.c" -o "$work/bridge.o"
"$sdk/bin/clang" -mexec-model=reactor -Wl,--export=convert -Wl,--strip-all -Wl,--gc-sections \
  -Wl,-z,stack-size=4194304 "$work/bridge.o" "$build/libredwg.a" -lwasi-emulated-signal -lm -o "$work/libredwg.wasm"
mkdir -p "$out/vendor"
gzip -9nc "$work/libredwg.wasm" > "$out/libredwg.wasm.gz"
cp "$src/COPYING" "$out/LibreDWG-LICENSE.txt"
cp shim/package/dist/{wasi,fs_mem,debug,fd,wasi_defs}.js "$out/vendor/"
cp shim/package/LICENSE-MIT "$out/vendor/WASI-SHIM-LICENSE.txt"
