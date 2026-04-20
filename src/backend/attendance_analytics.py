# -*- coding: utf-8 -*-
"""
凌策客戶組織 — 出缺勤統計與歷史編輯模組
功能：
  1. 每日 / 每月 出缺勤統計（所有人可檢視）
  2. HR 編輯歷史出缺勤紀錄
  3. 編輯需部門最高主管審批後才生效（兩階段儲存）
  4. 完整稽核軌跡
"""
import os, json, hashlib, threading, uuid, random
from datetime import datetime, timedelta, date
from typing import Optional, Dict, List

# 狀態集合
STATUS_SET = {
    'online':   {'label':'正常出勤', 'icon':'🟢'},
    'late':     {'label':'遲到',     'icon':'🟡'},
    'early':    {'label':'早退',     'icon':'🟠'},
    'absent':   {'label':'缺勤',     'icon':'🔴'},
    'leave':    {'label':'請假',     'icon':'📝'},
    'overtime': {'label':'加班',     'icon':'⏰'},
    'wfh':      {'label':'遠端',     'icon':'🏠'},
    'trip':     {'label':'公出',     'icon':'✈️'},
}


class AttendanceAnalyticsManager:
    def __init__(self, attendance_mgr, leave_ot_mgr, data_dir: str):
        self.attn = attendance_mgr
        self.leave_ot = leave_ot_mgr
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.history_file = os.path.join(data_dir, 'attendance_history.json')   # 打卡歷史快照
        self.edits_file   = os.path.join(data_dir, 'attendance_edits.jsonl')    # 編輯請求佇列
        self.audit_file   = os.path.join(data_dir, 'attendance_edit_audit.jsonl')  # 編輯稽核軌跡
        self._lock = threading.Lock()
        self._history: Dict[str, Dict[str, dict]] = {}  # {date: {member_id: record}}
        self._edits: List[dict] = []
        self._load()
        # 若歷史為空就自動產 30 天示範資料
        if not self._history:
            self._bootstrap_demo_history()

    # ═════════════════════════════════════════
    # 持久化
    # ═════════════════════════════════════════
    def _load(self):
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self._history = json.load(f)
            if os.path.exists(self.edits_file):
                with open(self.edits_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try: self._edits.append(json.loads(line))
                            except: pass
            print(f'[Analytics] 載入 {len(self._history)} 天歷史 / {len(self._edits)} 筆編輯紀錄')
        except Exception as e:
            print(f'[Analytics] 載入失敗: {e}')

    def _save_history(self):
        with self._lock:
            tmp = self.history_file + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(self._history, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.history_file)

    def _append_edit(self, edit: dict):
        with self._lock:
            self._edits.append(edit)
            with open(self.edits_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(edit, ensure_ascii=False) + '\n')

    def _rewrite_edits(self):
        """覆寫整份 edits.jsonl（用於狀態變更後）"""
        with self._lock:
            tmp = self.edits_file + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                for e in self._edits:
                    f.write(json.dumps(e, ensure_ascii=False) + '\n')
            os.replace(tmp, self.edits_file)

    def _audit(self, action: str, actor: str, detail: dict):
        try:
            with open(self.audit_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps({
                    'ts': datetime.now().isoformat(timespec='seconds'),
                    'action': action, 'actor': actor, 'detail': detail,
                }, ensure_ascii=False) + '\n')
        except Exception:
            pass

    # ═════════════════════════════════════════
    # Demo 歷史 bootstrap（30 天內隨機填）
    # ═════════════════════════════════════════
    def _bootstrap_demo_history(self):
        """為展示產生 30 天歷史，狀態分布：85% 正常 / 5% 遲到 / 5% 請假 / 3% 加班 / 2% 缺勤"""
        random.seed(2026)
        today = date.today()
        for days_ago in range(30, 0, -1):
            d = (today - timedelta(days=days_ago))
            # 跳過週末
            if d.weekday() >= 5: continue
            key = d.isoformat()
            records = {}
            for mid in self.attn.members:
                r = random.random()
                if r < 0.85:
                    st = 'online'; clock_in = f'08:{random.randint(10,55):02d}'
                elif r < 0.90:
                    st = 'late'; clock_in = f'09:{random.randint(5,45):02d}'
                elif r < 0.95:
                    st = 'leave'; clock_in = None
                elif r < 0.98:
                    st = 'overtime'; clock_in = f'08:{random.randint(10,40):02d}'
                else:
                    st = 'absent'; clock_in = None
                records[mid] = {
                    'status': st,
                    'clock_in': clock_in,
                    'clock_out': None if st in ('leave','absent') else f'17:{random.randint(30,59):02d}',
                    'note': '',
                }
            self._history[key] = records
        self._save_history()
        print(f'[Analytics] 已產生 30 天展示歷史資料')

    # ═════════════════════════════════════════
    # 查詢：每日 / 每月 / 個人
    # ═════════════════════════════════════════
    def daily_summary(self, date_str: str, dept: Optional[str] = None) -> dict:
        """特定日期全員出缺勤狀況"""
        records = self._history.get(date_str, {})
        out = []
        for mid, m in self.attn.members.items():
            if dept and not (m.dept or '').startswith(dept): continue
            rec = records.get(mid)
            if rec:
                status = rec.get('status', 'online')
            else:
                # 沒資料 = 尚未記錄（非工作日）
                status = 'none'
            out.append({
                'member_id': mid,
                'member_name': m.name,
                'dept': m.dept or '',
                'title': m.title or m.role or '',
                'status': status,
                'status_label': STATUS_SET.get(status, {}).get('label', status),
                'status_icon':  STATUS_SET.get(status, {}).get('icon', '❓'),
                'clock_in':  (rec or {}).get('clock_in'),
                'clock_out': (rec or {}).get('clock_out'),
                'note': (rec or {}).get('note', ''),
            })
        # 統計
        counter = {}
        for row in out:
            s = row['status']
            counter[s] = counter.get(s, 0) + 1
        return {'date': date_str, 'total': len(out), 'counter': counter, 'records': out}

    def monthly_summary(self, year: int, month: int, dept: Optional[str] = None) -> dict:
        """月度統計：每位員工本月各狀態次數"""
        prefix = f'{year:04d}-{month:02d}'
        days = [d for d in self._history if d.startswith(prefix)]
        days.sort()
        per_member = {}
        for mid, m in self.attn.members.items():
            if dept and not (m.dept or '').startswith(dept): continue
            per_member[mid] = {
                'member_id': mid, 'member_name': m.name,
                'dept': m.dept or '', 'title': m.title or m.role or '',
                'counter': {}, 'total_days': 0,
            }
        for d in days:
            recs = self._history.get(d, {})
            for mid, rec in recs.items():
                if mid not in per_member: continue
                s = rec.get('status', 'online')
                per_member[mid]['counter'][s] = per_member[mid]['counter'].get(s, 0) + 1
                per_member[mid]['total_days'] += 1
        # 計算整體
        grand = {}
        for pm in per_member.values():
            for s, n in pm['counter'].items():
                grand[s] = grand.get(s, 0) + n
        return {
            'year_month': prefix,
            'days': days,
            'work_days': len(days),
            'per_member': list(per_member.values()),
            'grand_counter': grand,
        }

    def member_monthly(self, member_id: str, year: int, month: int) -> dict:
        """個人月度明細（每日一列）"""
        prefix = f'{year:04d}-{month:02d}'
        m = self.attn.members.get(member_id)
        if not m: return {'error': '成員不存在'}
        days = sorted([d for d in self._history if d.startswith(prefix)])
        rows = []
        counter = {}
        for d in days:
            rec = self._history.get(d, {}).get(member_id)
            if not rec:
                rows.append({'date': d, 'status': 'none', 'status_icon': '—'})
                continue
            s = rec.get('status', 'online')
            counter[s] = counter.get(s, 0) + 1
            rows.append({
                'date': d, 'status': s,
                'status_label': STATUS_SET.get(s, {}).get('label', s),
                'status_icon':  STATUS_SET.get(s, {}).get('icon', '❓'),
                'clock_in':  rec.get('clock_in'),
                'clock_out': rec.get('clock_out'),
                'note': rec.get('note', ''),
            })
        return {
            'member_id': member_id,
            'member_name': m.name,
            'dept': m.dept or '',
            'title': m.title or m.role or '',
            'year_month': prefix,
            'counter': counter,
            'rows': rows,
        }

    # ═════════════════════════════════════════
    # 編輯工作流（HR 修改 → 部門最高主管審批）
    # ═════════════════════════════════════════
    def _find_dept_head(self, member_id: str) -> Optional[str]:
        """找該成員的部門最高主管（經理/協理），作為審批者"""
        chain = self.leave_ot.build_approval_chain(member_id)
        # 從鏈尾往前找第一個 經理/協理（排除總經理/董事長）
        for c in reversed(chain):
            t = (c.get('approver_title') or '')
            if ('經理' in t or '協理' in t) and '總經理' not in t:
                return c['approver_id']
        # 退而求其次：鏈最後一個
        if chain:
            return chain[-1]['approver_id']
        return None

    def request_edit(self, actor_id: str, target_id: str, date_str: str,
                     field: str, new_value: str, reason: str = '') -> dict:
        """HR 提出編輯請求，需部門最高主管審批後才生效"""
        actor = self.attn.members.get(actor_id)
        if not actor or not actor.is_hr:
            return {'success': False, 'error': '僅 HR 權限可編輯出缺勤紀錄'}
        target = self.attn.members.get(target_id)
        if not target:
            return {'success': False, 'error': '目標成員不存在'}
        if field not in ('status', 'clock_in', 'clock_out', 'note'):
            return {'success': False, 'error': f'不支援編輯欄位：{field}'}

        # 取現值
        old_rec = self._history.get(date_str, {}).get(target_id, {})
        old_value = old_rec.get(field)

        # 審批者 = 部門最高主管
        approver_id = self._find_dept_head(target_id)
        # 若目標本身是部門最高主管，就由更上層審批
        if approver_id == target_id:
            approver_id = None
            chain = self.leave_ot.build_approval_chain(target_id)
            if chain:
                approver_id = chain[0]['approver_id']

        edit = {
            'id': f'EDIT-{datetime.now().strftime("%Y%m%d")}-{uuid.uuid4().hex[:6].upper()}',
            'actor_id': actor_id, 'actor_name': actor.name,
            'target_id': target_id, 'target_name': target.name,
            'target_dept': target.dept or '',
            'date': date_str, 'field': field,
            'old_value': old_value, 'new_value': new_value,
            'reason': reason,
            'approver_id': approver_id,
            'approver_name': self.attn.members[approver_id].name if approver_id and approver_id in self.attn.members else '-',
            'status': 'pending',
            'created_at': datetime.now().isoformat(timespec='seconds'),
            'approved_at': None, 'reject_reason': None,
        }
        self._append_edit(edit)
        self._audit('edit_request', actor_id, {
            'edit_id': edit['id'], 'target': target_id, 'date': date_str,
            'field': field, 'old': old_value, 'new': new_value, 'reason': reason,
        })

        # 通知審批者
        if approver_id and hasattr(self.attn, '_add_notification'):
            try:
                self.attn._add_notification(
                    approver_id, 'attendance_edit_pending',
                    f'⏳ HR 申請修改 {target.name} 於 {date_str} 的 {field}：{old_value} → {new_value}（原因：{reason}）',
                    priority='normal'
                )
            except Exception:
                pass
        return {'success': True, 'edit': edit}

    def approve_edit(self, approver_id: str, edit_id: str) -> dict:
        """部門最高主管核准 → 實際寫入歷史紀錄"""
        edit = next((e for e in self._edits if e['id'] == edit_id), None)
        if not edit: return {'success': False, 'error': '編輯請求不存在'}
        if edit['status'] != 'pending': return {'success': False, 'error': f'狀態為 {edit["status"]}'}
        # 驗證審批者
        actor = self.attn.members.get(approver_id)
        is_authorized = (approver_id == edit['approver_id']) or (actor and any(k in (actor.title or '') for k in ('總經理', '董事長')))
        if not is_authorized:
            return {'success': False, 'error': '您不是此請求的審批者'}
        # 實際寫入歷史
        d = edit['date']; t = edit['target_id']; f = edit['field']
        self._history.setdefault(d, {}).setdefault(t, {
            'status': 'online', 'clock_in': None, 'clock_out': None, 'note': ''
        })
        self._history[d][t][f] = edit['new_value']
        self._save_history()
        # 更新 edit 狀態
        edit['status'] = 'approved'
        edit['approved_at'] = datetime.now().isoformat(timespec='seconds')
        edit['final_approver_id'] = approver_id
        self._rewrite_edits()
        self._audit('edit_approved', approver_id, {
            'edit_id': edit_id, 'target': t, 'date': d, 'field': f,
            'old': edit['old_value'], 'new': edit['new_value'],
        })
        return {'success': True, 'edit': edit}

    def reject_edit(self, approver_id: str, edit_id: str, reason: str = '') -> dict:
        edit = next((e for e in self._edits if e['id'] == edit_id), None)
        if not edit: return {'success': False, 'error': '編輯請求不存在'}
        if edit['status'] != 'pending': return {'success': False, 'error': f'狀態為 {edit["status"]}'}
        actor = self.attn.members.get(approver_id)
        is_authorized = (approver_id == edit['approver_id']) or (actor and any(k in (actor.title or '') for k in ('總經理', '董事長')))
        if not is_authorized:
            return {'success': False, 'error': '您不是此請求的審批者'}
        edit['status'] = 'rejected'
        edit['approved_at'] = datetime.now().isoformat(timespec='seconds')
        edit['reject_reason'] = reason
        edit['final_approver_id'] = approver_id
        self._rewrite_edits()
        self._audit('edit_rejected', approver_id, {
            'edit_id': edit_id, 'reason': reason, 'target': edit['target_id'],
        })
        return {'success': True, 'edit': edit}

    def list_edits(self, status: Optional[str] = None, approver_id: Optional[str] = None,
                   actor_id: Optional[str] = None, limit: int = 200) -> list:
        out = list(reversed(self._edits))
        if status: out = [e for e in out if e['status'] == status]
        if approver_id: out = [e for e in out if e['approver_id'] == approver_id]
        if actor_id: out = [e for e in out if e['actor_id'] == actor_id]
        return out[:limit]

    def read_audit(self, limit: int = 200) -> list:
        out = []
        if os.path.exists(self.audit_file):
            with open(self.audit_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    try: out.append(json.loads(line))
                    except: pass
        return out[-limit:][::-1]
