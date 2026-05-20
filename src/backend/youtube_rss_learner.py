# -*- coding: utf-8 -*-
"""addwii YouTube 頻道風格學習（公開 RSS · 無需 OAuth）

從 https://www.youtube.com/@addwii1650 拉公開 RSS feed，
萃取既有影片的：標題模式 / 內容主題 / 發布頻率 / 命名規範。
讓行銷 Agent 產新內容時自動套用相同風格。

RSS URL：
  · @-handle → 需先解出 channel_id
  · 直接 RSS: https://www.youtube.com/feeds/videos.xml?channel_id=UCxxx

我們先試 @ handle 抓首頁萃取 channel_id（公開資料），
若失敗用預存風格 fallback。
"""
import os, json, re, time
from datetime import datetime
from typing import Optional, List

STYLE_CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 '..', '..', 'data', 'addwii', 'youtube_style.json')
os.makedirs(os.path.dirname(STYLE_CACHE_PATH), exist_ok=True)

ADDWII_YT_HANDLE = '@addwii1650'
ADDWII_YT_URL    = 'https://www.youtube.com/@addwii1650'


def _try_resolve_channel_id(handle_url: str) -> Optional[str]:
    """從 @handle 頁面抓 channel_id"""
    try:
        import requests
        r = requests.get(handle_url, timeout=15,
                          headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code != 200: return None
        # 從 HTML 抓 "channelId":"UC..."
        m = re.search(r'"channelId":"(UC[A-Za-z0-9_-]{20,})"', r.text)
        if m: return m.group(1)
        m = re.search(r'channel_id=(UC[A-Za-z0-9_-]{20,})', r.text)
        if m: return m.group(1)
        m = re.search(r'(/channel/UC[A-Za-z0-9_-]{20,})', r.text)
        if m: return m.group(1).rsplit('/', 1)[1]
    except Exception:
        pass
    return None


def _fetch_rss(channel_id: str) -> Optional[dict]:
    """拉 RSS XML 並解析"""
    try:
        import requests
        from xml.etree import ElementTree as ET
        url = f'https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}'
        r = requests.get(url, timeout=15)
        if r.status_code != 200: return None
        root = ET.fromstring(r.text)
        ns = {'atom': 'http://www.w3.org/2005/Atom',
              'yt':   'http://www.youtube.com/xml/schemas/2015',
              'media': 'http://search.yahoo.com/mrss/'}
        videos = []
        for entry in root.findall('atom:entry', ns):
            title_e = entry.find('atom:title', ns)
            published_e = entry.find('atom:published', ns)
            link_e = entry.find('atom:link', ns)
            id_e = entry.find('yt:videoId', ns)
            desc_e = entry.find('media:group/media:description', ns)
            videos.append({
                'title':     title_e.text if title_e is not None else '',
                'published': published_e.text if published_e is not None else '',
                'video_id':  id_e.text if id_e is not None else '',
                'url':       link_e.attrib.get('href', '') if link_e is not None else '',
                'description': (desc_e.text or '')[:300] if desc_e is not None else '',
            })
        return {
            'channel_id': channel_id,
            'video_count': len(videos),
            'videos': videos,
        }
    except Exception as e:
        return None


def _analyze_style(videos: list) -> dict:
    """分析既有影片的標題模式 / 主題分佈"""
    if not videos: return {}

    # 標題長度統計
    title_lens = [len(v['title']) for v in videos if v.get('title')]
    avg_title_len = sum(title_lens) / len(title_lens) if title_lens else 0

    # 標題前綴模式（如「【】」「| |」「 - 」分隔器）
    delimiters = {'【': 0, '｜': 0, '|': 0, '：': 0, ' - ': 0, '？': 0, '！': 0}
    for v in videos:
        for d in delimiters:
            if d in v['title']: delimiters[d] += 1

    # 關鍵字提取
    keywords = {}
    for v in videos:
        for kw in re.findall(r'[一-鿿]{2,4}', v['title']):
            keywords[kw] = keywords.get(kw, 0) + 1
    top_keywords = sorted(keywords.items(), key=lambda x: -x[1])[:15]

    # 發布間隔
    dates = sorted([v['published'][:10] for v in videos if v.get('published')], reverse=True)
    most_recent = dates[0] if dates else 'unknown'
    publish_span = None
    if len(dates) >= 2:
        from datetime import datetime as dt
        try:
            d1 = dt.fromisoformat(dates[0])
            d_last = dt.fromisoformat(dates[-1])
            publish_span = (d1 - d_last).days
        except: pass

    return {
        'analyzed_count':    len(videos),
        'avg_title_length':  round(avg_title_len, 1),
        'common_delimiters': {k: v for k, v in delimiters.items() if v >= 2},
        'top_keywords':      top_keywords,
        'most_recent_video': most_recent,
        'publish_span_days': publish_span,
        'sample_titles':     [v['title'] for v in videos[:5]],
    }


def learn_style(force_refresh: bool = False) -> dict:
    """主入口：拉 RSS · 分析 · 寫入 cache"""
    # 1. cache 24h 內直接回
    if not force_refresh and os.path.exists(STYLE_CACHE_PATH):
        try:
            with open(STYLE_CACHE_PATH, encoding='utf-8') as f:
                cached = json.load(f)
            ts = datetime.fromisoformat(cached.get('learned_at', '2000-01-01'))
            if (datetime.now() - ts).days < 1:
                return cached
        except Exception: pass

    # 2. resolve channel_id
    channel_id = _try_resolve_channel_id(ADDWII_YT_URL)
    if not channel_id:
        # fallback: 用 KB 預存風格
        return _fallback_style()

    # 3. 拉 RSS
    feed = _fetch_rss(channel_id)
    if not feed:
        return _fallback_style(channel_id=channel_id)

    # 4. 分析風格
    style = _analyze_style(feed['videos'])

    # 5. 組裝結果
    result = {
        'channel_id':      channel_id,
        'channel_url':     ADDWII_YT_URL,
        'channel_handle':  ADDWII_YT_HANDLE,
        'video_count':     feed['video_count'],
        'recent_videos':   feed['videos'][:10],
        'style_analysis':  style,
        'style_summary':   _gen_style_summary(style),
        'learned_at':      datetime.now().isoformat(timespec='seconds'),
        'source':          'public RSS · no OAuth',
    }

    # 6. cache
    with open(STYLE_CACHE_PATH, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return result


def _gen_style_summary(style: dict) -> str:
    """產出人類可讀的風格摘要 · 給行銷 Agent 當 system prompt 用"""
    if not style: return '頻道風格：尚未抓到資料 · 用 KB 預存風格'
    parts = []
    if style.get('avg_title_length'):
        parts.append(f'標題平均 {style["avg_title_length"]} 字')
    if style.get('common_delimiters'):
        dms = ', '.join(style['common_delimiters'].keys())
        parts.append(f'常用分隔符：{dms}')
    if style.get('top_keywords'):
        kws = ', '.join(k for k, _ in style['top_keywords'][:8])
        parts.append(f'高頻詞：{kws}')
    return ' · '.join(parts) if parts else '預設風格'


def _fallback_style(channel_id: str = None) -> dict:
    """RSS 失敗時退回 KB 預存風格"""
    return {
        'channel_id':      channel_id,
        'channel_url':     ADDWII_YT_URL,
        'channel_handle':  ADDWII_YT_HANDLE,
        'source':          'KB fallback (RSS not available)',
        'style_summary':   '專業、溫暖、可信賴 · 繁體中文字幕 · 品牌色（深藍 + 白）',
        'style_analysis':  {},
        'recent_videos':   [],
        'video_count':     0,
        'learned_at':      datetime.now().isoformat(timespec='seconds'),
        'content_pillars': [
            '產品介紹（ZP2 系列 / S03-S12）',
            '場域實測（41 場 PM2.5 趨零驗證）',
            '客戶見證（過敏兒 / 新生兒家庭）',
            '健康議題（PM2.5 / 空汙 / 過敏）',
        ],
    }
