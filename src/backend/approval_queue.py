# -*- coding: utf-8 -*-
"""凌策 三軌人審 Queue · approval_queue.py

addwii / microjet / 維明 通用人審佇列，分三個 track：
  · sales       客服回覆 / 報價 / 議價
  · marketing   行銷貼文 / 短影音腳本
  · compliance  PII 命中 / 合規越權

每筆送進來自動拿 audit_id；老闆（總監）可從 dashboard 一鍵 approve / reject / edit。
"""
import os, json, time, threading, uuid
from datetime import datetime
from typing import Optional, Dict, List

QUEUE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         '..', '..', 'data', 'lingce', 'approval_queue')
os.makedirs(QUEUE_DIR, exist_ok=True)

_LOCK = threading.Lock()


def _path(track: str) -> str:
    return os.path.join(QUEUE_DIR, f'{track}.jsonl')


def _all_items(track: str) -> List[Dict]:
    p = _path(track)
    if not os.path.exists(p):
        return []
    items = []
    with open(p, encoding='utf-8') as f:
        for line in f:
            try:
                items.append(json.loads(line))
            except Exception:
                pass
    return items


def _write_all(track: str, items: List[Dict]):
    with open(_path(track), 'w', encoding='utf-8') as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + '\n')


def submit(track: str, payload: dict, agent: str = 'unknown',
           customer: str = 'unknown', priority: str = 'normal') -> dict:
    """送進 queue 等審

    Args:
        track:     sales / marketing / compliance
        payload:   要被人審的內容 dict（如報價單、貼文草稿、PII 命中事件）
        agent:     觸發此送審的 Agent
        customer:  關聯客戶
        priority:  high / normal / low

    Returns:
        {ticket_id, ts, status='pending', ...}
    """
    if track not in ('sales', 'marketing', 'compliance'):
        return {'error': f'unknown track: {track}'}

    ticket = {
        'ticket_id':  f'APP-{datetime.now().strftime("%Y%m%d%H%M%S")}-{uuid.uuid4().hex[:6].upper()}',
        'ts':         datetime.now().isoformat(timespec='seconds'),
        'track':      track,
        'agent':      agent,
        'customer':   customer,
        'priority':   priority,
        'status':     'pending',   # pending / approved / rejected / edited
        'payload':    payload,
        'review':     None,        # 填審核者意見
        'reviewed_by': None,
        'reviewed_at': None,
    }
    with _LOCK:
        with open(_path(track), 'a', encoding='utf-8') as f:
            f.write(json.dumps(ticket, ensure_ascii=False) + '\n')
    return ticket


def list_pending(track: str = None, limit: int = 50) -> dict:
    """列出待審項目（給 dashboard 紅點 + 列表用）"""
    tracks = [track] if track else ['sales', 'marketing', 'compliance']
    out = {}
    for t in tracks:
        items = _all_items(t)
        pending = [it for it in items if it.get('status') == 'pending']
        out[t] = {
            'total':    len(items),
            'pending':  len(pending),
            'items':    pending[-limit:],
        }
    return out


def review(track: str, ticket_id: str, action: str,
           reviewed_by: str = 'supervisor', note: str = '',
           edited_payload: dict = None) -> dict:
    """總監（總監角色）一鍵 approve / reject / edit

    Args:
        action:        approve / reject / edit
        reviewed_by:   審核者（預設 supervisor）
        note:          審核意見（必填 edit / reject）
        edited_payload: 若 edit，新的 payload
    """
    if action not in ('approve', 'reject', 'edit'):
        return {'error': f'unknown action: {action}'}

    with _LOCK:
        items = _all_items(track)
        found = None
        for it in items:
            if it.get('ticket_id') == ticket_id:
                found = it
                break
        if not found:
            return {'error': f'ticket not found: {ticket_id}'}
        if found.get('status') != 'pending':
            return {'error': f'ticket already reviewed: status={found.get("status")}'}

        found['status']      = 'approved' if action == 'approve' else ('rejected' if action == 'reject' else 'edited')
        found['review']      = note
        found['reviewed_by'] = reviewed_by
        found['reviewed_at'] = datetime.now().isoformat(timespec='seconds')
        if action == 'edit' and edited_payload:
            found['payload_original'] = found['payload']
            found['payload']          = edited_payload
        _write_all(track, items)
    return found


def stats() -> dict:
    """總攬統計（給 dashboard 卡片）"""
    out = {'tracks': {}}
    grand_pending = 0
    for t in ('sales', 'marketing', 'compliance'):
        items = _all_items(t)
        by_status = {}
        for it in items:
            s = it.get('status', 'pending')
            by_status[s] = by_status.get(s, 0) + 1
        out['tracks'][t] = {
            'total':     len(items),
            'by_status': by_status,
            'pending':   by_status.get('pending', 0),
        }
        grand_pending += by_status.get('pending', 0)
    out['total_pending'] = grand_pending
    out['ts']            = datetime.now().isoformat(timespec='seconds')
    return out


def seed_demo():
    """產生 demo 資料（供評審看到「真的有待審項目」）"""
    demos = [
        ('sales', {
            'type':           'negotiate_quote',
            'area_ping':      8,
            'customer_type':  'B2B',
            'segment':        'maternity_center',
            'requested_discount_pct': 12,
            'bundle_units':   5,
            'base_total_ntd': 132504,
            'final_total_ntd': 116603,
            'reason':         'B2B 月子中心 5 套包套折扣 + 客戶議價，折扣 12% 觸及主管核可門檻',
        }, 'customer-service', 'addwii · 永和月子中心', 'normal'),
        ('sales', {
            'type':           'negotiate_quote',
            'area_ping':      6,
            'customer_type':  'B2C',
            'segment':        'allergy_family',
            'requested_discount_pct': 8,
            'final_total_ntd': 92489,
            'reason':         'B2C 過敏家庭折扣 8% 超過 5% 自動門檻',
        }, 'customer-service', 'addwii · 王女士', 'normal'),
        ('marketing', {
            'type':           'fb_post_draft',
            'title':          '【自由呼吸 淨零生活】4 月新生兒家庭推薦',
            'channel':        'Facebook',
            'body':           '您的寶寶值得醫療無塵級的呼吸環境。addwii 嬰兒無塵室 S04，'
                              'CADR 2,200 環境部 NPA23C01250001 認證 PM2.5 趨零。',
            'image_url':      '(待生成)',
            'reason':         '草稿待總監核可後上版',
        }, 'docs', 'addwii', 'normal'),
        ('marketing', {
            'type':           'youtube_shorts_script',
            'title':          '60 秒看懂 addwii 為何便宜 30% 但 CADR 高 5 倍',
            'duration_s':     60,
            'script':         '[0:00] 你以為 Coway 850 CADR 賣 29,800 很划算？\n'
                              '[0:15] addwii S03 = 1,600 CADR、38,900 元。算一下：每 CADR 單價...\n'
                              '[0:45] 41 場域實測 PM2.5 趨零。看見差別了嗎？',
            'reason':         '腳本提及競品需法務確認用語合規',
        }, 'docs', 'addwii', 'high'),
        ('compliance', {
            'type':           'pii_hit',
            'context':        'customer_csv_upload',
            'pii_classes_found': ['phone', 'address', 'name'],
            'rows_affected':  142,
            'reason':         'CSV 上傳含 PII 13 類中的 3 類，需主管手動同意才能進入分析',
        }, 'legal', 'addwii · 41 場域回收資料', 'high'),
    ]
    for track, payload, agent, customer, prio in demos:
        submit(track, payload, agent=agent, customer=customer, priority=prio)
    return {'seeded': len(demos), 'stats': stats()}


if __name__ == '__main__':
    print(json.dumps(seed_demo(), ensure_ascii=False, indent=2))
