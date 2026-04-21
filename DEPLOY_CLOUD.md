# 雲端 Demo 部署指南

> 讓評審完全不用裝任何東西，開瀏覽器就能看到你的作品。
> 適合：主辦允許提供線上 demo URL、評審環境不確定。

---

## 🎯 方案比較

| 平台 | 費用 | 部署時間 | 優點 | 缺點 |
|---|---|---|---|---|
| **Render.com** ⭐ | 免費方案 | 3~5 分鐘 | 一鍵 Dockerfile 部署、自帶 HTTPS | 免費方案閒置 15 分鐘後休眠（首次訪問等 30-60 秒喚醒） |
| Railway.app | $5 試用金 | 2~3 分鐘 | 最快、最穩 | 無永久免費 |
| Fly.io | 免費方案 | 5~10 分鐘 | 全球多 region | 設定較複雜 |
| Hugging Face Spaces | 免費 | 10~15 分鐘 | AI 社群熟悉 | 有 2 CPU 限制 |

**推薦 Render.com** — 本專案已附 `Dockerfile` 和 `render.yaml`，連接 GitHub 後會自動部署。

---

## 🚀 Render 部署步驟（5 分鐘完成）

### 前置
1. 有 GitHub 帳號（免費）
2. 有 Render.com 帳號（免費，可用 GitHub 登入）

### 步驟
```bash
# 1. 進入專案目錄
cd C:\Users\B00325\Desktop\公司AI比賽\lingce-company

# 2. 初始化 git（若尚未）
git init
git add .
git commit -m "凌策公司 v1.0 雲端部署版"

# 3. 到 GitHub 建一個 private repo（名稱如 lingce-company）
#    複製它給的 URL，例如：https://github.com/yourname/lingce-company.git

# 4. push 上去
git remote add origin https://github.com/yourname/lingce-company.git
git branch -M main
git push -u origin main
```

### Render 設定
1. 到 https://dashboard.render.com/ 登入
2. 點右上 **New +** → **Web Service**
3. 點「Connect GitHub」→ 授權 → 選 `lingce-company` repo
4. Render 會自動偵測 `render.yaml` → 顯示「已找到 Blueprint」
5. 確認設定（Runtime: Docker、Plan: Free）→ 點 **Deploy**
6. 等 3~5 分鐘 build & deploy
7. 完成後拿到 URL：`https://lingce-demo-XXXX.onrender.com`

---

## ✅ 驗證部署成功

在瀏覽器打開：
- `https://your-app.onrender.com/` → 應該看到官網
- `https://your-app.onrender.com/dashboard.html` → 內部控制台
- `https://your-app.onrender.com/api/health` → 回傳 JSON

---

## 📋 雲端版本限制（要讓評審知道）

雲端版本為了成本考量**不跑 Ollama**，所以：

| 功能 | 雲端版 | 本地版 |
|---|---|---|
| 產品 Q&A 知識庫查詢 | ✓（bigram fallback） | ✓（ChromaDB + RAG） |
| AI 精煉回覆 | ✗（使用模板） | ✓（Qwen 2.5 7B） |
| CRM / 報價單 PDF | ✓ | ✓ |
| 合規中心 / PII Guard | ✓ | ✓ |
| 客戶驗收中心 | ✓ | ✓ |
| 三視角工作台 | ✓ | ✓ |
| Ollama 一鍵安裝助手 | ✗（雲端沒權限） | ✓ |

---

## 💡 小提醒

### Render 免費方案會休眠
- 閒置 15 分鐘沒人訪問 → 休眠
- 下次訪問 → 冷啟動 30~60 秒
- 評審點了第一下可能要等一下，建議在 URL 旁加註「首次載入約 60 秒」

### 若要永遠不休眠
- 升級 Render Starter 方案（$7/月）
- 或用 UptimeRobot 等服務每 5 分鐘 ping 一次 `/api/health`

### GitHub private repo 的原創性
- private repo 有 commit timestamp，是你的原創證據
- 不要公開 repo，避免同梯對手看到你的程式碼

---

## 🔗 繳交建議

把取得的 Render URL 加到：
1. 繳交 PPT 的最後一頁（「🌐 線上 Demo」QR Code + URL）
2. 完整版摘要 PDF 封面
3. 使用說明.txt 最上方

這樣評審有三種驗收路徑：
1. **最快**：開 Render URL（不用裝任何東西）
2. **完整**：解壓 zip + 雙擊 bat（含 Ollama 一鍵安裝）
3. **純文件**：看 PPT + PDF + screenshots

三層保險，不論評審電腦環境怎樣都能評分。

---

© 2026 Kuo Yu-Chun
