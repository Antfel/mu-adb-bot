# MU Immortal Bot — Runtime distribution

Packaged desktop app built with PyInstaller (`--onedir`). End users do not need Python installed.

**Important:** builds are **not cross-compiled**. Generate the macOS build on macOS and the Windows build on Windows.

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

## Build (developers)

### Prerequisites (both platforms)

```bash
python -m venv venv
# macOS / Linux:
source venv/bin/activate
# Windows:
venv\Scripts\activate.bat

pip install -r requirements.txt
pip install pyinstaller
```

Shared spec file: `MUImmortalBot.spec` (entry point: `bot_ui.py`).

### macOS build

Run **on macOS only**:

```bash
chmod +x scripts/build_mac.sh
./scripts/build_mac.sh
```

Output:

```text
dist/MUImmortalBot/MUImmortalBot
```

### Windows build

Run **on Windows only**:

```bat
scripts\build_windows.bat
```

Output:

```text
dist\MUImmortalBot\MUImmortalBot.exe
```

Distribute the entire folder `dist/MUImmortalBot/` (not only the `.exe`).

---

## macOS — End user setup

### 1. Emulator

Install BlueStacks (or another Android emulator) and run MU Immortal.

### 2. ADB

`adb` must be available in your shell PATH.

```bash
adb devices
```

You should see the emulator listed as `device`.

Install Android platform-tools if needed:

```bash
brew install --cask android-platform-tools
```

### 3. Tesseract OCR (automatic level read)

```bash
brew install tesseract
tesseract --version
```

### 4. Run the app

```bash
./dist/MUImmortalBot/MUImmortalBot
```

If macOS blocks the app (unsigned): **right-click → Open**.

### 5. Basic usage

1. Open emulator and game.
2. Confirm `adb devices`.
3. Open **MU Immortal Bot**.
4. Select **Device** and **Profile**.
5. Set **Nivel PJ** (or let OCR detect it).
6. Click **Iniciar Bot** and answer the spot confirmation dialog.

### Writable data (macOS)

Next to the executable:

- `dist/MUImmortalBot/profiles/`
- `dist/MUImmortalBot/special_locations/`
- `dist/MUImmortalBot/debug/` (OCR debug crops)

---

## Windows — End user setup

### 1. Emulator

Install BlueStacks (or another Android emulator) and run MU Immortal.

### 2. ADB

`adb.exe` must be on **PATH**, or place Android SDK **platform-tools** on PATH.

Example (PowerShell, session only):

```powershell
$env:Path += ";C:\platform-tools"
adb devices
```

Download platform-tools: [Android SDK Platform-Tools](https://developer.android.com/tools/releases/platform-tools)

Verify the emulator appears as `device`.

### 3. Tesseract OCR (automatic level read)

1. Download the Windows installer (UB Mannheim build):  
   https://github.com/UB-Mannheim/tesseract/wiki
2. Install Tesseract (default path is fine).
3. Add the install folder to **PATH**, e.g.  
   `C:\Program Files\Tesseract-OCR`
4. Verify in a new terminal:

```bat
tesseract --version
```

If OCR fails, the app still works with manual **Nivel PJ** from the profile/UI.

### 4. Run the app

```bat
dist\MUImmortalBot\MUImmortalBot.exe
```

Keep all files inside `dist\MUImmortalBot\` together when copying to another PC.

### 5. Basic usage

Same flow as macOS: device → profile → level → **Iniciar Bot** → spot dialog.

### Writable data (Windows)

Next to `MUImmortalBot.exe`:

- `dist\MUImmortalBot\profiles\`
- `dist\MUImmortalBot\special_locations\`
- `dist\MUImmortalBot\debug\`

---

## OCR troubleshooting

If level detection is wrong, inspect (after a failed or debug run):

- `debug/level_crop_raw.png`
- `debug/level_crop_processed.png`

Set `DEBUG_LEVEL_OCR = True` in `core/character_level_reader.py` before rebuilding to always save crops.

---

## Runtime Python dependencies (build machine)

See `requirements_runtime.txt`:

- opencv-python
- Pillow
- numpy
- pytesseract

System tools (not bundled): **adb**, **tesseract**.
