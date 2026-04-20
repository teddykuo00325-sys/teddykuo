# -*- coding: utf-8 -*-
"""
凌策 PDF 匯出模組
  1. 報價單 PDF（CRM 用）
  2. B2B 提案書 PDF（驗收中心 proposal 場景用）
  3. 出缺勤報表 PDF（HR 用）

用 reportlab 原生繪圖 + 內嵌字型；中文字型使用 STSong-Light (Adobe CID) 免下載。
"""
import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm, mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, PageBreak)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

# 註冊中文 CID 字型（ReportLab 內建，**完全不需安裝任何字型檔**）
# 優先繁中 MSung-Light (Adobe-CNS1)，不可用時退回簡中 STSong-Light (Adobe-GB1)
CN_FONT = 'Helvetica'
for _cid_name in ('MSung-Light', 'STSong-Light'):
    try:
        pdfmetrics.registerFont(UnicodeCIDFont(_cid_name))
        CN_FONT = _cid_name
        print(f'[PDF] 字型 {_cid_name} 註冊成功（無需外部字型檔）')
        break
    except Exception:
        continue


def _styles():
    ss = getSampleStyleSheet()
    title = ParagraphStyle('CNTitle', parent=ss['Title'], fontName=CN_FONT,
                            fontSize=20, leading=26, alignment=TA_CENTER,
                            textColor=colors.HexColor('#1e3a8a'))
    h2 = ParagraphStyle('CNH2', parent=ss['Heading2'], fontName=CN_FONT,
                        fontSize=13, leading=18, textColor=colors.HexColor('#2563eb'),
                        spaceBefore=8, spaceAfter=4)
    body = ParagraphStyle('CNBody', parent=ss['BodyText'], fontName=CN_FONT,
                          fontSize=10, leading=15)
    small = ParagraphStyle('CNSmall', parent=body, fontSize=8, textColor=colors.grey)
    right = ParagraphStyle('CNRight', parent=body, alignment=TA_RIGHT)
    return {'title': title, 'h2': h2, 'body': body, 'small': small, 'right': right}


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont(CN_FONT, 8)
    canvas.setFillColor(colors.grey)
    canvas.drawString(2*cm, 1*cm,
        '凌策 AI 顧問 · LINGCE AI CONSULTING · 由 AI Agent 自動生成')
    canvas.drawRightString(A4[0] - 2*cm, 1*cm, f'第 {doc.page} 頁')
    canvas.restoreState()


# ============================================================
# 1. 報價單 PDF（CRM 用）
# ============================================================
def build_quote_pdf(quote_dict, inquiry_dict=None, module_names=None):
    """
    quote_dict: { 報價編號, 詢問編號, 模組清單, 模組清單_names, 原價, 折扣, 報價金額, 有效期限, 狀態, 建立時間 }
    inquiry_dict (optional): { 公司名稱, 聯絡人, Email, 電話, 產業別 }
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            topMargin=2*cm, bottomMargin=2*cm,
                            leftMargin=2*cm, rightMargin=2*cm)
    st = _styles()
    flow = []

    # 標題
    flow.append(Paragraph('凌策 AI 顧問 · 報價單', st['title']))
    flow.append(Paragraph(f"QUOTATION · {quote_dict.get('報價編號','-')}", st['small']))
    flow.append(Spacer(1, 0.6*cm))

    # 客戶資訊區
    flow.append(Paragraph('客戶資訊', st['h2']))
    if inquiry_dict:
        ci = inquiry_dict
        info_data = [
            ['公司名稱', ci.get('公司名稱','-')],
            ['聯絡人',   ci.get('聯絡人','-')],
            ['Email',    ci.get('Email','-')],
            ['電話',     ci.get('電話','-') or '-'],
            ['產業別',   ci.get('產業別','-')],
            ['對應詢問單', quote_dict.get('詢問編號','-')],
        ]
    else:
        info_data = [['對應詢問單', quote_dict.get('詢問編號','-')]]
    tbl = Table(info_data, colWidths=[3.5*cm, 13*cm])
    tbl.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), CN_FONT),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#eff6ff')),
        ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#93c5fd')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    flow.append(tbl)
    flow.append(Spacer(1, 0.6*cm))

    # 報價明細
    flow.append(Paragraph('報價明細', st['h2']))
    mods = quote_dict.get('模組清單_names') or quote_dict.get('模組清單') or []
    mod_rows = [['#', 'AI 模組', '月費 (NT$)']]
    try:
        from crm_manager import MODULE_PRICES, MODULE_NAMES
        for i, name_or_id in enumerate(mods, 1):
            # 若是 ID 就翻成名稱
            if module_names:
                name = module_names.get(name_or_id, name_or_id)
                price = None
            else:
                name = MODULE_NAMES.get(name_or_id, name_or_id)
                # 反查 price by id — mods 可能已是 name
                price = MODULE_PRICES.get(name_or_id)
                if price is None:
                    # name → id 反查
                    for mid, mn in MODULE_NAMES.items():
                        if mn == name_or_id:
                            price = MODULE_PRICES.get(mid)
                            name = mn
                            break
            mod_rows.append([str(i), name, f'{price:,}' if price else '-'])
    except Exception:
        for i, name in enumerate(mods, 1):
            mod_rows.append([str(i), str(name), '-'])

    tbl2 = Table(mod_rows, colWidths=[1.5*cm, 11*cm, 4*cm])
    tbl2.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), CN_FONT),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e3a8a')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTSIZE', (0,0), (-1,0), 11),
        ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#93c5fd')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 6),
        ('ALIGN', (0,0), (0,-1), 'CENTER'),
        ('ALIGN', (2,0), (2,-1), 'RIGHT'),
    ]))
    flow.append(tbl2)
    flow.append(Spacer(1, 0.4*cm))

    # 金額總結
    total = {
        '列表價（月費小計）': f"NT$ {quote_dict.get('原價',0):,.0f}",
        '組合折扣':         f"-NT$ {quote_dict.get('折扣',0):,.0f}",
        '實際月費':         f"NT$ {quote_dict.get('報價金額',0):,.0f}",
        '有效期限':         quote_dict.get('有效期限','-'),
    }
    sum_rows = [[k, v] for k, v in total.items()]
    tbl3 = Table(sum_rows, colWidths=[4*cm, 12.5*cm])
    tbl3.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), CN_FONT),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('FONTSIZE', (0,2), (-1,2), 14),
        ('BACKGROUND', (0,2), (-1,2), colors.HexColor('#fef3c7')),
        ('TEXTCOLOR', (1,2), (1,2), colors.HexColor('#b45309')),
        ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#cbd5e1')),
        ('PADDING', (0,0), (-1,-1), 8),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('FONTNAME', (1,2), (1,2), CN_FONT),
    ]))
    flow.append(tbl3)
    flow.append(Spacer(1, 0.6*cm))

    # 條款
    flow.append(Paragraph('服務條款', st['h2']))
    flow.append(Paragraph('▸ 24 小時內由凌策 AI Deploy Agent 自動完成部署', st['body']))
    flow.append(Paragraph('▸ 30 天滿意保證，不合用可無痛退訂', st['body']))
    flow.append(Paragraph('▸ 1 年免費更新 + 新功能持續推送', st['body']))
    flow.append(Paragraph('▸ AI 客服 Agent 全年無休（每日 24 小時 × 每週 7 天），隨時自動回覆產品與使用問題', st['body']))
    flow.append(Spacer(1, 0.3*cm))
    flow.append(Paragraph(f'產出時間：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', st['small']))

    doc.build(flow, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


# ============================================================
# 1b. addwii 場域無塵室報價單（B2C 給終端客戶）
# 範例：陳先生 12 坪客廳無塵室 NT$ 168,000
# ============================================================
def _addwii_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont(CN_FONT, 8)
    canvas.setFillColor(colors.grey)
    canvas.drawString(2*cm, 1*cm,
        'addwii 加我科技 · Clean Room · 六款場域無塵室 · addwiicleanroom.com')
    canvas.drawRightString(A4[0] - 2*cm, 1*cm, f'第 {doc.page} 頁')
    canvas.restoreState()


def build_addwii_order_pdf(scenario_dict):
    """
    addwii 給 B2C 終端客戶的場域無塵室報價 / 訂單 PDF
    scenario_dict 來自 procurement_mgr.get_scenario()：
      包含 customer / space / inquiry / quote / order / bom / milestones
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            topMargin=2*cm, bottomMargin=2*cm,
                            leftMargin=2*cm, rightMargin=2*cm)
    st = _styles()
    st['title'].textColor = colors.HexColor('#0369a1')
    st['h2'].textColor = colors.HexColor('#0284c7')
    flow = []

    s = scenario_dict
    cust = s.get('customer', {})
    space = s.get('space', {})
    quote = s.get('quote', {})
    order = s.get('order', {})
    bom = s.get('bom', [])

    flow.append(Paragraph('addwii 加我科技 · 場域無塵室報價單', st['title']))
    flow.append(Paragraph(
        f"QUOTATION · {quote.get('id','-')}   |   訂單：{order.get('id','-')}", st['small']))
    flow.append(Spacer(1, 0.6*cm))

    flow.append(Paragraph('客戶資訊', st['h2']))
    info = [
        ['客戶姓名', cust.get('name','-')],
        ['聯絡電話', cust.get('phone','-')],
        ['安裝地址', cust.get('address','-')],
        ['來源通路', cust.get('channel','-')],
    ]
    tbl = Table(info, colWidths=[3.5*cm, 13*cm])
    tbl.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), CN_FONT),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#e0f2fe')),
        ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#7dd3fc')),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    flow.append(tbl)
    flow.append(Spacer(1, 0.4*cm))

    flow.append(Paragraph('施作空間', st['h2']))
    sp = [
        ['坪數', f"{space.get('area_ping','-')} 坪 ({space.get('area_m2','-')} m²)"],
        ['樓高', f"{space.get('height_m','-')} m"],
        ['選用場域', space.get('scenario','-')],
    ]
    tbl = Table(sp, colWidths=[3.5*cm, 13*cm])
    tbl.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), CN_FONT),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#e0f2fe')),
        ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#7dd3fc')),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    flow.append(tbl)
    flow.append(Spacer(1, 0.4*cm))

    flow.append(Paragraph('產品規格（來源：addwii 官網）', st['h2']))
    spec_rows = [
        ['過濾頻率', '每小時 52 次（一般清淨機 2~4 次）'],
        ['低速噪音', '39 dB（微風聲等級）'],
        ['濾網系統', '四層：初級 + 活性碳除臭 + HEPA H13 99.97% + UV 殺菌'],
        ['環境感測', 'ZS3/ZS2 空氣品質偵測器 + 多合一環境感測器 + 氣流感測器'],
        ['核心感測供應', 'microjet CurieJet P760（PM+VOC）/ P710（PM2.5 備援）'],
    ]
    tbl = Table(spec_rows, colWidths=[3.5*cm, 13*cm])
    tbl.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), CN_FONT),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#f0f9ff')),
        ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#bae6fd')),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    flow.append(tbl)
    flow.append(Spacer(1, 0.4*cm))

    flow.append(Paragraph('配置清單（BOM）', st['h2']))
    mod_rows = [['#', 'SKU', '品名', '供貨', '數量', '單價 (NT$)', '小計 (NT$)']]
    total = 0
    for i, b in enumerate(bom, 1):
        sub = (b.get('qty',0) or 0) * (b.get('unit',0) or 0)
        total += sub
        mod_rows.append([
            str(i), b.get('sku','-'), b.get('name','-'), b.get('supplier','-'),
            str(b.get('qty','-')), f"{b.get('unit',0):,}", f"{sub:,}",
        ])
    tbl = Table(mod_rows, colWidths=[0.8*cm, 2.6*cm, 5*cm, 3.4*cm, 1.4*cm, 2*cm, 2*cm])
    tbl.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), CN_FONT),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0284c7')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#7dd3fc')),
        ('ALIGN', (0,0), (0,-1), 'CENTER'),
        ('ALIGN', (4,0), (-1,-1), 'RIGHT'),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    flow.append(tbl)
    flow.append(Spacer(1, 0.4*cm))

    flow.append(Paragraph('金額總結', st['h2']))
    deposit = order.get('deposit', 0) or 0
    amount = order.get('amount', 0) or 0
    balance = amount - deposit
    total_rows = [
        ['配置清單小計',  f"NT$ {total:,}"],
        ['整機報價',      f"NT$ {amount:,}"],
        ['訂金（50%）',   f"NT$ {deposit:,}"],
        ['安裝完成尾款',  f"NT$ {balance:,}"],
        ['有效期限',      quote.get('validity','-')],
    ]
    tbl = Table(total_rows, colWidths=[5*cm, 11*cm])
    tbl.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), CN_FONT),
        ('FONTSIZE', (0,0), (-1,-1), 11),
        ('FONTSIZE', (0,1), (-1,1), 14),
        ('BACKGROUND', (0,1), (-1,1), colors.HexColor('#fef3c7')),
        ('TEXTCOLOR', (1,1), (1,1), colors.HexColor('#b45309')),
        ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#cbd5e1')),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('PADDING', (0,0), (-1,-1), 7),
    ]))
    flow.append(tbl)
    flow.append(Spacer(1, 0.4*cm))

    flow.append(Paragraph('安裝里程碑', st['h2']))
    for m in s.get('milestones', []):
        mark = '[v]' if m.get('done') else ('[*]' if m.get('current') else '[ ]')
        flow.append(Paragraph(
            f"{mark} {m.get('date','-')} · {m.get('label','-')}", st['body']))
    flow.append(Spacer(1, 0.3*cm))

    flow.append(Paragraph('服務條款', st['h2']))
    flow.append(Paragraph('▸ 主機保固 2 年、到府維修服務', st['body']))
    flow.append(Paragraph('▸ HEPA 濾網建議每 6~12 個月更換，addwii 免費寄送到府', st['body']))
    flow.append(Paragraph('▸ 核心感測器由 microjet（CurieJet）供貨，出貨序號永久綁定至此安裝地址', st['body']))
    flow.append(Paragraph('▸ 訂金收齊後排程製造，需向 microjet 採購感測器（約 4 天前置）', st['body']))
    flow.append(Spacer(1, 0.3*cm))
    flow.append(Paragraph(f'產出時間：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', st['small']))

    doc.build(flow, onFirstPage=_addwii_footer, onLaterPages=_addwii_footer)
    return buf.getvalue()


# ============================================================
# 1c. microjet → addwii B2B 零組件出貨單（含感測器序號）
# ============================================================
def _microjet_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont(CN_FONT, 8)
    canvas.setFillColor(colors.grey)
    canvas.drawString(2*cm, 1*cm,
        'MicroJet Technology · CurieJet® Sensor Modules · microjet.com.tw')
    canvas.drawRightString(A4[0] - 2*cm, 1*cm, f'第 {doc.page} 頁')
    canvas.restoreState()


def build_microjet_po_pdf(scenario_dict):
    """microjet 給下游品牌 (addwii) 的 B2B 採購 / 出貨單 PDF（含序號綁定）"""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            topMargin=2*cm, bottomMargin=2*cm,
                            leftMargin=2*cm, rightMargin=2*cm)
    st = _styles()
    st['title'].textColor = colors.HexColor('#b45309')
    st['h2'].textColor = colors.HexColor('#d97706')
    flow = []

    s = scenario_dict
    po = s.get('purchase_to_microjet', {})
    cust = s.get('customer', {})
    order = s.get('order', {})
    serials = [x for x in s.get('sensor_serials', [])
               if x.get('bound_to_order') == order.get('id')]

    shipped = (po.get('status') == '已出貨')
    kind = '出貨單（含序號綁定）' if shipped else '採購確認單'
    flow.append(Paragraph(f'MicroJet Technology · B2B {kind}', st['title']))
    flow.append(Paragraph(f"PO · {po.get('po_id','-')}", st['small']))
    flow.append(Spacer(1, 0.6*cm))

    flow.append(Paragraph('交易雙方', st['h2']))
    parties = [
        ['供貨方', 'MicroJet Technology 研能科技 (CurieJet® 感測器子品牌)'],
        ['採購方', 'addwii 加我科技 · 場域無塵室品牌 (6 人組織)'],
        ['採購單號', po.get('po_id','-')],
        ['下單日期', po.get('date','-')],
        ['預計出貨', po.get('expected_delivery','-')],
        ['當前狀態', po.get('status','-')],
    ]
    tbl = Table(parties, colWidths=[3.5*cm, 13*cm])
    tbl.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), CN_FONT),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#fef3c7')),
        ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#fcd34d')),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    flow.append(tbl)
    flow.append(Spacer(1, 0.4*cm))

    flow.append(Paragraph('最終安裝現場（感測器綁定對象）', st['h2']))
    site = [
        ['下游客戶',  cust.get('name','-')],
        ['對應訂單',  order.get('id','-')],
        ['安裝地址',  cust.get('address','-')],
        ['場域類型',  (s.get('space') or {}).get('scenario','-')],
    ]
    tbl = Table(site, colWidths=[3.5*cm, 13*cm])
    tbl.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), CN_FONT),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#fef3c7')),
        ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#fcd34d')),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    flow.append(tbl)
    flow.append(Spacer(1, 0.4*cm))

    flow.append(Paragraph('採購明細', st['h2']))
    rows = [['#', 'SKU', '品名', '數量', '單價 (NT$)', '小計 (NT$)']]
    sku_name = {
        'CJ-P760':'CurieJet P760 · PM+VOC 整合感測器 (29×29×7.2 mm)',
        'CJ-P710':'CurieJet P710 · PM2.5 顆粒感測器 (29×29×7.2 mm)',
    }
    for i, it in enumerate(po.get('items', []), 1):
        rows.append([
            str(i), it.get('sku','-'),
            sku_name.get(it.get('sku',''), it.get('sku','-')),
            str(it.get('qty','-')),
            f"{it.get('unit',0):,}", f"{it.get('subtotal',0):,}",
        ])
    rows.append(['', '', '', '', '總計', f"NT$ {po.get('total',0):,}"])
    tbl = Table(rows, colWidths=[0.8*cm, 2.4*cm, 7.5*cm, 1.5*cm, 2*cm, 2*cm])
    tbl.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), CN_FONT),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#d97706')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#fef3c7')),
        ('FONTSIZE', (0,-1), (-1,-1), 11),
        ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#fcd34d')),
        ('ALIGN', (0,0), (0,-1), 'CENTER'),
        ('ALIGN', (3,0), (-1,-1), 'RIGHT'),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    flow.append(tbl)
    flow.append(Spacer(1, 0.4*cm))

    if serials:
        flow.append(Paragraph('感測器序號綁定紀錄', st['h2']))
        srows = [['#', '序號', 'SKU', '綁定客戶', '綁定時間']]
        for i, x in enumerate(serials, 1):
            srows.append([
                str(i), x.get('serial','-'), x.get('sku','-'),
                x.get('bound_to_customer','-'),
                (x.get('bound_at') or '-')[:19].replace('T',' '),
            ])
        tbl = Table(srows, colWidths=[0.8*cm, 4.8*cm, 2*cm, 3*cm, 5.6*cm])
        tbl.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,-1), CN_FONT),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#059669')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#6ee7b7')),
            ('ALIGN', (0,0), (0,-1), 'CENTER'),
            ('PADDING', (0,0), (-1,-1), 5),
        ]))
        flow.append(tbl)
        flow.append(Spacer(1, 0.3*cm))
    else:
        flow.append(Paragraph('備註：採購單尚未出貨，序號尚未生成。出貨後將自動綁定至上述安裝現場並永久追溯。',
                              st['body']))
        flow.append(Spacer(1, 0.3*cm))

    flow.append(Paragraph('技術說明 / 條款', st['h2']))
    flow.append(Paragraph('▸ CurieJet P710/P760 為世界最小光學雷射 PM 感測模組 (29×29×7.2 mm)', st['body']))
    flow.append(Paragraph('▸ P760 整合 BME688，同步偵測 PM1.0/2.5/10 + VOC + 乙醇 + 氣壓', st['body']))
    flow.append(Paragraph('▸ 所有出貨感測器序號永久登錄並綁定至最終安裝地址，支援日後追溯', st['body']))
    flow.append(Paragraph('▸ 工業等級 1 年保固 · 年度維護合約可議', st['body']))
    flow.append(Spacer(1, 0.3*cm))
    flow.append(Paragraph(f'產出時間：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', st['small']))

    doc.build(flow, onFirstPage=_microjet_footer, onLaterPages=_microjet_footer)
    return buf.getvalue()


# ============================================================
# 2. B2B 提案書 PDF
# ============================================================
def build_proposal_pdf(proposal_dict):
    """proposal_dict: generate_proposal() 的回傳 dict['proposal']"""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm,
                            leftMargin=2*cm, rightMargin=2*cm)
    st = _styles()
    flow = []
    p = proposal_dict
    flow.append(Paragraph(p.get('title', '凌策 B2B 解決方案提案書'), st['title']))
    flow.append(Spacer(1, 0.5*cm))

    # 客戶資訊
    flow.append(Paragraph('一、客戶資訊', st['h2']))
    rows = [
        ['客戶產業', p.get('client','-')],
        ['客戶規模', p.get('scale','-')],
        ['預算',     p.get('budget','-')],
        ['核心痛點', p.get('pain_point','-')],
    ]
    tbl = Table(rows, colWidths=[3*cm, 13.5*cm])
    tbl.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), CN_FONT),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#eff6ff')),
        ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#93c5fd')),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    flow.append(tbl)
    flow.append(Spacer(1, 0.4*cm))

    # 解決方案
    flow.append(Paragraph('二、解決方案', st['h2']))
    for sol in p.get('solution', []):
        flow.append(Paragraph(f'▸ {sol}', st['body']))
    flow.append(Spacer(1, 0.4*cm))

    # ROI
    flow.append(Paragraph('三、投資回報分析', st['h2']))
    roi_rows = [[k, v] for k, v in (p.get('roi') or {}).items()]
    if roi_rows:
        tbl_roi = Table(roi_rows, colWidths=[5*cm, 11.5*cm])
        tbl_roi.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,-1), CN_FONT),
            ('FONTSIZE', (0,0), (-1,-1), 10),
            ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#dcfce7')),
            ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#86efac')),
            ('PADDING', (0,0), (-1,-1), 6),
        ]))
        flow.append(tbl_roi)
    flow.append(Spacer(1, 0.4*cm))

    # 下一步
    flow.append(Paragraph('四、下一步行動', st['h2']))
    for i, step in enumerate(p.get('next_step', []), 1):
        flow.append(Paragraph(f'{i}. {step}', st['body']))
    flow.append(Spacer(1, 0.6*cm))

    flow.append(Paragraph(f'提案日期：{datetime.now().strftime("%Y-%m-%d")}', st['small']))
    flow.append(Paragraph('凌策 AI 顧問 · 1 人老闆 + 10 AI Agent · 由 BD Agent 自動生成', st['small']))

    doc.build(flow, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


# ============================================================
# 3. AI 審計報告 PDF（✅ / ⚠️ / ❌ / 📌 結構化）
# ============================================================
def build_ai_analysis_pdf(title: str, subtitle: str, sections: list, verdict: str,
                          verdict_type: str = 'pass', meta: dict = None):
    """
    產出結構化 AI 報告 PDF。
    sections: [{'status':'pass'/'warn'/'fail', 'title':..., 'detail':...}]
    verdict: 綜合建議文字
    verdict_type: 'pass' | 'warn' | 'fail'
    meta: {'key':'value'} 頂部資訊欄
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm,
                            leftMargin=2*cm, rightMargin=2*cm)
    st = _styles()
    flow = []

    # 頂部標題
    flow.append(Paragraph(f'📋 {title}', st['title']))
    if subtitle:
        flow.append(Paragraph(subtitle, st['small']))
    flow.append(Spacer(1, 0.5*cm))

    # Meta 資訊（申請單位、金額等橫列）
    if meta:
        meta_rows = [[k, str(v)] for k, v in meta.items()]
        tbl = Table(meta_rows, colWidths=[4*cm, 12.5*cm])
        tbl.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,-1), CN_FONT),
            ('FONTSIZE', (0,0), (-1,-1), 10),
            ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#eff6ff')),
            ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#cbd5e1')),
            ('PADDING', (0,0), (-1,-1), 6),
        ]))
        flow.append(tbl)
        flow.append(Spacer(1, 0.5*cm))

    # 逐項審計結果
    flow.append(Paragraph('🔍 逐項審計結果', st['h2']))
    flow.append(Spacer(1, 0.2*cm))
    status_icon = {'pass':'✅', 'warn':'⚠️', 'fail':'❌', 'info':'ℹ️'}
    status_color = {
        'pass': colors.HexColor('#16a34a'),
        'warn': colors.HexColor('#d97706'),
        'fail': colors.HexColor('#dc2626'),
        'info': colors.HexColor('#2563eb'),
    }
    status_bg = {
        'pass': colors.HexColor('#dcfce7'),
        'warn': colors.HexColor('#fef3c7'),
        'fail': colors.HexColor('#fee2e2'),
        'info': colors.HexColor('#dbeafe'),
    }
    for sec in sections:
        s = sec.get('status', 'info')
        ico = status_icon.get(s, 'ℹ️')
        row_data = [
            [f'{ico} {sec.get("title","")}'],
            [Paragraph(sec.get('detail','').replace('\n','<br/>'), st['body'])],
        ]
        tbl = Table(row_data, colWidths=[16.5*cm])
        tbl.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,-1), CN_FONT),
            ('BACKGROUND', (0,0), (0,0), status_bg[s]),
            ('TEXTCOLOR', (0,0), (0,0), status_color[s]),
            ('FONTSIZE', (0,0), (0,0), 11),
            ('FONTSIZE', (0,1), (0,1), 10),
            ('BACKGROUND', (0,1), (0,1), colors.HexColor('#f8fafc')),
            ('GRID', (0,0), (-1,-1), 0.3, status_color[s]),
            ('PADDING', (0,0), (-1,-1), 8),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ]))
        flow.append(tbl)
        flow.append(Spacer(1, 0.25*cm))

    # 綜合建議（大色塊）
    flow.append(Spacer(1, 0.3*cm))
    flow.append(Paragraph('📌 AI 綜合建議', st['h2']))
    v_bg = status_bg.get(verdict_type, colors.HexColor('#dbeafe'))
    v_color = status_color.get(verdict_type, colors.HexColor('#2563eb'))
    v_ico = {'pass':'✅ 建議放行/通過', 'warn':'⚠️ 建議人工複查',
             'fail':'❌ 建議拒絕/退件', 'info':'ℹ️ 供參考'}.get(verdict_type, '📌')
    verdict_tbl = Table([[v_ico], [Paragraph(verdict.replace('\n','<br/>'), st['body'])]],
                       colWidths=[16.5*cm])
    verdict_tbl.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), CN_FONT),
        ('BACKGROUND', (0,0), (0,0), v_color),
        ('TEXTCOLOR', (0,0), (0,0), colors.white),
        ('FONTSIZE', (0,0), (0,0), 13),
        ('BACKGROUND', (0,1), (0,1), v_bg),
        ('FONTSIZE', (0,1), (0,1), 11),
        ('GRID', (0,0), (-1,-1), 0.3, v_color),
        ('PADDING', (0,0), (-1,-1), 10),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    flow.append(verdict_tbl)
    flow.append(Spacer(1, 0.5*cm))
    flow.append(Paragraph(f'產出時間：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', st['small']))

    doc.build(flow, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


# ============================================================
# 4. HR 出缺勤報表 PDF
# ============================================================
def build_attendance_report_pdf(report_dict):
    """report_dict: leave_ot_mgr.generate_attendance_report() 回傳"""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm,
                            leftMargin=1.5*cm, rightMargin=1.5*cm)
    st = _styles()
    flow = []
    flow.append(Paragraph('HR 出缺勤紀錄表（含加班）', st['title']))
    period = report_dict.get('period', {})
    flow.append(Paragraph(f"期間：{period.get('start','-')} ~ {period.get('end','-')}", st['small']))
    flow.append(Spacer(1, 0.5*cm))

    # 彙總（加班費金額僅 HR/財務主管可見，目前僅顯示時數）
    s = report_dict.get('summary', {})
    sum_rows = [
        ['員工數', f"{s.get('employees',0)} 人"],
        ['總請假時數', f"{s.get('total_leave_hours',0)} 小時"],
        ['總加班時數', f"{s.get('total_overtime_hours',0)} 小時"],
    ]
    tbl = Table(sum_rows, colWidths=[4*cm, 14*cm])
    tbl.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), CN_FONT),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#eff6ff')),
        ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#93c5fd')),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    flow.append(tbl)
    flow.append(Spacer(1, 0.5*cm))

    # 員工明細表（加班費金額欄已移除）
    flow.append(Paragraph('員工明細（加班費金額僅人事/財務部門主管可見）', st['h2']))
    hdr = ['員編', '姓名', '部門', '請假', '平日加班', '假日加班', '總加班']
    data = [hdr]
    for r in report_dict.get('rows', []):
        data.append([
            r.get('member_id','-'),
            r.get('member_name','-'),
            (r.get('dept','') or '')[:18],
            f"{r.get('leave_total_hours',0)}h",
            f"{r.get('overtime_weekday_hours',0)}h",
            f"{r.get('overtime_holiday_hours',0)}h",
            f"{r.get('overtime_total_hours',0)}h",
        ])
    if len(data) == 1:
        data.append(['', '（期間內無資料）', '', '', '', '', ''])
    tbl2 = Table(data, colWidths=[2.2*cm, 2.2*cm, 5*cm, 1.5*cm, 2*cm, 2*cm, 2.5*cm])
    tbl2.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), CN_FONT),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e3a8a')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTSIZE', (0,0), (-1,0), 10),
        ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#cbd5e1')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    flow.append(tbl2)
    flow.append(Spacer(1, 0.5*cm))
    flow.append(Paragraph(f'產出時間：{report_dict.get("generated_at", datetime.now().isoformat())}', st['small']))

    doc.build(flow, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()
