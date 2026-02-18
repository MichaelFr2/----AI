# Инструкция по настройке и запуску

## Шаг 1: Настройка виртуального окружения

### Вариант A: Автоматическая настройка

**macOS / Linux:**
```bash
./scripts/setup_env.sh
```

**Windows:**
```cmd
scripts\setup_env.bat
```

### Вариант B: Ручная настройка

1. Создайте виртуальное окружение (из корня проекта):
   ```bash
   python3 -m venv venv
   ```
2. Активируйте: `source venv/bin/activate` (macOS/Linux) или `venv\Scripts\activate` (Windows)
3. Установите зависимости: `pip install --upgrade pip && pip install -r requirements.txt`

> Требуется **Python 3.8+** (рекомендуется 3.11). Подробнее: [ENV_SETUP.md](ENV_SETUP.md)

## Шаг 2: Настройка переменных окружения

1. Создайте файл `.env` в корне проекта
2. Скопируйте содержимое из `env_example.txt` в `.env`
3. Заполните: `TELEGRAM_BOT_TOKEN`, `GIGACHAT_AUTH_KEY`, `CURATOR_CHAT_ID` (опционально)

Подробнее: получение токенов и Chat ID — в [README](../README.md).

## Шаг 3: Материалы курса

Поместите файлы (PDF, TXT, MD, DOCX) в папку `knowledge_base/`.

## Шаг 4: Запуск

```bash
source venv/bin/activate   # или venv\Scripts\activate на Windows
python bot.py
```

Или: `./scripts/run.sh` (macOS/Linux).

## Логи

- `logs/feedback_log.json` — обратная связь
- `logs/judge_log.json` — оценки Judge
- `logs/escalation_log.json` — эскалации

## Устранение проблем

- Бот не отвечает — проверьте `TELEGRAM_BOT_TOKEN`
- Нет ответов по курсу — добавьте файлы в `knowledge_base/`, перезапустите бота
- GigaChat — проверьте `GIGACHAT_AUTH_KEY` и доступ к API
- Куратор не получает сообщения — проверьте `CURATOR_CHAT_ID`, куратор должен отправить боту `/start`
