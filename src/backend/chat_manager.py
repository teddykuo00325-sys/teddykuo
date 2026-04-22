#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
凌策公司 — ChatManager 階級感知即時聊天系統

聊天規則：
1. 平行聊天（Peer）：同級同上級可互相發起 → 1 對 1
2. 上對下聊天（Downward）：上級可主動發起對下屬
   - 直屬下級：1 對 1
   - 跨級下屬：1 對 1 主聊，被跨越的中間主管加為 observers 並收到通知
3. 下對上聊天（Upward）：下級可主動發起對直屬上級 → 1 對 1
4. 跨級下對上：需經由直屬主管轉達（不允許直接跳級發起）
"""

import uuid
import os
import json
import threading
import requests
from datetime import datetime
from typing import Dict, List, Optional
from collections import defaultdict

# 聊天紀錄儲存目錄
# 預設舊路徑（向後相容）；多租戶模式下由 ChatManager(__init__) 以 chat_log_dir 參數覆寫
CHAT_LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'chat_logs')
os.makedirs(CHAT_LOG_DIR, exist_ok=True)

# Ollama 設定（可從環境變數覆寫）
OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://127.0.0.1:11434')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'gemma4:e2b')


def _top_dept(dept: Optional[str]) -> str:
    """取得頂層部門（去掉 ' / 子課' 部分）"""
    if not dept:
        return '(未分類)'
    return dept.split(' / ')[0].strip()


# ═══════════════════════════════════════════════════════════
# 敏感關鍵字屏蔽（禁止討論薪資類話題）
# ═══════════════════════════════════════════════════════════
import re as _re_mod

BLOCKED_CHINESE = [
    '薪資', '薪水', '薪酬', '薪金', '月薪', '年薪', '日薪',
    '調薪', '加薪', '減薪', '降薪',
    '獎金', '分紅', '紅利', '津貼', '獎酬',
    '底薪', '本薪', '勞健保金額',
]
# 英文需加邊界以避免誤判（例如 display 不該誤判為 pay）
BLOCKED_ENGLISH_PATTERNS = [
    _re_mod.compile(r'\bpay(check|day|ment|roll|s|ing)?\b', _re_mod.IGNORECASE),
    _re_mod.compile(r'\bpaid\b', _re_mod.IGNORECASE),
    _re_mod.compile(r'\bsalary|salaries\b', _re_mod.IGNORECASE),
    _re_mod.compile(r'\bwage[s]?\b', _re_mod.IGNORECASE),
    _re_mod.compile(r'\bbonus(es)?\b', _re_mod.IGNORECASE),
    _re_mod.compile(r'\bcompensation\b', _re_mod.IGNORECASE),
    _re_mod.compile(r'\braise[sd]?\b', _re_mod.IGNORECASE),
    _re_mod.compile(r'\bearnings?\b', _re_mod.IGNORECASE),
]

def check_blocked_content(content: str):
    """回傳 (is_blocked, matched_keyword)"""
    if not content:
        return False, None
    for kw in BLOCKED_CHINESE:
        if kw in content:
            return True, kw
    for pat in BLOCKED_ENGLISH_PATTERNS:
        m = pat.search(content)
        if m:
            return True, m.group()
    return False, None


class ChatRelation:
    """聊天關係類型"""
    PEER = 'peer'                       # 同級同上級
    DOWNWARD_DIRECT = 'downward_direct' # 直屬上對下
    UPWARD_DIRECT = 'upward_direct'     # 直屬下對上
    DOWNWARD_CROSS = 'downward_cross'   # 跨級上對下（中間主管加入）
    SELF = 'self'
    INVALID = 'invalid'


class ChatMessage:
    def __init__(self, room_id: str, sender_id: str, sender_name: str,
                 content: str, msg_type: str = 'text', ai_generated: bool = False,
                 msg_id: str = None, timestamp: datetime = None):
        self.id = msg_id or str(uuid.uuid4())[:8]
        self.room_id = room_id
        self.sender_id = sender_id
        self.sender_name = sender_name
        self.content = content
        self.type = msg_type  # text | system | alert
        self.ai_generated = ai_generated
        self.timestamp = timestamp or datetime.now()
        self.read_by: Dict[str, str] = {sender_id: self.timestamp.isoformat()}  # member_id -> read_at

    def to_dict(self):
        return {
            'id': self.id,
            'room_id': self.room_id,
            'sender_id': self.sender_id,
            'sender_name': self.sender_name,
            'content': self.content,
            'type': self.type,
            'ai_generated': self.ai_generated,
            'timestamp': self.timestamp.isoformat(),
            'time_display': self.timestamp.strftime('%H:%M:%S'),
            'read_by': self.read_by,
            'read_count': len(self.read_by),
        }

    @classmethod
    def from_dict(cls, data: Dict):
        msg = cls(
            room_id=data['room_id'],
            sender_id=data['sender_id'],
            sender_name=data['sender_name'],
            content=data['content'],
            msg_type=data.get('type', 'text'),
            ai_generated=data.get('ai_generated', False),
            msg_id=data['id'],
            timestamp=datetime.fromisoformat(data['timestamp']),
        )
        rb = data.get('read_by', {})
        # Support old list format
        if isinstance(rb, list):
            msg.read_by = {mid: msg.timestamp.isoformat() for mid in rb}
        else:
            msg.read_by = rb
        return msg


class ChatRoom:
    def __init__(self, room_id: str, participants: List[str],
                 observers: List[str] = None, relation: str = ChatRelation.PEER,
                 created_by: str = None, created_at: datetime = None):
        self.id = room_id
        self.participants = participants
        self.observers = observers or []
        self.relation = relation
        self.created_by = created_by
        self.created_at = created_at or datetime.now()
        self.messages: List[ChatMessage] = []
        self.last_activity = self.created_at
        self.typing: Dict[str, float] = {}  # member_id -> unix ts (typing expires after 5s)
        self.ai_enabled = False  # AI 自動回覆開關（預設關閉，需使用者手動啟用）
        # 跨部門協作審批
        self.approval_status = 'approved'  # approved | pending | rejected
        self.approver_id: Optional[str] = None  # 待誰核准（跨部門時 = 發起者的直屬主管）
        self.approval_reason: Optional[str] = None  # 核准/拒絕理由

    def all_members(self) -> List[str]:
        return self.participants + self.observers

    def can_send(self, member_id: str) -> bool:
        """主要對話人、被跨越的中間主管皆可發言"""
        return member_id in self.all_members()

    def can_view(self, member_id: str) -> bool:
        return member_id in self.all_members()

    def is_observer(self, member_id: str) -> bool:
        return member_id in self.observers

    def to_dict(self, member_lookup=None):
        def name_of(mid):
            if member_lookup and mid in member_lookup:
                m = member_lookup[mid]
                return {'id': mid, 'name': m.name, 'role': m.role, 'avatar': m.avatar}
            return {'id': mid, 'name': mid, 'role': '', 'avatar': '👤'}

        last_msg = self.messages[-1].to_dict() if self.messages else None

        # Typing: who is currently typing (within last 5 seconds)
        import time as _t
        now_ts = _t.time()
        typing_now = [mid for mid, ts in self.typing.items() if now_ts - ts < 5]

        return {
            'id': self.id,
            'participants': [name_of(p) for p in self.participants],
            'observers': [name_of(o) for o in self.observers],
            'relation': self.relation,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat(),
            'last_activity': self.last_activity.isoformat(),
            'message_count': len(self.messages),
            'last_message': last_msg,
            'typing_now': [name_of(mid) for mid in typing_now],
            'ai_enabled': self.ai_enabled,
            'approval_status': self.approval_status,
            'approver': name_of(self.approver_id) if self.approver_id else None,
            'approval_reason': self.approval_reason,
        }

    def set_typing(self, member_id: str):
        import time as _t
        self.typing[member_id] = _t.time()

    def clear_typing(self, member_id: str):
        self.typing.pop(member_id, None)

    def to_meta_dict(self):
        """序列化為可存檔的 metadata（不含訊息）"""
        return {
            'id': self.id,
            'participants': self.participants,
            'observers': self.observers,
            'relation': self.relation,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat(),
            'last_activity': self.last_activity.isoformat(),
            'ai_enabled': self.ai_enabled,
            'approval_status': self.approval_status,
            'approver_id': self.approver_id,
            'approval_reason': self.approval_reason,
        }


class ChatManager:
    """聊天管理器 — 整合 AttendanceManager 的組織層級資訊 + 檔案持久化 + AI 回覆"""

    def __init__(self, attendance_mgr, enable_ai_reply=True, chat_log_dir: str = None):
        self.attn = attendance_mgr
        self.rooms: Dict[str, ChatRoom] = {}
        self.unread_count: Dict[str, int] = defaultdict(int)
        self.enable_ai_reply = enable_ai_reply
        self._ai_lock = threading.Lock()
        self._save_lock = threading.Lock()
        # 多租戶：每個租戶有自己的聊天室目錄
        self._chat_dir = chat_log_dir or CHAT_LOG_DIR
        os.makedirs(self._chat_dir, exist_ok=True)
        # 從磁碟載入既有對話
        self._load_from_disk()

    # ════════════════════════════════════════════════
    # 持久化 — JSONL 檔案儲存
    # ════════════════════════════════════════════════
    def _index_path(self):
        return os.path.join(self._chat_dir, 'index.json')

    def _room_log_path(self, room_id):
        safe_id = room_id.replace('/', '_').replace('\\', '_')
        return os.path.join(self._chat_dir, f'{safe_id}.jsonl')

    def _save_index(self):
        with self._save_lock:
            index = {rid: room.to_meta_dict() for rid, room in self.rooms.items()}
            with open(self._index_path(), 'w', encoding='utf-8') as f:
                json.dump(index, f, ensure_ascii=False, indent=2)

    def _append_message_to_disk(self, room_id: str, msg: ChatMessage):
        """以 JSONL append-only 方式寫入訊息（真實聊天系統慣例）"""
        with self._save_lock:
            path = self._room_log_path(room_id)
            with open(path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(msg.to_dict(), ensure_ascii=False) + '\n')

    def _rewrite_room_log(self, room: ChatRoom):
        """用於更新已讀狀態（重寫整個檔案）"""
        with self._save_lock:
            path = self._room_log_path(room.id)
            with open(path, 'w', encoding='utf-8') as f:
                for msg in room.messages:
                    f.write(json.dumps(msg.to_dict(), ensure_ascii=False) + '\n')

    def _load_from_disk(self):
        """啟動時載入既有對話"""
        idx_path = self._index_path()
        if not os.path.exists(idx_path):
            return
        try:
            with open(idx_path, 'r', encoding='utf-8') as f:
                index = json.load(f)
        except Exception as e:
            print(f'[ChatManager] 無法載入 index.json: {e}')
            return

        for rid, meta in index.items():
            room = ChatRoom(
                room_id=rid,
                participants=meta['participants'],
                observers=meta.get('observers', []),
                relation=meta['relation'],
                created_by=meta.get('created_by'),
                created_at=datetime.fromisoformat(meta['created_at']),
            )
            room.ai_enabled = meta.get('ai_enabled', False)
            room.last_activity = datetime.fromisoformat(meta.get('last_activity', meta['created_at']))
            room.approval_status = meta.get('approval_status', 'approved')
            room.approver_id = meta.get('approver_id')
            room.approval_reason = meta.get('approval_reason')

            # 載入該房的訊息
            log_path = self._room_log_path(rid)
            if os.path.exists(log_path):
                with open(log_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            room.messages.append(ChatMessage.from_dict(data))
                        except Exception as e:
                            print(f'[ChatManager] 訊息載入錯誤: {e}')
            self.rooms[rid] = room
        print(f'[ChatManager] 已從磁碟載入 {len(self.rooms)} 個聊天室，共 {sum(len(r.messages) for r in self.rooms.values())} 則訊息')

    # ════════════════════════════════════════════════
    # 階級分析 — 核心規則引擎
    # ════════════════════════════════════════════════
    def analyze_relation(self, initiator_id: str, target_id: str) -> Dict:
        """
        分析兩人的組織關係，決定聊天類型
        回傳：
          {relation, allowed, observers, reason}
        """
        if initiator_id == target_id:
            return {'relation': ChatRelation.SELF, 'allowed': False, 'observers': [], 'reason': '不能與自己聊天'}

        initiator = self.attn.members.get(initiator_id)
        target = self.attn.members.get(target_id)
        if not initiator or not target:
            return {'relation': ChatRelation.INVALID, 'allowed': False, 'observers': [], 'reason': '成員不存在'}

        # HR 與無上級者（如董事長）：豁免所有關係檢查（跨部門協調/最高決策權）
        if initiator.is_hr:
            return {
                'relation': ChatRelation.PEER, 'allowed': True, 'observers': [],
                'reason': f'HR 協調權限（{initiator.name} → {target.name}，{target.role}）'
            }
        if not initiator.supervisor_id:
            return {
                'relation': ChatRelation.DOWNWARD_CROSS, 'allowed': True, 'observers': [],
                'reason': f'最高決策層發起（{initiator.name} → {target.name}）'
            }
        # 服務/支援部門（人事/HR/財務/總務/行政）— 本職就是跨部門協作
        initiator_dept = initiator.dept or ''
        initiator_title = initiator.title or ''
        if any(k in initiator_dept for k in self._SERVICE_DEPTS):
            return {
                'relation': ChatRelation.PEER, 'allowed': True, 'observers': [],
                'reason': f'服務部門協調權限（{initiator_dept} {initiator.name} → {target.name}）'
            }
        if any(k in initiator_title for k in self._SERVICE_TITLES):
            return {
                'relation': ChatRelation.PEER, 'allowed': True, 'observers': [],
                'reason': f'服務性職務協調權限（{initiator_title} {initiator.name} → {target.name}）'
            }
        # 高階職稱豁免
        if any(k in initiator_title for k in ('總經理', '協理', '經理')):
            return {
                'relation': ChatRelation.PEER, 'allowed': True, 'observers': [],
                'reason': f'{initiator_title} 跨部門協調權限（{initiator.name} → {target.name}）'
            }

        # 同級（同上級）→ PEER
        if initiator.supervisor_id and initiator.supervisor_id == target.supervisor_id:
            return {
                'relation': ChatRelation.PEER, 'allowed': True, 'observers': [],
                'reason': f'平行節點聊天（{initiator.role} ↔ {target.role}）'
            }

        # 檢查是否祖孫關係
        initiator_is_ancestor = self._is_ancestor(initiator_id, target_id)
        target_is_ancestor = self._is_ancestor(target_id, initiator_id)

        # 直屬上對下 / 下對上
        if target.supervisor_id == initiator_id:
            return {
                'relation': ChatRelation.DOWNWARD_DIRECT, 'allowed': True, 'observers': [],
                'reason': f'{initiator.role} → {target.role}（直屬主管對話）'
            }
        if initiator.supervisor_id == target_id:
            return {
                'relation': ChatRelation.UPWARD_DIRECT, 'allowed': True, 'observers': [],
                'reason': f'{initiator.role} → {target.role}（直屬下對上）'
            }

        # 跨級上對下 → 中間主管加入 observers
        if initiator_is_ancestor:
            intermediate = self._get_intermediate_supervisors(initiator_id, target_id)
            return {
                'relation': ChatRelation.DOWNWARD_CROSS, 'allowed': True,
                'observers': [m.id for m in intermediate],
                'observers_detail': [{'id': m.id, 'name': m.name, 'role': m.role} for m in intermediate],
                'reason': f'跨級對話：{initiator.role} 直接對 {target.role}，{len(intermediate)} 位中間主管將加入並收到通知'
            }

        # 跨級下對上 → 不允許（必須經由直屬）
        if target_is_ancestor:
            return {
                'relation': ChatRelation.INVALID, 'allowed': False, 'observers': [],
                'reason': f'跨級下對上聊天需經由直屬主管轉達，不可直接發起'
            }

        # 不同層級的平行（跨部門同級）→ 允許但類似 peer
        if initiator.role_level() == target.role_level():
            return {
                'relation': ChatRelation.PEER, 'allowed': True, 'observers': [],
                'reason': f'跨部門同級聊天（{initiator.role}）'
            }

        # 同頂層部門的跨子組 / 跨層級 → 允許（內部協作，無需中間主管介入）
        if _top_dept(initiator.dept) == _top_dept(target.dept):
            return {
                'relation': ChatRelation.PEER, 'allowed': True, 'observers': [],
                'reason': f'同部門內協作（{_top_dept(initiator.dept)}）'
            }

        # 其他不允許（跨部門跨級）
        return {
            'relation': ChatRelation.INVALID, 'allowed': False, 'observers': [],
            'reason': '跨部門跨級關係，需由主管轉介'
        }

    def _is_ancestor(self, ancestor_id: str, descendant_id: str) -> bool:
        """判斷 ancestor 是否為 descendant 的祖先（上上級）"""
        current = self.attn.members.get(descendant_id)
        while current and current.supervisor_id:
            if current.supervisor_id == ancestor_id:
                return True
            current = self.attn.members.get(current.supervisor_id)
        return False

    def _get_intermediate_supervisors(self, ancestor_id: str, descendant_id: str) -> List:
        """取得 ancestor 與 descendant 之間的所有中間主管（不含兩端）"""
        intermediate = []
        current = self.attn.members.get(descendant_id)
        # 從 descendant 往上找到 ancestor，收集中間所有人
        while current and current.supervisor_id:
            parent = self.attn.members.get(current.supervisor_id)
            if not parent:
                break
            if parent.id == ancestor_id:
                break
            intermediate.append(parent)
            current = parent
        return list(reversed(intermediate))  # 由上而下排序

    # ════════════════════════════════════════════════
    # 聊天室管理
    # ════════════════════════════════════════════════
    def create_or_get_room(self, initiator_id: str, target_id: str) -> Dict:
        """建立或取得聊天室"""
        analysis = self.analyze_relation(initiator_id, target_id)
        if not analysis['allowed']:
            return {'success': False, 'error': analysis['reason'], 'analysis': analysis}

        # 用成員組合作為 room_id 的基礎（無序，保證對稱）
        sorted_participants = sorted([initiator_id, target_id])
        room_id = 'room_' + '_'.join(sorted_participants)

        # 若已存在
        if room_id in self.rooms:
            existing = self.rooms[room_id]
            # 如果新分析有更多 observers，補上
            for o in analysis['observers']:
                if o not in existing.observers and o not in existing.participants:
                    existing.observers.append(o)
            return {
                'success': True,
                'room': existing.to_dict(self.attn.members),
                'analysis': analysis,
                'is_new': False,
            }

        # 建立新房
        room = ChatRoom(
            room_id=room_id,
            participants=[initiator_id, target_id],
            observers=analysis['observers'],
            relation=analysis['relation'],
            created_by=initiator_id,
        )

        # 跨部門協作審批判斷
        initiator = self.attn.members[initiator_id]
        target = self.attn.members[target_id]
        needs_approval = self._needs_cross_dept_approval(initiator, target)
        if needs_approval:
            room.approval_status = 'pending'
            room.approver_id = initiator.supervisor_id

        # 系統訊息：建立通知
        room.messages.append(ChatMessage(
            room_id, 'system', '系統',
            f'💬 {initiator.name}（{initiator.title or initiator.role}）發起與 {target.name}（{target.title or target.role}）的對話',
            msg_type='system'
        ))
        if needs_approval:
            approver = self.attn.members.get(room.approver_id)
            approver_name = approver.name if approver else '直屬主管'
            room.messages.append(ChatMessage(
                room_id, 'system', '系統',
                f'⏳ 跨部門協作審批中：本對話需要 {approver_name} 核准後才能開始訊息往來。'
                f'（發起者部門：{_top_dept(initiator.dept)}，對方部門：{_top_dept(target.dept)}）',
                msg_type='alert'
            ))
            # 通知核准人
            self.attn._add_notification(
                room.approver_id, 'chat_approval_pending',
                f'⏳ {initiator.name} 申請與 {target.name}（{_top_dept(target.dept)}）跨部門對話，請審核。',
                priority='high'
            )

        # 跨級通知中間主管
        if analysis['relation'] == ChatRelation.DOWNWARD_CROSS and analysis['observers']:
            obs_names = [self.attn.members[oid].name for oid in analysis['observers']]
            room.messages.append(ChatMessage(
                room_id, 'system', '系統',
                f'🔔 跨級通知：{", ".join(obs_names)} 已加入此對話作為中間主管（可閱讀、可發言）',
                msg_type='alert'
            ))
            # 發送通知到被跨越的主管
            for oid in analysis['observers']:
                self.attn._add_notification(
                    oid, 'cross_level_chat',
                    f'⚠️ {initiator.name}（{initiator.role}）直接與您下屬 {target.name}（{target.role}）發起對話',
                    priority='high'
                )
                self.unread_count[oid] += 1

        # 目標成員收到通知
        self.attn._add_notification(
            target_id, 'new_chat',
            f'💬 {initiator.name}（{initiator.role}）想與您對話',
            priority='normal'
        )
        self.unread_count[target_id] += 1

        self.rooms[room_id] = room
        # 持久化
        self._save_index()
        for m in room.messages:
            self._append_message_to_disk(room_id, m)
        return {
            'success': True,
            'room': room.to_dict(self.attn.members),
            'analysis': analysis,
            'is_new': True,
        }

    def send_message(self, room_id: str, sender_id: str, content: str,
                     ai_generated: bool = False, trigger_ai_reply: bool = True) -> Dict:
        room = self.rooms.get(room_id)
        if not room:
            # 自動恢復
            rebuilt = self._try_rebuild_room(room_id, sender_id)
            if rebuilt:
                room = rebuilt
            else:
                detail = self._diagnose_room_id(room_id)
                return {
                    'success': False,
                    'error': f'聊天室不存在（{detail}）',
                    'error_code': 'ROOM_NOT_FOUND',
                    'room_id': room_id,
                }

        if not room.can_send(sender_id) and not ai_generated:
            return {'success': False, 'error': '您不在此聊天室'}

        # 跨部門審批狀態檢查
        if not ai_generated and sender_id != 'system':
            if room.approval_status == 'pending':
                return {'success': False, 'error': '⏳ 此對話正在等待跨部門協作核准，核准後才可發送訊息'}
            if room.approval_status == 'rejected':
                return {'success': False, 'error': '❌ 此對話已被拒絕，無法發送訊息'}

        # 敏感關鍵字屏蔽（薪資、薪水、獎金、pay、salary 等）
        # AI 產生與 system 訊息不受限，避免 AI 回覆含這些字被誤擋
        if not ai_generated and sender_id != 'system':
            blocked, matched = check_blocked_content(content)
            if blocked:
                return {
                    'success': False,
                    'error': f'🚫 訊息含敏感關鍵字「{matched}」，本系統禁止在聊天中討論薪資、獎金等內容，請改用正式管道（HR / 簽呈）。',
                    'blocked_keyword': matched,
                }

        sender = self.attn.members.get(sender_id)
        sender_name = sender.name if sender else sender_id
        is_observer_msg = room.is_observer(sender_id)
        msg_type = 'observer_text' if is_observer_msg else 'text'
        msg = ChatMessage(room_id, sender_id, sender_name, content,
                         msg_type=msg_type, ai_generated=ai_generated)
        room.messages.append(msg)
        room.last_activity = msg.timestamp
        room.clear_typing(sender_id)

        # 更新未讀數
        for mid in room.all_members():
            if mid != sender_id:
                self.unread_count[mid] += 1

        # 持久化
        self._append_message_to_disk(room_id, msg)
        self._save_index()

        # 觸發 AI 自動回覆（非 AI 訊息 + 房設定允許）
        if trigger_ai_reply and not ai_generated and self.enable_ai_reply and room.ai_enabled:
            self._trigger_ai_reply(room, sender_id)

        return {'success': True, 'message': msg.to_dict()}

    # ════════════════════════════════════════════════
    # AI 自動回覆 — 核心真實感元素
    # ════════════════════════════════════════════════
    def _trigger_ai_reply(self, room: ChatRoom, from_sender_id: str):
        """
        當使用者發訊息後，觸發其他 participant 自動用 AI 回覆
        以背景執行緒處理，避免阻塞 API 回應
        """
        # 決定誰該回應：另一位 participant
        responders = [p for p in room.participants if p != from_sender_id]
        if not responders:
            return

        for responder_id in responders:
            # 設定 typing 狀態
            room.set_typing(responder_id)
            # 背景產生回覆
            t = threading.Thread(
                target=self._generate_ai_reply,
                args=(room.id, responder_id, from_sender_id),
                daemon=True
            )
            t.start()

    def _generate_ai_reply(self, room_id: str, responder_id: str, from_sender_id: str):
        """背景產生 AI 回覆（用 Ollama）"""
        with self._ai_lock:
            try:
                room = self.rooms.get(room_id)
                if not room:
                    return
                responder = self.attn.members.get(responder_id)
                sender = self.attn.members.get(from_sender_id)
                if not responder or not sender:
                    room.clear_typing(responder_id)
                    return

                # 建立角色 system prompt
                system = self._build_role_prompt(responder, sender, room)

                # 組裝對話歷史（最近 8 則，含觀察員發言）
                history = []
                for m in room.messages[-8:]:
                    if m.type not in ('text', 'observer_text'):
                        continue
                    role = 'assistant' if m.sender_id == responder_id else 'user'
                    # 觀察員訊息標註身分供 AI 理解上下文
                    content = m.content
                    if m.type == 'observer_text' and m.sender_id != responder_id:
                        content = f'[{m.sender_name}（中間主管）補充]：{content}'
                    history.append({'role': role, 'content': content})

                # 呼叫 Ollama
                reply = self._call_ollama(system, history)
                if reply:
                    # 再次確保 room 還在
                    if room_id in self.rooms:
                        self.send_message(room_id, responder_id, reply,
                                        ai_generated=True, trigger_ai_reply=False)
                room.clear_typing(responder_id)
            except Exception as e:
                print(f'[ChatManager] AI 回覆錯誤: {e}')
                try:
                    room.clear_typing(responder_id)
                except:
                    pass

    def _build_role_prompt(self, responder, sender, room) -> str:
        """依角色與關係建立 system prompt"""
        base = (
            f'你是凌策公司的「{responder.name}」，職務為「{responder.role}」，'
            f'所屬於「{responder.dept}」。'
        )
        # 個性基於角色
        persona = {
            '經理': '你風格權威而務實，用詞精簡，常問「時程」「交付」「風險」。',
            '副理': '你負責串連上下、協調跨課資源，說話中肯且有條理。',
            '課長': '你關注進度達成率與品質，技術底子紮實，用詞專業。',
            '副課長': '你直接對工程師，熟悉程式細節，回覆具體可執行。',
            '工程師': '你是前線實作者，技術導向，回覆簡短直白，偶爾會提到卡點與技術細節。',
        }.get(responder.role, '')

        relation_context = ''
        if room.relation == ChatRelation.DOWNWARD_CROSS:
            relation_context = '⚠️ 這是跨級對話（中間主管正在觀察），請注意回覆得體且維護層級禮貌。'
        elif room.relation == ChatRelation.PEER:
            relation_context = '這是與同事的平行對話，可以輕鬆但保持專業。'
        elif room.relation == ChatRelation.DOWNWARD_DIRECT:
            relation_context = '這是上級對你的訊息，請積極回應並回報進展。'
        elif room.relation == ChatRelation.UPWARD_DIRECT:
            relation_context = '這是你主動發給主管，請簡潔匯報或提出問題。'

        return (
            f'{base}{persona}\n{relation_context}\n'
            f'對方是 {sender.name}（{sender.role}）。\n'
            f'請用繁體中文、口語、簡短（1-3 句）回覆。不要加引號、不要解釋你是 AI，直接用該角色回話即可。'
        )

    def _call_ollama(self, system: str, messages: List[Dict]) -> Optional[str]:
        try:
            payload = {
                'model': OLLAMA_MODEL,
                'messages': [{'role': 'system', 'content': system}] + messages,
                'stream': False,
                'think': False,   # 試圖關閉 thinking（部分模型支援）
                'options': {'temperature': 0.8, 'num_predict': 800, 'num_ctx': 2048}
            }
            print(f'[Ollama] 呼叫中... ({len(messages)} 則歷史)')
            r = requests.post(f'{OLLAMA_URL}/api/chat', json=payload,
                              headers={'ngrok-skip-browser-warning': 'true'}, timeout=300)
            r.raise_for_status()
            data = r.json()
            msg = data.get('message', {})
            content = (msg.get('content') or '').strip()
            # Fallback：當 content 空（thinking 模式耗盡 tokens）取 thinking 最後一段當 content
            if not content:
                thinking = (msg.get('thinking') or '').strip()
                if thinking:
                    # 取思考的最後 1-2 句當作回答
                    parts = thinking.replace('\n', ' ').split('。')
                    content = '。'.join(parts[-2:]).strip() if len(parts) > 1 else thinking[-150:]
                    content = content[:200]
            print(f'[Ollama] 回覆：{content[:60]}...' if len(content) > 60 else f'[Ollama] 回覆：{content}')
            return content if content else None
        except Exception as e:
            print(f'[Ollama] 呼叫失敗: {e}')
            return None

    def set_typing(self, room_id: str, member_id: str):
        room = self.rooms.get(room_id)
        if room and member_id in room.participants:
            room.set_typing(member_id)
            return True
        return False

    def toggle_ai(self, room_id: str, enabled: bool):
        room = self.rooms.get(room_id)
        if room:
            room.ai_enabled = enabled
            self._save_index()
            return True
        return False

    # ════════════════════════════════════════════════
    # 跨部門協作審批
    # ════════════════════════════════════════════════
    # 服務/支援性質部門 — 本職就是跨部門協作，豁免上級核准
    _SERVICE_DEPTS = ('人事', 'HR', '人資', '財務', '會計', '總務', '行政')
    # 服務性職稱（助理、秘書等）— 日常就要跨部門聯繫
    _SERVICE_TITLES = ('助理', '秘書', '行政專員', 'HR', '人事專員')

    def _needs_cross_dept_approval(self, initiator, target) -> bool:
        """判斷是否需要跨部門協作審批"""
        # HR 權限豁免
        if initiator.is_hr:
            return False
        # 董事長等無上級者豁免
        if not initiator.supervisor_id:
            return False
        # 高階職稱豁免（總經理、協理、經理）— 有權自主跨部門協調
        t = initiator.title or ''
        if any(k in t for k in ('總經理', '協理', '經理')):
            return False
        # ✨ 服務/支援性部門豁免（人事、HR、財務、總務、行政）
        dept = (initiator.dept or '')
        if any(k in dept for k in self._SERVICE_DEPTS):
            return False
        # ✨ 服務性職稱豁免（助理、秘書、行政專員等）
        if any(k in t for k in self._SERVICE_TITLES):
            return False
        # 發起者與對方同頂層部門 → 不需要
        if _top_dept(initiator.dept) == _top_dept(target.dept):
            return False
        # 直屬上下級關係 → 不需要（管理鏈內）
        if initiator.supervisor_id == target.id or target.supervisor_id == initiator.id:
            return False
        return True

    def approve_room(self, approver_id: str, room_id: str) -> Dict:
        room = self.rooms.get(room_id)
        if not room:
            return {'success': False, 'error': '對話不存在'}
        if room.approval_status != 'pending':
            return {'success': False, 'error': f'此對話狀態為 {room.approval_status}，無法核准'}
        actor = self.attn.members.get(approver_id)
        if approver_id != room.approver_id and not (actor and actor.is_hr):
            return {'success': False, 'error': '您不是此對話的核准人'}
        room.approval_status = 'approved'
        room.approval_reason = '已核准'
        actor_name = actor.name if actor else approver_id
        msg = ChatMessage(
            room_id, 'system', '系統',
            f'✅ {actor_name} 已核准此跨部門協作，雙方可開始訊息往來。',
            msg_type='alert'
        )
        room.messages.append(msg)
        self._append_message_to_disk(room_id, msg)
        self._save_index()
        # 通知參與者
        for pid in room.participants:
            self.attn._add_notification(pid, 'chat_approved',
                f'✅ 您的跨部門對話已被 {actor_name} 核准。', priority='normal')
        return {'success': True, 'room': room.to_dict(self.attn.members)}

    def reject_room(self, approver_id: str, room_id: str, reason: str = '') -> Dict:
        room = self.rooms.get(room_id)
        if not room:
            return {'success': False, 'error': '對話不存在'}
        if room.approval_status != 'pending':
            return {'success': False, 'error': f'此對話狀態為 {room.approval_status}，無法拒絕'}
        actor = self.attn.members.get(approver_id)
        if approver_id != room.approver_id and not (actor and actor.is_hr):
            return {'success': False, 'error': '您不是此對話的核准人'}
        room.approval_status = 'rejected'
        room.approval_reason = reason or '未提供理由'
        actor_name = actor.name if actor else approver_id
        msg = ChatMessage(
            room_id, 'system', '系統',
            f'❌ {actor_name} 拒絕了此跨部門協作。{f"理由：{reason}" if reason else ""}',
            msg_type='alert'
        )
        room.messages.append(msg)
        self._append_message_to_disk(room_id, msg)
        self._save_index()
        for pid in room.participants:
            self.attn._add_notification(pid, 'chat_rejected',
                f'❌ 您的跨部門對話被 {actor_name} 拒絕。{reason}', priority='high')
        return {'success': True, 'room': room.to_dict(self.attn.members)}

    def list_pending_approvals(self, approver_id: str) -> List[Dict]:
        """列出某人需要審批的對話"""
        result = []
        for r in self.rooms.values():
            if r.approval_status == 'pending' and r.approver_id == approver_id:
                result.append(r.to_dict(self.attn.members))
        return result

    def list_rooms(self, member_id: str) -> List[Dict]:
        """列出該成員參與/觀察的所有聊天室"""
        result = []
        for room in self.rooms.values():
            if room.can_view(member_id):
                info = room.to_dict(self.attn.members)
                info['my_role'] = 'participant' if member_id in room.participants else 'observer'
                # 計算該成員在此房的未讀數
                unread = sum(
                    1 for msg in room.messages
                    if member_id not in msg.read_by and msg.sender_id != member_id
                       and msg.type in ('text', 'observer_text')
                )
                info['unread'] = unread
                result.append(info)
        # 依最後活動時間排序
        result.sort(key=lambda x: x['last_activity'], reverse=True)
        return result

    def _try_rebuild_room(self, room_id: str, requester_id: str):
        """嘗試從 room_id 'room_<id1>_<id2>' 解出雙方成員並重建聊天室"""
        if not room_id.startswith('room_'): return None
        body = room_id[5:]   # 去 'room_' 前綴
        # 兩個 member id 用 '_' 分隔，但 id 本身可能含 '-'（MGR-001）不含 '_'
        # 嘗試各種 split 位置
        parts = body.split('_')
        if len(parts) < 2: return None
        # 嘗試前 n 段 + 後 m 段組合（簡化：前 1 段 + 後 1 段）
        candidates = []
        for i in range(1, len(parts)):
            a = '_'.join(parts[:i])
            b = '_'.join(parts[i:])
            candidates.append((a, b))
        for a, b in candidates:
            if a in self.attn.members and b in self.attn.members:
                # 必須有一邊是 requester 才重建（避免任意重建）
                if requester_id not in (a, b):
                    continue
                result = self.create_or_get_room(a, b)
                if result.get('success'):
                    print(f'[ChatManager] 自動恢復聊天室 {room_id}（{a} ↔ {b}）')
                    return self.rooms.get(room_id)
        return None

    def _diagnose_room_id(self, room_id: str) -> str:
        """給 friendly 錯誤訊息，告訴 UI 為什麼找不到"""
        if not room_id: return '未提供 room_id'
        if not room_id.startswith('room_'): return '格式錯誤（應為 room_xxx_yyy）'
        body = room_id[5:]
        parts = body.split('_')
        # 嘗試識別成員
        for i in range(1, len(parts)):
            a = '_'.join(parts[:i]); b = '_'.join(parts[i:])
            if a in self.attn.members and b in self.attn.members:
                return f'{a} ↔ {b} 尚未建立對話'
        return '無法識別參與者 ID'


    def get_messages(self, room_id: str, member_id: str, since: Optional[str] = None) -> Dict:
        """取得聊天室訊息。若傳入 since (ISO timestamp) 只回傳之後的新訊息

        ★ 自動恢復：若 room_id 符合 'room_<id1>_<id2>' 格式但 room 不在記憶體（例如
          server 重啟後 index.json 載入不完整、或房間被意外清除），嘗試重建。
        """
        room = self.rooms.get(room_id)
        if not room:
            # 嘗試自動恢復
            rebuilt = self._try_rebuild_room(room_id, member_id)
            if rebuilt:
                room = rebuilt
            else:
                # 額外診斷訊息：是否是 room_id 格式錯誤、還是參與者不存在
                detail = self._diagnose_room_id(room_id)
                return {
                    'success': False,
                    'error': f'聊天室不存在（{detail}）',
                    'error_code': 'ROOM_NOT_FOUND',
                    'room_id': room_id,
                }
        if not room.can_view(member_id):
            return {'success': False, 'error': '無權查看'}

        msgs = room.messages
        if since:
            try:
                since_dt = datetime.fromisoformat(since)
                msgs = [m for m in msgs if m.timestamp > since_dt]
            except:
                pass

        # 標記已讀（帶時間戳）
        now_iso = datetime.now().isoformat()
        changed = False
        for m in room.messages:
            if m.sender_id != member_id and member_id not in m.read_by:
                m.read_by[member_id] = now_iso
                changed = True
        if changed:
            self._rewrite_room_log(room)
        # 重算未讀
        self._recompute_unread(member_id)

        return {
            'success': True,
            'room': room.to_dict(self.attn.members),
            'messages': [m.to_dict() for m in msgs],
            'my_role': 'participant' if member_id in room.participants else 'observer' if member_id in room.observers else None,
        }

    def _recompute_unread(self, member_id: str):
        total = 0
        for room in self.rooms.values():
            if room.can_view(member_id):
                total += sum(
                    1 for m in room.messages
                    if member_id not in m.read_by and m.sender_id != member_id
                       and m.type in ('text', 'observer_text')
                )
        self.unread_count[member_id] = total

    def get_unread_count(self, member_id: str) -> int:
        return self.unread_count.get(member_id, 0)

    def stats(self) -> Dict:
        return {
            'total_rooms': len(self.rooms),
            'total_messages': sum(len(r.messages) for r in self.rooms.values()),
            'rooms_by_relation': {
                r: sum(1 for room in self.rooms.values() if room.relation == r)
                for r in [ChatRelation.PEER, ChatRelation.DOWNWARD_DIRECT,
                         ChatRelation.UPWARD_DIRECT, ChatRelation.DOWNWARD_CROSS]
            }
        }


if __name__ == '__main__':
    # 簡單測試
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from attendance_manager import AttendanceManager
    from members_data import build_initial_org

    attn = AttendanceManager(build_initial_org())
    chat = ChatManager(attn)

    # 測試：經理 → 工程師（跨級 4 層）
    print('\n=== 測試 1：經理 MGR-001 → 工程師 ENG-001（跨 4 級）===')
    r = chat.create_or_get_room('MGR-001', 'ENG-001')
    print(f'關係：{r["analysis"]["relation"]}')
    print(f'允許：{r["analysis"]["allowed"]}')
    print(f'中間主管數：{len(r["analysis"]["observers"])}')
    print(f'理由：{r["analysis"]["reason"]}')

    # 測試：同組平行（工程師 → 工程師）
    print('\n=== 測試 2：ENG-001 → ENG-002（同組平行）===')
    r = chat.create_or_get_room('ENG-001', 'ENG-002')
    print(f'關係：{r["analysis"]["relation"]}  允許：{r["analysis"]["allowed"]}')
    print(f'理由：{r["analysis"]["reason"]}')

    # 測試：工程師 → 經理（跨級下對上，不允許）
    print('\n=== 測試 3：ENG-001 → MGR-001（跨級下對上）===')
    r = chat.create_or_get_room('ENG-001', 'MGR-001')
    print(f'關係：{r["analysis"]["relation"]}  允許：{r["analysis"]["allowed"]}')
    print(f'理由：{r["analysis"]["reason"]}')

    # 測試：直屬下對上
    print('\n=== 測試 4：ENG-001 → DSC-001（直屬下對上）===')
    r = chat.create_or_get_room('ENG-001', 'DSC-001')
    print(f'關係：{r["analysis"]["relation"]}  允許：{r["analysis"]["allowed"]}')

    print(f'\n總聊天室：{chat.stats()["total_rooms"]}')
