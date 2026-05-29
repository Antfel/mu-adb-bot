@echo off
setlocal EnableExtensions

cd /d "%~dp0\.."
set "ROOT=%CD%"

echo [BUILD] Platform: Windows
echo [BUILD] Cleaning previous artifacts...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

if exist "venv\Scripts\activate.bat" (
  call venv\Scripts\activate.bat
  echo [BUILD] Using local venv
) else (
  echo [BUILD] Using system Python (CI or no venv)
)

echo [BUILD] Installing build dependencies...
python -m pip install -q pyinstaller

echo [BUILD] Compiling Python sources...
python -m py_compile bot_ui.py core\path_utils.py core\vision.py core\profile.py core\navigation_config.py core\special_locations.py core\character_level_reader.py core\device_manager.py
if errorlevel 1 exit /b 1

echo [BUILD] Running PyInstaller (--onedir)...
pyinstaller MUImmortalBot.spec --noconfirm --clean
if errorlevel 1 exit /b 1

echo [BUILD] Done.
echo [BUILD] App folder: %ROOT%\dist\MUImmortalBot\
echo [BUILD] Run: %ROOT%\dist\MUImmortalBot\MUImmortalBot.exe

endlocal
