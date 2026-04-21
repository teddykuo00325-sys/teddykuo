# -*- coding: utf-8 -*-
"""將所有 chat_logs 內歷史檔案的真實姓名批次替換為「姓+OO」。
保留：陳先生（demo 客戶，非員工）、職稱詞。"""
import os, re, json

CHAT_LOGS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'chat_logs')
SURNAMES = (
    '王李張劉陳楊黃趙吳周徐孫馬朱胡林郭何高羅鄭梁謝宋唐許韓馮鄧曹彭曾肖田'
    '董袁潘於蔣蔡余杜葉程蘇魏呂丁任沈姚盧姜崔鍾譚陸汪范金石廖賈夏韋方白鄒'
    '孟熊秦邱江尹薛閻段雷侯龍史陶黎賀顧毛郝龔邵萬錢嚴覃武戴莫孔向湯俞倪'
)
# 豁免：職稱、角色、假客戶、系統詞
EXEMPT = {
    '董事長', '總經理', '經理', '協理', '副理', '課長', '副課長',
    '專員', '工程師', '總機',
    '陳先生', '陳小姐', '王先生', '李先生', '林媽媽',   # demo 客戶用
    '凌策', '凌策公司', '客服', '財務', '法務', '文件',
    'addwii', 'microjet', '維明',
}
# 只對「姓 + 2~3 字」的真實中文姓名做遮蔽
NAME_RE = re.compile(r'(?<![\u4e00-\u9fa5OO])([' + SURNAMES + r'])([\u4e00-\u9fa5]{1,3})(?![\u4e00-\u9fa5])')

def mask_name(match):
    full = match.group(0)
    if full in EXEMPT: return full
    if full.endswith('OO'): return full   # 已經遮蔽過
    if full.endswith('先生') or full.endswith('小姐') or full.endswith('女士'):
        return full  # demo 客戶保留
    # 純數字 / 英文混雜保留
    return match.group(1) + 'OO'

def process(fp):
    try:
        with open(fp, 'r', encoding='utf-8') as f: text = f.read()
    except Exception as e:
        print(f'  skip (read fail): {fp} - {e}')
        return 0
    # 額外保護：不動 JSON key 結構只改值裡的中文
    new_text = NAME_RE.sub(mask_name, text)
    if new_text == text: return 0
    with open(fp, 'w', encoding='utf-8') as f: f.write(new_text)
    return 1

# 掃描目標
targets = []
for root, dirs, files in os.walk(CHAT_LOGS):
    # 跳過 sqlite / db / binary
    for fn in files:
        if fn.endswith(('.db', '.sqlite3', '.zip', '.pyc')): continue
        targets.append(os.path.join(root, fn))

print(f'掃描 {len(targets)} 個檔案...')
changed = 0
for fp in targets:
    if process(fp):
        changed += 1
        print(f'  [v] 遮蔽：{os.path.relpath(fp, CHAT_LOGS)}')
print(f'\n完成：修改了 {changed} 個檔案')

# 額外清理：刪除 org_data.json.pre-rename（舊備份，有真名）
for stale in ['org_data.json.pre-rename']:
    fp = os.path.join(CHAT_LOGS, stale)
    if os.path.exists(fp):
        os.remove(fp)
        print(f'  [x] 刪除：{stale}（舊備份）')
