FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN addgroup --system --gid 999 appuser \
    && adduser --system --uid 999 --ingroup appuser appuser \
    && chown -R appuser:appuser /app

USER appuser
