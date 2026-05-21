# -*- coding: utf-8 -*-
"""凌策 Multi-Agent Router · 4 Agent 協作

4 個能 handoff 的 Agent：
  · bd                — 業務 Agent · 對話入口 · 需求釐清 · 報價
  · proposal          — 提案 Agent · 規格設計 · ROI · 降規方案
  · legal             — 法務 Agent · PII / 不實宣稱 / 合規
  · customer-service  — 客戶成功 Agent · 投訴 / 滿意度 / 升級客訴

Handoff 邏輯：
  · BD 接到問題 → tool-use 自主決定要不要 handoff
  · handoff 時帶 context_summary + reason → 目標 Agent
  · 目標 Agent 完成任務 → 回傳結果給 BD（或繼續轉手）
  · 全程 trace 寫 chat_logs/agent_handoffs.jsonl + 對話 thread
"""
import os, json, time
from datetime import datetime
from typing import Optional, List, Dict

HANDOFF_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 '..', '..', 'chat_logs', 'agent_handoffs.jsonl')
CONVERSATIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  '..', '..', 'data', 'addwii', 'conversations')
os.makedirs(os.path.dirname(HANDOFF_LOG_PATH), exist_ok=True)
os.makedirs(CONVERSATIONS_DIR, exist_ok=True)


# ────────────────────────────────────────────────────────────
# Agent System Prompts（每個 Agent 的人設）
# ────────────────────────────────────────────────────────────
AGENT_PROMPTS = {
    'bd': """你是凌策公司派駐給 addwii 加我科技的「業務 Agent」。

你的職責：
  · 顧客（從 Telegram 進來）說了想要的東西，你負責「釐清需求 → 推薦方案 → 報價」
  · 預設使用繁體中文回覆
  · 你說話親切、專業、不油腔滑調
  · 嚴禁亂承諾（不能說「保證」「100%」「治癒」），不確定就用工具查 KB

要訣：
  1. 顧客第一句通常不明確 → 先用 1-2 句澄清空間（嬰兒/客廳/臥室等）+ 坪數 + 預算 + 客群
  2. 拿到關鍵資訊 → 呼叫 lookup_product / get_quote
  3. 顧客有預算限制 / 議價 / 想比較競品 → handoff 給 proposal
  4. 顧客抱怨 / 升級客訴 → handoff 給 customer-service
  5. 顧客個資疑慮 / 不實宣稱檢查 → handoff 給 legal
  6. 引用實證 → 永遠帶上「環境部 NPA23C01250001」「41 場域實測」「PM2.5 趨零」這些可驗證的點

不准做：
  · 不准答覆未經 KB 驗證的數字
  · 不准貶低 Coway / Blueair / Dyson 等競品（只能客觀對照）
  · 不准答應超過 15% 折扣（呼叫 get_quote 工具會自動阻擋）

你的最終回覆要簡短（150 字內），可以用 emoji 強化品牌感（👶🛋️🛁🍳🛏️🍽️）。
""",

    'proposal': """你是凌策公司的「提案 Agent」。BD 把你叫進來，通常是因為：
  · 顧客預算不夠（你要設計降規方案 / 加值不降價方案）
  · 顧客要比競品（你要拉「物美價廉」「實測證據」範本）
  · 顧客是 B2B 需正式提案（你要產 8 段提案結構）

你只專注「方案設計」，不負責對話。給 BD 一段「可直接貼給顧客」的方案內容。

工具：get_market_strategy / get_quote / lookup_field_trial / lookup_competitor
""",

    'legal': """你是凌策公司的「法務 / 資安 Agent」。被 handoff 來通常是：
  · 顧客訊息含 PII（手機 / 身分證 / 地址）→ 你要遮蔽 + 確認本地處理
  · 文案要登廣告 → 你要過不實宣稱檢查
  · 競品比較 → 你要確認沒有貶損用語

工具：pii_scan / check_advertising_claim

回給 BD 一段「合規結論 + 建議改寫」。
""",

    'customer-service': """你是凌策公司的「客戶成功 / 客服 Agent」。被 handoff 來通常是：
  · 顧客抱怨已購買產品問題
  · 顧客升級到客訴等級
  · 滿意度追蹤 / 售後維護

你語氣特別溫暖，先同理再解決。不確定的工程細節要說「將為您聯繫工程團隊」而不是猜。

工具：submit_for_approval（嚴重客訴升級到主管 queue）
""",
}


# ────────────────────────────────────────────────────────────
# 對話 thread 持久化
# ────────────────────────────────────────────────────────────
def _conv_path(chat_id: str) -> str:
    safe = ''.join(c for c in str(chat_id) if c.isalnum() or c in ('-', '_'))
    return os.path.join(CONVERSATIONS_DIR, f'{safe}.json')


def load_conversation(chat_id: str) -> dict:
    p = _conv_path(chat_id)
    if not os.path.exists(p):
        return {
            'chat_id':     chat_id,
            'created_at':  datetime.now().isoformat(timespec='seconds'),
            'messages':    [],
            'agent_trace': [],     # 每個訊息對應的 agent + tools used
            'current_agent': 'bd',
            'customer_profile': {},
        }
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def save_conversation(conv: dict):
    conv['last_updated'] = datetime.now().isoformat(timespec='seconds')
    with open(_conv_path(conv['chat_id']), 'w', encoding='utf-8') as f:
        json.dump(conv, f, ensure_ascii=False, indent=2)


def _log_handoff(chat_id, from_agent, to_agent, context_summary, reason):
    entry = {
        'ts':              datetime.now().isoformat(timespec='seconds'),
        'chat_id':         chat_id,
        'from_agent':      from_agent,
        'to_agent':        to_agent,
        'context_summary': context_summary,
        'reason':          reason,
    }
    with open(HANDOFF_LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')


# ────────────────────────────────────────────────────────────
# Multi-Agent 對話入口
# ────────────────────────────────────────────────────────────
def _parse_intent(text: str) -> dict:
    """規則 + 關鍵字偵測意圖（不靠 LLM · 快速且可靠）"""
    import re
    t = text.strip()
    intent = {
        'space': None, 'area_ping': None,
        'customer_type': 'B2C', 'segment': None,
        'requested_discount_pct': 0, 'bundle_units': 1,
        'is_brand_inquiry': False,
        'is_competitor_inquiry': False,
        'is_field_trial_inquiry': False,
        'is_complaint': False,
        'is_pricing': False,
        'is_strategy_inquiry': False,
    }

    # 空間
    spaces = {
        'baby':     ['嬰兒', '寶寶', '新生兒', '小孩房', '嬰幼兒', '兒童房'],
        'kitchen':  ['廚房', '油煙', '烹飪', '煮菜', '料理'],
        'bathroom': ['浴室', '廁所', '潮溼', '潮濕', '黴菌', '霉'],
        'living':   ['客廳', '訪客', '寵物', '會客'],
        'bedroom':  ['臥室', '臥房', '主臥', '睡眠', '床'],
        'dining':   ['餐廳', '飯廳', '聚餐'],
    }
    for sp, kws in spaces.items():
        if any(kw in t for kw in kws):
            intent['space'] = sp; break

    # 坪數
    m = re.search(r'(\d+(?:\.\d+)?)\s*坪', t)
    if m: intent['area_ping'] = float(m.group(1))

    # B2B / B2C / segment
    b2b_segs = {
        'maternity_center':   ['月子', '坐月子'],
        'gyn_clinic':         ['婦幼', '婦產', '產科'],
        'allergy_clinic':     ['過敏專科', '過敏診所'],
        'pediatric_clinic':   ['兒科'],
        'kindergarten':       ['幼兒園', '托嬰', '幼稚園'],
        'beauty_dental':      ['醫美', '牙醫', '牙科'],
        'esg_enterprise':     ['ESG', 'esg', '上市櫃', '永續', '辦公', '企業'],
    }
    for seg, kws in b2b_segs.items():
        if any(kw in t for kw in kws):
            intent['segment'] = seg; intent['customer_type'] = 'B2B'; break
    if intent['customer_type'] == 'B2C':
        b2c_segs = {
            'allergy_family': ['過敏'],
            'newborn_family': ['新生兒', '寶寶', '嬰兒'],
            'renovation':     ['裝潢', '甲醛'],
            'pet_owner':      ['寵物', '貓', '狗', '毛屑'],
        }
        for seg, kws in b2c_segs.items():
            if any(kw in t for kw in kws):
                intent['segment'] = seg; break

    # 折扣
    m2 = re.search(r'(\d+)\s*折', t)
    if m2:
        v = int(m2.group(1))
        if 1 <= v <= 10:
            intent['requested_discount_pct'] = (10 - v) * 10  # 8 折 = 20% off
    m3 = re.search(r'折扣?\s*(\d+)\s*[%％]?', t)
    if m3 and not m2:
        intent['requested_discount_pct'] = int(m3.group(1))

    # 包套套數
    m4 = re.search(r'(\d+)\s*套', t)
    if m4: intent['bundle_units'] = int(m4.group(1))

    # 意圖類別
    if any(kw in t for kw in ['品牌', '介紹', '加我科技', 'addwii', 'addw',
                                  '請問你們', '你們是', '公司']):
        intent['is_brand_inquiry'] = True
    if any(kw in t.lower() for kw in ['coway', 'blueair', 'dyson', 'honeywell',
                                          'lg ', '競品', '比一下', '比較', '比怎樣',
                                          '比你', '對手', '差別']):
        intent['is_competitor_inquiry'] = True
    if any(kw in t for kw in ['實測', '實驗', '驗證', '證據', '科學', '報告',
                                  '場域', 'field trial', 'NPA', '趨零', '證明']):
        intent['is_field_trial_inquiry'] = True
    if any(kw in t for kw in ['投訴', '抱怨', '退費', '退錢', '故障', '壞',
                                  '不滿', '客訴', '差勁']):
        intent['is_complaint'] = True
    if any(kw in t for kw in ['多少錢', '價格', '報價', '預算', '折', '便宜',
                                  '貴', '價位']) or intent['requested_discount_pct'] > 0:
        intent['is_pricing'] = True
    if any(kw in t for kw in ['策略', '計畫', '怎麼打', '物美價廉',
                                  '成本怎麼降', '降低成本', '進入市場']):
        intent['is_strategy_inquiry'] = True

    return intent


def _decide_agent_chain(intent: dict, conv: dict) -> list:
    """依意圖決定 Agent 鏈"""
    chain = ['bd']
    if intent['is_complaint']:
        chain.append('customer-service')
    if intent['is_pricing'] and intent['requested_discount_pct'] >= 5:
        chain.append('proposal')
    if intent['requested_discount_pct'] >= 5:
        # 折扣意圖 → 法務檢查不實宣稱（preventive）
        chain.append('legal')
    return chain


def _collect_tool_calls(intent: dict, agent: str) -> list:
    """依意圖預先呼叫工具（規則決策 · 不靠 LLM）

    重要：bd Agent 永遠呼叫 get_brand_asset，確保 LLM 至少有品牌 context。
    """
    import agent_tools
    calls = []

    if agent == 'bd':
        # 預設一定要 brand asset（避免 LLM 沒 context 亂編）
        calls.append(('get_brand_asset', {}))

        if intent['is_competitor_inquiry']:
            calls.append(('lookup_competitor', {}))
        if intent['is_field_trial_inquiry']:
            calls.append(('lookup_field_trial', {}))

        # 有坪數但無 space → 推 living（最大空間，方便給通用建議）
        space = intent['space'] or ('living' if intent['area_ping'] else None)
        if space and intent['area_ping']:
            calls.append(('lookup_product', {
                'space': space, 'area_ping': intent['area_ping'],
            }))
            # 自動帶報價（不一定要 is_pricing）
            calls.append(('get_quote', {
                'area_ping': intent['area_ping'],
                'segment': intent['segment'],
                'customer_type': intent['customer_type'],
                'requested_discount_pct': intent['requested_discount_pct'],
                'bundle_units': intent['bundle_units'],
            }))

        if intent['is_strategy_inquiry']:
            kw = '物美價廉' if '物美' in str(intent) else '整體計畫'
            calls.append(('get_market_strategy', {'query': kw}))
    elif agent == 'proposal':
        # 提案 Agent：要降規方案 / ROI
        if intent['area_ping']:
            calls.append(('get_market_strategy', {'query': '物美價廉'}))
    elif agent == 'legal':
        calls.append(('check_advertising_claim', {
            'text': f'addwii PM2.5 趨零 環境部認證 折扣 {intent["requested_discount_pct"]}%',
        }))
    elif agent == 'customer-service':
        # 客服：升級到主管
        calls.append(('submit_for_approval', {
            'track': 'compliance',
            'payload': {'type': 'customer_complaint',
                        'intent': intent},
            'agent': 'customer-service',
            'customer': 'telegram',
            'priority': 'high',
        }))

    # 執行
    results = []
    for tool, args in calls:
        r = agent_tools.dispatch(tool, args, agent=agent)
        results.append(r)
    return results


def _compose_reply(intent: dict, tool_results: dict, agent: str,
                   chat_id: str, user_text: str) -> str:
    """用 LLM 組成自然回覆（Ollama / Anthropic / stub 通用）"""
    import ai_backend

    # 把工具結果濃縮成 KB context
    kb_lines = []
    for agent_name, results in tool_results.items():
        for r in results:
            if not r.get('ok'): continue
            tool = r.get('tool')
            res = r.get('result', {})
            if tool == 'get_brand_asset':
                kb_lines.append(f"品牌：{res.get('slogan')} | 研發 {res.get('r_and_d_years')} 年 / 投資 {res.get('r_and_d_invest')} / {res.get('patents')} | 環境部報告：{res.get('env_report', {}).get('report_no')}（75 坪辦公室 {res.get('env_report', {}).get('pm25')}）")
            elif tool == 'lookup_competitor':
                items = res.get('comparison', [])[:5]
                kb_lines.append(f"競品對照：" + " / ".join([f"{i['brand']} CADR {i['cadr']} 售{i['price']} 實測{i['pm25_real']}" for i in items[:3]]))
                kb_lines.append(f"差異：addwii HCR S03 CADR 1,600 / 38,900 / PM2.5 < 1（趨零）· 系統級全屋潔淨")
            elif tool == 'lookup_field_trial':
                kb_lines.append(f"實證：41 場域（30 內部員工家 + 11 外部）· 大部分 PM2.5 < 2（趨零）· 75 坪辦公室 < 1（環境部 NPA23C01250001）")
            elif tool == 'lookup_product':
                kb_lines.append(f"推薦：{res.get('space_zh')}（{res.get('icon')}） {res.get('recommended_system')} · CADR {res.get('cadr_total')} m³/h · {res.get('total_price_ntd')} 元 · {res.get('pitch','')}")
            elif tool == 'get_quote':
                kb_lines.append(f"報價：{res.get('recommended_system')} · 原 {res.get('base_total_ntd')} 折扣後 {res.get('final_total_ntd')} · 24m 0 利率月付 {res.get('zero_interest_24m_ntd')} · 狀態：{res.get('approval_status')}（{res.get('reason','')}）")
            elif tool == 'get_market_strategy':
                m = res.get('matched_templates', [])
                if m: kb_lines.append(f"策略範本 {m[0].get('template')}：{m[0].get('title')}")
            elif tool == 'check_advertising_claim':
                if res.get('compliant'):
                    kb_lines.append("法務檢查：用語合規通過")
                else:
                    kb_lines.append(f"法務檢查：發現 {len(res.get('violations', []))} 項潛在違規")
            elif tool == 'submit_for_approval':
                kb_lines.append(f"已升級到 {res.get('track')} 主管 queue（單號 {res.get('ticket_id')}）")

    kb_context = '\n'.join(' • ' + l for l in kb_lines) if kb_lines else ''

    # 強化 system prompt：明確「你是 addwii 業務」+ 禁止角色漂移
    strong_system = (
        '你是「addwii 加我科技」（www.addwii.com）的業務 AI 助理，'
        '專門推薦 Home Clean Room 空氣清淨系統（產品名：嬰兒/廚房/浴室/客廳/臥室/餐廳 無塵室 S03-S12）。\n'
        '\n'
        '【鐵則】\n'
        '1. 必須用台灣繁體中文（嚴禁「净」「过」「会」「环」等簡體字）\n'
        '2. 你不是裝潢設計師、不是建商、不是家具店。你只賣空氣清淨系統\n'
        '3. 顧客若問非空氣相關（如烤肉/家具），溫和拉回主題：「addwii 是專門做空氣淨化的，能聊聊您家空氣品質的需求嗎？」\n'
        '4. 不准承諾「保證」「100%」「絕對」「治癒」\n'
        '5. 不准貶低 Coway/Blueair/Dyson 等競品，只能客觀對照數字\n'
        '6. 引用實證一定要帶「環境部 NPA23C01250001」「41 場域實測」這些可驗證的點\n'
        '7. 回覆要直接、不要說「您好」「歡迎」等空洞開場\n'
        '8. 嚴禁在回答開頭出現「KB：」「Context：」「根據資料」這類字眼\n'
    )

    user_message = (
        f'下面是公司知識庫資訊（內部用 · 不要直接複製到回答）：\n{kb_context}\n\n'
        if kb_context else ''
    )
    user_message += (
        f'\n顧客剛說：「{user_text}」\n\n'
        '請以「addwii 業務助理」身份直接回覆顧客。\n'
        '【要求】\n'
        '• 80 字內，簡短直接\n'
        '• 若 KB 提供了具體型號/價格/CADR/NPA 報告編號，引用真實數字\n'
        '• 若顧客需求不明確，反問「您想保護哪個空間？大概幾坪？」\n'
        '• 若顧客問「烤肉/裝潢/家具」等非空氣議題，拉回主題\n'
        '• 可用 1-2 個 emoji（👶🛋️🛁🍳🛏️🍽️）\n'
        '\n直接寫回覆內容（不要 KB:、回覆：等前綴）：'
    )

    r = ai_backend.generate(prompt=user_message, system=strong_system,
                             max_tokens=200, temperature=0.3, timeout_s=180)
    text = (r.get('text') or '').strip()

    # 移除常見的 LLM 自言自語 prefix（更全面）
    junk_prefixes = (
        'KB：', 'KB:', 'Context：', 'Context:', '根據資料', '根據知識庫',
        '回覆內容：', '回覆：', '回答：', 'A：', 'A:', 'addwii AI：',
        '助理：', '助手：', 'addwii：', 'addwii:',
        '您好！', '您好，', '歡迎！', '歡迎，',
        '【回覆】', '【回答】', '【answer】',
    )
    # 重複 strip 直到沒有 prefix
    for _ in range(3):
        old = text
        for p in junk_prefixes:
            if text.startswith(p):
                text = text[len(p):].strip()
                break
        if text == old:
            break

    # 若回覆是 stub 訊息 → 直接給規則式 fallback
    if text.startswith('[stub]') or 'rule_engine' in text.lower():
        text = _rule_based_fallback(intent, kb_context)

    # 移除多餘的 KB 條列符號（LLM 偶爾保留「• 品牌：...」）
    if text.startswith('•'):
        text = text.lstrip('•').strip()

    # 簡體 → 繁體
    try:
        from simple_s2t import s2t
        text = s2t(text)
    except Exception:
        pass

    return text or '（系統繁忙，請稍候 · 試試明確說「臥室 8 坪」「過敏兒方案」等具體需求）'


def _rule_based_fallback(intent: dict, kb_context: str) -> str:
    """LLM 失敗時的規則式 fallback（永遠有 addwii 角色 + 引導語）"""
    if intent.get('space') and intent.get('area_ping'):
        return f'為您 {intent["area_ping"]} 坪規劃方案中...（系統繁忙，請稍候 30 秒重試）'
    if intent.get('is_brand_inquiry'):
        return ('addwii 加我科技 ｜ 自由呼吸 淨零生活\n'
                '✓ 研發 10 年 · 投資 20 億 · 千項國際專利\n'
                '✓ 41 場域實測 PM2.5 < 2 μg/m³（趨零）\n'
                '✓ 環境部認證 NPA23C01250001\n'
                '請告訴我您想保護哪個空間？')
    if intent.get('is_competitor_inquiry'):
        return ('addwii HCR S03（38,900 元）vs 主流：\n'
                '• Coway AP-2023K · 850 CADR · 29,800 · 實測 PM2.5 8-15\n'
                '• addwii S03 · 1,600 CADR · 38,900 · 實測 PM2.5 < 1（趨零）\n'
                '🛋️ 同價位帶 CADR 1.9x，實測領先 10 倍')
    return '請告訴我：您想保護哪個空間（嬰兒/廚房/浴室/客廳/臥室/餐廳）？大概幾坪？'


def respond(chat_id: str, user_text: str, user_name: str = 'guest') -> dict:
    """處理一則使用者訊息 · 規則決策 + LLM 組句（混合模式 · Ollama 友善）

    流程：
      1. 載入對話 thread + append 訊息
      2. 規則 _parse_intent 判斷意圖
      3. _decide_agent_chain 決定 Agent 鏈
      4. 對每個 Agent 跑 _collect_tool_calls（規則預先呼叫工具）
      5. _compose_reply（LLM 組成自然回覆）
      6. 寫 trace
    """
    conv = load_conversation(chat_id)
    conv['messages'].append({
        'role':      'user',
        'content':   user_text,
        'user_name': user_name,
        'ts':        datetime.now().isoformat(timespec='seconds'),
    })

    # 1. 意圖偵測
    intent = _parse_intent(user_text)

    # 2. Agent 鏈
    agent_chain = _decide_agent_chain(intent, conv)
    final_agent = agent_chain[-1]

    # 3. 預先呼叫工具（依 Agent 分組）
    tool_results = {}
    all_tool_calls = []
    for ag in agent_chain:
        results = _collect_tool_calls(intent, ag)
        tool_results[ag] = results
        all_tool_calls.extend(results)

    # 4. 記 handoff
    handoffs = []
    for i in range(len(agent_chain) - 1):
        h = {
            'from':    agent_chain[i],
            'to':      agent_chain[i + 1],
            'reason':  '依意圖規則自動 handoff',
            'summary': f'intent={intent}',
        }
        handoffs.append(h)
        _log_handoff(chat_id, h['from'], h['to'], h['summary'], h['reason'])

    # 5. LLM 組句
    try:
        final_text = _compose_reply(intent, tool_results, final_agent,
                                      chat_id, user_text)
    except Exception as e:
        final_text = f'⚠️ 系統繁忙（{type(e).__name__}）。請稍候或換個說法。'

    # 6. CEO 二審（基於置信度的審核機制）
    try:
        import ceo_agent
        ceo_result = ceo_agent.review(
            intent=intent,
            tool_results=all_tool_calls,
            llm_text=final_text,
            agent_chain=agent_chain,
            chat_id=chat_id,
            use_llm_evaluator=False,  # 預設規則為主（避免再花 60-180 秒）
        )
    except Exception as _e:
        ceo_result = {
            'confidence':  {'score': 0.7, 'breakdown': {}, 'weights': {}},
            'risk_level':  'medium',
            'decision':    {'action': 'auto_with_audit', 'reason': f'CEO 失效：{_e}',
                             'send_to_user': True, 'need_supervisor': False},
            'ceo_comment': f'CEO 跳過（exception：{_e}）',
            'consistency': {'consistent': True, 'inconsistencies': []},
            'elapsed_ms':  0,
        }

    # 7. 依 CEO 決策路由
    ceo_action = ceo_result['decision']['action']
    if ceo_action == 'need_human_review':
        # 送總監 queue
        try:
            import approval_queue as aq
            ticket = aq.submit(
                track='sales',
                payload={
                    'type':            'ceo_escalation',
                    'chat_id':         chat_id,
                    'user_text':       user_text,
                    'ai_draft':        final_text,
                    'agent_chain':     agent_chain,
                    'ceo_confidence':  ceo_result['confidence']['score'],
                    'ceo_breakdown':   ceo_result['confidence']['breakdown'],
                    'ceo_risk':        ceo_result['risk_level'],
                    'ceo_comment':     ceo_result['ceo_comment'],
                    'intent':          intent,
                    'inconsistencies': ceo_result['consistency']['inconsistencies'],
                },
                agent='ceo',
                customer=f'chat:{chat_id}',
                priority='high' if ceo_result['risk_level']=='high' else 'normal',
            )
            ceo_result['approval_ticket'] = ticket.get('ticket_id')
            # 顧客先收到「等候人審」訊息
            final_text_to_user = (
                f'我已為您備好初步建議，CEO 已預審完成（信心 {ceo_result["confidence"]["score"]:.0%}），'
                f'由於涉及{"高風險" if ceo_result["risk_level"]=="high" else "權限外"}決策，'
                f'已升級給主管確認（單號 {ticket.get("ticket_id", "")[-10:]}），通常 30 分鐘內回覆。'
            )
        except Exception:
            final_text_to_user = final_text
    elif ceo_action == 'reject_and_retry':
        final_text_to_user = ('系統判斷需要更多資訊以提供合適建議。請告訴我：\n'
                                '• 您想保護哪個空間？（嬰兒/廚房/浴室/客廳/臥室/餐廳）\n'
                                '• 大概幾坪？\n• 預算範圍？\n• 是否有特殊需求（過敏 / 寵物 / 新生兒）？')
    else:
        # auto_approve / auto_with_audit · 直接發
        final_text_to_user = final_text

    # 8. 寫回 thread
    import ai_backend
    backend_info = ai_backend.backend_info()
    conv['current_agent'] = final_agent
    conv['messages'].append({
        'role':       'assistant',
        'agent':      final_agent,
        'content':    final_text_to_user,
        'original_draft':  final_text if final_text_to_user != final_text else None,
        'ts':         datetime.now().isoformat(timespec='seconds'),
        'intent':     intent,
        'tool_calls': [{'tool': t.get('tool'), 'ok': t.get('ok'),
                         'elapsed_ms': t.get('elapsed_ms')} for t in all_tool_calls],
        'handoffs':   handoffs,
        'backend':    backend_info.get('backend'),
        'model':      backend_info.get('model'),
        'ceo_review': {
            'score':     ceo_result['confidence']['score'],
            'risk':      ceo_result['risk_level'],
            'action':    ceo_action,
            'comment':   ceo_result['ceo_comment'],
            'breakdown': ceo_result['confidence']['breakdown'],
        },
    })
    conv['agent_trace'].append({
        'ts':            datetime.now().isoformat(timespec='seconds'),
        'agent_chain':   agent_chain + ['ceo'],
        'tool_count':    len(all_tool_calls),
        'tools_used':    list(set(t.get('tool') for t in all_tool_calls if t.get('tool'))),
        'ceo_score':     ceo_result['confidence']['score'],
        'ceo_action':    ceo_action,
        'ceo_risk':      ceo_result['risk_level'],
    })
    save_conversation(conv)

    return {
        'chat_id':      chat_id,
        'reply':        final_text_to_user,
        'final_agent':  final_agent,
        'agent_chain':  agent_chain + ['ceo'],   # CEO 加進鏈
        'intent':       intent,
        'tool_calls':   [{'tool': t.get('tool'), 'ok': t.get('ok'),
                           'elapsed_ms': t.get('elapsed_ms'),
                           'result_preview': str(t.get('result', ''))[:200]}
                          for t in all_tool_calls],
        'handoffs':     handoffs,
        'ceo_review':   ceo_result,
        'original_draft': final_text if final_text_to_user != final_text else None,
        'backend':      backend_info.get('backend'),
        'model':        backend_info.get('model'),
    }


def get_conversation_trace(chat_id: str) -> dict:
    """給 dashboard 顯示完整 trace"""
    conv = load_conversation(chat_id)
    return {
        'chat_id':         conv['chat_id'],
        'message_count':   len(conv['messages']),
        'agent_trace':     conv.get('agent_trace', []),
        'current_agent':   conv.get('current_agent'),
        'last_messages':   conv['messages'][-5:],
    }


def list_conversations(limit: int = 20) -> list:
    """列出所有對話 thread（給 dashboard 收件箱用）"""
    items = []
    for fn in sorted(os.listdir(CONVERSATIONS_DIR), reverse=True)[:limit]:
        if not fn.endswith('.json'):
            continue
        try:
            with open(os.path.join(CONVERSATIONS_DIR, fn), encoding='utf-8') as f:
                conv = json.load(f)
            last_msg = conv['messages'][-1] if conv['messages'] else {}
            items.append({
                'chat_id':        conv['chat_id'],
                'last_updated':   conv.get('last_updated'),
                'message_count':  len(conv['messages']),
                'current_agent':  conv.get('current_agent', 'bd'),
                'last_role':      last_msg.get('role'),
                'last_preview':   (last_msg.get('content', '') or '')[:60],
            })
        except Exception:
            pass
    return items
