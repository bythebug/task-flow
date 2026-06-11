FROM python:3.13-slim

WORKDIR /app

# Install dependencies first (layer cache — only re-runs when requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

EXPOSE 5000

# PYTHONUNBUFFERED ensures logs reach the container runtime without buffering
ENV PYTHONUNBUFFERED=1

# 4 workers handles ~200 concurrent requests; tune to (2 * CPU cores + 1) in production
# Railway injects $PORT dynamically; fall back to 5000 for local Docker usage
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-5000} --workers 4 --timeout 60 run:app"]
