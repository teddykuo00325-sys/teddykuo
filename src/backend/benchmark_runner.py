# -*- coding: utf-8 -*-
"""
實測基準測試 Runner
提供可在驗收中心即時跑的三項客觀評分：
  1. 情緒分類準確率 (addwii 構面 2 / microjet 場景 D 的 ≥85%)
  2. PII 偵測 recall (addwii 構面 5 / microjet 場景 E 的 ≥95%)
  3. 工單分類 F1 score (microjet 場景 B 的 ≥0.85)

每個 runner 都回傳：
  { ok, accuracy/recall/f1, hit, miss, total, threshold, pass, details, elapsed_ms }
"""
from __future__ import annotations
import time, re
from typing import List, Dict, Any


# ═══════════════════════════════════════════════════════════
# 1. 情緒分類準確率（addwii 構面 2 · 對 ≥ 85% 門檻）
# ═══════════════════════════════════════════════════════════
def run_sentiment_accuracy() -> Dict[str, Any]:
    from acceptance_scenarios import analyze_feedback
    from feedback_test_cases import FEEDBACK_TEST_CASES
    t0 = time.time()
    records = [{'id': t['id'], 'customer': '測試', 'content': t['content']}
               for t in FEEDBACK_TEST_CASES]
    result = analyze_feedback(records, user='benchmark', use_ai=False)
    actual_map = {r['id']: r for r in result.get('records', [])}
    details = []
    hit = 0
    for tc in FEEDBACK_TEST_CASES:
        a = actual_map.get(tc['id'], {})
        exp = tc['expected']['sentiment']
        got = a.get('sentiment', '未判定')
        ok = (exp == got)
        if ok: hit += 1
        details.append({'id': tc['id'], 'expected': exp, 'actual': got, 'pass': ok,
                        'preview': tc['content'][:40] + '…'})
    total = len(FEEDBACK_TEST_CASES)
    acc = round(hit / total * 100, 1)
    return {
        'ok': True,
        'metric': 'accuracy_pct',
        'value': acc,
        'threshold': 85,
        'pass': acc >= 85,
        'hit': hit, 'miss': total - hit, 'total': total,
        'details': details,
        'elapsed_ms': int((time.time() - t0) * 1000),
        'note': f'對比 {total} 筆人工標記測試集',
    }


# ═══════════════════════════════════════════════════════════
# 2. PII 偵測 recall (≥ 95% 門檻)
# 在文本中埋 N 個已知 PII → 掃描 → 計算召回率
# ═══════════════════════════════════════════════════════════
# 埋設的已知 PII（每個類型多筆，模擬真實 Field Trial CSV）
PII_TEST_SAMPLES = [
    # TW_ID 身分證
    ('A123456789', 'TW_ID'),
    ('F234567890', 'TW_ID'),
    ('E298765432', 'TW_ID'),
    # TW_PHONE 手機
    ('0912-345-678', 'TW_PHONE'),
    ('0933 456 789', 'TW_PHONE'),
    ('0988765432', 'TW_PHONE'),
    # LANDLINE 市話
    ('02-2345-6789', 'LANDLINE'),
    ('(03) 567-8900', 'LANDLINE'),
    # EMAIL
    ('chen@example.com', 'EMAIL'),
    ('lin.jianhong@addwii.com', 'EMAIL'),
    ('test.user+abc@gmail.com', 'EMAIL'),
    # CREDIT 信用卡
    ('4532-1234-5678-9010', 'CREDIT'),
    ('5412 8888 7777 6666', 'CREDIT'),
    # TW_ADDR 地址
    ('台北市大安區和平東路二段 123 號 5F', 'TW_ADDR'),
    ('新北市板橋區中山路 1 段 50 號', 'TW_ADDR'),
    # CN_NAME 中文姓名
    ('陳雅婷', 'CN_NAME'),
    ('林建宏', 'CN_NAME'),
    ('黃志明', 'CN_NAME'),
    ('王小明', 'CN_NAME'),
]


def run_pii_recall() -> Dict[str, Any]:
    from pii_guard import mask_text
    t0 = time.time()
    # 將所有 PII 拼成一個 CSV 風格的測試文本
    lines = ['datetime,customer_name,phone,id_number,email,address,credit,comment']
    for i, (val, ptype) in enumerate(PII_TEST_SAMPLES):
        lines.append(f'2026-04-{15+(i%5):02d} 08:00,{val},{val},{val},{val},{val},{val},正常紀錄')
    test_text = '\n'.join(lines)

    masked, detections = mask_text(test_text, context='benchmark_pii_recall')
    detected_types = set(d.get('type') for d in detections)
    detected_values = set()
    for d in detections:
        # 從原文 slice 取出被偵測到的內容（approximate）
        detected_values.add((d.get('value') or '').strip())

    # 計算每個 PII 樣本是否有被偵測到（以 value 字串包含為準）
    hit_list = []
    miss_list = []
    for val, ptype in PII_TEST_SAMPLES:
        # 用「字串包含」判斷（實作 pii_guard 會 mask 原文，所以檢查 mask 後是否仍含原值）
        in_masked = val in masked
        detected = not in_masked
        if detected:
            hit_list.append({'value': val, 'type': ptype})
        else:
            miss_list.append({'value': val, 'type': ptype})

    hit = len(hit_list)
    total = len(PII_TEST_SAMPLES)
    recall = round(hit / total * 100, 1)
    return {
        'ok': True,
        'metric': 'recall_pct',
        'value': recall,
        'threshold': 95,
        'pass': recall >= 95,
        'hit': hit, 'miss': total - hit, 'total': total,
        'hit_list': hit_list[:20],
        'miss_list': miss_list,
        'detected_types': sorted(detected_types),
        'elapsed_ms': int((time.time() - t0) * 1000),
        'note': f'測試集含 {total} 筆已知 PII（{len(set(p[1] for p in PII_TEST_SAMPLES))} 類）',
    }


# ═══════════════════════════════════════════════════════════
# 3. 工單分類 F1 score (microjet 場景 B · ≥ 0.85 門檻)
# ═══════════════════════════════════════════════════════════
TICKET_TEST_CASES = [
    # 20 筆已標記客訴工單（涵蓋 6 類 + 3 緊急度）
    {'id':'TK-B01','content':'我上個月買的 MJ-3200 列印品質變差，再不處理要上網公開投訴！已打 0800 多次！',
     'expected_cat':'品質申訴', 'expected_urgency':'高'},
    {'id':'TK-B02','content':'印表機冒煙了，小孩在旁邊嚇壞了，我要聯絡消保官！',
     'expected_cat':'品質申訴', 'expected_urgency':'高'},
    {'id':'TK-B03','content':'MJ-3200 三週了都印不出來，APP 顯示 E-043 錯誤',
     'expected_cat':'維修', 'expected_urgency':'中'},
    {'id':'TK-B04','content':'想要退貨，沒用幾次品質不穩定',
     'expected_cat':'退貨', 'expected_urgency':'中'},
    {'id':'TK-B05','content':'新買的印表機無法開機，是不是瑕疵品？',
     'expected_cat':'維修', 'expected_urgency':'中'},
    {'id':'TK-B06','content':'CurieJet P760 裝不上 ESP32 開發板，驅動程式錯誤',
     'expected_cat':'相容性', 'expected_urgency':'低'},
    {'id':'TK-B07','content':'請問貴公司的 MJ-3200 支援 Mac 系統嗎？我的 driver 裝不上',
     'expected_cat':'相容性', 'expected_urgency':'低'},
    {'id':'TK-B08','content':'上月發票沒寄來，請協助補寄',
     'expected_cat':'帳務', 'expected_urgency':'低'},
    {'id':'TK-B09','content':'信用卡被重複扣款兩次，請盡快處理！',
     'expected_cat':'帳務', 'expected_urgency':'中'},
    {'id':'TK-B10','content':'剛買的機器連不上 Wi-Fi，網路設定都沒動',
     'expected_cat':'維修', 'expected_urgency':'低'},
    {'id':'TK-B11','content':'墨水匣 E-043 錯誤，是不是瑕疵？我要退貨',
     'expected_cat':'退貨', 'expected_urgency':'中'},
    {'id':'TK-B12','content':'客服打了 3 次沒人接，上週就反映問題',
     'expected_cat':'其他', 'expected_urgency':'中'},
    {'id':'TK-B13','content':'買了一週就壞了，不然就是瑕疵，要你們專人來換',
     'expected_cat':'品質申訴', 'expected_urgency':'中'},
    {'id':'TK-B14','content':'列印速度說是 42 ppm 但實測只有 20，廣告不實我要投訴',
     'expected_cat':'品質申訴', 'expected_urgency':'中'},
    {'id':'TK-B15','content':'APP 無法連線機器，改用有線也不行，已經三天了',
     'expected_cat':'維修', 'expected_urgency':'中'},
    {'id':'TK-B16','content':'怎麼這個產品連 Windows 11 都不支援？',
     'expected_cat':'相容性', 'expected_urgency':'低'},
    {'id':'TK-B17','content':'請問年度維護合約續約價格？',
     'expected_cat':'其他', 'expected_urgency':'低'},
    {'id':'TK-B18','content':'我要退款，拒絕付餘款，下週若沒處理好就上 Dcard 爆料',
     'expected_cat':'退貨', 'expected_urgency':'高'},
    {'id':'TK-B19','content':'帳單金額跟訂單不合，請核對',
     'expected_cat':'帳務', 'expected_urgency':'低'},
    {'id':'TK-B20','content':'列印品質穩定，很滿意',
     'expected_cat':'其他', 'expected_urgency':'低'},
]


def run_ticket_f1() -> Dict[str, Any]:
    """計算分類 F1（macro average）+ 緊急度 F1"""
    from microjet_scenarios import classify_ticket
    t0 = time.time()

    # 分類混淆矩陣
    cat_labels = ['退貨','維修','品質申訴','相容性','帳務','其他']
    urg_labels = ['高','中','低']
    cat_tp = {k: 0 for k in cat_labels}
    cat_fp = {k: 0 for k in cat_labels}
    cat_fn = {k: 0 for k in cat_labels}
    urg_tp = {k: 0 for k in urg_labels}
    urg_fp = {k: 0 for k in urg_labels}
    urg_fn = {k: 0 for k in urg_labels}
    details = []

    for tc in TICKET_TEST_CASES:
        cls = classify_ticket(tc['content'])
        got_cat = cls['category']
        got_urg = cls['urgency']
        exp_cat = tc['expected_cat']
        exp_urg = tc['expected_urgency']

        # 分類
        if got_cat == exp_cat: cat_tp[exp_cat] = cat_tp.get(exp_cat, 0) + 1
        else:
            cat_fp[got_cat] = cat_fp.get(got_cat, 0) + 1
            cat_fn[exp_cat] = cat_fn.get(exp_cat, 0) + 1
        # 緊急度
        if got_urg == exp_urg: urg_tp[exp_urg] = urg_tp.get(exp_urg, 0) + 1
        else:
            urg_fp[got_urg] = urg_fp.get(got_urg, 0) + 1
            urg_fn[exp_urg] = urg_fn.get(exp_urg, 0) + 1

        details.append({
            'id': tc['id'],
            'content_preview': tc['content'][:40] + '…',
            'category':  {'expected': exp_cat, 'actual': got_cat, 'pass': got_cat == exp_cat},
            'urgency':   {'expected': exp_urg, 'actual': got_urg, 'pass': got_urg == exp_urg},
        })

    # macro F1
    def _f1(tp, fp, fn):
        p = tp / (tp + fp) if (tp + fp) else 0
        r = tp / (tp + fn) if (tp + fn) else 0
        return 2 * p * r / (p + r) if (p + r) else 0

    cat_f1_per = {k: round(_f1(cat_tp[k], cat_fp[k], cat_fn[k]), 3) for k in cat_labels}
    urg_f1_per = {k: round(_f1(urg_tp[k], urg_fp[k], urg_fn[k]), 3) for k in urg_labels}
    cat_macro_f1 = round(sum(cat_f1_per.values()) / len(cat_labels), 3)
    urg_macro_f1 = round(sum(urg_f1_per.values()) / len(urg_labels), 3)

    # 以「緊急度 macro F1」為主指標（docx 明確提及 ≥ 0.85）
    pass_urg = urg_macro_f1 >= 0.85
    pass_cat_acc = sum(1 for d in details if d['category']['pass']) / len(details) >= 0.88

    return {
        'ok': True,
        'metric': 'urgency_macro_f1',
        'value': urg_macro_f1,
        'threshold': 0.85,
        'pass': pass_urg,
        'category_macro_f1': cat_macro_f1,
        'category_accuracy': round(sum(1 for d in details if d['category']['pass']) / len(details) * 100, 1),
        'urgency_accuracy':  round(sum(1 for d in details if d['urgency']['pass']) / len(details) * 100, 1),
        'urgency_f1_per_label': urg_f1_per,
        'category_f1_per_label': cat_f1_per,
        'total': len(TICKET_TEST_CASES),
        'details': details,
        'elapsed_ms': int((time.time() - t0) * 1000),
        'note': f'對比 {len(TICKET_TEST_CASES)} 筆人工標記測試集（6 分類 · 3 緊急度）',
    }


def run_all() -> Dict[str, Any]:
    t0 = time.time()
    try: sent = run_sentiment_accuracy()
    except Exception as e: sent = {'ok': False, 'error': str(e)}
    try: pii = run_pii_recall()
    except Exception as e: pii = {'ok': False, 'error': str(e)}
    try: tkt = run_ticket_f1()
    except Exception as e: tkt = {'ok': False, 'error': str(e)}
    return {
        'sentiment': sent,
        'pii':       pii,
        'tickets':   tkt,
        'total_elapsed_ms': int((time.time() - t0) * 1000),
        'summary': {
            'sentiment_pass': sent.get('pass', False),
            'pii_pass':       pii.get('pass', False),
            'tickets_pass':   tkt.get('pass', False),
            'all_pass': sent.get('pass') and pii.get('pass') and tkt.get('pass'),
        },
    }


if __name__ == '__main__':
    import json
    print(json.dumps(run_all(), ensure_ascii=False, indent=2))
