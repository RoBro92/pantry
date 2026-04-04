FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/apps/api:/app/apps/worker

WORKDIR /app/apps/worker

COPY apps/worker/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY VERSION /app/VERSION
COPY apps/api /app/apps/api
COPY apps/worker /app/apps/worker

CMD ["python", "-m", "worker.main"]
