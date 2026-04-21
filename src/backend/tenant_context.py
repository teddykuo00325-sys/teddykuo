# -*- coding: utf-8 -*-
"""
多租戶 Context：為 4 個租戶（lingce / microjet / addwii / weiming）
各自維護一組 Manager 實例 + 資料目錄路徑。

使用方式：
    from tenant_context import TENANT_CTX
    mgr = TENANT_CTX.get('microjet').attendance
    crm = TENANT_CTX.get('addwii').crm
"""
import os, threading
from typing import Dict


TENANT_IDS = ['lingce', 'microjet', 'addwii', 'weiming']
TENANT_META = {
    'lingce':   {'name': '凌策公司',   'icon': '🏛️', 'color': 'blue',
                 'desc': 'AI Agent 服務型組織 · 1 人老闆 + 10 AI'},
    'microjet': {'name': 'MicroJet',   'icon': '🏭', 'color': 'amber',
                 'desc': 'MEMS 壓電微流體製造 · 134 人'},
    'addwii':   {'name': 'addwii',     'icon': '🏠', 'color': 'sky',
                 'desc': '場域無塵室 B2C 品牌 · 6 人'},
    'weiming':  {'name': '維明顧問',   'icon': '📋', 'color': 'slate',
                 'desc': '企業顧問業 · 評估中'},
}

DATA_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'data')


class TenantPaths:
    """單一租戶的所有檔案路徑"""
    def __init__(self, tid: str):
        self.tid = tid
        self.root = os.path.abspath(os.path.join(DATA_ROOT, tid))
        self.org_file          = os.path.join(self.root, 'org.json')
        self.crm_db            = os.path.join(self.root, 'crm.db')
        self.audit_dir         = os.path.join(self.root, 'audit')
        self.leave_ot_dir      = os.path.join(self.root, 'leave_overtime')
        self.analytics_dir     = os.path.join(self.root, 'attendance_analytics')
        self.chat_rooms_dir    = os.path.join(self.root, 'chat_rooms')
        # 稽核檔（依 tenant 獨立）
        self.pii_audit         = os.path.join(self.audit_dir, 'pii_audit.jsonl')
        self.human_gate        = os.path.join(self.audit_dir, 'human_gate.jsonl')
        self.acceptance_audit  = os.path.join(self.audit_dir, 'acceptance_audit.jsonl')
        self.org_audit         = os.path.join(self.audit_dir, 'audit_log.jsonl')
        self.website_inquiries = os.path.join(self.audit_dir, 'website_inquiries.jsonl')
        self.tasks             = os.path.join(self.audit_dir, 'tasks.json')
        # 跨 tenant 共享（procurement）
        self.procurement_state = os.path.join(DATA_ROOT, 'lingce', 'audit', 'procurement_state.json')


class TenantBundle:
    """單一租戶的 Manager 集合（懶載入）"""
    def __init__(self, tid: str):
        self.tid = tid
        self.paths = TenantPaths(tid)
        self._attendance = None
        self._crm = None
        self._chat = None
        self._leave_ot = None
        self._analytics = None

    @property
    def attendance(self):
        if self._attendance is None:
            from attendance_manager import AttendanceManager
            from members_data import build_initial_org
            # 若 org.json 存在就從檔案載；否則退到 build_initial_org（只有第一次）
            if os.path.exists(self.paths.org_file):
                self._attendance = AttendanceManager([], org_file=self.paths.org_file)
            else:
                self._attendance = AttendanceManager(build_initial_org(), org_file=self.paths.org_file)
        return self._attendance

    @property
    def crm(self):
        if self._crm is None:
            from crm_manager import CRMManager
            self._crm = CRMManager(db_path=self.paths.crm_db)
        return self._crm

    @property
    def chat(self):
        if self._chat is None:
            from chat_manager import ChatManager
            # ChatManager 需要指定 log 目錄
            self._chat = ChatManager(self.attendance, chat_log_dir=self.paths.chat_rooms_dir)
        return self._chat

    @property
    def leave_ot(self):
        if self._leave_ot is None:
            from leave_overtime_manager import LeaveOvertimeManager
            os.makedirs(self.paths.leave_ot_dir, exist_ok=True)
            self._leave_ot = LeaveOvertimeManager(
                self.attendance,
                data_dir=self.paths.leave_ot_dir,
            )
        return self._leave_ot

    @property
    def analytics(self):
        if self._analytics is None:
            from attendance_analytics import AttendanceAnalyticsManager
            os.makedirs(self.paths.analytics_dir, exist_ok=True)
            self._analytics = AttendanceAnalyticsManager(
                self.attendance, self.leave_ot, self.paths.analytics_dir,
            )
        return self._analytics


class TenantRegistry:
    """全域註冊表"""
    def __init__(self):
        self._bundles: Dict[str, TenantBundle] = {}
        self._lock = threading.Lock()

    def get(self, tid: str) -> TenantBundle:
        if tid not in TENANT_IDS:
            tid = 'lingce'  # 預設
        with self._lock:
            if tid not in self._bundles:
                self._bundles[tid] = TenantBundle(tid)
        return self._bundles[tid]

    def all(self):
        return [(tid, self.get(tid)) for tid in TENANT_IDS]


TENANT_CTX = TenantRegistry()


def parse_tenant(request_args_or_json, default='lingce'):
    """從 Flask request 取得 tenant id（query/body/header 皆支援）"""
    if hasattr(request_args_or_json, 'get'):
        t = request_args_or_json.get('tenant')
        if t and t in TENANT_IDS: return t
    return default
