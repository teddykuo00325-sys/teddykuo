@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

title LingCe · 模型自動下載
color 0E
echo.
echo ============================================================
echo    凌策 LingCe · 本地 AI 模型自動下載
echo    首次執行：5-15 分鐘（依網路速度）
echo    之後執行：偵測已下載即跳過
echo ============================================================
echo.

REM ── 1. 檢查 Ollama ──
echo [1/3] 檢查 Ollama...
ollama --version >nul 2>&1
if errorlevel 1 (
    echo        Ollama 未安裝，嘗試 winget 安裝...
    where winget >nul 2>&1
    if errorlevel 1 (
        echo.
        echo    ERROR: winget 不可用，請手動安裝 Ollama：
        echo    https://ollama.com/download/windows
        pause & exit /b 1
    )
    winget install Ollama.Ollama --silent --accept-package-agreements --accept-source-agreements
    echo        Ollama 已安裝，請關閉此窗重新執行
    pause & exit /b 0
)
for /f "tokens=*" %%v in ('ollama --version 2^>^&1') do echo        %%v  [OK]

REM ── 2. 拉 Breeze-7B（台灣繁中 · 主模型） ──
echo.
echo [2/3] 檢查 Breeze-7B-Instruct-v1.0（台灣繁中專用）...
ollama list 2>nul | findstr /C:"second-state/Breeze-7B-Instruct" >nul
if errorlevel 1 (
    echo        下載中 ^(約 4.4 GB · 5-10 分鐘^)...
    echo        模型：聯發科 Breeze-7B-Instruct-v1.0 ^(GGUF Q4_K_M^)
    echo        來源：Hugging Face / second-state
    ollama pull hf.co/second-state/Breeze-7B-Instruct-v1_0-GGUF:Q4_K_M
    if errorlevel 1 (
        echo        WARNING: Breeze 下載失敗，將使用 qwen2.5:7b 備援
    ) else (
        echo        Breeze-7B 已下載  [OK]
    )
) else (
    echo        Breeze-7B 已存在  [OK]
)

REM ── 3. 拉 qwen2.5:7b（備援 · tool calling 強） ──
echo.
echo [3/3] 檢查 qwen2.5:7b（tool calling 備援）...
ollama list 2>nul | findstr /C:"qwen2.5:7b" >nul
if errorlevel 1 (
    echo        下載中 ^(約 4.7 GB · 5-10 分鐘^)...
    ollama pull qwen2.5:7b
    if errorlevel 1 (
        echo        WARNING: qwen2.5:7b 下載失敗
    ) else (
        echo        qwen2.5:7b 已下載  [OK]
    )
) else (
    echo        qwen2.5:7b 已存在  [OK]
)

echo.
echo ============================================================
echo    所有模型已就緒
echo    主模型：Breeze-7B-Instruct（台灣繁中）
echo    備援：qwen2.5:7b（tool calling）
echo ============================================================
echo.
echo    現在可雙擊 啟動凌策.bat 開始
echo.
endlocal
