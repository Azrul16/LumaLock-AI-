@echo off
setlocal
if not exist "%~dp0.venv\Scripts\pythonw.exe" (
    echo LumaLock's project-local environment is missing. Follow README.md to create .venv.
    pause
    exit /b 1
)
start "LumaLock AI" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0launch.py"
