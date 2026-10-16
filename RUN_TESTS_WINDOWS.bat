@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo Run RUN_WINDOWS.bat at least once before verifying.
 pause
 exit /b 1
)
".venv\Scripts\python.exe" -m pytest -q
if errorlevel 1 (echo TESTS FAILED & pause & exit /b 1)
".venv\Scripts\python.exe" -m scripts.verify_operations --output evidence\operations-matrix-local.json
if errorlevel 1 (echo PROVIDER CHECKS FAILED & pause & exit /b 1)
echo.
echo Verification complete. Inspect evidence\operations-matrix-local.json
pause
