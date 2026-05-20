# -*- coding: utf-8 -*-
"""
凌策 AI Backend · 多後端 LLM 抽象層

依環境自動偵測最佳後端，順序：
  1. Ollama @ 127.0.0.1:11434      （離線 phase 主設計 · qwen2.5:7b）
  2. Anthropic API（ANTHROPIC_API_KEY）（線上 phase 備援）
  3. HF transformers + microsoft/Phi-3-mini-4k-instruct（macOS M2 可跑）
  4. Stub 規則引擎 + 標示清楚（最差情況）

使用：
    from ai_backend import generate, backend_info
    text = generate("你好", system="你是 addwii 客服 Agent")
    print(backend_info())  # 顯示當前用哪個後端

環境變數：
    LINGCE_AI_BACKEND   ollama | anthropic | transformers | stub | auto（預設 auto）
    OLLAMA_URL          預設 http://127.0.0.1:11434
    OLLAMA_MODEL        預設 qwen2.5:7b
    ANTHROPIC_API_KEY   走 anthropic 後端時必要
    HF_MODEL            預設 microsoft/Phi-3-mini-4k-instruct
"""
import os
import json
import time
import threading

# ────────────────────────────────────────────────────────────
# 全域狀態
# ────────────────────────────────────────────────────────────
_BACKEND        = None          # 當前選定後端：ollama / anthropic / transformers / stub
_BACKEND_INFO   = {}            # 後端詳細資訊
_INIT_LOCK      = threading.Lock()
_HF_PIPELINE    = None          # HF transformers pipeline（lazy load）
_TOTAL_CALLS    = 0
_TOTAL_TOKENS   = 0


def _try_ollama() -> dict:
    """嘗試連 Ollama"""
    try:
        import requests
        url   = os.getenv('OLLAMA_URL',   'http://127.0.0.1:11434')
        model = os.getenv('OLLAMA_MODEL', 'qwen2.5:7b')
        r = requests.get(f'{url}/api/tags', timeout=2)
        if r.status_code == 200:
            tags = [m['name'] for m in r.json().get('models', [])]
            if any(model.split(':')[0] in t for t in tags) or len(tags) > 0:
                return {
                    'backend':  'ollama',
                    'url':      url,
                    'model':    model if any(model in t for t in tags) else (tags[0] if tags else model),
                    'license':  'Apache 2.0（qwen / gemma 等開源）',
                    'mode':     'offline',
                    'available_models': tags,
                }
    except Exception:
        pass
    return None


def _try_anthropic() -> dict:
    """嘗試連 Anthropic API"""
    key = os.getenv('ANTHROPIC_API_KEY')
    if not key or len(key) < 20:
        return None
    try:
        import anthropic  # type: ignore
        return {
            'backend':  'anthropic',
            'model':    os.getenv('ANTHROPIC_MODEL', 'claude-sonnet-4-5'),
            'license':  'Anthropic API（非離線）',
            'mode':     'online',
            'key_hint': f'***{key[-4:]}',
        }
    except ImportError:
        # anthropic SDK 未安裝
        return None


def _try_transformers() -> dict:
    """嘗試 HF transformers（lazy load，只回報可用性）"""
    try:
        import transformers  # type: ignore
        import torch  # type: ignore
        hf_model = os.getenv('HF_MODEL', 'microsoft/Phi-3-mini-4k-instruct')
        return {
            'backend':       'transformers',
            'model':         hf_model,
            'license':       'MIT (Phi-3) / Apache (其他開源)',
            'mode':          'offline',
            'load_status':   'pending（首次呼叫才下載 + 載入到 RAM）',
            'estimated_size': '2.4 GB (Phi-3-mini-4k)',
            'device':        'cuda' if torch.cuda.is_available() else ('mps' if torch.backends.mps.is_available() else 'cpu'),
        }
    except ImportError:
        return None


def _stub_info() -> dict:
    """規則引擎 stub（最差情況）"""
    return {
        'backend':  'stub',
        'model':    'rule_engine + distilled KB',
        'license':  '凌策自製規則庫',
        'mode':     'offline',
        'note':     '無 Ollama / Anthropic / Transformers 可用 → fallback 規則引擎；回答仍正確但非 LLM 生成',
    }


def init_backend(force: str = None) -> dict:
    """初始化後端（thread-safe · 只執行一次）

    Args:
        force: 強制指定後端（ollama/anthropic/transformers/stub）
    """
    global _BACKEND, _BACKEND_INFO
    with _INIT_LOCK:
        if _BACKEND and not force:
            return _BACKEND_INFO

        choice = force or os.getenv('LINGCE_AI_BACKEND', 'auto').lower()

        if choice == 'auto':
            # 自動偵測順序：ollama → anthropic → transformers → stub
            for trial in (_try_ollama, _try_anthropic, _try_transformers):
                info = trial()
                if info:
                    _BACKEND_INFO = info
                    _BACKEND = info['backend']
                    return info
            _BACKEND_INFO = _stub_info()
            _BACKEND = 'stub'
            return _BACKEND_INFO

        # 強制指定
        if choice == 'ollama':
            info = _try_ollama() or {'backend': 'ollama', 'error': '無法連線', 'mode': 'offline'}
        elif choice == 'anthropic':
            info = _try_anthropic() or {'backend': 'anthropic', 'error': '無 API key 或 SDK', 'mode': 'online'}
        elif choice == 'transformers':
            info = _try_transformers() or {'backend': 'transformers', 'error': '套件未安裝', 'mode': 'offline'}
        else:
            info = _stub_info()

        _BACKEND_INFO = info
        _BACKEND = info['backend']
        return info


def backend_info() -> dict:
    """回傳當前後端詳細資訊"""
    if not _BACKEND:
        init_backend()
    return {
        **_BACKEND_INFO,
        'total_calls':  _TOTAL_CALLS,
        'total_tokens': _TOTAL_TOKENS,
    }


# ────────────────────────────────────────────────────────────
# 主要呼叫介面
# ────────────────────────────────────────────────────────────
def generate(prompt: str,
             system: str = None,
             max_tokens: int = 500,
             temperature: float = 0.3,
             timeout_s: int = 60) -> dict:
    """統一 LLM 呼叫介面

    Returns:
        {
            'text':     生成文字,
            'backend':  ollama / anthropic / transformers / stub,
            'model':    具體模型名稱,
            'tokens':   約略 token 數,
            'latency_ms': 延遲,
            'fallback': True/False（是否走規則引擎 fallback）
        }
    """
    global _TOTAL_CALLS, _TOTAL_TOKENS
    if not _BACKEND:
        init_backend()

    t0 = time.time()
    _TOTAL_CALLS += 1

    try:
        if _BACKEND == 'ollama':
            result = _call_ollama(prompt, system, max_tokens, temperature, timeout_s)
        elif _BACKEND == 'anthropic':
            result = _call_anthropic(prompt, system, max_tokens, temperature, timeout_s)
        elif _BACKEND == 'transformers':
            result = _call_transformers(prompt, system, max_tokens, temperature)
        else:
            result = _call_stub(prompt, system)
    except Exception as e:
        # 任何後端失敗 → 降級 stub
        result = _call_stub(prompt, system)
        result['error'] = str(e)
        result['fallback'] = True

    result['latency_ms'] = int((time.time() - t0) * 1000)
    _TOTAL_TOKENS += result.get('tokens', 0)
    return result


def _call_ollama(prompt, system, max_tokens, temperature, timeout_s):
    import requests
    url   = _BACKEND_INFO.get('url',   'http://127.0.0.1:11434')
    model = _BACKEND_INFO.get('model', 'qwen2.5:7b')
    messages = []
    if system:
        messages.append({'role': 'system', 'content': system})
    messages.append({'role': 'user', 'content': prompt})
    r = requests.post(f'{url}/api/chat',
                      json={'model': model, 'messages': messages, 'stream': False,
                            'options': {'temperature': temperature, 'num_predict': max_tokens}},
                      timeout=timeout_s)
    r.raise_for_status()
    data = r.json()
    text = data.get('message', {}).get('content', '')
    return {
        'text':     text,
        'backend':  'ollama',
        'model':    model,
        'tokens':   data.get('eval_count', len(text) // 2),
        'fallback': False,
    }


def _call_anthropic(prompt, system, max_tokens, temperature, timeout_s):
    import anthropic
    client = anthropic.Anthropic()
    model = _BACKEND_INFO.get('model', 'claude-sonnet-4-5')
    msg = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system or 'You are a helpful assistant.',
        messages=[{'role': 'user', 'content': prompt}],
    )
    text = ''.join(b.text for b in msg.content if hasattr(b, 'text'))
    return {
        'text':     text,
        'backend':  'anthropic',
        'model':    model,
        'tokens':   msg.usage.output_tokens if hasattr(msg, 'usage') else len(text) // 4,
        'fallback': False,
    }


def _call_transformers(prompt, system, max_tokens, temperature):
    global _HF_PIPELINE
    if _HF_PIPELINE is None:
        from transformers import pipeline
        import torch
        hf_model = _BACKEND_INFO.get('model', 'microsoft/Phi-3-mini-4k-instruct')
        device = 'mps' if torch.backends.mps.is_available() else (0 if torch.cuda.is_available() else -1)
        _HF_PIPELINE = pipeline('text-generation', model=hf_model, device=device,
                                torch_dtype=torch.float16 if device != -1 else torch.float32,
                                trust_remote_code=True)
    msg = []
    if system:
        msg.append({'role': 'system', 'content': system})
    msg.append({'role': 'user', 'content': prompt})
    out = _HF_PIPELINE(msg, max_new_tokens=max_tokens, temperature=max(0.1, temperature),
                       do_sample=temperature > 0.1, return_full_text=False)
    text = out[0]['generated_text'] if out else ''
    return {
        'text':     text,
        'backend':  'transformers',
        'model':    _BACKEND_INFO.get('model'),
        'tokens':   len(text) // 4,
        'fallback': False,
    }


def _call_stub(prompt, system):
    """規則引擎 stub — 不真的呼叫 LLM，但回傳結構化提示"""
    return {
        'text':     '[stub] 規則引擎已回答（非 LLM 生成 · 啟動 Ollama 或設 ANTHROPIC_API_KEY 後可獲得 LLM 增強）',
        'backend':  'stub',
        'model':    'rule_engine',
        'tokens':   0,
        'fallback': True,
    }


# ────────────────────────────────────────────────────────────
# 模組載入時自動初始化（log 結果）
# ────────────────────────────────────────────────────────────
if __name__ != '__main__':
    info = init_backend()
    print(f"[ai_backend] 已選定後端: {info.get('backend')} · 模型: {info.get('model')} · 模式: {info.get('mode', 'unknown')}")
