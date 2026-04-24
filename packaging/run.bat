@echo off
REM Windows launcher for the SEO Content Pipeline.
REM Double-click from Explorer to start the app.
REM
REM Flow:
REM   1. cd to this script's directory (so api.env + uv.exe + .venv resolve locally).
REM   2. uv sync to materialize .venv with the required extras.
REM   3. uv run streamlit run streamlit_app\app.py on port 8501.
REM
REM SmartScreen will show "Windows protected your PC" on first launch;
REM the end-user README explains the More info -> Run anyway bypass.

setlocal

REM 1. cd to the launcher's own directory.
cd /d "%~dp0"

REM 2. Verify the bundled uv.exe exists.
if not exist ".\uv.exe" (
    echo.
    echo ERROR: Could not find the bundled 'uv.exe' next to this launcher.
    echo The zip may be incomplete - download a fresh copy from the releases page.
    echo.
    pause
    exit /b 1
)

REM 3. uv sync with the required extras.
.\uv.exe sync --quiet --extra ui --extra cli --extra anthropic --extra openai --extra google
if errorlevel 1 (
    echo.
    echo ERROR: Could not sync dependencies. Check your internet connection and try again.
    echo.
    pause
    exit /b 1
)

REM 4. Launch Streamlit. --server.headless false opens the browser automatically.
.\uv.exe run streamlit run streamlit_app\app.py --server.port 8501 --server.headless false

REM Pause on exit so any Streamlit error messages remain visible.
pause
endlocal
