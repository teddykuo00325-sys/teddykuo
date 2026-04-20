# -*- coding: utf-8 -*-
"""
凌策內部 CRM 營運模組
  詢問單 → 報價單 → 訂單 → 安裝記錄（完整狀態流轉）

設計參考對方團隊 lingce.db 架構，用 SQLite 單檔持久化。
所有狀態流轉都同步更新跨表（子查詢實現，因 SQLite 不支援 JOIN UPDATE）。
"""
import os, sqlite3, json, threading
from datetime import datetime, timedelta

# ══════════════════════════════════════
# AI 模組定價（與前端 AI_MODULES 一致的真實來源）
# ══════════════════════════════════════
MODULE_PRICES = {
    # 通用
    'doc': 3000, 'meeting': 3500, 'kb': 5000, 'cs': 8000,
    # 製造業
    'mat': 6000, 'po': 5500, 'sched': 8000, 'qa': 7000,
    # 買賣業
    'mkt': 4500, 'cust': 5500, 'quote': 4000, 'sales': 6500,
    # 訂單
    'order': 5000, 'eta': 4000,
}

MODULE_NAMES = {
    'doc':'AI 文件助理','meeting':'AI 會議記錄','kb':'AI 知識庫','cs':'AI 客服',
    'mat':'AI 缺料預警','po':'AI 採購建議','sched':'AI 生產排程','qa':'AI 品質分析',
    'mkt':'AI 行銷文案','cust':'AI 客戶分析','quote':'AI 報價助理','sales':'AI 銷售預測',
    'order':'AI 訂單管理','eta':'AI 交期預估',
}

def calc_quote(module_ids):
    """算月費：4 項 9 折 / 7 項 85 折"""
    list_price = sum(MODULE_PRICES.get(m, 0) for m in module_ids)
    if len(module_ids) >= 7: disc = 0.85
    elif len(module_ids) >= 4: disc = 0.90
    else: disc = 1.0
    return {
        'list_price': list_price,
        'discount_pct': round((1 - disc) * 100),
        'net_price': round(list_price * disc),
        'savings': round(list_price * (1 - disc)),
    }

# ══════════════════════════════════════
# CRMManager
# ══════════════════════════════════════
class CRMManager:
    STATUS = {
        'inquiry':       ['新詢問', '已報價', '已成交', '安裝中', '已完成', '結案'],
        'quotation':     ['草稿', '已送出', '已接受', '已拒絕'],
        'order':         ['待安裝', '安裝中', '已完成'],
        'installation':  ['待執行', '執行中', '已完成'],
    }
    INDUSTRY = ['製造業', '買賣業', '貿易業', '其他']
    SOURCE   = ['官網', 'Email', 'LINE', '電話', '手動']

    def __init__(self, db_path='chat_logs/lingce_crm.db'):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

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
                    產業別   TEXT CHECK(產業別 IN ('製造業','買賣業','貿易業','其他')),
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
        if isinstance(modules, str): modules = json.loads(modules)
        quote = calc_quote(modules)
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

    def convert_to_quote(self, inquiry_id):
        """詢問單 → 報價單（狀態同步更新為已報價）"""
        inq = self.get_inquiry(inquiry_id)
        if not inq: return {'error': '詢問單不存在'}
        if inq['狀態'] != '新詢問':
            return {'error': f'詢問單狀態為 {inq["狀態"]}，無法轉報價'}
        modules = inq['選擇模組'] or []
        q = calc_quote(modules)
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
        """報價單 → 訂單（雙向同步：報價=已接受、詢問單=已成交）"""
        q = self.get_quote(qid)
        if not q: return {'error': '報價單不存在'}
        if q['狀態'] == '已接受':
            return {'error': '此報價已接受'}
        oid = self._next_id('ORD', '訂單', '訂單編號')
        deliver = (datetime.now() + timedelta(days=14)).strftime('%Y-%m-%d')
        with self._lock, self._conn() as c:
            c.execute("""INSERT INTO 訂單
                (訂單編號,報價編號,成交金額,付款狀態,交付期限,狀態)
                VALUES (?,?,?,?,?,?)""", (
                oid, qid, q['報價金額'], '未付', deliver, '待安裝',
            ))
            c.execute('UPDATE 報價單 SET 狀態=? WHERE 報價編號=?', ('已接受', qid))
            c.execute("""UPDATE 詢問單 SET 狀態='已成交'
                         WHERE 詢問編號=(SELECT 詢問編號 FROM 報價單 WHERE 報價編號=?)""", (qid,))
        return self.get_order(oid)

    def reject_quote(self, qid, reason=''):
        with self._lock, self._conn() as c:
            c.execute('UPDATE 報價單 SET 狀態=? WHERE 報價編號=?', ('已拒絕', qid))
        return {'success': True, 'id': qid}

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
        """訂單 → 建立安裝記錄；訂單狀態 = 安裝中"""
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
        today = datetime.now().strftime('%Y-%m-%d')
        with self._lock, self._conn() as c:
            c.execute("""INSERT INTO 安裝記錄
                (安裝編號,訂單編號,客戶名稱,安裝模組,安裝狀態,安裝日期)
                VALUES (?,?,?,?,?,?)""", (
                iid, oid, company, modules, '執行中', today,
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
        with self._conn() as c:
            def count(tbl, field='狀態', value=None):
                if value is None:
                    return c.execute(f'SELECT COUNT(*) FROM {tbl}').fetchone()[0]
                return c.execute(f'SELECT COUNT(*) FROM {tbl} WHERE {field}=?', (value,)).fetchone()[0]
            total_inq = count('詢問單')
            total_qou = count('報價單')
            total_ord = count('訂單')
            total_ins = count('安裝記錄')
            mrr = c.execute("""
                SELECT COALESCE(SUM(成交金額),0) FROM 訂單 WHERE 狀態 IN ('安裝中','已完成')
            """).fetchone()[0]
            pipeline_value = c.execute("""
                SELECT COALESCE(SUM(報價金額),0) FROM 報價單 WHERE 狀態 IN ('草稿','已送出')
            """).fetchone()[0]
        return {
            'inquiries': total_inq,
            'quotes': total_qou,
            'orders': total_ord,
            'installations': total_ins,
            'mrr': round(mrr),
            'pipeline_value': round(pipeline_value),
        }

    # ══════════════════════════════════════
    # 工具
    # ══════════════════════════════════════
    def _row_to_dict(self, r, tbl):
        if not r: return None
        d = dict(r)
        # 展開 JSON 欄位
        for key in ('選擇模組', '模組清單', '安裝模組'):
            if key in d and d[key]:
                try: d[key] = json.loads(d[key])
                except Exception: pass
        # 附加模組名稱列表，方便前端顯示
        for key in ('選擇模組', '模組清單', '安裝模組'):
            if isinstance(d.get(key), list):
                d[key + '_names'] = [MODULE_NAMES.get(m, m) for m in d[key]]
        return d
