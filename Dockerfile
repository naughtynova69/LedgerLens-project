# Stage 1: Build React + Vite frontend
FROM node:22-alpine AS frontend-builder
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: FastAPI + Deterministic Rules Engine + Embedded Knowledge Graph + Static SPA
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    GEMINI_PRIMARY_MODEL=gemini-3.8-vision-flash \
    GEMINI_FLASH_MODEL=gemini-3.8-vision-flash \
    DB_PATH=/tmp/ledgerlens.db \
    UPLOAD_DIR=/tmp/uploads \
    LEDGERLENS_GRAPH_PATH=/tmp/ledgerlens.lbdb \
    LBUG_C_API_LIB_PATH=/app/lbug/lib/liblbug.so \
    FRONTEND_DIST=/app/frontend/dist

WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && mkdir -p /app/lbug/lib \
    && curl -sL --max-time 180 \
       -o /tmp/liblbug.tar.gz \
       https://github.com/LadybugDB/ladybug/releases/download/v0.22.3/liblbug-linux-x86_64.tar.gz \
    && tar -xzf /tmp/liblbug.tar.gz -C /app/lbug/lib \
    && rm -f /tmp/liblbug.tar.gz \
    && ls -la /app/lbug/lib

# liblbug.so links against OpenSSL 3 — present in python:3.12-slim (libssl3).
COPY backend/ /app/backend/
COPY sample_data/ /app/sample_data/
COPY --from=frontend-builder /build/frontend/dist /app/frontend/dist

EXPOSE 8080
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
