# -*- coding: utf-8 -*-
"""
情緒分析標準測試資料集
對應 addwii_驗收評比標準_含測試題目v3.docx 測試題二：
  「噪音投訴 / 效果讚美 / 售後抱怨」3 筆真實客服紀錄
  驗收門檻：情緒分類準確率 ≥ 85%
"""

FEEDBACK_TEST_CASES = [
    {
        'id': 'TC-001',
        'content': '買了三個月，半夜運轉聲音像吹風機一樣吵，害小孩睡不著。房間明明 8 坪，低速也超過 50 分貝，完全不是官網說的 39 dB。',
        'expected': {
            'sentiment': '負面',
            'categories': ['硬體'],
            'reason':     '噪音投訴 — 實測分貝與官網不符',
        },
    },
    {
        'id': 'TC-002',
        'content': '裝在嬰兒房 2 個月，PM2.5 數值一直維持在 5 以下，小孩的過敏性鼻炎明顯改善。老婆說晚上終於能睡整夜了，謝謝 addwii。',
        'expected': {
            'sentiment': '正面',
            'categories': ['準確度', '服務'],
            'reason':     '效果讚美 — 對產品功能非常滿意',
        },
    },
    {
        'id': 'TC-003',
        'content': '濾網才用半年就壞了，我打客服等了 40 分鐘沒人接，LINE 也只有機器人。這個售後真的很差，下次不會再買了。',
        'expected': {
            'sentiment': '負面',
            'categories': ['硬體', '服務'],
            'reason':     '售後抱怨 — 客服響應速度差 + 耗材壽命短',
        },
    },
    # 擴充 7 筆，總共 10 筆讓準確率更有代表性
    {
        'id': 'TC-004',
        'content': '新買的 HCR-200 一週就當機了兩次，APP 也常連不上。是不是韌體問題？希望快點修好。',
        'expected': {
            'sentiment': '負面',
            'categories': ['硬體', '軟體'],
        },
    },
    {
        'id': 'TC-005',
        'content': '整體設計非常簡約漂亮，擺在客廳完全沒違和感，運作也很穩定。給五顆星。',
        'expected': {
            'sentiment': '正面',
            'categories': ['硬體'],
        },
    },
    {
        'id': 'TC-006',
        'content': '還沒收到東西，不予置評。',
        'expected': {
            'sentiment': '中性',
            'categories': ['其他'],
        },
    },
    {
        'id': 'TC-007',
        'content': '到府安裝的師傅很專業，解說也很清楚，給 addwii 服務團隊加分。',
        'expected': {
            'sentiment': '正面',
            'categories': ['服務'],
        },
    },
    {
        'id': 'TC-008',
        'content': '感測器數值一天比一天高，但我明明有定期換濾網。不知道是不是感測器壞了？客服能幫忙校正嗎？',
        'expected': {
            'sentiment': '負面',
            'categories': ['準確度', '硬體'],
        },
    },
    {
        'id': 'TC-009',
        'content': 'APP 介面改版後變得更好用了！尤其是趨勢圖那塊，讚。',
        'expected': {
            'sentiment': '正面',
            'categories': ['軟體'],
        },
    },
    {
        'id': 'TC-010',
        'content': '價格真的偏高，但比較過市面同級產品，CADR 比其他品牌強 2 倍，算是一分錢一分貨。',
        'expected': {
            'sentiment': '正面',
            'categories': ['其他'],
        },
    },
]


def run_accuracy_test(analyze_func):
    """
    用標準案例跑一次，回傳：
      - 準確率 (%)
      - 每題命中/未命中
      - 驗收門檻比對（≥ 85% 通過）
    analyze_func: 一個回傳 [{'id','sentiment','categories',...}] 的函式
    """
    records = [{'id': t['id'], 'customer': '測試', 'content': t['content']}
               for t in FEEDBACK_TEST_CASES]
    result = analyze_func(records, user='accuracy-test', use_ai=False)

    actual_map = {r['id']: r for r in result.get('records', [])}
    details = []
    hit = 0
    for tc in FEEDBACK_TEST_CASES:
        actual = actual_map.get(tc['id'], {})
        expected_sent = tc['expected']['sentiment']
        actual_sent   = actual.get('sentiment', '未判定')
        pass_sent = (actual_sent == expected_sent)
        if pass_sent: hit += 1
        details.append({
            'id':             tc['id'],
            'content_preview': tc['content'][:30] + '...',
            'expected':       expected_sent,
            'actual':         actual_sent,
            'pass':           pass_sent,
            'categories':     actual.get('categories', []),
            'suggestion':     actual.get('suggestion', ''),
        })

    total = len(FEEDBACK_TEST_CASES)
    accuracy = round(hit / total * 100, 1)
    return {
        'total_cases':    total,
        'hit':            hit,
        'miss':           total - hit,
        'accuracy_pct':   accuracy,
        'threshold_pct':  85,
        'pass_threshold': accuracy >= 85,
        'details':        details,
    }
