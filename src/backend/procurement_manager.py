"""Phase 3：addwii→microjet 採購流程 + 感測器序號綁定

單一 12 坪情境 (陳先生) 的後端狀態機，JSON 持久化。
前端動作：出貨採購單 / 推進訂單里程碑 / 查看感測器序號。

設計原則：
- 最小可用：單一情境、單檔 JSON、零外部依賴
- 所有狀態變更都寫入 audit log（append-only）
- 序號由 ship_po 時自動生成，形如 CJ-P760-20260422-0001
"""
from __future__ import annotations
import json
import os
import threading
from datetime import datetime
from typing import Any


_DEFAULT = {
    'customer': {
        'id': 'CUST-001',
        'name': '陳先生',
        'phone': '0912-345-678',
        'address': '台北市大安區和平東路二段 xxx 號 5F',
        'channel': 'addwii 官網表單填寫',
    },
    'space': {
        'area_ping': 12, 'area_m2': 39.6, 'height_m': 2.8,
        'scenario': '客廳款（Living Room Clean Room）',
    },
    'inquiry': {'id': 'INQ-2026-0412', 'date': '2026-04-12', 'status': '已回覆'},
    'quote':   {'id': 'QUO-2026-0041', 'date': '2026-04-14',
                'amount': 168000, 'validity': '30 天', 'status': '客戶已簽回'},
    'order': {
        'id': 'ORD-2026-0028', 'date': '2026-04-16',
        'amount': 168000, 'deposit': 84000, 'status': '製造中',
        'current_milestone': 'manufacture',   # 當前所在里程碑 key
    },
    # 8 階段里程碑（key → label/date/done/current 狀態由 current_milestone 推導）
    'milestones': [
        {'key':'inquiry',     'label':'客戶詢價',                    'date':'2026-04-12'},
        {'key':'quote',       'label':'addwii 報價',                 'date':'2026-04-14'},
        {'key':'contract',    'label':'簽約 + 付訂金 50%',           'date':'2026-04-16'},
        {'key':'purchase',    'label':'addwii → microjet 採購感測器','date':'2026-04-18'},
        {'key':'manufacture', 'label':'主機製造 + 感測器到料',       'date':'2026-04-20'},
        {'key':'shipping',    'label':'出貨',                        'date':'2026-04-26'},
        {'key':'install',     'label':'到府安裝 + 序號綁定',         'date':'2026-04-28'},
        {'key':'acceptance',  'label':'驗收完工 + 尾款',             'date':'2026-04-29'},
    ],
    'bom': [
        {'sku':'ADW-LR-12P',   'name':'客廳無塵室主機（12 坪適用）', 'qty':1, 'unit':148000, 'supplier':'addwii 自製'},
        {'sku':'CJ-P760',      'name':'PM + VOC 整合感測器模組',      'qty':2, 'unit':3200,   'supplier':'microjet / CurieJet'},
        {'sku':'CJ-P710',      'name':'PM2.5 備援感測器模組',          'qty':1, 'unit':2400,   'supplier':'microjet / CurieJet'},
        {'sku':'ADW-HEPA-H13', 'name':'HEPA H13 濾網組（初始配備）',   'qty':1, 'unit':3600,   'supplier':'addwii'},
        {'sku':'ADW-CARBON',   'name':'活性碳除臭層',                   'qty':1, 'unit':1800,   'supplier':'addwii'},
        {'sku':'ADW-UV',       'name':'UV 殺菌模組',                    'qty':1, 'unit':4800,   'supplier':'addwii'},
    ],
    'purchase_to_microjet': {
        'po_id': 'PO-ADW-2026-0117', 'date': '2026-04-18',
        'items': [
            {'sku':'CJ-P760', 'qty':2, 'unit':3200, 'subtotal':6400},
            {'sku':'CJ-P710', 'qty':1, 'unit':2400, 'subtotal':2400},
        ],
        'total': 8800,
        'expected_delivery': '2026-04-22',
        'status': 'microjet 備貨中',   # 備貨中 → 已出貨 → 已到料
        'shipped_at': None,
    },
    # 感測器序號（ship_po 時生成；每顆綁定到本訂單）
    'sensor_serials': [],   # [{serial, sku, shipped_at, bound_to_order, bound_at}]
    'audit': [],            # [{ts, action, detail}]
}


class ProcurementManager:
    MILESTONE_ORDER = ['inquiry','quote','contract','purchase','manufacture','shipping','install','acceptance']

    def __init__(self, json_path: str):
        self.json_path = json_path
        # ★ 用 RLock 而非 Lock：reset() 內呼叫 get_scenario()，Lock 會死鎖
        self._lock = threading.RLock()
        self.state: dict[str, Any] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.json_path):
            try:
                with open(self.json_path, 'r', encoding='utf-8') as f:
                    self.state = json.load(f)
                return
            except Exception as e:
                print(f'[Procurement] 載入失敗，重置: {e}')
        self.state = json.loads(json.dumps(_DEFAULT))  # deep copy
        self._save()

    def _save(self):
        os.makedirs(os.path.dirname(self.json_path), exist_ok=True)
        with open(self.json_path, 'w', encoding='utf-8') as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    def _audit(self, action: str, detail: dict):
        self.state.setdefault('audit', []).append({
            'ts': datetime.now().isoformat(timespec='seconds'),
            'action': action, 'detail': detail,
        })

    def reset(self) -> dict:
        """重置到初始狀態（展示/測試用）"""
        with self._lock:
            self.state = json.loads(json.dumps(_DEFAULT))
            self._audit('reset', {})
            self._save()
            return self.get_scenario()

    def get_scenario(self) -> dict:
        """回傳含 done/current 旗標的完整情境"""
        with self._lock:
            out = json.loads(json.dumps(self.state))
            current = out['order']['current_milestone']
            current_idx = self.MILESTONE_ORDER.index(current) if current in self.MILESTONE_ORDER else -1
            for i, m in enumerate(out['milestones']):
                m['done'] = i <= current_idx
                m['current'] = (i == current_idx)
            # 移除冗長 audit（前端另外拉）
            out.pop('audit', None)
            return out

    def get_audit(self, limit: int = 50) -> list:
        with self._lock:
            return list(reversed(self.state.get('audit', [])))[:limit]

    # ─── 動作 1：microjet 出貨採購單 → 自動生成序號 + 綁定至訂單
    def ship_po(self, po_id: str) -> dict:
        with self._lock:
            po = self.state['purchase_to_microjet']
            if po['po_id'] != po_id:
                return {'ok': False, 'error': f'PO {po_id} 不存在'}
            if po['status'] == '已出貨':
                return {'ok': False, 'error': '此採購單已出貨'}

            now = datetime.now()
            ship_date = now.strftime('%Y%m%d')
            order_id = self.state['order']['id']
            existing = len(self.state.get('sensor_serials', []))
            new_serials = []
            seq = existing + 1
            for item in po['items']:
                for _ in range(item['qty']):
                    serial = f"{item['sku']}-{ship_date}-{seq:04d}"
                    rec = {
                        'serial': serial,
                        'sku': item['sku'],
                        'shipped_at': now.isoformat(timespec='seconds'),
                        'bound_to_order': order_id,
                        'bound_to_customer': self.state['customer']['name'],
                        'bound_address': self.state['customer']['address'],
                        'bound_at': now.isoformat(timespec='seconds'),
                    }
                    self.state.setdefault('sensor_serials', []).append(rec)
                    new_serials.append(rec)
                    seq += 1

            po['status'] = '已出貨'
            po['shipped_at'] = now.isoformat(timespec='seconds')

            # 若當前在 manufacture，推進到 shipping
            cur = self.state['order']['current_milestone']
            if cur in ('purchase', 'manufacture'):
                self.state['order']['current_milestone'] = 'shipping'
                self.state['order']['status'] = '運送中'

            self._audit('ship_po', {
                'po_id': po_id, 'serials_generated': [s['serial'] for s in new_serials],
                'bound_order': order_id,
            })
            self._save()
            return {'ok': True, 'serials': new_serials,
                    'new_milestone': self.state['order']['current_milestone']}

    # ─── 動作 2：推進訂單里程碑
    def advance_order(self, order_id: str) -> dict:
        with self._lock:
            if self.state['order']['id'] != order_id:
                return {'ok': False, 'error': f'訂單 {order_id} 不存在'}
            cur = self.state['order']['current_milestone']
            try:
                idx = self.MILESTONE_ORDER.index(cur)
            except ValueError:
                return {'ok': False, 'error': f'未知里程碑 {cur}'}
            if idx >= len(self.MILESTONE_ORDER) - 1:
                return {'ok': False, 'error': '已到最終里程碑（驗收完工）'}

            next_key = self.MILESTONE_ORDER[idx + 1]
            self.state['order']['current_milestone'] = next_key
            # 更新狀態文字
            status_map = {
                'quote': '報價中', 'contract': '已簽約', 'purchase': '採購中',
                'manufacture': '製造中', 'shipping': '運送中', 'install': '安裝中',
                'acceptance': '已完工',
            }
            self.state['order']['status'] = status_map.get(next_key, self.state['order']['status'])
            self._audit('advance_order', {
                'order_id': order_id, 'from': cur, 'to': next_key,
            })
            self._save()
            return {'ok': True, 'current_milestone': next_key,
                    'status': self.state['order']['status']}

    # ─── 動作 3：手動綁定 / 查詢序號（進階操作）
    def list_serials(self) -> list:
        with self._lock:
            return list(self.state.get('sensor_serials', []))
