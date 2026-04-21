# 🔄 凌策專案 — 接續工作交接文件

> **給新環境上的自己 / Claude 的一份完整狀態快照**
> 讀完此文件 + 看一下 CLAUDE.md → 立刻可無縫接續開發

---

## 🎯 一分鐘理解此專案

**凌策公司 = 1 位人類老闆（你）+ 10 個 AI Agent 員工** 組成的新世代 IT 服務公司，參加「AI 領導人擂台大賽」。

- **沒有傳統員工** — 所有 BD / 客服 / 提案 / 前端 / 後端 / QA / 財務 / 法務 / 文件 都由 AI 扮演
- **透過 AI 指揮官** — 老闆用自然語言下指令，Orchestrator 自動分派
- **服務 3 家客戶**：
  - **microjet 微型噴射**（B2B 精密感測）— 134 人真實組織 Live
  - **addwii 加我科技**（B2C 場域無塵室）— 6 人真實組織 Live
  - **維明顧問**（評估中）— 商業模式討論中
- **驗收中心** = 依客戶老闆提供的驗收標準 `.docx` 對應之 AI 能力場景

---

## 📂 目前系統狀態（2026-04-18）

### 前端（`dashboard.html` ~6200 行）9 個頁面

| # | 頁面 | 狀態 |
|---|---|---|
| 1 | 📊 總覽儀表板 | ✅ 完成（1+10 定位 + 雙軌商業模式 + 3 客戶卡）|
| 2 | 🤖 AI Agent 管理 | ✅ 完成（1 位老闆 + 10 AI 組織圖） |
| 3 | 💼 **AI 模組商品** | ✅ 完成（14 模組 × 4 類 + 客戶採用矩陣 + 折扣）|
| 4 | 📋 **CRM 營運** | ✅ 完成（詢問→報價→訂單→安裝 完整流程） |
| 5 | 💰 Token 成本監控 | ✅ 完成（冷熱系統雙備援敘事） |
| 6 | 🏗️ 系統架構 | ✅ 完成（實際技術堆疊：Flask+Ollama+JSONL） |
| 7 | ⚡ AI 指揮官 | ✅ 完成（規則引擎秒回 + Ollama 選配深化） |
| 8 | 🎯 凌策客戶模擬器 | ✅ 完成（3 客戶 × 預設問題 + 自訂輸入；雙模式：具體問題走指揮官 / 導入類跑 8 階段 pipeline） |
| 9 | 🏢 組織出缺勤 | ✅ 完成（microjet+addwii 兩家分開呈現，140 人 Live） |
| 10 | 🏆 客戶驗收中心 | ✅ 完成（依 docx 6 場景 + AI Agent Workflow 視覺化） |

### 後端（`src/backend/`）

| 檔案 | 行數 | 功能 |
|---|---:|---|
| `server.py` | ~1400 | Flask 主程式 + 所有 API 路由 |
| `attendance_manager.py` | ~800 | 客戶組織 + 出缺勤狀態機 + HR 權限 |
| `chat_manager.py` | ~800 | 階級感知聊天 + 跨部門審批（含服務部門豁免） |
| `task_manager.py` | ~400 | 任務派工 + 審批 |
| `leave_overtime_manager.py` | ~550 | 請假多級審批鏈 + 職務代理人 + HR 出缺勤報表 |
| `members_data.py` | ~900 | 140 人客戶組織（microjet 134 + addwii 6 + 董事會 1） |
| `acceptance_scenarios.py` | ~500 | 驗收中心 6 大 AI 能力場景 |
| `crm_manager.py` | ~260 | **NEW** CRM 詢問→報價→訂單→安裝 SQLite |

### 資料檔

- `chat_logs/org_data.json` — 140 人組織樹（自動備份）
- `chat_logs/lingce_crm.db` — CRM SQLite 資料庫（第二波新增）
- `chat_logs/*.jsonl` — 聊天訊息、稽核記錄 (append-only)
- `chat_logs/tasks.json` `leaves.json` `overtimes.json` — 各模組狀態

---

## 🛠️ 完整依賴清單

### Python 套件（已安裝）
```bash
pip install flask flask-cors requests python-docx python-pptx
```

### 本機服務
```
Ollama (localhost:11434) + gemma4:e2b 模型
```

### 未來（第三波）需要新增
```bash
pip install chromadb sentence-transformers
# 然後下載 Qwen3.5 9B 或 Qwen2.5 7B (約 5~8 GB)
ollama pull qwen2.5:7b    # 建議
# 或用 LM Studio 載入 Qwen3.5-9B-Instruct Q4_K_M
```

---

## 🚀 新機器啟動流程

```bash
# 1. 安裝 Python 3.11+
# 2. 安裝 Ollama: https://ollama.com
# 3. 下載模型
ollama pull gemma4:e2b   # 現有（小、CPU 可跑）
ollama pull qwen2.5:7b   # 升級（要有 8GB+ VRAM）

# 4. 安裝 Python 套件
cd lingce-company
pip install flask flask-cors requests python-docx python-pptx
# 第三波新增：
pip install chromadb sentence-transformers

# 5. 啟動後端
python src/backend/server.py

# 6. 開啟瀏覽器
# → http://localhost:5000/dashboard.html
# → http://localhost:5000/index.html  (官網)
```

**重要環境變數**（選配）：
```bash
OLLAMA_URL=http://localhost:11434    # 預設就是這個
OLLAMA_MODEL=qwen2.5:7b              # 要升級時改這個
```

---

## 🎬 對話決策歷程（重要！）

以下是此專案從零到目前的**關鍵決策與轉折**，讓新環境的 Claude 能快速理解為何現在是這樣：

### 早期（系統基礎）
1. 建立 140 人客戶組織（microjet+addwii 共用董事會）
2. 出缺勤狀態機 + 階級聊天 + 跨部門審批
3. 任務派工 + 請假加班多級審批
4. HR 權限 + 稽核日誌

### 驗收中心演進
5. 依 `addwii_驗收評比標準_含測試題目v3.docx` 與 `microjet_驗收標準_v0.3_1.docx` 建立 6 大場景
6. 一開始用 SSE 串流呼叫 Ollama — **失敗**：Flask 開發伺服器會 buffer，前端卡住
7. 改為 KB bigram 倒排索引 + 規則引擎秒回，Ollama 改為選配
8. 發現 gemma4:e2b 在 CPU 上 **75 秒還產不出內容**，決定不依賴 AI，以規則為主
9. **重要教訓**：`localhost` 在 Windows 會解析到 `::1` (IPv6) 但 Flask 預設只監聽 IPv4 → 每個請求等 2 秒超時。**已修**：server 改監聽 `::` (dual-stack)

### 定位大轉換
10. 使用者指示：凌策 = **1 人老闆 + 10 AI Agent**，不是有員工的公司
11. 140 人是「客戶現場」，不是凌策內部 HR
12. 客戶驗收中心 = 依客戶老闆提供的 docx **生成的系統**，不是凌策自訂
13. 客戶模擬器 → 更名「凌策客戶模擬器」，支援預設 + 自訂問題
14. AI 指揮官整合驗收中心 — 自然語言自動路由到 6 大場景

### 完整對齊（13 項一次修完）
15. 移除虛假 Claude Opus / Palantir / vLLM / Qdrant / MCP 字樣
16. Token 成本頁改寫為真實三層（規則/Ollama/Claude 備援）
17. 系統架構頁改寫為實際堆疊（Flask + Ollama + JSONL）
18. 刪除 150 行死碼 `_OLD_SIM_SCENARIOS`

### 雙客戶分開呈現
19. 使用者指示：addwii 和 microjet 不要講共用董事長、分開展示
20. 總覽儀表板 3 張獨立客戶卡 + 組織頁 2 張獨立 banner

### 對方團隊文件吸收
21. 讀了 `MicroJet AI 客服系統開發技術文件v1.0` + `凌策系統開發文件.docx` + `凌策公司簡報.pptx` + `addwii_AI智能平台_開發文件v1.1初稿.docx`
22. 發現對方有**商品模組化思維**（14 個 AI 模組 × 定價）+ **雙軌商業模式**（凌策自用 ⟷ 客戶授權）+ **CRM 流程**（詢問→報價→訂單→安裝）+ **真 RAG**（ChromaDB + sentence-transformers + Qwen 9B）

### 三波吸收計畫
- **🥇 第一波（已完成）**：商業敘事升級 — 新增「AI 模組商品」頁 + 總覽雙軌商業模式 + Token 頁冷熱系統敘事
- **🥈 第二波（已完成）**：CRM 營運骨架 — SQLite + 4 張表 + 14 API + 前端 CRM 頁 + 官網詢價表單
- **🥉 第三波（待新機器）**：技術深度補強 — ChromaDB 真 RAG + Qwen 2.5 7B / Qwen 3.5 9B + addwii 房間洞察深化 + reportlab PDF 輸出

---

## 📋 第三波詳細執行清單（新機器上執行）

### 環境準備
```bash
# GPU 確認
nvidia-smi   # 應看到 GPU + VRAM
# 安裝套件
pip install chromadb sentence-transformers reportlab
# 下載大模型（選一）
ollama pull qwen2.5:7b           # 平衡選擇（4.7GB）
ollama pull qwen2.5:14b          # 若有 16GB+ VRAM
# 或用 LM Studio 載入 Qwen3.5-9B-Instruct Q4_K_M
```

### A. 將 bigram KB 升級為真 RAG
**目標檔**：`src/backend/acceptance_scenarios.py`

**改動**：
1. `_build_faq_index()` 改為初始化 ChromaDB：
   ```python
   import chromadb
   from chromadb.utils import embedding_functions
   ef = embedding_functions.SentenceTransformerEmbeddingFunction(
       model_name="paraphrase-multilingual-MiniLM-L12-v2")
   client = chromadb.PersistentClient(path="./chroma_kb")
   collection = client.get_or_create_collection("lingce_faq", embedding_function=ef)
   ```
2. `_qa_compute()` 改為向量查詢：
   ```python
   results = collection.query(query_texts=[question], n_results=3)
   ```
3. 把 addwii 10 FAQ + microjet 12 FAQ 以 `collection.upsert()` 寫入

### B. 切換大模型
**目標檔**：`src/backend/server.py`
```python
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'qwen2.5:7b')  # 改這行
```
並重新啟用 AI 指揮官的 Ollama 選配（若品質過關可取代規則引擎為預設）。

### C. 深化 addwii 感測器洞察
**目標檔**：`src/backend/acceptance_scenarios.py` 的 `analyze_all_csv()`

加入對方 addwii docx 的分析深度：
- Room vs Room 雷達圖（前端用 Chart.js 或 CSS）
- 清淨機開 vs 關的降低率（範例 Room 118 86.6%）
- 跨房間 CO2 排行
- 凌晨高峰時段分析

### D. PDF 提案輸出
新增 `src/backend/pdf_export.py` 用 reportlab：
- 報價單 PDF
- B2B 提案書 PDF（對應 microjet 驗收 C 場景）
- 出缺勤報表 PDF（HR 用）

### E. 把「AI 對話助理」還給指揮官
現在指揮官以規則為主，Qwen 9B 跑起來後可以恢復成「真的跟 AI 對話」感覺。

---

## 🎁 接續對話時給 Claude 的提示詞

複製下方整段給新環境的 Claude，祂立刻可以接續：

```
我要繼續一個正在進行中的專案。請先讀以下檔案：
1. HANDOFF.md  — 整個專案歷史與目前狀態
2. CLAUDE.md   — 專案定位與架構
3. dashboard.html 與 src/backend/ 程式碼

之後我們要執行「第三波」：ChromaDB 真 RAG + Qwen 2.5 7B + addwii 房間洞察深化 + reportlab PDF 輸出。

目前系統是一位人類老闆 + 10 AI Agent 的凌策公司，服務 addwii / microjet / 維明三家客戶。關鍵轉折與決策都在 HANDOFF.md 的「對話決策歷程」章節。

準備好後請先用一句話確認你理解此專案的定位，然後我們開始第三波。
```

---

## 🗃️ 需要連同專案一起帶走的外部檔案

```
1. C:\Users\B00325\Desktop\10CSVfile\           ← 10 個感測器 CSV
2. C:\Users\B00325\Desktop\addwii_驗收評比標準_含測試題目v3.docx
3. C:\Users\B00325\Desktop\microjet_驗收標準_v0.3_1.docx
4. C:\Users\B00325\AppData\Local\Temp\凌策系統開發文件.docx       ← 對方團隊參考
5. C:\Users\B00325\AppData\Local\Temp\凌策公司簡報.pptx            ← 對方團隊參考
6. C:\Users\B00325\Desktop\addwii_AI智能平台_開發文件v1.1初稿.docx  ← 對方團隊參考
7. MicroJet AI 客服系統開發技術文件  (對方團隊 txt/docx — 若有存檔)
```

建議在新機器上也把它們放相同相對位置，或在 `acceptance_scenarios.py` 的 `CSV_DIR` 改為新路徑。

---

## 🏁 新機器第一個 Smoke Test

```bash
# 進專案目錄
cd lingce-company

# 啟動後端（自動備份 org_data + 預熱 CSV + 預熱 Ollama）
python src/backend/server.py

# 另開一個 terminal 測試
curl http://localhost:5000/api/health
curl http://localhost:5000/api/crm/summary
curl http://localhost:5000/api/acceptance/kb-meta
```

全部 200 就代表接續成功，可直接進瀏覽器繼續開發。

---

*最後更新：2026-04-18*
*下次在新機器啟動 Claude 對話時，請先提供此文件。*
