# -*- coding: utf-8 -*-
"""測試：跨階級中間主管（觀察員）也可發言"""
import requests, time, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

API = 'http://localhost:5000'
ROOM = 'room_ENG-001_MGR-001'

print('=== 步驟 1: 建立跨級對話 (經理→工程師) ===')
r = requests.post(f'{API}/api/chat/create', json={
    'initiator_id': 'MGR-001', 'target_id': 'ENG-001'}, timeout=30)
d = r.json()
print(f'  關係: {d["analysis"]["relation"]}')
print(f'  觀察員: {[o["name"] for o in d["room"]["observers"]]}')

print('\n=== 步驟 2: 經理發訊息 ===')
requests.post(f'{API}/api/chat/send', json={
    'room_id': ROOM, 'sender_id': 'MGR-001',
    'content': '阿翔，客戶要加匯出 Excel 功能，本週能做嗎？'}, timeout=30)
print('  王大衛（經理）: 阿翔，客戶要加匯出 Excel 功能，本週能做嗎？')

time.sleep(3)

print('\n=== 步驟 3: 中間主管陳雅婷（課長）插話 ===')
r = requests.post(f'{API}/api/chat/send', json={
    'room_id': ROOM, 'sender_id': 'SCT-001',
    'content': '我這邊確認一下，阿翔這週的進度比較滿，可能要挪開登入模組的時間來做這個。'}, timeout=30)
print('  送出結果:', r.json().get('success'))

time.sleep(2)

print('\n=== 步驟 4: 另一位中間主管蔡文傑（副課長）也插話 ===')
r = requests.post(f'{API}/api/chat/send', json={
    'room_id': ROOM, 'sender_id': 'DSC-001',
    'content': '我可以把登入模組接手給另一個工程師，讓阿翔專心做匯出。'}, timeout=30)
print('  送出結果:', r.json().get('success'))

# 等 AI 回覆
print('\n=== 步驟 5: 等 AI 回覆（郭宇翔看到上下文後回應）===')
start = time.time()
prev = 0
while time.time() - start < 120:
    time.sleep(3)
    r = requests.get(f'{API}/api/chat/messages/{ROOM}?member_id=MGR-001', timeout=30)
    d = r.json()
    msgs = d.get('messages', [])
    text_count = sum(1 for m in msgs if m['type'] in ('text', 'observer_text'))
    ai_count = sum(1 for m in msgs if m.get('ai_generated'))
    typing = d.get('room', {}).get('typing_now', [])
    elapsed = int(time.time() - start)
    print(f'  [{elapsed:3d}s] 訊息: {text_count} 則 (AI: {ai_count}) | 輸入中: {[t["name"] for t in typing]}')
    if ai_count >= 1:
        print('  ✅ AI 已回覆')
        break

print('\n=== 步驟 6: 完整對話（觀察員發言標記）===')
r = requests.get(f'{API}/api/chat/messages/{ROOM}?member_id=MGR-001', timeout=30)
d = r.json()
print('─' * 70)
for m in d['messages']:
    if m['type'] == 'system':
        continue
    if m['type'] == 'alert':
        print(f'  [系統通知] {m["content"]}')
        continue
    tag = '🟣 AI' if m.get('ai_generated') else ''
    if m['type'] == 'observer_text':
        tag += ' 🟠中間主管'
    print(f'  [{m["time_display"]}] {m["sender_name"]} {tag}')
    print(f'    "{m["content"]}"')
    print()

print('\n=== 步驟 7: 磁碟紀錄驗證 ===')
import os
path = 'chat_logs/room_ENG-001_MGR-001.jsonl'
with open(path, 'r', encoding='utf-8') as f:
    lines = [l for l in f if l.strip()]
print(f'  檔案: {path}')
print(f'  行數: {len(lines)} 行（每行 1 JSON）')
print(f'  大小: {os.path.getsize(path)} bytes')
# 確認有 observer_text
import json
types = []
for ln in lines:
    t = json.loads(ln).get('type')
    types.append(t)
print(f'  訊息類型分佈: {dict((t, types.count(t)) for t in set(types))}')

print('\n完成！')
