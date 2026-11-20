# Stage 1: Build React + Vite frontend
FROM node:22-alpine AS frontend-builder
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: FastAPI + Deterministic Rules Engine + Static SPA
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    GEMINI_PRIMARY_MODEL=gemini-3.8-vision-flash \
    GEMINI_FLASH_MODEL=gemini-3.8-vision-flash \
    DB_PATH=/tmp/ledgerlens.db \
    UPLOAD_DIR=/tmp/uploads \
    FRONTEND_DIST=/app/frontend/dist

WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ /app/backend/
COPY sample_data/ /app/sample_data/
COPY --from=frontend-builder /build/frontend/dist /app/frontend/dist

EXPOSE 8080
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
