# -*- coding: utf-8 -*-
"""測試 HR 組織編輯"""
import requests, sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

API = 'http://localhost:5000'

print('=' * 60)
print('  HR 組織編輯測試')
print('=' * 60)

# 1. HR 新增成員
print('\n[1] 黃珮琪（HR）新增「陳新人」...')
r = requests.post(f'{API}/api/org/members', json={
    'actor_id': 'HR-001',
    'member': {'name': '陳新人', 'role': '工程師',
               'dept': '前端 A 課', 'supervisor_id': 'DSC-001',
               'avatar': '🧑‍💻'}
}, timeout=30)
d = r.json()
print(f'  結果: {"成功" if d.get("success") else "失敗 — "+d.get("error","")}')
if d.get('member'):
    print(f'  新成員 ID: {d["member"]["id"]}, 姓名: {d["member"]["name"]}')
    NEW_ID = d['member']['id']
else:
    NEW_ID = None

# 2. 非 HR 嘗試新增（應拒絕）
print('\n[2] 郭宇翔（工程師，非 HR）嘗試新增成員...')
r = requests.post(f'{API}/api/org/members', json={
    'actor_id': 'ENG-001',
    'member': {'name': '非法新增', 'role': '工程師', 'dept': '測試'}
}, timeout=30)
d = r.json()
print(f'  結果: {"不當通過！" if d.get("success") else "✅ 正確拒絕 — " + d.get("error","")}')

# 3. HR 修改姓名 + 調整上級
if NEW_ID:
    print(f'\n[3] HR 修改 {NEW_ID} 的上級改為劉淑芬（DSC-002）...')
    r = requests.patch(f'{API}/api/org/members/{NEW_ID}', json={
        'actor_id': 'HR-001',
        'updates': {'supervisor_id': 'DSC-002', 'dept': '前端 A 課（轉組）'}
    }, timeout=30)
    d = r.json()
    print(f'  結果: {"成功" if d.get("success") else "失敗 — "+d.get("error","")}')

# 4. HR 嘗試造成循環
print('\n[4] HR 嘗試將李美華（副理）的上級設為其下屬陳雅婷（課長）— 循環...')
r = requests.patch(f'{API}/api/org/members/DMG-001', json={
    'actor_id': 'HR-001',
    'updates': {'supervisor_id': 'SCT-001'}
}, timeout=30)
d = r.json()
print(f'  結果: {"不當通過！" if d.get("success") else "✅ 正確拒絕 — " + d.get("error","")}')

# 5. HR 刪除剛新增的成員
if NEW_ID:
    print(f'\n[5] HR 刪除 {NEW_ID}...')
    r = requests.delete(f'{API}/api/org/members/{NEW_ID}?actor_id=HR-001', timeout=30)
    d = r.json()
    print(f'  結果: {"成功" if d.get("success") else "失敗 — "+d.get("error","")}')

# 6. 確認 org_data.json 落地
print('\n[6] 持久化檔案檢查...')
path = 'chat_logs/org_data.json'
if os.path.exists(path):
    size = os.path.getsize(path)
    import json as _j
    with open(path, 'r', encoding='utf-8') as f:
        org = _j.load(f)
    print(f'  ✅ 檔案存在：{path}')
    print(f'  大小：{size} bytes')
    print(f'  成員數：{len(org)}')
    hr_count = sum(1 for m in org if m.get('is_hr'))
    print(f'  HR 權限人數：{hr_count}')
else:
    print(f'  ❌ 檔案未建立')

# 7. 最終組織統計
print('\n[7] 當前組織統計...')
r = requests.get(f'{API}/api/org/members-flat', timeout=10)
data = r.json()
print(f'  總人數：{len(data)}')
from collections import Counter
roles = Counter(m['role'] for m in data)
for role, count in roles.items():
    print(f'    {role}: {count}')

print('\n完成！')
