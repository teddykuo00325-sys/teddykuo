#!/usr/bin/env bash
# 凌策 LingCe · 本地 AI 模型自動下載（macOS / Linux）
# 首次執行：5-15 分鐘（依網路速度）；之後執行：偵測已下載即跳過

set -e

echo ""
echo "============================================================"
echo "   凌策 LingCe · 本地 AI 模型自動下載"
echo "   首次執行：5-15 分鐘（依網路速度）"
echo "   之後執行：偵測已下載即跳過"
echo "============================================================"
echo ""

# ── 1. 檢查 Ollama ──
echo "[1/3] 檢查 Ollama..."
if ! command -v ollama &> /dev/null; then
    echo "       Ollama 未安裝。"
    OS="$(uname -s)"
    if [ "$OS" = "Darwin" ]; then
        echo "       macOS：請從 https://ollama.com/download/mac 下載安裝後重試"
        echo "       或執行：brew install ollama"
    elif [ "$OS" = "Linux" ]; then
        echo "       Linux：執行下列指令自動安裝："
        echo "         curl -fsSL https://ollama.com/install.sh | sh"
    fi
    exit 1
fi
echo "       $(ollama --version)  [OK]"

# ── 2. 拉 Breeze-7B（台灣繁中 · 主模型）──
echo ""
echo "[2/3] 檢查 Breeze-7B-Instruct-v1.0（台灣繁中專用）..."
if ollama list 2>/dev/null | grep -q "second-state/Breeze-7B-Instruct"; then
    echo "       Breeze-7B 已存在  [OK]"
else
    echo "       下載中（約 4.4 GB · 5-10 分鐘）..."
    echo "       模型：聯發科 Breeze-7B-Instruct-v1.0（GGUF Q4_K_M）"
    echo "       來源：Hugging Face / second-state"
    if ollama pull hf.co/second-state/Breeze-7B-Instruct-v1_0-GGUF:Q4_K_M; then
        echo "       Breeze-7B 已下載  [OK]"
    else
        echo "       WARNING: Breeze 下載失敗，將使用 qwen2.5:7b 備援"
    fi
fi

# ── 3. 拉 qwen2.5:7b（備援 · tool calling 強）──
echo ""
echo "[3/3] 檢查 qwen2.5:7b（tool calling 備援）..."
if ollama list 2>/dev/null | grep -q "qwen2.5:7b"; then
    echo "       qwen2.5:7b 已存在  [OK]"
else
    echo "       下載中（約 4.7 GB · 5-10 分鐘）..."
    if ollama pull qwen2.5:7b; then
        echo "       qwen2.5:7b 已下載  [OK]"
    else
        echo "       WARNING: qwen2.5:7b 下載失敗"
    fi
fi

echo ""
echo "============================================================"
echo "   所有模型已就緒"
echo "   主模型：Breeze-7B-Instruct（台灣繁中）"
echo "   備援：qwen2.5:7b（tool calling）"
echo "============================================================"
echo ""
echo "   現在可啟動 server："
echo "     python src/backend/server.py"
echo "   或 macOS / Linux：LINGCE_PORT=5050 python src/backend/server.py"
echo ""
