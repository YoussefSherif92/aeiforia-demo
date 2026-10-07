FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt /tmp/backend-requirements.txt
COPY frontend/requirements.txt /tmp/frontend-requirements.txt

RUN pip install --no-cache-dir \
    -r /tmp/backend-requirements.txt \
    -r /tmp/frontend-requirements.txt \
    supervisor==4.2.5

COPY backend /app/backend
COPY frontend /app/frontend
COPY knowledge /app/knowledge
COPY supervisord.conf /app/supervisord.conf

ENV PYTHONUNBUFFERED=1
ENV PORT=10000
ENV API_URL=http://127.0.0.1:8000

CMD ["supervisord", "-c", "/app/supervisord.conf"]
