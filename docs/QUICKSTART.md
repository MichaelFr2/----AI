# Быстрый старт

## За 5 минут

1. **Окружение:** `./scripts/setup_env.sh` (или вручную: `python3 -m venv venv && source venv/bin/activate`)
2. **Зависимости:** `pip install -r requirements.txt`
3. **Конфиг:** скопируйте `env_example.txt` в `.env`, заполните `TELEGRAM_BOT_TOKEN` и `GIGACHAT_AUTH_KEY`
4. **База знаний:** положите PDF/TXT/MD/DOCX в `knowledge_base/`
5. **Запуск:** `python bot.py` или `./scripts/run.sh`

## Тестирование

```bash
python test_bot.py
```

## Документация

- [SETUP.md](SETUP.md) — полная настройка
- [ARCHITECTURE.md](ARCHITECTURE.md) — архитектура
- [README.md](README.md) (в docs/) — оглавление документации
