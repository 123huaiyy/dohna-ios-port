#!/usr/bin/env bash
set -euo pipefail

# Build Aether.ipa embedding the patched USADA-KARROT/xsystem4 (AIN v14 + GBK) runtime.
# Must be executed on macOS with Xcode (Apple iOS SDK) + Godot 4.7.2 + vcpkg prerequisites.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
XS4_DIR="$PORT_ROOT/engine/xsystem4"
OVERLAY_CMAKE="$PORT_ROOT/aether_overlay/CMakeLists.xsystem4_runtime.txt"
STANDALONE_PATCH="$PORT_ROOT/aether_overlay/apply_dohna_standalone.py"

AETHER_DIR="${1:-${AETHER_DIR:-$PORT_ROOT/.aether}}"
AETHER_REF="${AETHER_REF:-eaaccc78965ca95efce94525014359ad94e7603b}"
BUILD_TYPE="${BUILD_TYPE:-release}"
JOBS="${JOBS:-4}"

if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "Error: iOS .ipa compilation requires macOS with Xcode (current OS: $(uname -s))." >&2
    echo "       Run this script on a Mac, or trigger .github/workflows/build_dohna_ios.yml on GitHub Actions." >&2
    exit 1
fi

if [[ ! -f "$XS4_DIR/src/embedded.c" ]]; then
    echo "Error: patched xsystem4 runtime not found at $XS4_DIR" >&2
    exit 1
fi

if [[ ! -d "$AETHER_DIR/.git" ]]; then
    echo "Cloning AetherKiri/Aether ($AETHER_REF) into $AETHER_DIR ..."
    mkdir -p "$AETHER_DIR"
    git -C "$AETHER_DIR" init
    git -C "$AETHER_DIR" remote add origin https://github.com/AetherKiri/Aether.git
    git -C "$AETHER_DIR" fetch --depth 1 origin "$AETHER_REF"
    git -C "$AETHER_DIR" checkout FETCH_HEAD
fi

pushd "$AETHER_DIR" >/dev/null

# Initialize public submodules required by Aether's iOS build (private runtimes stay off).
export AETHERKIRI_WITH_INTERNAL="${AETHERKIRI_WITH_INTERNAL:-false}"
export AETHERKIRI_ENABLE_INTERNAL="${AETHERKIRI_ENABLE_INTERNAL:-false}"
git -c url.https://github.com/.insteadOf=git@github.com: submodule update --init --depth 1 \
    packages/AetherONScripterYuri \
    packages/AetherSiglus \
    packages/AetherMinori \
    packages/AetherCMVS \
    packages/AetherEntisGLS \
    packages/AetherKrkr \
    packages/AetherMAGES \
    packages/AetherSystem4 \
    packages/rfvp \
    packages/ruffle
git -c url.https://github.com/.insteadOf=git@github.com: submodule update --init --recursive --depth 1 \
    packages/psdfile \
    packages/AetherN2System \
    packages/AetherSystem35 \
    packages/AetherSystem3

if [[ ! -f "$AETHER_DIR/bridge/xsystem4_runtime/CMakeLists.txt.orig" ]]; then
    cp "$AETHER_DIR/bridge/xsystem4_runtime/CMakeLists.txt" \
       "$AETHER_DIR/bridge/xsystem4_runtime/CMakeLists.txt.orig"
fi
cp "$OVERLAY_CMAKE" "$AETHER_DIR/bridge/xsystem4_runtime/CMakeLists.txt"

if [[ -f "$STANDALONE_PATCH" ]]; then
    echo "==> Applying standalone Dohna Dohna branding and auto-boot overlay"
    python3 "$STANDALONE_PATCH" "$AETHER_DIR"
fi

if command -v ccache >/dev/null 2>&1; then
    export CMAKE_C_COMPILER_LAUNCHER="${CMAKE_C_COMPILER_LAUNCHER:-ccache}"
    export CMAKE_CXX_COMPILER_LAUNCHER="${CMAKE_CXX_COMPILER_LAUNCHER:-ccache}"
fi

export AETHERKIRI_XSYSTEM4_DIR="$XS4_DIR"
chmod +x ./build.sh
./build.sh ios "$BUILD_TYPE" --jobs="$JOBS" --package-ipa

if [[ -f "out/ios/$BUILD_TYPE/build.ninja" ]] && ! grep -Fq "$XS4_DIR" "out/ios/$BUILD_TYPE/build.ninja"; then
    echo "Error: build.ninja did not reference patched runtime $XS4_DIR" >&2
    exit 1
fi

popd >/dev/null

BUILD_TYPE_CAP="$(tr '[:lower:]' '[:upper:]' <<< "${BUILD_TYPE:0:1}")${BUILD_TYPE:1}"
IPA_PATH="$AETHER_DIR/out/godot/ios/$BUILD_TYPE/Aether-${BUILD_TYPE_CAP}-Unsigned.ipa"
echo "Built iOS package: $IPA_PATH"
