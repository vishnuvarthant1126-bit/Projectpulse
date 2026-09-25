# Build from the repository root:  docker build -f backend/Dockerfile .
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_DIR=/data \
    SAMPLE_DATA_DIR=/app/sample_data \
    EMBEDDING_MODEL_DIR=/models/all-MiniLM-L6-v2

WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install -r requirements.txt

# Local embedding model (~90 MB). Set --build-arg DOWNLOAD_MODEL=false if you use
# EMBEDDING_PROVIDER=openai or mount your own model directory at /models.
ARG DOWNLOAD_MODEL=true
COPY backend/scripts/download_model.py ./scripts/download_model.py
RUN if [ "$DOWNLOAD_MODEL" = "true" ]; then python scripts/download_model.py; fi

COPY backend/app ./app
COPY sample_data /app/sample_data

RUN useradd --create-home --uid 10001 app && mkdir -p /data && chown app:app /data
USER app
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen(f\"http://127.0.0.1:{os.environ.get('PORT', '8000')}/api/health\", timeout=4)"
# Hosting platforms such as Render set PORT; locally it defaults to 8000.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers"]
