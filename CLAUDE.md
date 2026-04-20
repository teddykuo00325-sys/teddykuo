# 凌策公司 — AI Agent 服務型組織

## 🎯 專案定位（核心心智模型）

凌策公司 = **1 位人類老闆（兼員工）+ 10 個 AI Agent 員工** 所構成的新世代 IT 服務公司。
沒有傳統業務員、工程師、客服。所有職能都由 AI Agent 扮演。

### 組成

| 身份 | 人數 | 說明 |
|---|---:|---|
| **人類老闆** | 1 | 唯一實體員工；負責監管、決策、風控、簽核 |
| **AI Agent 員工** | 10 | Orchestrator · BD · 客服 · 提案 · 前端 · 後端 · QA · 財務 · 法務 · 文件 |

### 老闆如何工作
透過「AI 指揮官」頁面，用自然語言一句話下達指令 → Orchestrator 自動分派 →
10 個 AI Agent 或 6 個客戶能力場景（驗收中心）完成執行。

---

## 🧑‍🤝‍🧑 三家服務中客戶

| 客戶 | 商業模式 | 組織規模 |
|---|---|---|
| **microjet 微型噴射** | B2B 精密感測製造（CurieJet 感測器 / ComeTrue 3D 列印 / MEMS 壓電微泵） | 134 人真實組織 |
| **addwii 加我科技** | B2C 場域無塵室品牌（六款場域產品：嬰兒/廚房/浴室/客廳/臥室/餐廳） | 6 人真實組織 |
| **維明顧問** | 待定 | 評估中 |

### 「組織出缺勤」頁面
兩家客戶 (microjet 134 人 + addwii 6 人) 分別部署的「智慧組織管理系統」合併展示介面。
這**不是**凌策自己的 HR — 凌策內部只有 1 人 + 10 AI。各家客戶在此獨立運作。

### 「客戶驗收中心」頁面
根據客戶老闆提供的 .docx 驗收標準所生成的 AI 能力對應系統：
- `addwii_驗收評比標準_含測試題目v3.docx` → 5 大構面
- `microjet_驗收標準_v0.3_1.docx` → 5 大場景

---

## 📂 專案結構
```
lingce-company/
├── dashboard.html                    # 主儀表板（老闆視角）
├── src/backend/
│   ├── server.py                     # Flask API
│   ├── attendance_manager.py         # 客戶組織狀態機
│   ├── chat_manager.py               # 客戶組織聊天
│   ├── task_manager.py               # 任務派工
│   ├── leave_overtime_manager.py     # 請假/加班（多級審批 + 職務代理人）
│   ├── members_data.py               # microjet + addwii 集團員工
│   └── acceptance_scenarios.py       # 驗收中心 6 大 AI 能力場景
├── chat_logs/                        # JSONL 持久化
└── ...
```

---

## 🛠️ 開發指令
- 啟動後端：`python src/backend/server.py`
  - 自動預熱 Ollama gemma4:e2b
  - 自動預熱 CSV 快取
  - IPv6 dual-stack（`::`）避免 Windows localhost 解析延遲
- 瀏覽器開啟：`http://localhost:5000/dashboard.html`

## 🛡️ 技術選型
- 前端：HTML + Tailwind CSS (CDN)
- 後端：Flask + Werkzeug + requests
- AI：Ollama 本地（gemma4:e2b）+ Claude API 備援
- 資料：JSONL append-only + JSON state files
- 稽核：`acceptance_audit.jsonl` 非同步 queue 寫入

## 📋 關鍵功能模組

### 老闆視角
1. **📊 總覽儀表板** — 凌策體質 + 客戶現場一覽
2. **🤖 AI Agent 管理** — 10 位 AI 員工狀態
3. **💰 Token 成本** — AI 公司的 P&L
4. **⚡ AI 指揮官** ⭐ — 老闆下指令主要入口
5. **🎯 凌策客戶模擬器** — 模擬客戶上門
6. **📍 客戶組織現場** — microjet + addwii 140 人 Live
7. **🏆 客戶驗收中心** — 依 docx 標準對應之 AI 能力

### AI 指揮官 路由邏輯
1. 偵測到客戶 + 驗收場景關鍵字 → **Scenario Dispatch**（QA / Feedback / Proposal / Content / CSV / PII）
2. 偵測到客戶但無明確場景 → 預設 QA
3. 狀態查詢（進度/盤點）+ 無客戶 → **規則引擎**秒回
4. 其他 → 規則引擎通用引導

---

## 🚫 常見誤解澄清

- ❌ 凌策不是在賣「智慧組織管理系統」；那是已交付給 microjet+addwii 的**案例**
- ❌ 「組織出缺勤」140 人不是凌策員工；是客戶現場
- ❌ 驗收中心不是凌策自己定的標準；是客戶老闆給的 .docx 逐項對應
- ✅ 凌策賣的是「AI Agent 服務能力」本身 — 用 10 個 AI 取代業務/客服/工程/行銷團隊
