"""Блок 5: Обратная связь + эскалация (тул по ТЗ v15).
Кнопки только для type=question. На каждый ответ с кнопками создаётся запись с request_id;
при нажатии «Полезно»/«Не помогло» запись в логе обновляется по request_id."""
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
import config

logger = logging.getLogger(__name__)

# Создаем папку для логов (абсолютный путь, чтобы не зависеть от cwd при запуске)
LOGS_DIR = os.path.abspath(config.LOGS_PATH)
os.makedirs(LOGS_DIR, exist_ok=True)

FEEDBACK_LOG_FILE = os.path.join(LOGS_DIR, "feedback_log.json")
ESCALATION_LOG_FILE = os.path.join(LOGS_DIR, "escalation_log.json")
JUDGE_LOG_FILE = os.path.join(LOGS_DIR, "judge_log.json")


def _safe_judge_verdict(judge_verdict: Optional[Dict]) -> Optional[Dict]:
    """Копия judge_verdict только из JSON-сериализуемых типов (избегаем TypeError при записи)."""
    if judge_verdict is None:
        return None
    try:
        return json.loads(json.dumps(judge_verdict, default=str, ensure_ascii=False))
    except (TypeError, ValueError):
        return {k: str(v) for k, v in judge_verdict.items()}


def _load_feedback_log() -> list:
    """Читает feedback_log.json, возвращает список записей."""
    if not os.path.exists(FEEDBACK_LOG_FILE):
        return []
    try:
        with open(FEEDBACK_LOG_FILE, "r", encoding="utf-8") as f:
            logs = json.load(f)
    except (json.JSONDecodeError, IOError):
        return []
    return logs if isinstance(logs, list) else []


def _save_feedback_log(logs: list) -> None:
    """Записывает список в feedback_log.json."""
    with open(FEEDBACK_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())


def generate_request_id() -> str:
    """Уникальный id запроса (для связи ответа и нажатия кнопки фидбэка)."""
    return str(uuid.uuid4())


def create_feedback_entry(
    request_id: str,
    user_id: int,
    question: str,
    answer: str,
    query_type: str,
    judge_verdict: Optional[Dict] = None,
) -> None:
    """Создаёт запись в логе обратной связи при отправке ответа с кнопками (rating=null).
    Позже при нажатии кнопки запись обновляется через update_feedback_rating."""
    safe_verdict = _safe_judge_verdict(judge_verdict)
    log_entry = {
        "request_id": request_id,
        "timestamp": datetime.now().isoformat(),
        "user_id": user_id,
        "question": str(question)[:2000],
        "answer": str(answer)[:5000],
        "query_type": query_type,
        "judge_verdict": safe_verdict,
        "rating": None,
    }
    logs = _load_feedback_log()
    logs.append(log_entry)
    try:
        _save_feedback_log(logs)
        logger.info("Feedback entry создана: request_id=%s user_id=%s", request_id, user_id)
        try:
            from logs_to_sheets import duplicate_feedback_to_sheets
            duplicate_feedback_to_sheets(log_entry)
        except Exception:
            pass
        try:
            from logs_to_excel import duplicate_feedback_to_excel
            duplicate_feedback_to_excel(log_entry)
        except Exception:
            pass
    except Exception as e:
        logger.exception("Ошибка записи feedback entry: %s", e)


def update_feedback_rating(request_id: str, rating: str) -> bool:
    """Обновляет запись в логе по request_id при нажатии «Полезно»/«Не помогло». Возвращает True если запись найдена."""
    logs = _load_feedback_log()
    for i, entry in enumerate(logs):
        if entry.get("request_id") == request_id:
            logs[i] = {**entry, "rating": rating, "feedback_at": datetime.now().isoformat()}
            try:
                _save_feedback_log(logs)
                logger.info("User feedback обновлён: request_id=%s rating=%s", request_id, rating)
                feedback_at = logs[i].get("feedback_at", "")
                try:
                    from logs_to_sheets import duplicate_feedback_rating_update_to_sheets
                    duplicate_feedback_rating_update_to_sheets(request_id, rating, feedback_at)
                except Exception:
                    pass
                try:
                    from logs_to_excel import duplicate_feedback_rating_update_to_excel
                    duplicate_feedback_rating_update_to_excel(request_id, rating, feedback_at)
                except Exception:
                    pass
                return True
            except Exception as e:
                logger.exception("Ошибка обновления feedback: %s", e)
                return False
    logger.warning("Запись с request_id=%s не найдена в логе", request_id)
    return False


def log_feedback(user_id: int, question: str, answer: str, rating: str, judge_verdict: Optional[Dict] = None):
    """Дополнительно логирует обратную связь одной строкой (для путей без request_id, например старый контекст).
    Предпочтительно использовать create_feedback_entry + update_feedback_rating."""
    safe_verdict = _safe_judge_verdict(judge_verdict)
    log_entry = {
        "request_id": None,
        "timestamp": datetime.now().isoformat(),
        "user_id": user_id,
        "question": str(question)[:2000],
        "answer": str(answer)[:5000],
        "rating": rating,
        "judge_verdict": safe_verdict,
    }
    logs = _load_feedback_log()
    logs.append(log_entry)
    try:
        _save_feedback_log(logs)
        logger.info("User feedback записан: user_id=%s rating=%s", user_id, rating)
        try:
            from logs_to_sheets import duplicate_feedback_to_sheets
            duplicate_feedback_to_sheets(log_entry)
        except Exception:
            pass
        try:
            from logs_to_excel import duplicate_feedback_to_excel
            duplicate_feedback_to_excel(log_entry)
        except Exception:
            pass
    except Exception as e:
        logger.exception("Ошибка записи в feedback_log.json: %s", e)


def get_feedback_log_path() -> str:
    """Путь к файлу лога обратной связи (для проверки)."""
    return FEEDBACK_LOG_FILE


def read_feedback_log(last_n: int = 10) -> list:
    """Читает последние N записей из feedback_log.json. Для проверки, что фидбэк фиксируется."""
    if not os.path.exists(FEEDBACK_LOG_FILE):
        return []
    try:
        with open(FEEDBACK_LOG_FILE, "r", encoding="utf-8") as f:
            logs = json.load(f)
        return logs[-last_n:] if isinstance(logs, list) else []
    except (json.JSONDecodeError, IOError):
        return []


def log_judge_only(
    user_id: int, question: str, answer: str, judge_verdict: Dict, request_id: Optional[str] = None
):
    """Логирует оценку Judge. request_id — для связи с записью в feedback_log при нажатии кнопки."""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "request_id": request_id,
        "user_id": user_id,
        "question": question,
        "answer": answer,
        "judge_verdict": judge_verdict,
        "user_feedback": None,
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
        try:
            from logs_to_sheets import duplicate_judge_to_sheets
            duplicate_judge_to_sheets(log_entry)
        except Exception:
            pass
        try:
            from logs_to_excel import duplicate_judge_to_excel
            duplicate_judge_to_excel(log_entry)
        except Exception:
            pass
    except IOError as e:
        logger.exception("Ошибка записи в judge_log.json: %s", e)


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
        try:
            from logs_to_sheets import duplicate_escalation_to_sheets
            duplicate_escalation_to_sheets(log_entry)
        except Exception:
            pass
        try:
            from logs_to_excel import duplicate_escalation_to_excel
            duplicate_escalation_to_excel(log_entry)
        except Exception:
            pass
    except IOError as e:
        logger.exception("Ошибка записи в escalation_log.json: %s", e)

    return log_entry


def format_escalation_message(
    user_id: int,
    question: str,
    answer: str,
    judge_verdict: Optional[Dict] = None,
    username: Optional[str] = None,
) -> str:
    """Форматирует сообщение для куратора (username — @ студента для удобства)."""
    username_str = f"@{username}" if username else "не указан"
    reply_cmd = f"/reply {user_id} "
    message = f"""🔔 Эскалация от студента

👤 Студент ID: {user_id}
📛 Username: {username_str}

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
    
    message += f"\n\n✏️ Ответить: скопируйте команду ниже и допишите текст после пробела:\n`{reply_cmd}`"
    
    return message
