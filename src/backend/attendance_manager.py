#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
凌策公司 — AttendanceManager 出缺勤管理器

核心功能：
1. 狀態機管理四種狀態：Online / Resting / Offline / Abnormal
2. 全域時間服務：每分鐘比對當前時間與預設時段
3. 組織層級：經理 > 副理 > 課長 > 副課長 > 工程師
4. 自動化排程：週二 16:00 推送目標、週三 09:00 稽核回報
"""

from datetime import datetime, time, timedelta, date
from enum import Enum
from typing import Dict, List, Optional, Tuple  # noqa: F401
import json
import os


# ══════════════════════════════════════════════════════════
# 狀態定義
# ══════════════════════════════════════════════════════════
class AttendanceStatus(Enum):
    """四種出缺勤狀態"""
    ONLINE = 'online'        # 上班中（綠燈）
    RESTING = 'resting'      # 休息中（黃燈）
    OFFLINE = 'offline'      # 未上班/已下班（灰燈）
    ABNORMAL = 'abnormal'    # 異常未打卡（紅燈）

    @property
    def label(self):
        return {'online': '上班中', 'resting': '休息中', 'offline': '未上班/已下班', 'abnormal': '異常'}[self.value]

    @property
    def color(self):
        return {'online': 'green', 'resting': 'yellow', 'offline': 'gray', 'abnormal': 'red'}[self.value]


# ══════════════════════════════════════════════════════════
# 時間段定義
# ══════════════════════════════════════════════════════════
class TimeWindows:
    """所有預設時段"""
    CLOCK_IN_START = time(8, 0)      # 上班打卡區間起
    CLOCK_IN_END = time(9, 0)        # 上班打卡區間迄（超過視為未到工）
    CLOCK_OUT_START = time(17, 20)   # 下班打卡區間起
    CLOCK_OUT_END = time(18, 20)     # 下班打卡區間迄

    REST_MORNING = (time(10, 0), time(10, 10))     # 上午休息
    REST_LUNCH = (time(12, 10), time(13, 10))      # 午休
    REST_AFTERNOON = (time(15, 0), time(15, 10))   # 下午休息

    WORK_DAY_END = time(18, 20)  # 一日結束

    @classmethod
    def is_in_rest_period(cls, t: time) -> bool:
        """判斷當前時間是否在休息時段"""
        for start, end in [cls.REST_MORNING, cls.REST_LUNCH, cls.REST_AFTERNOON]:
            if start <= t <= end:
                return True
        return False

    @classmethod
    def current_rest_type(cls, t: time) -> Optional[str]:
        """取得當前休息類型"""
        if cls.REST_MORNING[0] <= t <= cls.REST_MORNING[1]:
            return '上午茶歇'
        if cls.REST_LUNCH[0] <= t <= cls.REST_LUNCH[1]:
            return '午休'
        if cls.REST_AFTERNOON[0] <= t <= cls.REST_AFTERNOON[1]:
            return '下午茶歇'
        return None


# ══════════════════════════════════════════════════════════
# 成員資料模型
# ══════════════════════════════════════════════════════════
class Member:
    """組織成員"""

    ROLE_HIERARCHY = ['經理', '人事經理', '副理', '課長', '副課長', '工程師']

    def __init__(self, mid: str, name: str, role: str, dept: str,
                 supervisor_id: Optional[str] = None, avatar: str = '👤',
                 is_hr: bool = False, title: Optional[str] = None):
        self.id = mid
        self.name = name
        self.role = role          # 6 階層角色：經理/人事經理/副理/課長/副課長/工程師
        self.title = title or role  # 實際職稱（如 "總經理"、"行銷長"、"MIS 工程師"）
        self.dept = dept
        self.supervisor_id = supervisor_id
        self.avatar = avatar
        self.is_hr = is_hr

        # 出缺勤狀態
        self.clock_in_time: Optional[datetime] = None
        self.clock_out_time: Optional[datetime] = None
        self._forced_status: Optional[AttendanceStatus] = None  # 人為覆寫（如休假）

        # 週目標與回報
        self.weekly_objective: Optional[Dict] = None
        self.weekly_report: Optional[Dict] = None
        self.notified_for_report = False

    def role_level(self) -> int:
        """層級等級：0=經理，1=人事經理（視為同級），2=副理..."""
        # 人事經理視覺上與副理同級，但權限獨立
        if self.role == '人事經理':
            return 1
        try:
            return self.ROLE_HIERARCHY.index(self.role)
        except ValueError:
            return 5

    def to_dict(self, include_status: Optional[AttendanceStatus] = None) -> Dict:
        return {
            'id': self.id,
            'name': self.name,
            'role': self.role,
            'title': self.title,
            'role_level': self.role_level(),
            'dept': self.dept,
            'supervisor_id': self.supervisor_id,
            'avatar': self.avatar,
            'is_hr': self.is_hr,
            'clock_in_time': self.clock_in_time.strftime('%H:%M') if self.clock_in_time else None,
            'clock_out_time': self.clock_out_time.strftime('%H:%M') if self.clock_out_time else None,
            'status': (include_status or AttendanceStatus.OFFLINE).value,
            'status_label': (include_status or AttendanceStatus.OFFLINE).label,
            'status_color': (include_status or AttendanceStatus.OFFLINE).color,
            'weekly_objective': self.weekly_objective,
            'weekly_report': self.weekly_report,
            'has_report': self.weekly_report is not None,
            'objective_progress': self.weekly_objective.get('progress', 0) if self.weekly_objective else 0,
        }


# ══════════════════════════════════════════════════════════
# AttendanceManager 主管理器
# ══════════════════════════════════════════════════════════
class AttendanceManager:
    """出缺勤管理器 — 核心狀態機 + 時間服務 + 組織編輯"""

    def __init__(self, members: List[Member], org_file: Optional[str] = None):
        self.members: Dict[str, Member] = {m.id: m for m in members}
        self.notifications: List[Dict] = []
        self._demo_time: Optional[datetime] = None
        self._org_file = org_file  # 若指定，組織變更會持久化到此檔案
        # 如果檔案存在，載入覆寫（HR 先前的編輯會還原）
        if org_file and os.path.exists(org_file):
            self._load_org_from_file(org_file)

    # ──────────────────────────────────────────
    # 組織持久化
    # ──────────────────────────────────────────
    def _save_org_to_file(self):
        if not self._org_file:
            return
        data = [{
            'id': m.id, 'name': m.name, 'role': m.role, 'title': m.title, 'dept': m.dept,
            'supervisor_id': m.supervisor_id, 'avatar': m.avatar, 'is_hr': m.is_hr
        } for m in self.members.values()]
        with open(self._org_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_org_from_file(self, path: str):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.members = {}
            for row in data:
                m = Member(row['id'], row['name'], row['role'], row['dept'],
                          row.get('supervisor_id'), row.get('avatar', '👤'),
                          is_hr=row.get('is_hr', False), title=row.get('title'))
                self.members[m.id] = m
            print(f'[AttendanceManager] 已從 {path} 載入 {len(self.members)} 位成員')
            # 啟動時自動備份（時間戳命名，保留最近 10 份）
            try:
                backup_dir = os.path.join(os.path.dirname(path), 'backups')
                os.makedirs(backup_dir, exist_ok=True)
                ts = datetime.now().strftime('%Y%m%d-%H%M%S')
                backup_path = os.path.join(backup_dir, f'org_data.{ts}.json')
                with open(backup_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                # 清理舊備份（保留最近 10 份）
                backups = sorted([f for f in os.listdir(backup_dir) if f.startswith('org_data.')])
                for old in backups[:-10]:
                    try: os.remove(os.path.join(backup_dir, old))
                    except: pass
                print(f'[AttendanceManager] 組織資料備份 → {backup_path}')
            except Exception as be:
                print(f'[AttendanceManager] 備份失敗（不影響運作）: {be}')
        except Exception as e:
            print(f'[AttendanceManager] 載入組織檔案失敗: {e}')

    # ──────────────────────────────────────────
    # 組織編輯（HR 權限）
    # ──────────────────────────────────────────
    def check_hr_permission(self, actor_id: str) -> bool:
        """嚴格 HR（用於 chat 豁免等）"""
        actor = self.members.get(actor_id)
        return bool(actor and actor.is_hr)

    def check_org_edit_permission(self, actor_id: str) -> bool:
        """組織編輯權限：HR 或 總經理"""
        actor = self.members.get(actor_id)
        if not actor:
            return False
        if actor.is_hr:
            return True
        # 總經理 也有組織編輯權限
        if actor.title and '總經理' in actor.title:
            return True
        return False

    def check_view_all_permission(self, actor_id: str) -> bool:
        """可檢視全組織圖：HR / 總經理 / 無上級者（董事長）"""
        actor = self.members.get(actor_id)
        if not actor:
            return False
        if actor.is_hr:
            return True
        if actor.title and '總經理' in actor.title:
            return True
        if not actor.supervisor_id:  # 董事長 / 最高層
            return True
        return False

    # ══════════════════════════════════════════════════════
    # 稽核日誌（HR 編輯追蹤）
    # ══════════════════════════════════════════════════════
    def _audit_log_path(self) -> Optional[str]:
        if not self._org_file:
            return None
        return os.path.join(os.path.dirname(self._org_file), 'audit_log.jsonl')

    def _log_audit(self, action: str, actor_id: str, target_id: str,
                   before: Optional[Dict] = None, after: Optional[Dict] = None,
                   note: str = ''):
        """記錄 HR / 總經理的組織編輯操作"""
        path = self._audit_log_path()
        if not path:
            return
        actor = self.members.get(actor_id)
        target = self.members.get(target_id)
        entry = {
            'timestamp': datetime.now().isoformat(),
            'action': action,  # add_member/update_member/remove_member/grant_hr/revoke_hr
            'actor_id': actor_id,
            'actor_name': actor.name if actor else actor_id,
            'actor_title': actor.title if actor else '',
            'target_id': target_id,
            'target_name': target.name if target else target_id,
            'before': before,
            'after': after,
            'note': note,
        }
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        except Exception as e:
            print(f'[audit] 寫檔失敗: {e}')

    def get_audit_log(self, limit: int = 200, action_filter: Optional[str] = None,
                      target_id_filter: Optional[str] = None) -> List[Dict]:
        """取得稽核日誌（最新在前）"""
        path = self._audit_log_path()
        if not path or not os.path.exists(path):
            return []
        entries = []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        e = json.loads(line)
                        if action_filter and e.get('action') != action_filter:
                            continue
                        if target_id_filter and e.get('target_id') != target_id_filter:
                            continue
                        entries.append(e)
                    except:
                        pass
        except Exception as e:
            print(f'[audit] 讀檔失敗: {e}')
        # 取最後 limit 筆、反序（最新在前）
        return entries[-limit:][::-1]

    def can_grant_hr(self, actor_id: str, target_id: str) -> Tuple[bool, str]:
        """判斷 actor 是否可授予/撤銷 target 的 HR 權限
        規則：
          - 總經理：可對任何人授予/撤銷
          - 現任 HR（人事經理）：可對任何人授予/撤銷（不限部門）
          - 其他：無權
        """
        actor = self.members.get(actor_id)
        target = self.members.get(target_id)
        if not actor or not target:
            return False, '成員不存在'
        if actor.title and '總經理' in actor.title:
            return True, ''
        if actor.is_hr:
            return True, ''
        return False, '僅總經理或現任 HR 可調整 HR 權限'

    def add_member(self, actor_id: str, member_data: Dict) -> Dict:
        if not self.check_org_edit_permission(actor_id):
            return {'success': False, 'error': '無權限：需人事經理或總經理'}
        # 若新增成員時順便設 is_hr=True，需額外驗證
        if member_data.get('is_hr'):
            actor = self.members.get(actor_id)
            # 僅總經理可建立已帶 HR 權限的新成員
            if not (actor and actor.title and '總經理' in actor.title):
                return {'success': False, 'error': '僅總經理可建立已帶 HR 權限的新成員'}
        mid = member_data.get('id') or f'NEW-{len(self.members)+1:03d}'
        if mid in self.members:
            return {'success': False, 'error': f'ID {mid} 已存在'}
        m = Member(
            mid=mid,
            name=member_data.get('name', ''),
            role=member_data.get('role', '工程師'),
            dept=member_data.get('dept', ''),
            supervisor_id=member_data.get('supervisor_id'),
            avatar=member_data.get('avatar', '👤'),
            is_hr=bool(member_data.get('is_hr', False)),
        )
        self.members[mid] = m
        self._save_org_to_file()
        self._log_audit('add_member', actor_id, mid, after=member_data,
                        note=f'新增成員：{m.name}（{m.title}）')
        return {'success': True, 'member': m.to_dict()}

    def update_member(self, actor_id: str, mid: str, updates: Dict) -> Dict:
        if not self.check_org_edit_permission(actor_id):
            return {'success': False, 'error': '無權限：需人事經理或總經理'}
        # is_hr 變更需要額外權限
        if 'is_hr' in updates:
            ok, reason = self.can_grant_hr(actor_id, mid)
            if not ok:
                return {'success': False, 'error': f'無法調整 HR 權限：{reason}'}
        m = self.members.get(mid)
        if not m:
            return {'success': False, 'error': f'成員 {mid} 不存在'}
        # 避免循環：supervisor_id 不能指向自己或下屬
        new_sup = updates.get('supervisor_id')
        if new_sup is not None and new_sup != m.supervisor_id:
            if new_sup == mid:
                return {'success': False, 'error': '不能將自己設為上級'}
            # 檢查循環
            subs_ids = {s.id for s in self.get_subordinates(mid, recursive=True)}
            if new_sup in subs_ids:
                return {'success': False, 'error': '不能將下屬設為上級（會造成循環）'}
            m.supervisor_id = new_sup
        # 記錄變更前的值
        before = {}
        for field in ('name', 'role', 'title', 'dept', 'avatar', 'is_hr', 'supervisor_id'):
            if field in updates:
                before[field] = getattr(m, field, None)
        for field in ('name', 'role', 'title', 'dept', 'avatar', 'is_hr'):
            if field in updates:
                setattr(m, field, updates[field])
        self._save_org_to_file()
        # 稽核：is_hr 變更拆為 grant/revoke，其餘為 update_member
        if 'is_hr' in updates and before.get('is_hr') != updates['is_hr']:
            action = 'grant_hr' if updates['is_hr'] else 'revoke_hr'
            self._log_audit(action, actor_id, mid,
                            before={'is_hr': before.get('is_hr')},
                            after={'is_hr': updates['is_hr']},
                            note=f"{'授予' if updates['is_hr'] else '撤銷'} {m.name} 的 HR 權限")
            other_updates = {k: v for k, v in updates.items() if k != 'is_hr'}
            if other_updates:
                self._log_audit('update_member', actor_id, mid,
                                before={k: before.get(k) for k in other_updates},
                                after=other_updates)
        else:
            self._log_audit('update_member', actor_id, mid, before=before, after=updates)
        return {'success': True, 'member': m.to_dict()}

    def remove_member(self, actor_id: str, mid: str) -> Dict:
        if not self.check_org_edit_permission(actor_id):
            return {'success': False, 'error': '無權限：需人事經理或總經理'}
        m = self.members.get(mid)
        if not m:
            return {'success': False, 'error': '成員不存在'}
        # 不可移除最高層（無上級者）
        if m.supervisor_id is None:
            roots = [x for x in self.members.values() if x.supervisor_id is None]
            if len(roots) == 1:
                return {'success': False, 'error': '不可移除唯一根節點（最高主管）'}
        # 記錄被刪成員的快照
        snapshot = {
            'id': m.id, 'name': m.name, 'title': m.title, 'role': m.role,
            'dept': m.dept, 'supervisor_id': m.supervisor_id, 'is_hr': m.is_hr,
        }
        # 將其下屬改為直接回報給此人的上級
        for sub in list(self.members.values()):
            if sub.supervisor_id == mid:
                sub.supervisor_id = m.supervisor_id
        del self.members[mid]
        self._save_org_to_file()
        self._log_audit('remove_member', actor_id, mid, before=snapshot,
                        note=f'移除成員：{m.name}（{m.title}）')
        return {'success': True, 'removed': mid}

    # ──────────────────────────────────────────
    # 時間服務
    # ──────────────────────────────────────────
    def now(self) -> datetime:
        """取得當前時間（支援展示覆寫）"""
        return self._demo_time if self._demo_time else datetime.now()

    def set_demo_time(self, dt: Optional[datetime]):
        """設定展示用時間（用於 Demo）"""
        self._demo_time = dt

    # ──────────────────────────────────────────
    # 狀態機核心邏輯
    # ──────────────────────────────────────────
    def get_status(self, member_id: str) -> AttendanceStatus:
        """
        狀態機判斷：根據當前時間 + 打卡記錄計算成員狀態
        規則：
          - 已打下班卡 → OFFLINE
          - 已打上班卡 + 休息時段 → RESTING
          - 已打上班卡 + 工作時段 → ONLINE
          - 未打上班卡 + 超過 09:00 → ABNORMAL
          - 未打上班卡 + 早於 09:00 → OFFLINE（尚未上班）
        """
        m = self.members.get(member_id)
        if not m:
            return AttendanceStatus.OFFLINE

        if m._forced_status:
            return m._forced_status

        now = self.now()
        current_t = now.time()
        today = now.date()

        # 檢查打卡記錄是否為今天
        clocked_in_today = (
            m.clock_in_time is not None and m.clock_in_time.date() == today
        )
        clocked_out_today = (
            m.clock_out_time is not None and m.clock_out_time.date() == today
        )

        # 已下班
        if clocked_out_today:
            return AttendanceStatus.OFFLINE

        # 已打上班卡
        if clocked_in_today:
            if TimeWindows.is_in_rest_period(current_t):
                return AttendanceStatus.RESTING
            return AttendanceStatus.ONLINE

        # 未打上班卡
        if current_t > TimeWindows.CLOCK_IN_END:
            # 超過 09:00 仍未打卡 → 異常
            # 但如果已經過了下班時間，則視為離線（可能請假）
            if current_t > TimeWindows.WORK_DAY_END:
                return AttendanceStatus.OFFLINE
            return AttendanceStatus.ABNORMAL

        return AttendanceStatus.OFFLINE  # 尚未到上班時間

    # ──────────────────────────────────────────
    # 打卡動作
    # ──────────────────────────────────────────
    def clock_in(self, member_id: str, timestamp: Optional[datetime] = None) -> Dict:
        """上班打卡"""
        m = self.members.get(member_id)
        if not m:
            return {'success': False, 'error': 'Member not found'}

        ts = timestamp or self.now()
        t = ts.time()

        if t < TimeWindows.CLOCK_IN_START:
            return {'success': False, 'error': f'尚未到上班打卡時間（{TimeWindows.CLOCK_IN_START.strftime("%H:%M")} 起）'}

        # 已打過上班卡
        if m.clock_in_time and m.clock_in_time.date() == ts.date():
            return {'success': False, 'error': '今日已打上班卡', 'clock_in_time': m.clock_in_time.isoformat()}

        m.clock_in_time = ts
        is_late = t > TimeWindows.CLOCK_IN_END

        return {
            'success': True,
            'member': m.name,
            'clock_in_time': ts.strftime('%H:%M:%S'),
            'is_late': is_late,
            'status': self.get_status(member_id).value
        }

    def clock_out(self, member_id: str, timestamp: Optional[datetime] = None) -> Dict:
        """下班打卡"""
        m = self.members.get(member_id)
        if not m:
            return {'success': False, 'error': 'Member not found'}

        ts = timestamp or self.now()
        t = ts.time()

        if t < TimeWindows.CLOCK_OUT_START:
            return {'success': False, 'error': f'尚未到下班打卡時間（{TimeWindows.CLOCK_OUT_START.strftime("%H:%M")} 起）'}

        if not m.clock_in_time or m.clock_in_time.date() != ts.date():
            return {'success': False, 'error': '今日尚未打上班卡'}

        if m.clock_out_time and m.clock_out_time.date() == ts.date():
            return {'success': False, 'error': '今日已打下班卡'}

        m.clock_out_time = ts
        return {
            'success': True,
            'member': m.name,
            'clock_out_time': ts.strftime('%H:%M:%S'),
            'status': self.get_status(member_id).value
        }

    # ──────────────────────────────────────────
    # 組織層級查詢
    # ──────────────────────────────────────────
    def get_supervisor(self, member_id: str) -> Optional[Member]:
        """取得直屬上級"""
        m = self.members.get(member_id)
        if not m or not m.supervisor_id:
            return None
        return self.members.get(m.supervisor_id)

    def get_subordinates(self, member_id: str, recursive: bool = False) -> List[Member]:
        """取得下屬（可遞迴取得整個子樹）"""
        direct = [m for m in self.members.values() if m.supervisor_id == member_id]
        if not recursive:
            return direct
        all_subs = list(direct)
        for sub in direct:
            all_subs.extend(self.get_subordinates(sub.id, recursive=True))
        return all_subs

    def get_peers(self, member_id: str) -> List[Member]:
        """取得同階層同上級（平行節點）"""
        m = self.members.get(member_id)
        if not m or not m.supervisor_id:
            return []
        return [
            o for o in self.members.values()
            if o.id != member_id and o.supervisor_id == m.supervisor_id
        ]

    def build_org_tree(self, root_id: Optional[str] = None) -> Dict:
        """建立組織樹狀結構（含狀態資訊）"""
        # 找到根節點
        if root_id is None:
            roots = [m for m in self.members.values() if m.supervisor_id is None]
            if not roots:
                return {}
            root = roots[0]
        else:
            root = self.members.get(root_id)
            if not root:
                return {}

        def build_node(m: Member) -> Dict:
            status = self.get_status(m.id)
            node = m.to_dict(include_status=status)
            node['children'] = [
                build_node(sub) for sub in sorted(
                    [s for s in self.members.values() if s.supervisor_id == m.id],
                    key=lambda x: (x.role_level(), x.name)
                )
            ]
            return node

        return build_node(root)

    # ──────────────────────────────────────────
    # 自動化排程任務
    # ──────────────────────────────────────────
    def should_distribute_objectives(self) -> bool:
        """檢查是否為週二 16:00（目標推送時點）"""
        now = self.now()
        return now.weekday() == 1 and now.hour == 16 and now.minute < 5

    def should_audit_reports(self) -> bool:
        """檢查是否為週三 09:00（回報稽核時點）"""
        now = self.now()
        return now.weekday() == 2 and now.hour == 9 and now.minute < 5

    def distribute_objectives(self, objectives_map: Dict[str, Dict]) -> Dict:
        """
        推送週目標
        objectives_map: {role: {title, description, kpi}}
        須確認成員上班中才推送，否則排入補發隊列
        """
        distributed = []
        queued = []

        for mid, m in self.members.items():
            status = self.get_status(mid)
            role_obj = objectives_map.get(m.role, objectives_map.get('default'))
            if not role_obj:
                continue

            objective = {
                **role_obj,
                'distributed_at': self.now().isoformat(),
                'progress': 0,
                'owner_role': m.role,
                'supervisor_role': self.get_supervisor(mid).role if self.get_supervisor(mid) else None,
            }

            if status == AttendanceStatus.ONLINE:
                m.weekly_objective = objective
                distributed.append({'member_id': mid, 'member_name': m.name, 'role': m.role})
                self._add_notification(mid, 'objective_received', f'已收到本週目標：{role_obj.get("title","")}')
            else:
                objective['queued'] = True
                queued.append({'member_id': mid, 'member_name': m.name, 'role': m.role, 'reason': status.label})

        return {
            'distributed': distributed,
            'queued': queued,
            'total_distributed': len(distributed),
            'total_queued': len(queued),
        }

    def audit_reports(self) -> Dict:
        """
        稽核回報
        檢查所有成員是否已填寫回報，未填且上班中者發送提醒
        """
        missing = []
        reminded = []
        completed = []

        for mid, m in self.members.items():
            # 經理以上不檢查（彙整者）
            if m.role_level() == 0:
                continue

            if m.weekly_report:
                completed.append({'member_id': mid, 'name': m.name, 'role': m.role})
            else:
                missing.append({'member_id': mid, 'name': m.name, 'role': m.role})
                status = self.get_status(mid)
                if status == AttendanceStatus.ONLINE and not m.notified_for_report:
                    m.notified_for_report = True
                    reminded.append({'member_id': mid, 'name': m.name})
                    self._add_notification(mid, 'report_reminder', '請盡快填寫本週進度回報（已完成、阻礙點、下週預計）', priority='high')

        return {
            'total_members': len([m for m in self.members.values() if m.role_level() > 0]),
            'completed_count': len(completed),
            'missing_count': len(missing),
            'reminded_count': len(reminded),
            'completed': completed,
            'missing': missing,
            'reminded': reminded,
        }

    # ──────────────────────────────────────────
    # 回報與目標
    # ──────────────────────────────────────────
    def submit_report(self, member_id: str, completed_items: List[str],
                      blockers: List[str], next_week_plan: List[str]) -> Dict:
        """提交週回報（結構化）"""
        m = self.members.get(member_id)
        if not m:
            return {'success': False, 'error': 'Member not found'}

        report = {
            'completed': completed_items,
            'blockers': blockers,
            'next_week': next_week_plan,
            'submitted_at': self.now().isoformat(),
            'owner_role': m.role,
            'supervisor_role': self.get_supervisor(member_id).role if self.get_supervisor(member_id) else None,
        }
        m.weekly_report = report
        m.notified_for_report = False

        # 觸發上層彙整（示意 — 實際可透過 Ollama 產生摘要）
        supervisor = self.get_supervisor(member_id)
        if supervisor:
            self._add_notification(supervisor.id, 'subordinate_report', f'{m.name} 已提交週回報，可進行彙整審閱')

        return {'success': True, 'member': m.name, 'report': report}

    def aggregate_team_report(self, supervisor_id: str) -> Dict:
        """上級彙整下屬回報（垂直彙整）"""
        supervisor = self.members.get(supervisor_id)
        if not supervisor:
            return {'success': False, 'error': 'Supervisor not found'}

        subs = self.get_subordinates(supervisor_id)
        submitted = [s for s in subs if s.weekly_report]
        pending = [s for s in subs if not s.weekly_report]

        all_completed = []
        all_blockers = []
        all_next_week = []

        for s in submitted:
            r = s.weekly_report
            all_completed.extend([f'[{s.name}] {i}' for i in r.get('completed', [])])
            all_blockers.extend([f'[{s.name}] {i}' for i in r.get('blockers', [])])
            all_next_week.extend([f'[{s.name}] {i}' for i in r.get('next_week', [])])

        return {
            'supervisor': supervisor.name,
            'supervisor_role': supervisor.role,
            'team_size': len(subs),
            'submitted_count': len(submitted),
            'pending_count': len(pending),
            'pending_members': [{'id': p.id, 'name': p.name} for p in pending],
            'aggregated': {
                'completed': all_completed,
                'blockers': all_blockers,
                'next_week': all_next_week,
            }
        }

    def detect_parallel_gaps(self) -> List[Dict]:
        """偵測平行節點進度落差（進度差 > 30% 標記需平行溝通）"""
        gaps = []
        # 依上級分組
        groups: Dict[str, List[Member]] = {}
        for m in self.members.values():
            if m.supervisor_id:
                groups.setdefault(m.supervisor_id, []).append(m)

        for sup_id, peers in groups.items():
            if len(peers) < 2:
                continue
            progresses = [(p, p.weekly_objective.get('progress', 0) if p.weekly_objective else 0) for p in peers]
            max_p = max(progresses, key=lambda x: x[1])
            min_p = min(progresses, key=lambda x: x[1])
            if max_p[1] - min_p[1] > 30:
                sup = self.members.get(sup_id)
                gaps.append({
                    'supervisor': sup.name if sup else None,
                    'supervisor_id': sup_id,
                    'peers': [{'name': p.name, 'progress': prog} for p, prog in progresses],
                    'gap': max_p[1] - min_p[1],
                    'leading': max_p[0].name,
                    'lagging': min_p[0].name,
                    'suggestion': '建議進行平行溝通以對齊進度',
                })
        return gaps

    # ──────────────────────────────────────────
    # 通知系統
    # ──────────────────────────────────────────
    def _add_notification(self, member_id: str, ntype: str, message: str, priority: str = 'normal'):
        self.notifications.append({
            'member_id': member_id,
            'type': ntype,
            'message': message,
            'priority': priority,
            'timestamp': self.now().isoformat(),
            'read': False,
        })
        # 保留最近 200 則
        if len(self.notifications) > 200:
            self.notifications = self.notifications[-200:]

    def check_abnormal_members(self) -> List[Dict]:
        """掃描異常成員（逾時未打卡），回傳需通知上級的清單"""
        abnormal = []
        for mid, m in self.members.items():
            status = self.get_status(mid)
            if status == AttendanceStatus.ABNORMAL:
                supervisor = self.get_supervisor(mid)
                if supervisor:
                    abnormal.append({
                        'member_id': mid,
                        'member_name': m.name,
                        'role': m.role,
                        'supervisor_id': supervisor.id,
                        'supervisor_name': supervisor.name,
                        'message': f'{m.name}（{m.role}）尚未打卡，請確認狀況',
                    })
                    # 避免重複通知
                    today_key = f'abnormal_{self.now().date().isoformat()}'
                    already_notified = any(
                        n['member_id'] == supervisor.id and n['type'] == today_key
                        for n in self.notifications
                    )
                    if not already_notified:
                        self._add_notification(supervisor.id, today_key,
                                              f'下屬 {m.name} 異常未打卡', priority='high')
        return abnormal

    # ──────────────────────────────────────────
    # 工具方法
    # ──────────────────────────────────────────
    def get_all_status(self) -> List[Dict]:
        """取得所有成員目前狀態（用於 UI）"""
        return [
            self.members[mid].to_dict(include_status=self.get_status(mid))
            for mid in self.members
        ]

    def stats(self) -> Dict:
        """統計資料"""
        all_status = [self.get_status(mid) for mid in self.members]
        return {
            'total': len(self.members),
            'online': sum(1 for s in all_status if s == AttendanceStatus.ONLINE),
            'resting': sum(1 for s in all_status if s == AttendanceStatus.RESTING),
            'offline': sum(1 for s in all_status if s == AttendanceStatus.OFFLINE),
            'abnormal': sum(1 for s in all_status if s == AttendanceStatus.ABNORMAL),
            'reports_submitted': sum(1 for m in self.members.values() if m.weekly_report),
            'objectives_received': sum(1 for m in self.members.values() if m.weekly_objective),
        }


# ══════════════════════════════════════════════════════════
# 測試
# ══════════════════════════════════════════════════════════
if __name__ == '__main__':
    from datetime import datetime
    # 建立測試成員
    members = [
        Member('m1', '王經理', '經理', '產品研發處', None, '👨‍💼'),
        Member('m2', '李副理', '副理', '前端組', 'm1', '👩‍💼'),
        Member('m3', '張課長', '課長', '前端 A 課', 'm2', '👨‍💼'),
        Member('m4', '陳副課長', '副課長', '前端 A 課', 'm3', '👨‍💻'),
        Member('m5', '林工程師', '工程師', '前端 A 課', 'm4', '👨‍💻'),
    ]
    mgr = AttendanceManager(members)

    # 測試不同時段
    for test_time in ['08:30', '09:30', '10:05', '11:00', '12:30', '14:00', '15:05', '17:30']:
        h, m = map(int, test_time.split(':'))
        mgr.set_demo_time(datetime.now().replace(hour=h, minute=m, second=0))
        # 模擬 08:30 打卡
        if test_time == '08:30':
            for mbr in members:
                mgr.clock_in(mbr.id)
        stats = mgr.stats()
        print(f'[{test_time}] 在線:{stats["online"]} 休息:{stats["resting"]} 離線:{stats["offline"]} 異常:{stats["abnormal"]}')
