"""Блок 1: Нормализация запроса (LLM)"""
import json
from typing import Dict, Any
import config
from gigachat_client import get_client

SYSTEM_PROMPT = f"""Ты - система нормализации запросов для курса {config.COURSE_NAME}.

Твоя задача:
1. Переформулировать запрос студента в чистый поисковый запрос (убрать опечатки, сленг, привести к формальному виду)
2. Классифицировать запрос по типу

Критически важно:
- Любое оскорбление (тупой, отстой, иди в бан, бесполезный и т.п.) в адрес бота или помощника — ВСЕГДА type: "abuse", никогда "question".
- Вопрос не по материалам курса — ВСЕГДА type: "off_topic". "question" — ТОЛЬКО если вопрос явно про темы, термины, модули и задания курса.
- Темы из других областей (физика, квантовая механика, телепортация, погода, политика, кулинария, криптовалюты, кино, общие факты не из курса) — ВСЕГДА off_topic, даже если сформулированы как «в менеджменте» или «в контексте курса».

Типы запросов:
- "question" - только реальный вопрос по содержанию курса (темы, термины, модули, задания курса)
- "abuse" - оскорбление или неуважительное обращение
- "off_topic" - вопрос не по теме курса (в т.ч. научные/бытовые темы, не входящие в программу курса)
- "cheat" - попытка получить ответ на экзамен/тест или обмануть систему

Формат ответа - строго JSON:
{{
    "type": "question" | "abuse" | "off_topic" | "cheat",
    "normalized_query": "очищенный поисковый запрос"
}}

Примеры:
Вход: "как работает раг?"
Выход: {{"type": "question", "normalized_query": "как работает RAG"}}

Вход: "ты тупой бот"
Выход: {{"type": "abuse", "normalized_query": "оскорбление"}}

Вход: "какая погода сегодня?"
Выход: {{"type": "off_topic", "normalized_query": "вопрос не по теме курса"}}

Вход: "дай ответы на экзамен"
Выход: {{"type": "cheat", "normalized_query": "попытка получить ответы на экзамен"}}

Вопросы НЕ по теме курса (всегда off_topic): погода, политика, кулинария, криптовалюты, физика, квантовая телепортация, телепортация, общие факты не из курса.
Вход: "Кто президент России?"
Выход: {{"type": "off_topic", "normalized_query": "вопрос не по теме курса"}}

Вход: "Как приготовить борщ?"
Выход: {{"type": "off_topic", "normalized_query": "вопрос не по теме курса"}}

Вход: "рассказать про квантовую телепортацию в менеджменте"
Выход: {{"type": "off_topic", "normalized_query": "вопрос не по теме курса"}}

Вход: "что такое телепортация"
Выход: {{"type": "off_topic", "normalized_query": "вопрос не по теме курса"}}

Просьбы решить задание/тест/домашку за студента (cheat): "подскажи ответ на задание", "реши за меня", "скинь решение".
Вход: "Подскажи ответ на задание 5" → {{"type": "cheat", "normalized_query": "попытка получить ответ на задание"}}

ВАЖНО: Отвечай ТОЛЬКО валидным JSON, без дополнительного текста.
"""

RESPONSE_TEMPLATES = {
    "abuse": "Пожалуйста, будьте вежливы. Я здесь, чтобы помочь вам с вопросами по курсу.",
    "off_topic": f"Этот вопрос не относится к курсу {config.COURSE_NAME}. Пожалуйста, задайте вопрос по материалам курса.",
    "cheat": "Я не могу помочь с получением ответов на экзамены или тесты. Если у вас есть вопросы по материалам курса, я буду рад помочь."
}


async def normalize_query(user_query: str) -> Dict[str, Any]:
    """
    Нормализует запрос пользователя и классифицирует его.
    
    Returns:
        {
            "type": str,
            "normalized_query": str,
            "original_query": str
        }
    """
    try:
        client = await get_client()
        
        user_message = user_query
        
        response_text = await client.chat_completion(
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            max_tokens=200,
            temperature=0.3,
            response_format="json_object"
        )
        
        # Парсим JSON ответ
        # GigaChat может вернуть JSON в тексте, попробуем извлечь
        try:
            result = json.loads(response_text)
        except json.JSONDecodeError:
            # Если не JSON, попробуем найти JSON в тексте
            import re
            json_match = re.search(r'\{[^}]+\}', response_text)
            if json_match:
                result = json.loads(json_match.group())
            else:
                raise
        
        result["original_query"] = user_query
        
        # Валидация типа
        if result.get("type") not in ["question", "abuse", "off_topic", "cheat"]:
            result["type"] = "question"
        
        return result
        
    except Exception as e:
        # Fallback: если ошибка, считаем вопросом
        return {
            "type": "question",
            "normalized_query": user_query,
            "original_query": user_query
        }


def get_response_template(query_type: str) -> str:
    """Возвращает шаблонный ответ для типов, не требующих RAG"""
    return RESPONSE_TEMPLATES.get(query_type, "Извините, не могу обработать этот запрос.")
