# 🌐 雲端串接本機 Ollama（Cloudflare Tunnel · 免註冊）

> **為什麼用 Cloudflare Tunnel 而非 ngrok**：
> - ✅ 免註冊、免 token
> - ✅ 台灣可正常使用
> - ✅ 無瀏覽器警告頁
> - ✅ Cloudflare 全球節點更穩定
> - ✅ 免費無限流量

---

## 📐 架構圖

```
評審瀏覽器                  Render 雲端 Flask          你家電腦
   │                             │                        │
   │  (1) 點「AI 精煉」            │                        │
   ├────────────────────────────▶│                        │
   │                             │  (2) POST /api/generate │
   │                             ├─[Cloudflare Tunnel]───▶│
   │                             │                        │ (3) Ollama qwen2.5:7b
   │                             │                        │     本地推論 20~40s
   │                             │  (4) 回傳答案           │
   │                             │◀──────────[CF]─────────│
   │  (5) 答案呈現                │                        │
   │◀────────────────────────────│                        │
```

**合規加分**：敏感資料只在你家電腦被處理，Cloudflare 只轉發加密 TLS 流量。

---

## 🚀 快速設定（10 分鐘）

### Step 1：本機安裝 Ollama（若已裝跳過）

Windows：
```powershell
# 下載 https://ollama.com/download/windows → 安裝
# 然後開 PowerShell：
ollama pull qwen2.5:7b        # 下載 7B 模型（~5GB · 首次較久）
```

### Step 2：安裝 cloudflared（3 種方式擇一）

**方式 A · winget（最簡單）**
```powershell
winget install --id Cloudflare.cloudflared
```

**方式 B · 手動下載**
1. 到 https://github.com/cloudflare/cloudflared/releases/latest
2. 下載 `cloudflared-windows-amd64.exe`（約 25 MB）
3. 重命名為 `cloudflared.exe`
4. 放到專案根目錄 `lingce-company\cloudflared.exe`

**方式 C · Scoop**
```powershell
scoop install cloudflared
```

---

### Step 3：一鍵啟動

雙擊：
```
scripts\setup\啟動凌策_cloudflared.bat
```

腳本會自動：
- 啟動 Ollama 服務（背景）
- 確認 qwen2.5:7b 已下載
- 啟動 Cloudflare Quick Tunnel
- 輸出你要貼到 Render 的 URL

你會看到類似輸出：
```
2026-04-22 ... INF +--------------------------------------------------------------------------------------------+
2026-04-22 ... INF |  Your quick Tunnel has been created! Visit it at (it may take some time to be reachable):  |
2026-04-22 ... INF |  https://lazy-forest-1234.trycloudflare.com                                                |
2026-04-22 ... INF +--------------------------------------------------------------------------------------------+
```

**複製** `https://lazy-forest-1234.trycloudflare.com` 👈

### Step 4：Render 設定環境變數

1. 到 https://dashboard.render.com → 選 `lingce-demo`
2. 左側 **Environment**
3. 編輯兩個變數：
   ```
   OLLAMA_URL   = https://lazy-forest-1234.trycloudflare.com
   OLLAMA_MODEL = qwen2.5:7b
   ```
4. **Save changes** → Render 自動重建（~3 分鐘）

### Step 5：驗證

訪問 https://teddykuo.onrender.com/api/health

應看到：
```json
{
  "ollama": {
    "connected": true,
    "url": "https://lazy-forest-1234.trycloudflare.com",
    "model": "qwen2.5:7b",
    "available_models": ["qwen2.5:7b", ...]
  }
}
```

### Step 6：實測

1. 打開 https://teddykuo.onrender.com/dashboard.html
2. 進 addwii 驗收中心 → 1️⃣ 產品知識
3. 輸入「8 坪嬰兒房推薦？」
4. 勾 ✅ 啟用 Qwen 2.5 7B AI 精煉回覆
5. 按執行
6. **你電腦的 CPU / GPU 會飆高** ← Ollama 在你電腦跑 7B 推論
7. ~30s 後雲端網頁出現真正繁中答案

---

## 🔐 合規敘事強化

評審會問：「雲端版怎麼做到本地 LLM？」

答：
> 凌策的設計是「1 人 + 10 AI」。這個「1 人」= 凌策老闆（郭祐均）。
> 當評審在雲端版點「AI 精煉」時，推論請求會透過 Cloudflare 加密隧道
> 送到**凌策老闆個人電腦**上的 Qwen 2.5 7B 模型做本地推論。
> **真正的「凌策伺服器」就是老闆那台電腦** — 這就是 1 人 + AI 組織的實踐。
> 個資全程加密傳輸、推論不落地、稽核紀錄即時寫入 JSONL。

---

## ⚠️ 注意事項

### 坑 1：免費 quick tunnel URL 每次重啟會變
每次重新跑 `cloudflared tunnel --url ...` 會產生新 URL。
重開後需回 Render 重設 `OLLAMA_URL`。

**解法**：
- 比賽期間保持腳本常駐（不關）
- 或免費註冊 Cloudflare 帳號可綁定 named tunnel（永久 URL）

### 坑 2：電腦休眠 → tunnel 斷
```powershell
# 停用 AC 睡眠
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
```

### 坑 3：防火牆可能擋 cloudflared
首次執行 Windows 會問是否允許網路存取 → 點「允許」。

### 坑 4：上傳頻寬
AI 答案通常 1~3KB 文字 → 家用網路完全夠。
即便評審同時問，你家上傳不會被吃滿。

---

## 🎯 效果對照

| 場景 | 無 tunnel | **有 tunnel** |
|---|---|---|
| 評審按「AI 精煉」 | Template fallback · 2s · 一般繁中 | **真 Qwen 2.5 7B** · 30s · 高品質繁中 |
| 合規敘事 | 「雲端版未接 Ollama」 | **「推論在凌策老闆電腦 · 零外流」** 🔥 |
| 故事性 | 弱 | **強** — 真正的「1 人 + AI」|
| 成本 | $0 | **$0** |

---

## 🛠️ 進階：永久 URL（可選）

若比賽期間每天重啟電腦，可用 named tunnel 綁永久子域：

```powershell
cloudflared login                # 一次性登入（會開瀏覽器）
cloudflared tunnel create lingce
cloudflared tunnel route dns lingce ollama.你的域名.com
cloudflared tunnel run lingce
```

需要你有一個 Cloudflare 託管的域名（也可免費申請）。

對比賽展示而言，**quick tunnel 已經足夠**。
