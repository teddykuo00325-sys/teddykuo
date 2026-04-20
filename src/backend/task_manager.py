#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
凌策公司 — TaskManager 任務派工引擎

兩種派工方式：
1. auto_dispatch_project: 自動從頂層往下層層派發（AI 指揮官/客戶模擬器觸發）
2. dispatch_task: 單點上對下手動派發

每個任務會自動更新被派發者的週目標，方便前端即時顯示。
"""

import json
import os
import uuid
import threading
from datetime import datetime
from typing import Dict, List, Optional


# 依角色產出任務的模板（自動派工時使用）
ROLE_TASK_TEMPLATES = {
    '經理': {
        'title': '策略監督：{project}',
        'desc': '監督全案執行、核准關鍵里程碑、對外管理客戶期望。\n專案主題：{description}',
    },
    '人事經理': {
        'title': '人力盤點：{project}',
        'desc': '評估專案所需人力、協調跨課人員調度、追蹤成員出缺勤狀態。\n專案主題：{description}',
    },
    '副理': {
        'title': '部門統籌：{project}',
        'desc': '整合所屬課組資源、推進部門里程碑、彙整課長回報。\n專案主題：{description}',
    },
    '課長': {
        'title': '課組推進：{project}',
        'desc': '追蹤副課長進度、確保交付品質、處理課內技術決策。\n專案主題：{description}',
    },
    '副課長': {
        'title': '小組分派：{project}',
        'desc': '分派具體開發任務給工程師、進行 Code Review、彙整小組進度。\n專案主題：{description}',
    },
    '工程師': {
        'title': '執行任務：{project}',
        'desc': '根據上級分派，負責具體開發工作。\n專案主題：{description}',
    },
}


class Task:
    def __init__(self, task_id: str, title: str, description: str,
                 assigned_to: str, assigned_by: str,
                 client: Optional[str] = None, parent_task_id: Optional[str] = None,
                 project_id: Optional[str] = None,
                 created_at: Optional[datetime] = None):
        self.id = task_id
        self.title = title
        self.description = description
        self.assigned_to = assigned_to
        self.assigned_by = assigned_by
        self.client = client
        self.parent_task_id = parent_task_id
        self.children_task_ids: List[str] = []
        self.project_id = project_id
        self.status = 'pending'       # pending | in_progress | blocked | done
        self.progress = 0
        self.created_at = created_at or datetime.now()
        self.updates: List[Dict] = []
        # 跨組派工審批
        self.approval_status = 'approved'   # approved | pending | rejected
        self.approver_id: Optional[str] = None   # 待誰核准（target 的直屬主管）
        self.approval_reason: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'assigned_to': self.assigned_to,
            'assigned_by': self.assigned_by,
            'client': self.client,
            'parent_task_id': self.parent_task_id,
            'children_task_ids': self.children_task_ids,
            'project_id': self.project_id,
            'status': self.status,
            'progress': self.progress,
            'created_at': self.created_at.isoformat(),
            'updates': self.updates,
            'approval_status': self.approval_status,
            'approver_id': self.approver_id,
            'approval_reason': self.approval_reason,
        }

    @classmethod
    def from_dict(cls, d: Dict):
        t = cls(
            task_id=d['id'], title=d['title'], description=d['description'],
            assigned_to=d['assigned_to'], assigned_by=d['assigned_by'],
            client=d.get('client'), parent_task_id=d.get('parent_task_id'),
            project_id=d.get('project_id'),
            created_at=datetime.fromisoformat(d['created_at']),
        )
        t.children_task_ids = d.get('children_task_ids', [])
        t.status = d.get('status', 'pending')
        t.progress = d.get('progress', 0)
        t.updates = d.get('updates', [])
        t.approval_status = d.get('approval_status', 'approved')
        t.approver_id = d.get('approver_id')
        t.approval_reason = d.get('approval_reason')
        return t


class TaskManager:
    def __init__(self, attendance_mgr, file_path: str, chat_mgr=None):
        self.attn = attendance_mgr
        self.chat = chat_mgr  # 可選：派工時自動通知
        self.tasks: Dict[str, Task] = {}
        self.file_path = file_path
        self._lock = threading.Lock()
        self._load()

    # ═══════════════════════════════════════════════════════
    # 持久化
    # ═══════════════════════════════════════════════════════
    def _save(self):
        with self._lock:
            data = {tid: t.to_dict() for tid, t in self.tasks.items()}
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

    def _load(self):
        if not os.path.exists(self.file_path):
            return
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for tid, d in data.items():
                self.tasks[tid] = Task.from_dict(d)
            print(f'[TaskManager] 載入 {len(self.tasks)} 項任務')
        except Exception as e:
            print(f'[TaskManager] 載入失敗: {e}')

    # ═══════════════════════════════════════════════════════
    # 權限：派任務「只限直屬下屬」
    # 規則：
    #   - 上對下只能派給直屬下屬（單層下派），不得跨階/跨單位
    #   - 同層級需求應先溝通，再由該層級派發自己的下屬
    #   - HR / 人事經理 例外：可派全組織（組織調度用途）
    # ═══════════════════════════════════════════════════════
    def can_dispatch(self, from_id: str, to_id: str) -> str:
        """
        【整合後的規則：提出需求】
        需求可雙向流動（上對下、下對上、平行），但跨組需核准。
        回傳空字串表示允許；否則回傳拒絕原因。
        實際是否需核准由 dispatch_task 內根據「是否同組」判斷。
        """
        from_m = self.attn.members.get(from_id)
        to_m = self.attn.members.get(to_id)
        if not from_m:
            return '需求提出者不存在'
        if not to_m:
            return '需求對象不存在'
        if from_id == to_id:
            return '不能向自己提出需求'
        return ''  # 一律允許提出，是否需核准由任務審批機制控管

    def _is_same_group(self, from_m, to_m) -> bool:
        """判斷兩人是否為「同組」— 免審批的直接通道
        同組定義：
          - 共同直屬上級（平行同事）
          - 互為直屬上下級
          - HR 豁免
        """
        if from_m.is_hr:
            return True
        # 平行同事（同直屬上級）
        if from_m.supervisor_id and from_m.supervisor_id == to_m.supervisor_id:
            return True
        # 我是對方直屬主管
        if to_m.supervisor_id == from_m.id:
            return True
        # 對方是我的直屬主管（我向我的上級提需求）
        if from_m.supervisor_id == to_m.id:
            return True
        return False

    def _is_ancestor(self, ancestor_id: str, descendant_id: str) -> bool:
        """判斷 ancestor 是否為 descendant 的祖先（任意深度）"""
        cur = self.attn.members.get(descendant_id)
        visited = set()
        while cur and cur.supervisor_id and cur.id not in visited:
            visited.add(cur.id)
            if cur.supervisor_id == ancestor_id:
                return True
            cur = self.attn.members.get(cur.supervisor_id)
        return False

    def _ancestor_chain(self, member_id: str):
        chain = []
        cur = self.attn.members.get(member_id)
        while cur and cur.supervisor_id:
            p = self.attn.members.get(cur.supervisor_id)
            if not p:
                break
            chain.append(p)
            cur = p
        return chain

    # ═══════════════════════════════════════════════════════
    # 自動派工：從頂層往下層層派發
    # ═══════════════════════════════════════════════════════
    def auto_dispatch_project(self, initiator_id: str, project_title: str,
                              description: str, client: Optional[str] = None) -> Dict:
        """
        依組織樹遞迴派發任務。每個成員依自己的角色收到客製化任務。
        回傳每個層級的派工統計。
        """
        # 找根節點
        roots = [m for m in self.attn.members.values() if m.supervisor_id is None]
        if not roots:
            return {'success': False, 'error': '找不到組織根節點'}
        root = roots[0]

        project_id = 'PRJ-' + datetime.now().strftime('%Y%m%d-%H%M%S')
        created_tasks: List[Task] = []

        def render_task(role: str) -> Dict:
            tpl = ROLE_TASK_TEMPLATES.get(role, {'title': '{project}', 'desc': '{description}'})
            return {
                'title': tpl['title'].format(project=project_title, description=description),
                'desc': tpl['desc'].format(project=project_title, description=description),
            }

        def assign_recursive(member, parent_task_id: Optional[str] = None):
            t_data = render_task(member.role)
            task = Task(
                task_id=self._new_id(),
                title=t_data['title'],
                description=t_data['desc'],
                assigned_to=member.id,
                assigned_by=(initiator_id if parent_task_id is None
                             else self.tasks[parent_task_id].assigned_to),
                client=client,
                parent_task_id=parent_task_id,
                project_id=project_id,
            )
            self.tasks[task.id] = task
            if parent_task_id and parent_task_id in self.tasks:
                self.tasks[parent_task_id].children_task_ids.append(task.id)
            created_tasks.append(task)

            # 遞迴下層
            subs = [m for m in self.attn.members.values() if m.supervisor_id == member.id]
            for sub in subs:
                assign_recursive(sub, task.id)

            # 更新成員週目標
            self._update_member_objective(member.id)

        assign_recursive(root)

        # 人事經理不一定在組織樹中（若是平級），確保也收到
        # 已經在樹內就不用再發

        self._save()

        # 統計
        by_role = {}
        for t in created_tasks:
            m = self.attn.members.get(t.assigned_to)
            if m:
                by_role[m.role] = by_role.get(m.role, 0) + 1

        return {
            'success': True,
            'project_id': project_id,
            'project_title': project_title,
            'client': client,
            'total_tasks': len(created_tasks),
            'by_role': by_role,
            'root_task_id': created_tasks[0].id if created_tasks else None,
        }

    # ═══════════════════════════════════════════════════════
    # 手動派工：上對下單點派發
    # ═══════════════════════════════════════════════════════
    def dispatch_task(self, from_id: str, to_id: str, title: str, description: str,
                      client: Optional[str] = None, parent_task_id: Optional[str] = None) -> Dict:
        reject_reason = self.can_dispatch(from_id, to_id)
        if reject_reason:
            return {'success': False, 'error': reject_reason}
        to_m = self.attn.members.get(to_id)
        from_m = self.attn.members.get(from_id)
        if not to_m:
            return {'success': False, 'error': '指派對象不存在'}

        task = Task(
            task_id=self._new_id(),
            title=title, description=description,
            assigned_to=to_id, assigned_by=from_id,
            client=client, parent_task_id=parent_task_id,
        )

        # 跨組提需求審批判斷：
        # - 同組（平行 / 直屬上下 / HR）→ 直接生效
        # - 跨組 → 對方組長（直屬主管）核准後才生效
        same_group = self._is_same_group(from_m, to_m)
        if not same_group and to_m.supervisor_id:
            task.approval_status = 'pending'
            task.approver_id = to_m.supervisor_id

        self.tasks[task.id] = task
        if parent_task_id and parent_task_id in self.tasks:
            self.tasks[parent_task_id].children_task_ids.append(task.id)

        # 僅在 approved 狀態下才更新週目標
        if task.approval_status == 'approved':
            self._update_member_objective(to_id)
        self._save()

        # 通知
        if task.approval_status == 'pending' and task.approver_id:
            approver = self.attn.members.get(task.approver_id)
            approver_name = approver.name if approver else task.approver_id
            self.attn._add_notification(
                task.approver_id, 'request_pending_approval',
                f'⏳ {from_m.name if from_m else from_id} 向您的下屬 {to_m.name} 提出跨組需求「{title}」，請審核。',
                priority='high'
            )
            self.attn._add_notification(
                from_id, 'request_pending',
                f'⏳ 您對 {to_m.name} 的需求「{title}」需經 {approver_name}（組長）核准',
                priority='normal'
            )
        else:
            self.attn._add_notification(
                to_id, 'request_received',
                f'📝 {from_m.name if from_m else from_id} 提出新需求：{title}',
                priority='normal'
            )
        return {'success': True, 'task': task.to_dict()}

    # ═══════════════════════════════════════════════════════
    # 任務審批
    # ═══════════════════════════════════════════════════════
    def approve_task(self, approver_id: str, task_id: str) -> Dict:
        t = self.tasks.get(task_id)
        if not t:
            return {'success': False, 'error': '任務不存在'}
        if t.approval_status != 'pending':
            return {'success': False, 'error': f'任務狀態為 {t.approval_status}，無法核准'}
        actor = self.attn.members.get(approver_id)
        if approver_id != t.approver_id and not (actor and actor.is_hr):
            return {'success': False, 'error': '您不是此任務的核准人'}
        t.approval_status = 'approved'
        t.approval_reason = '已核准'
        self._update_member_objective(t.assigned_to)
        self._save()
        # 通知
        self.attn._add_notification(
            t.assigned_to, 'task_approved',
            f'✅ 任務「{t.title}」已被核准，請開始執行', priority='normal'
        )
        self.attn._add_notification(
            t.assigned_by, 'task_approved',
            f'✅ 您指派的任務「{t.title}」已被 {actor.name if actor else approver_id} 核准',
            priority='normal'
        )
        return {'success': True, 'task': t.to_dict()}

    def reject_task(self, approver_id: str, task_id: str, reason: str = '') -> Dict:
        t = self.tasks.get(task_id)
        if not t:
            return {'success': False, 'error': '任務不存在'}
        if t.approval_status != 'pending':
            return {'success': False, 'error': f'任務狀態為 {t.approval_status}，無法拒絕'}
        actor = self.attn.members.get(approver_id)
        if approver_id != t.approver_id and not (actor and actor.is_hr):
            return {'success': False, 'error': '您不是此任務的核准人'}
        t.approval_status = 'rejected'
        t.approval_reason = reason or '未提供理由'
        self._save()
        self.attn._add_notification(
            t.assigned_by, 'task_rejected',
            f'❌ 您指派給 {self.attn.members[t.assigned_to].name} 的「{t.title}」被 {actor.name if actor else approver_id} 拒絕。{reason}',
            priority='high'
        )
        return {'success': True, 'task': t.to_dict()}

    def list_pending_task_approvals(self, approver_id: str) -> List[Dict]:
        result = []
        for t in self.tasks.values():
            if t.approval_status == 'pending' and t.approver_id == approver_id:
                d = t.to_dict()
                from_m = self.attn.members.get(t.assigned_by)
                to_m = self.attn.members.get(t.assigned_to)
                d['from_name'] = from_m.name if from_m else t.assigned_by
                d['to_name'] = to_m.name if to_m else t.assigned_to
                result.append(d)
        return result

    # ═══════════════════════════════════════════════════════
    # 進度更新
    # ═══════════════════════════════════════════════════════
    def update_progress(self, task_id: str, progress: int, status: Optional[str] = None,
                        note: Optional[str] = None, actor_id: Optional[str] = None) -> Dict:
        t = self.tasks.get(task_id)
        if not t:
            return {'success': False, 'error': '任務不存在'}
        old = t.progress
        t.progress = max(0, min(100, int(progress)))
        if status:
            t.status = status
        elif t.progress >= 100:
            t.status = 'done'
        elif t.progress > 0:
            t.status = 'in_progress'
        t.updates.append({
            'at': datetime.now().isoformat(),
            'from': old, 'to': t.progress,
            'status': t.status, 'note': note or '',
            'actor_id': actor_id or t.assigned_to,
        })
        self._update_member_objective(t.assigned_to)
        # 若已完成，檢查父任務是否所有子任務都完成→ 自動推進父任務進度
        if t.status == 'done' and t.parent_task_id:
            self._maybe_propagate_up(t.parent_task_id)
        self._save()
        return {'success': True, 'task': t.to_dict()}

    def _maybe_propagate_up(self, parent_id: str):
        p = self.tasks.get(parent_id)
        if not p:
            return
        children = [self.tasks[cid] for cid in p.children_task_ids if cid in self.tasks]
        if not children:
            return
        avg_progress = sum(c.progress for c in children) / len(children)
        p.progress = int(avg_progress)
        if all(c.status == 'done' for c in children):
            p.status = 'done'
        elif p.progress > 0:
            p.status = 'in_progress'
        self._update_member_objective(p.assigned_to)
        if p.status == 'done' and p.parent_task_id:
            self._maybe_propagate_up(p.parent_task_id)

    # ═══════════════════════════════════════════════════════
    # 成員週目標更新（整合進 attendance_manager 的 weekly_objective）
    # ═══════════════════════════════════════════════════════
    def _update_member_objective(self, member_id: str):
        m = self.attn.members.get(member_id)
        if not m:
            return
        my_tasks = [t for t in self.tasks.values() if t.assigned_to == member_id]
        active = [t for t in my_tasks if t.status != 'done']
        done_count = sum(1 for t in my_tasks if t.status == 'done')

        if not my_tasks:
            return

        avg_progress = int(sum(t.progress for t in my_tasks) / len(my_tasks)) if my_tasks else 0
        # 最新任務作為標題顯示
        latest = max(my_tasks, key=lambda t: t.created_at)
        m.weekly_objective = {
            'title': latest.title,
            'description': f'共 {len(my_tasks)} 項任務（進行中 {len(active)} / 已完成 {done_count}）',
            'kpi': '全部任務如期完成',
            'progress': avg_progress,
            'task_count': len(my_tasks),
            'active_count': len(active),
            'done_count': done_count,
        }

    # ═══════════════════════════════════════════════════════
    # 查詢
    # ═══════════════════════════════════════════════════════
    def get_member_tasks(self, member_id: str) -> Dict:
        assigned_to_me = [t.to_dict() for t in self.tasks.values() if t.assigned_to == member_id]
        assigned_by_me = [t.to_dict() for t in self.tasks.values() if t.assigned_by == member_id]
        # 補上對方名字
        for t in assigned_to_me:
            assigner = self.attn.members.get(t['assigned_by'])
            t['assigner_name'] = assigner.name if assigner else t['assigned_by']
            t['assigner_role'] = assigner.role if assigner else ''
        for t in assigned_by_me:
            assignee = self.attn.members.get(t['assigned_to'])
            t['assignee_name'] = assignee.name if assignee else t['assigned_to']
            t['assignee_role'] = assignee.role if assignee else ''
        return {
            'assigned_to_me': sorted(assigned_to_me, key=lambda t: t['created_at'], reverse=True),
            'assigned_by_me': sorted(assigned_by_me, key=lambda t: t['created_at'], reverse=True),
            'stats': {
                'total_to_me': len(assigned_to_me),
                'active_to_me': sum(1 for t in assigned_to_me if t['status'] != 'done'),
                'done_to_me': sum(1 for t in assigned_to_me if t['status'] == 'done'),
                'total_by_me': len(assigned_by_me),
            }
        }

    def get_project_tree(self, project_id: str) -> Dict:
        project_tasks = [t for t in self.tasks.values() if t.project_id == project_id]
        if not project_tasks:
            return {}
        # 找 root task（parent_task_id is None within this project）
        root = next((t for t in project_tasks if t.parent_task_id is None), None)
        if not root:
            return {}

        def build(t: Task) -> Dict:
            m = self.attn.members.get(t.assigned_to)
            d = t.to_dict()
            d['assignee_name'] = m.name if m else t.assigned_to
            d['assignee_role'] = m.role if m else ''
            d['assignee_avatar'] = m.avatar if m else '👤'
            d['children'] = [build(self.tasks[cid]) for cid in t.children_task_ids if cid in self.tasks]
            return d

        return build(root)

    def list_projects(self) -> List[Dict]:
        by_project: Dict[str, List[Task]] = {}
        for t in self.tasks.values():
            if t.project_id:
                by_project.setdefault(t.project_id, []).append(t)
        result = []
        for pid, tasks in by_project.items():
            total = len(tasks)
            done = sum(1 for t in tasks if t.status == 'done')
            avg = int(sum(t.progress for t in tasks) / total) if total else 0
            root = next((t for t in tasks if t.parent_task_id is None), tasks[0])
            result.append({
                'project_id': pid,
                'project_title': root.title.split('：', 1)[-1] if '：' in root.title else root.title,
                'client': root.client,
                'total_tasks': total,
                'done_tasks': done,
                'avg_progress': avg,
                'created_at': min(t.created_at.isoformat() for t in tasks),
            })
        return sorted(result, key=lambda p: p['created_at'], reverse=True)

    def stats(self) -> Dict:
        return {
            'total_tasks': len(self.tasks),
            'by_status': {
                s: sum(1 for t in self.tasks.values() if t.status == s)
                for s in ['pending', 'in_progress', 'blocked', 'done']
            },
            'total_projects': len({t.project_id for t in self.tasks.values() if t.project_id}),
        }

    def _new_id(self) -> str:
        return 'T-' + uuid.uuid4().hex[:8].upper()


if __name__ == '__main__':
    # 測試
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from attendance_manager import AttendanceManager
    from members_data import build_initial_org

    attn = AttendanceManager(build_initial_org())
    import tempfile
    tm = TaskManager(attn, os.path.join(tempfile.gettempdir(), 'test_tasks.json'))

    r = tm.auto_dispatch_project(
        'MGR-001', 'addwii AI 客服系統',
        '建置 24/7 智慧客服與 Dashboard，兩週交付',
        client='addwii'
    )
    print('自動派工：', r)

    # 查看某人的任務
    eng = tm.get_member_tasks('ENG-001')
    print(f'\n郭宇翔（工程師）收到任務：{len(eng["assigned_to_me"])} 項')
    for t in eng['assigned_to_me']:
        print(f'  - {t["title"]}')
        print(f'    指派人: {t["assigner_name"]}（{t["assigner_role"]}）')
