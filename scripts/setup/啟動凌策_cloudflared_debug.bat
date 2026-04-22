@echo on
chcp 65001
title 凌策 tunnel debug
echo.
echo ==================================================
echo  除錯版：逐步顯示每一步，有錯立刻暫停
echo ==================================================
echo.
echo 目前時間：%date% %time%
echo 當前目錄：%cd%
echo.

echo [1] 檢查 Ollama 是否已安裝...
where ollama
if errorlevel 1 (
    echo.
    echo ❌ Ollama 未安裝
    echo 請下載： https://ollama.com/download/windows
    pause
    exit /b 1
)
echo ✅ Ollama 已安裝
echo.
pause

echo [2] 啟動 Ollama 服務...
start "Ollama" ollama serve
timeout /t 3
echo ✅ Ollama 啟動指令已送出
echo.
pause

echo [3] 確認 qwen2.5:7b 模型...
ollama list
echo.
pause

echo [4] 檢查 cloudflared 是否已安裝...
where cloudflared
if errorlevel 1 (
    echo.
    echo ❌ cloudflared 未安裝
    echo.
    echo 請 3 選 1 安裝：
    echo.
    echo   方法 A ^(最簡單^)：開 PowerShell 輸入：
    echo      winget install --id Cloudflare.cloudflared
    echo.
    echo   方法 B ^(手動下載^)：
    echo      1. https://github.com/cloudflare/cloudflared/releases/latest
    echo      2. 下載 cloudflared-windows-amd64.exe
    echo      3. 重命名為 cloudflared.exe
    echo      4. 放到 C:\Windows 或任何 PATH 目錄
    echo.
    echo   方法 C ^(scoop^)：
    echo      scoop install cloudflared
    echo.
    pause
    exit /b 1
)
echo ✅ cloudflared 已安裝
echo.
pause

echo [5] 啟動 Cloudflare Tunnel（這不會關閉，等你看到 URL）...
echo.
echo     👀 稍後找到類似這行：
echo         https://XXXX.trycloudflare.com
echo     把它複製起來貼到 Render Dashboard 的 OLLAMA_URL
echo.
echo ==================================================
cloudflared tunnel --url http://localhost:11434
echo.
echo Tunnel 已結束
pause
