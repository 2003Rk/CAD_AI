#!/usr/bin/env bash
set -euo pipefail

# Build a macOS .app and package it into a .dmg.
# Run from project root: bash scripts/build_macos_dmg.sh

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -d ".venv" ]]; then
  echo "Missing .venv. Create it first (python -m venv .venv)."
  exit 1
fi

source .venv/bin/activate

if ! command -v hdiutil >/dev/null 2>&1; then
  echo "Missing hdiutil. This script must be run on macOS."
  exit 1
fi

if ! python -c "import PyInstaller" >/dev/null 2>&1; then
  echo "Missing PyInstaller in .venv. Install it first: python -m pip install pyinstaller"
  exit 1
fi

rm -rf build dist

PYI_ARGS=(
  --noconfirm
  --clean
  --windowed
  --name "CAD Eval"
  --collect-all matplotlib
  --collect-all ezdxf
  --collect-all PIL
  --collect-all rich
)

if [[ -f ".env" ]]; then
  PYI_ARGS+=(--add-data ".env:.")
fi

if [[ -d "credentials" ]]; then
  PYI_ARGS+=(--add-data "credentials:credentials")
fi

if [[ -d "data" ]]; then
  PYI_ARGS+=(--add-data "data:data")
fi

pyinstaller \
  "${PYI_ARGS[@]}" \
  desktop_launcher.py

mkdir -p dist/dmg-root
rm -rf "dist/dmg-root/CAD Eval.app"
cp -R "dist/CAD Eval.app" "dist/dmg-root/CAD Eval.app"

DMG_PATH="dist/CAD-Eval-macOS.dmg"
rm -f "$DMG_PATH"

hdiutil create \
  -volname "CAD Eval" \
  -srcfolder "dist/dmg-root" \
  -ov \
  -format UDZO \
  "$DMG_PATH"

echo "Built DMG: $DMG_PATH"
