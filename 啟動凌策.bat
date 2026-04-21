@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion
cd /d "%~dp0"

title LingCe Launcher
color 0B
echo.
echo ============================================================
echo    LingCe Company - One Click Launcher
echo    Author: Kuo Yu-Chun
echo ============================================================
echo.

REM ---- 1. Check Python ----
echo [1/4] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo    ERROR: Python not found.
    echo    Trying winget install Python.Python.3.11...
    where winget >nul 2>&1
    if errorlevel 1 (
        echo    winget not available. Please install Python manually:
        echo    https://www.python.org/downloads/
        echo    Make sure "Add Python to PATH" is checked!
        pause & exit /b 1
    )
    winget install Python.Python.3.11 --silent --accept-package-agreements --accept-source-agreements
    echo    Python installed. Please CLOSE this window and re-run the bat.
    pause & exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do echo        Python %%v  [OK]

REM ---- 2. Install packages ----
echo.
echo [2/4] Checking Python packages...
python -c "import flask, flask_cors, requests, reportlab, docx" >nul 2>&1
if errorlevel 1 (
    echo        Installing minimal packages ^(~1 min^)...
    python -m pip install --quiet --upgrade pip
    python -m pip install --quiet -r requirements-minimal.txt
    if errorlevel 1 (
        echo    Package install failed. Manual:  pip install -r requirements-minimal.txt
        pause & exit /b 1
    )
    echo        Packages installed  [OK]
) else (
    echo        Packages ready  [OK]
)

REM ---- 3. Kill old server ----
echo.
echo [3/4] Cleaning port 5000...
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5000 " ^| findstr "LISTENING"') do (
    taskkill /F /PID %%p >nul 2>&1
)

REM ---- 4. Start backend ----
echo.
echo [4/4] Starting backend server...
echo        A second window will open for server logs.
echo        ** DO NOT CLOSE or PRESS CTRL+C in either window **
echo        ** The server is running when you see "Running on http://..." **
echo.

start "LingCe Backend Server" cmd /k "title LingCe Backend Server & color 0A & cd /d "%~dp0" & echo. & echo ============================================ & echo   LingCe Backend - DO NOT CLOSE THIS WINDOW & echo   If you see "Press CTRL+C to quit" that's Flask's & echo   informational message. DO NOT press CTRL+C unless & echo   you want to stop the system. & echo ============================================ & echo. & python src\backend\server.py & echo. & echo Server stopped. Press any key to close. & pause"

REM Wait fixed 12 seconds for Flask to boot
echo        Waiting 12 sec for Flask to initialize.
for /L %%i in (1,1,12) do (
    <nul set /p=.
    timeout /t 1 /nobreak >nul
)
echo.

REM ── Open browser via 2 methods in parallel ──
set "URL=http://127.0.0.1:5000/index.html"

echo.
echo ============================================================
echo                     SYSTEM READY
echo ============================================================
echo.
echo    Opening browser automatically...
echo.

REM 只用 start 開一次（避免兩個 tab）；若失敗再用 Python 備援
start "" "%URL%" >nul 2>&1
if errorlevel 1 (
    python -c "import webbrowser; webbrowser.open('%URL%')" >nul 2>&1
)

REM ── Big clear manual instructions ──
echo.
echo ============================================================
echo.
echo   If browser did NOT open, please MANUALLY copy and paste
echo   this URL into your browser address bar:
echo.
echo        ^>^>^>  http://127.0.0.1:5000/index.html  ^<^<^<
echo.
echo   Or equivalently:
echo        http://localhost:5000
echo        http://localhost:5000/dashboard.html
echo.
echo ============================================================
echo.
echo   IMPORTANT:
echo     - Keep BOTH windows open while using the system
echo     - To stop the system: close the "LingCe Backend Server" window
echo     - Do NOT press CTRL+C unless you want to shutdown
echo.
echo ============================================================
echo.
echo   This launcher window will auto-close in 120 seconds.
echo   (The backend server will keep running)
echo.
timeout /t 120 /nobreak
