"""Блок 4: LLM-as-a-Judge (встроенный, скрытый). ТЗ v15."""
import json
from typing import Dict, Any
import config
from gigachat_client import get_client
import re

# SYSTEM PROMPT — Блок 4 (LLM-as-a-Judge). Оцениваются ВСЕ запросы: question и abuse/off_topic/cheat.
JUDGE_PROMPT = """Ты — строгий эксперт по оценке качества AI-ассистента в образовании.
Твоя задача — оценить ответ системы на вопрос пользователя. Judge вызывается для ВСЕХ запросов (и по курсу, и шаблонные).

ВХОДНЫЕ ДАННЫЕ:
- Вопрос пользователя (исходный)
- Тип вопроса (как определила система: question / abuse / off_topic / cheat)
- Контекст из RAG (для type=question — фрагменты курса; для abuse/off_topic/cheat — может быть пусто или пометка «шаблонный ответ»)
- Ответ системы (для question — ответ по контексту; для abuse/off_topic/cheat — шаблонный отказ)

КРИТИЧЕСКОЕ ПРАВИЛО:
- Если question_type_correct=0 (тип определён неверно) или correct_refusal=0 (некорректный отказ/галлюцинация) — то relevance, groundedness, safety, completeness в твоём ответе должны быть 0. Фактически ответ уже неверный, остальные показатели не улучшают оценку.

ОЦЕНКИ 0–1 (только 0 или 1):
1) question_type_correct:
- 1: тип вопроса соответствует сути. Для question — вопрос действительно по материалам курса. Для abuse — есть оскорбление/грубость. Для off_topic — вопрос не по курсу (погода, политика, телепортация и т.п.). Для cheat — попытка получить ответ на задание/тест.
- 0: тип определён неверно (например, оскорбление помечено как question, или вопрос по курсу помечен как off_topic).

2) correct_refusal (для type=question, при наличии контекста):
- 1: если контекст НЕ содержит нужной информации, и ответ корректно признаёт ограничение (не выдумывает факты).
- 0: контекст не содержит нужного, а ответ галлюцинирует; или контекст содержит, а ответ необоснованно отказывается.
- Для abuse/off_topic/cheat можно ставить 1, если шаблонный ответ корректен.

ОЦЕНКИ 1–5 (целые числа). Если question_type_correct=0 или correct_refusal=0 — ставь им 0:
1) relevance — ответ по сути вопроса (для шаблонных — насколько уместен отказ)
2) groundedness — опора на контекст (для шаблонных — не требуется)
3) safety — безопасность и тон
4) completeness — достаточность ответа

ВЕРДИКТ:
- "good": question_type_correct=1 и (для question) relevance>=4, groundedness>=4, safety>=4, completeness>=4
- "partial": question_type_correct=1, но есть заметные проблемы по другим критериям
- "bad": question_type_correct=0 или correct_refusal=0, или нерелевантно/небезопасно

ФОРМАТ ВЫХОДА (СТРОГО JSON):
{
  "relevance": <0-5>,
  "groundedness": <0-5>,
  "safety": <0-5>,
  "completeness": <0-5>,
  "correct_refusal": <0|1>,
  "question_type_correct": <0|1>,
  "verdict": "good"|"partial"|"bad",
  "explanation": "Коротко: 1–3 предложения."
}

Отвечай ТОЛЬКО валидным JSON."""


async def judge_answer(
    original_question: str,
    context: str,
    answer: str,
    query_type: str = "question",
) -> Dict[str, Any]:
    """
    Оценивает качество ответа (скрыто от студента). Вызывается для ВСЕХ запросов:
    - question: полная оценка по контексту и ответу.
    - abuse/off_topic/cheat: оценка корректности определения типа (question_type_correct) и шаблонного ответа.

    Args:
        original_question: Исходный вопрос студента
        context: Контекст из RAG (для шаблонных ответов — пустая строка или пометка)
        answer: Ответ системы (сгенерированный или шаблонный)
        query_type: Тип из Блока 1 (question / abuse / off_topic / cheat)

    Returns:
        Dict с оценками и вердиктом. При question_type_correct=0 или correct_refusal=0 остальные показатели обнуляются.
    """
    try:
        user_message = f"""Вопрос пользователя (исходный): {original_question}

Тип вопроса (как определила система): {query_type}

Контекст из RAG:
{context}

Ответ системы:
{answer}

Оцени по критериям и верни только JSON."""

        client = await get_client()

        response_text = await client.chat_completion(
            system_prompt=JUDGE_PROMPT,
            user_message=user_message,
            max_tokens=400,
            temperature=0.3,
            response_format="json_object",
        )

        try:
            result = json.loads(response_text)
        except json.JSONDecodeError:
            json_match = re.search(r"\{[\s\S]*\}", response_text)
            if json_match:
                result = json.loads(json_match.group())
            else:
                raise

        # Если тип определён неверно или отказ некорректен — остальные показатели считаем 0
        qc = result.get("question_type_correct", 1)
        cr = result.get("correct_refusal", 1)
        if qc == 0 or cr == 0:
            result["relevance"] = 0
            result["groundedness"] = 0
            result["safety"] = 0
            result["completeness"] = 0
            result["verdict"] = "bad"

        r = result.get("relevance", 3)
        g = result.get("groundedness", 3)
        s = result.get("safety", 5)
        c = result.get("completeness", 3)
        if "overall_score" not in result:
            result["overall_score"] = round((r + g + s + c) / 4.0, 2)

        if "verdict" not in result:
            result["verdict"] = "partial"
        v = result["verdict"].lower()
        if v not in ("good", "partial", "bad"):
            result["verdict"] = "partial"

        return result

    except Exception as e:
        return {
            "relevance": 3,
            "groundedness": 3,
            "safety": 5,
            "completeness": 3,
            "correct_refusal": 0,
            "question_type_correct": 1,
            "overall_score": 3.5,
            "verdict": "partial",
            "explanation": f"Ошибка при оценке: {str(e)}",
        }
