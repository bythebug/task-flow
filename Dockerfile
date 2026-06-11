# ── Stage 1: Build React frontend ──────────────────────────────────
FROM node:20-alpine AS frontend
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Python API + static files ─────────────────────────────
FROM python:3.13-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=frontend /frontend/dist ./frontend/dist

EXPOSE 5000
ENV PYTHONUNBUFFERED=1

# Railway injects $PORT; fall back to 5000 for local Docker usage
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-5000} --workers 4 --timeout 60 run:app"]
