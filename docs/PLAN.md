# План выполнения проекта ОбучAI

## Выполнено

- **Блок 1:** Нормализация (классификация question/abuse/off_topic/cheat, JSON)
- **Блок 2:** RAG (ChromaDB, чанки, sentence-transformers)
- **Блок 3:** Генерация ответа (GigaChat, по контексту)
- **Блок 4:** LLM-Judge (скрыто, логи в judge_log.json)
- **Блок 5:** Кнопки обратной связи, эскалация куратору

## Схема

Студент → Блок 1 → (question → Блок 2 → Блок 3 → Блок 4 → Блок 5) или (abuse/off_topic/cheat → шаблон → лог)

## Запуск

См. [SETUP.md](SETUP.md). Кратко: `./scripts/setup_env.sh`, настроить `.env`, `python bot.py`.

## Стек

Python 3.8+, python-telegram-bot, GigaChat (gigachat_client), LangChain, ChromaDB, sentence-transformers.
