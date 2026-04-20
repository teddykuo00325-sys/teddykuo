@echo off
REM ═══════════════════════════════════════════════
REM  凌策專案 — 新機器一鍵設定
REM ═══════════════════════════════════════════════

echo.
echo ================================================
echo  凌策專案 — 新機器環境設定
echo ================================================
echo.

REM 1. 檢查 Python
echo [1/5] 檢查 Python...
python --version 2>nul
if errorlevel 1 (
  echo   錯誤：未安裝 Python。請先到 https://www.python.org 下載 3.11+ 版本
  pause & exit /b 1
)

REM 2. 檢查 Ollama
echo.
echo [2/5] 檢查 Ollama...
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
  echo   警告：Ollama 尚未啟動或未安裝
  echo   請到 https://ollama.com 下載並安裝
  echo   裝好後執行：ollama serve
  echo.
  echo   （可繼續安裝其他套件）
)

REM 3. 安裝 Python 依賴
echo.
echo [3/5] 安裝 Python 套件（現有）...
pip install flask flask-cors requests python-docx python-pptx

echo.
echo [4/5] 安裝 Python 套件（第三波升級）...
echo    這些套件較大，約需 1-3 分鐘...
pip install chromadb sentence-transformers reportlab

REM 4. 下載模型（如果 Ollama 可用）
echo.
echo [5/5] 檢查 / 下載 AI 模型...
curl -s http://localhost:11434/api/tags >nul 2>&1
if not errorlevel 1 (
  echo   正在拉取 gemma4:e2b (小模型，約 2GB)...
  ollama pull gemma4:e2b
  echo.
  echo   建議升級（有 GPU 的話）：
  echo     ollama pull qwen2.5:7b    （約 4.7GB，繁中優秀）
  echo     ollama pull qwen2.5:14b   （約 9GB，最強）
) else (
  echo   Ollama 未啟動，跳過模型下載
)

echo.
echo ================================================
echo   設定完成！
echo ================================================
echo.
echo 啟動後端：
echo   python src\backend\server.py
echo.
echo 開啟瀏覽器：
echo   http://localhost:5000/dashboard.html
echo.
echo 若要啟用第三波升級 (真 RAG + 大模型)：
echo   1. 確認 ollama pull qwen2.5:7b 完成
echo   2. 修改 src\backend\server.py 的 OLLAMA_MODEL
echo   3. 請 Claude 執行 HANDOFF.md 的「第三波詳細執行清單」
echo.
pause
