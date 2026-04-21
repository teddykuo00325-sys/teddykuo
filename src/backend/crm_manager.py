# -*- coding: utf-8 -*-
"""
凌策內部 CRM 營運模組
  詢問單 → 報價單 → 訂單 → 安裝記錄（完整狀態流轉）

設計參考對方團隊 lingce.db 架構，用 SQLite 單檔持久化。
所有狀態流轉都同步更新跨表（子查詢實現，因 SQLite 不支援 JOIN UPDATE）。
"""
import os, sqlite3, json, threading
from datetime import datetime, timedelta

# ══════════════════════════════════════════════════════════════
# 每家 tenant 賣的東西完全不同 → 各自獨立產品目錄
# ══════════════════════════════════════════════════════════════
# lingce 凌策：AI Agent 服務 (月費訂閱)
LINGCE_MODULES = {
    # 通用
    'doc':    {'name':'AI 文件助理',  'price': 3000, 'unit':'月', 'category':'通用'},
    'meeting':{'name':'AI 會議記錄',  'price': 3500, 'unit':'月', 'category':'通用'},
    'kb':     {'name':'AI 知識庫',    'price': 5000, 'unit':'月', 'category':'通用'},
    'cs':     {'name':'AI 客服',      'price': 8000, 'unit':'月', 'category':'通用'},
    # 製造業
    'mat':    {'name':'AI 缺料預警',  'price': 6000, 'unit':'月', 'category':'製造'},
    'po':     {'name':'AI 採購建議',  'price': 5500, 'unit':'月', 'category':'製造'},
    'sched':  {'name':'AI 生產排程',  'price': 8000, 'unit':'月', 'category':'製造'},
    'qa':     {'name':'AI 品質分析',  'price': 7000, 'unit':'月', 'category':'製造'},
    # 買賣業
    'mkt':    {'name':'AI 行銷文案',  'price': 4500, 'unit':'月', 'category':'買賣'},
    'cust':   {'name':'AI 客戶分析',  'price': 5500, 'unit':'月', 'category':'買賣'},
    'quote':  {'name':'AI 報價助理',  'price': 4000, 'unit':'月', 'category':'買賣'},
    'sales':  {'name':'AI 銷售預測',  'price': 6500, 'unit':'月', 'category':'買賣'},
    'order':  {'name':'AI 訂單管理',  'price': 5000, 'unit':'月', 'category':'買賣'},
    'eta':    {'name':'AI 交期預估',  'price': 4000, 'unit':'月', 'category':'買賣'},
}

# microjet 微型噴射：B2B 硬體（感測器 / 3D 列印 / MEMS 壓電微泵）
MICROJET_PRODUCTS = {
    'CJ-SENSOR-PRO':  {'name':'CurieJet Pro 精密感測器', 'price': 180000, 'unit':'台', 'category':'感測器'},
    'CJ-SENSOR-STD':  {'name':'CurieJet Std 標準版',    'price':  95000, 'unit':'台', 'category':'感測器'},
    'CT-3DP-INDUST':  {'name':'ComeTrue 工業級 3D 列印機', 'price': 850000, 'unit':'台', 'category':'3D 列印'},
    'CT-3DP-DESK':    {'name':'ComeTrue 桌機級 3D 列印機', 'price': 280000, 'unit':'台', 'category':'3D 列印'},
    'MEMS-PUMP-P760': {'name':'MEMS 壓電微泵 P760',     'price':  45000, 'unit':'顆', 'category':'微泵'},
    'MEMS-PUMP-P500': {'name':'MEMS 壓電微泵 P500',     'price':  28000, 'unit':'顆', 'category':'微泵'},
    'SVC-MAINT-YR':   {'name':'年度維護合約',           'price': 120000, 'unit':'年', 'category':'服務'},
    'SVC-OEM-INT':    {'name':'OEM 整合工程服務',       'price': 500000, 'unit':'案', 'category':'服務'},
}

# addwii 加我科技：B2C 無塵室產品 + 濾網訂閱
ADDWII_PRODUCTS = {
    'HCR-100':       {'name':'Home Clean Room HCR-100 (1~5 坪)',   'price': 28000, 'unit':'台', 'category':'清淨機'},
    'HCR-200':       {'name':'Home Clean Room HCR-200 (5~10 坪)',  'price': 42000, 'unit':'台', 'category':'清淨機'},
    'HCR-300':       {'name':'Home Clean Room HCR-300 (10~16 坪)', 'price': 68000, 'unit':'台', 'category':'清淨機'},
    'FILTER-H13':    {'name':'HEPA H13 濾網（年訂閱）',             'price':  3600, 'unit':'組', 'category':'耗材'},
    'FILTER-CARBON': {'name':'活性碳濾網（年訂閱）',                 'price':  1800, 'unit':'組', 'category':'耗材'},
    'SVC-INSTALL':   {'name':'到府安裝 + 空氣品質體檢',             'price':  2500, 'unit':'次', 'category':'服務'},
    'SVC-WARR-PLUS': {'name':'延長保固 3 年',                       'price':  4800, 'unit':'年', 'category':'服務'},
}

# 總表：tenant → catalog
PRODUCT_CATALOGS = {
    'lingce':   LINGCE_MODULES,
    'microjet': MICROJET_PRODUCTS,
    'addwii':   ADDWII_PRODUCTS,
    'weiming':  {},   # 評估中
}

# 舊版相容（保留 server.py 別的地方還在引用的命名）
MODULE_PRICES = {k: v['price'] for k, v in LINGCE_MODULES.items()}
MODULE_NAMES  = {k: v['name']  for k, v in LINGCE_MODULES.items()}


def get_catalog(tenant: str) -> dict:
    return PRODUCT_CATALOGS.get(tenant, {})


def calc_quote(module_ids, tenant: str = 'lingce', quantities: dict = None):
    """
    算價格：
    - lingce（月訂閱）：4 項 9 折 / 7 項 85 折
    - microjet/addwii（硬體）：3 件以上 95 折 / 5 件以上 92 折
    quantities: {module_id: count} 用於 B2B/B2C 硬體，預設每項 1
    """
    catalog = get_catalog(tenant)
    quantities = quantities or {}

    list_price = 0
    line_items = []
    for mid in module_ids:
        item = catalog.get(mid)
        if not item:
            continue
        qty = quantities.get(mid, 1)
        subtotal = item['price'] * qty
        list_price += subtotal
        line_items.append({
            'id': mid, 'name': item['name'], 'unit_price': item['price'],
            'qty': qty, 'subtotal': subtotal, 'category': item.get('category', ''),
        })

    # 折扣策略依 tenant 不同
    if tenant == 'lingce':
        if   len(module_ids) >= 7: disc = 0.85
        elif len(module_ids) >= 4: disc = 0.90
        else: disc = 1.0
    else:   # microjet / addwii：硬體量販
        total_qty = sum(quantities.get(m, 1) for m in module_ids)
        if   total_qty >= 5: disc = 0.92
        elif total_qty >= 3: disc = 0.95
        else: disc = 1.0

    net = round(list_price * disc)
    return {
        'tenant': tenant,
        'list_price':   list_price,
        'discount_pct': round((1 - disc) * 100),
        'net_price':    net,
        'savings':      list_price - net,
        'line_items':   line_items,
    }

# ══════════════════════════════════════
# CRMManager
# ══════════════════════════════════════
class CRMManager:
    STATUS = {
        'inquiry':       ['新詢問', '已報價', '已成交', '安裝中', '已完成', '結案', '已拒絕'],
        'quotation':     ['草稿', '已送出', '已接受', '已拒絕'],
        'order':         ['待安裝', '安裝中', '已完成'],
        'installation':  ['待執行', '執行中', '已完成'],
    }
    # 擴充產業別（原本死 CHECK 已放寬）
    INDUSTRY = ['製造業', '買賣業', '貿易業', 'B2C 品牌', 'AI 服務', '企業顧問', '個人消費者', '其他']
    SOURCE   = ['官網', 'Email', 'LINE', '電話', '手動', '實體門市', '展會']

    def __init__(self, db_path='chat_logs/lingce_crm.db', tenant: str = 'lingce'):
        os.makedirs(os.path.dirname(db_path) or '.', exist_ok=True)
        self.db_path = db_path
        self.tenant = tenant
        self._lock = threading.Lock()
        self._init_db()
        self._migrate_schema()

    def _conn(self):
        c = sqlite3.connect(self.db_path)
        c.row_factory = sqlite3.Row
        return c

    def _init_db(self):
        with self._conn() as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS 詢問單 (
                    詢問編號 TEXT PRIMARY KEY,
                    公司名稱 TEXT NOT NULL,
                    聯絡人   TEXT NOT NULL,
                    電話     TEXT,
                    Email    TEXT NOT NULL,
                    產業別   TEXT,
                    需求說明 TEXT,
                    選擇模組 TEXT,
                    報價金額 REAL,
                    狀態     TEXT DEFAULT '新詢問',
                    來源     TEXT DEFAULT '官網',
                    建立時間 TEXT DEFAULT CURRENT_TIMESTAMP,
                    備註     TEXT
                );
                CREATE TABLE IF NOT EXISTS 報價單 (
                    報價編號 TEXT PRIMARY KEY,
                    詢問編號 TEXT NOT NULL,
                    模組清單 TEXT,
                    原價     REAL,
                    折扣     REAL,
                    報價金額 REAL,
                    有效期限 TEXT,
                    狀態     TEXT DEFAULT '草稿',
                    建立時間 TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (詢問編號) REFERENCES 詢問單(詢問編號)
                );
                CREATE TABLE IF NOT EXISTS 訂單 (
                    訂單編號 TEXT PRIMARY KEY,
                    報價編號 TEXT NOT NULL,
                    成交金額 REAL,
                    付款狀態 TEXT DEFAULT '未付',
                    交付期限 TEXT,
                    狀態     TEXT DEFAULT '待安裝',
                    建立時間 TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (報價編號) REFERENCES 報價單(報價編號)
                );
                CREATE TABLE IF NOT EXISTS 安裝記錄 (
                    安裝編號 TEXT PRIMARY KEY,
                    訂單編號 TEXT NOT NULL,
                    客戶名稱 TEXT,
                    安裝模組 TEXT,
                    安裝狀態 TEXT DEFAULT '待執行',
                    負責Agent TEXT DEFAULT 'AI Deploy Agent',
                    安裝日期 TEXT,
                    備註     TEXT,
                    建立時間 TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (訂單編號) REFERENCES 訂單(訂單編號)
                );
            """)

    # ── 舊資料庫 schema 升級 ──
    def _migrate_schema(self):
        """
        1. 既有 DB 若仍有 CHECK(產業別 IN ...)，建新表搬資料
        2. 報價單 / 訂單 / 安裝記錄 缺 備註 欄位 → ALTER TABLE ADD COLUMN
        """
        with self._lock, self._conn() as c:
            # Step 1: 詢問單 CHECK 限制
            row = c.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='詢問單'"
            ).fetchone()
            if row and 'CHECK' in (row[0] or ''):
                c.executescript("""
                    CREATE TABLE 詢問單_new (
                        詢問編號 TEXT PRIMARY KEY,
                        公司名稱 TEXT NOT NULL,
                        聯絡人   TEXT NOT NULL,
                        電話     TEXT,
                        Email    TEXT NOT NULL,
                        產業別   TEXT,
                        需求說明 TEXT,
                        選擇模組 TEXT,
                        報價金額 REAL,
                        狀態     TEXT DEFAULT '新詢問',
                        來源     TEXT DEFAULT '官網',
                        建立時間 TEXT DEFAULT CURRENT_TIMESTAMP,
                        備註     TEXT
                    );
                    INSERT INTO 詢問單_new SELECT * FROM 詢問單;
                    DROP TABLE 詢問單;
                    ALTER TABLE 詢問單_new RENAME TO 詢問單;
                """)
                print(f'[CRM] 遷移 {self.tenant} 詢問單 schema 完成（移除 CHECK 產業別限制）')

            # Step 2: 補欄位（ALTER TABLE ADD COLUMN IF NOT EXISTS 的土炮版）
            def ensure_col(table, col, ddl):
                cols = [r['name'] for r in c.execute(f'PRAGMA table_info({table})').fetchall()]
                if col not in cols:
                    c.execute(f'ALTER TABLE {table} ADD COLUMN {col} {ddl}')
                    print(f'[CRM] {self.tenant} {table} 新增欄位 {col}')
            ensure_col('報價單', '備註', 'TEXT')
            ensure_col('訂單',   '備註', 'TEXT')
            ensure_col('訂單',   '月費', 'REAL')   # MRR 用：若為月訂閱則填
            ensure_col('安裝記錄','備註','TEXT')

    # ── 流水號 ──
    def _next_id(self, prefix, table, field):
        ym = datetime.now().strftime('%Y%m')
        with self._conn() as c:
            n = c.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {field} LIKE ?",
                (f'{prefix}-{ym}-%',)
            ).fetchone()[0]
        return f'{prefix}-{ym}-{n+1:04d}'

    # ══════════════════════════════════════
    # 詢問單
    # ══════════════════════════════════════
    def create_inquiry(self, data):
        modules = data.get('選擇模組') or []
        quantities = data.get('數量') or {}
        if isinstance(modules, str): modules = json.loads(modules)
        if isinstance(quantities, str): quantities = json.loads(quantities)
        quote = calc_quote(modules, tenant=self.tenant, quantities=quantities)
        iid = self._next_id('INQ', '詢問單', '詢問編號')
        with self._lock, self._conn() as c:
            c.execute("""INSERT INTO 詢問單
                (詢問編號,公司名稱,聯絡人,電話,Email,產業別,需求說明,選擇模組,報價金額,狀態,來源,備註)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", (
                iid,
                data.get('公司名稱',''), data.get('聯絡人',''),
                data.get('電話',''), data.get('Email',''),
                data.get('產業別','其他'), data.get('需求說明',''),
                json.dumps(modules, ensure_ascii=False),
                quote['net_price'],
                '新詢問',
                data.get('來源','手動'),
                data.get('備註',''),
            ))
        return self.get_inquiry(iid)

    def get_inquiry(self, iid):
        with self._conn() as c:
            r = c.execute('SELECT * FROM 詢問單 WHERE 詢問編號=?', (iid,)).fetchone()
            return self._row_to_dict(r, '詢問單')

    def list_inquiries(self, status=None):
        with self._conn() as c:
            if status:
                rows = c.execute('SELECT * FROM 詢問單 WHERE 狀態=? ORDER BY 建立時間 DESC', (status,)).fetchall()
            else:
                rows = c.execute('SELECT * FROM 詢問單 ORDER BY 建立時間 DESC').fetchall()
            return [self._row_to_dict(r, '詢問單') for r in rows]

    def convert_to_quote(self, inquiry_id, quantities: dict = None):
        """
        詢問單 → 報價單（狀態同步更新為已報價）
        B1 fix: 允許「新詢問」「已拒絕」狀態重報價；「已成交/安裝中/已完成」擋下
        """
        inq = self.get_inquiry(inquiry_id)
        if not inq: return {'error': '詢問單不存在'}
        if inq['狀態'] in ('已成交', '安裝中', '已完成', '結案'):
            return {'error': f'詢問單狀態為 {inq["狀態"]}，已進入後段流程，無法重報價'}
        modules = inq['選擇模組'] or []
        quantities = quantities or {}
        q = calc_quote(modules, tenant=self.tenant, quantities=quantities)
        qid = self._next_id('QUO', '報價單', '報價編號')
        expiry = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
        with self._lock, self._conn() as c:
            c.execute("""INSERT INTO 報價單
                (報價編號,詢問編號,模組清單,原價,折扣,報價金額,有效期限,狀態)
                VALUES (?,?,?,?,?,?,?,?)""", (
                qid, inquiry_id,
                json.dumps(modules, ensure_ascii=False),
                q['list_price'], q['savings'], q['net_price'],
                expiry, '已送出',
            ))
            c.execute('UPDATE 詢問單 SET 狀態=? WHERE 詢問編號=?', ('已報價', inquiry_id))
        return self.get_quote(qid)

    # ══════════════════════════════════════
    # 報價單
    # ══════════════════════════════════════
    def get_quote(self, qid):
        with self._conn() as c:
            r = c.execute('SELECT * FROM 報價單 WHERE 報價編號=?', (qid,)).fetchone()
            return self._row_to_dict(r, '報價單')

    def list_quotes(self, status=None):
        with self._conn() as c:
            sql = 'SELECT * FROM 報價單 ORDER BY 建立時間 DESC'
            args = ()
            if status:
                sql = 'SELECT * FROM 報價單 WHERE 狀態=? ORDER BY 建立時間 DESC'
                args = (status,)
            return [self._row_to_dict(r, '報價單') for r in c.execute(sql, args).fetchall()]

    def accept_quote(self, qid):
        """
        報價單 → 訂單（雙向同步：報價=已接受、詢問單=已成交）
        B1 fix: 「已接受」或「已拒絕」皆不可再接受
        """
        q = self.get_quote(qid)
        if not q: return {'error': '報價單不存在'}
        if q['狀態'] in ('已接受', '已拒絕'):
            return {'error': f'此報價已是 {q["狀態"]} 狀態，不可再接受'}
        oid = self._next_id('ORD', '訂單', '訂單編號')
        deliver = (datetime.now() + timedelta(days=14)).strftime('%Y-%m-%d')
        # lingce 是月訂閱 → 記錄月費（MRR 用）；microjet/addwii 是硬體一次性銷售
        monthly_fee = q['報價金額'] if self.tenant == 'lingce' else 0
        with self._lock, self._conn() as c:
            c.execute("""INSERT INTO 訂單
                (訂單編號,報價編號,成交金額,付款狀態,交付期限,狀態,月費)
                VALUES (?,?,?,?,?,?,?)""", (
                oid, qid, q['報價金額'], '未付', deliver, '待安裝', monthly_fee,
            ))
            c.execute('UPDATE 報價單 SET 狀態=? WHERE 報價編號=?', ('已接受', qid))
            c.execute("""UPDATE 詢問單 SET 狀態='已成交'
                         WHERE 詢問編號=(SELECT 詢問編號 FROM 報價單 WHERE 報價編號=?)""", (qid,))
        return self.get_order(oid)

    def reject_quote(self, qid, reason=''):
        """
        B2 fix: reason 寫入 備註 + 詢問單同步回「已拒絕」
        """
        q = self.get_quote(qid)
        if not q: return {'error': '報價單不存在'}
        with self._lock, self._conn() as c:
            c.execute('UPDATE 報價單 SET 狀態=?, 備註=? WHERE 報價編號=?',
                      ('已拒絕', f'[{datetime.now().strftime("%Y-%m-%d %H:%M")}] 拒絕原因：{reason or "未填寫"}', qid))
            # 反查詢問單，狀態同步
            c.execute("""UPDATE 詢問單 SET 狀態='已拒絕'
                         WHERE 詢問編號=(SELECT 詢問編號 FROM 報價單 WHERE 報價編號=?)""", (qid,))
        return {'success': True, 'id': qid, 'reason_logged': bool(reason)}

    # ══════════════════════════════════════
    # 訂單
    # ══════════════════════════════════════
    def get_order(self, oid):
        with self._conn() as c:
            r = c.execute('SELECT * FROM 訂單 WHERE 訂單編號=?', (oid,)).fetchone()
            return self._row_to_dict(r, '訂單')

    def list_orders(self, status=None):
        with self._conn() as c:
            sql = 'SELECT * FROM 訂單 ORDER BY 建立時間 DESC'
            args = ()
            if status:
                sql = 'SELECT * FROM 訂單 WHERE 狀態=? ORDER BY 建立時間 DESC'
                args = (status,)
            return [self._row_to_dict(r, '訂單') for r in c.execute(sql, args).fetchall()]

    def start_installation(self, oid):
        """訂單 → 建立安裝記錄；訂單狀態 = 安裝中
        B3 fix: 安裝日期使用訂單的「交付期限」而非當天
        """
        o = self.get_order(oid)
        if not o: return {'error': '訂單不存在'}
        if o['狀態'] != '待安裝':
            return {'error': f'訂單狀態 {o["狀態"]} 不可建立安裝'}
        # 反查公司名稱 + 模組
        with self._conn() as c:
            row = c.execute("""
                SELECT i.公司名稱, q.模組清單 FROM 訂單 o
                JOIN 報價單 q ON o.報價編號 = q.報價編號
                JOIN 詢問單 i ON q.詢問編號 = i.詢問編號
                WHERE o.訂單編號=?
            """, (oid,)).fetchone()
            company = row['公司名稱'] if row else '?'
            modules = row['模組清單'] if row else '[]'
        iid = self._next_id('INS', '安裝記錄', '安裝編號')
        # B3: 優先用訂單交付期限（若在未來），否則取今天
        today_str = datetime.now().strftime('%Y-%m-%d')
        install_date = o.get('交付期限') or today_str
        try:
            if datetime.strptime(install_date, '%Y-%m-%d') < datetime.now():
                install_date = today_str
        except Exception:
            install_date = today_str
        with self._lock, self._conn() as c:
            c.execute("""INSERT INTO 安裝記錄
                (安裝編號,訂單編號,客戶名稱,安裝模組,安裝狀態,安裝日期)
                VALUES (?,?,?,?,?,?)""", (
                iid, oid, company, modules, '執行中', install_date,
            ))
            c.execute('UPDATE 訂單 SET 狀態=? WHERE 訂單編號=?', ('安裝中', oid))
            c.execute("""UPDATE 詢問單 SET 狀態='安裝中'
                         WHERE 詢問編號=(
                             SELECT i2.詢問編號 FROM 報價單 q2
                             JOIN 訂單 o2 ON q2.報價編號 = o2.報價編號
                             JOIN 詢問單 i2 ON q2.詢問編號 = i2.詢問編號
                             WHERE o2.訂單編號=?
                         )""", (oid,))
        return self.get_installation(iid)

    # ══════════════════════════════════════
    # 安裝記錄
    # ══════════════════════════════════════
    def get_installation(self, iid):
        with self._conn() as c:
            r = c.execute('SELECT * FROM 安裝記錄 WHERE 安裝編號=?', (iid,)).fetchone()
            return self._row_to_dict(r, '安裝記錄')

    def list_installations(self, status=None):
        with self._conn() as c:
            sql = 'SELECT * FROM 安裝記錄 ORDER BY 建立時間 DESC'
            args = ()
            if status:
                sql = 'SELECT * FROM 安裝記錄 WHERE 安裝狀態=? ORDER BY 建立時間 DESC'
                args = (status,)
            return [self._row_to_dict(r, '安裝記錄') for r in c.execute(sql, args).fetchall()]

    def complete_installation(self, iid):
        """三表同步更新為已完成"""
        ins = self.get_installation(iid)
        if not ins: return {'error': '安裝記錄不存在'}
        with self._lock, self._conn() as c:
            c.execute('UPDATE 安裝記錄 SET 安裝狀態=? WHERE 安裝編號=?', ('已完成', iid))
            c.execute("""UPDATE 訂單 SET 狀態='已完成'
                         WHERE 訂單編號=(SELECT 訂單編號 FROM 安裝記錄 WHERE 安裝編號=?)""", (iid,))
            c.execute("""UPDATE 詢問單 SET 狀態='已完成'
                         WHERE 詢問編號=(
                             SELECT i2.詢問編號 FROM 安裝記錄 ins
                             JOIN 訂單 o2 ON ins.訂單編號 = o2.訂單編號
                             JOIN 報價單 q2 ON o2.報價編號 = q2.報價編號
                             JOIN 詢問單 i2 ON q2.詢問編號 = i2.詢問編號
                             WHERE ins.安裝編號=?
                         )""", (iid,))
        return self.get_installation(iid)

    # ══════════════════════════════════════
    # 統計
    # ══════════════════════════════════════
    def summary(self):
        """
        B4 fix: MRR 改為「月費 × 在活狀態訂單數」
        B5 fix: pipeline_value 改為報價單的實際金額（草稿+已送出）
        """
        with self._conn() as c:
            def count(tbl, field='狀態', value=None):
                if value is None:
                    return c.execute(f'SELECT COUNT(*) FROM {tbl}').fetchone()[0]
                return c.execute(f'SELECT COUNT(*) FROM {tbl} WHERE {field}=?', (value,)).fetchone()[0]
            total_inq = count('詢問單')
            total_qou = count('報價單')
            total_ord = count('訂單')
            total_ins = count('安裝記錄')
            accepted_orders = count('訂單', '狀態', '已完成') + count('訂單', '狀態', '安裝中') + count('訂單', '狀態', '待安裝')
            # B4: MRR = lingce 訂單的月費加總（microjet/addwii 是一次性銷售，MRR=0）
            mrr = c.execute("""
                SELECT COALESCE(SUM(月費),0) FROM 訂單 WHERE 狀態 IN ('安裝中','已完成','待安裝')
            """).fetchone()[0] or 0
            # 一次性銷售累計（microjet/addwii 的「已成交營收」）
            one_time_rev = c.execute("""
                SELECT COALESCE(SUM(成交金額),0) FROM 訂單
                WHERE 狀態 IN ('安裝中','已完成','待安裝')
                  AND (月費 IS NULL OR 月費 = 0)
            """).fetchone()[0] or 0
            # B5: pipeline 只算「進行中」的報價實際金額
            pipeline_value = c.execute("""
                SELECT COALESCE(SUM(報價金額),0) FROM 報價單 WHERE 狀態 IN ('草稿','已送出')
            """).fetchone()[0] or 0
            # 成交率（已接受 / 總報價數）
            accepted = count('報價單', '狀態', '已接受')
            win_rate = round(accepted / max(total_qou, 1) * 100, 1)
        return {
            'tenant': self.tenant,
            'inquiries': total_inq,
            'quotes': total_qou,
            'orders': total_ord,
            'installations': total_ins,
            'mrr': round(mrr),                    # 月訂閱收入（lingce 專屬）
            'one_time_revenue': round(one_time_rev),  # 一次性銷售累計（microjet/addwii）
            'pipeline_value': round(pipeline_value),  # 進行中報價金額
            'win_rate_pct': win_rate,
            'accepted_orders': accepted_orders,
        }

    # ══════════════════════════════════════
    # 工具
    # ══════════════════════════════════════
    def _row_to_dict(self, r, tbl):
        if not r: return None
        d = dict(r)
        catalog = get_catalog(self.tenant)
        # 展開 JSON 欄位
        for key in ('選擇模組', '模組清單', '安裝模組'):
            if key in d and d[key]:
                try: d[key] = json.loads(d[key])
                except Exception: pass
        # 附加模組/產品名稱列表（用 tenant 自己的 catalog）
        for key in ('選擇模組', '模組清單', '安裝模組'):
            if isinstance(d.get(key), list):
                d[key + '_names'] = [
                    (catalog.get(m, {}).get('name') or MODULE_NAMES.get(m, m))
                    for m in d[key]
                ]
        return d
