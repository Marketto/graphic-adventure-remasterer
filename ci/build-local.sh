#!/bin/bash
# Local build of the remastered ScummVM fork (Linux; Web too if emsdk can be downloaded).
# Usage: ENGINE=<scummvm engine id> build-local.sh <scummvm fork folder> [web]
set -euo pipefail
SRC=${1:?ScummVM fork folder}
ENGINE=${ENGINE:?set ENGINE to the ScummVM engine id of the game}
cd "$SRC"
./configure --disable-all-engines --enable-release --disable-detection-full --enable-engine="$ENGINE"
make -j"$(nproc)"
make test
mkdir -p dist-linux && cp scummvm dist-linux/scummvm-remaster && cp COPYING dist-linux/GPL-3.0.txt
echo "Linux: $SRC/dist-linux"
if [ "${2:-}" = "web" ]; then
  dists/emscripten/build.sh build --disable-all-engines --enable-release --enable-engine="$ENGINE"
  echo "Web: $SRC/build-emscripten"
fi
