# 凌策公司 · LingCe

> **1 位人類老闆 + 10 個 AI Agent 員工** 所構成的新世代 AI 服務公司
> 作者：郭祐均 Kuo Yu-Chun · 凌策 AI 擂台大賽作品

---

## 🏆 給評審的 3 分鐘快速導覽

| 順序 | 看什麼 | 理由 |
|---|---|---|
| 1 | [`PROJECT_BRIEF.md`](./PROJECT_BRIEF.md) | 2 頁完整 briefing（數字牆 / 對比表 / Demo 動線）|
| 2 | [`CLAUDE.md`](./CLAUDE.md) | 技術架構（tenant_context · API · 合規）|
| 3 | 實際跑一次 | 雙擊 `啟動凌策.bat` |

---

## 🚀 快速啟動（Windows 10/11）

### 最簡單的方式（終端使用者）
```
雙擊 啟動凌策.bat
```
- 自動檢查 Python → winget 安裝 → 啟動後端 → 打開瀏覽器
- 首次 20~60 秒；後續 10 秒

### 開發者模式
```bash
python src/backend/server.py
# → http://localhost:5000/dashboard.html
```

---

## ⚠️ 使用注意

- **不要**從檔案總管雙擊 `dashboard.html`（會變 `file://` 協定，CORS 擋 API）
- 請從瀏覽器打開：`http://localhost:5000/dashboard.html`
- 關閉系統 → 關掉黑色終端機視窗即可

---

## 📦 事前安裝

| 必裝 | Python 3.11+ | [下載](https://www.python.org/downloads/) · 安裝時勾「Add to PATH」|
| 選裝 | Ollama + Qwen 2.5 7B | [下載](https://ollama.com) · 用於本地 LLM 推論 |

> 沒裝 Ollama 也能跑 80% 功能（知識庫/CRM/PDF/合規中心/官網仍正常）

---

## 📊 這個專案在做什麼

凌策 LingCe 是一家 **AI Agent 服務型組織**：

- **1 位人類老闆**負責監管、決策、風控
- **10 個 AI Agent 員工**（Orchestrator / BD / CS / Proposal / FE / BE / QA / Finance / Legal / Doc）各司其職
- **3 家真實付費客戶**：microjet（134 人 B2B 製造）· addwii（6 人 B2C 品牌）· 維明顧問（評估中）
- **4-tenant 架構**：每家客戶擁有獨立的 CRM / 組織 / 稽核日誌

詳見 [PROJECT_BRIEF.md](./PROJECT_BRIEF.md)。

---

## 📁 專案結構

```
lingce-company/
├── README.md                    ← 本檔（終端使用者入口）
├── PROJECT_BRIEF.md             ← AI 評審首讀 briefing
├── CLAUDE.md                    ← 架構說明 + 多租戶路由
│
├── index.html                   ← 對外官網
├── dashboard.html               ← 老闆儀表板（SPA）
├── 啟動凌策.bat                   ← Windows 一鍵啟動
│
├── src/backend/                 ← Flask API
│   ├── server.py                     主入口
│   ├── tenant_context.py             多租戶調度
│   ├── {attendance,crm,chat,...}_manager.py
│   ├── acceptance_scenarios.py       驗收中心 AI 能力
│   ├── pii_guard.py                  PII 9 類偵測
│   └── pdf_export.py                 報告 PDF
│
├── data/<tenant>/               ← 每 tenant 獨立資料
│   ├── lingce/  (1 人 + 10 AI)
│   ├── microjet/ (134 人)
│   ├── addwii/   (6 人)
│   └── weiming/  (評估中)
│
├── chat_logs/                   ← operator-level 稽核（全系統共用）
│   ├── pii_audit.jsonl
│   ├── human_gate.jsonl
│   ├── acceptance_audit.jsonl
│   └── chroma_kb/                    RAG 向量庫
│
├── scripts/                     ← migration / 一次性腳本
├── docs/                        ← 其他技術文件
├── tests/                       ← 單元測試
└── legacy/                      ← 早期原型（已不使用，僅保留追溯）
```

---

## 🛡️ 合規設計（addwii 構面 5）

| 控制項 | 機制 |
|---|---|
| **C1** 個資不外流 | `CLAUDE_API_DISABLED=True` · 本地 Ollama |
| **C2** PII 自動遮蔽 | `pii_guard.py` 9 類偵測（ID / 電話 / Email / 地址 …）|
| **C3** 稽核日誌 | append-only JSONL · 不可刪改 |
| **C4** 人工審核閘 | 破壞性 / 匯出操作 → 必填理由 + 二次確認 |

前往儀表板「🛡️ 合規中心 → 🏛️ 信任鏈總覽」即可看到即時證據。

---

## 🎖️ 標語

> **別人做 AI 助手；我們做 AI 公司。**
