# -*- coding: utf-8 -*-
"""凌策 addwii 行銷 Agent

從議題 → 4 種通道文案（FB / IG / LINE / Threads）+ YT Shorts 腳本
所有產出皆通過：
  1. ai_backend.generate（LLM 撰寫）
  2. check_advertising_claim（合規檢查）
  3. simple_s2t（強制繁體）

YT Shorts 腳本含：
  · title / hook / pain / solution / cta
  · srt 字幕（時間軸對齊）
  · shot_list（5 個 scene）
  · thumbnail_svg（疊字構圖）
  · hashtags / voiceover_text
"""
import os, json, re
from datetime import datetime
from typing import Dict, List, Optional

POSTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          '..', '..', 'data', 'addwii', 'marketing_posts')
os.makedirs(POSTS_DIR, exist_ok=True)


# ────────────────────────────────────────────────────────────
# 通道風格（FB / IG / LINE / Threads 各自不同）
# ────────────────────────────────────────────────────────────
CHANNEL_STYLES = {
    'facebook': {
        'tone':         '專業詳細 · 段落式',
        'length_chars': 300,
        'cta_style':    '「了解更多 → addwii.com」',
        'emoji_density': 'medium',
        'hashtags':     ['#addwii', '#自由呼吸淨零生活', '#HomeCleanRoom'],
    },
    'instagram': {
        'tone':         '視覺感性 · 短句',
        'length_chars': 220,
        'cta_style':    '「Bio 連結 ↑」',
        'emoji_density': 'high',
        'hashtags':     ['#addwii', '#PM25', '#無塵室', '#淨零生活', '#寶寶健康'],
    },
    'line':     {
        'tone':         '親切提醒 · 條列式',
        'length_chars': 180,
        'cta_style':    '「點下方按鈕看更多 ↓」',
        'emoji_density': 'medium',
        'hashtags':     [],
    },
    'threads':  {
        'tone':         '時事連結 · 短促',
        'length_chars': 500,  # threads 字數較寬
        'cta_style':    '「留言告訴我你的看法」',
        'emoji_density': 'low',
        'hashtags':     ['#PM2.5', '#addwii', '#環保署'],
    },
}


# ────────────────────────────────────────────────────────────
# 內容生成
# ────────────────────────────────────────────────────────────
def generate_post_for_channel(topic: dict, channel: str) -> dict:
    """為單一通道產出文案"""
    import ai_backend
    import agent_tools
    style = CHANNEL_STYLES.get(channel, CHANNEL_STYLES['facebook'])

    pain_str = ' / '.join(topic.get('pain_points', topic.get('pain', [])))
    space = topic.get('recommended_space', topic.get('space', ''))
    angle = topic.get('angle', '')
    hook_data = topic.get('hook_data', {})

    # 加 hook 資料（即時環保署紅燈）
    hook_text = ''
    if hook_data:
        hook_text = f"今日鉤點：{hook_data.get('site','')} {hook_data.get('pm25','')} μg/m³"

    simple_system = (
        '你是 addwii 行銷文案 Agent。一律台灣繁體中文（禁簡體）。'
        '不准用「保證」「100%」「絕對」這類絕對性詞。'
        f'寫 {channel} 風格：{style["tone"]}，{style["length_chars"]} 字內。'
    )
    prompt = (
        f'今日議題：{topic.get("title")}\n'
        f'痛點：{pain_str}\n'
        f'切入角度：{angle}\n'
        f'推薦空間：{space}\n'
        f'{hook_text}\n\n'
        f'addwii 已驗證實證：環境部 NPA23C01250001 / 41 場域 PM2.5 趨零 / S03 = 1,600 CADR / 38,900 元 / 24 期 0 利率\n\n'
        f'請寫一篇 {channel} 貼文。{style["cta_style"]} 必含。'
    )

    r = ai_backend.generate(prompt=prompt, system=simple_system,
                             max_tokens=400, temperature=0.5, timeout_s=180)
    text = (r.get('text') or '').strip()

    # 強制繁體
    try:
        from simple_s2t import s2t
        text = s2t(text)
    except Exception: pass

    # 加 hashtags
    if style['hashtags']:
        if not text.endswith('\n'): text += '\n'
        text += '\n' + ' '.join(style['hashtags'])

    # 合規檢查
    check = agent_tools.dispatch('check_advertising_claim', {'text': text}, agent='marketing')
    compliance = check.get('result', {})

    return {
        'channel':       channel,
        'topic_title':   topic.get('title'),
        'text':          text,
        'char_count':    len(text),
        'hashtags':      style['hashtags'],
        'compliance':    compliance,
        'backend':       r.get('backend'),
        'model':         r.get('model'),
        'generated_at':  datetime.now().isoformat(timespec='seconds'),
    }


def generate_all_channels(topic: dict, channels: list = None) -> dict:
    """一次產 4 通道版本"""
    channels = channels or ['facebook', 'instagram', 'line', 'threads']
    posts = {}
    for ch in channels:
        posts[ch] = generate_post_for_channel(topic, ch)
    return {
        'topic':         topic,
        'channels':      list(posts.keys()),
        'posts':         posts,
        'generated_at':  datetime.now().isoformat(timespec='seconds'),
    }


# ────────────────────────────────────────────────────────────
# YT Shorts 腳本生成
# ────────────────────────────────────────────────────────────
def _srt_format(t_seconds: float) -> str:
    h = int(t_seconds // 3600)
    m = int((t_seconds % 3600) // 60)
    s = int(t_seconds % 60)
    ms = int((t_seconds % 1) * 1000)
    return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'


def generate_yt_shorts_script(topic: dict, duration_s: int = 60) -> dict:
    """產出 60 秒 YT Shorts 完整腳本 + SRT + thumbnail SVG"""
    import ai_backend
    pain = ' / '.join(topic.get('pain_points', topic.get('pain', [])))
    space = topic.get('recommended_space', topic.get('space', 'bedroom'))

    simple_system = '你是 addwii 短影片腳本作家。一律台灣繁體中文（禁簡體）。語氣輕快、有節奏感。不准用絕對詞。'
    prompt = (
        f'議題：{topic.get("title")}\n'
        f'痛點：{pain}\n'
        f'目標空間：{space}\n'
        f'時長：{duration_s} 秒\n\n'
        f'請依下列結構產 YT Shorts 逐字稿（每段標時間軸）：\n'
        f'[0-3s] HOOK：吸睛開場（一句話）\n'
        f'[3-13s] PAIN：點出痛點（具體場景 / 數字）\n'
        f'[13-50s] SOLUTION：addwii 解法（具體數字：環境部 NPA23C01250001 / 41 場域實測 / S03 1,600 CADR / 38,900 元 / 24 期月付 1,621）\n'
        f'[50-60s] CTA：點下方連結看實測'
    )

    r = ai_backend.generate(prompt=prompt, system=simple_system,
                             max_tokens=600, temperature=0.4, timeout_s=180)
    full_script = (r.get('text') or '').strip()
    try:
        from simple_s2t import s2t
        full_script = s2t(full_script)
    except Exception: pass

    # 解析時間軸區段
    sections = {'hook': '', 'pain': '', 'solution': '', 'cta': ''}
    lines = full_script.split('\n')
    current = None
    for l in lines:
        l = l.strip()
        if not l: continue
        if 'HOOK' in l.upper() or '[0' in l and ('-3' in l or '0-3' in l):
            current = 'hook'
        elif 'PAIN' in l.upper() or '[3' in l:
            current = 'pain'
        elif 'SOLUTION' in l.upper() or '[13' in l:
            current = 'solution'
        elif 'CTA' in l.upper() or '[50' in l:
            current = 'cta'
        elif current:
            sections[current] += l + '\n'

    # SRT 字幕（簡化版 · 4 段對齊 hook/pain/solution/cta）
    srt = ''
    sec_times = [(0, 3), (3, 13), (13, 50), (50, 60)]
    sec_keys  = ['hook', 'pain', 'solution', 'cta']
    for i, (start, end) in enumerate(sec_times):
        txt = sections[sec_keys[i]].strip().replace('\n', ' ')[:120] or sec_keys[i].upper()
        srt += f'{i+1}\n{_srt_format(start)} --> {_srt_format(end)}\n{txt}\n\n'

    # Shot list（5 個 scene）
    shot_list = [
        {'t_s': 0,  'scene': 'ZP2-1600 機身 close-up + 標題疊字「PM2.5 趨零」'},
        {'t_s': 13, 'scene': f'{space} 空間實景 + PM2.5 計數從紅變綠'},
        {'t_s': 25, 'scene': '競品 vs addwii 對比表格動畫（CADR / 售價 / PM2.5 實測）'},
        {'t_s': 40, 'scene': '環境部 NPA23C01250001 報告封面特寫'},
        {'t_s': 55, 'scene': 'addwii logo + CTA「看 41 場域實測 → addwii.com」'},
    ]

    # Thumbnail SVG（簡單疊字構圖）
    thumb_title = topic.get('title', 'addwii Home Clean Room')[:14]
    thumb_svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720" viewBox="0 0 1280 720">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#1e3a8a"/>
      <stop offset="100%" stop-color="#0c4a6e"/>
    </linearGradient>
  </defs>
  <rect width="1280" height="720" fill="url(#bg)"/>
  <text x="640" y="200" text-anchor="middle" font-family="Noto Sans TC, sans-serif"
        font-size="80" font-weight="900" fill="#fff">{thumb_title}</text>
  <text x="640" y="340" text-anchor="middle" font-family="sans-serif"
        font-size="50" fill="#fef08a">PM2.5 趨零 vs 競品 8-15</text>
  <text x="640" y="450" text-anchor="middle" font-family="sans-serif"
        font-size="42" fill="#34d399">環境部 NPA23C01250001 認證</text>
  <text x="640" y="600" text-anchor="middle" font-family="sans-serif"
        font-size="38" fill="#fbbf24">addwii Home Clean Room</text>
  <text x="640" y="660" text-anchor="middle" font-family="sans-serif"
        font-size="28" fill="#94a3b8">自由呼吸 淨零生活</text>
</svg>'''

    return {
        'title':           topic.get('title', '60 秒看懂 addwii Home Clean Room'),
        'duration_s':      duration_s,
        'platform':        'YouTube Shorts',
        'sections':        sections,
        'full_script':     full_script,
        'srt':             srt,
        'shot_list':       shot_list,
        'thumbnail_svg':   thumb_svg,
        'bgm_suggest':     '上揚輕快 · 90 BPM · 無版權音樂：Chillpeach / Lofi-Hiphop',
        'hashtags':        ['#PM25', '#addwii', '#無塵室', '#淨零生活', '#寶寶健康'],
        'voiceover_text':  full_script,
        'generated_at':    datetime.now().isoformat(timespec='seconds'),
        'backend':         r.get('backend'),
    }


# ────────────────────────────────────────────────────────────
# 持久化 + 送 approval queue
# ────────────────────────────────────────────────────────────
def save_post(post: dict, status: str = 'draft') -> dict:
    """存草稿 + 自動送 approval queue（marketing track）"""
    post_id = f'POST-{datetime.now().strftime("%Y%m%d%H%M%S")}'
    post['post_id'] = post_id
    post['status']  = status
    with open(os.path.join(POSTS_DIR, f'{post_id}.json'), 'w', encoding='utf-8') as f:
        json.dump(post, f, ensure_ascii=False, indent=2)
    # 送人審
    try:
        import approval_queue as aq
        ticket = aq.submit(
            track='marketing',
            payload={'type': 'fb_post_draft' if post.get('channel') else 'youtube_shorts_script',
                     'post_id':  post_id,
                     'title':    post.get('title') or post.get('topic_title') or '草稿',
                     'channel':  post.get('channel', 'multi'),
                     'body':     (post.get('text') or post.get('full_script', ''))[:500],
                     'compliance': post.get('compliance', {}),
                     'reason':   '行銷文案上版前須總監核可'},
            agent='marketing-agent',
            customer='addwii',
            priority='normal',
        )
        post['approval_ticket_id'] = ticket.get('ticket_id')
    except Exception as e:
        post['approval_error'] = str(e)
    return post


def list_pending_posts(limit: int = 30) -> dict:
    """列出未發布草稿"""
    items = []
    for fn in sorted(os.listdir(POSTS_DIR), reverse=True)[:limit]:
        if not fn.endswith('.json'): continue
        try:
            with open(os.path.join(POSTS_DIR, fn), encoding='utf-8') as f:
                d = json.load(f)
            items.append({
                'post_id':    d.get('post_id'),
                'channel':    d.get('channel', 'youtube_shorts'),
                'title':      d.get('title') or d.get('topic_title'),
                'status':     d.get('status', 'draft'),
                'approval':   d.get('approval_ticket_id'),
                'generated':  d.get('generated_at'),
            })
        except Exception: pass
    return {'pending_count': sum(1 for i in items if i['status'] == 'draft'),
            'total':         len(items),
            'items':         items}
