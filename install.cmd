@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
set PIP_CACHE_DIR=%CD%\pip-cache
set TEMP=%CD%\temp
set TMP=%TEMP%
if not exist "%TEMP%" mkdir "%TEMP%"
python -m venv .venv
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -m pip install -e .
if errorlevel 1 goto fail
echo Installation complete. Configure EDUCODER_AK and EDUCODER_SK locally before starting.
pause
exit /b 0
:fail
echo Installation failed. Check the error above.
pause
exit /b 1
