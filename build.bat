@echo off
REM Light AI Gateway - Windows Build Script
REM Run this on Windows to build the EXE

echo ====================================
echo  Light AI Gateway - Building Windows EXE
echo ====================================

REM Check Python
python --version
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.10+
    pause
    exit /b 1
)

REM Install dependencies
echo.
echo [1/3] Installing dependencies...
REM pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

REM Install PyInstaller
echo.
echo [2/3] Installing PyInstaller...
REM pip install pyinstaller==6.11.1
if errorlevel 1 (
    echo ERROR: Failed to install PyInstaller
    pause
    exit /b 1
)

REM Build EXE  (--clean removes stale cache, --noconfirm skips prompts)
echo.
echo [3/3] Building EXE (this may take a few minutes)...
pyinstaller build.spec --clean --noconfirm
if errorlevel 1 (
    echo ERROR: Build failed
    pause
    exit /b 1
)

echo.
echo ====================================
echo  Build Complete!
echo  Output: dist\AIGateway.exe
echo ====================================
pause
