# WarehouseDB only — build from WarehouseDB/
#   docker compose up --build -d
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_ENV=production

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY config.py run.py wsgi.py ./
COPY scripts/ scripts/
COPY json/ json/

RUN mkdir -p instance \
    && useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["waitress-serve", "--host=0.0.0.0", "--port=8000", "wsgi:app"]
