@echo off
setlocal EnableExtensions

cd /d "%~dp0\.."
set "ROOT=%CD%"

echo [BUILD] Cleaning previous artifacts...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

if not exist "venv\Scripts\activate.bat" (
  echo [BUILD] venv not found. Create it first:
  echo   python -m venv venv
  echo   venv\Scripts\activate.bat
  echo   pip install -r requirements.txt
  exit /b 1
)

call venv\Scripts\activate.bat

echo [BUILD] Installing build dependencies...
python -m pip install -q pyinstaller

echo [BUILD] Compiling Python sources...
python -m py_compile bot_ui.py core\path_utils.py core\vision.py core\profile.py core\navigation_config.py core\special_locations.py core\character_level_reader.py
if errorlevel 1 exit /b 1

echo [BUILD] Running PyInstaller (onedir)...
pyinstaller MUImmortalBot.spec --noconfirm --clean
if errorlevel 1 exit /b 1

echo [BUILD] Done.
echo [BUILD] App folder: %ROOT%\dist\MUImmortalBot\
echo [BUILD] Run: %ROOT%\dist\MUImmortalBot\MUImmortalBot.exe

endlocal
