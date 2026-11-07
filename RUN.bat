@echo off
setlocal EnableExtensions DisableDelayedExpansion
title Get Going Fast - Viggle Recast
cd /d "%~dp0"
set "PYTHONDONTWRITEBYTECODE=1"
set "GRADIO_ANALYTICS_ENABLED=False"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" app.py %*
  exit /b %errorlevel%
)
if exist "runtime-python.txt" (
  set /p GGF_PYTHON=<runtime-python.txt
  "%GGF_PYTHON%" app.py %*
  exit /b %errorlevel%
)
echo Run the installer first, or configure runtime-python.txt for an existing runtime.
exit /b 1
