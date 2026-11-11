# ── Backend – Flask + LangChain + FAISS + Ollama client ──────────────────────
FROM python:3.11-slim AS base

# System deps needed by some Python packages (faiss, pypdf, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (cached layer)
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY backend/ ./backend/
COPY app.py   ./app.py

# Expose Flask default port
EXPOSE 5000

# Environment variable defaults (override at runtime or via docker-compose)
ENV CHATBOT_ANSWER_MODEL=qwen2.5:7b \
    CHATBOT_EMBEDDING_MODEL=bge-m3 \
    CHATBOT_RELEVANCE_THRESHOLD=1.0 \
    CHATBOT_FUZZY_CUTOFF=80 \
    CHATBOT_DATA_DIR=backend/data \
    CHATBOT_QA_PATH=backend/qa.txt \
    CHATBOT_SOURCE_PATH=backend/data/chatbot.txt \
    CHATBOT_LEGACY_SOURCES=false \
    CHATBOT_OLLAMA_BASE_URL=http://ollama:11434 \
    CHATBOT_CHUNK_SIZE=500 \
    CHATBOT_CHUNK_OVERLAP=50 \
    CHATBOT_TOP_K=3 \
    CHATBOT_QUERY_REWRITE=auto \
    CHATBOT_HOST=0.0.0.0 \
    CHATBOT_PORT=5000 \
    FLASK_ENV=production \
    PYTHONUNBUFFERED=1

CMD ["python", "app.py"]
