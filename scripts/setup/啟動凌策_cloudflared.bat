@echo off
chcp 65001 >nul
REM ═══════════════════════════════════════════════════════════
REM  凌策雲端 Ollama tunnel 啟動器（Cloudflare Tunnel 版）
REM  免註冊、免 token、比 ngrok 穩定
REM  作用：啟動本機 Ollama + Cloudflare Tunnel
REM        讓 Render 雲端版能真正使用 Qwen 2.5 7B 做推論
REM ═══════════════════════════════════════════════════════════

title 凌策 · 本機 Ollama + Cloudflare Tunnel

echo.
echo ========================================
echo  凌策雲端 AI 精煉 tunnel 啟動中
echo  （Cloudflare Tunnel · 免註冊版）
echo ========================================
echo.

REM Step 1: 確認 ollama 已安裝
where ollama >nul 2>nul
if %errorlevel% neq 0 (
    echo [1/3] ❌ Ollama 未安裝
    echo     請下載： https://ollama.com/download/windows
    echo.
    pause
    exit /b 1
)
echo [1/3] ✅ Ollama 已安裝
echo.

REM Step 2: 啟動 Ollama 服務（背景）
echo [2/3] 啟動 Ollama 服務 ( port 11434 )...
start /B "" ollama serve >nul 2>&1
timeout /t 3 /nobreak >nul
echo        ✅ Ollama 服務已在背景運行
echo.

REM 確認 qwen2.5:7b 模型存在
ollama list | findstr "qwen2.5:7b" >nul
if %errorlevel% neq 0 (
    echo        ⚠️  qwen2.5:7b 模型未下載，現在開始下載（約 5GB）...
    ollama pull qwen2.5:7b
)
echo.

REM Step 3: 確認 cloudflared 已安裝
set CF_EXE=cloudflared
where cloudflared >nul 2>nul
if %errorlevel% neq 0 (
    REM 嘗試從當前目錄 / 專案根目錄找
    if exist "%~dp0cloudflared.exe" set CF_EXE="%~dp0cloudflared.exe"
    if exist "%~dp0..\..\cloudflared.exe" set CF_EXE="%~dp0..\..\cloudflared.exe"
)

where cloudflared >nul 2>nul
if %errorlevel% neq 0 (
    if not exist "%~dp0cloudflared.exe" (
        echo [3/3] ❌ cloudflared 未安裝
        echo.
        echo 請先下載 cloudflared.exe（約 25MB，無需註冊帳號）：
        echo.
        echo   1. 到 https://github.com/cloudflare/cloudflared/releases/latest
        echo   2. 下載 cloudflared-windows-amd64.exe
        echo   3. 重命名為 cloudflared.exe
        echo   4. 放到本 bat 同目錄： %~dp0
        echo      或任何已在 PATH 的目錄
        echo.
        echo 💡 也可以用 winget 一鍵安裝：
        echo      winget install --id Cloudflare.cloudflared
        echo.
        pause
        exit /b 1
    )
)
echo [3/3] ✅ cloudflared 已準備
echo.

echo ========================================
echo  啟動 Cloudflare Tunnel ( Ollama 11434 → 雲端 )
echo ========================================
echo.
echo 👀 稍後會看到 Your quick Tunnel has been created
echo    複製下方 https://XXXX.trycloudflare.com 網址
echo    然後到 Render Dashboard → Environment：
echo.
echo      OLLAMA_URL   = 上述 https 網址
echo      OLLAMA_MODEL = qwen2.5:7b
echo.
echo    Save 後 Render 會重建（~3 分鐘）
echo.
echo 🔒 此視窗保持開著，評審測試時 AI 推論會發生在你的電腦
echo    （按 Ctrl+C 即中止隧道）
echo.
echo ========================================
echo.

%CF_EXE% tunnel --url http://localhost:11434
