@echo off
chcp 65001 >nul
REM ═══════════════════════════════════════════════════════════
REM  凌策雲端 Ollama tunnel 啟動器（評審展示用）
REM  作用：啟動本機 Ollama + ngrok tunnel
REM        讓 Render 雲端版能真正使用 Qwen 2.5 7B 做推論
REM  注意：比賽期間需保持此視窗開著、電腦不睡眠
REM ═══════════════════════════════════════════════════════════

title 凌策 · 本機 Ollama + ngrok 雲端隧道

echo.
echo ========================================
echo  凌策雲端 AI 精煉 tunnel 啟動中
echo ========================================
echo.

REM Step 1: 確認 ollama 已安裝
where ollama >nul 2>nul
if %errorlevel% neq 0 (
    echo [1/3] Ollama 未安裝，請先下載：https://ollama.com/download/windows
    pause
    exit /b 1
)
echo [1/3] ✅ Ollama 已安裝
echo.

REM Step 2: 啟動 Ollama 服務（背景）
echo [2/3] 啟動 Ollama 服務（port 11434）...
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

REM Step 3: 確認 ngrok 已安裝
where ngrok >nul 2>nul
if %errorlevel% neq 0 (
    echo [3/3] ❌ ngrok 未安裝
    echo.
    echo 請先完成：
    echo   1. 到 https://ngrok.com/signup 註冊免費帳號
    echo   2. 下載 https://ngrok.com/download 解壓到 PATH 目錄
    echo   3. 設定 authtoken： ngrok config add-authtoken 你的token
    echo.
    pause
    exit /b 1
)
echo [3/3] ✅ ngrok 已安裝
echo.

echo ========================================
echo  啟動 ngrok tunnel （Ollama 11434 → 雲端）
echo ========================================
echo.
echo 👀 複製下方 Forwarding 的 https 網址
echo    然後到 Render Dashboard → Environment：
echo      OLLAMA_URL   = 上述 https 網址
echo      OLLAMA_MODEL = qwen2.5:7b
echo    Save 後 Render 會重建（~3 分鐘）
echo.
echo 🔒 此視窗保持開著，評審測試時 AI 推論會發生在你的電腦
echo    （按 Ctrl+C 即中止隧道）
echo.

ngrok http 11434 --host-header=rewrite --request-header-add "ngrok-skip-browser-warning: true"
