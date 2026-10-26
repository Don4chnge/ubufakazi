# Ubufakazi 2.0 demo server (serves the MVP site too). Build from the repo root:
#   docker build -t ubufakazi . && docker run -p 8000:8000 -v ubf-data:/app/server/data ubufakazi
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY server/requirements.txt server/requirements.txt
RUN pip install --no-cache-dir -r server/requirements.txt
COPY site site
COPY server server
RUN useradd --create-home ubf && chown -R ubf /app/server
USER ubf
WORKDIR /app/server
EXPOSE 8000
# setup is idempotent: it creates .env with random secrets on first start and never overwrites existing data
CMD ["sh", "-c", "python -m ubufakazi_server.setup && uvicorn ubufakazi_server.app:app --host 0.0.0.0 --port 8000"]
