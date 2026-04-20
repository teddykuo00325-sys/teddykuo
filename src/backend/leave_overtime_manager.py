#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
凌策智慧組織管理系統 — 請假 & 加班管理模組

功能：
1. 請假申請（事假/病假/特休/...）+ 主管核准
2. 加班紀錄 + 加班費計算（參考研能規則）
3. 加班計算機（上下班時間、休息時段）

加班規則（依研能公司）：
  - 平日加班需 ≥ 2 小時才計費
  - 平日前 2 小時：時薪 × 1.34
  - 平日 2~4 小時：前 2 小時 1.34、後續 1.67
  - 平日 4~6 小時：前 2 + 2~4 不變、超過 4 部分 ×2.0（上限 6 小時）
  - 假日加班：全程 時薪 × 2.0
  - 時薪 = 月薪 / 30 / 8
"""

import os
import json
import uuid
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional


# ═══════════════════════════════════════════════════════
# 加班規則引擎（純邏輯，無狀態）
# ═══════════════════════════════════════════════════════
LEAVE_TYPES = ['事假', '病假', '特休', '婚假', '喪假', '產假', '陪產假', '公假', '生理假', '其他']


def _parse_hhmm(hhmm: str) -> Optional[datetime]:
    try:
        return datetime.strptime(hhmm.zfill(4), '%H%M')
    except Exception:
        return None


def calculate_weekday_off_times(start_hhmm: str) -> Dict:
    """平日上班時間 → 計算 0/2/3/4 小時加班下班時間"""
    warnings = []
    advice = None
    start = _parse_hhmm(start_hhmm)
    if not start:
        return {'error': '時間格式錯誤（請用 HHMM，例如 0830）'}

    earliest = _parse_hhmm('0800')
    latest = _parse_hhmm('0900')

    if start < earliest:
        warnings.append(f'上班時間 {start.strftime("%H:%M")} 早於 08:00，已調整為 08:00 起算')
        start = earliest
    elif start > latest:
        late_min = int((start - latest).total_seconds() / 60)
        warnings.append(f'遲到 {late_min} 分鐘（超過 09:00）')
        if late_min <= 60:
            advice = '建議請事假 2 小時'
        elif late_min <= 120:
            advice = '建議請事假 3 小時'
        elif late_min <= 180:
            advice = '建議請事假 4 小時'
        else:
            advice = '建議請事假 > 4 小時'
        start = earliest

    work_duration = timedelta(hours=8)
    total_break = timedelta(minutes=80)
    night_rest = timedelta(minutes=30)

    off_times = {'不加班': (start + work_duration + total_break).strftime('%H:%M')}
    for hours in range(2, 5):
        t = start + work_duration + total_break + timedelta(hours=hours) + night_rest
        off_times[f'加班 {hours} 小時'] = t.strftime('%H:%M')

    return {
        'day_type': 'weekday',
        'start_time': start.strftime('%H:%M'),
        'off_times': off_times,
        'warnings': warnings,
        'late_advice': advice,
    }


def calculate_holiday_off_times(start_hhmm: str) -> Dict:
    """假日上班時間 → 計算 2~9 小時加班下班時間"""
    warnings = []
    start = _parse_hhmm(start_hhmm)
    if not start:
        return {'error': '時間格式錯誤（請用 HHMM，例如 0700）'}

    earliest = _parse_hhmm('0700')
    lunch_start = _parse_hhmm('1210')
    lunch_end = _parse_hhmm('1310')
    morning_break_end = _parse_hhmm('1010')
    afternoon_break = _parse_hhmm('1510')
    evening_break = _parse_hhmm('1720')

    if start < earliest:
        warnings.append(f'上班時間 {start.strftime("%H:%M")} 早於 07:00，已調整為 07:00')
        start = earliest
    if lunch_start <= start <= lunch_end:
        warnings.append('上班時間在 12:10~13:10 之間，已調整為 13:10')
        start = lunch_end

    off_times = {}
    for hours in range(2, 10):
        end = start + timedelta(hours=hours)
        # 上午休息 10 分鐘（若上班在 10:10 前 & 午休前）
        if start < morning_break_end and start < lunch_end:
            end += timedelta(minutes=10)
        # 午休 60 分鐘
        if start <= lunch_start < end:
            end += timedelta(minutes=60)
        # 下午休息 10 分鐘
        if start < afternoon_break <= end:
            end += timedelta(minutes=10)
        # 夜間休息 30 分鐘
        if end > evening_break:
            end += timedelta(minutes=30)
        off_times[f'加班 {hours} 小時'] = end.strftime('%H:%M')

    return {
        'day_type': 'holiday',
        'start_time': start.strftime('%H:%M'),
        'off_times': off_times,
        'warnings': warnings,
    }


def calculate_overtime_pay(monthly_salary: float, overtime_hours: float, is_holiday: bool) -> Dict:
    """
    依研能規則計算加班費
    - 時薪 = 月薪 / 30 / 8
    - 平日：1.34x (前2hr) / 1.67x (2~4hr) / 2x (4~6hr, 上限 6hr)
    - 假日：全程 2x
    """
    if monthly_salary <= 0:
        return {'error': '月薪需 > 0'}
    if overtime_hours < 2:
        return {
            'pay': 0, 'hourly_wage': monthly_salary / 30 / 8,
            'capped_hours': overtime_hours,
            'note': '加班時數須 ≥ 2 小時方計費'
        }

    hourly = monthly_salary / 30 / 8
    pay = 0
    breakdown = []

    if is_holiday:
        pay = hourly * 2 * overtime_hours
        breakdown.append({'hours': overtime_hours, 'rate': 2.0, 'subtotal': pay, 'label': '假日加班'})
        capped = overtime_hours
    else:
        capped = min(overtime_hours, 6)
        if capped <= 2:
            p = hourly * 1.34 * capped
            pay += p
            breakdown.append({'hours': capped, 'rate': 1.34, 'subtotal': round(p, 2), 'label': '前 2 小時'})
        elif capped <= 4:
            p1 = hourly * 1.34 * 2
            p2 = hourly * 1.67 * (capped - 2)
            pay = p1 + p2
            breakdown.append({'hours': 2, 'rate': 1.34, 'subtotal': round(p1, 2), 'label': '前 2 小時'})
            breakdown.append({'hours': capped - 2, 'rate': 1.67, 'subtotal': round(p2, 2), 'label': '第 3~4 小時'})
        else:
            p1 = hourly * 1.34 * 2
            p2 = hourly * 1.67 * 2
            p3 = hourly * 2 * (capped - 4)
            pay = p1 + p2 + p3
            breakdown.append({'hours': 2, 'rate': 1.34, 'subtotal': round(p1, 2), 'label': '前 2 小時'})
            breakdown.append({'hours': 2, 'rate': 1.67, 'subtotal': round(p2, 2), 'label': '第 3~4 小時'})
            breakdown.append({'hours': capped - 4, 'rate': 2.0, 'subtotal': round(p3, 2), 'label': '第 5~6 小時'})

    note = None
    if not is_holiday and overtime_hours > 6:
        note = f'加班時數 {overtime_hours} 小時超過上限，僅計費 6 小時'

    return {
        'monthly_salary': monthly_salary,
        'hourly_wage': round(hourly, 2),
        'overtime_hours': overtime_hours,
        'capped_hours': round(capped, 2),
        'is_holiday': is_holiday,
        'pay': round(pay, 2),
        'breakdown': breakdown,
        'note': note,
    }


# ═══════════════════════════════════════════════════════
# LeaveRequest / OvertimeRecord
# ═══════════════════════════════════════════════════════
class LeaveRequest:
    def __init__(self, lid, member_id, leave_type, start_at, end_at, hours, reason,
                 approver_id=None, created_at=None, approval_chain=None, proxy_id=None):
        self.id = lid
        self.member_id = member_id
        self.leave_type = leave_type
        self.start_at = start_at
        self.end_at = end_at
        self.hours = hours
        self.reason = reason
        self.status = 'pending'   # pending/in_approval/approved/rejected/cancelled
        self.approver_id = approver_id   # 向後相容：代表目前待審者
        self.created_at = created_at or datetime.now()
        self.approved_at = None
        self.rejected_at = None
        self.reject_reason = None
        # 多級審批鏈：[{approver_id, approver_name, approver_title, status, approved_at, reject_reason}]
        self.approval_chain = approval_chain or []
        self.current_step = 0     # 目前等待的層級 index
        self.proxy_id = proxy_id  # 職務代理人

    def to_dict(self):
        return {
            'id': self.id, 'member_id': self.member_id,
            'leave_type': self.leave_type,
            'start_at': self.start_at.isoformat() if isinstance(self.start_at, datetime) else self.start_at,
            'end_at': self.end_at.isoformat() if isinstance(self.end_at, datetime) else self.end_at,
            'hours': self.hours, 'reason': self.reason,
            'status': self.status, 'approver_id': self.approver_id,
            'created_at': self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
            'approved_at': self.approved_at.isoformat() if self.approved_at else None,
            'rejected_at': self.rejected_at.isoformat() if self.rejected_at else None,
            'reject_reason': self.reject_reason,
            'approval_chain': self.approval_chain,
            'current_step': self.current_step,
            'proxy_id': self.proxy_id,
        }

    @classmethod
    def from_dict(cls, d):
        obj = cls(d['id'], d['member_id'], d['leave_type'],
                  datetime.fromisoformat(d['start_at']), datetime.fromisoformat(d['end_at']),
                  d['hours'], d['reason'], d.get('approver_id'),
                  datetime.fromisoformat(d['created_at']),
                  approval_chain=d.get('approval_chain') or [],
                  proxy_id=d.get('proxy_id'))
        obj.status = d.get('status', 'pending')
        obj.approved_at = datetime.fromisoformat(d['approved_at']) if d.get('approved_at') else None
        obj.rejected_at = datetime.fromisoformat(d['rejected_at']) if d.get('rejected_at') else None
        obj.reject_reason = d.get('reject_reason')
        obj.current_step = d.get('current_step', 0)
        return obj


class OvertimeRecord:
    def __init__(self, oid, member_id, work_date, day_type, start_hhmm, overtime_hours,
                 reason='', approver_id=None, created_at=None):
        self.id = oid
        self.member_id = member_id
        self.work_date = work_date  # YYYY-MM-DD
        self.day_type = day_type  # weekday/holiday
        self.start_hhmm = start_hhmm
        self.overtime_hours = overtime_hours  # float
        self.reason = reason
        self.approver_id = approver_id
        self.status = 'pending'
        self.created_at = created_at or datetime.now()
        self.approved_at = None
        self.rejected_at = None
        self.reject_reason = None
        self.estimated_pay = None

    def to_dict(self):
        return {
            'id': self.id, 'member_id': self.member_id,
            'work_date': self.work_date,
            'day_type': self.day_type,
            'start_hhmm': self.start_hhmm,
            'overtime_hours': self.overtime_hours,
            'reason': self.reason,
            'approver_id': self.approver_id,
            'status': self.status,
            'created_at': self.created_at.isoformat() if isinstance(self.created_at, datetime) else self.created_at,
            'approved_at': self.approved_at.isoformat() if self.approved_at else None,
            'rejected_at': self.rejected_at.isoformat() if self.rejected_at else None,
            'reject_reason': self.reject_reason,
            'estimated_pay': self.estimated_pay,
        }

    @classmethod
    def from_dict(cls, d):
        obj = cls(d['id'], d['member_id'], d['work_date'], d['day_type'],
                  d['start_hhmm'], d['overtime_hours'], d.get('reason',''),
                  d.get('approver_id'), datetime.fromisoformat(d['created_at']))
        obj.status = d.get('status', 'pending')
        obj.approved_at = datetime.fromisoformat(d['approved_at']) if d.get('approved_at') else None
        obj.rejected_at = datetime.fromisoformat(d['rejected_at']) if d.get('rejected_at') else None
        obj.reject_reason = d.get('reject_reason')
        obj.estimated_pay = d.get('estimated_pay')
        return obj


# ═══════════════════════════════════════════════════════
# Manager
# ═══════════════════════════════════════════════════════
class LeaveOvertimeManager:
    def __init__(self, attendance_mgr, data_dir: str):
        self.attn = attendance_mgr
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.leave_file = os.path.join(data_dir, 'leaves.json')
        self.overtime_file = os.path.join(data_dir, 'overtimes.json')
        self.leaves: Dict[str, LeaveRequest] = {}
        self.overtimes: Dict[str, OvertimeRecord] = {}
        self._lock = threading.Lock()
        self._load()

    def _load(self):
        try:
            if os.path.exists(self.leave_file):
                with open(self.leave_file, 'r', encoding='utf-8') as f:
                    for d in json.load(f).values():
                        l = LeaveRequest.from_dict(d)
                        self.leaves[l.id] = l
            if os.path.exists(self.overtime_file):
                with open(self.overtime_file, 'r', encoding='utf-8') as f:
                    for d in json.load(f).values():
                        o = OvertimeRecord.from_dict(d)
                        self.overtimes[o.id] = o
            print(f'[LeaveOT] 載入 {len(self.leaves)} 請假 / {len(self.overtimes)} 加班')
        except Exception as e:
            print(f'[LeaveOT] 載入失敗: {e}')

    def _save_leaves(self):
        with self._lock:
            with open(self.leave_file, 'w', encoding='utf-8') as f:
                json.dump({k: v.to_dict() for k, v in self.leaves.items()}, f, ensure_ascii=False, indent=2)

    def _save_overtimes(self):
        with self._lock:
            with open(self.overtime_file, 'w', encoding='utf-8') as f:
                json.dump({k: v.to_dict() for k, v in self.overtimes.items()}, f, ensure_ascii=False, indent=2)

    def _new_id(self, prefix):
        return f'{prefix}-{uuid.uuid4().hex[:8].upper()}'

    # ── 審批鏈建構 ──
    # 自然鏈停止點（含該層）：部門最高主管（經理 / 協理）
    DEPT_HEAD_KW = ('經理', '協理')
    # 最終審批者（一定要是最後一關）
    FINAL_APPROVER_KW = ('總經理',)

    # 指定 HR：地理貼近現場的 HR，負責對基層員工的事實確認
    DESIGNATED_HR_PRIMARY   = 'MFG-003'  # 童煜中（製造處 · 頂埔廠 · 行政專員）
    DESIGNATED_HR_SECONDARY = 'RD2-004'  # 高迪瑭（研發二部 · 文管專員）

    # 指定 HR 路由表：部門關鍵字 → 指定 HR ID
    DESIGNATED_HR_ROUTE = [
        ('製造處',         DESIGNATED_HR_PRIMARY),   # 童
        ('頂埔廠',         DESIGNATED_HR_PRIMARY),   # 童
        ('addwii',         DESIGNATED_HR_PRIMARY),   # 童（使用者指定 addwii 也過童）
        ('研發二部',       DESIGNATED_HR_SECONDARY), # 高
        ('RD2',           DESIGNATED_HR_SECONDARY), # 高
        # 其他 microjet 部門預設 → 高迪瑭（總部/研發區）
    ]
    DESIGNATED_HR_DEFAULT = DESIGNATED_HR_SECONDARY  # 高

    # 人事 HR 預設審批者（日常承擔審批的 HR 部門成員）
    PERSONAL_HR_DEFAULT  = 'HRA-002'  # 陳玉梅（人事課長）承擔日常
    PERSONAL_HR_FALLBACK = 'HRA-001'  # 陳瑞照（人事經理）高階/迴避用

    def _find_final_approver(self, initiator_dept: str):
        """找總經理 ID；若該集團有多個總經理，優先同部門集團（addwii / MICROJET）的"""
        # 先找同集團下的總經理
        initiator_top = (initiator_dept or '').split('·')[0].strip().split('/')[0].strip()
        candidates = []
        for mid, m in self.attn.members.items():
            if '總經理' in (m.title or ''):
                candidates.append(m)
        if not candidates:
            return None
        # 優先同集團
        for c in candidates:
            c_top = (c.dept or '').split('·')[0].strip().split('/')[0].strip()
            if c_top and initiator_top and c_top == initiator_top:
                return c
        return candidates[0]

    def _mk_step(self, member, role_tag=None, is_final=False):
        """建一個審批步驟 dict（供 chain 使用）"""
        step = {
            'approver_id': member.id,
            'approver_name': member.name,
            'approver_title': member.title or '',
            'approver_dept': member.dept or '',
            'status': 'pending',
            'approved_at': None,
            'reject_reason': None,
        }
        if role_tag: step['role_tag'] = role_tag  # 前端顯示用（如「指定 HR」「人事 HR」）
        if is_final: step['is_final'] = True
        return step

    def _route_designated_hr(self, initiator_id: str, initiator_dept: str):
        """依部門路由指定 HR；若申請人就是該指定 HR 則改派另一位"""
        target_id = None
        for kw, hr_id in self.DESIGNATED_HR_ROUTE:
            if kw in (initiator_dept or ''):
                target_id = hr_id
                break
        if target_id is None:
            target_id = self.DESIGNATED_HR_DEFAULT
        # 迴避：申請人就是此指定 HR → 改派另一位
        if target_id == initiator_id:
            target_id = (self.DESIGNATED_HR_SECONDARY
                         if target_id == self.DESIGNATED_HR_PRIMARY
                         else self.DESIGNATED_HR_PRIMARY)
        return self.attn.members.get(target_id)

    def _route_personal_hr(self, initiator_id: str):
        """人事 HR 預設派 HRA-002；若申請人自己是 HRA-002 則改派 HRA-001"""
        target_id = self.PERSONAL_HR_DEFAULT
        if target_id == initiator_id:
            target_id = self.PERSONAL_HR_FALLBACK
        # 若申請人是 HRA-001 本人 → 改派 HRA-002（反過來）
        if target_id == initiator_id:
            target_id = self.PERSONAL_HR_DEFAULT
        return self.attn.members.get(target_id)

    def build_approval_chain(self, member_id):
        """
        凌策客戶組織 (microjet + addwii) 請假審批規則：

        基層員工 (工程師/副課長/專員/副理/課長)：
          ① 直屬主管
          ② 部門經理（若直屬已是經理則跳過重複）
          ③ 指定 HR（童煜中 或 高迪瑭，依部門路由、現場事實確認）
          ④ 人事 HR（HRA-002 陳玉梅 預設，勞基法合規審查）
          ⑤ 總經理（最終授權）

        高階主管 (經理/協理)：
          ① 直屬主管 (若有)
          ② 總經理   （跳過指定 HR/人事 HR 層，因層級高於）

        最高層 (總經理 / 董事長)：
          無需審批

        迴避邏輯：
          - 申請人本身即指定 HR / 人事 HR → 自動改派另一位
        """
        chain = []
        m = self.attn.members.get(member_id)
        if not m: return chain
        title = m.title or ''

        # 自己是總經理或董事長 → 無需審批
        if '總經理' in title or '董事長' in title:
            return chain

        # 判斷是否為「高階主管」(經理/協理) — 跳過指定 HR / 人事 HR 兩層
        is_senior = any(kw in title for kw in self.DEPT_HEAD_KW)

        # ── 第一段：自然追溯 直屬主管 → 部門最高主管 (經理/協理) ──
        # 規則：
        #   - 遇到總經理 → 加入鏈，自然鏈收工
        #   - 遇到董事長 → 跳過（董事長為集團層級，不介入營運請假）
        #   - 遇到經理/協理 → 加入鏈，停止自然追溯
        visited = set([member_id])
        cur_id = m.supervisor_id
        while cur_id and cur_id not in visited:
            visited.add(cur_id)
            sup = self.attn.members.get(cur_id)
            if not sup: break
            sup_title = sup.title or ''
            if '董事長' in sup_title:
                # 董事長不參與請假審批，改以向上鏈（此時鏈結束，後續由總經理收尾）
                break
            chain.append(self._mk_step(sup, role_tag=self._guess_role_tag(sup)))
            if any(kw in sup_title for kw in self.FINAL_APPROVER_KW):
                break  # 已到總經理
            if any(kw in sup_title for kw in self.DEPT_HEAD_KW):
                break
            cur_id = sup.supervisor_id

        # ── 第二段：指定 HR → 人事 HR (僅基層套用) ──
        if not is_senior:
            des_hr = self._route_designated_hr(member_id, m.dept or '')
            if des_hr and not any(c['approver_id'] == des_hr.id for c in chain):
                chain.append(self._mk_step(des_hr, role_tag='指定 HR（現場確認）'))
            per_hr = self._route_personal_hr(member_id)
            if per_hr and not any(c['approver_id'] == per_hr.id for c in chain):
                chain.append(self._mk_step(per_hr, role_tag='人事 HR（合規審查）'))

        # ── 第三段：總經理（最終授權，統一收尾）──
        gm = self._find_final_approver(m.dept or '')
        if gm and not any(c['approver_id'] == gm.id for c in chain):
            chain.append(self._mk_step(gm, role_tag='總經理（最終授權）', is_final=True))

        # 若已在鏈中的最後一步即總經理 → 補標註 is_final
        if chain and not chain[-1].get('is_final') and '總經理' in (chain[-1].get('approver_title') or ''):
            chain[-1]['is_final'] = True
            chain[-1]['role_tag'] = '總經理（最終授權）'

        return chain

    def _guess_role_tag(self, member):
        """依成員 title 推測他在審批鏈中的角色標籤（前端顯示用）"""
        t = member.title or ''
        if '董事長' in t: return '董事長'
        if '總經理' in t: return '總經理（最終授權）'
        if '協理' in t: return '部門協理'
        if '經理' in t: return '部門經理'
        if '副理' in t: return '副理'
        if '課長' in t: return '課長'
        if '副課長' in t: return '副課長'
        return '直屬主管'

    # ── 請假（多級審批 + 代理人）──
    def apply_leave(self, member_id, leave_type, start_at, end_at, hours, reason='', proxy_id=None):
        m = self.attn.members.get(member_id)
        if not m:
            return {'success': False, 'error': '成員不存在'}
        if leave_type not in LEAVE_TYPES:
            return {'success': False, 'error': f'無效假別（支援：{",".join(LEAVE_TYPES)}）'}
        try:
            sd = datetime.fromisoformat(start_at) if isinstance(start_at, str) else start_at
            ed = datetime.fromisoformat(end_at) if isinstance(end_at, str) else end_at
        except Exception:
            return {'success': False, 'error': '日期格式錯誤'}
        if ed <= sd:
            return {'success': False, 'error': '結束時間必須晚於開始時間'}

        if proxy_id:
            if proxy_id == member_id:
                return {'success': False, 'error': '代理人不能是本人'}
            if not self.attn.members.get(proxy_id):
                return {'success': False, 'error': '代理人不存在'}

        chain = self.build_approval_chain(member_id)
        first_approver = chain[0]['approver_id'] if chain else None

        req = LeaveRequest(self._new_id('LV'), member_id, leave_type, sd, ed, hours, reason,
                           approver_id=first_approver, approval_chain=chain, proxy_id=proxy_id)
        # 無審批鏈（例如已是董事長）
        if not chain:
            req.status = 'approved'
            req.approved_at = datetime.now()
        else:
            req.status = 'in_approval'
        self.leaves[req.id] = req
        self._save_leaves()

        if first_approver:
            self.attn._add_notification(
                first_approver, 'leave_pending',
                f'⏳ {m.name} 申請 {leave_type} {hours} 小時，請審核 (審批鏈 1/{len(chain)})',
                priority='high'
            )
        return {'success': True, 'leave': req.to_dict()}

    def approve_leave(self, approver_id, leave_id):
        r = self.leaves.get(leave_id)
        if not r: return {'success': False, 'error': '請假單不存在'}
        if r.status not in ('pending', 'in_approval'):
            return {'success': False, 'error': f'狀態為 {r.status}'}
        actor = self.attn.members.get(approver_id)
        is_hr = bool(actor and actor.is_hr)
        # 必須是目前階段的核准人，或 HR 可越權
        expected = r.approver_id
        if approver_id != expected and not is_hr:
            return {'success': False, 'error': '您不是此階段的核准人'}
        # 標記該層為已核准
        if r.approval_chain and r.current_step < len(r.approval_chain):
            step = r.approval_chain[r.current_step]
            step['status'] = 'approved'
            step['approved_at'] = datetime.now().isoformat(timespec='seconds')
            step['actor_id'] = approver_id  # 紀錄實際操作者（HR 越權時會不同）
        # 推進到下一層
        r.current_step += 1
        if r.current_step >= len(r.approval_chain):
            # 全部通過
            r.status = 'approved'
            r.approver_id = None
            r.approved_at = datetime.now()
            self.attn._add_notification(r.member_id, 'leave_approved',
                f'✅ 您的 {r.leave_type} 請假已全部核准 (共 {len(r.approval_chain)} 層)', priority='normal')
        else:
            next_step = r.approval_chain[r.current_step]
            r.approver_id = next_step['approver_id']
            r.status = 'in_approval'
            self.attn._add_notification(r.approver_id, 'leave_pending',
                f'⏳ {self.attn.members[r.member_id].name} 的請假已通過前階，請接續審核 ({r.current_step+1}/{len(r.approval_chain)})',
                priority='high')
        self._save_leaves()
        return {'success': True, 'leave': r.to_dict()}

    def reject_leave(self, approver_id, leave_id, reason=''):
        r = self.leaves.get(leave_id)
        if not r: return {'success': False, 'error': '請假單不存在'}
        if r.status not in ('pending', 'in_approval'):
            return {'success': False, 'error': f'狀態為 {r.status}'}
        actor = self.attn.members.get(approver_id)
        is_hr = bool(actor and actor.is_hr)
        if approver_id != r.approver_id and not is_hr:
            return {'success': False, 'error': '您不是此階段的核准人'}
        if r.approval_chain and r.current_step < len(r.approval_chain):
            step = r.approval_chain[r.current_step]
            step['status'] = 'rejected'
            step['reject_reason'] = reason
            step['approved_at'] = datetime.now().isoformat(timespec='seconds')
            step['actor_id'] = approver_id
        r.status = 'rejected'
        r.rejected_at = datetime.now()
        r.reject_reason = reason
        self._save_leaves()
        self.attn._add_notification(r.member_id, 'leave_rejected',
            f'❌ 您的 {r.leave_type} 請假於第 {r.current_step+1} 關被拒絕：{reason}', priority='high')
        return {'success': True, 'leave': r.to_dict()}

    def get_member_leaves(self, member_id):
        return sorted([l.to_dict() for l in self.leaves.values() if l.member_id == member_id],
                      key=lambda x: x['created_at'], reverse=True)

    def get_pending_leaves_for(self, approver_id):
        """我目前需要審的（即審批鏈指向我的那一層）"""
        result = []
        for l in self.leaves.values():
            if l.status in ('pending', 'in_approval') and l.approver_id == approver_id:
                d = l.to_dict()
                m = self.attn.members.get(l.member_id)
                d['member_name'] = m.name if m else l.member_id
                d['member_title'] = m.title if m else ''
                d['member_dept']  = m.dept if m else ''
                if l.proxy_id:
                    pm = self.attn.members.get(l.proxy_id)
                    d['proxy_name'] = pm.name if pm else l.proxy_id
                result.append(d)
        return sorted(result, key=lambda x: x['created_at'])

    # ── 職務代理人 ──
    def get_active_proxies(self, now=None):
        """回傳目前生效中的代理關係 {proxy_id: [被代理人 leave dict,...]}"""
        now = now or datetime.now()
        active = {}
        for l in self.leaves.values():
            if l.status != 'approved' or not l.proxy_id: continue
            if l.start_at <= now <= l.end_at:
                active.setdefault(l.proxy_id, []).append(l.to_dict())
        return active

    def get_active_proxy_for(self, member_id, now=None):
        """查該員現在是否被代理中 → 回傳代理人 id 或 None"""
        now = now or datetime.now()
        for l in self.leaves.values():
            if l.member_id == member_id and l.status == 'approved' and l.proxy_id and l.start_at <= now <= l.end_at:
                return l.proxy_id
        return None

    def who_am_i_proxying(self, proxy_id, now=None):
        """查我現在代理誰"""
        now = now or datetime.now()
        out = []
        for l in self.leaves.values():
            if l.proxy_id == proxy_id and l.status == 'approved' and l.start_at <= now <= l.end_at:
                m = self.attn.members.get(l.member_id)
                out.append({
                    'leave_id': l.id,
                    'member_id': l.member_id,
                    'member_name': m.name if m else l.member_id,
                    'member_title': m.title if m else '',
                    'start_at': l.start_at.isoformat(),
                    'end_at': l.end_at.isoformat(),
                    'leave_type': l.leave_type,
                })
        return out

    # ── HR 出缺勤紀錄表（含加班）──
    def generate_attendance_report(self, start_date: str, end_date: str, dept: Optional[str] = None,
                                   member_ids: Optional[list] = None):
        """
        產出期間內 [start_date, end_date] 每位員工的出缺勤彙總
        - 請假時數（依假別小計）
        - 加班時數（平日/假日）+ 估算加班費
        - 結果為可匯出 CSV 的純資料
        """
        try:
            sd = datetime.fromisoformat(start_date + 'T00:00:00') if len(start_date)==10 else datetime.fromisoformat(start_date)
            ed = datetime.fromisoformat(end_date + 'T23:59:59') if len(end_date)==10 else datetime.fromisoformat(end_date)
        except Exception:
            return {'error': '日期格式需為 YYYY-MM-DD'}

        # 目標員工清單
        if member_ids:
            targets = [self.attn.members[mid] for mid in member_ids if mid in self.attn.members]
        elif dept:
            targets = [m for m in self.attn.members.values() if (m.dept or '') == dept or (m.dept or '').startswith(dept)]
        else:
            targets = list(self.attn.members.values())

        rows = []
        total_leave_h = 0.0
        total_ot_h = 0.0
        total_ot_pay = 0.0
        for m in targets:
            leave_by_type = {}
            leave_total = 0.0
            for l in self.leaves.values():
                if l.member_id != m.id or l.status != 'approved': continue
                # 重疊判斷（最寬鬆：任一時段落在區間內）
                if l.end_at < sd or l.start_at > ed: continue
                leave_by_type[l.leave_type] = leave_by_type.get(l.leave_type, 0) + l.hours
                leave_total += l.hours
            ot_weekday_h = 0.0; ot_holiday_h = 0.0; ot_pay = 0.0
            for o in self.overtimes.values():
                if o.member_id != m.id or o.status != 'approved': continue
                try:
                    od = datetime.fromisoformat(o.work_date + 'T00:00:00') if len(o.work_date)==10 else datetime.fromisoformat(o.work_date)
                except Exception:
                    continue
                if od < sd or od > ed: continue
                if o.day_type == 'holiday': ot_holiday_h += o.overtime_hours
                else: ot_weekday_h += o.overtime_hours
                if o.estimated_pay: ot_pay += o.estimated_pay
            rows.append({
                'member_id': m.id,
                'member_name': m.name,
                'dept': m.dept or '',
                'title': m.title or '',
                'leave_by_type': leave_by_type,
                'leave_total_hours': round(leave_total, 1),
                'overtime_weekday_hours': round(ot_weekday_h, 1),
                'overtime_holiday_hours': round(ot_holiday_h, 1),
                'overtime_total_hours': round(ot_weekday_h + ot_holiday_h, 1),
                'overtime_estimated_pay': round(ot_pay, 2),
            })
            total_leave_h += leave_total
            total_ot_h += (ot_weekday_h + ot_holiday_h)
            total_ot_pay += ot_pay

        # 依部門 → 姓名排序
        rows.sort(key=lambda r: (r['dept'], r['member_name']))
        return {
            'period': {'start': start_date, 'end': end_date},
            'filter': {'dept': dept, 'member_ids': member_ids},
            'summary': {
                'employees': len(rows),
                'total_leave_hours': round(total_leave_h, 1),
                'total_overtime_hours': round(total_ot_h, 1),
                'total_overtime_pay_est': round(total_ot_pay, 2),
            },
            'rows': rows,
            'generated_at': datetime.now().isoformat(timespec='seconds'),
        }

    def export_attendance_csv(self, report: dict, include_pay: bool = False) -> str:
        """把 report 轉成 CSV 字串（供下載）
        include_pay: 是否包含加班費金額欄位（預設 False，僅 HR/財務主管可開啟）"""
        import io as _io, csv as _csv
        buf = _io.StringIO()
        w = _csv.writer(buf)
        base_header = ['員編','姓名','部門','職稱','請假總時數','假別細目',
                       '平日加班時數','假日加班時數','加班總時數']
        if include_pay:
            base_header.append('估算加班費')
        w.writerow(base_header)
        for r in report.get('rows', []):
            detail = '; '.join(f'{k}:{v}h' for k,v in r['leave_by_type'].items())
            row = [r['member_id'], r['member_name'], r['dept'], r['title'],
                   r['leave_total_hours'], detail,
                   r['overtime_weekday_hours'], r['overtime_holiday_hours'],
                   r['overtime_total_hours']]
            if include_pay:
                row.append(r['overtime_estimated_pay'])
            w.writerow(row)
        return buf.getvalue()

    # ── 加班 ──
    def submit_overtime(self, member_id, work_date, day_type, start_hhmm, overtime_hours,
                        reason='', monthly_salary=None):
        m = self.attn.members.get(member_id)
        if not m:
            return {'success': False, 'error': '成員不存在'}
        rec = OvertimeRecord(self._new_id('OT'), member_id, work_date, day_type,
                              start_hhmm, overtime_hours, reason, m.supervisor_id)
        # 估算加班費（可選，若提供 monthly_salary）
        if monthly_salary and monthly_salary > 0:
            r = calculate_overtime_pay(monthly_salary, overtime_hours, day_type == 'holiday')
            rec.estimated_pay = r.get('pay')
        if not rec.approver_id:
            rec.status = 'approved'
            rec.approved_at = datetime.now()
        self.overtimes[rec.id] = rec
        self._save_overtimes()
        if rec.approver_id and rec.status == 'pending':
            self.attn._add_notification(rec.approver_id, 'overtime_pending',
                f'⏳ {m.name} 申報 {day_type} {overtime_hours} 小時加班，請審核。',
                priority='normal')
        return {'success': True, 'overtime': rec.to_dict()}

    def approve_overtime(self, approver_id, ot_id):
        r = self.overtimes.get(ot_id)
        if not r: return {'success': False, 'error': '加班單不存在'}
        if r.status != 'pending': return {'success': False, 'error': f'狀態為 {r.status}'}
        actor = self.attn.members.get(approver_id)
        if approver_id != r.approver_id and not (actor and actor.is_hr):
            return {'success': False, 'error': '您不是此加班單的核准人'}
        r.status = 'approved'
        r.approved_at = datetime.now()
        self._save_overtimes()
        self.attn._add_notification(r.member_id, 'overtime_approved',
            f'✅ 您的加班申報已被核准', priority='normal')
        return {'success': True, 'overtime': r.to_dict()}

    def reject_overtime(self, approver_id, ot_id, reason=''):
        r = self.overtimes.get(ot_id)
        if not r: return {'success': False, 'error': '加班單不存在'}
        if r.status != 'pending': return {'success': False, 'error': f'狀態為 {r.status}'}
        actor = self.attn.members.get(approver_id)
        if approver_id != r.approver_id and not (actor and actor.is_hr):
            return {'success': False, 'error': '您不是此加班單的核准人'}
        r.status = 'rejected'
        r.rejected_at = datetime.now()
        r.reject_reason = reason
        self._save_overtimes()
        self.attn._add_notification(r.member_id, 'overtime_rejected',
            f'❌ 您的加班申報被拒絕：{reason}', priority='high')
        return {'success': True, 'overtime': r.to_dict()}

    def get_member_overtimes(self, member_id):
        return sorted([o.to_dict() for o in self.overtimes.values() if o.member_id == member_id],
                      key=lambda x: x['created_at'], reverse=True)

    def get_pending_overtimes_for(self, approver_id):
        result = []
        for o in self.overtimes.values():
            if o.status == 'pending' and o.approver_id == approver_id:
                d = o.to_dict()
                m = self.attn.members.get(o.member_id)
                d['member_name'] = m.name if m else o.member_id
                d['member_title'] = m.title if m else ''
                result.append(d)
        return sorted(result, key=lambda x: x['created_at'])


if __name__ == '__main__':
    # 測試加班計算
    print('=== 平日 0830 ===')
    print(calculate_weekday_off_times('0830'))
    print('\n=== 平日 0930 (遲到) ===')
    print(calculate_weekday_off_times('0930'))
    print('\n=== 假日 0800 ===')
    print(calculate_holiday_off_times('0800'))
    print('\n=== 加班費（月薪 60000，平日加班 3 小時）===')
    print(calculate_overtime_pay(60000, 3, False))
    print('\n=== 加班費（月薪 60000，假日加班 8 小時）===')
    print(calculate_overtime_pay(60000, 8, True))
