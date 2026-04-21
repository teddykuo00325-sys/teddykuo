# -*- coding: utf-8 -*-
"""
CRM Demo Data Seeder
為 3 家 tenant 建立完整的 pipeline demo 資料（詢問→報價→訂單→安裝）
給評審看「實際跑過完整流程」的證據
"""
from tenant_context import TENANT_CTX


LINGCE_DEMO = [
    # (公司, 聯絡, 電話, Email, 產業別, 模組, 來源, 需求說明, 推進到哪個階段)
    ('addwii 加我科技', '陳總監', '02-2345-6789', 'ceo@addwii.com', 'B2C 品牌',
     ['kb','cs','mkt','order','eta'], '官網', 'B2C 清淨機品牌數位轉型', 'installed'),
    ('MicroJet Technology', '林經理', '03-567-8900', 'pm@microjet.com.tw', '製造業',
     ['mat','po','sched','qa','doc'], 'Email', 'MEMS 壓電微泵產線 AI 化', 'ordered'),
    ('台積電測試專案', '王處長', '03-666-1234', 'test@tsmc.com', '製造業',
     ['qa','sched','kb','doc','meeting','cs','mat'], 'Email', '先進封裝 WP 品質 AI 分析 PoC', 'quoted'),
    ('維明顧問', '張副總', '02-8700-5566', 'service@weiming.com', '企業顧問',
     ['doc','meeting','kb','cs'], 'LINE', '顧問業知識管理 AI', 'quoted'),
]

MICROJET_DEMO = [
    ('奇景光電', '許採購', '03-568-0000', 'buyer@himax.com', '製造業',
     [('CJ-SENSOR-PRO', 6), ('SVC-MAINT-YR', 1)], 'Email', 'LCD 驅動產線精密感測', 'installed'),
    ('Panasonic 台灣', '吉田課長', '02-2758-0888', 'industrial@panasonic.tw', '製造業',
     [('CT-3DP-INDUST', 2), ('SVC-OEM-INT', 1)], '展會', '車用零件原型快速打樣', 'ordered'),
    ('聯發科 IoT 部門', '趙 PM', '03-5678-1234', 'iot-pm@mediatek.com', '製造業',
     [('MEMS-PUMP-P760', 50), ('CJ-SENSOR-STD', 20)], '官網', '穿戴裝置冷卻微泵專案', 'quoted'),
    ('台灣獸醫聯合診所', '謝醫師', '02-2707-5566', 'vet@clinic.tw', '其他',
     [('CJ-SENSOR-STD', 3)], '電話', '寵物醫院空氣品質監測', 'quoted'),
]

ADDWII_DEMO = [
    # addwii 個人客戶姓名以合規格式存入（姓+OO）
    ('陳 OO（個人）', '陳 OO', '0912-***-678', 'addwii-user01@masked.local', '個人消費者',
     [('HCR-200', 1), ('FILTER-H13', 1), ('SVC-INSTALL', 1)], '官網', '新生兒房空氣淨化', 'installed'),
    ('王 OO（個人）', '王 OO', '0933-***-456', 'addwii-user02@masked.local', '個人消費者',
     [('HCR-300', 1), ('SVC-WARR-PLUS', 1)], 'LINE', '客廳 + 開放式廚房', 'ordered'),
    ('林 OO（家庭）', '林 OO', '0922-***-111', 'addwii-user03@masked.local', '個人消費者',
     [('HCR-100', 2), ('FILTER-H13', 2)], '實體門市', '兩個小孩房間', 'quoted'),
    ('張 OO（個人）', '張 OO', '0988-***-222', 'addwii-user04@masked.local', '個人消費者',
     [('HCR-200', 1)], '官網', '臥室 + 書房', 'quoted'),
    ('李氏企業福委會', '李主委', '02-8833-1234', 'welfare@liusfamily.com', '買賣業',
     [('HCR-200', 8), ('HCR-300', 2), ('FILTER-H13', 10), ('SVC-INSTALL', 10)], '展會',
     '員工宿舍團購', 'installed'),
]


def _reset_tenant_db(bundle):
    """清空該 tenant 的 4 張表"""
    with bundle.crm._lock, bundle.crm._conn() as c:
        c.executescript("""
            DELETE FROM 安裝記錄;
            DELETE FROM 訂單;
            DELETE FROM 報價單;
            DELETE FROM 詢問單;
        """)


def _seed_lingce(force=False):
    bundle = TENANT_CTX.get('lingce')
    if force:
        _reset_tenant_db(bundle)
    crm = bundle.crm
    results = []
    for company, contact, phone, email, industry, mods, source, need, stage in LINGCE_DEMO:
        inq = crm.create_inquiry({
            '公司名稱': company, '聯絡人': contact, '電話': phone, 'Email': email,
            '產業別': industry, '需求說明': need, '選擇模組': mods, '來源': source,
        })
        if stage in ('quoted', 'ordered', 'installed'):
            q = crm.convert_to_quote(inq['詢問編號'])
            if stage in ('ordered', 'installed'):
                o = crm.accept_quote(q['報價編號'])
                if stage == 'installed':
                    ins = crm.start_installation(o['訂單編號'])
                    crm.complete_installation(ins['安裝編號'])
        results.append({'company': company, 'stage': stage})
    return results


def _seed_tenant_with_qty(tid, demo_list, force=False):
    bundle = TENANT_CTX.get(tid)
    if force:
        _reset_tenant_db(bundle)
    crm = bundle.crm
    results = []
    for company, contact, phone, email, industry, items, source, need, stage in demo_list:
        # items = [(product_id, qty), ...]
        mods = [x[0] for x in items]
        qty_map = {x[0]: x[1] for x in items}
        inq = crm.create_inquiry({
            '公司名稱': company, '聯絡人': contact, '電話': phone, 'Email': email,
            '產業別': industry, '需求說明': need, '選擇模組': mods,
            '數量': qty_map, '來源': source,
        })
        if stage in ('quoted', 'ordered', 'installed'):
            q = crm.convert_to_quote(inq['詢問編號'], quantities=qty_map)
            if stage in ('ordered', 'installed'):
                o = crm.accept_quote(q['報價編號'])
                if stage == 'installed':
                    ins = crm.start_installation(o['訂單編號'])
                    crm.complete_installation(ins['安裝編號'])
        results.append({'company': company, 'stage': stage})
    return results


def seed_all(force=False):
    """一鍵播種 3 家 tenant 的完整 demo pipeline"""
    out = {
        'lingce':   _seed_lingce(force=force),
        'microjet': _seed_tenant_with_qty('microjet', MICROJET_DEMO, force=force),
        'addwii':   _seed_tenant_with_qty('addwii',   ADDWII_DEMO,   force=force),
    }
    # 回傳 summary
    summaries = {}
    for tid in ('lingce','microjet','addwii','weiming'):
        summaries[tid] = TENANT_CTX.get(tid).crm.summary()
    return {'seeded': out, 'summaries': summaries}


if __name__ == '__main__':
    import json, sys
    force = '--force' in sys.argv
    r = seed_all(force=force)
    print(json.dumps(r, ensure_ascii=False, indent=2))
