# ОбучAI — AI-куратор для онлайн-курсов

Бот для помощи студентам: вопрос → нормализация → RAG → ответ → LLM-Judge (скрыто) → обратная связь и эскалация к куратору.

## Быстрый старт

1. **Окружение:** `./scripts/setup_env.sh` (или вручную: `python3 -m venv venv && source venv/bin/activate`)
2. **Зависимости:** `pip install -r requirements.txt`
3. **Конфиг:** скопируйте `env_example.txt` в `.env`, заполните:
   - `TELEGRAM_BOT_TOKEN` — токен от [@BotFather](https://t.me/BotFather)
   - `GIGACHAT_AUTH_KEY` — ключ GigaChat (Сбер)
   - `CURATOR_CHAT_ID` — (опционально) chat_id куратора
4. **База знаний:** положите PDF/TXT/MD/DOCX в `knowledge_base/`
5. **Запуск:** `python bot.py` или `./scripts/run.sh`

Тесты: `python test_bot.py`

## Структура проекта

```
ОбучAI/
├── bot.py                 # Точка входа, Telegram
├── config.py              # Конфигурация
├── gigachat_client.py     # Клиент GigaChat
├── block1_normalization.py # Нормализация и классификация запроса
├── block2_rag.py          # RAG: загрузка документов, поиск
├── block3_generation.py   # Генерация ответа по контексту
├── block4_judge.py        # LLM-Judge (скрытая оценка)
├── block5_feedback.py     # Обратная связь и эскалация
├── test_bot.py            # Тесты блоков
├── requirements.txt
├── env_example.txt        # Пример .env
├── scripts/               # Скрипты окружения и запуска
│   ├── setup_env.sh
│   ├── setup_env.bat
│   ├── run.sh
│   └── install_python_and_setup.sh
├── docs/                  # Документация
│   ├── README.md
│   ├── SETUP.md
│   ├── QUICKSTART.md
│   ├── ENV_SETUP.md
│   ├── ARCHITECTURE.md
│   ├── PLAN.md
│   └── MIGRATION.md
├── knowledge_base/        # Материалы курса (PDF, TXT, MD, DOCX)
├── vector_db/             # ChromaDB (создаётся при запуске)
└── logs/                  # feedback_log.json, judge_log.json, escalation_log.json
```

## Документация

- [docs/QUICKSTART.md](docs/QUICKSTART.md) — быстрый старт
- [docs/SETUP.md](docs/SETUP.md) — установка и настройка
- [docs/ENV_SETUP.md](docs/ENV_SETUP.md) — виртуальное окружение
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — архитектура
- [docs/README.md](docs/README.md) — оглавление документации

## Требования

- Python 3.8+ (рекомендуется 3.11)
- GigaChat Authorization Key
- Telegram Bot Token
- Материалы курса в `knowledge_base/`

## Лицензия

MIT
