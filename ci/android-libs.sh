#!/bin/bash
# Builds libpng, libjpeg-turbo, libogg and libvorbis for Android arm64 with the NDK.
# Usage: ANDROID_NDK_ROOT=... android-libs.sh <prefix>
# Copy to .github/remaster/android-libs.sh in the ScummVM fork (used by remaster-build.yml).
set -euo pipefail
PREFIX=${1:?prefix}
API=21
ABI=arm64-v8a
TC="$ANDROID_NDK_ROOT/build/cmake/android.toolchain.cmake"
WORK=$(mktemp -d)
mkdir -p "$PREFIX"

fetch() { curl -fsSL "$1" | tar xz -C "$WORK"; }

cmake_build() {
  local src=$1; shift
  cmake -S "$src" -B "$src/build" -G "Unix Makefiles" \
    -DCMAKE_TOOLCHAIN_FILE="$TC" -DANDROID_ABI=$ABI -DANDROID_PLATFORM=android-$API \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$PREFIX" -DBUILD_SHARED_LIBS=OFF \
    -DCMAKE_POSITION_INDEPENDENT_CODE=ON "$@"
  cmake --build "$src/build" -j"$(nproc)"
  cmake --install "$src/build"
}

fetch https://github.com/pnggroup/libpng/archive/refs/tags/v1.6.43.tar.gz
cmake_build "$WORK/libpng-1.6.43" -DPNG_SHARED=OFF -DPNG_TESTS=OFF -DPNG_TOOLS=OFF

fetch https://github.com/libjpeg-turbo/libjpeg-turbo/archive/refs/tags/3.0.3.tar.gz
cmake_build "$WORK/libjpeg-turbo-3.0.3" -DENABLE_SHARED=OFF -DWITH_TURBOJPEG=OFF

fetch https://github.com/xiph/ogg/archive/refs/tags/v1.3.5.tar.gz
cmake_build "$WORK/ogg-1.3.5" -DINSTALL_DOCS=OFF

fetch https://github.com/xiph/vorbis/archive/refs/tags/v1.3.7.tar.gz
cmake_build "$WORK/vorbis-1.3.7" -DOGG_ROOT="$PREFIX"

echo "Android libraries installed in $PREFIX"
