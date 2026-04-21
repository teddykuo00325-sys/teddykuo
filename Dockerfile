# 凌策公司 — 雲端 demo 容器
# 在 Render / Railway / Fly.io / 自架 Docker 主機上一鍵啟動
# 注意：雲端版本不含 Ollama，所有 AI 精煉功能走模板 fallback

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=5000

WORKDIR /app

# 只裝精簡依賴（~30 MB，無 chromadb/sentence-transformers）
COPY requirements-minimal.txt ./
RUN pip install --upgrade pip && pip install -r requirements-minimal.txt && \
    pip install gunicorn

# 複製專案
COPY . .

# 雲端用不到 Ollama，告知 server 走 fallback
ENV OLLAMA_URL=http://disabled-in-cloud:11434 \
    OLLAMA_MODEL=none

# 雲端平台會設定 $PORT，預設 5000
EXPOSE 5000

# 生產級 WSGI（不是 dev server）
CMD ["sh", "-c", "cd /app && python -m gunicorn --chdir src/backend server:app --bind 0.0.0.0:${PORT:-5000} --workers 2 --timeout 120"]
