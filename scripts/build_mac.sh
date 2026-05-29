#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "[BUILD] Platform: macOS"
echo "[BUILD] Cleaning previous artifacts..."
rm -rf build dist

if [[ ! -d "venv" ]]; then
  echo "[BUILD] venv not found. Create it first:"
  echo "  python3 -m venv venv"
  echo "  source venv/bin/activate"
  echo "  pip install -r requirements.txt"
  exit 1
fi

# shellcheck disable=SC1091
source venv/bin/activate

echo "[BUILD] Installing build dependencies..."
pip install -q pyinstaller

echo "[BUILD] Compiling Python sources..."
python -m py_compile \
  bot_ui.py \
  core/path_utils.py \
  core/vision.py \
  core/profile.py \
  core/navigation_config.py \
  core/special_locations.py \
  core/character_level_reader.py

echo "[BUILD] Running PyInstaller (--onedir)..."
pyinstaller MUImmortalBot.spec --noconfirm --clean

echo "[BUILD] Done."
echo "[BUILD] Output: $ROOT/dist/MUImmortalBot/"
echo "[BUILD] Run:    $ROOT/dist/MUImmortalBot/MUImmortalBot"
