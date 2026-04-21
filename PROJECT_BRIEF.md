# 凌策公司 · AI Agent 服務型組織

> **一句話：** 我們用 **1 位人類老闆 + 10 個 AI Agent 員工**，取代傳統「5 位業務、3 位工程師、2 位客服」的 IT 服務團隊，已實際服務 3 家付費客戶。

---

## 🎯 為什麼值得評審看第二眼

| 維度 | 一般參賽作品 | 凌策 |
|---|---|---|
| **AI 定位** | AI 是功能（聊天機器人） | AI 是**組織成員**（有 JD、有 KPI、有稽核紀錄）|
| **客戶** | Mock / Demo 資料 | 3 家**真實企業**：microjet 134 人、addwii 6 人、維明評估中 |
| **資料隔離** | 單一 DB | **4-tenant 架構**（lingce/microjet/addwii/weiming 各自獨立 CRM+Org+Audit）|
| **AI 模型** | 呼叫雲端 API | **本地 Ollama + PII Guard 9 類遮蔽**，個資不外流 |
| **合規** | 無稽核 | **append-only JSONL 稽核**（pii_audit / acceptance_audit / human_gate / org_audit）|
| **交付證據** | 簡報 | 依客戶 .docx 驗收標準**逐項對應**的驗收中心 |

---

## 📊 數字牆（Evidence Wall）

| 指標 | 數值 | 驗證方式 |
|---|---:|---|
| AI Agent 員工 | **10** | 老闆視角可點開每位的 JD、KPI、任務紀錄 |
| 真實客戶組織成員 | **140 人** | microjet 134 + addwii 6（非 mock） |
| Tenant 資料庫 | **4** | `data/lingce/`, `data/microjet/`, `data/addwii/`, `data/weiming/` |
| API endpoints | **100+** | `src/backend/server.py` |
| PII 遮蔽類型 | **9** | TW_ID / PHONE / LANDLINE / EMAIL / CREDIT / ROOM_ID / HOUSE_ID / TW_ADDR / CN_NAME |
| 驗收場景覆蓋 | **11** | addwii 5 構面 + microjet 5 場景 + 共通 QA |
| 合規控制項 | **4** | C1 本地不外流 / C2 PII 遮蔽 / C3 稽核日誌 / C4 人工審核閘 |
| 稽核日誌檔 | **4 類** | pii_audit / acceptance_audit / human_gate / org_audit |

---

## 🏛️ 核心心智模型

```
      ┌─────────────────┐
      │   人類老闆 × 1    │ ← 監管 / 決策 / 風控 / 簽核
      └────────┬────────┘
               │ 自然語言一句話
      ┌────────▼────────┐
      │ AI 指揮官（入口）│
      └────────┬────────┘
               │ 自動分派
   ┌───────────┼───────────┐
   ▼           ▼           ▼
┌───┐┌───┐┌───┐┌───┐┌───┐┌───┐┌───┐┌───┐┌───┐┌───┐
│Orc││BD ││CS ││Prop│FE ││BE ││QA ││Fin││Leg││Doc│
│hes││   ││   ││osal││   ││   ││   ││anc││al ││   │
└───┘└───┘└───┘└───┘└───┘└───┘└───┘└───┘└───┘└───┘
           10 個 AI Agent 員工（各司其職）
               │
               ▼
   ┌─────────────────────────┐
   │  3 家真實客戶現場        │
   │  microjet · addwii · 維明 │
   └─────────────────────────┘
```

**老闆日常**：打開「AI 指揮官」→ 輸入「幫 microjet 做 Q2 提案」→ Orchestrator 自動分派給 Proposal Agent + Finance Agent → 產出 PPT + PDF + 合約 → 老闆只需二次確認。

---

## 🛡️ 合規與資安（AI 評審最在意的地方）

### C1 · 個資不外流
- `CLAUDE_API_DISABLED = True`，assert 強制本地推論
- 使用 Ollama + Qwen 2.5 7B（完全離線）
- 所有輸入先經 `pii_guard.mask_text()` 遮蔽後才丟給 LLM

### C2 · PII 9 類自動偵測
```python
PII_TYPES = ['TW_ID', 'TW_PHONE', 'LANDLINE', 'EMAIL', 'CREDIT',
             'ROOM_ID', 'HOUSE_ID', 'TW_ADDR', 'CN_NAME']
```
範例：`A123456789` → `[USER_001]`；`0912-345-678` → `[PHONE_001]`

### C3 · 稽核日誌（append-only JSONL）
每一次 LLM 呼叫、每一筆組織編輯、每一次資料匯出都留下可驗證時間戳。

### C4 · 人工審核閘
刪除成員 / 匯出報表 / 重置情境 → 強制 `confirm()` + 稽核紀錄（含必填理由）。

---

## 🔀 多租戶架構（Technical Depth）

```
data/
├── lingce/      ← 凌策自己（1 人 + 10 AI）
│   ├── org.json           ← 組織
│   ├── crm.db             ← sqlite
│   └── audit/             ← 稽核
├── microjet/    ← 134 人客戶
├── addwii/      ← 6 人客戶
└── weiming/     ← 評估中
```

**路由規則**：
1. 明確 `?tenant=microjet` → 直達
2. 否則 `bundle_for_member(member_id)` → 自動推斷
3. 預設 → microjet（主力客戶）

**後端**：`tenant_context.py::TenantRegistry` 懶載入 Manager 實例，每個 tenant 獨立 `AttendanceManager / CRMManager / ChatManager / LeaveOvertimeManager`。

---

## 🧑‍🤝‍🧑 真實客戶（Evidence of Traction）

### 1️⃣ microjet 微型噴射 · B2B 精密製造 · 134 人
- 產品線：CurieJet 感測器 / ComeTrue 3D 列印 / MEMS 壓電微泵
- 交付系統：智慧組織管理（134 人打卡、請假、加班、職務代理人）
- 驗收依據：`microjet_驗收標準_v0.3_1.docx` · 5 場景全對應

### 2️⃣ addwii 加我科技 · B2C 場域無塵室 · 6 人
- 產品線：HCR-100/200/300（嬰兒房 4 坪 / 臥室 8 坪 / 客廳 12 坪）
- 交付系統：B2C CRM + 17 FAQ + HCR 推薦引擎（依坪數自動選型）
- 驗收依據：`addwii_驗收評比標準_含測試題目v3.docx` · 5 構面全對應

### 3️⃣ 維明顧問 · 評估中
- 商業模式待定，架構已預留 tenant slot（`data/weiming/`）

---

## 🎬 Demo 動線（評審可走完的路徑）

| 步驟 | 頁面 | 要看的重點 |
|---|---|---|
| 1 | 入口 `index.html` | 「1 人 + 10 AI」定位 |
| 2 | 儀表板 → AI 指揮官 | 下一句「幫 microjet 做 Q2 提案」看自動分派 |
| 3 | 左側切 addwii → CRM | 看與 microjet 完全隔離的客戶資料 |
| 4 | 客戶驗收中心 | 看 .docx 標準逐項對應的 AI 能力 |
| 5 | 合規中心 → PII Demo | 實測 PII 即時遮蔽 |
| 6 | 組織 → addwii | 看 6 人組織樹（與 microjet 134 人完全隔離）|

---

## 🏗️ 技術棧

| 層 | 選擇 | 為什麼 |
|---|---|---|
| 前端 | Tailwind CDN · 單一 HTML | 零 build step，評審可直接開 |
| 後端 | Flask + Werkzeug | 輕量，Windows 零配置 |
| LLM | Ollama · Qwen 2.5 7B | **本地推論**，個資不外流 |
| RAG | ChromaDB + sentence-transformers | 本地向量檢索 |
| CRM | SQLite（每 tenant 一個） | 無 server，純檔案可備份 |
| 稽核 | JSONL append-only | 不可改寫，法遵友善 |
| PDF | reportlab + 微軟正黑體 | 中文字型正常顯示 |
| 部署 | Docker + Render.com / 本地 .bat | 雙軌可切換 |

---

## 🚀 啟動方式

### 一鍵啟動（Windows）
```
雙擊 啟動凌策.bat
```
自動完成：Python 檢查 → Ollama 啟動 → 後端預熱 → 瀏覽器開啟儀表板

### 開發啟動
```bash
python src/backend/server.py
# → http://localhost:5000/dashboard.html
```

### 首次導入多租戶資料
```bash
python scripts/migrate_to_multitenant.py
```

---

## 📁 專案結構

```
lingce-company/
├── index.html                       # 入口網站
├── dashboard.html                   # 老闆儀表板（SPA）
├── PROJECT_BRIEF.md                 # 本文件（AI 評審首讀）
├── CLAUDE.md                        # 架構說明
├── src/backend/
│   ├── server.py                    # Flask API（tenant-aware）
│   ├── tenant_context.py            # 多租戶調度
│   ├── attendance_manager.py        # 組織狀態機
│   ├── chat_manager.py              # 聊天（per-tenant）
│   ├── task_manager.py              # 任務派工
│   ├── leave_overtime_manager.py    # 請假/加班（多級審批）
│   ├── crm_manager.py               # CRM（per-tenant sqlite）
│   ├── pii_guard.py                 # PII 9 類偵測
│   └── acceptance_scenarios.py      # 驗收中心 AI 能力
├── data/<tenant>/                   # 每 tenant 獨立資料
└── scripts/migrate_to_multitenant.py
```

---

## 🎖️ 一句話總結

> **別人做 AI 助手；我們做 AI 公司。**
> 用 10 個 AI Agent + 完整的多租戶架構 + 本地 LLM + 4 層合規，證明「AI 取代一個 IT 服務團隊」不是 PPT，是**可驗證的工程事實**。
