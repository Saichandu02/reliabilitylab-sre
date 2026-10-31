FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 DATABASE_PATH=/data/orders.db BUILD_VERSION=0.1.0
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN useradd -m appuser && mkdir -p /data && chown appuser:appuser /data
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/healthz')" || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
