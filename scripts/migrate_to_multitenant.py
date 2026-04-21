# -*- coding: utf-8 -*-
"""
多租戶資料遷移腳本（一次性）
將現有單一 lingce_crm.db / org_data.json 拆分為 4 個租戶獨立資料：
  - lingce   (凌策自己 · 1 老闆 + 10 AI Agent)
  - microjet (134 人 · B2B 製造)
  - addwii   (6 人 · B2C 品牌)
  - weiming  (評估中)
"""
import os, json, shutil, sqlite3
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
CHAT_LOGS = os.path.join(ROOT, 'chat_logs')
TENANTS = ['lingce', 'microjet', 'addwii', 'weiming']

# ─── 步驟 1：建 data/<tenant>/ 目錄結構 ───
print('=' * 60)
print('  多租戶資料遷移')
print('=' * 60)
for t in TENANTS:
    for sub in ['audit', 'leave_overtime', 'attendance_analytics', 'chat_rooms']:
        os.makedirs(os.path.join(DATA, t, sub), exist_ok=True)
    print(f'  [v] 建立 data/{t}/')

# ─── 步驟 2：拆分 org_data.json ───
print('\n[2/6] 拆分組織資料...')
src_org = os.path.join(CHAT_LOGS, 'org_data.json')
if os.path.exists(src_org):
    with open(src_org, 'r', encoding='utf-8') as f:
        all_members = json.load(f)
else:
    all_members = []

# 分類規則：
# - dept 含 'addwii' → addwii
# - 其他所有 → microjet（含集團董事會/總經理室/人事總務/MIS/財務/...）
by_tenant = {'lingce': [], 'microjet': [], 'addwii': [], 'weiming': []}
for m in all_members:
    dept = m.get('dept', '')
    if 'addwii' in dept.lower():
        by_tenant['addwii'].append(m)
    else:
        by_tenant['microjet'].append(m)

# ─── 凌策自己的組織：1 位老闆 + 10 個 AI Agent ───
LINGCE_ORG = [
    {'id': 'LC-BOSS',   'name': '凌策老闆', 'role': '經理', 'dept': '凌策管理層',
     'supervisor_id': None, 'avatar': '👑', 'is_hr': True, 'title': '創辦人 / 唯一人類員工'},
    # 10 AI Agents (與 DATA.agents 對應)
    {'id': 'AI-ORCH', 'name': 'Orchestrator', 'role': '工程師', 'dept': '指揮中心',
     'supervisor_id': 'LC-BOSS', 'avatar': '🎯', 'is_hr': False, 'title': 'AI 協調指揮'},
    {'id': 'AI-BD',   'name': 'BD Agent',     'role': '工程師', 'dept': '業務開發',
     'supervisor_id': 'AI-ORCH', 'avatar': '🤝', 'is_hr': False, 'title': 'AI 業務'},
    {'id': 'AI-CS',   'name': '客服 Agent',   'role': '工程師', 'dept': '業務開發',
     'supervisor_id': 'AI-ORCH', 'avatar': '💬', 'is_hr': False, 'title': 'AI 客服'},
    {'id': 'AI-PROP', 'name': '提案 Agent',   'role': '工程師', 'dept': '業務開發',
     'supervisor_id': 'AI-ORCH', 'avatar': '📋', 'is_hr': False, 'title': 'AI 提案'},
    {'id': 'AI-FE',   'name': '前端 Agent',   'role': '工程師', 'dept': '技術研發',
     'supervisor_id': 'AI-ORCH', 'avatar': '🎨', 'is_hr': False, 'title': 'AI 前端'},
    {'id': 'AI-BE',   'name': '後端 Agent',   'role': '工程師', 'dept': '技術研發',
     'supervisor_id': 'AI-ORCH', 'avatar': '⚙️', 'is_hr': False, 'title': 'AI 後端'},
    {'id': 'AI-QA',   'name': 'QA Agent',     'role': '工程師', 'dept': '技術研發',
     'supervisor_id': 'AI-ORCH', 'avatar': '🔍', 'is_hr': False, 'title': 'AI 品管'},
    {'id': 'AI-FIN',  'name': '財務 Agent',   'role': '工程師', 'dept': '營運管理',
     'supervisor_id': 'AI-ORCH', 'avatar': '💰', 'is_hr': False, 'title': 'AI 財務'},
    {'id': 'AI-LEGAL','name': '法務 Agent',   'role': '工程師', 'dept': '營運管理',
     'supervisor_id': 'AI-ORCH', 'avatar': '⚖️', 'is_hr': False, 'title': 'AI 法務'},
    {'id': 'AI-DOC',  'name': '文件 Agent',   'role': '工程師', 'dept': '營運管理',
     'supervisor_id': 'AI-ORCH', 'avatar': '📄', 'is_hr': False, 'title': 'AI 文件'},
]
by_tenant['lingce'] = LINGCE_ORG

# 寫入 4 個 org.json
for t, members in by_tenant.items():
    path = os.path.join(DATA, t, 'org.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(members, f, ensure_ascii=False, indent=2)
    print(f'  lingce/{t}/org.json  → {len(members):>3d} 位')

# ─── 步驟 3：建 4 個空的 CRM SQLite DB ───
print('\n[3/6] 建立 4 個獨立 CRM 資料庫...')
for t in TENANTS:
    db_path = os.path.join(DATA, t, 'crm.db')
    if os.path.exists(db_path):
        os.remove(db_path)
    conn = sqlite3.connect(db_path)
    # 這裡只建空檔案；CRMManager 啟動時會自動建 schema
    conn.close()
    print(f'  data/{t}/crm.db (清空)')

# ─── 步驟 4：每 tenant 示範資料 ───
print('\n[4/6] 塞示範 CRM 資料（每 tenant 3~5 筆）...')

# 用 CRMManager 塞資料確保 schema 正確
import sys
sys.path.insert(0, os.path.join(ROOT, 'src', 'backend'))
from crm_manager import CRMManager

DEMO_DATA = {
    'lingce': [
        {'公司名稱': 'addwii 加我科技', '聯絡人': 'ADW-001 執行長', '電話': '02-1234-5678',
         'Email': 'ceo@addwii-demo.com', '產業別': 'B2C 品牌', '需求說明': '導入 AI 內容行銷 + 客訴情緒分析',
         '選擇模組': ['mkt', 'cust', 'kb', 'cs'], '來源': '官網', '備註': '月費 85 折（7 項以上）'},
        {'公司名稱': 'MicroJet Technology', '聯絡人': 'MGR-001 總經理', '電話': '02-9876-5432',
         'Email': 'mgr@microjet-demo.com', '產業別': '製造業', '需求說明': '產品 Q&A 知識庫 + CSV 洞察 + PII 合規',
         '選擇模組': ['kb', 'cs', 'qa', 'sched'], '來源': 'Email', '備註': '134 人規模授權'},
        {'公司名稱': '台積電測試專案', '聯絡人': '王主管', '電話': '03-5678-9012',
         'Email': 'wang@tsmc-demo.com', '產業別': '製造業', '需求說明': 'AI 品質分析提升良率',
         '選擇模組': ['qa', 'sched', 'po', 'mat'], '來源': '官網', '備註': '等待 NDA 簽署'},
        {'公司名稱': '維明顧問', '聯絡人': '王顧問', '電話': '0912-345-678',
         'Email': 'wei@weiming-demo.com', '產業別': '顧問業', '需求說明': '評估中',
         '選擇模組': ['doc', 'meeting'], '來源': 'LINE', '備註': 'BD Agent 持續訪談'},
    ],
    'microjet': [
        {'公司名稱': 'addwii 加我科技', '聯絡人': '吳OO 採購經理', '電話': '02-1234-5678',
         'Email': 'purchase@addwii-demo.com', '產業別': 'B2C 品牌',
         '需求說明': 'CurieJet P760 × 2 + P710 × 1（陳先生 12 坪案專用）',
         '選擇模組': [], '來源': 'Email', '備註': 'PO-ADW-2026-0117，NT$ 8,800'},
        {'公司名稱': '奇景光電', '聯絡人': '陳OO 採購部', '電話': '03-8888-7777',
         'Email': 'chen@himax-demo.com', '產業別': '製造業',
         '需求說明': 'ComeTrue T10 3D 列印機 × 1 導入評估',
         '選擇模組': [], '來源': '電話', '備註': 'POC 試印階段'},
        {'公司名稱': 'Panasonic 台灣', '聯絡人': '林OO 研發主管', '電話': '02-3333-4444',
         'Email': 'lin@panasonic-tw-demo.com', '產業別': '製造業',
         '需求說明': 'MEMS 壓電微泵 大量導入',
         '選擇模組': [], '來源': 'Email', '備註': '年度採購合約議價中'},
        {'公司名稱': '台灣獸醫聯合診所', '聯絡人': '黃OO 醫師', '電話': '0912-555-666',
         'Email': 'huang@vet-demo.com', '產業別': '醫療',
         '需求說明': 'CurieJet P760 用於寵物呼吸監測',
         '選擇模組': [], '來源': '官網', '備註': '小量試用 10 套'},
    ],
    'addwii': [
        {'公司名稱': '陳先生', '聯絡人': '陳先生', '電話': '0912-345-678',
         'Email': 'chen@personal-demo.com', '產業別': 'B2C 個人',
         '需求說明': '12 坪客廳無塵室整機（HCR-300 等級）',
         '選擇模組': [], '來源': '官網', '備註': 'ORD-2026-0028，NT$ 168,000（已付訂金 50%）'},
        {'公司名稱': '王小姐', '聯絡人': '王小姐', '電話': '0921-888-999',
         'Email': 'wang@personal-demo.com', '產業別': 'B2C 個人',
         '需求說明': '8 坪臥室無塵室（HCR-200）',
         '選擇模組': [], '來源': '官網', '備註': 'ORD-2026-0027，NT$ 118,000，安裝中'},
        {'公司名稱': '林媽媽', '聯絡人': '林媽媽', '電話': '0933-111-222',
         'Email': 'lin@personal-demo.com', '產業別': 'B2C 個人',
         '需求說明': '4 坪嬰兒房無塵室（HCR-100）',
         '選擇模組': [], '來源': 'LINE', '備註': 'ORD-2026-0026，NT$ 98,000，已完工'},
        {'公司名稱': '張先生', '聯絡人': '張先生', '電話': '0939-777-888',
         'Email': 'chang@personal-demo.com', '產業別': 'B2C 個人',
         '需求說明': '6 坪廚房無塵室（含油煙過濾）',
         '選擇模組': [], '來源': '電話', '備註': '報價單已送出'},
        {'公司名稱': '李氏企業福委會', '聯絡人': '李先生', '電話': '07-2222-3333',
         'Email': 'li@company-demo.com', '產業別': 'B2B 企業採購',
         '需求說明': '公司會議室 × 5 間部署（約 20 坪）',
         '選擇模組': [], '來源': '展場', '備註': '5 台 HCR-300 團購'},
    ],
    'weiming': [],  # 評估中，無客戶
}

# 產業別對應（CRM schema 只允許 4 值）
INDUSTRY_MAP = {
    'B2C 品牌': '買賣業', 'B2C 個人': '其他', 'B2B 企業採購': '買賣業',
    '顧問業': '其他', '醫療': '其他',
}
for t, cases in DEMO_DATA.items():
    db_path = os.path.join(DATA, t, 'crm.db')
    mgr = CRMManager(db_path=db_path)
    for c in cases:
        c_copy = dict(c)
        c_copy['產業別'] = INDUSTRY_MAP.get(c.get('產業別', ''), c.get('產業別', '其他'))
        mgr.create_inquiry(c_copy)
    print(f'  data/{t}/crm.db  → {len(cases)} 筆詢問單')

# ─── 步驟 5：遷移稽核 log（共享檔分到 lingce）───
print('\n[5/6] 遷移稽核紀錄...')
AUDIT_FILES_TO_LINGCE = [
    'acceptance_audit.jsonl', 'pii_audit.jsonl', 'human_gate.jsonl',
    'website_inquiries.jsonl', 'tasks.json', 'audit_log.jsonl',
    'procurement_state.json',  # 跨 tenant 共享，但留在 lingce audit
]
for fn in AUDIT_FILES_TO_LINGCE:
    src = os.path.join(CHAT_LOGS, fn)
    dst = os.path.join(DATA, 'lingce', 'audit', fn)
    if os.path.exists(src):
        shutil.copy2(src, dst)
        print(f'  lingce/audit/{fn}')

# attendance_analytics 分 tenant（目前只有 lingce 有）
src_aa = os.path.join(CHAT_LOGS, 'attendance_analytics')
if os.path.isdir(src_aa):
    for t in ['microjet', 'addwii']:
        dst = os.path.join(DATA, t, 'attendance_analytics')
        if os.path.exists(dst): shutil.rmtree(dst)
        shutil.copytree(src_aa, dst)
        print(f'  → data/{t}/attendance_analytics/')

# 聊天室：依成員分類到所屬 tenant
all_microjet_ids = {m['id'] for m in by_tenant['microjet']}
all_addwii_ids   = {m['id'] for m in by_tenant['addwii']}
all_lingce_ids   = {m['id'] for m in by_tenant['lingce']}

def classify_room(room_fn):
    """從 room_A_B.jsonl 判定歸屬"""
    stem = room_fn.replace('room_', '').replace('.jsonl', '')
    parts = stem.split('_')
    ids = []
    for i in range(1, len(parts)):
        a = '_'.join(parts[:i]); b = '_'.join(parts[i:])
        if a in all_microjet_ids or a in all_addwii_ids or a in all_lingce_ids:
            ids = [a, b]; break
    if not ids: return 'lingce'
    a, b = ids
    # 兩邊都在 addwii → addwii；兩邊都在 microjet → microjet；否則看第一人
    in_addwii = a in all_addwii_ids or b in all_addwii_ids
    in_microjet = a in all_microjet_ids or b in all_microjet_ids
    if in_addwii and not in_microjet: return 'addwii'
    if in_microjet and not in_addwii: return 'microjet'
    return 'microjet'  # 預設：混合歸 microjet（多半是總部人員對話）

for fn in os.listdir(CHAT_LOGS):
    if fn.startswith('room_') and fn.endswith('.jsonl'):
        tenant = classify_room(fn)
        dst = os.path.join(DATA, tenant, 'chat_rooms', fn)
        shutil.copy2(os.path.join(CHAT_LOGS, fn), dst)

print(f'  聊天室：依成員分類到各 tenant/chat_rooms/')

# index.json 複製到 lingce（後續可依需求再拆）
src_idx = os.path.join(CHAT_LOGS, 'index.json')
if os.path.exists(src_idx):
    shutil.copy2(src_idx, os.path.join(DATA, 'lingce', 'chat_rooms', 'index.json'))

# ─── 步驟 6：維明評估頁 ───
print('\n[6/6] 建立維明評估資料...')
weiming_info = {
    'client_id': 'weiming',
    'name': '維明顧問',
    'status': 'evaluation',
    'stage': 'BD Agent 訪談中',
    'industry': '企業顧問業',
    'started_at': '2026-04-10',
    'interviews': [
        {'date': '2026-04-10', 'topic': '首次接觸 · 商業模式初步說明', 'notes': '客戶對 AI 模組感興趣但尚未決定導入項目'},
        {'date': '2026-04-15', 'topic': '深度訪談 · 需求盤點', 'notes': '客戶希望先試用「AI 會議記錄」+「AI 文件助理」兩個基礎模組'},
        {'date': '2026-04-20', 'topic': '試算報價 · 商業條款討論', 'notes': '預估月費 NT$ 6,500（2 模組，無折扣），客戶考慮中'},
    ],
    'pending_items': [
        'NDA 保密協議簽署',
        '3 個月試用期條款確認',
        '客戶內部預算審核',
    ],
    'next_step': '2026-04-28 安排技術 Demo',
}
with open(os.path.join(DATA, 'weiming', 'evaluation.json'), 'w', encoding='utf-8') as f:
    json.dump(weiming_info, f, ensure_ascii=False, indent=2)
print(f'  data/weiming/evaluation.json')

print('\n' + '=' * 60)
print('  遷移完成')
print('=' * 60)
print(f'''
  組織：
    lingce   {len(by_tenant['lingce']):>3d} 位（1 老闆 + 10 AI Agent）
    microjet {len(by_tenant['microjet']):>3d} 位
    addwii   {len(by_tenant['addwii']):>3d} 位
    weiming  {len(by_tenant['weiming']):>3d} 位（評估中）

  CRM 示範資料：
    lingce   {len(DEMO_DATA['lingce'])} 筆
    microjet {len(DEMO_DATA['microjet'])} 筆
    addwii   {len(DEMO_DATA['addwii'])} 筆
    weiming  {len(DEMO_DATA['weiming'])} 筆

  稽核 log、聊天室：已依歸屬分類到各 tenant/
  procurement_state.json：共享於 lingce/audit/（跨 tenant 讀寫）
''')
