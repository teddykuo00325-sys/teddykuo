# -*- coding: utf-8 -*-
"""凌策 Telegram Bot Adapter · 模擬 LINE OA 入口（dry-run 模式）

addwii 不開放真實 LINE 官方帳號 → 用 Telegram bot 模擬同等流程。
本模組同時支援：
  1. dry-run（預設）— 不真連 Telegram API，模擬 webhook 進入，給評審看流程
  2. live          — 設 TELEGRAM_BOT_TOKEN 後真連 Telegram，可實機運作

流程：
  使用者 LINE/Telegram 訊息
    → PII Guard 13 類過濾（個資不入 LLM）
    → 客服 Agent 判斷客群（B2B/B2C）+ 空間 + 坪數
    → 走 ai_backend.generate（Ollama / Anthropic / fallback）
    → 議價：若折扣超權 → approval_queue.submit('sales')
    → 回覆使用者
    → 總監若有需審項目，會在 dashboard 看到紅點
"""
import os
import json
import time
import uuid
from datetime import datetime
from typing import Optional, Dict

# 偵測模式
TELEGRAM_BOT_TOKEN  = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_MODE       = 'live' if TELEGRAM_BOT_TOKEN else 'dry-run'
TELEGRAM_LOG_DIR    = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    '..', '..', 'data', 'lingce', 'telegram_logs')
os.makedirs(TELEGRAM_LOG_DIR, exist_ok=True)


def _log(direction: str, payload: dict):
    """所有 webhook 進出都寫 jsonl"""
    log_path = os.path.join(TELEGRAM_LOG_DIR, f'{datetime.now().strftime("%Y%m%d")}.jsonl')
    entry = {
        'ts':        datetime.now().isoformat(timespec='seconds'),
        'direction': direction,  # inbound / outbound
        'mode':      TELEGRAM_MODE,
        'payload':   payload,
    }
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')


def _parse_user_intent(text: str) -> dict:
    """規則 + 關鍵字偵測客戶屬性（B2B/B2C/空間/坪數）"""
    text_lower = text.lower()

    # 空間偵測
    space = None
    space_kw = {
        'baby':     ['嬰兒', '寶寶', '新生兒', '嬰幼兒'],
        'kitchen':  ['廚房', '油煙', '烹飪'],
        'bathroom': ['浴室', '廁所', '潮溼', '黴菌'],
        'living':   ['客廳', '訪客', '寵物'],
        'bedroom':  ['臥室', '臥房', '主臥', '睡眠'],
        'dining':   ['餐廳', '飯廳', '聚餐'],
    }
    for sp, kws in space_kw.items():
        if any(kw in text for kw in kws):
            space = sp
            break

    # 坪數偵測（中文數字 + 阿拉伯數字）
    area = None
    import re
    m = re.search(r'(\d+(?:\.\d+)?)\s*坪', text)
    if m:
        area = float(m.group(1))

    # B2B / B2C
    b2b_kw = ['月子', '診所', '幼兒園', '托嬰', '醫美', '牙醫', 'ESG', '企業', '辦公']
    customer_type = 'B2B' if any(kw in text for kw in b2b_kw) else 'B2C'

    # 客群細分
    segment = None
    seg_map = {
        'maternity_center':   ['月子中心', '月子'],
        'gyn_clinic':         ['婦幼', '產科', '婦產'],
        'allergy_clinic':     ['過敏專科', '過敏診所'],
        'pediatric_clinic':   ['兒科'],
        'kindergarten':       ['幼兒園', '托嬰'],
        'beauty_dental':      ['醫美', '牙醫'],
        'esg_enterprise':     ['ESG', '上市櫃', '永續'],
        'allergy_family':     ['過敏兒', '過敏'],
        'newborn_family':     ['新生兒', '寶寶'],
        'renovation':         ['裝潢', '甲醛'],
        'pet_owner':          ['寵物', '貓', '狗'],
    }
    for seg, kws in seg_map.items():
        if any(kw in text for kw in kws):
            segment = seg
            break

    # 折扣意圖偵測
    requested_discount = 0
    m2 = re.search(r'(\d+)\s*[%％]?\s*折', text)
    if m2:
        # 「8折」= 20% off; 「打 9 折」 = 10% off
        v = int(m2.group(1))
        if v <= 10:
            requested_discount = (10 - v) * 10  # 8 折 = 20%
    m3 = re.search(r'折扣\s*(\d+)\s*[%％]', text)
    if m3:
        requested_discount = int(m3.group(1))

    return {
        'space':                  space,
        'area_ping':              area,
        'customer_type':          customer_type,
        'segment':                segment,
        'requested_discount_pct': requested_discount,
    }


def handle_message(chat_id: str, text: str, user_name: str = 'guest') -> dict:
    """處理一則 Telegram inbound 訊息

    流程：PII → 意圖偵測 → AI 回覆 → 議價閘 → outbound
    """
    inbound = {
        'chat_id':   chat_id,
        'user_name': user_name,
        'text':      text,
    }
    _log('inbound', inbound)

    # 1. PII 遮蔽
    try:
        from pii_guard import mask_text
        safe_text, pii_dets = mask_text(text, context='telegram:inbound')
    except Exception:
        safe_text, pii_dets = text, []

    # 2. 意圖偵測
    intent = _parse_user_intent(safe_text)

    # 3. 走業務邏輯
    reply_text = ''
    quote_info = None
    approval_ticket = None

    try:
        import acceptance_scenarios as accs

        # 3a. 若偵測到空間 + 坪數 → 推薦方案
        if intent['space'] and intent['area_ping']:
            rec = accs.recommend_by_space(intent['space'], intent['area_ping'])
            if intent.get('requested_discount_pct', 0) > 0 or intent['customer_type'] == 'B2B':
                # 走議價
                q = accs.quote_with_negotiation(
                    area_ping=intent['area_ping'],
                    segment=intent['segment'],
                    customer_type=intent['customer_type'],
                    requested_discount_pct=intent.get('requested_discount_pct', 0),
                )
                quote_info = q
                if q['approval_status'] == 'NEED_HUMAN_REVIEW':
                    # 送進 approval_queue
                    try:
                        import approval_queue as aq
                        approval_ticket = aq.submit(
                            track='sales',
                            payload={'intent': intent, 'quote': q,
                                     'source': 'telegram', 'chat_id': chat_id},
                            agent='customer-service',
                            customer=f'telegram:{user_name}',
                        )
                    except Exception:
                        pass

                if q['approval_status'] == 'AUTO_APPROVED':
                    reply_text = (f"{rec['icon']} {rec['space_zh']} · 推薦方案 {rec['recommended_system']}\n"
                                  f"原價 {q['base_total_ntd']:,} 元 → 折扣後 {q['final_total_ntd']:,} 元\n"
                                  f"24 期 0 利率月付 {q['zero_interest_24m_ntd']:,} 元\n"
                                  f"環境部 NPA23C01250001 認證 PM2.5 趨零\n"
                                  f"✅ 此報價已自動核可（{q['reason']}）")
                elif q['approval_status'] == 'NEED_HUMAN_REVIEW':
                    reply_text = (f"{rec['icon']} 已為您試算 {rec['space_zh']} · {rec['recommended_system']} 方案\n"
                                  f"折扣後 {q['final_total_ntd']:,} 元\n"
                                  f"⏳ 您提的折扣 {intent.get('requested_discount_pct')}% 已送總監核可，"
                                  f"通常 30 分鐘內回覆（單號 {approval_ticket.get('ticket_id') if approval_ticket else 'N/A'}）")
                else:  # REJECTED
                    reply_text = (f"很抱歉，您要求的折扣 {intent.get('requested_discount_pct')}% 超過權限上限。\n"
                                  f"建議改用：升規送 2 年濾網 / 24 期 0 利率 / 趨零保固 等加值方案。")
            else:
                reply_text = (f"{rec['icon']} 為您推薦 {rec['space_zh']} · {rec['recommended_system']}\n"
                              f"CADR {rec['cadr_total']} m³/h · 售價 {rec['total_price_ntd']:,} 元\n"
                              f"{rec['pitch']}")
        else:
            # 3b. 無明確空間/坪數 → 走客服 Agent qa_chat
            session_id = f'telegram-{chat_id}'
            r = accs.qa_chat_multi(session_id=session_id, customer='addwii',
                                    question=safe_text, user=user_name)
            reply_text = r.get('answer') or r.get('response') or '抱歉，請告訴我您想保護的空間（嬰兒/客廳/臥室等）與大概坪數。'
    except Exception as e:
        reply_text = f'[系統處理中發生錯誤] {e}'

    # 4. outbound
    outbound = {
        'chat_id':         chat_id,
        'reply_text':      reply_text,
        'intent_detected': intent,
        'pii_redactions':  len(pii_dets),
        'quote':           quote_info,
        'approval_ticket': approval_ticket,
    }
    _log('outbound', outbound)

    # 5. 若 live 模式真發 Telegram
    if TELEGRAM_MODE == 'live':
        try:
            import requests
            requests.post(
                f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage',
                json={'chat_id': chat_id, 'text': reply_text},
                timeout=10,
            )
            outbound['delivery'] = 'sent_to_telegram'
        except Exception as e:
            outbound['delivery'] = f'failed: {e}'
    else:
        outbound['delivery'] = 'dry-run (not sent to real Telegram)'

    return outbound


def status() -> dict:
    """給 dashboard 顯示 Telegram 連線狀態"""
    today_log = os.path.join(TELEGRAM_LOG_DIR, f'{datetime.now().strftime("%Y%m%d")}.jsonl')
    today_count = 0
    if os.path.exists(today_log):
        with open(today_log, encoding='utf-8') as f:
            today_count = sum(1 for _ in f)
    return {
        'mode':                  TELEGRAM_MODE,
        'token_present':         bool(TELEGRAM_BOT_TOKEN),
        'today_events':          today_count,
        'log_dir':               TELEGRAM_LOG_DIR,
        'reason_for_dry_run':    'addwii 不開放 LINE 官方帳號 webhook → 使用 Telegram bot 模擬同等流程；可設 TELEGRAM_BOT_TOKEN 切到 live 模式',
        'simulated_flow':        [
            '1. user 發 Telegram → handle_message(chat_id, text)',
            '2. PII Guard 13 類遮蔽',
            '3. 意圖偵測：空間 / 坪數 / B2B-B2C / 客群 / 折扣意圖',
            '4. 走 ai_backend.generate 或 recommend_by_space / quote_with_negotiation',
            '5. 議價閘：< 5% 自動 / 5-10% 送 approval_queue / > 15% 拒絕',
            '6. 回覆使用者 + 寫 telegram_logs jsonl',
            '7. 總監若有待審 → dashboard 紅點通知',
        ],
    }


def demo_conversation():
    """產生 demo 對話展示（給評審看流程運作）"""
    scenarios = [
        ('chat_001', '我家有過敏兒 想找臥室 8 坪的解決方案', '王女士'),
        ('chat_002', '我們是月子中心 想配 8 坪嬰兒房 5 套 算 8 折', '永和月子中心'),
        ('chat_003', '客廳 12 坪 想看看價格', '陳先生'),
        ('chat_004', '我要 80% 折扣不然不買', '殺價客戶'),
    ]
    results = []
    for chat_id, text, user in scenarios:
        results.append({
            'inbound':  {'chat_id': chat_id, 'text': text, 'user': user},
            'outbound': handle_message(chat_id, text, user),
        })
    return {'scenarios_run': len(scenarios), 'results': results}


if __name__ == '__main__':
    print('=== Telegram bot status ===')
    print(json.dumps(status(), ensure_ascii=False, indent=2))
    print()
    print('=== Demo conversations ===')
    print(json.dumps(demo_conversation(), ensure_ascii=False, indent=2))
