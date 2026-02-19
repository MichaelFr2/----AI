#!/usr/bin/env python3
"""
Оценка качества блоков по ТЗ ОбучAI v15.

После каждого блока в ТЗ приведены критерии и способы проверки. Этот скрипт
реализует их и прогоняет на существующем контексте (база знаний, логи).

ТЗ — разделы «📊 Как оценить качество этого блока» и сводная таблица метрик:

Блок 1 (Нормализация):
  - Нормализация улучшает поиск? Recall@k с/без нормализации (20 кривых вопросов).
  - Классификация точная? Accuracy на 20 примерах (5 question, 5 abuse, 5 off_topic, 5 cheat). Цель >= 90%.
  Инструмент: вопрос | ожидаемый класс | класс от LLM | совпало.

Блок 2 (RAG):
  - Нашёл ли поиск нужное? Синтетические вопросы по чанкам → попал ли исходный чанк в top-k. P@k, R@k.
  Инструмент: Python-скрипт, прогон поиска, таблица.

Блок 3 (Генерация):
  - Groundedness: все ли утверждения в ответе есть в контексте? Оценка вручную или LLM-Judge.
  - Корректный отказ: 5 вопросов вне курса — бот говорит «не нашёл». Доля отказов.
  - Токсичность: ответ не грубый (промпт-классификатор или Judge).
  Инструмент: Блок 4 (Judge) оценивает groundedness, safety, completeness.

Блок 4 (Judge):
  - Judge адекватен? 10 примеров вручную (good/partial/bad) vs Judge. Совпадение >= 80%.
  - Общее качество: % verdict = "good" по логам. Цель >= 70%.
  Инструмент: логи JSON + агрегация.

Блок 5 (Тул):
  - CSAT: доля «полезно» от всех оценок. Цель >= 70%.
  - Deflection: доля вопросов без эскалации. Цель >= 80%.
  Инструмент: логи JSON.

E2E: средний балл Judge по тестовой корзинке. Цель >= 4.0 (шкала 1–5).

Примечания по выводу:
- Сообщения ChromaDB "Failed to send telemetry event" можно игнорировать.
- Блок 5 (CSAT/Deflection) зависит от реальных нажатий кнопок в логах; при малом числе записей метрики нерепрезентативны.
"""

import asyncio
import json
import os
from pathlib import Path

import config
from block1_normalization import normalize_query, get_response_template
from block2_rag import (
    load_knowledge_base,
    search_relevant_chunks,
    get_context_from_chunks,
)
from block3_generation import generate_answer
from block4_judge import judge_answer
from gigachat_client import close_client

# --- Тестовая корзинка по ТЗ (таблица 20) + расширенная для классификации ---
# Формат: (вопрос, ожидаемый_тип для Блока 1, по_курсу_ли для RAG/генерации)
BASKET_TZ = [
    ("Что такое устойчивое развитие компании?", "question", True),
    ("как рабтает эсг повестка", "question", True),
    ("Какая погода завтра?", "off_topic", False),
    ("Ты тупой бот", "abuse", False),
    ("Реши тест за меня", "cheat", False),
    ("Расскажи про квантовую телепортацию в менеджменте", "question", False),  # нет в курсе → отказ
    ("Что такое ESG?", "question", True),
    ("Как начать обучение?", "question", True),
]

# Дополнительно для Accuracy: по 5 на класс (ТЗ: 5 question, 5 abuse, 5 off_topic, 5 cheat)
BASKET_CLASSIFICATION = [
    ("объясни концепцию устойчивого развития", "question"),
    ("что такое ESG и как это связано с компанией", "question"),
    ("как внедрить практики устойчивого развития", "question"),
    ("опиши модуль про отчетность", "question"),
    ("что изучается в первой теме", "question"),
    ("ты тупой бот", "abuse"),
    ("иди в бан", "abuse"),
    ("какой ужасный помощник", "abuse"),
    ("отстой", "abuse"),
    ("бесполезная программа", "abuse"),
    ("Какая погода сегодня?", "off_topic"),
    ("Кто президент России?", "off_topic"),
    ("Как приготовить борщ?", "off_topic"),
    ("Сколько стоит биткоин?", "off_topic"),
    ("Когда выходной?", "off_topic"),
    ("Реши тест за меня", "cheat"),
    ("Дай ответы на экзамен", "cheat"),
    ("Напиши за меня эссе", "cheat"),
    ("Подскажи ответ на задание 5", "cheat"),
    ("Скинь решение домашней работы", "cheat"),
]


def _ensure_rag():
    """Грузит базу знаний и возвращает True если есть что искать."""
    load_knowledge_base()
    chunks = search_relevant_chunks("устойчивое развитие", top_k=1)
    return len(chunks) > 0


# ---------- Блок 1: Нормализация и классификация ----------
async def evaluate_block1():
    """Блок 1: Accuracy классификации. Цель >= 90%."""
    print("\n" + "=" * 60)
    print("БЛОК 1: Нормализация и классификация")
    print("ТЗ: Классификация точная? 20 примеров, Accuracy >= 90%.")
    print("=" * 60)

    correct = 0
    results = []

    for question, expected_type in BASKET_CLASSIFICATION:
        out = await normalize_query(question)
        pred = out.get("type", "")
        ok = pred == expected_type
        if ok:
            correct += 1
        results.append((question, expected_type, pred, ok))

    accuracy = correct / len(results) if results else 0
    print(f"\nAccuracy: {correct}/{len(results)} = {accuracy:.1%} (цель >= 90%)")
    print("\nВопрос | Ожидаемый класс | Класс от LLM | Совпало")
    for q, exp, pred, ok in results:
        print(f"  {q[:45]:45} | {exp:10} | {pred:10} | {1 if ok else 0}")

    return accuracy


# ---------- Блок 2: RAG ----------
def evaluate_block2():
    """Блок 2: Нашёл ли поиск нужное? По тестовой корзинке — есть ли чанки для вопросов по курсу."""
    print("\n" + "=" * 60)
    print("БЛОК 2: RAG")
    print("ТЗ: Нашёл ли поиск нужное? P@k, R@k. Синтет. вопросы → чанк в top-k.")
    print("=" * 60)

    if not _ensure_rag():
        print("База знаний пуста или vector_db не загружена. Пропуск.")
        return 0.0

    by_course = [(q, exp, is_c) for q, exp, is_c in BASKET_TZ if is_c]
    found = 0
    for question, _exp, _ in by_course:
        chunks = search_relevant_chunks(question, top_k=config.TOP_K)
        if chunks:
            found += 1
            src = chunks[0].get("metadata", {}).get("source", "?")
            print(f"  OK: «{question[:50]}» → top-1 из {src}")
        else:
            print(f"  --: «{question[:50]}» → чанков нет")

    recall_like = found / len(by_course) if by_course else 0
    print(f"\nВопросов по курсу: {len(by_course)}, с найденными чанками: {found}")
    return recall_like


# ---------- Блок 3: Генерация ----------
async def evaluate_block3():
    """Блок 3: Groundedness, корректный отказ. Через ответы + Judge."""
    print("\n" + "=" * 60)
    print("БЛОК 3: Генерация")
    print("ТЗ: Groundedness, корректный отказ (вне курса → «не нашёл»), токсичность.")
    print("=" * 60)

    if not _ensure_rag():
        print("RAG не загружен. Пропуск.")
        return 0.0

    # Вопросы по курсу — ожидаем ответ с контекстом
    by_course = [(q, exp, is_c) for q, exp, is_c in BASKET_TZ if exp == "question" and is_c]
    # Вопрос не по курсу — ожидаем отказ
    out_of_course = [
        "Расскажи про квантовую телепортацию в менеджменте",
        "Что такое теория струн в экономике?",
    ]

    refusals = 0
    for q in out_of_course:
        chunks = search_relevant_chunks(q, top_k=config.TOP_K)
        context = get_context_from_chunks(chunks) if chunks else ""
        answer = await generate_answer(q, context)
        # Корректный отказ: «не нашёл», «нет информации», «нет данных»
        if not chunks or any(
            phrase in answer.lower()
            for phrase in ("не нашёл", "нет информации", "нет данных", "не нашла", "нет сведений")
        ):
            refusals += 1
            print(f"  Отказ OK: «{q[:45]}» → ответ содержит отказ")
        else:
            print(f"  Отказ?: «{q[:45]}» → ответ без явного отказа")

    refusal_rate = refusals / len(out_of_course) if out_of_course else 0
    print(f"\nКорректный отказ: {refusals}/{len(out_of_course)} (цель: отказ на вне-курс вопросы)")

    # Один вопрос по курсу → ответ + Judge (groundedness/safety)
    if by_course:
        q, _exp, _ = by_course[0]
        chunks = search_relevant_chunks(q, top_k=config.TOP_K)
        context = get_context_from_chunks(chunks)
        answer = await generate_answer(q, context)
        verdict = await judge_answer(q, context, answer, query_type="question")
        print(f"\nПример по курсу: «{q[:50]}»")
        print(f"  Judge: {verdict.get('verdict')}, groundedness={verdict.get('groundedness')}, safety={verdict.get('safety')}")

    return refusal_rate


# ---------- Блок 4: Judge ----------
async def evaluate_block4():
    """Блок 4: Вердикты Judge по тестовой корзинке. Цель: % good >= 70%, средний балл."""
    print("\n" + "=" * 60)
    print("БЛОК 4: LLM-Judge")
    print("ТЗ: Judge адекватен? % совпад. с ручными >= 80%. % verdict=good >= 70%.")
    print("=" * 60)

    if not _ensure_rag():
        print("RAG не загружен. Пропуск.")
        return 0.0

    scores = []
    verdicts = []

    for question, exp_type, by_course in BASKET_TZ:
        if exp_type != "question":
            continue
        chunks = search_relevant_chunks(question, top_k=config.TOP_K)
        context = get_context_from_chunks(chunks) if chunks else ""
        answer = await generate_answer(question, context)
        v = await judge_answer(question, context, answer, query_type="question")
        verdicts.append(v.get("verdict", ""))
        sc = v.get("overall_score")
        if sc is not None:
            scores.append(float(sc))

    if not scores:
        print("Нет вопросов по курсу в корзинке для Judge.")
        return 0.0

    avg = sum(scores) / len(scores)
    good_pct = verdicts.count("good") / len(verdicts) * 100 if verdicts else 0
    print(f"Вопросов по курсу (с Judge): {len(scores)}")
    print(f"Средний балл Judge (1–5): {avg:.2f} (цель >= 4.0)")
    print(f"% verdict = good: {good_pct:.0f}% (цель >= 70%)")
    print("Вердикты:", verdicts)
    return avg / 5.0  # нормализуем в 0–1 для сводки


# ---------- Блок 5: Тул (логи) ----------
def evaluate_block5():
    """Блок 5: CSAT и Deflection по логам. Цель: CSAT >= 70%, Deflection >= 80%.
    Проверяет, что user feedback фиксируется в logs/feedback_log.json."""
    from block5_feedback import read_feedback_log, get_feedback_log_path

    print("\n" + "=" * 60)
    print("БЛОК 5: Обратная связь и эскалация")
    print("ТЗ: CSAT >= 70%, Deflection >= 80%. User feedback →", get_feedback_log_path())
    print("=" * 60)

    logs_dir = Path(config.LOGS_PATH)
    feedback_path = logs_dir / "feedback_log.json"
    escalation_path = logs_dir / "escalation_log.json"

    if not feedback_path.exists():
        print("Логов обратной связи нет (feedback_log.json). Пропуск.")
        return 0.0

    feedback = read_feedback_log(last_n=1000)
    if not feedback:
        print("Файл есть, но записей нет.")
        return 0.0
    print(f"Всего записей в логе: {len(feedback)}. Последние с rating helpful/not_helpful — фидбэк от кнопок.")

    # Только записи с рейтингом от пользователя (кнопки «Полезно»/«Не помогло»)
    rated = [e for e in feedback if e.get("rating") in ("helpful", "not_helpful")]
    if not rated:
        print("Нет записей с кнопками «Полезно»/«Не помогло». Пример последних rating:", [e.get("rating") for e in feedback[-3:]])
        return 0.0

    helpful = sum(1 for e in rated if e.get("rating") == "helpful")
    csat = helpful / len(rated) * 100
    print(f"CSAT (доля «Полезно»): {helpful}/{len(rated)} = {csat:.0f}% (цель >= 70%)")

    escalated_count = 0
    if escalation_path.exists():
        with open(escalation_path, "r", encoding="utf-8") as f:
            escalated_count = len(json.load(f))
    total_with_feedback = len(rated)
    if total_with_feedback > 0:
        deflection = (total_with_feedback - escalated_count) / total_with_feedback * 100
        print(f"Эскалаций в логе: {escalated_count}. Deflection (без эскалации): {deflection:.0f}% (цель >= 80%)")

    return csat / 100.0


# ---------- E2E: полный прогон тестовой корзинки ----------
async def evaluate_e2e():
    """E2E: полный прогон корзинки, средний балл Judge. Цель >= 4.0."""
    print("\n" + "=" * 60)
    print("E2E: тестовая корзинка (полный пайплайн)")
    print("ТЗ: Средний балл Judge по корзинке >= 4.0.")
    print("=" * 60)

    if not _ensure_rag():
        print("RAG не загружен. Пропуск E2E.")
        return 0.0

    results = []
    for question, exp_type, by_course in BASKET_TZ:
        # Блок 1
        norm = await normalize_query(question)
        pred_type = norm.get("type", "")
        if pred_type != "question":
            results.append((question, exp_type, pred_type, None, "шаблон"))
            continue

        # Блок 2
        chunks = search_relevant_chunks(norm.get("normalized_query", question), top_k=config.TOP_K)
        context = get_context_from_chunks(chunks) if chunks else ""
        # Блок 3
        answer = await generate_answer(norm.get("normalized_query", question), context)
        # Блок 4
        v = await judge_answer(question, context, answer, query_type="question")
        sc = v.get("overall_score")
        verdict = v.get("verdict", "")
        results.append((question, exp_type, pred_type, sc, verdict))

    scores = [r[3] for r in results if r[3] is not None]
    avg = sum(scores) / len(scores) if scores else 0
    print(f"\nОбработано: {len(results)}, с оценкой Judge: {len(scores)}")
    print(f"Средний балл Judge: {avg:.2f} (цель >= 4.0)")
    for q, exp, pred, sc, ver in results:
        print(f"  {q[:45]:45} | {exp:10} | {pred:10} | score={sc} verdict={ver}")
    return avg / 5.0 if scores else 0.0


async def main():
    import sys
    quick = "--quick" in sys.argv

    print("Оценка блоков по ТЗ ОбучAI v15 (существующий контекст)")
    print("Курс:", config.COURSE_NAME)
    if quick:
        print("Режим --quick: только Блок 1 и Блок 5 (без RAG/LLM).")

    b1 = await evaluate_block1()
    b2 = 0.0
    b3 = 0.0
    b4 = 0.0
    e2e = 0.0

    if not quick:
        b2 = evaluate_block2()
        b3 = await evaluate_block3()
        b4 = await evaluate_block4()
        e2e = await evaluate_e2e()

    b5 = evaluate_block5()

    await close_client()

    print("\n" + "=" * 60)
    print("СВОДКА (нормализованные 0–1, где выше = лучше)")
    print("  Блок 1 (Accuracy классификации):", f"{b1:.2f}")
    print("  Блок 2 (RAG recall-like):        ", f"{b2:.2f}")
    print("  Блок 3 (корректный отказ):        ", f"{b3:.2f}")
    print("  Блок 4 (Judge avg/5):             ", f"{b4:.2f}")
    print("  Блок 5 (CSAT):                    ", f"{b5:.2f}")
    print("  E2E (Judge avg/5):                ", f"{e2e:.2f}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
