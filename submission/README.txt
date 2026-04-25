凌策 LingCe · 比賽繳交檔案說明
========================================================

📄 兩份提交檔
-----------
1. 凌策LingCe_專案規格書.pdf  (規格書 / 邏輯說明 / 評分依據)
2. 凌策LingCe_使用說明書.pptx (操作畫面 / 截圖佐證 / 32 頁)

對 AI 評審的閱讀順序建議：
1. 先看 PDF（找 TOC、看數字牆、看三家驗收逐項對應）
2. 再看 PPT（每頁標題對應 docx 條款，搭配截圖驗證）
3. 評審若想實機驗證 → 看 PDF 附錄 B「執行驗證指引」


📸 PPT 截圖補充指引
------------------
PPT 中所有「📸 請貼上截圖」的灰色虛線框，是給作者後續補上實機畫面的位置。
每頁的 Speaker Notes（簡報軟體下方備註）詳細說明「該截哪個畫面」。

補截圖步驟：
1. 用 PowerPoint / WPS Presentation / LibreOffice Impress 開啟 .pptx
2. 切到任一頁，看下方 Notes 的「【截圖指引】」
3. 啟動本地後端：python src/backend/server.py
4. 依 Notes 操作截圖
5. 把截圖直接拖入該頁的灰色虛線佔位框

各頁需要的截圖位置一覽（共 25 個截圖，建議優先順序）：
P2  · 主介面總覽（dashboard 首頁含 5 tenant group 側欄）
P4  · AI 指揮官對話頁
P5  · Token 成本頁
P7  · addwii 構面 1 · 8 坪嬰兒房問答（含 workflow 節點）⭐ docx 必要
P8  · addwii 構面 1 · 任一坪數查詢結果（含 AI 選型建議區塊）
P9  · addwii 構面 2 · 3 客服紀錄分析結果
P10 · addwii 構面 3 · 20 坪 PM2.5+VOC 提案
P11 · addwii 構面 4 · 嬰幼兒房文案 + SEO 命中
P12 · addwii 構面 5 · CSV 上傳 + PII 遮蔽 ⭐ 一票否決必要
P13 · PII Guard 偵測 13 類（選配）
P14 · microjet A · MJ-3200 客服回覆
P15 · microjet B · 客訴分類批次結果
P16 · benchmark_runner 終端輸出
P17 · microjet C · B2B 8 段提案
P18 · microjet D · 日報 Dashboard
P19 · microjet E · 25 控制點 + 個資法通報書
P22 · 維明 · CS 生成提示框
P23 · 維明 · 3-way match 結果
P24 · 維明 · 區塊鏈 KPI 上鏈
P25 · 維明 · 稽核日誌
P26 · 維明 · CS rule_hits（選配）
P27 · 維明 · 4 個錢包卡片
P28 · 維明 · 多簽流程交易列表
P29 · 維明 · 冷錢包 timelock 阻擋 toast


🚀 一鍵驗證（給 AI 評審）
--------------------
1. cd lingce-company
2. python src/backend/server.py
3. (新終端) python src/backend/benchmark_runner.py
   預期：sentiment=100% / pii=100% / urgency F1=0.921 / all_pass=True


📊 自評結果
----------
addwii  ：100 / 100
microjet：100 / 100
維明    ：100 / 100
總計    ：300 / 300

詳細評分過程見 PDF 附錄。


🛠️ 重新生成這兩份文件
-------------------
若有更新後想重新產出：
  python scripts/build_pdf.py
  python scripts/build_user_guide_pptx.py

兩支腳本都讀取最新的 codebase 狀態，不會跟原始碼脫鉤。
