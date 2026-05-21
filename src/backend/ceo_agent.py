# -*- coding: utf-8 -*-
"""凌策 CEO Agent · 基於置信度的二層審核（Confidence-based Filtering）

定位：
  Agent（BD / 客服 / 提案 / 法務 / 行銷）→ CEO Agent 二審 → 總監人審
  CEO 不重做 PII / 不實宣稱（法務的職責），他關注：
    · 跨領域整合（BD 報的價 + 提案的方案 + 客服承諾的時程 是否一致）
    · 商業合理性（毛利 / 議價權限 / 長期影響）
    · 品牌調性（不准 BD 寫便宜、行銷寫高端）
    · 信心評分（最終 decision confidence）
    · 路由決策（自動發 / 進總監 queue / 退回 Agent）

信心分數（5 維度加權）：
  · LLM self-rated      30%（基於文字品質啟發式）
  · KB 命中度           25%（tool calls 成功率）
  · 議價權限            20%（折扣是否落在客群上限）
  · PII / 不實宣稱      15%（命中即扣 0.3+）
  · 品牌一致性          10%（引用真實數字 + 禁詞檢查）

三閘路由：
  · score ≧ 0.85 + risk=low    → 自動通過（auto_approve）
  · score 0.70-0.85 + risk≦med → 通過但抽樣 audit
  · score < 0.70 OR risk=high  → 送總監 queue（need_human_review）
  · score < 0.50               → 退回 Agent 重試（reject_and_retry）
"""
import os
import json
import time
from datetime import datetime
from typing import Optional, List, Dict, Any

CEO_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             '..', '..', 'chat_logs', 'ceo_reviews.jsonl')
os.makedirs(os.path.dirname(CEO_LOG_PATH), exist_ok=True)


# ────────────────────────────────────────────────────────────
# 信心分數計算（5 維度加權）
# ────────────────────────────────────────────────────────────
WEIGHTS = {
    'llm_quality':       0.30,
    'kb_coverage':       0.25,
    'bargain_authority': 0.20,
    'safety':            0.15,
    'brand_consistency': 0.10,
}

FORBIDDEN_WORDS = ['保證', '100%', '絕對', '治癒', '根除', '完全', '永久',
                    '萬無一失', '保你', '一定能']

KB_SIGNALS = ['NPA23C01250001', '41 場域', '41場域',
                'CADR', '環境部', '醫療', '無塵室',
                'addwii', 'Home Clean Room', '趨零', 'PM2.5']


def calculate_confidence(intent: dict, tool_results: list,
                          llm_text: str, agent_chain: list) -> dict:
    """5 維度加權計算信心分數 + breakdown"""
    breakdown = {}

    # ─── 1. LLM 品質（30%）─────────────────────
    llm_score = 0.65  # baseline
    text_len = len(llm_text or '')
    if text_len >= 60:           llm_score += 0.10
    if text_len >= 120:          llm_score += 0.05
    if any(s in llm_text for s in KB_SIGNALS):
        llm_score += 0.15
    # 不確定詞扣分
    hedge = sum(1 for w in ['可能', '大概', '或許', '應該', '貌似'] if w in llm_text)
    llm_score -= hedge * 0.05
    # stub 偵測
    if '[stub]' in llm_text or 'rule_engine' in llm_text.lower():
        llm_score = 0.20
    if llm_text.strip().startswith('（系統繁忙') or '無法' in llm_text[:20]:
        llm_score -= 0.20
    breakdown['llm_quality'] = round(max(0.0, min(1.0, llm_score)), 3)

    # ─── 2. KB 命中度（25%）─────────────────────
    if tool_results:
        ok_count = sum(1 for r in tool_results if r.get('ok'))
        kb_score = min(1.0, ok_count / 3.0)
        # 關鍵工具有命中加分
        critical_tools = {'lookup_product', 'get_quote', 'get_brand_asset',
                            'lookup_field_trial', 'lookup_competitor'}
        critical_hit = sum(1 for r in tool_results
                            if r.get('tool') in critical_tools and r.get('ok'))
        if critical_hit >= 2: kb_score = min(1.0, kb_score + 0.20)
    else:
        kb_score = 0.30  # 沒呼叫工具 = 低 KB 信心
    breakdown['kb_coverage'] = round(kb_score, 3)

    # ─── 3. 議價權限（20%）─────────────────────
    bargain_score = 1.0
    disc = intent.get('requested_discount_pct', 0)
    if disc > 15:    bargain_score = 0.05   # 超權拒絕
    elif disc > 10:  bargain_score = 0.40   # 需主管核可
    elif disc > 5:   bargain_score = 0.65   # 邊緣（看客群上限）
    # 若是 B2B 客群，提高權限
    if intent.get('customer_type') == 'B2B' and disc <= 12:
        bargain_score = max(bargain_score, 0.85)
    breakdown['bargain_authority'] = round(bargain_score, 3)

    # ─── 4. 安全（PII / 不實宣稱）（15%）─────────
    safety_score = 1.0
    for r in tool_results:
        tool = r.get('tool', '')
        res = r.get('result', {}) if isinstance(r.get('result'), dict) else {}
        if tool == 'pii_scan' and res.get('count', 0) > 0:
            safety_score -= 0.40
        if tool == 'check_advertising_claim':
            if isinstance(res, dict) and not res.get('compliant', True):
                vlen = len(res.get('violations', []))
                safety_score -= min(0.60, 0.20 * vlen)
    # 文本內含禁詞
    forbid_hit = sum(1 for w in FORBIDDEN_WORDS if w in llm_text)
    safety_score -= forbid_hit * 0.25
    breakdown['safety'] = round(max(0.0, min(1.0, safety_score)), 3)

    # ─── 5. 品牌一致性（10%）───────────────────
    brand_score = 0.65
    if any(b in llm_text for b in ['addwii', 'Home Clean Room', '無塵室', '加我科技']):
        brand_score += 0.20
    if any(b in llm_text for b in ['自由呼吸', '淨零生活']):
        brand_score += 0.10
    if forbid_hit > 0:           # 用了絕對詞 = 品牌風險
        brand_score -= 0.25
    breakdown['brand_consistency'] = round(max(0.0, min(1.0, brand_score)), 3)

    # ─── 加權合成 ────────────────────────────
    total = sum(breakdown[k] * WEIGHTS[k] for k in WEIGHTS)
    return {
        'score':     round(total, 3),
        'breakdown': breakdown,
        'weights':   WEIGHTS,
    }


# ────────────────────────────────────────────────────────────
# 風險等級
# ────────────────────────────────────────────────────────────
def classify_risk(intent: dict, tool_results: list, llm_text: str) -> str:
    """high / medium / low"""
    # high triggers
    if intent.get('requested_discount_pct', 0) > 10:           return 'high'
    if intent.get('is_complaint'):                             return 'high'
    for r in tool_results:
        res = r.get('result', {}) if isinstance(r.get('result'), dict) else {}
        if r.get('tool') == 'pii_scan' and res.get('count', 0) > 0:
            return 'high'
        if r.get('tool') == 'check_advertising_claim':
            if isinstance(res, dict) and not res.get('compliant', True):
                vlen = len(res.get('violations', []))
                if vlen >= 2: return 'high'

    # forbidden words 命中
    forbid_hit = sum(1 for w in FORBIDDEN_WORDS if w in llm_text)
    if forbid_hit >= 2: return 'high'
    if forbid_hit == 1: return 'medium'

    # medium triggers
    if intent.get('requested_discount_pct', 0) > 5:            return 'medium'
    if intent.get('is_competitor_inquiry'):                    return 'medium'
    if intent.get('customer_type') == 'B2B' and intent.get('bundle_units', 1) >= 5:
        return 'medium'

    return 'low'


# ────────────────────────────────────────────────────────────
# 三閘路由決策
# ────────────────────────────────────────────────────────────
def route_decision(confidence: dict, risk: str) -> dict:
    """依信心分數 + 風險決定路由"""
    score = confidence['score']

    if score >= 0.85 and risk == 'low':
        return {
            'action':         'auto_approve',
            'reason':         f'高信心 {score:.2f} + 低風險 → CEO 自動核可',
            'send_to_user':   True,
            'log_for_audit':  True,
            'need_supervisor': False,
        }

    if score >= 0.70 and risk in ('low', 'medium'):
        return {
            'action':         'auto_with_audit',
            'reason':         f'中信心 {score:.2f} + 風險 {risk} → 通過但記入抽樣 audit',
            'send_to_user':   True,
            'log_for_audit':  True,
            'need_supervisor': False,
            'sample_rate':    0.10,    # 10% 抽樣供總監事後復查
        }

    if score < 0.50:
        return {
            'action':         'reject_and_retry',
            'reason':         f'低信心 {score:.2f} → 退回 Agent 重生',
            'send_to_user':   False,
            'log_for_audit':  True,
            'need_supervisor': False,
            'retry':          True,
        }

    # score 0.50-0.70 OR risk='high'
    return {
        'action':         'need_human_review',
        'reason':         f'信心 {score:.2f} 或風險 {risk} → 進總監 queue',
        'send_to_user':   False,    # 等總監批准才發
        'log_for_audit':  True,
        'need_supervisor': True,
    }


# ────────────────────────────────────────────────────────────
# 跨 Agent 一致性檢查（CEO 獨特職責）
# ────────────────────────────────────────────────────────────
def cross_agent_consistency(tool_results: list) -> dict:
    """檢查 BD/proposal/legal/customer-service 各 Agent 結果是否一致"""
    inconsistencies = []

    # 1. 報價數字一致性
    quotes = []
    for r in tool_results:
        if r.get('tool') == 'get_quote' and r.get('ok'):
            res = r.get('result', {})
            quotes.append({'system': res.get('recommended_system'),
                            'total': res.get('final_total_ntd')})
    if len(quotes) >= 2:
        systems = {q['system'] for q in quotes if q['system']}
        if len(systems) > 1:
            inconsistencies.append(f'多 Agent 推薦不同 S 系列：{systems}')

    # 2. 推薦空間一致性
    spaces = []
    for r in tool_results:
        if r.get('tool') == 'lookup_product' and r.get('ok'):
            res = r.get('result', {})
            spaces.append(res.get('space'))
    if len(spaces) >= 2 and len(set(spaces)) > 1:
        inconsistencies.append(f'空間推薦不一致：{set(spaces)}')

    # 3. 法務檢查是否通過
    legal_ok = True
    for r in tool_results:
        if r.get('tool') == 'check_advertising_claim':
            res = r.get('result', {}) if isinstance(r.get('result'), dict) else {}
            if not res.get('compliant', True):
                legal_ok = False
                inconsistencies.append('法務 Agent 標示合規不通過')

    return {
        'consistent':       len(inconsistencies) == 0,
        'inconsistencies':  inconsistencies,
        'legal_ok':         legal_ok,
    }


# ────────────────────────────────────────────────────────────
# CEO 主審入口
# ────────────────────────────────────────────────────────────
def review(intent: dict,
           tool_results: list,
           llm_text: str,
           agent_chain: list,
           chat_id: str = None,
           use_llm_evaluator: bool = False) -> dict:
    """CEO Agent 二審主入口

    Args:
        intent:          _parse_intent 結果
        tool_results:    各 Agent 跑出的 tool calls
        llm_text:        最後 Agent 給的回覆
        agent_chain:     ['bd', 'proposal', ...]
        use_llm_evaluator: True 時加跑一次 LLM 評估（慢但準），預設 False（規則為主）

    Returns:
        {
            confidence: {score, breakdown, weights},
            risk_level: 'low' / 'medium' / 'high',
            consistency: {...},
            decision: {action, reason, ...},
            ceo_comment: '...',
            elapsed_ms: ...,
        }
    """
    t0 = time.time()

    # 1. 信心分數
    confidence = calculate_confidence(intent, tool_results, llm_text, agent_chain)

    # 2. 風險等級
    risk = classify_risk(intent, tool_results, llm_text)

    # 3. 跨 Agent 一致性
    consistency = cross_agent_consistency(tool_results)
    if not consistency['consistent']:
        # 信心扣分
        confidence['score'] = max(0.0, confidence['score'] - 0.10)
        confidence['adjusted_for_inconsistency'] = True

    # 4. 三閘路由
    decision = route_decision(confidence, risk)

    # 5. CEO 評語（規則）
    ceo_comment = _generate_ceo_comment(intent, tool_results, llm_text,
                                          confidence, risk, decision)

    # 6.（可選）LLM 評估補強
    llm_eval = None
    if use_llm_evaluator:
        llm_eval = _llm_evaluate(intent, tool_results, llm_text, confidence, risk)

    result = {
        'chat_id':       chat_id,
        'ts':            datetime.now().isoformat(timespec='seconds'),
        'agent_chain':   agent_chain,
        'confidence':    confidence,
        'risk_level':    risk,
        'consistency':   consistency,
        'decision':      decision,
        'ceo_comment':   ceo_comment,
        'llm_evaluation': llm_eval,
        'elapsed_ms':    int((time.time() - t0) * 1000),
    }

    # 7. 寫稽核
    _log_ceo_review(result)
    return result


def _generate_ceo_comment(intent, tool_results, llm_text, confidence, risk, decision) -> str:
    """CEO 規則式評語（給總監看的人類可讀說明）"""
    bd = confidence['breakdown']
    parts = []

    # 信心分數整體說明
    score = confidence['score']
    if score >= 0.85:
        parts.append(f'✅ 信心 {score:.2f}（高）')
    elif score >= 0.70:
        parts.append(f'🟡 信心 {score:.2f}（中）')
    else:
        parts.append(f'🔴 信心 {score:.2f}（低）')

    parts.append(f'· 風險 {risk}')

    # 弱項指出
    weak = []
    if bd['llm_quality'] < 0.6: weak.append('LLM 品質弱（可能 fallback / 過短）')
    if bd['kb_coverage'] < 0.5: weak.append('KB 未命中（無工具呼叫成功）')
    if bd['bargain_authority'] < 0.5: weak.append('議價超權')
    if bd['safety'] < 0.7: weak.append('安全分扣分（PII / 禁詞 / 違規）')
    if bd['brand_consistency'] < 0.6: weak.append('品牌一致性低')

    if weak:
        parts.append('弱項：' + ' / '.join(weak))

    parts.append(f'→ {decision["action"]}')

    return ' '.join(parts)


def _llm_evaluate(intent, tool_results, llm_text, confidence, risk) -> Optional[str]:
    """選配 · LLM 二次評估（慢但準）"""
    try:
        import sys
        _bdir = os.path.dirname(os.path.abspath(__file__))
        if _bdir not in sys.path: sys.path.insert(0, _bdir)
        import ai_backend
        sys_p = (
            '你是 addwii 加我科技的 CEO Agent，負責審查業務員/客服/行銷 Agent 的產出。\n'
            '一律繁體中文。簡短客觀。請從「跨領域一致性、商業合理性、品牌調性」三個角度給 100 字內評語。'
        )
        prompt = (
            f'業務 Agent 給顧客的回覆：「{(llm_text or "")[:300]}」\n\n'
            f'規則引擎信心：{confidence["score"]:.2f}\n'
            f'風險等級：{risk}\n'
            f'弱項：LLM={confidence["breakdown"]["llm_quality"]:.2f} · '
            f'KB={confidence["breakdown"]["kb_coverage"]:.2f} · '
            f'議價={confidence["breakdown"]["bargain_authority"]:.2f} · '
            f'安全={confidence["breakdown"]["safety"]:.2f} · '
            f'品牌={confidence["breakdown"]["brand_consistency"]:.2f}\n\n'
            f'請給 CEO 評語（100 字內 · 直接寫評語）：'
        )
        r = ai_backend.generate(prompt=prompt, system=sys_p,
                                 max_tokens=200, temperature=0.2, timeout_s=120)
        if not r.get('fallback'):
            return (r.get('text') or '').strip()
    except Exception:
        pass
    return None


# ────────────────────────────────────────────────────────────
# 持久化
# ────────────────────────────────────────────────────────────
def _log_ceo_review(result: dict):
    try:
        with open(CEO_LOG_PATH, 'a', encoding='utf-8') as f:
            # 精簡寫入（避免 jsonl 過大）
            entry = {
                'ts':          result['ts'],
                'chat_id':     result.get('chat_id'),
                'agent_chain': result['agent_chain'],
                'score':       result['confidence']['score'],
                'breakdown':   result['confidence']['breakdown'],
                'risk':        result['risk_level'],
                'action':      result['decision']['action'],
                'consistent':  result['consistency']['consistent'],
                'elapsed_ms':  result['elapsed_ms'],
            }
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    except Exception:
        pass


def get_recent_reviews(n: int = 50) -> list:
    if not os.path.exists(CEO_LOG_PATH): return []
    lines = []
    with open(CEO_LOG_PATH, encoding='utf-8') as f:
        for line in f:
            try: lines.append(json.loads(line))
            except: pass
    return lines[-n:]


def get_stats() -> dict:
    reviews = get_recent_reviews(1000)
    if not reviews:
        return {'total': 0, 'by_action': {}, 'by_risk': {}, 'avg_score': 0,
                'avg_elapsed_ms': 0}
    by_action = {}
    by_risk = {}
    total_score = 0
    total_elapsed = 0
    for r in reviews:
        by_action[r['action']] = by_action.get(r['action'], 0) + 1
        by_risk[r['risk']] = by_risk.get(r['risk'], 0) + 1
        total_score += r.get('score', 0)
        total_elapsed += r.get('elapsed_ms', 0)
    n = len(reviews)
    return {
        'total':           n,
        'by_action':       by_action,
        'by_risk':         by_risk,
        'avg_score':       round(total_score / n, 3),
        'avg_elapsed_ms':  round(total_elapsed / n, 1),
        'auto_approve_rate':   round(by_action.get('auto_approve', 0) / n, 3),
        'human_review_rate':   round(by_action.get('need_human_review', 0) / n, 3),
    }
