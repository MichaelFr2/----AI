#!/bin/bash
# Установка Python 3.11 (Homebrew) и настройка окружения. Запускать из корня: ./scripts/install_python_and_setup.sh
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "🔧 Установка Python 3.11 и настройка виртуального окружения..."

if ! command -v brew &> /dev/null; then
    echo "❌ Homebrew не найден. Установите: https://brew.sh"
    exit 1
fi

echo "📦 Установка Python 3.11..."
brew install python@3.11

PYTHON311=$(brew --prefix python@3.11 2>/dev/null)/bin/python3.11
[ -x "$PYTHON311" ] || PYTHON311=$(which python3.11 2>/dev/null)
[ -x "$PYTHON311" ] || { echo "❌ Python 3.11 не найден"; exit 1; }

echo "✅ Найден: $PYTHON311"
$PYTHON311 --version

[ -d "venv" ] && rm -rf venv
echo "📦 Создание виртуального окружения..."
$PYTHON311 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo "✅ Готово. Активация: source venv/bin/activate"
