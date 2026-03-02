#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "==> Применяем миграции..."
python manage.py migrate

echo "==> Запускаем сборщик в фоне..."
python manage.py collect &
COLLECT_PID=$!

cleanup() {
    echo "==> Останавливаем сборщик (PID=$COLLECT_PID)..."
    kill "$COLLECT_PID" 2>/dev/null
    wait "$COLLECT_PID" 2>/dev/null
    echo "==> Готово."
}
trap cleanup EXIT INT TERM

echo "==> Запускаем веб-сервер..."
python manage.py runserver 0.0.0.0:8000
