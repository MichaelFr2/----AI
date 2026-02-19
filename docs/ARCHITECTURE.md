# Архитектура бота ОбучAI

## Поток обработки запроса

1. **Вход:** сообщение пользователя в Telegram.
2. **Лог:** в консоль пишется исходный текст (до нормализации).
3. **Блок 1 — Нормализация:** классификация типа (question | abuse | off_topic | cheat) и нормализованный запрос. Результат дублируется в лист **Normalization** (Google Таблица), если настроено.
4. **Ветвление по типу:**
   - **abuse / off_topic / cheat:** шаблонный ответ → **Блок 4 Judge** (контекст пустой, проверка корректности типа) → запись в judge_log + лист Judge → ответ пользователю **без кнопок**, выход.
   - **question:** переход к RAG.
5. **Блок 2 — RAG:** поиск чанков по нормализованному запросу.
   - **Нет чанков:** отказ «в базе не найдено» → Judge → judge_log + Judge в таблице → ответ **без кнопок**, выход.
   - **Есть чанки:** контекст собирается, переход к генерации.
6. **Блок 3 — Генерация:** ответ по контексту (GigaChat).
7. **Блок 4 — Judge:** полная оценка (relevance, groundedness, safety, completeness, question_type_correct, correct_refusal, verdict). Если type_ok=0 или refusal_ok=0, показатели rel/grnd/safe/compl в ответе Judge обнуляются.
8. **Идентификация запроса:** генерируется **request_id** (UUID), сохраняется в user_contexts вместе с question, answer, judge_verdict.
9. **Логи:** запись в judge_log.json и в лист **Judge** (в т.ч. rel, grnd, safe, compl, score, type_ok, refusal_ok). Создаётся запись в feedback_log с request_id и rating=null; дублирование в лист **Feedback**.
10. **Блок 5:** пользователю показывается ответ и **кнопки** «Полезно» / «Не помогло» (только для ветки question с чанками).
11. **Нажатие кнопки:** по request_id обновляется запись в feedback_log (rating=helpful/not_helpful) и в листе Feedback. При «Не помогло» показываются кнопки «Вызвать куратора» / «Закрыть».
12. **Эскалация:** при «Вызвать куратора» — запись в escalation_log, дублирование в лист **Escalation**, отправка сообщения куратору (CURATOR_CHAT_ID).

Кнопки фидбэка и эскалации есть только для ответов по курсу (type=question с полученным ответом из RAG).

---

## Схема (ASCII)

```
                    ┌─────────────────────────────────────┐
                    │         Telegram: сообщение         │
                    └─────────────────┬───────────────────┘
                                      │
                    ┌─────────────────▼───────────────────┐
                    │  Лог: исходный текст (до нормализации) │
                    └─────────────────┬───────────────────┘
                                      │
                    ┌─────────────────▼───────────────────┐
                    │  Блок 1: Нормализация               │
                    │  type, normalized_query             │
                    │  → Sheets: Normalization (опц.)      │
                    └─────────────────┬───────────────────┘
                                      │
              ┌───────────────────────┴───────────────────────┐
              │                                                 │
    abuse / off_topic / cheat                            question
              │                                                 │
              ▼                                                 ▼
    ┌─────────────────────┐                         ┌─────────────────────┐
    │ Шаблонный ответ     │                         │ Блок 2: RAG         │
    │ (get_response_      │                         │ поиск чанков        │
    │  template)          │                         └──────────┬──────────┘
    └──────────┬──────────┘                                      │
              │                                    ┌────────────┴────────────┐
              │                                    │ нет чанков              │ есть
              │                                    ▼                         ▼
              │                         ответ «не найдено»          Блок 3: Генерация
              │                         (без кнопок)                         │
              │                                    │                         │
              └────────────────┬──────────────────┴─────────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │ Блок 4: Judge       │  ВСЕ запросы
                    │ rel, grnd, safe,    │  question_type_correct, correct_refusal
                    │ compl, verdict,     │  при 0 → rel/grnd/safe/compl = 0
                    │ score               │
                    │ → judge_log.json    │
                    │ → Sheets: Judge     │
                    └──────────┬──────────┘
                               │
              ┌────────────────┴────────────────┐
              │                                  │
    ответ без кнопок                  question + ответ из RAG
    (шаблон / отказ)                            │
                                                ▼
                                    request_id, create_feedback_entry
                                    → feedback_log (rating=null)
                                    → Sheets: Feedback
                                                │
                                    ┌───────────▼───────────┐
                                    │ Блок 5: кнопки       │
                                    │ Полезно / Не помогло │
                                    └───────────┬──────────┘
                                                │
                        ┌───────────────────────┴───────────────────────┐
                        │ нажатие «Полезно»     │ нажатие «Не помогло»  │
                        ▼                       ▼                       │
                update_feedback_rating   update_feedback_rating          │
                (request_id, helpful)    (request_id, not_helpful)      │
                → Feedback в Sheets     кнопки: Куратор / Закрыть       │
                                                        │
                                                        ▼ «Вызвать куратора»
                                                log_escalation
                                                → escalation_log.json
                                                → Sheets: Escalation
                                                → сообщение куратору
```

---

## Модули (корень проекта)

| Файл | Назначение |
|------|------------|
| `bot.py` | Точка входа, Telegram, связка блоков 1–5, вызов дублирования в Sheets |
| `config.py` | Конфигурация (пути, ключи, RAG/LLM, GOOGLE_SHEET_ID, GOOGLE_CREDENTIALS_PATH) |
| `gigachat_client.py` | Клиент GigaChat API (async, OAuth) |
| `block1_normalization.py` | Классификация и нормализация запроса (LLM) |
| `block2_rag.py` | Загрузка документов, чанки, ChromaDB, гибридный поиск |
| `block3_generation.py` | Генерация ответа по контексту (GigaChat) |
| `block4_judge.py` | LLM-Judge: оценка всех запросов; при type_ok=0 или refusal_ok=0 обнуление rel/grnd/safe/compl |
| `block5_feedback.py` | Логи в файлы (feedback_log, judge_log, escalation_log), request_id, create_feedback_entry, update_feedback_rating, эскалация |
| `logs_to_sheets.py` | Дублирование в Google Таблицу: Normalization, Judge, Feedback, Escalation (фоновые потоки) |

---

## Данные и логи

### Файлы (каталог `logs/`)

| Файл | Содержимое |
|------|------------|
| `feedback_log.json` | Список записей: request_id, user_id, question, answer, query_type, judge_verdict, rating (null → helpful/not_helpful при нажатии), feedback_at |
| `judge_log.json` | Каждая оценка Judge: timestamp, request_id, user_id, question, answer, judge_verdict |
| `escalation_log.json` | Эскалации: user_id, question, answer, judge_verdict, escalated |

### Google Таблица (опционально)

При заданных `GOOGLE_SHEET_ID` и `GOOGLE_CREDENTIALS_PATH` в таблице создаются листы:

| Лист | Колонки |
|------|---------|
| **Normalization** | timestamp, user_id, original_text, normalized_query, type |
| **Judge** | timestamp, request_id, user_id, question, answer, **rel**, **grnd**, **safe**, **compl**, verdict, score, type_ok, refusal_ok, explanation |
| **Feedback** | timestamp, request_id, user_id, query_type, rating, feedback_at, question, answer (обновление rating по request_id при нажатии кнопки) |
| **Escalation** | timestamp, user_id, question, answer, escalated |

Остальное: `knowledge_base/`, `vector_db/` (ChromaDB).

---

## Конфигурация

- **.env:** `TELEGRAM_BOT_TOKEN`, `GIGACHAT_AUTH_KEY`, `CURATOR_CHAT_ID`, при необходимости `GOOGLE_SHEET_ID`, `GOOGLE_CREDENTIALS_PATH`.
- **config.py:** пути (LOGS_PATH, KNOWLEDGE_BASE_PATH, VECTOR_DB_PATH), параметры RAG (CHUNK_SIZE, TOP_K, TOP_K_CANDIDATES), температура, курс (COURSE_NAME). ID таблицы можно задать полным URL — из него извлекается ID.

Таблицу нужно открыть на редактирование для email сервисного аккаунта (поле `client_email` в JSON ключа).
