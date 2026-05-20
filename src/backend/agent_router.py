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
def respond(chat_id: str, user_text: str, user_name: str = 'guest') -> dict:
    """處理一則使用者訊息 · 自動跑 multi-agent 流程

    流程：
      1. 載入對話 thread
      2. 取當前 Agent（預設 bd）
      3. 用 ai_backend.generate_with_tools 跑 tool-use 迴圈
      4. 若 LLM 呼叫了 handoff_to_agent → 換 Agent 再跑一輪
      5. 寫入 thread + trace
    """
    import ai_backend
    import agent_tools

    conv = load_conversation(chat_id)
    conv['messages'].append({
        'role':      'user',
        'content':   user_text,
        'user_name': user_name,
        'ts':        datetime.now().isoformat(timespec='seconds'),
    })

    current_agent = conv.get('current_agent', 'bd')
    all_tool_calls = []
    handoffs = []
    final_text = ''
    max_handoffs = 3
    handoff_count = 0

    # 構建對話歷史（給 LLM 看）
    history = '\n'.join(
        f'{m["role"]}: {m["content"]}'
        for m in conv['messages'][-10:]   # 最近 10 輪
    )

    while handoff_count <= max_handoffs:
        system = AGENT_PROMPTS.get(current_agent, AGENT_PROMPTS['bd'])
        tools = agent_tools.list_tools_for_llm('anthropic')

        r = ai_backend.generate_with_tools(
            prompt=f'對話歷史：\n{history}\n\n顧客最新訊息：{user_text}',
            system=system,
            tools=tools,
            max_tokens=1500,
            temperature=0.2,
            max_iters=5,
            agent_id=current_agent,
        )
        all_tool_calls.extend(r.get('tool_calls', []))
        final_text = r.get('final_text', '')

        # 偵測 LLM 在 tool_calls 裡有沒有呼叫 handoff_to_agent
        handoff_call = next(
            (tc for tc in r.get('tool_calls', []) if tc.get('tool') == 'handoff_to_agent'),
            None,
        )
        if handoff_call:
            target = handoff_call['input'].get('target_agent', 'bd')
            reason = handoff_call['input'].get('reason', '')
            summary = handoff_call['input'].get('context_summary', '')
            handoffs.append({
                'from':    current_agent,
                'to':      target,
                'reason':  reason,
                'summary': summary,
            })
            _log_handoff(chat_id, current_agent, target, summary, reason)
            current_agent = target
            handoff_count += 1
            # 更新 history 給下一個 Agent 看
            history += f'\n[Handoff: {handoffs[-1]["from"]} → {target}] {summary} (因：{reason})'
            continue

        break  # 沒 handoff，迴圈結束

    # 寫回 thread
    conv['current_agent'] = current_agent
    conv['messages'].append({
        'role':            'assistant',
        'agent':           current_agent,
        'content':         final_text,
        'ts':              datetime.now().isoformat(timespec='seconds'),
        'tool_calls':      all_tool_calls,
        'handoffs':        handoffs,
        'backend':         r.get('backend'),
        'model':           r.get('model'),
        'iterations':      r.get('iterations'),
    })
    conv['agent_trace'].append({
        'ts':           datetime.now().isoformat(timespec='seconds'),
        'agent_chain':  ['bd'] + [h['to'] for h in handoffs],
        'tool_count':   len(all_tool_calls),
        'tools_used':   [tc['tool'] for tc in all_tool_calls],
    })
    save_conversation(conv)

    return {
        'chat_id':        chat_id,
        'reply':          final_text,
        'final_agent':    current_agent,
        'agent_chain':    ['bd'] + [h['to'] for h in handoffs],
        'tool_calls':     all_tool_calls,
        'handoffs':       handoffs,
        'backend':        r.get('backend'),
        'model':          r.get('model'),
        'iterations':     r.get('iterations'),
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
