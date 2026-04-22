# -*- coding: utf-8 -*-
"""
P0 合規：PII（個人識別資訊）偵測與遮蔽中介層

所有進入 LLM（本地 Ollama / 雲端 Claude）的文字必須先經過 mask_text()。
目的：
  ① 符合驗收構面五「個資零外洩」一票否決題
  ② 即使雲端 API 被誤啟用，PII 也已在呼叫前被遮蔽
  ③ append-only 稽核 log 記錄所有偵測結果供驗收展示

偵測類型：
  - 台灣手機 / 市話
  - Email
  - 身分證字號
  - 信用卡號（16 位連號）
  - 中文姓名（2~4 字，含常見姓氏）
  - 英文姓名 (Alice/Bob 等)
  - 住址片段（台北市 xx 區 xx 路 xx 號）
  - addwii CSV 特殊欄位（roomId / houseId）
"""
from __future__ import annotations
import re, json, os, threading
from datetime import datetime
from typing import Any

# ─── 偵測規則（順序重要：先長後短，避免誤替換）───
# 常見中文姓氏（前 100 大）
_CN_SURNAMES = (
    '王李張劉陳楊黃趙吳周徐孫馬朱胡林郭何高羅鄭'
    '梁謝宋唐許韓馮鄧曹彭曾肖田董袁潘於蔣蔡余杜葉程蘇魏呂丁任沈姚盧姜崔鍾譚陸汪范金石廖賈夏韋付方白鄒孟熊秦邱江尹薛閻段雷侯龍史陶黎賀顧毛郝龔邵萬錢嚴覃武戴莫孔向湯'
)

PATTERNS: list[tuple[str, re.Pattern, str]] = [
    # type, compiled regex, token prefix
    ('TW_ID',      re.compile(r'\b[A-Z][12]\d{8}\b'),                                            'ID'),
    ('TW_PHONE',   re.compile(r'\b09\d{2}[-\s]?\d{3}[-\s]?\d{3}\b'),                             'PHONE'),
    # 支援 02-xxxx-xxxx / 02 xxxx xxxx / (02) xxx-xxxx / 02xxxxxxxx 各種寫法
    ('LANDLINE',   re.compile(r'\(?0[2-8]\)?[-\s]?\d{3,4}[-\s]?\d{4}\b'),                         'PHONE'),
    ('EMAIL',      re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'),            'EMAIL'),
    ('CREDIT',     re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'),                                   'CARD'),
    # addwii CSV 專屬（roomId_x / houseId_y）
    ('ROOM_ID',    re.compile(r'\broom[_\s]?id[_\s]?\d+\b', re.IGNORECASE),                       'ROOM'),
    ('HOUSE_ID',   re.compile(r'\bhouse[_\s]?id[_\s]?\d+\b', re.IGNORECASE),                      'HOUSE'),
    # 住址片段：xx路/街/段 + 號碼
    ('TW_ADDR',    re.compile(r'[\u4e00-\u9fa5]{2,8}(?:縣|市)[\u4e00-\u9fa5]{1,4}區[\u4e00-\u9fa5\w]+(?:路|街|大道)\w*段?\w*號?\w*樓?'), 'ADDR'),
    # 中文姓名（2~4 字，開頭為常見姓氏）
    ('CN_NAME',    re.compile(r'(?:先生|小姐|女士)?(?<![\u4e00-\u9fa5])[' + _CN_SURNAMES + r'][\u4e00-\u9fa5]{1,3}(?=先生|小姐|女士|同學|老師|\b|[，。、：；！？,;\s])'), 'USER'),
    # 英文姓名（頭字母大寫兩字，避免誤中其他）
    ('EN_NAME',    re.compile(r'\b(?:Mr\.?|Ms\.?|Mrs\.?|Dr\.?)\s*[A-Z][a-z]{2,12}(?:\s[A-Z][a-z]{2,12})?\b'), 'USER'),
]

# ─── 稽核 log ───
_AUDIT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           '..', '..', 'chat_logs', 'pii_audit.jsonl')
_AUDIT_LOCK = threading.Lock()


def _append_audit(record: dict) -> None:
    try:
        with _AUDIT_LOCK:
            os.makedirs(os.path.dirname(_AUDIT_FILE), exist_ok=True)
            with open(_AUDIT_FILE, 'a', encoding='utf-8') as f:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
    except Exception as e:
        print(f'[pii_guard] audit write failed: {e}')


def mask_text(text: str, context: str = 'unknown') -> tuple[str, list[dict]]:
    """
    遮蔽文字中的 PII，回傳 (已遮蔽文字, 偵測詳情列表)

    context: 呼叫來源標記（寫入 audit log）
    """
    if not text:
        return text, []

    detections: list[dict] = []
    counter: dict[str, int] = {}
    masked = text

    for pii_type, pattern, prefix in PATTERNS:
        def _replace(m, _prefix=prefix, _type=pii_type):
            original = m.group(0)
            counter[_prefix] = counter.get(_prefix, 0) + 1
            token = f'[{_prefix}_{counter[_prefix]:03d}]'
            detections.append({
                'type': _type,
                'original_len': len(original),
                'token': token,
                'preview': original[:2] + '***' if len(original) > 2 else '***',
            })
            return token
        masked = pattern.sub(_replace, masked)

    if detections:
        _append_audit({
            'ts': datetime.now().isoformat(timespec='seconds'),
            'context': context,
            'detections_count': len(detections),
            'types': sorted({d['type'] for d in detections}),
            'input_len': len(text),
            'output_len': len(masked),
        })

    return masked, detections


def is_safe_for_external_api(text: str) -> tuple[bool, list[dict]]:
    """
    檢查文字是否可安全傳給雲端 API（Claude 等）。
    若有任何 PII 偵測到則回 False。
    """
    _, dets = mask_text(text, context='external_api_check')
    return (len(dets) == 0, dets)


def read_recent_audit(limit: int = 50) -> list[dict]:
    """讀取最近的 PII 偵測稽核紀錄（給前端展示用）"""
    if not os.path.exists(_AUDIT_FILE):
        return []
    rows = []
    try:
        with open(_AUDIT_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line: continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
    except Exception as e:
        print(f'[pii_guard] audit read failed: {e}')
    return list(reversed(rows))[:limit]


def audit_stats() -> dict:
    """彙總稽核統計（給合規展示頁用）"""
    rows = read_recent_audit(limit=10000)
    total_detections = sum(r.get('detections_count', 0) for r in rows)
    by_type: dict[str, int] = {}
    by_context: dict[str, int] = {}
    for r in rows:
        for t in r.get('types', []):
            by_type[t] = by_type.get(t, 0) + 1
        ctx = r.get('context', 'unknown')
        by_context[ctx] = by_context.get(ctx, 0) + 1
    return {
        'total_calls_scanned': len(rows),
        'total_pii_detected': total_detections,
        'by_type': by_type,
        'by_context': by_context,
        'last_10': rows[:10],
    }


# ─── 雲端 API 開關（P0：明確聲明已關閉）───
CLAUDE_API_DISABLED = True  # 硬性關閉；即使環境變數被改動也不會啟用


def assert_local_only():
    """呼叫敏感資料處理時用；確保雲端 API 關閉"""
    if not CLAUDE_API_DISABLED:
        raise RuntimeError('Cloud API is enabled — violates compliance policy')
    return True
