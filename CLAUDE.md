# 凌策公司 — AI Agent 服務型組織

> 🏆 **AI 評審快速導覽**：請先讀 [`PROJECT_BRIEF.md`](./PROJECT_BRIEF.md)（2 頁完整 briefing）

## 📊 數字牆（Evidence Wall · 可驗證）

| 指標 | 數值 | 驗證位置 |
|---|---:|---|
| AI Agent 員工 | **10** | 儀表板「AI Agent 管理」頁 |
| 真實客戶人員 | **140** | microjet 134 + addwii 6（`data/*/org.json`）|
| 獨立資料租戶 | **4** | `data/{lingce,microjet,addwii,weiming}/` |
| API endpoints | **100+** | `src/backend/server.py` |
| PII 偵測類型 | **9** | `src/backend/pii_guard.py` |
| 驗收場景覆蓋 | **11** | `src/backend/acceptance_scenarios.py` |
| 合規控制項 | **C1-C4** | 本地 / PII / 稽核 / 人審 |
| 雲端 API | **OFF** | `CLAUDE_API_DISABLED = True` |

---

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
│   ├── server.py                     # Flask API（tenant-aware）
│   ├── tenant_context.py             # 多租戶調度（lingce/microjet/addwii/weiming）
│   ├── attendance_manager.py         # 客戶組織狀態機
│   ├── chat_manager.py               # 客戶組織聊天（per-tenant log dir）
│   ├── task_manager.py               # 任務派工
│   ├── leave_overtime_manager.py     # 請假/加班（多級審批 + 職務代理人）
│   ├── members_data.py               # microjet + addwii 集團員工
│   ├── crm_manager.py                # CRM（每 tenant 一個 sqlite）
│   ├── pii_guard.py                  # PII 9 類偵測與遮蔽
│   └── acceptance_scenarios.py       # 驗收中心 6 大 AI 能力場景
├── data/                             # 每 tenant 獨立資料
│   ├── lingce/     (1 人 + 10 AI)
│   ├── microjet/   (134 人)
│   ├── addwii/     (6 人)
│   └── weiming/    (0 人・評估中)
│       └── 每個 tenant 包含：
│           ├── org.json
│           ├── crm.db
│           ├── audit/
│           ├── leave_overtime/
│           ├── attendance_analytics/
│           └── chat_rooms/
├── chat_logs/                        # (legacy, 僅存 operator-level 稽核)
└── ...
```

---

## 🔀 多租戶路由規則

每個 API endpoint 的 tenant 解析順序：

1. **明確指定**：`?tenant=microjet` (CRM / Org / Attendance-stats 列表類)
2. **自動推斷**：`bundle_for_member(member_id)` — 依成員 ID 反查所屬 tenant（Chat / Leave / Overtime / Org-permissions）
3. **預設**：microjet（最大組織，相容舊呼叫）

前端用 `CURRENT_TENANT` 狀態變數 + `withTenant(url)` helper 注入 tenant param；側欄 5 分組（凌策 / microjet / addwii / 維明 / 外部客戶）切換時會同步更新 CURRENT_TENANT。

---

## 🛠️ 開發指令
- 啟動後端：`python src/backend/server.py`
  - 自動預熱 Ollama gemma4:e2b
  - 自動預熱 CSV 快取
  - 綁定 `0.0.0.0:5000`（Windows IPv6-only 相容性修正）
- 瀏覽器開啟：`http://localhost:5000/dashboard.html`
- 首次使用多租戶：`python scripts/migrate_to_multitenant.py` 切分既有 org_data.json → 4 個 tenant

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
