"""Блок 5: Обратная связь + эскалация (тул по ТЗ v15).
Кнопки логируются; при «Не помогло» показывается модалка; эскалация в куратора — только по кнопке «Вызвать куратора»."""
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional
import config

# Создаем папку для логов
os.makedirs(config.LOGS_PATH, exist_ok=True)

FEEDBACK_LOG_FILE = os.path.join(config.LOGS_PATH, "feedback_log.json")
ESCALATION_LOG_FILE = os.path.join(config.LOGS_PATH, "escalation_log.json")
JUDGE_LOG_FILE = os.path.join(config.LOGS_PATH, "judge_log.json")


def log_feedback(user_id: int, question: str, answer: str, rating: str, judge_verdict: Optional[Dict] = None):
    """Логирует обратную связь от студента"""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "user_id": user_id,
        "question": question,
        "answer": answer,
        "rating": rating,  # "helpful", "not_helpful", "judge_only", "not_rated"
        "judge_verdict": judge_verdict
    }
    
    # Загружаем существующие логи
    if os.path.exists(FEEDBACK_LOG_FILE):
        try:
            with open(FEEDBACK_LOG_FILE, 'r', encoding='utf-8') as f:
                logs = json.load(f)
        except (json.JSONDecodeError, IOError):
            logs = []
    else:
        logs = []
    
    logs.append(log_entry)
    
    # Сохраняем
    try:
        with open(FEEDBACK_LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"Ошибка записи в feedback_log.json: {e}")


def log_judge_only(user_id: int, question: str, answer: str, judge_verdict: Dict):
    """Логирует только оценку Judge (без обратной связи от пользователя)"""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "user_id": user_id,
        "question": question,
        "answer": answer,
        "judge_verdict": judge_verdict,
        "user_feedback": None  # Пользователь еще не дал обратную связь
    }
    
    # Загружаем существующие логи
    if os.path.exists(JUDGE_LOG_FILE):
        try:
            with open(JUDGE_LOG_FILE, 'r', encoding='utf-8') as f:
                logs = json.load(f)
        except (json.JSONDecodeError, IOError):
            logs = []
    else:
        logs = []
    
    logs.append(log_entry)
    
    # Сохраняем
    try:
        with open(JUDGE_LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"Ошибка записи в judge_log.json: {e}")


def log_escalation(user_id: int, question: str, answer: str, judge_verdict: Optional[Dict] = None):
    """Логирует эскалацию к куратору"""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "user_id": user_id,
        "question": question,
        "answer": answer,
        "judge_verdict": judge_verdict,
        "escalated": True
    }
    
    # Загружаем существующие логи
    if os.path.exists(ESCALATION_LOG_FILE):
        try:
            with open(ESCALATION_LOG_FILE, 'r', encoding='utf-8') as f:
                logs = json.load(f)
        except (json.JSONDecodeError, IOError):
            logs = []
    else:
        logs = []
    
    logs.append(log_entry)
    
    # Сохраняем
    try:
        with open(ESCALATION_LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"Ошибка записи в escalation_log.json: {e}")
    
    return log_entry


def format_escalation_message(user_id: int, question: str, answer: str, judge_verdict: Optional[Dict] = None) -> str:
    """Форматирует сообщение для куратора"""
    message = f"""🔔 Эскалация от студента

👤 Студент ID: {user_id}

❓ Вопрос:
{question}

🤖 Ответ бота:
{answer}
"""
    
    if judge_verdict:
        verdict = judge_verdict.get("verdict", "N/A")
        message += f"\n📊 Judge verdict: {verdict}"
        if judge_verdict.get("overall_score") is not None:
            message += f" (средний балл 1–5: {judge_verdict['overall_score']})"
        if judge_verdict.get("explanation"):
            message += f"\nКомментарий: {judge_verdict['explanation']}"
    
    message += "\n\nПожалуйста, свяжитесь со студентом."
    
    return message
