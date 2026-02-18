# Настройка виртуального окружения

## Автоматическая настройка

**macOS / Linux:** из корня проекта
```bash
./scripts/setup_env.sh
```

**Windows:** из корня проекта
```cmd
scripts\setup_env.bat
```

## Ручная настройка

1. **Создание:** `python3 -m venv venv` (или `python -m venv venv` на Windows)
2. **Активация:** `source venv/bin/activate` (macOS/Linux) или `venv\Scripts\activate` (Windows)
3. **pip:** `pip install --upgrade pip`
4. **Зависимости:** `pip install -r requirements.txt`

Требуется **Python 3.8+** (рекомендуется 3.11). На macOS при необходимости: `./scripts/install_python_and_setup.sh` (устанавливает Python 3.11 через Homebrew).

## Проверка

```bash
pip list
python -c "import telegram; import langchain; print('OK')"
```

## Деактивация

```bash
deactivate
```

## Устранение проблем

- `python3: command not found` — установите Python 3.8+ или используйте `python`
- Ошибки при установке пакетов — обновите pip, проверьте интернет
- ChromaDB — на macOS может понадобиться `brew install cmake`
