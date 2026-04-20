# -*- coding: utf-8 -*-
"""測試聊天流程：王大衛（經理）→ 郭宇翔（工程師）跨級對話"""
import requests
import time
import json
import sys
import io

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

API = 'http://localhost:5000'
ROOM_ID = 'room_ENG-001_MGR-001'

print('=' * 60)
print('  聊天流程測試 — 經理發起跨級對話')
print('=' * 60)

# Step 0: 建立聊天室
print('\n[步驟 0] 王大衛（經理）發起對話（建立聊天室）...')
r = requests.post(f'{API}/api/chat/create', json={
    'initiator_id': 'MGR-001', 'target_id': 'ENG-001'
}, timeout=30)
rd = r.json()
print(f'  建立成功：{rd.get("success")}, 新房：{rd.get("is_new")}')
print(f'  關係：{rd["analysis"]["relation"]}')
print(f'  觀察員：{[o["name"] for o in rd["room"]["observers"]]}')

# Step 1: 經理發訊息
print('\n[步驟 1] 王大衛（經理）發送：')
msg1 = '阿翔，客戶臨時要加一個匯出 Excel 的功能，本週五前能做好嗎？'
print(f'  > {msg1}')
r = requests.post(f'{API}/api/chat/send', json={
    'room_id': ROOM_ID, 'sender_id': 'MGR-001', 'content': msg1
}, timeout=30)
print(f'  API 回應：{r.json().get("success")}')

# Step 2: 立即檢查 typing 狀態（應該 ENG-001 正在輸入）
print('\n[步驟 2] 立即查看聊天室狀態（期待：郭宇翔輸入中）')
time.sleep(2)
r = requests.get(f'{API}/api/chat/messages/{ROOM_ID}?member_id=MGR-001', timeout=30)
d = r.json()
typing_now = d.get('room', {}).get('typing_now', [])
print(f'  輸入中：{[t["name"] for t in typing_now]}')

# Step 3: 等 AI 回覆（gemma4:e2b 大約 30-60 秒）
print('\n[步驟 3] 等待 AI 背景產出回覆...')
max_wait = 120
start = time.time()
prev_count = len(d['messages'])
while time.time() - start < max_wait:
    time.sleep(3)
    r = requests.get(f'{API}/api/chat/messages/{ROOM_ID}?member_id=MGR-001', timeout=30)
    d = r.json()
    cur = len(d['messages'])
    elapsed = int(time.time() - start)
    typing_now = d.get('room', {}).get('typing_now', [])
    print(f'  [{elapsed:3d}s] 訊息數：{cur} | 輸入中：{[t["name"] for t in typing_now]}')
    if cur > prev_count:
        print('  ✅ 新訊息到達！')
        break

# Step 4: 查看最終對話
print('\n[步驟 4] 完整對話紀錄：')
print('-' * 60)
for m in d['messages']:
    if m['type'] == 'system':
        continue
    if m['type'] == 'alert':
        print(f'  [系統] {m["content"]}')
        continue
    ai_tag = ' (AI)' if m.get('ai_generated') else ''
    read_count = m.get('read_count', 0)
    print(f'  [{m["time_display"]}] {m["sender_name"]}{ai_tag} (已讀 {read_count}):')
    print(f'    {m["content"]}')
    print()

# Step 5: 觀察員視角 — 陳雅婷（課長）
print('\n[步驟 5] 切換身分：陳雅婷（課長，中間主管觀察員）看到的：')
r = requests.get(f'{API}/api/chat/rooms/SCT-001', timeout=30)
d = r.json()
print(f'  未讀總數：{d["unread_total"]}')
for room in d['rooms']:
    print(f'  - 房間 {room["id"][:25]}... | 我的角色：{room["my_role"]} | 未讀 {room["unread"]}')

# Step 6: 磁碟驗證
print('\n[步驟 6] 磁碟檔案驗證：')
import os
log_path = 'chat_logs/room_ENG-001_MGR-001.jsonl'
if os.path.exists(log_path):
    with open(log_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    print(f'  檔案：{log_path}')
    print(f'  行數：{len(lines)} 行（每行 1 則訊息，append-only JSONL）')
    print(f'  大小：{os.path.getsize(log_path)} bytes')

print('\n' + '=' * 60)
print('  測試完成')
print('=' * 60)
