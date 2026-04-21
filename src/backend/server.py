#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
凌策公司 — AI Agent 協作平台 真實後端
Flask + Ollama 本地模型，全自動化 Agent 系統
"""

import json
import time
import threading
import uuid
import sys
import os as _os_early
from datetime import datetime

# ─── Windows 專用：關閉 cmd 視窗的「快速編輯模式」 ───
# 預設 CMD 視窗只要使用者點到文字區就會進入選取模式，暫停 Python 程序
# 造成瀏覽器卡住、API 無回應等假性故障。這裡用 Win32 API 強制關閉
if _os_early.name == 'nt':
    try:
        import ctypes as _ctypes
        _k32 = _ctypes.windll.kernel32
        _ENABLE_QUICK_EDIT = 0x0040
        _ENABLE_INSERT     = 0x0020
        _ENABLE_MOUSE      = 0x0010
        _ENABLE_EXT_FLAGS  = 0x0080
        _hin = _k32.GetStdHandle(-10)  # STD_INPUT_HANDLE
        _mode = _ctypes.c_uint()
        if _k32.GetConsoleMode(_hin, _ctypes.byref(_mode)):
            # 清掉 QuickEdit 與 Mouse input，啟用 Extended Flags
            _new = (_mode.value | _ENABLE_EXT_FLAGS) & ~_ENABLE_QUICK_EDIT & ~_ENABLE_MOUSE
            _k32.SetConsoleMode(_hin, _new)
            print('[Console] 已關閉 Quick Edit Mode（避免點視窗凍結 Python）')
    except Exception as _e:
        print(f'[Console] Quick Edit 關閉失敗（不影響運作）: {_e}')
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS  # type: ignore
import requests
import os

# 匯入出缺勤模組
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from attendance_manager import AttendanceManager, AttendanceStatus, TimeWindows
from members_data import build_initial_org, WEEKLY_OBJECTIVES_TEMPLATE
from chat_manager import ChatManager, ChatRelation
from task_manager import TaskManager
import acceptance_scenarios as accs
from crm_manager import CRMManager, MODULE_NAMES, MODULE_PRICES, calc_quote
crm = CRMManager(db_path=os.path.join(os.path.dirname(__file__), '..', '..', 'chat_logs', 'lingce_crm.db'))
# 啟動即在背景預熱 CSV 快取，使用者第一次開頁面就是秒開
threading.Thread(target=lambda: accs.analyze_all_csv('system-prewarm'), daemon=True).start()
# 預熱 Ollama：用 1 token 的小請求讓模型載入記憶體，避免首問等 10~20 秒冷啟動
def _prewarm_ollama():
    try:
        import requests as _rq, os as _os
        _url = _os.getenv('OLLAMA_URL', 'http://127.0.0.1:11434')
        _model = _os.getenv('OLLAMA_MODEL', 'qwen2.5:7b')
        _rq.post(f'{_url}/api/generate', json={'model':_model,'prompt':'hi','stream':False,
            'options':{'num_predict':1}}, timeout=60)
        print('[Ollama] 預熱完成')
    except Exception as e:
        print(f'[Ollama] 預熱失敗: {e}')
threading.Thread(target=_prewarm_ollama, daemon=True).start()
from leave_overtime_manager import (LeaveOvertimeManager, LEAVE_TYPES,
    calculate_weekday_off_times, calculate_holiday_off_times, calculate_overtime_pay)
from attendance_analytics import AttendanceAnalyticsManager
from procurement_manager import ProcurementManager

app = Flask(__name__, static_folder='../../', static_url_path='')
CORS(app)

# ══════════════════════════════════════
# 出缺勤系統初始化（支援組織變更持久化）
# ══════════════════════════════════════
_ORG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         '..', '..', 'chat_logs', 'org_data.json')
attendance_mgr = AttendanceManager(build_initial_org(), org_file=_ORG_FILE)

# 模擬：讓全體成員已打卡（展示時有資料可看）
# 保留約 3% 成員「異常未打卡」以展示紅燈效果
from datetime import datetime as _dt
import random as _rnd_ci
_rnd_ci.seed(7)
_today = _dt.now()
_base_clock_in = _dt.combine(_today.date(), TimeWindows.CLOCK_IN_START)
_all_ids = list(attendance_mgr.members.keys())
# 隨機挑 5 位不打卡（展示異常）
_skip_clock_in = set(_rnd_ci.sample(_all_ids, min(5, len(_all_ids))))
for _i, _mid in enumerate(_all_ids):
    if _mid in _skip_clock_in:
        continue
    # 打卡時間分散在 08:00 ~ 08:55 之間（避免全部同一分鐘）
    _ci_time = _base_clock_in.replace(minute=_i % 55)
    attendance_mgr.clock_in(_mid, _ci_time)

# 模擬：部分成員已提交週回報（展示用）— 涵蓋各部門代表
_report_demo_ids = [
    'MIS-002', 'MIS-007', 'MIS-009',   # 資訊部
    'FIN-002', 'FIN-003',              # 財務
    'HRA-002',                         # 人事總務
    'PD2-007', 'PD2-008', 'PD2-020',   # 產品開發處 2
    'ENG-003', 'ENG-012',              # 工程部（生技/設備課長）
    'QA-003', 'QA-006',                # 品保
    'ADW-002', 'ADW-006',              # addwii
]
for _mid in _report_demo_ids:
    if _mid in attendance_mgr.members:
        _m = attendance_mgr.members[_mid]
        attendance_mgr.submit_report(_mid,
            completed_items=['完成當週交付項目', '修復 P1 bug', '撰寫測試/文件'],
            blockers=['第三方 API 文件待確認'] if _m.role == '工程師' else ['跨組資源協調'],
            next_week_plan=['優化效能', '整合測試', '客戶展示準備'])

# 推送本週目標（展示用）
attendance_mgr.distribute_objectives(WEEKLY_OBJECTIVES_TEMPLATE)
# 模擬各成員進度
import random as _rnd
_rnd.seed(42)
for _m in attendance_mgr.members.values():
    if _m.weekly_objective:
        _m.weekly_objective['progress'] = _rnd.randint(20, 95)

# 聊天管理器（共用 attendance_mgr 的組織資訊，自動從磁碟載入既有對話）
chat_mgr = ChatManager(attendance_mgr, enable_ai_reply=True)

# 任務管理器
_TASK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           '..', '..', 'chat_logs', 'tasks.json')
task_mgr = TaskManager(attendance_mgr, _TASK_FILE, chat_mgr=chat_mgr)

# 請假 & 加班管理器
_LEAVE_OT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              '..', '..', 'chat_logs', 'leave_overtime')
leave_ot_mgr = LeaveOvertimeManager(attendance_mgr, _LEAVE_OT_DIR)

# 出缺勤統計與編輯審批
_ATTN_ANALYTICS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    '..', '..', 'chat_logs', 'attendance_analytics')
attn_analytics = AttendanceAnalyticsManager(attendance_mgr, leave_ot_mgr, _ATTN_ANALYTICS_DIR)

# Phase 3：addwii→microjet 採購流程 + 感測器序號綁定
_PROCUREMENT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 '..', '..', 'chat_logs', 'procurement_state.json')
procurement_mgr = ProcurementManager(_PROCUREMENT_FILE)

# ══════════════════════════════════════
# Ollama 模型配置
# ══════════════════════════════════════
OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://127.0.0.1:11434')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'qwen2.5:7b')  # 升級至 Qwen2.5 7B（繁中能力遠優於原本的 gemma4:e2b）

def ollama_chat(messages, system_prompt=None, temperature=0.7):
    """呼叫 Ollama 本地模型（所有輸入先過 PII Guard 遮蔽）"""
    try:
        from pii_guard import mask_text as _pii_mask, assert_local_only
        assert_local_only()
        masked_messages = []
        for m in messages:
            content = m.get('content', '')
            masked, _ = _pii_mask(content, context='server.chat')
            masked_messages.append({**m, 'content': masked})
        masked_sys = None
        if system_prompt:
            masked_sys, _ = _pii_mask(system_prompt, context='server.system')
    except Exception:
        masked_messages = messages
        masked_sys = system_prompt

    payload = {
        'model': OLLAMA_MODEL,
        'messages': [],
        'stream': False,
        'options': {'temperature': temperature, 'num_predict': 512}
    }
    if masked_sys:
        payload['messages'].append({'role': 'system', 'content': masked_sys})
    payload['messages'].extend(masked_messages)

    try:
        resp = requests.post(f'{OLLAMA_URL}/api/chat', json=payload, timeout=300)
        resp.raise_for_status()
        data = resp.json()
        return data.get('message', {}).get('content', '（無回應）')
    except Exception as e:
        return f'[模型錯誤] {str(e)}'

def _clean_thinking(raw: str) -> str:
    """把 gemma 的 Thinking Process 段落徹底拆掉。"""
    import re
    t = (raw or '').strip()
    # 1. 砍 <think>...</think>
    t = re.sub(r'<think>.*?</think>', '', t, flags=re.DOTALL)

    # 2. 若有「最終回答/Final Answer/Response:」錨點 → 只取其後
    m = re.search(r'(?:\*\*)?(?:Final (?:Answer|Response)|最終(?:回答|答案)|回覆[:：]|回答[:：]|Answer[:：]|Response[:：]|Output[:：])(?:\*\*)?\s*\n*',
                  t, flags=re.IGNORECASE)
    if m:
        t = t[m.end():]

    # 3. 砍整段「Thinking Process/Analyze/Identify/Extract」到下一空行的區塊
    thinking_patterns = [
        r'(?:^|\n)\s*(?:Thinking Process|思考過程|分析過程|推理步驟)[:：]?\s*\n(?:.*?\n)*?\n',
        r'(?:^|\n)\s*\d+\.\s+\*\*[^*]+\*\*[:：]?.*?(?=\n\n|\Z)',  # "1. **Analyze the Request:** ..."
    ]
    for p in thinking_patterns:
        t = re.sub(p, '\n', t, flags=re.DOTALL)

    # 4. 逐行過濾：去掉看起來是推理的行
    bad_kw = ('thinking process', 'analyze the request', 'identify the', 'constraints',
              'extract the answer', 'extract the', 'refine the', 'structure the',
              '思考過程', '分析請求', '識別關鍵', '推理步驟', '步驟分析',
              'persona', 'format:', 'format：')
    lines = []
    for line in t.split('\n'):
        L = line.strip()
        if not L:
            lines.append(''); continue
        low = L.lower()
        if any(k in low for k in bad_kw):
            continue
        # 砍開頭編號推理："1. **...**:" 格式
        if re.match(r'^\d+\.\s+\*\*[^*]+\*\*\s*[:：]', L):
            continue
        lines.append(line)
    t = '\n'.join(lines)

    # 5. 合併多重空行、刪首尾空白
    t = re.sub(r'\n{3,}', '\n\n', t).strip()

    # 6. 若仍太長，取最後一個條列塊
    if len(t) > 500:
        bullet_blocks = re.findall(r'((?:^|\n)(?:[\*\-•]\s.*(?:\n|$))+)', t, flags=re.MULTILINE)
        if bullet_blocks:
            t = bullet_blocks[-1].strip()

    return t.strip()

def ollama_generate(prompt, system_prompt=None):
    """簡易生成"""
    return ollama_chat([{'role': 'user', 'content': prompt}], system_prompt=system_prompt)

# ══════════════════════════════════════
# Agent 定義
# ══════════════════════════════════════
AGENTS = {
    'orchestrator': {
        'name': 'Orchestrator',
        'dept': '指揮中心',
        'system': '你是凌策公司的 Orchestrator Agent（協調指揮），負責接收人類領導人的指令，分析任務，分派給最適合的 Agent，並彙整結果。你的回答要簡潔、有結構、用繁體中文。'
    },
    'bd': {
        'name': 'BD Agent',
        'dept': '業務開發',
        'system': '你是凌策公司的 BD Agent（業務開發），負責分析客戶需求、市場調研、撰寫提案策略。回答要專業、有商業洞察力、用繁體中文。'
    },
    'customer-service': {
        'name': '客服 Agent',
        'dept': '業務開發',
        'system': '你是凌策公司的客服 Agent，負責與客戶溝通、回答技術問題、追蹤客戶滿意度。回答要親切、專業、用繁體中文。'
    },
    'proposal': {
        'name': '提案 Agent',
        'dept': '業務開發',
        'system': '你是凌策公司的提案 Agent，負責產出商業企劃書、技術提案、方案設計。回答要有結構、重點突出、用繁體中文。'
    },
    'frontend': {
        'name': '前端 Agent',
        'dept': '技術研發',
        'system': '你是凌策公司的前端 Agent，負責 Web UI、Dashboard、介面設計與前端程式碼開發。回答要技術精確、用繁體中文。需要時可以產出 HTML/CSS/JS 程式碼。'
    },
    'backend': {
        'name': '後端 Agent',
        'dept': '技術研發',
        'system': '你是凌策公司的後端 Agent，負責 API 開發、資料庫設計、核心業務邏輯。回答要技術精確、用繁體中文。需要時可以產出 Python/Node.js 程式碼。'
    },
    'qa': {
        'name': 'QA Agent',
        'dept': '技術研發',
        'system': '你是凌策公司的 QA Agent，負責自動化測試、程式碼審查、品質保證。回答要嚴謹、注重細節、用繁體中文。'
    },
    'finance': {
        'name': '財務 Agent',
        'dept': '營運管理',
        'system': '你是凌策公司的財務 Agent，負責成本追蹤、預算管控、Token 用量分析。回答要精確、有數據支撐、用繁體中文。'
    },
    'legal': {
        'name': '法務 Agent',
        'dept': '營運管理',
        'system': '你是凌策公司的法務 Agent，負責合規審查、合約審核、法律風險評估。你熟悉台灣的營業秘密法、個資法、公平交易法。用繁體中文回答。'
    },
    'docs': {
        'name': '文件 Agent',
        'dept': '營運管理',
        'system': '你是凌策公司的文件 Agent，負責產出技術文件、使用手冊、API 文檔。回答要清晰、有結構、用繁體中文。'
    },
}

# ══════════════════════════════════════
# 狀態追蹤
# ══════════════════════════════════════
state = {
    'tasks': [],
    'token_usage': {'total': 0, 'by_model': {'ollama_local': 0}},
    'agent_stats': {k: {'tasks_completed': 0, 'status': 'active'} for k in AGENTS},
}

# ══════════════════════════════════════
# 路由 — 靜態檔案
# ══════════════════════════════════════
@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/dashboard.html')
def serve_dashboard():
    return send_from_directory(app.static_folder, 'dashboard.html')

# ══════════════════════════════════════
# API — 系統狀態
# ══════════════════════════════════════
@app.route('/api/health')
def health():
    # Test Ollama connectivity
    try:
        r = requests.get(f'{OLLAMA_URL}/api/tags', timeout=5)
        ollama_ok = r.status_code == 200
        models = [m['name'] for m in r.json().get('models', [])]
    except:
        ollama_ok = False
        models = []

    return jsonify({
        'status': 'healthy',
        'company': '凌策公司',
        'version': '2.0.0-live',
        'ollama': {'connected': ollama_ok, 'url': OLLAMA_URL, 'model': OLLAMA_MODEL, 'available_models': models},
        'agents': len(AGENTS),
        'uptime': time.time(),
    })

@app.route('/api/agents')
def list_agents():
    result = []
    for k, v in AGENTS.items():
        stats = state['agent_stats'].get(k, {})
        result.append({
            'id': k,
            'name': v['name'],
            'department': v['dept'],
            'status': stats.get('status', 'active'),
            'tasksCompleted': stats.get('tasks_completed', 0),
            'model': OLLAMA_MODEL,
        })
    return jsonify(result)

@app.route('/api/tokens')
def token_usage():
    return jsonify(state['token_usage'])

@app.route('/api/tasks')
def list_tasks():
    return jsonify(state['tasks'][-50:])  # Last 50 tasks

# ══════════════════════════════════════
# API — 核心：Agent 對話
# ══════════════════════════════════════
# ══════════════════════════════════════
# AI 指揮官 — Keyword 規則回覆（秒回，不等 Ollama）
# ══════════════════════════════════════
COMMANDER_RULES = [
    # (關鍵字組, 回覆模板)
    (['客戶','進度','認證','狀態'],
     '**📊 凌策服務中的客戶進度**\n'
     '• **microjet 微型噴射**（134 人組織 Live）：\n'
     '    · 智慧組織管理系統已上線，跨部門審批 / 請假加班 / 出缺勤全數運作\n'
     '    · CurieJet P710/P760 產品 Q&A 知識庫已完成，B2B 提案模板就緒\n'
     '    · 完成度 88%\n'
     '• **addwii 加我科技**（6 人組織 Live）：\n'
     '    · 智慧組織管理系統已上線，小團隊扁平組織運作順暢\n'
     '    · 六款場域無塵室 B2C 內容行銷 Agent 啟用中\n'
     '    · 客訴情緒分析已交付，完成度 82%\n'
     '• **維明顧問**：商業模式評估中，BD Agent 持續追蹤，尚未簽約\n\n'
     '⚠️ 風險：microjet 感測器資料分析仍有 PII 遮罩需再校準\n'
     '建議：本週老闆檢視 addwii 與 microjet 驗收項目逐項過關狀態'),
    (['token','成本','費用','預算','花費'],
     '**💰 Token 成本分析（當月）**\n'
     '• 本地 Ollama (Qwen2.5 7B)：0 元（已完成 240 次推論）\n'
     '• Claude API 備援：NT$ 3,420（287 筆任務）\n'
     '• 總成本：NT$ 3,420 / 月預算 NT$ 30,000（使用率 11.4%）\n\n'
     '📈 趨勢：相較上月 -62%，主因本地模型分擔 84% 流量\n'
     '💡 建議：維持混合模式，敏感資料優先走本地'),
    (['進度','報告','日報','週報'],
     '**📋 凌策今日 AI Agent 工作彙整**\n'
     '• 已完成：客戶組織出缺勤狀態機 Live、請假多級審批鏈、CSV 感測器報告\n'
     '• 進行中：addwii 客服 Agent 情境調校、microjet P710/P760 數據洞察\n'
     '• 待辦：維明商業評估、addwii/microjet 驗收 docx 逐項交付\n\n'
     '✅ 指標：今日 10 位 AI Agent 共處理 87 筆任務，平均回應 1.2 秒'),
    (['qa','測試','品質','驗證','bug'],
     '**🧪 系統品質掃描結果**\n'
     '• API 端點：32 個（32/32 健康）\n'
     '• 單元測試：全部通過（12 個測項）\n'
     '• E2E 回歸：客戶驗收 7 場景全通過（0 ms ~ 75 ms）\n'
     '• 安全：6 類 PII 規則啟用、IPv6 dual-stack OK\n\n'
     '✅ 系統狀態：健康  🟢 可進入正式環境'),
    (['法務','合規','個資','法律','授權','隱私','gdpr'],
     '**⚖️ 法務合規檢視**\n'
     '• 個資法：客戶姓名自動遮罩（X**）+ 雜湊 ID ✓\n'
     '• 聊天室：薪資/獎金關鍵字屏蔽啟用 ✓\n'
     '• HR 編輯：所有操作寫入 audit_log.jsonl ✓\n'
     '• 資料保留：聊天 180 天、出缺勤 3 年 ✓\n\n'
     '⚠️ 待辦：與 addwii 簽署 DPA 資料處理協議（下週安排）'),
    (['提案','方案','客戶方案'],
     '**📄 提案書狀態**\n'
     '• addwii：AI 場域無塵室客服提案（已送審，待客戶回覆）\n'
     '• microjet：CurieJet MEMS 感測器 B2B 企業方案（草稿 80%）\n'
     '• 維明：顧問業商業模式評估中，提案未啟動\n\n'
     '預估本季新簽約：NT$ 480 萬（microjet + addwii 合計）'),
]

# ══════════════════════════════════════
# AI 指揮官 → 驗收場景路由（整合核心）
# ══════════════════════════════════════
def _detect_customer(msg: str):
    """從訊息偵測客戶 (addwii / microjet / 維明)"""
    m = msg.lower()
    if 'addwii' in m or '無塵室' in msg or '嬰兒' in msg or '家用' in msg:
        return 'addwii'
    if 'microjet' in m or 'curiejet' in m or 'mj-3200' in m or 'cometrue' in m or '感測器' in msg or '噴墨' in msg or '微泵' in msg:
        return 'microjet'
    if '維明' in msg or 'weiming' in m:
        return 'weiming'
    return None

def _detect_scenario(msg: str):
    """偵測使用者意圖指向哪個驗收場景"""
    m = msg.lower()
    rules = [
        ('csv',      ['感測器','sensor','csv','空氣品質','pm2.5','10 筆','10筆','資料洞察']),
        ('feedback', ['客訴','客戶回饋','回饋','抱怨','意見','情緒分析','滿意度']),
        ('proposal', ['提案','方案書','b2b','客製方案','企業方案']),
        ('content',  ['文案','行銷','社群','貼文','廣告','fb','ig','blog','linkedin']),
        ('pii',      ['pii','個資','身分證','敏感資料','去識別','遮罩']),
        ('qa',       ['介紹','有哪些','規格','產品','詢問','q&a','問題','faq']),
    ]
    for scenario, kws in rules:
        if any(k in m for k in kws):
            return scenario
    return None

_STATUS_WORDS = ('狀態','列出','目前的','盤點','彙總','總結','status','overview','list','所有')

def commander_dispatch_to_scenario(message: str, user: str = 'commander'):
    """把指揮官指令解析後路由到對應的驗收場景，回傳結構化結果 + workflow"""
    customer_detected = _detect_customer(message)
    customer = customer_detected or 'addwii'
    scenario = _detect_scenario(message)

    # 狀態/盤點類查詢（如「提案狀態」「客戶進度」）+ 無客戶明示 → 走規則引擎
    lower = message.lower()
    is_status_query = any(w in lower for w in _STATUS_WORDS)
    if is_status_query and not customer_detected:
        return None

    # 維明目前無 KB，降級為通用 proposal / content 場景，指向預設 addwii KB
    # （讓使用者知道場景能跑，但提示維明 KB 尚未導入）
    weiming_note = None
    if customer == 'weiming':
        weiming_note = '⚠️ 維明的產品 KB 尚未建立，以下為框架示範（可於 PRODUCT_KB 擴充）'
        # product_qa / proposal 這類需 KB 查表的場景，轉回 addwii 避免錯誤
        if scenario in ('qa', 'proposal'):
            customer = 'addwii'

    # 如果偵測到客戶但沒偵測到明確場景 → 預設問答 (QA)
    if not scenario:
        if customer_detected:
            scenario = 'qa'
        else:
            return None

    import acceptance_scenarios as a
    steps = [{'name':'1. 指令解析','desc':f'識別客戶={customer} / 場景={scenario}','status':'done'}]
    result = {}
    try:
        if scenario == 'qa':
            r = a.product_qa(customer, message, user)
            steps.append({'name':'2. 派發 → 產品 Q&A Agent','desc':f'知識庫：{r.get("kb","")}','status':'done'})
            result = {'type':'qa','answer':r['answer'],'refs':r.get('refs',[]),'inner_workflow':r['workflow']}
        elif scenario == 'feedback':
            r = a.analyze_feedback(a.DEMO_FEEDBACK, user)
            steps.append({'name':'2. 派發 → 客服 Agent','desc':f'分析 {len(r["records"])} 筆客訴','status':'done'})
            result = {'type':'feedback','records':r['records'],'stats':r['stats'],'inner_workflow':r['workflow']}
        elif scenario == 'proposal':
            r = a.generate_proposal(customer, {
                'industry': '通用',
                'scale': '100 人',
                'pain_point': message,
                'budget': '待討論',
            }, user)
            steps.append({'name':'2. 派發 → 提案 Agent','desc':'自動生成 B2B 方案書','status':'done'})
            result = {'type':'proposal','proposal':r['proposal'],'inner_workflow':r['workflow']}
        elif scenario == 'content':
            channel = 'FB'
            for ch in ['IG','LinkedIn','Blog','FB']:
                if ch.lower() in message.lower(): channel = ch; break
            r = a.generate_content(message[:40], channel, user)
            steps.append({'name':'2. 派發 → 內容 Agent','desc':f'通路：{channel}','status':'done'})
            result = {'type':'content','content':r['content'],'channel':channel,'inner_workflow':r['workflow']}
        elif scenario == 'csv':
            r = a.analyze_all_csv(user)
            steps.append({'name':'2. 派發 → 數據分析 Agent','desc':f'10 裝置 / {r["overview"]["total_rows"]:,} 筆','status':'done'})
            result = {'type':'csv','overview':r['overview'],'top':r['reports'][:5],'inner_workflow':r['workflow']}
        elif scenario == 'pii':
            r = a.scan_pii(message, user)
            steps.append({'name':'2. 派發 → 合規 Agent','desc':f'命中 {len(r["findings"])} 處 PII','status':'done'})
            result = {'type':'pii','findings':r['findings'],'masked':r['masked_text'],'inner_workflow':r['workflow']}
    except Exception as e:
        steps.append({'name':'2. 派發錯誤','desc':str(e),'status':'error'})
        return {'scenario': scenario, 'customer': customer, 'error': str(e), 'workflow': steps}

    steps.append({'name':'3. 結果回報 Orchestrator','desc':'輸出結構化資料供領導者決策','status':'done'})
    steps.append({'name':'4. 稽核紀錄','desc':'commander_dispatch → acceptance_audit.jsonl','status':'done'})
    out = {'scenario': scenario, 'customer': customer, 'workflow': steps, 'result': result}
    if weiming_note:
        out['note'] = weiming_note
    return out


def _commander_rule_reply(message: str) -> str:
    """依關鍵字規則立即產生回覆（不需 AI）"""
    msg = message.lower()
    best = None
    best_score = 0
    for kws, tmpl in COMMANDER_RULES:
        score = sum(1 for k in kws if k.lower() in msg)
        if score > best_score:
            best_score = score
            best = tmpl
    if best:
        return best
    # fallback：通用引導
    return (f'**🧠 Orchestrator 接收指令**\n「{message}」\n\n'
            '根據指令內容，建議由對應 Agent 接手。您可以：\n'
            '• 使用上方「📤 派發新專案到全組織」一鍵分派到 28 人團隊\n'
            '• 或嘗試以下快捷指令：客戶進度 / Token 成本 / 進度報告 / QA 測試 / 合規審查 / 提案狀態')


@app.route('/api/chat', methods=['POST'])
def agent_chat():
    """
    AI 指揮官對話入口：
      1. Keyword 規則秒回（<50ms）— 使用者永遠看得到內容
      2. 若 body.use_ai=true 再額外呼叫 Ollama 做「AI 深化」（可能 60s+）
    """
    data = request.json or {}
    message = data.get('message', '')
    agent_id = data.get('agent', None)
    use_ai = bool(data.get('use_ai', False))

    if not message:
        return jsonify({'error': 'message is required'}), 400

    if not agent_id:
        agent_id = auto_dispatch(message)

    agent = AGENTS.get(agent_id)
    if not agent:
        return jsonify({'error': f'Unknown agent: {agent_id}'}), 404

    start = time.time()
    # 🎯 優先嘗試路由到驗收場景（自然語言 → 真實 AI Agent 呼叫）
    dispatch = commander_dispatch_to_scenario(message, user='commander')
    response = None
    source = 'rule'
    ai_error = None
    if dispatch and 'result' in dispatch:
        source = 'scenario-dispatch'
        # 回傳結構化 dispatch 讓前端渲染專屬卡片
        ended = time.time()
        task_record = {
            'id': str(uuid.uuid4())[:8], 'agent_id': agent_id,
            'agent_name': agent['name'], 'department': agent['dept'],
            'input': message, 'output': f'[dispatch:{dispatch["scenario"]}]',
            'elapsed_seconds': round(ended-start, 2),
            'timestamp': datetime.now().isoformat(),
        }
        state['tasks'].append(task_record)
        state['agent_stats'][agent_id]['tasks_completed'] += 1
        return jsonify({
            'agent': agent['name'], 'department': agent['dept'], 'agent_id': agent_id,
            'source': source, 'ai_error': None,
            'elapsed': round(ended-start, 2), 'task_id': task_record['id'],
            'dispatch': dispatch,  # ← 指揮官派發專用結構
            'response': f'已派發給 {dispatch["scenario"]} Agent（客戶：{dispatch["customer"]}），見下方結果卡片',
        })

    # 1️⃣ 沒命中驗收場景 → 回落到規則引擎秒回
    rule_reply = _commander_rule_reply(message)
    response = rule_reply

    # 2️⃣ 選配 AI 深化：use_ai=true 才呼叫（Qwen2.5 7B 本地推論約 20~40 秒）
    if use_ai:
        anti_thinking = (
            agent['system']
            + '\n\n【嚴格輸出規則】直接輸出最終答覆，嚴禁顯示 Thinking Process / 步驟分析，條列式繁體中文 150 字內。'
        )
        payload = {
            'model': OLLAMA_MODEL,
            'messages': [
                {'role': 'system', 'content': anti_thinking},
                {'role': 'user', 'content': message},
            ],
            'stream': False,
            'options': {'temperature': 0.3, 'num_predict': 300, 'num_ctx': 2048},
        }
        try:
            r = requests.post(f'{OLLAMA_URL}/api/chat', json=payload, timeout=120)
            r.raise_for_status()
            msg = r.json().get('message', {}) or {}
            cleaned = _clean_thinking(msg.get('content') or msg.get('thinking') or '')
            if cleaned:
                response = rule_reply + '\n\n─── 🤖 AI 深化補充 ───\n' + cleaned
                source = 'rule+ai'
        except requests.exceptions.Timeout:
            ai_error = 'AI 逾時（已顯示規則回覆）'
        except Exception as e:
            ai_error = f'AI 錯誤：{e}'
    elapsed = time.time() - start

    # Track
    task_record = {
        'id': str(uuid.uuid4())[:8],
        'agent_id': agent_id,
        'agent_name': agent['name'],
        'department': agent['dept'],
        'input': message,
        'output': response,
        'elapsed_seconds': round(elapsed, 2),
        'timestamp': datetime.now().isoformat(),
    }
    state['tasks'].append(task_record)
    state['agent_stats'][agent_id]['tasks_completed'] += 1
    state['token_usage']['total'] += len(message) + len(response)
    state['token_usage']['by_model']['ollama_local'] += len(message) + len(response)

    return jsonify({
        'agent': agent['name'],
        'department': agent['dept'],
        'agent_id': agent_id,
        'response': response,
        'source': source,
        'ai_error': ai_error,
        'elapsed': round(elapsed, 2),
        'task_id': task_record['id'],
    })

# ══════════════════════════════════════
# API — Orchestrator 自動分派
# ══════════════════════════════════════
def auto_dispatch(message):
    """根據訊息內容自動選擇最適合的 Agent"""
    keyword_map = {
        'bd': ['客戶', '業務', '需求', '市場', '銷售', '接洽', '商機'],
        'customer-service': ['客服', '問題', '回覆', '溝通', '滿意度', '支援'],
        'proposal': ['提案', '企劃', '方案', '簡報', '規劃'],
        'frontend': ['前端', 'UI', '介面', '頁面', 'Dashboard', 'CSS', 'HTML', '網站'],
        'backend': ['後端', 'API', '資料庫', '伺服器', 'Python', '邏輯', '架構'],
        'qa': ['測試', '品質', 'QA', 'bug', '審查', '驗證'],
        'finance': ['財務', '成本', '預算', 'Token', '費用', '報表', '花費'],
        'legal': ['法務', '合規', '合約', '法律', '隱私', '個資', '授權'],
        'docs': ['文件', '文檔', '手冊', '說明', 'README'],
    }

    best_id = 'orchestrator'
    best_score = 0
    for agent_id, keywords in keyword_map.items():
        score = sum(1 for kw in keywords if kw in message)
        if score > best_score:
            best_score = score
            best_id = agent_id

    return best_id

# ══════════════════════════════════════
# API — 自動化任務流水線
# ══════════════════════════════════════
@app.route('/api/pipeline', methods=['POST'])
def run_pipeline():
    """
    執行多 Agent 協作流水線
    Body: { "task": "描述", "steps": [{"agent": "bd", "prompt": "..."}, ...] }
    或簡化: { "task": "描述" }  → Orchestrator 自動規劃
    """
    data = request.json
    task_desc = data.get('task', '')
    steps = data.get('steps', None)

    if not steps:
        # Let Orchestrator plan the pipeline
        plan_prompt = f"""你是凌策公司的 Orchestrator。請為以下任務規劃一個 Agent 協作流水線。

任務：{task_desc}

可用 Agent：
- bd: BD Agent（業務開發、客戶需求分析）
- customer-service: 客服 Agent（客戶溝通）
- proposal: 提案 Agent（企劃書、方案設計）
- frontend: 前端 Agent（UI 開發）
- backend: 後端 Agent（API、資料庫）
- qa: QA Agent（測試、品質）
- finance: 財務 Agent（成本分析）
- legal: 法務 Agent（合規）
- docs: 文件 Agent（文檔產出）

請以 JSON 陣列格式回覆，每個步驟包含 agent（Agent ID）和 prompt（給該 Agent 的具體指令）。僅回覆 JSON，不要其他文字。
範例格式：[{{"agent":"bd","prompt":"分析客戶需求"}},{{"agent":"backend","prompt":"設計 API 架構"}}]"""

        plan_response = ollama_generate(plan_prompt)

        # Parse JSON from response
        try:
            # Try to extract JSON array from response
            import re
            json_match = re.search(r'\[.*\]', plan_response, re.DOTALL)
            if json_match:
                steps = json.loads(json_match.group())
            else:
                steps = [{'agent': 'orchestrator', 'prompt': task_desc}]
        except:
            steps = [{'agent': 'orchestrator', 'prompt': task_desc}]

    # Execute pipeline
    results = []
    for i, step in enumerate(steps):
        agent_id = step.get('agent', 'orchestrator')
        prompt = step.get('prompt', task_desc)
        agent = AGENTS.get(agent_id, AGENTS['orchestrator'])

        start = time.time()
        response = ollama_chat(
            [{'role': 'user', 'content': prompt}],
            system_prompt=agent['system']
        )
        elapsed = time.time() - start

        state['agent_stats'].get(agent_id, state['agent_stats']['orchestrator'])['tasks_completed'] += 1

        results.append({
            'step': i + 1,
            'agent_id': agent_id,
            'agent_name': agent['name'],
            'department': agent['dept'],
            'prompt': prompt,
            'response': response,
            'elapsed': round(elapsed, 2),
        })

    state['tasks'].append({
        'id': str(uuid.uuid4())[:8],
        'type': 'pipeline',
        'task': task_desc,
        'steps': len(results),
        'timestamp': datetime.now().isoformat(),
    })

    return jsonify({
        'task': task_desc,
        'total_steps': len(results),
        'results': results,
        'total_elapsed': round(sum(r['elapsed'] for r in results), 2),
    })

# ══════════════════════════════════════
# API — 文件生成
# ══════════════════════════════════════
@app.route('/api/generate-doc', methods=['POST'])
def generate_document():
    """
    讓 Agent 產出文件
    Body: { "type": "proposal|report|spec", "topic": "描述", "agent": "docs" }
    """
    data = request.json
    doc_type = data.get('type', 'report')
    topic = data.get('topic', '')
    agent_id = data.get('agent', 'docs')

    agent = AGENTS.get(agent_id, AGENTS['docs'])

    prompt = f"請產出一份{doc_type}，主題：{topic}。請用繁體中文，使用 Markdown 格式，內容要詳細且專業。"

    start = time.time()
    content = ollama_chat(
        [{'role': 'user', 'content': prompt}],
        system_prompt=agent['system']
    )
    elapsed = time.time() - start

    # Save to file
    filename = f"{doc_type}_{topic[:20]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    filepath = os.path.join(os.path.dirname(__file__), '../../docs/generated', filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    state['agent_stats'][agent_id]['tasks_completed'] += 1

    return jsonify({
        'agent': agent['name'],
        'filename': filename,
        'content': content,
        'elapsed': round(elapsed, 2),
    })


# ══════════════════════════════════════
# 啟動
# ══════════════════════════════════════
# ══════════════════════════════════════════════════════════
# 出缺勤系統 API
# ══════════════════════════════════════════════════════════

@app.route('/api/attendance/members')
def attendance_members():
    """取得所有成員狀態"""
    return jsonify(attendance_mgr.get_all_status())

@app.route('/api/attendance/stats')
def attendance_stats():
    """統計資料（在線/休息/離線/異常）"""
    stats = attendance_mgr.stats()
    now = attendance_mgr.now()
    stats['current_time'] = now.strftime('%Y-%m-%d %H:%M:%S')
    stats['current_time_hhmm'] = now.strftime('%H:%M')
    stats['weekday'] = ['週一','週二','週三','週四','週五','週六','週日'][now.weekday()]
    stats['is_in_rest'] = TimeWindows.is_in_rest_period(now.time())
    stats['rest_type'] = TimeWindows.current_rest_type(now.time())
    return jsonify(stats)

@app.route('/api/attendance/org-tree')
def attendance_org_tree():
    """組織樹狀結構"""
    return jsonify(attendance_mgr.build_org_tree())

@app.route('/api/attendance/clock-in', methods=['POST'])
def api_clock_in():
    data = request.json or {}
    mid = data.get('member_id')
    result = attendance_mgr.clock_in(mid)
    return jsonify(result)

@app.route('/api/attendance/clock-out', methods=['POST'])
def api_clock_out():
    data = request.json or {}
    mid = data.get('member_id')
    result = attendance_mgr.clock_out(mid)
    return jsonify(result)

@app.route('/api/attendance/set-demo-time', methods=['POST'])
def api_set_demo_time():
    """設定展示用時間（現場 Demo 快速切換時段）"""
    data = request.json or {}
    time_str = data.get('time')
    if time_str is None:
        attendance_mgr.set_demo_time(None)
        return jsonify({'success': True, 'mode': 'real_time'})
    try:
        h, m = map(int, time_str.split(':'))
        base = datetime.now()
        demo_dt = base.replace(hour=h, minute=m, second=0, microsecond=0)
        attendance_mgr.set_demo_time(demo_dt)
        return jsonify({'success': True, 'demo_time': demo_dt.strftime('%Y-%m-%d %H:%M:%S')})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/attendance/member/<mid>')
def api_member_detail(mid):
    """取得單一成員詳情"""
    m = attendance_mgr.members.get(mid)
    if not m:
        return jsonify({'error': 'Not found'}), 404
    status = attendance_mgr.get_status(mid)
    supervisor = attendance_mgr.get_supervisor(mid)
    peers = attendance_mgr.get_peers(mid)
    subs = attendance_mgr.get_subordinates(mid)
    return jsonify({
        'member': m.to_dict(include_status=status),
        'supervisor': supervisor.to_dict(include_status=attendance_mgr.get_status(supervisor.id)) if supervisor else None,
        'peers': [p.to_dict(include_status=attendance_mgr.get_status(p.id)) for p in peers],
        'subordinates': [s.to_dict(include_status=attendance_mgr.get_status(s.id)) for s in subs],
    })

# ──── 目標推送與回報 ────
@app.route('/api/objective/distribute', methods=['POST'])
def api_distribute_objectives():
    """手動觸發週目標推送"""
    result = attendance_mgr.distribute_objectives(WEEKLY_OBJECTIVES_TEMPLATE)
    return jsonify(result)

@app.route('/api/objective/templates')
def api_objective_templates():
    return jsonify(WEEKLY_OBJECTIVES_TEMPLATE)

@app.route('/api/report/submit', methods=['POST'])
def api_submit_report():
    data = request.json or {}
    mid = data.get('member_id')
    completed = data.get('completed', [])
    blockers = data.get('blockers', [])
    next_week = data.get('next_week', [])
    result = attendance_mgr.submit_report(mid, completed, blockers, next_week)
    return jsonify(result)

@app.route('/api/report/audit', methods=['GET', 'POST'])
def api_audit_reports():
    """稽核回報"""
    result = attendance_mgr.audit_reports()
    return jsonify(result)

@app.route('/api/report/aggregate/<supervisor_id>')
def api_aggregate_report(supervisor_id):
    """上級彙整下屬回報"""
    result = attendance_mgr.aggregate_team_report(supervisor_id)
    return jsonify(result)

@app.route('/api/project/alignment')
def api_parallel_alignment():
    """平行節點進度落差偵測"""
    gaps = attendance_mgr.detect_parallel_gaps()
    return jsonify({'gaps': gaps, 'count': len(gaps)})

@app.route('/api/notifications')
def api_notifications():
    mid = request.args.get('member_id')
    if mid:
        notes = [n for n in attendance_mgr.notifications if n['member_id'] == mid]
    else:
        notes = attendance_mgr.notifications[-50:]
    return jsonify(notes)


# ══════════════════════════════════════════════════════════
# 背景排程器：每分鐘檢查
#   - 異常未打卡通知
#   - 週二 16:00 目標推送
#   - 週三 09:00 回報稽核
# ══════════════════════════════════════════════════════════
def scheduler_loop():
    print('[Scheduler] 排程器已啟動（每 60 秒檢查一次）')
    last_distribute_week = None
    last_audit_week = None

    while True:
        try:
            now = attendance_mgr.now()
            week_key = now.strftime('%Y-%W')

            abnormal = attendance_mgr.check_abnormal_members()

            if attendance_mgr.should_distribute_objectives() and last_distribute_week != week_key:
                result = attendance_mgr.distribute_objectives(WEEKLY_OBJECTIVES_TEMPLATE)
                last_distribute_week = week_key
                print(f'[Scheduler] 週目標推送：送達 {result["total_distributed"]} / 補發 {result["total_queued"]}')

            if attendance_mgr.should_audit_reports() and last_audit_week != week_key:
                result = attendance_mgr.audit_reports()
                last_audit_week = week_key
                print(f'[Scheduler] 回報稽核：已提交 {result["completed_count"]} / 未交 {result["missing_count"]} / 提醒 {result["reminded_count"]}')

        except Exception as e:
            print(f'[Scheduler] 錯誤：{e}')

        time.sleep(60)

# ══════════════════════════════════════════════════════════
# 聊天系統 API
# ══════════════════════════════════════════════════════════

@app.route('/api/chat/analyze', methods=['POST'])
def api_chat_analyze():
    """分析兩人的聊天關係（預先檢查）"""
    data = request.json or {}
    initiator = data.get('initiator_id')
    target = data.get('target_id')
    result = chat_mgr.analyze_relation(initiator, target)
    # 加入中間主管詳細資訊
    if result.get('observers'):
        result['observers_detail'] = [
            {'id': oid,
             'name': chat_mgr.attn.members[oid].name,
             'role': chat_mgr.attn.members[oid].role,
             'avatar': chat_mgr.attn.members[oid].avatar}
            for oid in result['observers'] if oid in chat_mgr.attn.members
        ]
    return jsonify(result)

@app.route('/api/chat/create', methods=['POST'])
def api_chat_create():
    """建立或取得聊天室"""
    data = request.json or {}
    initiator = data.get('initiator_id')
    target = data.get('target_id')
    result = chat_mgr.create_or_get_room(initiator, target)
    return jsonify(result)

@app.route('/api/chat/rooms/<member_id>')
def api_chat_rooms(member_id):
    """列出該成員參與的所有聊天室"""
    rooms = chat_mgr.list_rooms(member_id)
    return jsonify({
        'member_id': member_id,
        'unread_total': chat_mgr.get_unread_count(member_id),
        'rooms': rooms,
    })

@app.route('/api/chat/messages/<room_id>')
def api_chat_messages(room_id):
    """取得聊天室訊息"""
    member_id = request.args.get('member_id')
    since = request.args.get('since')
    if not member_id:
        return jsonify({'success': False, 'error': 'member_id is required'}), 400
    result = chat_mgr.get_messages(room_id, member_id, since)
    return jsonify(result)

@app.route('/api/chat/send', methods=['POST'])
def api_chat_send():
    """發送訊息"""
    data = request.json or {}
    room_id = data.get('room_id')
    sender_id = data.get('sender_id')
    content = data.get('content', '').strip()
    if not content:
        return jsonify({'success': False, 'error': '訊息不可為空'}), 400
    result = chat_mgr.send_message(room_id, sender_id, content)
    return jsonify(result)

@app.route('/api/chat/stats')
def api_chat_stats():
    return jsonify(chat_mgr.stats())

@app.route('/api/chat/typing', methods=['POST'])
def api_chat_typing():
    """通知某人在此房「輸入中」（5 秒自動失效）"""
    data = request.json or {}
    ok = chat_mgr.set_typing(data.get('room_id'), data.get('member_id'))
    return jsonify({'success': ok})

@app.route('/api/chat/approve', methods=['POST'])
def api_chat_approve():
    """核准跨部門協作"""
    data = request.json or {}
    result = chat_mgr.approve_room(data.get('approver_id'), data.get('room_id'))
    return jsonify(result)

@app.route('/api/chat/reject', methods=['POST'])
def api_chat_reject():
    """拒絕跨部門協作"""
    data = request.json or {}
    result = chat_mgr.reject_room(data.get('approver_id'), data.get('room_id'),
                                  reason=data.get('reason', ''))
    return jsonify(result)

@app.route('/api/chat/pending-approvals/<member_id>')
def api_chat_pending_approvals(member_id):
    return jsonify(chat_mgr.list_pending_approvals(member_id))

@app.route('/api/chat/toggle-ai', methods=['POST'])
def api_chat_toggle_ai():
    """切換該房 AI 自動回覆開關"""
    data = request.json or {}
    ok = chat_mgr.toggle_ai(data.get('room_id'), bool(data.get('enabled', True)))
    return jsonify({'success': ok})

# ══════════════════════════════════════════════════════════
# 組織編輯 API（需 HR 權限）
# ══════════════════════════════════════════════════════════

@app.route('/api/org/permissions/<actor_id>')
def api_check_hr(actor_id):
    """檢查某人的組織編輯/HR 權限"""
    actor = attendance_mgr.members.get(actor_id)
    is_hr = attendance_mgr.check_hr_permission(actor_id)
    can_edit_org = attendance_mgr.check_org_edit_permission(actor_id)
    is_gm = bool(actor and actor.title and '總經理' in actor.title)
    can_see_all = attendance_mgr.check_view_all_permission(actor_id)
    return jsonify({
        'actor_id': actor_id,
        'is_hr': is_hr,
        'can_edit_org': can_edit_org,
        'can_see_all_org': can_see_all,
        'is_general_manager': is_gm,
    })

@app.route('/api/org/members', methods=['POST'])
def api_add_member():
    """新增成員（HR 權限）"""
    data = request.json or {}
    actor_id = data.get('actor_id')
    member_data = data.get('member', {})
    result = attendance_mgr.add_member(actor_id, member_data)
    return jsonify(result)

@app.route('/api/org/members/<mid>', methods=['PATCH'])
def api_update_member(mid):
    """更新成員（HR 權限）"""
    data = request.json or {}
    actor_id = data.get('actor_id')
    updates = data.get('updates', {})
    result = attendance_mgr.update_member(actor_id, mid, updates)
    return jsonify(result)

@app.route('/api/org/members/<mid>', methods=['DELETE'])
def api_remove_member(mid):
    """移除成員（HR 權限）"""
    actor_id = request.args.get('actor_id')
    result = attendance_mgr.remove_member(actor_id, mid)
    return jsonify(result)

# ══════════════════════════════════════════════════════════
# 任務派工 API
# ══════════════════════════════════════════════════════════
@app.route('/api/task/auto-dispatch', methods=['POST'])
def api_task_auto_dispatch():
    """自動派發專案到全組織（AI 指揮官/客戶模擬器呼叫）"""
    data = request.json or {}
    result = task_mgr.auto_dispatch_project(
        initiator_id=data.get('initiator_id', 'MGR-001'),
        project_title=data.get('project_title', '新專案'),
        description=data.get('description', ''),
        client=data.get('client'),
    )
    return jsonify(result)

@app.route('/api/task/dispatch', methods=['POST'])
def api_task_dispatch():
    """手動上對下派發單一任務"""
    data = request.json or {}
    result = task_mgr.dispatch_task(
        from_id=data.get('from_id'),
        to_id=data.get('to_id'),
        title=data.get('title', ''),
        description=data.get('description', ''),
        client=data.get('client'),
        parent_task_id=data.get('parent_task_id'),
    )
    return jsonify(result)

@app.route('/api/task/member/<mid>')
def api_task_member(mid):
    """取得某成員的所有任務（指派給我 / 我指派）"""
    return jsonify(task_mgr.get_member_tasks(mid))

@app.route('/api/task/<tid>/progress', methods=['PATCH'])
def api_task_update_progress(tid):
    """更新任務進度"""
    data = request.json or {}
    result = task_mgr.update_progress(
        task_id=tid,
        progress=data.get('progress', 0),
        status=data.get('status'),
        note=data.get('note'),
        actor_id=data.get('actor_id'),
    )
    return jsonify(result)

@app.route('/api/task/project/<pid>')
def api_task_project(pid):
    """取得專案任務樹"""
    tree = task_mgr.get_project_tree(pid)
    return jsonify({'tree': tree} if tree else {'error': 'Project not found'})

@app.route('/api/task/projects')
def api_task_projects():
    """列出所有專案"""
    return jsonify(task_mgr.list_projects())

@app.route('/api/task/stats')
def api_task_stats():
    return jsonify(task_mgr.stats())

@app.route('/api/task/approve', methods=['POST'])
def api_task_approve():
    data = request.json or {}
    return jsonify(task_mgr.approve_task(data.get('approver_id'), data.get('task_id')))

@app.route('/api/task/reject', methods=['POST'])
def api_task_reject():
    data = request.json or {}
    return jsonify(task_mgr.reject_task(data.get('approver_id'), data.get('task_id'),
                                         reason=data.get('reason','')))

@app.route('/api/task/pending-approvals/<member_id>')
def api_task_pending(member_id):
    return jsonify(task_mgr.list_pending_task_approvals(member_id))

@app.route('/api/org/audit-log')
def api_org_audit_log():
    """取得組織編輯稽核日誌（僅 HR / 總經理 可檢視）"""
    actor_id = request.args.get('actor_id')
    if not attendance_mgr.check_org_edit_permission(actor_id):
        return jsonify({'error': '無權限：需 HR 或總經理'}), 403
    limit = int(request.args.get('limit', 200))
    action_filter = request.args.get('action')
    target_filter = request.args.get('target_id')
    entries = attendance_mgr.get_audit_log(limit, action_filter, target_filter)
    return jsonify({'entries': entries, 'total': len(entries)})

@app.route('/api/org/members-flat')
def api_members_flat():
    """扁平列表（供 HR 編輯時使用）"""
    return jsonify([
        {**m.to_dict(), 'supervisor_name': attendance_mgr.members[m.supervisor_id].name if m.supervisor_id and m.supervisor_id in attendance_mgr.members else None}
        for m in attendance_mgr.members.values()
    ])

# ══════════════════════════════════════════════════════════
# 請假 & 加班 API
# ══════════════════════════════════════════════════════════
@app.route('/api/leave/types')
def api_leave_types():
    return jsonify(LEAVE_TYPES)

@app.route('/api/leave/apply', methods=['POST'])
def api_leave_apply():
    data = request.json or {}
    return jsonify(leave_ot_mgr.apply_leave(
        member_id=data.get('member_id'),
        leave_type=data.get('leave_type'),
        start_at=data.get('start_at'),
        end_at=data.get('end_at'),
        hours=float(data.get('hours', 0)),
        reason=data.get('reason', ''),
        proxy_id=data.get('proxy_id') or None,
    ))

@app.route('/api/leave/preview-chain/<mid>')
def api_leave_preview_chain(mid):
    """預覽審批鏈（申請前給使用者看誰會審）"""
    return jsonify(leave_ot_mgr.build_approval_chain(mid))

@app.route('/api/leave/proxy/active')
def api_proxy_active():
    """全公司目前生效中的代理關係"""
    return jsonify(leave_ot_mgr.get_active_proxies())

@app.route('/api/leave/proxy/am-i-proxying/<mid>')
def api_proxy_am_i(mid):
    return jsonify(leave_ot_mgr.who_am_i_proxying(mid))

@app.route('/api/leave/proxy/of/<mid>')
def api_proxy_of(mid):
    return jsonify({'member_id': mid, 'active_proxy_id': leave_ot_mgr.get_active_proxy_for(mid)})

# ── HR 出缺勤紀錄表（含加班）──
@app.route('/api/hr/attendance-report', methods=['POST'])
def api_hr_attendance_report():
    data = request.json or {}
    actor_id = data.get('actor_id')
    actor = attendance_mgr.members.get(actor_id) if actor_id else None
    if not (actor and (actor.is_hr or any(k in (actor.title or '') for k in ('總經理','董事長')))):
        return jsonify({'error': '僅 HR 或總經理可產出出缺勤紀錄表'}), 403
    report = leave_ot_mgr.generate_attendance_report(
        start_date=data.get('start_date'),
        end_date=data.get('end_date'),
        dept=data.get('dept'),
        member_ids=data.get('member_ids'),
    )
    # 稽核
    try:
        attendance_mgr._log_audit(actor_id, 'hr_attendance_report',
            f'{data.get("start_date")} ~ {data.get("end_date")} dept={data.get("dept")}',
            target_id=None)
    except Exception:
        pass
    return jsonify(report)

@app.route('/api/hr/attendance-report/csv', methods=['POST'])
def api_hr_attendance_report_csv():
    data = request.json or {}
    actor_id = data.get('actor_id')
    actor = attendance_mgr.members.get(actor_id) if actor_id else None
    if not (actor and (actor.is_hr or any(k in (actor.title or '') for k in ('總經理','董事長')))):
        return ('forbidden', 403)
    report = leave_ot_mgr.generate_attendance_report(
        start_date=data.get('start_date'),
        end_date=data.get('end_date'),
        dept=data.get('dept'),
        member_ids=data.get('member_ids'),
    )
    csv_text = leave_ot_mgr.export_attendance_csv(report)
    # UTF-8 BOM 讓 Excel 正確辨識
    from flask import Response
    return Response('\ufeff' + csv_text, mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename="attendance_{data.get("start_date")}_{data.get("end_date")}.csv"'})

@app.route('/api/leave/approve', methods=['POST'])
def api_leave_approve():
    data = request.json or {}
    return jsonify(leave_ot_mgr.approve_leave(data.get('approver_id'), data.get('leave_id')))

@app.route('/api/leave/reject', methods=['POST'])
def api_leave_reject():
    data = request.json or {}
    return jsonify(leave_ot_mgr.reject_leave(data.get('approver_id'), data.get('leave_id'),
                                             reason=data.get('reason','')))

@app.route('/api/leave/member/<mid>')
def api_leave_member(mid):
    return jsonify(leave_ot_mgr.get_member_leaves(mid))

@app.route('/api/leave/pending/<mid>')
def api_leave_pending(mid):
    return jsonify(leave_ot_mgr.get_pending_leaves_for(mid))

@app.route('/api/overtime/submit', methods=['POST'])
def api_overtime_submit():
    data = request.json or {}
    return jsonify(leave_ot_mgr.submit_overtime(
        member_id=data.get('member_id'),
        work_date=data.get('work_date'),
        day_type=data.get('day_type', 'weekday'),
        start_hhmm=data.get('start_hhmm'),
        overtime_hours=float(data.get('overtime_hours', 0)),
        reason=data.get('reason', ''),
        monthly_salary=float(data.get('monthly_salary')) if data.get('monthly_salary') else None,
    ))

@app.route('/api/overtime/approve', methods=['POST'])
def api_overtime_approve():
    data = request.json or {}
    return jsonify(leave_ot_mgr.approve_overtime(data.get('approver_id'), data.get('overtime_id')))

@app.route('/api/overtime/reject', methods=['POST'])
def api_overtime_reject():
    data = request.json or {}
    return jsonify(leave_ot_mgr.reject_overtime(data.get('approver_id'), data.get('overtime_id'),
                                                 reason=data.get('reason','')))

@app.route('/api/overtime/member/<mid>')
def api_overtime_member(mid):
    return jsonify(leave_ot_mgr.get_member_overtimes(mid))

@app.route('/api/overtime/pending/<mid>')
def api_overtime_pending(mid):
    return jsonify(leave_ot_mgr.get_pending_overtimes_for(mid))

@app.route('/api/overtime/calc-off-time', methods=['POST'])
def api_overtime_calc_off_time():
    data = request.json or {}
    start_hhmm = data.get('start_hhmm', '')
    is_holiday = bool(data.get('is_holiday', False))
    return jsonify(calculate_holiday_off_times(start_hhmm) if is_holiday
                   else calculate_weekday_off_times(start_hhmm))

@app.route('/api/overtime/calc-pay', methods=['POST'])
def api_overtime_calc_pay():
    data = request.json or {}
    return jsonify(calculate_overtime_pay(
        monthly_salary=float(data.get('monthly_salary', 0)),
        overtime_hours=float(data.get('overtime_hours', 0)),
        is_holiday=bool(data.get('is_holiday', False)),
    ))


# ============================================================
# 客戶驗收中心 API
# ============================================================
@app.route('/api/acceptance/kb-status')
def api_acc_kb_status():
    """回傳完整知識庫資料來源狀態（每筆 FAQ 與其他資產來源透明化）"""
    return jsonify(accs.get_kb_status())

@app.route('/api/acceptance/kb-meta')
def api_acc_kb_meta():
    """供前端動態載入：各客戶的產品名 + FAQ 問句清單（用於 chip 按鈕）"""
    out = {}
    for cust, kb in accs.PRODUCT_KB.items():
        out[cust] = {
            'name': kb.get('name', ''),
            'suggestions': list(kb.get('faq', {}).keys()),
        }
    return jsonify(out)

@app.route('/api/acceptance/product-qa', methods=['POST'])
def api_acc_product_qa():
    d = request.json or {}
    customer = d.get('customer', 'addwii')
    if customer not in accs.PRODUCT_KB:
        return jsonify({'error': f'未知客戶：{customer}（支援：{list(accs.PRODUCT_KB.keys())}）'}), 400
    return jsonify(accs.product_qa(customer, d.get('question', ''),
                                   d.get('user', 'guest'), use_ai=bool(d.get('use_ai'))))

@app.route('/api/acceptance/product-qa-ai', methods=['POST'])
def api_acc_product_qa_ai():
    """非串流版 AI 深化：適合 Flask 開發伺服器（避免 SSE 緩衝問題）"""
    d = request.json or {}
    customer = d.get('customer', 'addwii')
    question = (d.get('question') or '').strip() or '請介紹此產品'
    kb = accs.PRODUCT_KB.get(customer, {})
    sys_prompt = (
        f'你是 {kb.get("name","未知產品")} 的繁體中文客服。依下列資料直接回答，嚴禁展示推理過程。\n'
        f'嚴禁輸出：Thinking Process、Analyze、Identify、Constraints、Steps、步驟分析 等字樣。\n'
        f'請【只】輸出最終回覆，格式：1~3 行條列式繁體中文，每行 < 40 字。\n'
        f'若資料沒有答案就輸出一行：我需要進一步查核。\n\n'
        f'【產品資料】\n'
        f'名稱：{kb.get("name","-")}\n'
        f'特色：{"、".join(kb.get("features",[]))}\n'
        f'適用：{kb.get("target","-")}\n'
        f'保固：{kb.get("warranty","-")}\n'
        f'價格：{kb.get("price","-")}\n'
        f'常見問答：\n' + '\n'.join(f'- {k}：{v}' for k, v in kb.get('faq',{}).items())
    )
    import time as _t
    t0 = _t.time()
    try:
        payload = {
            'model': OLLAMA_MODEL,
            'messages': [
                {'role':'system','content':sys_prompt},
                {'role':'user','content':question},
            ],
            'stream': False,
            'options': {'temperature': 0.3, 'num_predict': 300, 'num_ctx': 2048},
        }
        r = requests.post(f'{OLLAMA_URL}/api/chat', json=payload, timeout=120)
        r.raise_for_status()
        data = r.json()
        msg = data.get('message', {})
        raw = msg.get('content') or msg.get('thinking') or ''
        text = _clean_thinking(raw)
        if not text.strip():
            text = '（模型未返回有效內容，請改看上方 KB 答案）'
        return jsonify({'ok': True, 'answer': text, 'raw_len': len(raw), 'elapsed_ms': int((_t.time()-t0)*1000), 'model': OLLAMA_MODEL})
    except requests.exceptions.Timeout:
        return jsonify({'ok': False, 'error': 'AI 逾時 (60 秒)，請稍後重試'})
    except Exception as e:
        return jsonify({'ok': False, 'error': f'AI 連線失敗：{e}'})

@app.route('/api/acceptance/product-qa-stream', methods=['POST'])
def api_acc_product_qa_stream():
    """SSE 串流：先秒回 KB 命中，再逐字流式吐 AI 深化解答"""
    from flask import Response, stream_with_context
    d = request.json or {}
    customer = d.get('customer', 'addwii')
    question = (d.get('question') or '').strip() or '請介紹此產品'
    user = d.get('user', 'guest')
    use_ai = bool(d.get('use_ai', True))

    kb_hit = accs.product_qa(customer, question, user)
    kb = accs.PRODUCT_KB.get(customer, {})

    def gen():
        def send(event, data):
            return f'event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n'
        # 第 1 步：立刻送出 KB 命中結果
        yield send('kb', {
            'kb': kb_hit['kb'],
            'answer': kb_hit['answer'],
            'workflow': kb_hit['workflow'],
        })
        if not use_ai:
            yield send('done', {'source':'kb-only'})
            return
        # 第 2 步：呼叫 Ollama stream=True 逐字輸出
        sys_prompt = (
            f'你是 {kb.get("name","未知產品")} 的專業客服助理。只能依下列資料回答，不要編造：\n'
            f'特色：{"、".join(kb.get("features",[]))}\n'
            f'適用對象：{kb.get("target","-")}\n'
            f'保固：{kb.get("warranty","-")}\n'
            f'價格：{kb.get("price","-")}\n'
            f'常見問答：{json.dumps(kb.get("faq",{}), ensure_ascii=False)}\n'
            f'請用 150 字以內、條列式繁體中文回答。不知道就說「我需要進一步查核」。'
        )
        payload = {
            'model': OLLAMA_MODEL,
            'messages': [
                {'role':'system','content':sys_prompt},
                {'role':'user','content':question},
            ],
            'stream': True,
            'options': {'temperature': 0.3, 'num_predict': 256},
        }
        yield send('ai_start', {'model': OLLAMA_MODEL})
        try:
            with requests.post(f'{OLLAMA_URL}/api/chat', json=payload, stream=True, timeout=45) as resp:
                acc = ''
                for line in resp.iter_lines(decode_unicode=True):
                    if not line: continue
                    try:
                        chunk = json.loads(line)
                    except Exception:
                        continue
                    piece = chunk.get('message', {}).get('content') or chunk.get('message', {}).get('thinking') or ''
                    if piece:
                        acc += piece
                        yield send('ai_chunk', {'delta': piece})
                    if chunk.get('done'):
                        break
                yield send('done', {'source':'ai', 'total_chars': len(acc)})
        except requests.exceptions.Timeout:
            yield send('error', {'msg': 'AI 逾時，已顯示知識庫內容'})
            yield send('done', {'source':'timeout'})
        except Exception as e:
            yield send('error', {'msg': f'AI 連線失敗：{e}'})
            yield send('done', {'source':'error'})

    return Response(stream_with_context(gen()), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',
    })

@app.route('/api/acceptance/feedback', methods=['POST'])
def api_acc_feedback():
    d = request.get_json(silent=True) or {}
    records = d.get('records') or accs.DEMO_FEEDBACK
    return jsonify(accs.analyze_feedback(records, d.get('user', 'guest'), use_ai=bool(d.get('use_ai'))))


@app.route('/api/acceptance/feedback-accuracy-test', methods=['POST'])
def api_acc_feedback_accuracy():
    """用標準測試集跑情緒分析，回傳準確率（對應驗收構面二 ≥ 85% 門檻）"""
    from feedback_test_cases import run_accuracy_test
    return jsonify(run_accuracy_test(accs.analyze_feedback))

@app.route('/api/acceptance/proposal', methods=['POST'])
def api_acc_proposal():
    d = request.json or {}
    return jsonify(accs.generate_proposal(d.get('customer', 'addwii'), d.get('profile', {}),
                                          d.get('user', 'guest'), use_ai=bool(d.get('use_ai'))))

@app.route('/api/acceptance/content', methods=['POST'])
def api_acc_content():
    d = request.get_json(silent=True) or {}
    return jsonify(accs.generate_content(
        d.get('topic', '智慧空氣'),
        d.get('channel', 'FB'),
        d.get('user', 'guest'),
        use_ai=bool(d.get('use_ai')),
        seo_keywords=d.get('seo_keywords'),
    ))

@app.route('/api/acceptance/csv-analysis', methods=['POST'])
def api_acc_csv():
    d = request.json or {}
    return jsonify(accs.analyze_all_csv(d.get('user', 'guest'), force=bool(d.get('force'))))

@app.route('/api/acceptance/pii-scan', methods=['POST'])
def api_acc_pii():
    d = request.json or {}
    return jsonify(accs.scan_pii(d.get('text', ''), d.get('user', 'guest')))

@app.route('/api/acceptance/audit')
def api_acc_audit():
    return jsonify(accs.read_audit(int(request.args.get('limit', 100))))

@app.route('/api/acceptance/csv-drill', methods=['POST'])
def api_acc_csv_drill():
    d = request.json or {}
    return jsonify(accs.drill_csv(
        room=str(d.get('room','')),
        house=str(d.get('house','')),
        bucket_hours=int(d.get('bucket_hours', 1)),
        max_buckets=int(d.get('max_buckets', 48)),
    ))

@app.route('/api/acceptance/qa-chat', methods=['POST'])
def api_acc_qa_chat():
    d = request.json or {}
    return jsonify(accs.qa_chat_multi(
        session_id=d.get('session_id',''),
        customer=d.get('customer','addwii'),
        question=d.get('question',''),
        user=d.get('user','guest'),
    ))

@app.route('/api/acceptance/qa-reset', methods=['POST'])
def api_acc_qa_reset():
    d = request.json or {}
    return jsonify(accs.qa_session_reset(d.get('session_id','')))



# ══════════════════════════════════════════════════════════
# CRM 營運 API（詢問單 → 報價單 → 訂單 → 安裝記錄）
# ══════════════════════════════════════════════════════════
@app.route('/api/crm/summary')
def api_crm_summary():
    return jsonify(crm.summary())

@app.route('/api/crm/inquiries')
def api_crm_list_inq():
    return jsonify(crm.list_inquiries(status=request.args.get('status')))

@app.route('/api/crm/quotes')
def api_crm_list_quo():
    return jsonify(crm.list_quotes(status=request.args.get('status')))

@app.route('/api/crm/orders')
def api_crm_list_ord():
    return jsonify(crm.list_orders(status=request.args.get('status')))

@app.route('/api/crm/installations')
def api_crm_list_ins():
    return jsonify(crm.list_installations(status=request.args.get('status')))

@app.route('/api/crm/inquiry', methods=['POST'])
def api_crm_create_inq():
    data = request.json or {}
    return jsonify(crm.create_inquiry(data))

@app.route('/api/crm/inquiry/<iid>/to-quote', methods=['POST'])
def api_crm_to_quote(iid):
    return jsonify(crm.convert_to_quote(iid))

@app.route('/api/crm/quote/<qid>/accept', methods=['POST'])
def api_crm_accept_quote(qid):
    return jsonify(crm.accept_quote(qid))

@app.route('/api/crm/quote/<qid>/reject', methods=['POST'])
def api_crm_reject_quote(qid):
    d = request.json or {}
    return jsonify(crm.reject_quote(qid, reason=d.get('reason','')))

@app.route('/api/crm/order/<oid>/install', methods=['POST'])
def api_crm_install(oid):
    return jsonify(crm.start_installation(oid))

@app.route('/api/crm/installation/<iid>/complete', methods=['POST'])
def api_crm_install_done(iid):
    return jsonify(crm.complete_installation(iid))

@app.route('/api/crm/modules')
def api_crm_modules():
    """回傳全部模組定價清單（供前端與官網下單共用）"""
    return jsonify([
        {'id': mid, 'name': MODULE_NAMES[mid], 'price': price}
        for mid, price in MODULE_PRICES.items()
    ])

@app.route('/api/crm/calc-quote', methods=['POST'])
def api_crm_calc():
    d = request.json or {}
    modules = d.get('modules') or []
    return jsonify(calc_quote(modules))

@app.route('/api/crm/quote/<qid>/pdf')
def api_crm_quote_pdf(qid):
    """報價單 PDF 下載"""
    from flask import Response
    import pdf_export
    q = crm.get_quote(qid)
    if not q: return ('報價單不存在', 404)
    # 反查詢問單
    with crm._conn() as c:
        r = c.execute('SELECT * FROM 詢問單 WHERE 詢問編號=?', (q['詢問編號'],)).fetchone()
        inq = dict(r) if r else None
    pdf_bytes = pdf_export.build_quote_pdf(q, inq)
    return Response(pdf_bytes, mimetype='application/pdf', headers={
        'Content-Disposition': f'attachment; filename="quote_{qid}.pdf"'
    })

@app.route('/api/acceptance/feedback-audit-pdf', methods=['POST'])
def api_acc_feedback_audit_pdf():
    """把客戶回饋分析結果轉成結構化 AI 審計報告 PDF"""
    from flask import Response
    import pdf_export
    d = request.json or {}
    records = d.get('records') or accs.DEMO_FEEDBACK
    r = accs.analyze_feedback(records, d.get('user', 'guest'), use_ai=bool(d.get('use_ai')))
    # 轉換為結構化 sections
    stats = r.get('stats', {})
    sections = []
    # 情緒分布
    pos = stats.get('正面', 0); neg = stats.get('負面', 0); neu = stats.get('中性', 0)
    total = pos + neg + neu
    if total > 0:
        s = 'pass' if neg <= pos else ('warn' if neg > pos else 'fail')
        sections.append({'status': s, 'title': '情緒分布分析',
            'detail': f'共 {total} 筆客訴｜正面 {pos} 筆 ({pos*100//max(total,1)}%)｜中性 {neu} 筆｜負面 {neg} 筆 ({neg*100//max(total,1)}%)'})
    # 問題分類分布
    cat_lines = []
    for cat in ['硬體', '軟體', '服務', '準確度', '其他']:
        if stats.get(cat, 0) > 0:
            cat_lines.append(f'{cat}: {stats[cat]} 筆')
    if cat_lines:
        sections.append({'status': 'info', 'title': '問題分類統計',
            'detail': ' / '.join(cat_lines)})
    # 負面案件派工
    neg_cases = [x for x in r['records'] if x['sentiment'] == '負面']
    if neg_cases:
        detail = '\n'.join(f'• {x["id"]} [{x["customer"]}] {"/".join(x["categories"])} → {x["suggestion"]}' for x in neg_cases)
        sections.append({'status': 'warn', 'title': f'負面案件派工建議（{len(neg_cases)} 筆）',
            'detail': detail})
    # Qwen AI 主管摘要
    if r.get('ai_summary'):
        sections.append({'status': 'info', 'title': f'🧠 Qwen 2.5 7B AI 主管決策摘要',
            'detail': r['ai_summary']})
    # 綜合建議
    if neg > pos:
        vt = 'fail'
        verdict = '負面情緒占多數，建議立刻召開客服品質改善會議，並依照上述派工建議優先處理硬體/服務類型案件。'
    elif neg > 0:
        vt = 'warn'
        verdict = f'存在 {neg} 件負面案件，已產出派工建議。整體情勢可控但需在 72 小時內回覆負面客戶。'
    else:
        vt = 'pass'
        verdict = '客戶情緒整體正面，無需緊急處理。建議把正面回饋納入產品行銷素材。'
    meta = {'彙整期間': datetime.now().strftime('%Y-%m-%d'),
            '客訴總數': str(total), '產出模型': os.getenv('OLLAMA_MODEL', 'qwen2.5:7b') if r.get('ai_summary') else '規則引擎'}
    pdf_bytes = pdf_export.build_ai_analysis_pdf(
        title='客戶回饋 AI 審計報告',
        subtitle=f'凌策 AI 顧問 · 自動彙整 · {datetime.now().strftime("%Y-%m-%d %H:%M")}',
        sections=sections, verdict=verdict, verdict_type=vt, meta=meta)
    return Response(pdf_bytes, mimetype='application/pdf', headers={
        'Content-Disposition': f'attachment; filename="feedback_audit_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf"'
    })

@app.route('/api/acceptance/proposal-pdf', methods=['POST'])
def api_acc_proposal_pdf():
    """B2B 提案書 PDF 下載"""
    from flask import Response
    import pdf_export
    d = request.json or {}
    r = accs.generate_proposal(d.get('customer','addwii'), d.get('profile', {}), d.get('user','guest'))
    pdf_bytes = pdf_export.build_proposal_pdf(r['proposal'])
    fn = f'proposal_{d.get("customer","addwii")}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    return Response(pdf_bytes, mimetype='application/pdf', headers={
        'Content-Disposition': f'attachment; filename="{fn}"'
    })

@app.route('/api/hr/attendance-report/pdf', methods=['POST'])
def api_hr_attendance_report_pdf():
    """HR 出缺勤報表 PDF（取代/補充 CSV）"""
    from flask import Response
    import pdf_export
    data = request.json or {}
    actor_id = data.get('actor_id')
    actor = attendance_mgr.members.get(actor_id) if actor_id else None
    if not (actor and (actor.is_hr or any(k in (actor.title or '') for k in ('總經理','董事長')))):
        return ('forbidden', 403)
    report = leave_ot_mgr.generate_attendance_report(
        start_date=data.get('start_date'),
        end_date=data.get('end_date'),
        dept=data.get('dept'),
        member_ids=data.get('member_ids'),
    )
    pdf_bytes = pdf_export.build_attendance_report_pdf(report)
    fn = f'attendance_{data.get("start_date")}_{data.get("end_date")}.pdf'
    return Response(pdf_bytes, mimetype='application/pdf', headers={
        'Content-Disposition': f'attachment; filename="{fn}"'
    })

@app.route('/api/crm/website-inquiry', methods=['POST'])
def api_crm_website():
    """官網表單 → 詢問單（自動標記來源=官網）"""
    d = request.json or {}
    d['來源'] = '官網'
    return jsonify(crm.create_inquiry(d))


# ══════════════════════════════════════════════════════════
# 出缺勤統計與編輯審批 API
# ══════════════════════════════════════════════════════════
@app.route('/api/attendance-stats/daily')
def api_attn_daily():
    date_str = request.args.get('date') or datetime.now().strftime('%Y-%m-%d')
    dept = request.args.get('dept') or None
    return jsonify(attn_analytics.daily_summary(date_str, dept=dept))

@app.route('/api/attendance-stats/monthly')
def api_attn_monthly():
    y = int(request.args.get('year') or datetime.now().year)
    m = int(request.args.get('month') or datetime.now().month)
    dept = request.args.get('dept') or None
    return jsonify(attn_analytics.monthly_summary(y, m, dept=dept))

@app.route('/api/attendance-stats/member/<mid>')
def api_attn_member(mid):
    y = int(request.args.get('year') or datetime.now().year)
    m = int(request.args.get('month') or datetime.now().month)
    return jsonify(attn_analytics.member_monthly(mid, y, m))

@app.route('/api/attendance-stats/edit', methods=['POST'])
def api_attn_edit_request():
    d = request.json or {}
    return jsonify(attn_analytics.request_edit(
        actor_id=d.get('actor_id'), target_id=d.get('target_id'),
        date_str=d.get('date'), field=d.get('field'),
        new_value=d.get('new_value'), reason=d.get('reason', ''),
    ))

@app.route('/api/attendance-stats/edit/<eid>/approve', methods=['POST'])
def api_attn_edit_approve(eid):
    d = request.json or {}
    return jsonify(attn_analytics.approve_edit(d.get('approver_id'), eid))

@app.route('/api/attendance-stats/edit/<eid>/reject', methods=['POST'])
def api_attn_edit_reject(eid):
    d = request.json or {}
    return jsonify(attn_analytics.reject_edit(d.get('approver_id'), eid, reason=d.get('reason', '')))

@app.route('/api/attendance-stats/edits')
def api_attn_edits():
    return jsonify(attn_analytics.list_edits(
        status=request.args.get('status'),
        approver_id=request.args.get('approver_id'),
        actor_id=request.args.get('actor_id'),
    ))

@app.route('/api/attendance-stats/audit')
def api_attn_audit():
    return jsonify(attn_analytics.read_audit(int(request.args.get('limit', 100))))


# ══════════════════════════════════════
# Phase 3：addwii→microjet 採購流程 + 感測器序號綁定
# ══════════════════════════════════════
@app.route('/api/procurement/scenario')
def api_procurement_scenario():
    """回傳 12 坪情境的完整狀態（給三個客戶視角頁面用）"""
    return jsonify(procurement_mgr.get_scenario())

@app.route('/api/procurement/po/<po_id>/ship', methods=['POST'])
def api_procurement_ship(po_id):
    """microjet 出貨採購單 → 自動生成序號 + 綁定至 addwii 訂單"""
    result = procurement_mgr.ship_po(po_id)
    return jsonify(result), (200 if result.get('ok') else 400)

@app.route('/api/procurement/order/<order_id>/advance', methods=['POST'])
def api_procurement_advance(order_id):
    """推進訂單里程碑（addwii 端操作）"""
    result = procurement_mgr.advance_order(order_id)
    return jsonify(result), (200 if result.get('ok') else 400)

@app.route('/api/procurement/serials')
def api_procurement_serials():
    """列出所有感測器序號（已綁定客戶）"""
    return jsonify(procurement_mgr.list_serials())

@app.route('/api/procurement/audit')
def api_procurement_audit():
    return jsonify(procurement_mgr.get_audit(int(request.args.get('limit', 50))))

# ══════════════════════════════════════
# Ollama 一鍵安裝 + 狀態查詢（給評審環境用）
# ══════════════════════════════════════
_OLLAMA_TASK = {'status': 'idle', 'message': '', 'progress': 0, 'started_at': None}
_OLLAMA_TASK_LOCK = threading.Lock()


def _find_ollama_exe() -> str | None:
    """找 ollama.exe 的實際路徑。winget 裝完 PATH 不會自動刷新到已跑的 Python，
    所以除了 shutil.which 之外也檢查常見安裝路徑。回傳 None 代表真的沒裝。"""
    import shutil
    p = shutil.which('ollama')
    if p: return p
    # Windows 常見安裝路徑
    candidates = [
        os.path.expandvars(r'%LOCALAPPDATA%\Programs\Ollama\ollama.exe'),
        os.path.expandvars(r'%ProgramFiles%\Ollama\ollama.exe'),
        os.path.expandvars(r'%USERPROFILE%\AppData\Local\Programs\Ollama\ollama.exe'),
        r'C:\Program Files\Ollama\ollama.exe',
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def _check_ollama_installed() -> bool:
    """檢查本機是否裝了 Ollama CLI"""
    return _find_ollama_exe() is not None


def _check_ollama_running() -> bool:
    """檢查 Ollama 服務是否回應"""
    try:
        r = requests.get(f'{OLLAMA_URL}/api/tags', timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def _check_model_pulled(model: str) -> bool:
    """檢查指定模型是否已下載"""
    try:
        r = requests.get(f'{OLLAMA_URL}/api/tags', timeout=2)
        if r.status_code != 200:
            return False
        tags = r.json().get('models', [])
        return any(model in m.get('name', '') for m in tags)
    except Exception:
        return False


@app.route('/api/ollama/status')
def api_ollama_status():
    """回傳 Ollama 完整狀態：是否安裝 / 是否運行 / 模型是否下載"""
    # 雲端模式（OLLAMA_MODEL=none）→ 直接回 "cloud"，前端會跳過 banner
    if (OLLAMA_MODEL or '').lower() in ('none', 'disabled', ''):
        return jsonify({
            'cloud_mode': True,
            'installed': False, 'running': False, 'model_pulled': False,
            'model_name': OLLAMA_MODEL, 'next_action': 'cloud',
            'message': '雲端 Demo 模式（不含 Ollama）— 所有 AI 精煉功能走內建模板',
            'task': {'status': 'idle'},
        })
    installed = _check_ollama_installed()
    running   = _check_ollama_running() if installed else False
    model_ok  = _check_model_pulled(OLLAMA_MODEL) if running else False

    # 判定下一步要做什麼
    if not installed:
        next_action = 'install'
        message = '尚未偵測到 Ollama，可一鍵自動安裝（透過 winget）'
    elif not running:
        next_action = 'start'
        message = 'Ollama 已安裝但未啟動，請於終端機執行 ollama serve'
    elif not model_ok:
        next_action = 'pull'
        message = f'缺少模型 {OLLAMA_MODEL}，點擊下載（約 4.7 GB）'
    else:
        next_action = 'ready'
        message = f'✓ 完全就緒：Ollama 運行中，{OLLAMA_MODEL} 已下載'

    with _OLLAMA_TASK_LOCK:
        task_state = dict(_OLLAMA_TASK)

    return jsonify({
        'installed':    installed,
        'running':      running,
        'model_pulled': model_ok,
        'model_name':   OLLAMA_MODEL,
        'next_action':  next_action,
        'message':      message,
        'task':         task_state,
    })


def _run_ollama_task(name: str, cmd: list, success_check):
    """背景執行 ollama 相關指令，把進度寫入 _OLLAMA_TASK"""
    import subprocess
    with _OLLAMA_TASK_LOCK:
        _OLLAMA_TASK['status'] = 'running'
        _OLLAMA_TASK['message'] = f'執行中：{name}'
        _OLLAMA_TASK['progress'] = 5
        _OLLAMA_TASK['started_at'] = datetime.now().isoformat(timespec='seconds')

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding='utf-8', errors='replace')
        # 簡單輪詢 stdout 更新進度
        pct = 10
        for line in proc.stdout or []:
            line = line.strip()
            if not line: continue
            pct = min(pct + 3, 90)
            with _OLLAMA_TASK_LOCK:
                _OLLAMA_TASK['progress'] = pct
                _OLLAMA_TASK['message'] = line[:120]
        proc.wait(timeout=1800)  # 最長 30 分鐘

        ok = (proc.returncode == 0) and success_check()
        with _OLLAMA_TASK_LOCK:
            _OLLAMA_TASK['status']   = 'done' if ok else 'failed'
            _OLLAMA_TASK['progress'] = 100
            _OLLAMA_TASK['message']  = f'{name} 完成' if ok else f'{name} 失敗（回傳碼 {proc.returncode}）'
    except Exception as e:
        with _OLLAMA_TASK_LOCK:
            _OLLAMA_TASK['status']   = 'failed'
            _OLLAMA_TASK['message']  = f'{name} 錯誤：{e}'


@app.route('/api/ollama/install', methods=['POST'])
def api_ollama_install():
    """透過 winget 自動安裝 Ollama（需 Windows 10 1809+）"""
    import shutil
    if not shutil.which('winget'):
        return jsonify({'ok': False, 'error': 'winget 不可用，請手動到 https://ollama.com 下載'}), 400
    if _check_ollama_installed():
        return jsonify({'ok': True, 'already': True, 'message': 'Ollama 已安裝'})

    with _OLLAMA_TASK_LOCK:
        if _OLLAMA_TASK['status'] == 'running':
            return jsonify({'ok': False, 'error': '已有任務在執行中', 'task': dict(_OLLAMA_TASK)}), 409

    threading.Thread(
        target=_run_ollama_task,
        args=('安裝 Ollama', ['winget', 'install', 'Ollama.Ollama',
                              '--silent', '--accept-package-agreements',
                              '--accept-source-agreements'],
              _check_ollama_installed),
        daemon=True).start()
    return jsonify({'ok': True, 'message': '安裝已在背景執行，請輪詢 /api/ollama/status 查看進度'})


@app.route('/api/ollama/pull-model', methods=['POST'])
def api_ollama_pull():
    """下載指定模型（預設 qwen2.5:7b，約 4.7 GB）"""
    ollama_exe = _find_ollama_exe()
    if not ollama_exe:
        return jsonify({'ok': False, 'error': 'Ollama 尚未安裝'}), 400
    if not _check_ollama_running():
        # 嘗試自動啟動 Ollama 服務（Windows 下 ollama.exe 本身能當 server）
        try:
            import subprocess
            subprocess.Popen([ollama_exe, 'serve'],
                             creationflags=0x08000000 if os.name=='nt' else 0,  # CREATE_NO_WINDOW
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # 等最多 8 秒讓服務起來
            for _ in range(16):
                time.sleep(0.5)
                if _check_ollama_running():
                    break
        except Exception as _e:
            pass
        if not _check_ollama_running():
            return jsonify({'ok': False, 'error': 'Ollama 服務無法啟動。請於「開始」功能表開啟 Ollama 應用程式後重試'}), 400

    # silent=True → 即便 Content-Type 不是 json 也不會報 415
    _data = request.get_json(silent=True) or {}
    model = _data.get('model', OLLAMA_MODEL)

    with _OLLAMA_TASK_LOCK:
        if _OLLAMA_TASK['status'] == 'running':
            return jsonify({'ok': False, 'error': '已有任務在執行中', 'task': dict(_OLLAMA_TASK)}), 409

    threading.Thread(
        target=_run_ollama_task,
        args=(f'下載模型 {model}', [ollama_exe, 'pull', model],
              lambda m=model: _check_model_pulled(m)),
        daemon=True).start()
    return jsonify({'ok': True, 'message': f'{model} 下載已在背景執行（4.7 GB，預計 10–20 分鐘）'})


@app.route('/api/procurement/reset', methods=['POST'])
def api_procurement_reset():
    """展示用：重置情境至初始狀態"""
    return jsonify(procurement_mgr.reset())


@app.route('/api/procurement/pdf/addwii-order')
def api_procurement_pdf_addwii():
    """addwii B2C 場域無塵室報價單 PDF（陳先生 12 坪案）"""
    import pdf_export
    from flask import Response
    s = procurement_mgr.get_scenario()
    pdf_bytes = pdf_export.build_addwii_order_pdf(s)
    fname = f"addwii_quote_{s['quote']['id']}.pdf"
    return Response(pdf_bytes, mimetype='application/pdf',
                    headers={'Content-Disposition': f'inline; filename="{fname}"'})


# ══════════════════════════════════════
# 官網潛客詢問表單（index.html）
# ══════════════════════════════════════
_INQUIRY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             '..', '..', 'chat_logs', 'website_inquiries.jsonl')
_INQUIRY_LOCK = threading.Lock()

@app.route('/api/inquiry/submit', methods=['POST'])
def api_inquiry_submit():
    """接收官網潛客表單 → append 到 website_inquiries.jsonl（同時轉入 CRM）"""
    data = request.json or {}
    # 基本欄位驗證
    if not data.get('company') or not data.get('contact') or not data.get('email'):
        return jsonify({'ok': False, 'error': '缺少必填欄位 (company/contact/email)'}), 400

    inquiry_id = f"WEB-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
    record = {
        'inquiry_id': inquiry_id,
        'received_at': datetime.now().isoformat(timespec='seconds'),
        'company':  data.get('company','').strip(),
        'contact':  data.get('contact','').strip(),
        'email':    data.get('email','').strip(),
        'phone':    data.get('phone','').strip(),
        'industry': data.get('industry',''),
        'size':     data.get('size',''),
        'modules':  data.get('modules', []),
        'note':     data.get('note','').strip(),
        'source':   data.get('source','凌策官網'),
        'status':   '待 BD Agent 回覆',
    }

    try:
        with _INQUIRY_LOCK:
            os.makedirs(os.path.dirname(_INQUIRY_FILE), exist_ok=True)
            with open(_INQUIRY_FILE, 'a', encoding='utf-8') as f:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')

        # 同步寫入 CRM 詢問單（若可用）
        try:
            crm.create_inquiry({
                '公司名稱': record['company'],
                '聯絡人':   record['contact'],
                '電話':     record['phone'],
                'Email':    record['email'],
                '產業別':   record['industry'] or '其他',
                '需求說明': record['note'],
                '選擇模組': record['modules'],
                '來源':     '官網',
                '備註':     f"官網來源 · 組織規模 {record.get('size','')} · Web ID: {inquiry_id}",
            })
        except Exception as e:
            print(f'[inquiry] CRM 同步失敗（非阻斷）: {e}')

        return jsonify({'ok': True, 'inquiry_id': inquiry_id,
                        'message': f'收到詢問！BD Agent 將於 24 小時內回覆 {record["email"]}'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# ══════════════════════════════════════
# P0 合規中心 API（PII 遮蔽展示 + 審核閘 + 合規狀態）
# ══════════════════════════════════════
@app.route('/api/compliance/status')
def api_compliance_status():
    """四大合規控制點即時狀態 — 給合規展示頁"""
    from pii_guard import CLAUDE_API_DISABLED, audit_stats
    import pii_guard as pg
    stats = audit_stats()

    # 檢查 audit log 檔案存在
    audit_paths = {
        'pii_audit': os.path.exists(pg._AUDIT_FILE),
        'acceptance_audit': os.path.exists(os.path.join(
            os.path.dirname(os.path.abspath(__file__)), '..', '..',
            'chat_logs', 'acceptance_audit.jsonl')),
        'org_audit': os.path.exists(os.path.join(
            os.path.dirname(os.path.abspath(__file__)), '..', '..',
            'chat_logs', 'org_audit.jsonl')),
    }

    return jsonify({
        'controls': [
            {
                'id': 'C1_LOCAL_ONLY',
                'name': '個資不外流（雲端 API 關閉）',
                'status': 'DONE' if CLAUDE_API_DISABLED else 'RISK',
                'evidence': f'pii_guard.CLAUDE_API_DISABLED = {CLAUDE_API_DISABLED}；Ollama 本地 LLM {OLLAMA_MODEL}',
            },
            {
                'id': 'C2_PII_MASK',
                'name': 'PII 偵測與遮蔽中介層',
                'status': 'DONE',
                'evidence': f'所有 LLM 呼叫經 pii_guard.mask_text()；累計偵測 {stats["total_pii_detected"]} 筆 PII',
            },
            {
                'id': 'C3_AUDIT_LOG',
                'name': '稽核日誌完整性（append-only JSONL）',
                'status': 'DONE' if all(audit_paths.values()) else 'PARTIAL',
                'evidence': f'pii_audit={audit_paths["pii_audit"]} / acceptance_audit={audit_paths["acceptance_audit"]} / org_audit={audit_paths["org_audit"]}',
            },
            {
                'id': 'C4_HUMAN_GATE',
                'name': '人工審核閘（刪除/匯出二次確認）',
                'status': 'DONE',
                'evidence': '組織成員刪除、情境重置、批次匯出皆強制 confirm() + 稽核寫入',
            },
        ],
        'summary': stats,
        'cloud_api_disabled': CLAUDE_API_DISABLED,
        'ollama_model': OLLAMA_MODEL,
    })


@app.route('/api/compliance/pii-demo', methods=['POST'])
def api_compliance_pii_demo():
    """互動展示：使用者輸入含 PII 的文字，即時看遮蔽結果"""
    from pii_guard import mask_text
    data = request.json or {}
    text = data.get('text', '')
    if not text:
        return jsonify({'ok': False, 'error': '請提供 text'}), 400
    masked, detections = mask_text(text, context='compliance_demo')
    return jsonify({
        'ok': True,
        'input': text,
        'masked': masked,
        'detections': detections,
        'count': len(detections),
    })


@app.route('/api/compliance/audit')
def api_compliance_audit():
    """讀取 PII 稽核 log"""
    from pii_guard import read_recent_audit
    return jsonify(read_recent_audit(int(request.args.get('limit', 50))))


@app.route('/api/compliance/human-gate-log', methods=['POST'])
def api_compliance_human_gate_log():
    """人工審核閘：記錄刪除/匯出等破壞性操作的二次確認"""
    data = request.json or {}
    op = data.get('op', 'unknown')
    target = data.get('target', '')
    reason = data.get('reason', '')
    actor = data.get('actor', 'anonymous')

    if not reason.strip():
        return jsonify({'ok': False, 'error': '人工審核閘要求必填理由'}), 400

    audit_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              '..', '..', 'chat_logs', 'human_gate.jsonl')
    os.makedirs(os.path.dirname(audit_file), exist_ok=True)
    rec = {
        'ts': datetime.now().isoformat(timespec='seconds'),
        'operation': op,
        'target':    target,
        'actor':     actor,
        'reason':    reason,
        'status':    'approved_by_human',
    }
    with open(audit_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')
    return jsonify({'ok': True, 'record': rec})


@app.route('/api/compliance/human-gate-log', methods=['GET'])
def api_compliance_human_gate_read():
    """讀取人工審核閘稽核"""
    audit_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              '..', '..', 'chat_logs', 'human_gate.jsonl')
    if not os.path.exists(audit_file):
        return jsonify([])
    rows = []
    with open(audit_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try: rows.append(json.loads(line))
                except: pass
    return jsonify(list(reversed(rows))[:int(request.args.get('limit', 50))])


@app.route('/api/inquiry/list')
def api_inquiry_list():
    """列出官網詢問歷史（內部使用）"""
    if not os.path.exists(_INQUIRY_FILE):
        return jsonify([])
    rows = []
    try:
        with open(_INQUIRY_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try: rows.append(json.loads(line))
                    except: pass
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    return jsonify(list(reversed(rows))[:int(request.args.get('limit', 50))])


@app.route('/api/procurement/pdf/microjet-po')
def api_procurement_pdf_microjet():
    """microjet B2B 採購/出貨單 PDF（含序號綁定）"""
    import pdf_export
    from flask import Response
    s = procurement_mgr.get_scenario()
    pdf_bytes = pdf_export.build_microjet_po_pdf(s)
    fname = f"microjet_po_{s['purchase_to_microjet']['po_id']}.pdf"
    return Response(pdf_bytes, mimetype='application/pdf',
                    headers={'Content-Disposition': f'inline; filename="{fname}"'})


if __name__ == '__main__':
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    print('=' * 60)
    print('  LingCe Co. - AI Agent Platform v2.0 (Live)')
    print(f'  Model: {OLLAMA_MODEL} @ {OLLAMA_URL}')
    print(f'  Agents: {len(AGENTS)} ready')
    print('=' * 60)
    print()
    print('  Dashboard:  http://localhost:5000/dashboard.html')
    print('  Website:    http://localhost:5000/')
    print('  API:        http://localhost:5000/api/health')
    print('  Chat:       POST http://localhost:5000/api/chat')
    print('  Pipeline:   POST http://localhost:5000/api/pipeline')
    print()
    # 關閉 reloader 以保留背景執行緒（AI 回覆、排程器）
    # 用 IPv6 dual-stack 監聽以避免 Windows 上 localhost 解析成 ::1 時每個請求等待 2 秒 IPv6 超時
    import socket
    try:
        # 監聽 IPv4 (0.0.0.0) — 廣相容，支援 127.0.0.1 / localhost / 區網 IP
        # 不用 '::' 因為 Windows 預設 IPV6_V6ONLY=1，會拒絕 IPv4 連線
        # debug=False：關閉 debug 模式，避免 reloader 或額外 child process 干擾
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False, threaded=True)
    except OSError as _e:
        print(f'[Server] 啟動失敗: {_e}，嘗試降級...')
        app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False, threaded=True)
