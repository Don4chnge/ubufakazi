# Ubufakazi 2.0 server (also serves the website). Build from the repo root.
#   docker build -t ubufakazi . && docker run -p 8000:8000 -v ubf-data:/data ubufakazi
# On Railway/Render: mount a persistent volume at /data. Optional variables: UBF_DEMO_SEED, TELEGRAM_BOT_TOKEN,
# GEMINI_API_KEY, UBF_PUBLIC_BASE_URL (https://... turns on Secure cookies).
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UBF_DATA_DIR=/data PORT=8000
WORKDIR /app
COPY server/requirements.txt server/requirements.txt
RUN pip install --no-cache-dir -r server/requirements.txt
COPY site site
COPY server server
WORKDIR /app/server
EXPOSE 8000
# Runs as root because hosted volumes are mounted root-owned. setup is idempotent: first start creates secrets on the
# volume, the database, stations, demo accounts and synthetic reports; later starts keep everything.
# --proxy-headers: behind the host's proxy, use the real client IP for rate limiting and the audit log.
CMD ["sh", "-c", "python -m ubufakazi_server.setup && exec uvicorn ubufakazi_server.app:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
