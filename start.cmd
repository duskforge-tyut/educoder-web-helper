@echo off
set PYTHONUTF8=1
set PYTHONDONTWRITEBYTECODE=1
"%~dp0.venv\Scripts\pythonw.exe" "%~dp0web\launcher.py"
