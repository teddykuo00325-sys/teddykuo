# -*- coding: utf-8 -*-
"""addwii 內容日曆 + Publisher mock

功能：
  · 排程：每日 1 篇 + 每週 1 支 YT Shorts
  · Calendar：未來 7 天視圖
  · Publisher mock：FB / IG / YouTube / Telegram 4 通道
    - 有 token → 真實 publish（暫不接，留 hook）
    - 無 token → 寫 audit log + mark as "pending_token"

API token 儲存：
  data/addwii/publisher_tokens.json  （加密存？目前明文示意；正式部署應改 keyring）
"""
import os, json
from datetime import datetime, timedelta

DATA_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          '..', '..', 'data', 'addwii')
CALENDAR_PATH = os.path.join(DATA_DIR, 'content_calendar.json')
TOKENS_PATH   = os.path.join(DATA_DIR, 'publisher_tokens.json')
PUBLISH_LOG   = os.path.join(DATA_DIR, 'publish_log.jsonl')
os.makedirs(DATA_DIR, exist_ok=True)


# ────────────────────────────────────────────────────────────
# 內容日曆
# ────────────────────────────────────────────────────────────
def _load_calendar() -> dict:
    if not os.path.exists(CALENDAR_PATH):
        return {'entries': []}
    try:
        with open(CALENDAR_PATH, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {'entries': []}


def _save_calendar(cal: dict):
    with open(CALENDAR_PATH, 'w', encoding='utf-8') as f:
        json.dump(cal, f, ensure_ascii=False, indent=2)


def build_week_schedule(start_date: str = None) -> dict:
    """產出本週排程：每日 1 篇 + 週三 + 週五 YT Shorts"""
    import topic_generator
    if start_date:
        try:
            start = datetime.fromisoformat(start_date)
        except Exception:
            start = datetime.now()
    else:
        start = datetime.now()

    week = topic_generator.generate_week_topics(7)

    entries = []
    for i, topic in enumerate(week):
        d = datetime.fromisoformat(topic['date'])
        # 每日 1 篇 FB
        entries.append({
            'date':           topic['date'],
            'time':           '09:00',
            'weekday':        topic['weekday'],
            'channel':        'facebook',
            'content_type':   'social_post',
            'topic_title':    topic['title'],
            'topic_space':    topic['space'],
            'status':         'scheduled',
        })
        # IG 同步
        entries.append({
            'date':           topic['date'],
            'time':           '10:00',
            'weekday':        topic['weekday'],
            'channel':        'instagram',
            'content_type':   'social_post',
            'topic_title':    topic['title'],
            'topic_space':    topic['space'],
            'status':         'scheduled',
        })
        # 週三 + 週五 YT Shorts
        if d.weekday() in (2, 4):
            entries.append({
                'date':           topic['date'],
                'time':           '14:00',
                'weekday':        topic['weekday'],
                'channel':        'youtube',
                'content_type':   'yt_shorts',
                'topic_title':    topic['title'],
                'topic_space':    topic['space'],
                'status':         'scheduled',
            })

    cal = {
        'start_date':       start.strftime('%Y-%m-%d'),
        'end_date':         (start + timedelta(days=6)).strftime('%Y-%m-%d'),
        'generated_at':     datetime.now().isoformat(timespec='seconds'),
        'this_week_count':  len(entries),
        'entries':          entries,
    }
    _save_calendar(cal)
    return cal


def get_calendar() -> dict:
    cal = _load_calendar()
    if not cal.get('entries'):
        return build_week_schedule()
    return cal


# ────────────────────────────────────────────────────────────
# Publisher Token Manager
# ────────────────────────────────────────────────────────────
def _load_tokens() -> dict:
    if not os.path.exists(TOKENS_PATH):
        return {}
    try:
        with open(TOKENS_PATH, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def _save_tokens(tokens: dict):
    with open(TOKENS_PATH, 'w', encoding='utf-8') as f:
        json.dump(tokens, f, ensure_ascii=False, indent=2)


def set_publisher_token(channel: str, token: str) -> dict:
    """設定通道 token（FB Page / IG Business / YouTube OAuth / Telegram bot）"""
    tokens = _load_tokens()
    tokens[channel] = {
        'token_preview': '***' + (token[-4:] if len(token) > 4 else token),
        'configured_at': datetime.now().isoformat(timespec='seconds'),
        # 真實 token 加密存（目前 demo 用 base64 obfuscate）
        'token_obfs':    _obfuscate(token),
    }
    _save_tokens(tokens)
    return {'ok': True, 'channel': channel, 'configured': True}


def _obfuscate(s: str) -> str:
    import base64
    return base64.b64encode(s.encode('utf-8')).decode('ascii')


def _deobfuscate(s: str) -> str:
    import base64
    try: return base64.b64decode(s.encode('ascii')).decode('utf-8')
    except: return ''


def get_publishers_status() -> dict:
    """查所有 publisher 通道狀態"""
    tokens = _load_tokens()
    channels = {}
    for ch in ('facebook', 'instagram', 'youtube', 'telegram'):
        cfg = tokens.get(ch)
        channels[ch] = {
            'configured':      bool(cfg),
            'token_preview':   cfg.get('token_preview') if cfg else None,
            'configured_at':   cfg.get('configured_at') if cfg else None,
        }
    return {
        'channels':         channels,
        'configured_count': sum(1 for v in channels.values() if v['configured']),
        'total':            4,
    }


# ────────────────────────────────────────────────────────────
# Publisher（mock + 真實 hook）
# ────────────────────────────────────────────────────────────
def publish_post(channel: str, post_data: dict) -> dict:
    """發布貼文。若 token 未設 → mock；若已設 → 真實 POST"""
    tokens = _load_tokens()
    cfg = tokens.get(channel)

    entry = {
        'ts':         datetime.now().isoformat(timespec='seconds'),
        'channel':    channel,
        'post_data':  {k: v for k, v in post_data.items() if k != 'text' and k != 'full_script'},
        'text_preview': (post_data.get('text') or post_data.get('full_script', ''))[:200],
        'has_token':  bool(cfg),
    }

    if not cfg:
        entry['status'] = 'mock_published'
        entry['note']   = f'{channel} token 未設 · 已記入 audit · 等 token 補入後可重發'
    else:
        # 真實 publish hook（依平台不同呼叫不同 API）
        try:
            if channel == 'telegram':
                # 直接走現有 telegram_live_bot
                from telegram_live_bot import send_message
                chat_id = post_data.get('chat_id', '@addwii_official')  # 預設頻道名
                send_message(chat_id, post_data.get('text', ''))
                entry['status'] = 'live_published'
            elif channel == 'facebook':
                # TODO: FB Graph API · 預留
                entry['status'] = 'token_present_but_hook_not_wired'
                entry['note']   = 'FB Graph API hook 預留 · TG token 是唯一現已串接的'
            elif channel == 'instagram':
                entry['status'] = 'token_present_but_hook_not_wired'
                entry['note']   = 'IG Business API hook 預留'
            elif channel == 'youtube':
                entry['status'] = 'token_present_but_hook_not_wired'
                entry['note']   = 'YouTube Data API hook 預留'
        except Exception as e:
            entry['status'] = 'error'
            entry['error']  = str(e)

    # 寫 audit log
    with open(PUBLISH_LOG, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    return entry


def get_publish_log(limit: int = 50) -> dict:
    """讀 publish audit log"""
    if not os.path.exists(PUBLISH_LOG):
        return {'entries': []}
    items = []
    with open(PUBLISH_LOG, encoding='utf-8') as f:
        for line in f:
            try: items.append(json.loads(line))
            except: pass
    return {'total': len(items), 'entries': items[-limit:]}
