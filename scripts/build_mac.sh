#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "[BUILD] Platform: macOS"
echo "[BUILD] Cleaning previous artifacts..."
rm -rf build dist

if [[ -d "venv" ]]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
  echo "[BUILD] Using local venv"
else
  echo "[BUILD] Using system Python (CI or no venv)"
fi

echo "[BUILD] Installing build dependencies..."
python -m pip install -q pyinstaller

echo "[BUILD] Compiling Python sources..."
python -m py_compile \
  bot_ui.py \
  core/path_utils.py \
  core/vision.py \
  core/profile.py \
  core/navigation_config.py \
  core/special_locations.py \
  core/character_level_reader.py \
  core/device_manager.py

echo "[BUILD] Running PyInstaller (--onedir)..."
pyinstaller MUImmortalBot.spec --noconfirm --clean

echo "[BUILD] Done."
echo "[BUILD] Output: $ROOT/dist/MUImmortalBot/"
echo "[BUILD] Run:    $ROOT/dist/MUImmortalBot/MUImmortalBot"
