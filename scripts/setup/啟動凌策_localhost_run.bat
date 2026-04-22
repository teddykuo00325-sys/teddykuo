@echo off
chcp 65001
title 凌策 tunnel (localhost.run 備援方案)

echo.
echo ==================================================
echo  凌策 tunnel · localhost.run 版
echo  (免註冊、零安裝、不被 Cloudflare Bot 擋)
echo ==================================================
echo.

REM Step 1: Ollama
echo [1/3] 檢查 Ollama...
where ollama
if errorlevel 1 (
    echo ❌ Ollama 未安裝 https://ollama.com/download/windows
    pause
    exit /b 1
)
echo ✅ Ollama OK
echo.
start "Ollama" ollama serve
timeout /t 3
echo.

REM Step 2: 確認 OpenSSH
echo [2/3] 檢查 OpenSSH（Windows 10+ 內建）...
where ssh
if errorlevel 1 (
    echo ❌ OpenSSH 未安裝
    echo 開「設定 → 應用程式 → 選用功能」搜尋 OpenSSH Client 安裝
    pause
    exit /b 1
)
echo ✅ OpenSSH OK
echo.

REM Step 3: 建 SSH tunnel 到 localhost.run
echo [3/3] 啟動 SSH tunnel → localhost.run...
echo.
echo 👀 請稍候，會看到：
echo     https://XXXX.lhr.life → 複製這個 URL
echo     (首次連線會問 yes/no，輸入 yes)
echo.
echo 🔒 此視窗保持開著，關掉 tunnel 就失效
echo.
echo ==================================================

ssh -R 80:localhost:11434 nokey@localhost.run
