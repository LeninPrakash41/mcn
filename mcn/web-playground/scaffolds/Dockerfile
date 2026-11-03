# ── Production image for an MCN full-stack app ────────────────────────────────

# Stage 1: build the React frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --prefer-offline || npm install
COPY frontend/ ./
RUN npm run build || mkdir -p dist

# Stage 2: the MCN API
FROM debian:bookworm-slim AS runner
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
ENV MCN_HOME=/opt/mcn MCN_NO_MODIFY_PATH=1
RUN curl -fsSL https://raw.githubusercontent.com/LeninPrakash41/mcn/main/install.sh | sh
ENV PATH=/opt/mcn/bin:$PATH PORT=8080

WORKDIR /app
COPY backend/ ./backend/
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# The SQLite database (mcn_data.db) lives in /app/data so it survives restarts
WORKDIR /app/data
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/ || exit 1
CMD ["mcn", "serve", "/app/backend/main.mcn", "--host", "0.0.0.0", "--port", "8080"]
