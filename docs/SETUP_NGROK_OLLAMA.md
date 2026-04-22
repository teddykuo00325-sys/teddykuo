# 🌐 雲端串接本機 Ollama（ngrok tunnel）

> **目標**：讓 Render 雲端版 `teddykuo.onrender.com` 使用你本機正在跑的 Ollama 做真正 Qwen 2.5 7B 推論。
> **合規效果**：評審在雲端操作「AI 精煉」時，實際推論是發生在凌策老闆（你）的電腦 — 真正的「本地 LLM · 個資不外流」。

---

## 📐 架構圖

```
評審瀏覽器                  Render 雲端 Flask          你家電腦
   │                             │                        │
   │  (1) 點「AI 精煉」            │                        │
   ├────────────────────────────▶│                        │
   │                             │  (2) POST /api/generate │
   │                             ├────────[ngrok]────────▶│
   │                             │                        │ (3) Ollama qwen2.5:7b
   │                             │                        │     本地推論 20~40s
   │                             │  (4) 回傳答案           │
   │                             │◀───────[ngrok]─────────│
   │  (5) 答案呈現                │                        │
   │◀────────────────────────────│                        │
```

關鍵點：**敏感資料只在你家電腦被處理，ngrok 只傳答案**。

---

## 🚀 快速設定（15 分鐘）

### Step 1：本機安裝 Ollama（若已裝跳過）

Windows：
```
下載 https://ollama.com/download/windows → 安裝
開啟 PowerShell：
  ollama pull qwen2.5:7b        # 下載 7B 模型（~5GB）
  ollama serve                    # 啟動服務（預設 port 11434）
```

驗證：
```
curl http://127.0.0.1:11434/api/tags
# 應看到 qwen2.5:7b 在列表
```

### Step 2：註冊 ngrok + 安裝

1. 到 https://ngrok.com/signup 用 Google / GitHub 一鍵註冊
2. 取得 Authtoken：https://dashboard.ngrok.com/get-started/your-authtoken
3. 下載安裝：https://ngrok.com/download（Windows 版）
4. 設定 authtoken：
   ```
   ngrok config add-authtoken <你的 token>
   ```

### Step 3：啟動 ngrok tunnel（暴露 Ollama）

```
ngrok http 11434 --host-header=rewrite
```

輸出會類似：
```
Forwarding  https://abc123-def456.ngrok-free.app → http://localhost:11434
```

**複製 https 網址** 👆 這就是 Render 要用的 OLLAMA_URL。

> ⚠️ `--host-header=rewrite` 必須加，否則 ngrok 免費版會把 Host header 改成 ngrok 網址，Ollama 會拒絕連線。

### Step 4：Render 設定環境變數

1. 到 https://dashboard.render.com → 選你的 service `lingce-demo`
2. 左側選 **Environment**
3. 編輯 `OLLAMA_URL`：
   - 從 `http://disabled-in-cloud:11434`
   - 改成 `https://abc123-def456.ngrok-free.app`
4. 編輯 `OLLAMA_MODEL`：
   - 從 `none`
   - 改成 `qwen2.5:7b`
5. 點 **Save changes** → Render 自動重建（~3 分鐘）

### Step 5：驗證

訪問 https://teddykuo.onrender.com/api/health

應看到：
```json
{
  "ollama": {
    "connected": true,
    "url": "https://abc123...ngrok-free.app",
    "model": "qwen2.5:7b",
    "available_models": ["qwen2.5:7b", ...]
  }
}
```

測試：
1. 打開 https://teddykuo.onrender.com/dashboard.html
2. 進 addwii 驗收中心 → 構面 1（產品知識）
3. 輸入「8 坪嬰兒房推薦？」
4. 勾 ✅ 啟用 Qwen 2.5 7B AI 精煉回覆
5. 按執行
6. **你電腦的 Ollama 會開始跑**（可觀察 CPU 飆高）
7. ~30s 後，雲端網頁出現真正的 AI 答案

---

## 🔐 安全性考量

| 項目 | 效果 |
|---|---|
| 評審看到的答案 | 由你家電腦產生，無任何外部 LLM 參與 |
| 資料是否上雲 | ngrok 傳輸有 TLS 加密，**僅傳 prompt 和回應文字** |
| 你家電腦被攻擊風險 | ngrok 只開 11434 port 到 Ollama，無其他入口 |
| 永久曝光 | 不會 — 關掉 ngrok 即失效 |

---

## ⚠️ 常見坑

### 坑 1：ngrok 免費版「瀏覽器警告頁」
免費版 ngrok URL 首訪會跳警告頁要求點 Visit Site。API 呼叫會收到 HTML 不是 JSON。

**解法**：啟動時加 header：
```
ngrok http 11434 --host-header=rewrite --request-header-add "ngrok-skip-browser-warning: true"
```

或在 Flask 端呼叫 Ollama 時加 header（已內建於 `server.py`）。

### 坑 2：ngrok 免費版 URL 每次重啟都變
每關掉再開 ngrok，URL 會變。需到 Render 重設環境變數。

**解法**：
- 付費版（$8/月）可綁定 static domain 一勞永逸
- 或腳本自動更新 Render env（進階）

### 坑 3：電腦休眠
電腦睡眠 → ngrok tunnel 斷 → 雲端 LLM 失效。

**解法**：
- Windows：`powercfg /change standby-timeout-ac 0` 停用 AC 模式睡眠
- 比賽期間把 `啟動凌策_ngrok.bat` 開著就行

---

## 🎯 評審體驗差異

| 場景 | 之前（無 ngrok）| 現在（ngrok + 本機 Ollama）|
|---|---|---|
| 按「AI 精煉」 | Template fallback · 3s · 一般品質 | **真 Qwen 2.5 7B** · 30s · 繁中高品質 |
| 合規說明 | 「雲端版未接 Ollama」 | **「推論發生在凌策老闆個人電腦 · 零外流」** |
| 故事性 | 弱 | **強**（真正的「1 人 + AI」— 老闆電腦就是伺服器）|

---

## 📝 一鍵腳本（比賽期間用）

見：`scripts/setup/啟動凌策_ngrok.bat`

雙擊即啟動：Ollama + ngrok tunnel + 印出要貼到 Render 的 URL。
