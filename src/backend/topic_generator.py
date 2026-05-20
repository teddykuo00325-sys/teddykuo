# -*- coding: utf-8 -*-
"""凌策 addwii 行銷議題引擎

每日自動產出 1 個主題議題，來源混合 4 種：
  A. 環保署 air quality API（公開 · 無 token · 即時空汙紅燈站點）
  B. 季節 / 氣象事件（12 個月日曆 · 梅雨/沙塵/寒流/過敏季）
  C. 節慶 / 場景（母親節 / 大掃除 / 開學 / 過年）
  D. 預存議題庫（過敏 / 嬰兒呼吸 / 寵物 / 裝潢甲醛 ...）

輸出：
  {
    'date': '2026-05-20',
    'today_topic': {
      'title': '...',
      'category': 'air_quality' / 'season' / 'festival' / 'evergreen',
      'pain_points': [...],
      'hook_data': {...},  # 即時數字（PM2.5, AQI ...）
      'recommended_space': 'baby' / 'bedroom' / ...,
      'angle':  '銷售切入點',
      'source': '環保署 API'  / '季節庫'  ...,
    },
    'all_candidates': [...]
  }
"""
import os, json, time, random
from datetime import datetime, timedelta
from typing import Optional, List, Dict

# 暫存：今日議題 cache
_TOPIC_CACHE = {}
_CACHE_TS    = None


# ────────────────────────────────────────────────────────────
# A. 環保署空氣品質 API
# ────────────────────────────────────────────────────────────
EPA_API_URL = 'https://data.moenv.gov.tw/api/v2/aqx_p_432'
EPA_API_KEY = os.getenv('EPA_API_KEY', '')   # 選配


def fetch_epa_air_quality() -> dict:
    """拉環保署即時空汙資料。失敗回 None。"""
    try:
        import requests
        params = {'format': 'json', 'limit': 100, 'sort': 'pm2.5 desc'}
        if EPA_API_KEY: params['api_key'] = EPA_API_KEY
        r = requests.get(EPA_API_URL, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        records = data.get('records', [])
        # 萃取 PM2.5 紅燈站點
        red_alerts = []
        for rec in records[:50]:
            try:
                pm25 = float(rec.get('pm2.5', 0) or 0)
                if pm25 >= 35:  # WHO 24 小時建議 ≤ 25 / 紅害 ≥ 54
                    red_alerts.append({
                        'site':         rec.get('sitename', ''),
                        'county':       rec.get('county', ''),
                        'pm25':         pm25,
                        'aqi':          rec.get('aqi'),
                        'status':       rec.get('status', ''),
                        'pollutant':    rec.get('pollutant', ''),
                        'publish_time': rec.get('publishtime', ''),
                    })
            except Exception:
                continue
        return {
            'fetched_at':     datetime.now().isoformat(timespec='seconds'),
            'total_sites':    len(records),
            'red_alert_count': len(red_alerts),
            'red_alerts':     red_alerts[:5],
            'source':         '環保署即時空氣品質指標 API',
        }
    except Exception as e:
        return {'error': str(e), 'fallback': True}


# ────────────────────────────────────────────────────────────
# B. 季節庫（依台灣月份）
# ────────────────────────────────────────────────────────────
SEASON_TOPICS = {
    1:  {'theme': '寒流 + 室內密閉空污累積',  'pain': ['緊閉門窗導致 CO₂/PM2.5 累積', '冬季空氣含菌量高'], 'space': 'bedroom'},
    2:  {'theme': '春節大掃除揚塵',           'pain': ['打掃揚塵', '舊棉絮過敏'],                       'space': 'living'},
    3:  {'theme': '春季過敏季開始',           'pain': ['塵蟎/花粉爆量', '兒童氣喘加劇'],                'space': 'bedroom'},
    4:  {'theme': '梅雨季濕度 + 黴菌',         'pain': ['浴室發霉', '室內濕度 80%+', '黴菌孢子'],         'space': 'bathroom'},
    5:  {'theme': '母親節 + 為家人健康加倍',   'pain': ['媽媽長時間在家暴露', '為新生兒寶寶換新環境'],   'space': 'baby'},
    6:  {'theme': '梅雨後潮溼 + 異味殘留',     'pain': ['濕氣引發呼吸道', '梅雨黴味'],                   'space': 'bathroom'},
    7:  {'theme': '夏季冷氣密閉 + 異味循環',   'pain': ['冷氣關門關窗', '油煙倒灌'],                     'space': 'kitchen'},
    8:  {'theme': '颱風前後氣壓變化',         'pain': ['過敏加劇', '颱風揚塵'],                         'space': 'bedroom'},
    9:  {'theme': '開學季 + 家中小孩呼吸道',   'pain': ['幼兒園交叉感染', '回家帶病菌'],                 'space': 'baby'},
    10: {'theme': '秋季東北季風帶懸浮微粒',   'pain': ['空氣品質惡化', '夜咳患者增'],                   'space': 'bedroom'},
    11: {'theme': '冬季流感 + 室內病毒',       'pain': ['流感高峰', '密閉空間病毒'],                     'space': 'living'},
    12: {'theme': '歲末年終大掃除',           'pain': ['揚塵爆量', '甲醛家具搬入'],                     'space': 'living'},
}


# ────────────────────────────────────────────────────────────
# C. 節慶庫
# ────────────────────────────────────────────────────────────
FESTIVAL_TOPICS = [
    {'date_match': (5, 12), 'event': '母親節', 'theme': '為媽媽打造淨零呼吸',
     'pain': ['媽媽 24h 在家最久'], 'space': 'living'},
    {'date_match': (8, 8), 'event': '父親節', 'theme': '為爸爸守護臥室空氣',
     'pain': ['夜間鼻塞影響睡眠'], 'space': 'bedroom'},
    {'date_match': (10, 31), 'event': '萬聖節 + 派對', 'theme': '聚餐後空氣品質如何回復',
     'pain': ['多人室內聚會'], 'space': 'living'},
    {'date_match': (11, 11), 'event': '雙11 限時優惠', 'theme': 'addwii 雙11 限定促銷',
     'pain': ['節慶把握囤購'], 'space': 'baby'},
    {'date_match': (12, 25), 'event': '聖誕節', 'theme': '為家人添購健康禮物',
     'pain': ['節日送禮選擇'], 'space': 'living'},
]


# ────────────────────────────────────────────────────────────
# D. 常青議題庫
# ────────────────────────────────────────────────────────────
EVERGREEN_TOPICS = [
    {'title': '過敏兒家庭最該知道的 5 個 PM2.5 真相', 'space': 'bedroom',
     'pain': ['塵蟎', '空污', '夜咳'], 'category': 'allergy'},
    {'title': '新生兒呼吸道脆弱 · 嬰兒房 PM2.5 要 < 5 才安全', 'space': 'baby',
     'pain': ['新生兒哮喘', '呼吸道發育'], 'category': 'newborn'},
    {'title': '裝潢甲醛揮發 3 年 · 如何加速清除', 'space': 'living',
     'pain': ['甲醛', '裝潢氣味', 'TVOC'], 'category': 'renovation'},
    {'title': '寵物毛屑 + 異味 · 系統級全屋潔淨', 'space': 'living',
     'pain': ['寵物毛屑', '室內異味', '訪客過敏'], 'category': 'pet'},
    {'title': '廚房油煙 PM2.5 瞬間飆到 200+ · 該怎麼辦', 'space': 'kitchen',
     'pain': ['烹飪油煙', 'TVOC', '致癌物'], 'category': 'kitchen'},
    {'title': '梅雨季浴室霉味 · 排風 + 除濕 + HEPA 三合一', 'space': 'bathroom',
     'pain': ['黴菌', '濕度', '異味'], 'category': 'bathroom'},
    {'title': '上班族整天密閉冷氣 · 下班頭痛的原因', 'space': 'living',
     'pain': ['CO₂ 累積', '辦公密閉'], 'category': 'office'},
    {'title': '為什麼 850 CADR 的清淨機在 8 坪空間不夠用', 'space': 'living',
     'pain': ['CADR 不足', '清淨機選錯'], 'category': 'product_education'},
    {'title': 'WHO 年均 PM2.5 建議 ≦ 5 · 你家達標嗎', 'space': 'bedroom',
     'pain': ['WHO 標準', '健康量化'], 'category': 'health_standard'},
    {'title': '為什麼 addwii 41 場域實測 PM2.5 < 2 而競品 8-15', 'space': 'living',
     'pain': ['競品比較', '實測數據'], 'category': 'competitor'},
]


def _today_festival() -> Optional[dict]:
    now = datetime.now()
    for f in FESTIVAL_TOPICS:
        m, d = f['date_match']
        if now.month == m and abs(now.day - d) <= 3:
            return f
    return None


def generate_today_topic() -> dict:
    """產生今日議題（自動依當天決定走 A/B/C/D 哪條）"""
    global _CACHE_TS
    # 1h cache
    if _CACHE_TS and (datetime.now() - _CACHE_TS).total_seconds() < 3600 and 'today_topic' in _TOPIC_CACHE:
        return _TOPIC_CACHE

    now = datetime.now()
    candidates = []

    # A. 環保署 API · 若紅燈站點 > 0 → 高優先
    epa = fetch_epa_air_quality()
    if not epa.get('error') and epa.get('red_alert_count', 0) > 0:
        red = epa['red_alerts'][0]
        candidates.append({
            'title':     f'⚠️ 今日 {red["site"]} PM2.5 達 {red["pm25"]} μg/m³（{red["status"]}） · 家中防護重要',
            'category':  'air_quality_alert',
            'pain_points': [f'{red["county"]} {red["site"]} 達紅害等級', '今日室外空氣不宜開窗'],
            'hook_data':   red,
            'recommended_space': 'bedroom',
            'angle':       '即時新聞鉤 · 引導關注家中空氣品質 · CTA 看 addwii 41 場域實測 PM2.5 趨零',
            'source':      '環保署 air quality API',
            'priority':    'high',
        })

    # B. 季節庫
    season = SEASON_TOPICS.get(now.month, {})
    if season:
        candidates.append({
            'title':     f'{now.month} 月主題 · {season["theme"]}',
            'category':  'season',
            'pain_points': season['pain'],
            'recommended_space': season['space'],
            'angle':       f'季節性切入 · {now.month} 月典型空氣議題',
            'source':      '季節議題庫',
            'priority':    'medium',
        })

    # C. 節慶
    fest = _today_festival()
    if fest:
        candidates.append({
            'title':     f'{fest["event"]} 特別企劃 · {fest["theme"]}',
            'category':  'festival',
            'pain_points': fest['pain'],
            'recommended_space': fest['space'],
            'angle':       '節慶情感切入',
            'source':      '節慶議題庫',
            'priority':    'high' if fest['event'] in ('母親節', '雙11 限時優惠') else 'medium',
        })

    # D. 常青庫 · 補位
    evg = random.Random(now.toordinal()).choice(EVERGREEN_TOPICS)
    candidates.append({
        'title':     evg['title'],
        'category':  'evergreen',
        'pain_points': evg['pain'],
        'recommended_space': evg['space'],
        'angle':       'addwii 常青教育議題',
        'source':      f'常青議題庫（{evg["category"]}）',
        'priority':    'low',
    })

    # 選擇今日主議題（依 priority high > medium > low）
    priority_order = {'high': 0, 'medium': 1, 'low': 2}
    candidates.sort(key=lambda c: priority_order.get(c['priority'], 99))
    today = candidates[0] if candidates else None

    _TOPIC_CACHE.clear()
    _TOPIC_CACHE.update({
        'date':            now.strftime('%Y-%m-%d'),
        'generated_at':    now.isoformat(timespec='seconds'),
        'today_topic':     today,
        'all_candidates':  candidates,
        'epa_summary':     {'red_alert_count': epa.get('red_alert_count', 0),
                             'total_sites':     epa.get('total_sites', 0),
                             'fetched_at':      epa.get('fetched_at')},
    })
    _CACHE_TS = now
    return _TOPIC_CACHE


def generate_week_topics(days: int = 7) -> list:
    """產生未來 N 天的議題（給內容日曆用 · 簡化版：D 庫輪播）"""
    topics = []
    now = datetime.now()
    for i in range(days):
        d = now + timedelta(days=i)
        evg = EVERGREEN_TOPICS[(d.toordinal() + i) % len(EVERGREEN_TOPICS)]
        topics.append({
            'date':       d.strftime('%Y-%m-%d'),
            'weekday':    d.strftime('%a'),
            'title':      evg['title'],
            'space':      evg['space'],
            'pain':       evg['pain'],
            'category':   evg['category'],
        })
    return topics
