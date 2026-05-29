# MU Immortal Bot — Runtime distribution

Packaged desktop app built with PyInstaller (`--onedir`, entry point `bot_ui.py`). End users do not need Python installed.

**Important:** builds are **not cross-compiled**. macOS artifacts are built on `macos-latest`, Windows artifacts on `windows-latest`.

---

## Download from GitHub Actions (recommended)

Automated builds run on **push to `main`** and on **manual workflow dispatch**.

### Steps

1. Open the repository on GitHub → **Actions**.
2. Select workflow **Build MU Immortal Bot**.
3. Open the latest successful run.
4. Scroll to **Artifacts** at the bottom.
5. Download:
   - **MUImmortalBot-Windows** — full `dist/MUImmortalBot/` folder (zipped)
   - **MUImmortalBot-macOS** — full `dist/MUImmortalBot/` folder (zipped)

Artifacts are kept **30 days**.

### After download

**Windows:** unzip and run `MUImmortalBot.exe` inside the folder (keep all files together).

**macOS:** unzip and run `./MUImmortalBot` (if blocked: right-click → Open).

### Before running the bot

1. Start your **Android emulator** (BlueStacks, etc.) and open **MU Immortal**.
2. Verify ADB sees the device (see platform setup below).
3. Install **Tesseract** if you want automatic level OCR (optional; manual level still works).

---

## What is included in the bundle

| Resource | Purpose |
|----------|---------|
| `templates/` | Vision template images |
| `navigation/` | Map JSON definitions |
| `profiles/` | Default profile seeds (writable copy next to the exe) |
| `special_locations/` | Farm spot / elf buff seeds (writable copy next to the exe) |

User-edited profiles and locations are stored beside the executable after first run.

---

## Build locally (developers)

### Prerequisites

```bash
python -m venv venv
# macOS:
source venv/bin/activate
# Windows:
venv\Scripts\activate.bat

pip install -r requirements.txt
pip install pyinstaller
```

Shared spec: `MUImmortalBot.spec` (`--onedir`, name `MUImmortalBot`).

### macOS (on Mac only)

```bash
chmod +x scripts/build_mac.sh
./scripts/build_mac.sh
```

Output: `dist/MUImmortalBot/MUImmortalBot`

### Windows (on Windows only)

```bat
scripts\build_windows.bat
```

Output: `dist\MUImmortalBot\MUImmortalBot.exe`

### CI workflow

See `.github/workflows/build.yml` — same scripts, Python **3.13**.

---

## macOS — End user setup

### Emulator

Install BlueStacks (or another Android emulator) and run MU Immortal **before** starting the bot.

### ADB

```bash
brew install --cask android-platform-tools
adb devices
```

The emulator must appear as `device`.

### Tesseract OCR (optional)

```bash
brew install tesseract
tesseract --version
```

### Run

```bash
./MUImmortalBot/MUImmortalBot
```

### Writable data

Next to the executable:

- `profiles/`
- `special_locations/`
- `debug/` (OCR debug crops)

---

## Windows — End user setup

### Emulator

Install BlueStacks (or another Android emulator) and run MU Immortal **before** starting the bot.

### ADB

Install [Android SDK Platform-Tools](https://developer.android.com/tools/releases/platform-tools) and add the folder to **PATH** (must contain `adb.exe`).

```powershell
adb devices
```

The emulator must appear as `device`.

### Tesseract OCR (optional)

1. Installer: https://github.com/UB-Mannheim/tesseract/wiki  
2. Add to PATH, e.g. `C:\Program Files\Tesseract-OCR`  
3. Verify: `tesseract --version`

### Run

```bat
MUImmortalBot\MUImmortalBot.exe
```

Keep the entire `MUImmortalBot` folder intact when copying to another PC.

### Writable data

Next to `MUImmortalBot.exe`:

- `profiles\`
- `special_locations\`
- `debug\`

---

## Basic usage

1. Open emulator and game.
2. Confirm `adb devices`.
3. Open **MU Immortal Bot**.
4. Select **Device** and **Profile**.
5. Set **Nivel PJ** (or use OCR).
6. Click **Iniciar Bot** and answer the spot confirmation.

Use **Refrescar dispositivos** or **Reiniciar ADB** in the UI if the device list is empty.

---

## OCR troubleshooting

If level detection fails, check:

- `debug/level_crop_raw.png`
- `debug/level_crop_processed.png`

Set `DEBUG_LEVEL_OCR = True` in `core/character_level_reader.py` before rebuilding.

---

## Runtime dependencies (bundled vs system)

**Bundled:** opencv-python, Pillow, numpy, pytesseract (see `requirements_runtime.txt`).

**Not bundled (install on host):** `adb`, `tesseract`.
