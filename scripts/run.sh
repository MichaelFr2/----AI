#!/bin/bash
# Запуск бота. Запускать из корня проекта: ./scripts/run.sh
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -d "venv" ]; then
    echo "❌ Виртуальное окружение не найдено. Запустите: ./scripts/setup_env.sh"
    exit 1
fi

if [ ! -f ".env" ]; then
    echo "⚠️  Файл .env не найден. Скопируйте env_example.txt в .env и заполните."
    exit 1
fi

source venv/bin/activate
echo "🚀 Запуск бота..."
exec python bot.py
