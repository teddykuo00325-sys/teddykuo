# -*- coding: utf-8 -*-
"""凌策 addwii 業務助理 · Telegram Live Bot (long-polling)

不需公開 webhook · 不需 ngrok · 不需設定外部網域。
只要設 TELEGRAM_BOT_TOKEN 環境變數，跑此腳本即可。

啟動：
    set TELEGRAM_BOT_TOKEN=1234567890:AAEx......
    python src/backend/telegram_live_bot.py

或從 server 內背景啟動：
    POST /api/telegram/live/start

流程（每則訊息）：
    Telegram → long-polling getUpdates
      → PII Guard 13 類遮蔽
      → agent_router.respond（multi-agent + tool calling）
      → Telegram sendMessage（真實發出）
      → 寫 telegram_logs/jsonl
"""
import os, time, json, threading, traceback
from datetime import datetime
from typing import Optional

import requests

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
API_BASE = f'https://api.telegram.org/bot{TOKEN}'
LOG_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         '..', '..', 'data', 'lingce', 'telegram_logs')
os.makedirs(LOG_DIR, exist_ok=True)

# Bot 啟動狀態
_BOT_RUNNING   = False
_BOT_THREAD    = None
_LAST_UPDATE_ID = 0
_STATS = {
    'started_at':    None,
    'messages_in':   0,
    'messages_out':  0,
    'errors':        0,
    'last_user':     None,
    'last_text':     None,
}


def _log(direction: str, payload: dict):
    log_path = os.path.join(LOG_DIR, f'live_{datetime.now().strftime("%Y%m%d")}.jsonl')
    entry = {
        'ts':        datetime.now().isoformat(timespec='seconds'),
        'direction': direction,
        'payload':   payload,
    }
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')


def send_message(chat_id, text, parse_mode='Markdown'):
    """發送訊息給使用者"""
    if not TOKEN:
        return {'ok': False, 'error': 'no TELEGRAM_BOT_TOKEN'}
    try:
        # Telegram message 上限 4096
        text = (text or '（無回覆）')[:4000]
        r = requests.post(f'{API_BASE}/sendMessage', json={
            'chat_id':   chat_id,
            'text':      text,
            'parse_mode': parse_mode,
        }, timeout=15)
        r.raise_for_status()
        _log('outbound', {'chat_id': chat_id, 'text': text})
        _STATS['messages_out'] += 1
        return {'ok': True}
    except Exception as e:
        _STATS['errors'] += 1
        _log('outbound_error', {'chat_id': chat_id, 'error': str(e)})
        return {'ok': False, 'error': str(e)}


def get_me():
    """取得 bot 資訊"""
    if not TOKEN:
        return {'ok': False, 'error': 'no TELEGRAM_BOT_TOKEN set'}
    try:
        r = requests.get(f'{API_BASE}/getMe', timeout=10)
        return r.json()
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def _handle_update(update: dict):
    """處理單一 Telegram update"""
    msg = update.get('message') or update.get('edited_message')
    if not msg:
        return
    chat_id = msg['chat']['id']
    text    = msg.get('text', '')
    if not text:
        return  # 暫不處理圖/檔
    user    = msg.get('from', {})
    user_name = user.get('first_name', '') + (' ' + user.get('last_name', '') if user.get('last_name') else '')
    if user.get('username'):
        user_name += f' (@{user["username"]})'

    _STATS['messages_in'] += 1
    _STATS['last_user']    = user_name
    _STATS['last_text']    = text
    _log('inbound', {'chat_id': chat_id, 'user_name': user_name, 'text': text})

    # 顯示「打字中」狀態
    try:
        requests.post(f'{API_BASE}/sendChatAction', json={
            'chat_id': chat_id, 'action': 'typing',
        }, timeout=5)
    except Exception:
        pass

    # 入特殊指令
    if text.lower() in ('/start', '/help'):
        send_message(chat_id, (
            "👋 您好！我是 *addwii 加我科技* 的 AI 業務助理\n"
            "（由凌策公司 AI Agent 提供 · 自由呼吸 淨零生活）\n\n"
            "您可以這樣問我：\n"
            "🛏️ _我家有過敏兒 想找臥室 8 坪的方案_\n"
            "🍳 _廚房油煙好嚴重 5 坪怎麼處理_\n"
            "🏢 _我們是月子中心 想配 8 坪嬰兒房 5 套 算 8 折_\n"
            "📊 _Coway 跟你們比怎樣_\n\n"
            "我背後有 10 個 AI Agent 協作（業務 / 提案 / 法務 / 客服），"
            "會自動依您的需求 handoff 給最適合的同事處理。\n\n"
            "想了解品牌？回 _品牌_\n"
            "想看實證？回 _實測_\n"
            "想比競品？回 _競品_"
        ))
        return

    # 走 multi-agent router
    try:
        from agent_router import respond
        r = respond(chat_id=str(chat_id), user_text=text, user_name=user_name)
        reply = r.get('reply') or '（系統暫時無法回應，已留紀錄）'

        # 附上 trace tail（讓使用者看到背後 agent + tools）
        trace_tail = ''
        chain = r.get('agent_chain', [])
        if len(chain) > 1:
            trace_tail += f"\n\n_🔄 Agent 鏈：{' → '.join(chain)}_"
        tools = r.get('tool_calls', [])
        if tools:
            tools_used = ', '.join(set(t['tool'] for t in tools))
            trace_tail += f"\n_🛠 工具：{tools_used}_"
        backend = r.get('backend')
        if backend:
            trace_tail += f"\n_⚙️ 後端：{backend}_"

        send_message(chat_id, reply + trace_tail)
    except Exception as e:
        _STATS['errors'] += 1
        tb = traceback.format_exc()
        _log('handler_error', {'chat_id': chat_id, 'error': str(e), 'tb': tb[-500:]})
        send_message(chat_id, f'⚠️ 系統處理時發生錯誤，已記錄。請稍候再試或換個說法。')


def _polling_loop():
    """背景 long-polling 主迴圈"""
    global _LAST_UPDATE_ID, _BOT_RUNNING
    _STATS['started_at'] = datetime.now().isoformat(timespec='seconds')

    while _BOT_RUNNING:
        try:
            r = requests.get(f'{API_BASE}/getUpdates', params={
                'offset':         _LAST_UPDATE_ID + 1,
                'timeout':        30,
                'allowed_updates': json.dumps(['message', 'edited_message']),
            }, timeout=35)
            data = r.json()
            if data.get('ok'):
                for update in data.get('result', []):
                    _LAST_UPDATE_ID = max(_LAST_UPDATE_ID, update['update_id'])
                    threading.Thread(target=_handle_update, args=(update,),
                                     daemon=True).start()
        except requests.exceptions.Timeout:
            continue
        except Exception as e:
            _STATS['errors'] += 1
            _log('polling_error', {'error': str(e)})
            time.sleep(3)


def start():
    """啟動 bot（在背景執行緒跑 polling）"""
    global _BOT_RUNNING, _BOT_THREAD
    if not TOKEN:
        return {'ok': False, 'error': 'TELEGRAM_BOT_TOKEN not set · 請設環境變數'}
    if _BOT_RUNNING:
        return {'ok': True, 'status': 'already running', 'stats': _STATS}
    me = get_me()
    if not me.get('ok'):
        return {'ok': False, 'error': f'token 無效：{me}'}
    _BOT_RUNNING = True
    _BOT_THREAD  = threading.Thread(target=_polling_loop, daemon=True)
    _BOT_THREAD.start()
    return {'ok': True, 'status': 'started', 'bot': me.get('result'), 'stats': _STATS}


def stop():
    """停止 bot"""
    global _BOT_RUNNING
    _BOT_RUNNING = False
    return {'ok': True, 'status': 'stopping', 'stats': _STATS}


def status():
    """取得 bot 狀態"""
    return {
        'running':      _BOT_RUNNING,
        'token_set':    bool(TOKEN),
        'last_update_id': _LAST_UPDATE_ID,
        'stats':        _STATS,
        'me':           get_me() if TOKEN else None,
    }


if __name__ == '__main__':
    import sys
    if not TOKEN:
        print('ERROR: TELEGRAM_BOT_TOKEN not set')
        print('Usage: set TELEGRAM_BOT_TOKEN=xxxx && python src/backend/telegram_live_bot.py')
        sys.exit(1)
    print('Starting addwii AI bot...')
    r = start()
    print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
    # 保持主執行緒
    try:
        while _BOT_RUNNING:
            time.sleep(10)
            print(f'[stats] in={_STATS["messages_in"]} out={_STATS["messages_out"]} err={_STATS["errors"]}')
    except KeyboardInterrupt:
        stop()
        print('Stopped.')
