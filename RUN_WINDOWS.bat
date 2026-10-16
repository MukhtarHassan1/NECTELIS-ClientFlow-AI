@echo off
setlocal
cd /d "%~dp0"
echo ===============================================
echo   NECTELIS - CLIENTFLOW AI - LOCAL PROOF LAB
echo   Synthetic data / mock mode only
 echo ===============================================
if not exist ".venv\Scripts\python.exe" (
    echo Creating Python 3.11 virtual environment...
    py -3.11 -m venv .venv
    if errorlevel 1 (
        echo Python 3.11 was not found. Install Python 3.11+ and retry.
        pause
        exit /b 1
    )
)
echo Installing project dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo Dependency installation failed.
    pause
    exit /b 1
)
echo.
echo Open http://127.0.0.1:8000 in your browser.
echo Press Ctrl+C to stop.
".venv\Scripts\python.exe" -m uvicorn clientflow.api:app --host 127.0.0.1 --port 8000
pause
