# -*- coding: utf-8 -*-
"""驗證跨階級觀察員（中間主管）可以發言"""
import requests, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

API = 'http://localhost:5000'

# 1. 先建立跨級對話
print('[1] 建立跨級對話 MGR-001 → ENG-001')
r = requests.post(f'{API}/api/chat/create', json={
    'initiator_id': 'MGR-001', 'target_id': 'ENG-001'})
d = r.json()
room = d['room']
print(f'  關係: {d["analysis"]["relation"]}')
print(f'  主對話人: {[p["name"] for p in room["participants"]]}')
print(f'  觀察員: {[o["name"] for o in room["observers"]]}')
ROOM = room['id']

# 2. 觀察員（陳雅婷，課長）嘗試發言
print('\n[2] 中間主管陳雅婷（課長，observer）嘗試發言')
r = requests.post(f'{API}/api/chat/send', json={
    'room_id': ROOM, 'sender_id': 'SCT-001',
    'content': '我這邊補充：建議先評估影響範圍'})
d = r.json()
print(f'  發言成功: {d.get("success")}')
if d.get('success'):
    print(f'  訊息類型: {d["message"]["type"]} (應為 observer_text)')
    print(f'  觀察員發言能夠發出 ✅')
else:
    print(f'  ❌ 失敗: {d.get("error")}')

# 3. 另一位觀察員（蔡文傑，副課長）也發言
print('\n[3] 中間主管蔡文傑（副課長，observer）嘗試發言')
r = requests.post(f'{API}/api/chat/send', json={
    'room_id': ROOM, 'sender_id': 'DSC-001',
    'content': '我這組可以先暫停登入模組，配合這個需求'})
d = r.json()
print(f'  發言成功: {d.get("success")}')
if d.get('success'):
    print(f'  訊息類型: {d["message"]["type"]}')

# 4. 非相關成員（范佑翔）嘗試發言（應拒絕）
print('\n[4] 非相關成員范佑翔（ENG-005）嘗試發言（應拒絕）')
r = requests.post(f'{API}/api/chat/send', json={
    'room_id': ROOM, 'sender_id': 'ENG-005',
    'content': '我能插話嗎？'})
d = r.json()
print(f'  發言成功: {d.get("success")}  (應為 False)')
if not d.get('success'):
    print(f'  ✅ 正確拒絕: {d.get("error")}')

# 5. 查看完整對話
print('\n[5] 最終完整對話')
r = requests.get(f'{API}/api/chat/messages/{ROOM}?member_id=MGR-001')
d = r.json()
print('─' * 60)
for m in d['messages']:
    if m['type'] == 'system': continue
    if m['type'] == 'alert':
        print(f'  [系統] {m["content"]}')
        continue
    tag = '[AI]' if m.get('ai_generated') else ''
    obs_tag = '[中間主管]' if m['type'] == 'observer_text' else ''
    print(f'  [{m["time_display"]}] {m["sender_name"]} {tag}{obs_tag}')
    print(f'    {m["content"]}')

print('\n完成！')
