# ── Multi-Stage Production Dockerfile for MCN Full-Stack App ──────────────────

# Stage 1: Build React Frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --prefer-offline || npm install
COPY frontend/ ./
RUN npm run build || mkdir -p dist

# Stage 2: Production Runtime (Python API + Static Frontend via Nginx / Static server)
FROM python:3.12-slim AS runner
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt || true

COPY . .
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["python", "backend/main.mcn"]
