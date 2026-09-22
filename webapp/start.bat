@echo off
REM === VideoStick WebApp launcher ===
REM Set environment then start Flask server.

setlocal
cd /d "%~dp0\.."

REM Use venv Python if available
if exist "venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0\..\venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

REM Set project root so 'src' package can be imported
set "PYTHONPATH=%~dp0\.."

echo.
echo ============================================================
echo  VideoStick WebApp
echo  Python: %PYTHON_EXE%
echo  URL:    http://127.0.0.1:5555
echo ============================================================
echo.

"%PYTHON_EXE%" webapp\webapp.py
endlocal
