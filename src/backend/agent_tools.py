# -*- coding: utf-8 -*-
"""凌策 Agent Tools · LLM Function Calling Schema + Dispatcher

定義 Agent 可呼叫的工具集。設計符合：
  · Anthropic tool_use 規範（claude-sonnet-4.x）
  · Ollama JSON-mode function calling（qwen2.5）
  · OpenAI function calling（備援）

每次 tool 呼叫都會：
  1. 寫入 conversation thread 的 trace
  2. append 到 chat_logs/agent_tool_calls.jsonl（稽核）
  3. 回傳 {result, elapsed_ms, agent_used}
"""
import os, json, time, traceback
from datetime import datetime
from typing import Callable, Dict, Any

# ────────────────────────────────────────────────────────────
# Tool Schema（Anthropic / OpenAI 通用格式）
# ────────────────────────────────────────────────────────────
TOOL_SCHEMAS = [
    {
        'name': 'lookup_product',
        'description': '依空間類型 + 坪數推薦 addwii Home Clean Room 方案（S03-S12）。空間可選 baby/kitchen/bathroom/living/bedroom/dining。',
        'input_schema': {
            'type': 'object',
            'properties': {
                'space':     {'type': 'string', 'enum': ['baby', 'kitchen', 'bathroom', 'living', 'bedroom', 'dining']},
                'area_ping': {'type': 'number', 'description': '坪數（1-30）'},
            },
            'required': ['space'],
        },
    },
    {
        'name': 'get_quote',
        'description': '完整報價：含設備、安裝、維護、稅、24m 0 利率分期。支援議價（B2B 12% / B2C 5% 上限；超 15% 拒絕）。',
        'input_schema': {
            'type': 'object',
            'properties': {
                'area_ping':              {'type': 'number'},
                'segment':                {'type': 'string', 'description': '客群代號（maternity_center / gyn_clinic / allergy_family ...）'},
                'customer_type':          {'type': 'string', 'enum': ['B2B', 'B2C']},
                'requested_discount_pct': {'type': 'number', 'description': '顧客要求折扣 %（0-30）'},
                'bundle_units':           {'type': 'integer', 'description': '整戶配置套數（>=3 觸發包套折扣）'},
                'seasonal_promo':         {'type': 'boolean', 'description': '是否套用節慶促銷（S03 限定）'},
            },
            'required': ['area_ping'],
        },
    },
    {
        'name': 'lookup_competitor',
        'description': '取得 addwii 與 5 大競品（Coway/Blueair/Dyson/Honeywell/LG）的 CADR / 價格 / 實測 PM2.5 對照。',
        'input_schema': {'type': 'object', 'properties': {}},
    },
    {
        'name': 'get_brand_asset',
        'description': '取得 addwii 品牌資產（口號、研發年數、專利、媒體背書、環境部報告編號 NPA23C01250001）。',
        'input_schema': {'type': 'object', 'properties': {}},
    },
    {
        'name': 'lookup_field_trial',
        'description': '取得 41 場域 Field Trial 實測結果（30 內部員工家 + 11 外部 · PM2.5 趨零 / 75 坪辦公室 ND<1）。',
        'input_schema': {'type': 'object', 'properties': {}},
    },
    {
        'name': 'get_market_strategy',
        'description': '依關鍵字取市場策略範本（A 整體計畫 / B 競爭力 / C 成本 / D 實測 / E 競品）。',
        'input_schema': {
            'type': 'object',
            'properties': {'query': {'type': 'string', 'description': '關鍵字（如「物美價廉」「成本怎麼降」「Coway 比怎樣」）'}},
            'required': ['query'],
        },
    },
    {
        'name': 'submit_for_approval',
        'description': '送進三軌人審 queue（sales/marketing/compliance）。折扣超權、行銷貼文、PII 命中時呼叫。',
        'input_schema': {
            'type': 'object',
            'properties': {
                'track':    {'type': 'string', 'enum': ['sales', 'marketing', 'compliance']},
                'payload':  {'type': 'object'},
                'agent':    {'type': 'string', 'description': '送審的 Agent 名稱'},
                'customer': {'type': 'string'},
                'priority': {'type': 'string', 'enum': ['high', 'normal', 'low']},
            },
            'required': ['track', 'payload'],
        },
    },
    {
        'name': 'handoff_to_agent',
        'description': '把當前對話轉交給另一個 Agent（4 個可選：bd / proposal / legal / customer-service）。需附 context summary。',
        'input_schema': {
            'type': 'object',
            'properties': {
                'target_agent':    {'type': 'string', 'enum': ['bd', 'proposal', 'legal', 'customer-service']},
                'context_summary': {'type': 'string', 'description': '當前對話的關鍵 context（200 字內）'},
                'reason':          {'type': 'string', 'description': '為何要 handoff（如「議價超權」「合規檢查」「報價超預算需降規」）'},
            },
            'required': ['target_agent', 'context_summary', 'reason'],
        },
    },
    {
        'name': 'pii_scan',
        'description': '掃描文字是否含 PII 13 類（手機/身分證/email/姓名/地址/銀行帳號/護照/健保卡/車牌/...）。回傳 hits + 遮蔽版。',
        'input_schema': {
            'type': 'object',
            'properties': {'text': {'type': 'string'}},
            'required': ['text'],
        },
    },
    {
        'name': 'check_advertising_claim',
        'description': '檢查文案是否含不實宣稱（如「100% 治癒」「保證根除」）或競品攻擊（如「Coway 是垃圾」）。回傳 violations + 建議改寫。',
        'input_schema': {
            'type': 'object',
            'properties': {'text': {'type': 'string'}},
            'required': ['text'],
        },
    },
]


# ────────────────────────────────────────────────────────────
# Tool 實作（Dispatcher）
# ────────────────────────────────────────────────────────────
TOOL_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              '..', '..', 'chat_logs', 'agent_tool_calls.jsonl')
os.makedirs(os.path.dirname(TOOL_LOG_PATH), exist_ok=True)


def _log_tool_call(tool: str, args: dict, result: Any, agent: str, elapsed_ms: int):
    """每次 tool 呼叫寫稽核"""
    try:
        entry = {
            'ts':         datetime.now().isoformat(timespec='seconds'),
            'tool':       tool,
            'agent':      agent,
            'args':       args,
            'elapsed_ms': elapsed_ms,
            'result_preview': str(result)[:300],
        }
        with open(TOOL_LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    except Exception:
        pass


def dispatch(tool: str, args: dict, agent: str = 'unknown') -> dict:
    """執行一個 tool · 自動寫稽核 + 回 trace

    Returns:
        {ok, result, elapsed_ms, agent, tool, args}
    """
    t0 = time.time()
    try:
        if tool == 'lookup_product':
            import acceptance_scenarios as accs
            r = accs.recommend_by_space(
                space=args.get('space', 'living'),
                area_ping=args.get('area_ping'),
            )

        elif tool == 'get_quote':
            import acceptance_scenarios as accs
            r = accs.quote_with_negotiation(
                area_ping=float(args.get('area_ping', 6)),
                segment=args.get('segment'),
                customer_type=args.get('customer_type', 'B2C'),
                requested_discount_pct=float(args.get('requested_discount_pct', 0)),
                bundle_units=int(args.get('bundle_units', 1)),
                seasonal_promo=bool(args.get('seasonal_promo', False)),
            )

        elif tool == 'lookup_competitor':
            import acceptance_scenarios as accs
            r = accs.MARKET_STRATEGY_TEMPLATES['E']['content']

        elif tool == 'get_brand_asset':
            import acceptance_scenarios as accs
            r = accs.get_brand_assets()

        elif tool == 'lookup_field_trial':
            import acceptance_scenarios as accs
            r = accs.get_field_trial_summary()

        elif tool == 'get_market_strategy':
            import acceptance_scenarios as accs
            r = accs.get_market_strategy(args.get('query', ''))

        elif tool == 'submit_for_approval':
            import approval_queue as aq
            r = aq.submit(
                track=args.get('track', 'sales'),
                payload=args.get('payload', {}),
                agent=args.get('agent', agent),
                customer=args.get('customer', 'unknown'),
                priority=args.get('priority', 'normal'),
            )

        elif tool == 'handoff_to_agent':
            # 純記錄；實際 handoff 由 agent_router 決策後改變對話狀態
            r = {
                'handoff_recorded': True,
                'from_agent':       agent,
                'to_agent':         args.get('target_agent'),
                'context_summary':  args.get('context_summary'),
                'reason':           args.get('reason'),
            }

        elif tool == 'pii_scan':
            try:
                from pii_guard import scan
                hits = scan(args.get('text', ''))
                r = {'pii_classes_found': hits, 'count': len(hits) if hits else 0}
            except Exception:
                # 退化版
                import re
                text = args.get('text', '')
                hits = []
                for cls, pat in [('phone', r'09\d{2}[-\s]?\d{3}[-\s]?\d{3}'),
                                  ('email', r'[\w.+-]+@[\w-]+\.[\w.-]+'),
                                  ('id_card', r'[A-Z][12]\d{8}')]:
                    if re.search(pat, text):
                        hits.append(cls)
                r = {'pii_classes_found': hits, 'count': len(hits)}

        elif tool == 'check_advertising_claim':
            text = args.get('text', '')
            violations = []
            forbidden = ['100%', '完全治癒', '保證根除', '絕對', '永久', '徹底根治',
                         '是垃圾', '騙人', '比賽爛']
            for w in forbidden:
                if w in text:
                    violations.append({'type': '不實宣稱或競品攻擊', 'phrase': w})
            r = {
                'violations':     violations,
                'compliant':      len(violations) == 0,
                'suggestion':     '建議改用「實測驗證」「環境部 NPA 認證」「PM2.5 趨零」等已驗證用語' if violations else '通過',
            }

        else:
            r = {'error': f'unknown tool: {tool}'}

        elapsed_ms = int((time.time() - t0) * 1000)
        _log_tool_call(tool, args, r, agent, elapsed_ms)
        return {'ok': True, 'tool': tool, 'args': args, 'agent': agent,
                'elapsed_ms': elapsed_ms, 'result': r}

    except Exception as e:
        elapsed_ms = int((time.time() - t0) * 1000)
        tb = traceback.format_exc()
        _log_tool_call(tool, args, {'error': str(e)}, agent, elapsed_ms)
        return {'ok': False, 'tool': tool, 'args': args, 'agent': agent,
                'elapsed_ms': elapsed_ms, 'error': str(e), 'traceback': tb[-500:]}


def list_tools_for_llm(target_format: str = 'anthropic') -> list:
    """回傳指定格式的 tool schema 給 LLM

    Args:
        target_format: anthropic / openai
    """
    if target_format == 'anthropic':
        return TOOL_SCHEMAS
    elif target_format == 'openai':
        return [{
            'type': 'function',
            'function': {
                'name':        t['name'],
                'description': t['description'],
                'parameters':  t['input_schema'],
            },
        } for t in TOOL_SCHEMAS]
    return TOOL_SCHEMAS


def get_recent_tool_calls(n: int = 50) -> list:
    """讀最近 N 筆 tool call log（給 dashboard 顯示）"""
    if not os.path.exists(TOOL_LOG_PATH):
        return []
    lines = []
    with open(TOOL_LOG_PATH, encoding='utf-8') as f:
        for line in f:
            try:
                lines.append(json.loads(line))
            except Exception:
                pass
    return lines[-n:]
