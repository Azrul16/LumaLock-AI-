@echo off
setlocal
title LumaLock AI - Local server
cd /d "%~dp0"
if not exist "%~dp0.venv\Scripts\python.exe" (
    echo The project-local Python environment is missing.
    echo Follow the setup steps in README.md to create .venv.
    pause
    exit /b 1
)
set "PYTHONNOUSERSITE=1"
set "OPENBLAS_NUM_THREADS=1"
set "LUMALOCK_WATCH_CONSOLE=1"
echo LumaLock AI - your local image workspace
echo.
echo Opening your browser. Keep this terminal open while using the app.
echo Closing this terminal stops the server and its AI workers.
echo.
"%~dp0.venv\Scripts\python.exe" -u "%~dp0launch.py" %*
if errorlevel 1 (
    echo.
    echo LumaLock could not start. See data\logs\lumalock.log for details.
    pause
)
endlocal
