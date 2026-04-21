#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MicroJet 集團組織成員名冊（依頂埔廠分機一覽表，保留真實職稱）

欄位：
  - name: 姓名
  - role: 層級角色（經理/副理/課長/副課長/工程師）— 用於組織階層邏輯
  - title: 實際職稱（MIS工程師、協理、副廠長、研發副課長...）— 顯示用
  - dept: 所屬部門
"""

from attendance_manager import Member


# 部門常量
MGR_OFFICE = 'MICROJET · 總經理室'
HRA = 'MICROJET · 人事總務'
MIS = 'MICROJET · 資訊部'
FIN = 'MICROJET · 財務部'
ENG_DEPT = 'MICROJET · 工程部'
BIO = 'MICROJET · 工程部 / 生技課'
EQP = 'MICROJET · 工程部 / 設備課'
PM_DEPT = 'MICROJET · PM 部'
PD1 = 'MICROJET · 產品開發處 1'
MFG = 'MICROJET · 製造處 / 頂埔廠'
MAT = 'MICROJET · 資材'
PR = 'MICROJET · 採購'
PS = 'MICROJET · Pump & Sensor 行銷業務處'
PRT = 'MICROJET · 列印行銷業務處'
RD2 = 'MICROJET · 研發二部（RD2）'
QA = 'MICROJET · 品保處'
ADDWII = 'addwii 加我科技'


def build_initial_org():
    members = [
        # ════════════════════════════════════════════════
        # 集團董事會
        # ════════════════════════════════════════════════
        Member('BOARD-001', '董事長', '經理', '集團董事會', None, '👑', title='董事長'),

        # ════════════════════════════════════════════════
        # MICROJET
        # ════════════════════════════════════════════════

        # ── 總經理室
        Member('MGR-001', '薛達偉', '副理', MGR_OFFICE, 'BOARD-001', '🎯', title='總經理'),
        Member('MGR-002', '鄭永明', '副理', MGR_OFFICE, 'MGR-001', '📋', title='專案經理'),
        Member('MGR-003', '呂昭穎', '工程師', MGR_OFFICE, 'MGR-001', '💼', title='秘書'),
        Member('MGR-004', '張馨文', '工程師', MGR_OFFICE, 'MGR-001', '📋', title='專員'),
        Member('MGR-005', '李南枝', '工程師', MGR_OFFICE, 'MGR-001', '🔍', title='稽核專員'),

        # ── 人事總務（陳瑞照經理 — HR）
        Member('HRA-001', '陳瑞照', '副理', HRA, 'MGR-001', '👥', title='經理', is_hr=True),
        Member('HRA-002', '陳玉梅', '課長', HRA, 'HRA-001', '👥', title='課長'),
        Member('HRA-003', '尤心怡', '工程師', HRA, 'HRA-001', '📋', title='專員'),
        Member('HRA-004', '江以薰', '工程師', HRA, 'HRA-001', '☎️', title='總機'),

        # ── 資訊部（王文聰協理 → 陳煜騰經理 → 黃發源課長 → 三位工程師）
        Member('MIS-001', '王文聰', '副理', MIS, 'MGR-001', '🖥️', title='協理'),
        Member('MIS-007', '陳煜騰', '副理', MIS, 'MIS-001', '🖥️', title='經理'),
        Member('MIS-008', '黃發源', '課長', MIS, 'MIS-007', '🖥️', title='課長'),
        Member('MIS-009', '張宏宇', '工程師', MIS, 'MIS-008', '🧑‍💻', title='工程師'),
        Member('MIS-010', '許勝傑', '工程師', MIS, 'MIS-008', '🧑‍💻', title='工程師'),
        Member('MIS-011', '江弘翔', '工程師', MIS, 'MIS-008', '🧑‍💻', title='工程師'),
        Member('MIS-002', '劉宗翰', '工程師', MIS, 'MIS-001', '🧑‍💻', title='MIS 工程師'),
        Member('MIS-003', '鄭淳灃', '工程師', MIS, 'MIS-001', '🧑‍💻', title='MIS 工程師'),
        Member('MIS-004', '王竹源', '工程師', MIS, 'MIS-001', '🧑‍💻', title='MIS 工程師'),
        Member('MIS-005', '解庚霖', '工程師', MIS, 'MIS-001', '🧑‍💻', title='MIS 工程師'),
        Member('MIS-006', '陳婷如', '工程師', MIS, 'MIS-001', '🎨', title='UI/UX 設計師'),

        # ── 財務部（楊建鴻經理）
        Member('FIN-001', '楊建鴻', '副理', FIN, 'MGR-001', '💰', title='經理'),
        Member('FIN-002', '洪碧玲', '副理', FIN, 'FIN-001', '💰', title='副理'),
        Member('FIN-003', '徐立宸', '課長', FIN, 'FIN-002', '💰', title='課長'),
        Member('FIN-004', '王心瑜', '副課長', FIN, 'FIN-003', '💰', title='副課長'),
        Member('FIN-005', '姜宜怡', '工程師', FIN, 'FIN-004', '📒', title='專員'),
        Member('FIN-006', '許均薇', '工程師', FIN, 'FIN-004', '📒', title='專員'),
        Member('FIN-007', '吳淑苓', '工程師', FIN, 'FIN-004', '📒', title='助理'),
        Member('FIN-008', '張紋綺', '工程師', FIN, 'FIN-004', '📒', title='助理'),

        # ── 工程部（張凱欣經理）
        Member('ENG-001', '張凱欣', '副理', ENG_DEPT, 'MGR-001', '🔧', title='經理'),
        Member('ENG-002', '劉文雄', '工程師', ENG_DEPT, 'ENG-001', '🛠️', title='工程師'),
        # 生技課（林永康課長）
        Member('ENG-003', '林永康', '課長', BIO, 'ENG-001', '🧪', title='生技課長'),
        Member('ENG-004', '黃建誌', '工程師', BIO, 'ENG-003', '🧪', title='生技工程師'),
        Member('ENG-005', '廖偉辰', '工程師', BIO, 'ENG-003', '🧪', title='生技工程師'),
        Member('ENG-006', '廖勝弘', '工程師', BIO, 'ENG-003', '🧪', title='生技工程師'),
        Member('ENG-007', '周志勇', '工程師', BIO, 'ENG-003', '🧪', title='生技工程師'),
        Member('ENG-008', '陳思緹', '工程師', BIO, 'ENG-003', '🧪', title='生技工程師'),
        Member('ENG-009', '康晉嘉', '工程師', BIO, 'ENG-003', '🧪', title='生技工程師'),
        Member('ENG-010', '高資閔', '工程師', BIO, 'ENG-003', '🧪', title='生技助理工程師'),
        Member('ENG-011', '溫正明', '工程師', BIO, 'ENG-003', '🧪', title='生技助理工程師'),
        # 設備課（林勝雄課長）
        Member('ENG-012', '林勝雄', '課長', EQP, 'ENG-001', '⚙️', title='設備課長'),
        Member('ENG-013', '劉博仁', '工程師', EQP, 'ENG-012', '⚙️', title='設備工程師'),
        Member('ENG-014', '李嘉峻', '工程師', EQP, 'ENG-012', '⚙️', title='設備工程師'),
        Member('ENG-015', '王柏奇', '工程師', EQP, 'ENG-012', '⚙️', title='設備工程師'),
        # 電控 / 資料庫
        Member('ENG-016', '呂嘉紘', '工程師', ENG_DEPT, 'ENG-001', '🔌', title='電控工程師'),
        Member('ENG-017', '李韙哲', '工程師', ENG_DEPT, 'ENG-001', '🗄️', title='資料庫工程師'),

        # ── PM 部（鄭石宏經理）
        Member('PM-001', '鄭石宏', '副理', PM_DEPT, 'MGR-001', '📐', title='經理'),

        # ── 產品開發處 1（張英倫協理）
        Member('PD1-001', '張英倫', '副理', PD1, 'MGR-001', '🔭', title='協理'),
        Member('PD1-002', '陳世昌', '副理', PD1, 'PD1-001', '🔧', title='整合副理'),
        Member('PD1-003', '廖鴻信', '副課長', PD1, 'PD1-002', '🔧', title='整合副課長'),
        Member('PD1-004', '高中偉', '副課長', PD1, 'PD1-002', '🔧', title='整合副課長'),
        Member('PD1-005', '廖王平', '工程師', PD1, 'PD1-002', '🔧', title='整合高級工程師'),
        Member('PD1-006', '莫立邦', '工程師', PD1, 'PD1-002', '🔧', title='整合工程師'),
        Member('PD1-007', '邱元治', '工程師', PD1, 'PD1-002', '🔧', title='整合工程師'),
        Member('PD1-008', '張鈞偒', '工程師', PD1, 'PD1-002', '🔧', title='整合工程師'),
        Member('PD1-009', '黃立', '工程師', PD1, 'PD1-002', '🔧', title='整合工程師'),
        Member('PD1-010', '曾韋傑', '工程師', PD1, 'PD1-001', '📡', title='韌體工程師'),
        Member('PD1-011', '張凱博', '工程師', PD1, 'PD1-001', '💻', title='軟體工程師'),

        # ── 製造處 / 頂埔廠（吳祥滌協理）
        Member('MFG-001', '吳祥滌', '副理', MFG, 'MGR-001', '🏭', title='協理'),
        Member('MFG-002', '徐振春', '副理', MFG, 'MFG-001', '🏭', title='副廠長'),
        Member('MFG-003', '童煜中', '工程師', MFG, 'MFG-001', '📋', title='行政專員'),
        Member('MFG-004', '鄭如娟', '工程師', MFG, 'MFG-001', '📋', title='總務助理'),
        Member('MFG-005', '李紹南', '副理', MFG, 'MFG-001', '🏭', title='副理'),
        Member('MFG-006', '謝基強', '副課長', MFG, 'MFG-005', '🏭', title='副課長'),
        Member('MFG-007', '賴伊玲', '工程師', MFG, 'MFG-005', '📋', title='生產助理'),

        # ── 資材（廖仁君副理）
        Member('MAT-001', '廖仁君', '副理', MAT, 'MGR-001', '📦', title='副理'),
        Member('MAT-002', '黃政遠', '工程師', MAT, 'MAT-001', '📦', title='物管工程師'),
        Member('MAT-003', '吳俞育', '工程師', MAT, 'MAT-001', '📦', title='倉儲管理師'),
        Member('MAT-004', '盧建銘', '工程師', MAT, 'MAT-001', '📦', title='倉儲管理師'),
        Member('MAT-005', '陳柔瑾', '工程師', MAT, 'MAT-001', '📦', title='物流管理師'),

        # ── 採購（高傳恩副理）
        Member('PR-001', '高傳恩', '副理', PR, 'MGR-001', '🛒', title='副理'),
        Member('PR-002', '梁菀真', '副課長', PR, 'PR-001', '🛒', title='副課長'),
        Member('PR-003', '鐘運勳', '工程師', PR, 'PR-001', '🛒', title='工程師'),
        Member('PR-004', '邱凡哲', '工程師', PR, 'PR-001', '🛒', title='工程師'),

        # ── Pump & Sensor 行銷業務處（林慕哲產品經理）
        Member('PS-001', '林慕哲', '副理', PS, 'MGR-001', '📊', title='產品經理'),
        Member('PS-002', '林俊宇', '課長', PS, 'PS-001', '📊', title='產品課長'),
        Member('PS-003', '劉金銘', '副理', PS, 'PS-001', '💼', title='業務副理'),
        Member('PS-004', '陳裔芳', '工程師', PS, 'PS-001', '📋', title='企劃專員'),
        Member('PS-005', '何宜道', '工程師', PS, 'PS-003', '💼', title='業務專員'),
        Member('PS-006', '蔡佩君', '工程師', PS, 'PS-003', '💼', title='業務專員'),

        # ── 列印行銷業務處（李清源 Stephen 協理）
        Member('PRT-001', '李清源', '副理', PRT, 'MGR-001', '🖨️', title='協理（Stephen）'),
        Member('PRT-002', '張麗君', '工程師', PRT, 'PRT-001', '💼', title='專員（Sunny）'),
        Member('PRT-003', '林秋月', '工程師', PRT, 'PRT-001', '💼', title='專員（Irene）'),
        Member('PRT-004', '王玉華', '副理', PRT, 'PRT-001', '💼', title='副理（Amy）'),
        Member('PRT-005', '江晏圻', '工程師', PRT, 'PRT-004', '💼', title='助理（Sara）'),
        Member('PRT-006', '葉家樺', '副理', PRT, 'PRT-001', '💼', title='副理（Vivian）'),
        Member('PRT-007', '林思辰', '工程師', PRT, 'PRT-006', '💼', title='助理（Anna）'),
        Member('PRT-008', '賴詩顏', '工程師', PRT, 'PRT-006', '💼', title='助理（Sally）'),
        Member('PRT-009', '李幼雯', '工程師', PRT, 'PRT-001', '💼', title='專員（Jessy）'),
        Member('PRT-010', '龔翊祺', '工程師', PRT, 'PRT-001', '💼', title='助理（Zaria）'),
        Member('PRT-011', '翁千惠', '工程師', PRT, 'PRT-001', '🚢', title='船務（Joan）'),

        # ── 研發二部（RD2）— 以 HR 編輯版為準
        # 林景松（研發經理）下設 吳錦銓（研發副理）統籌中層，其下分硬體/機構/韌體/軟體/支援/研發/專案各組
        Member('RD2-001', '林景松', '副理', RD2, 'MGR-001', '🔬', title='研發經理'),
        Member('RD2-002', '吳錦銓', '副理', RD2, 'RD2-001', '🔬', title='研發副理'),
        Member('RD2-003', '張雅茹', '副課長', RD2, 'RD2-002', '🔬', title='副課長'),
        Member('RD2-004', '高迪瑭', '工程師', RD2, 'RD2-001', '📂', title='文管專員'),
        # 硬體組
        Member('RD2-005', '陳永昌', '副課長', RD2, 'RD2-002', '⚡', title='硬體副課長'),
        Member('RD2-006', '黃琮棋', '工程師', RD2, 'RD2-005', '⚡', title='硬體工程師'),
        # 機構組
        Member('RD2-007', '陳智凱', '課長', RD2, 'RD2-002', '🔧', title='機構課長'),
        Member('RD2-008', '楊文陽', '工程師', RD2, 'RD2-007', '🔧', title='機構工程師'),
        # 韌體組
        Member('RD2-009', '賴忠延', '副課長', RD2, 'RD2-002', '📡', title='韌體副課長'),
        Member('RD2-010', '張伊伸', '副課長', RD2, 'RD2-002', '📡', title='韌體副課長'),
        Member('RD2-011', '黃郁軒', '工程師', RD2, 'RD2-010', '📡', title='韌體工程師'),
        Member('RD2-012', '林義傑', '工程師', RD2, 'RD2-009', '📡', title='韌體工程師'),
        # 軟體組（掛於 RD2-009 賴忠延韌體副課長之下）
        Member('RD2-013', '陳慶維', '工程師', RD2, 'RD2-009', '💻', title='軟體工程師'),
        Member('RD2-014', '林煒宸', '工程師', RD2, 'RD2-009', '💻', title='軟體助理工程師'),
        # 技術支援
        Member('RD2-015', '余建成', '課長', RD2, 'RD2-002', '🛠️', title='技術支援課長'),
        Member('RD2-016', '馬建威', '課長', RD2, 'RD2-002', '🛠️', title='技術支援課長'),
        # 研發副課長 + 底下工程師
        Member('RD2-017', '楊政憲', '副課長', RD2, 'RD2-002', '🔬', title='研發副課長'),
        Member('RD2-018', '郭祐均', '副課長', RD2, 'RD2-002', '🔬', title='研發副課長'),
        Member('RD2-019', '林紫鈴', '副課長', RD2, 'RD2-002', '🔬', title='研發副課長'),
        Member('RD2-020', '柳帆禹', '工程師', RD2, 'RD2-003', '🔬', title='研發工程師'),
        Member('RD2-021', '宋毅軒', '工程師', RD2, 'RD2-019', '🔬', title='研發工程師'),
        Member('RD2-022', '黃振哲', '工程師', RD2, 'RD2-019', '🔬', title='研發助理工程師'),
        Member('RD2-023', '胡睿城', '工程師', RD2, 'RD2-016', '🔬', title='研發助理工程師'),
        Member('RD2-024', '陳傳宗', '工程師', RD2, 'RD2-019', '🔬', title='研發助理工程師'),
        Member('RD2-025', '江孟勳', '工程師', RD2, 'RD2-018', '🔬', title='研發助理工程師'),
        # 專案
        Member('RD2-026', '陳昱慈', '副理', RD2, 'RD2-001', '📋', title='專案副理'),
        Member('RD2-027', '王怡臻', '工程師', RD2, 'RD2-026', '📋', title='專案管理師'),
        # HR 新增成員
        Member('RD2-028', '李易勲', '工程師', RD2, 'RD2-018', '👤', title='工程師'),

        # ── 品保處（李海杖經理）
        Member('QA-001', '李海杖', '副理', QA, 'MGR-001', '🛡️', title='經理'),
        Member('QA-002', '楊沛晴', '副理', QA, 'QA-001', '🛡️', title='副理'),
        Member('QA-003', '陳昌志', '課長', QA, 'QA-002', '🛡️', title='課長'),
        Member('QA-004', '吳傑士', '課長', QA, 'QA-002', '🛡️', title='課長'),
        Member('QA-005', '林晏羽', '副課長', QA, 'QA-003', '🛡️', title='副課長'),
        Member('QA-006', '陳美燕', '工程師', QA, 'QA-003', '🛡️', title='工程師'),
        Member('QA-007', '成建煌', '工程師', QA, 'QA-003', '🛡️', title='工程師'),
        Member('QA-008', '蕭閔宗', '工程師', QA, 'QA-003', '🛡️', title='工程師'),
        Member('QA-009', '林于婷', '工程師', QA, 'QA-004', '🛡️', title='工程師'),
        Member('QA-010', '吳以群', '工程師', QA, 'QA-004', '🛡️', title='工程師'),
        Member('QA-011', '廖秋俐', '工程師', QA, 'QA-004', '🛡️', title='助理工程師'),
        Member('QA-012', '謝保廷', '工程師', QA, 'QA-004', '🛡️', title='助理工程師'),
        Member('QA-013', '楊博丞', '工程師', QA, 'QA-005', '🛡️', title='品檢員'),
        Member('QA-014', '劉芬伶', '工程師', QA, 'QA-001', '📂', title='文管專員'),
        Member('QA-015', '江燕菁', '工程師', QA, 'QA-001', '📂', title='文管專員'),
        Member('QA-016', '鄭勤潔', '工程師', QA, 'QA-005', '🛡️', title='品檢員'),

        # ════════════════════════════════════════════════
        # 加我科技 addwii（獨立子公司，直接向董事長報告）
        # ════════════════════════════════════════════════
        Member('ADW-001', '呂劉彩玲', '副理', ADDWII, 'BOARD-001', '📣', title='行銷長（CMO）'),
        Member('ADW-002', '方和傑', '副理', ADDWII, 'ADW-001', '🛒', title='電商技術總監'),
        Member('ADW-003', '楊勝凱', '副理', ADDWII, 'ADW-001', '🛍️', title='商品經理'),
        Member('ADW-004', '俞威名', '課長', ADDWII, 'ADW-001', '🖥️', title='資訊課長'),
        Member('ADW-005', '杜怡旻', '副理', ADDWII, 'ADW-001', '📒', title='主辦會計暨行政主管'),
        Member('ADW-006', '吳維禎', '工程師', ADDWII, 'ADW-001', '📱', title='社群行銷專員'),
    ]
    # ── 個資遮蔽：統一把所有中文姓名改為「姓 + OO」──
    # 例：薛秀霞 → 薛OO；張馨文 → 張OO；職稱為「董事長」「X 姓」等非人名保留
    import re as _re
    _HANZI = _re.compile(r'^[\u4e00-\u9fa5]{2,4}$')
    _EXEMPT_NAMES = {'董事長', '總經理', '經理', '協理', '副理', '課長', '專員', '工程師'}
    for _m in members:
        _nm = getattr(_m, 'name', '') or ''
        if _nm in _EXEMPT_NAMES:
            continue
        if _HANZI.match(_nm):
            _m.name = _nm[0] + 'OO'   # 保留姓（第 1 字），其餘以 OO 取代
    return members


# ═══════════════════════════════════════════
# 週目標模板（依角色推送不同內容）
# ═══════════════════════════════════════════
WEEKLY_OBJECTIVES_TEMPLATE = {
    '經理': {
        'title': '本週策略目標 — 集團經營決策',
        'description': '核准關鍵里程碑、審核各子公司交付、策略對焦',
        'kpi': '各子公司里程碑達成率 ≥ 90% / 跨公司議題 < 48hr 解除',
    },
    '副理': {
        'title': '本週部門目標 — 部門推進與跨組協調',
        'description': '推進部門里程碑、清除跨組阻塞、彙整下屬回報給上級',
        'kpi': '里程碑達成率 ≥ 90% / 跨組議題回應 < 4hr / 週報彙整完成',
    },
    '課長': {
        'title': '本週課組目標 — 工作包交付與品質',
        'description': '追蹤副課長/工程師進度、確保技術交付品質、處理技術決策',
        'kpi': '進度達成率 ≥ 85% / QA 通過率 ≥ 95% / 技術問題解決時效 < 24hr',
    },
    '副課長': {
        'title': '本週小組目標 — 任務分派與協作',
        'description': '分派具體工作給工程師、進行 Code Review、彙整小組進度',
        'kpi': '任務完成率 ≥ 90% / Review 時效 < 4hr / 阻礙解決率 100%',
    },
    '工程師': {
        'title': '本週技術目標 — 功能交付與品質',
        'description': '完成分派的開發/驗證/整合任務、撰寫測試、回報每日進度',
        'kpi': '任務完成 ≥ 80% / 測試覆蓋率 ≥ 70% / 日報完成率 100%',
    },
    '人事經理': {
        'title': '本週人事目標 — 組織效能與人員配置',
        'description': '優化組織結構、追蹤出缺勤異常、進行跨部門人力調度',
        'kpi': '出缺勤異常率 < 2% / 組織圖資料完整度 100% / 跨部門協調案數',
    },
}


if __name__ == '__main__':
    members = build_initial_org()
    print(f'總人數：{len(members)}')
    # 驗證：每個人都有 title
    for m in members:
        if not m.title or m.title == m.role:
            print(f'  警告：{m.id} {m.name} 沒有自訂 title，fallback 為 role={m.role}')
    # 展示前 10 位
    print('\n前 10 筆（姓名 / 職稱 / 部門）：')
    for m in members[:10]:
        print(f'  {m.avatar} {m.name:6s}  · {m.title:18s} · {m.dept}')
