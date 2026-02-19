"""Дублирование логов в Google Таблицу в реальном времени.
Если заданы GOOGLE_SHEET_ID и GOOGLE_CREDENTIALS_PATH, каждое событие (Judge, Feedback, Escalation)
дополнительно отправляется в таблицу. Запись выполняется в фоновом потоке, чтобы не блокировать бота."""
import logging
import threading
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

_sheet_client = None
_sheet_lock = threading.Lock()
_initialized = False


def _get_client():
    """Ленивая инициализация клиента Google Sheets. Возвращает (gc, spreadsheet) или (None, None)."""
    global _sheet_client, _initialized
    import os
    import config
    sheet_id = getattr(config, "GOOGLE_SHEET_ID", "").strip()
    cred_path = getattr(config, "GOOGLE_CREDENTIALS_PATH", "").strip()
    if not sheet_id or not cred_path:
        return None, None
    path = os.path.abspath(cred_path)
    if not os.path.exists(path):
        logger.warning("Google credentials не найден: %s (задайте GOOGLE_CREDENTIALS_PATH в .env)", path)
        return None, None
    with _sheet_lock:
        if _initialized and _sheet_client is not None:
            return _sheet_client
        _initialized = True
    try:
        import gspread
        gc = gspread.service_account(filename=path)
        sh = gc.open_by_key(sheet_id)
        with _sheet_lock:
            _sheet_client = (gc, sh)
        logger.info("Google Sheets подключена: %s", sheet_id[:16] + "...")
        return _sheet_client
    except Exception as e:
        with _sheet_lock:
            _initialized = False
        logger.warning("Google Sheets: инициализация не удалась — %s. Проверьте: 1) файл ключа; 2) таблица открыта на доступ для email из JSON (Редактор).", e)
        return None, None


def _ensure_headers(ws, headers: list, force_if_mismatch: bool = False) -> None:
    """Записывает заголовки в первую строку. Если force_if_mismatch — перезаписать при несовпадении числа колонок или первой колонки."""
    try:
        row1 = ws.row_values(1)
        need_update = not row1 or row1[0] != "timestamp"
        if force_if_mismatch and row1:
            need_update = need_update or len(row1) != len(headers) or (len(row1) > 5 and row1[5] != headers[5])
        if need_update:
            end_col = chr(ord("A") + min(len(headers), 26) - 1)
            ws.update(f"A1:{end_col}1", [headers], value_input_option="USER_ENTERED")
    except Exception:
        pass


def _append_normalization_sync(entry: Dict[str, Any]) -> None:
    """Лист Normalization: исходный текст и результат Блока 1 для оценки нормализации."""
    gc, sh = _get_client()
    if not sh:
        return
    try:
        ws = sh.worksheet("Normalization") if "Normalization" in [s.title for s in sh.worksheets()] else sh.add_worksheet("Normalization", rows=1000, cols=8)
        _ensure_headers(ws, ["timestamp", "user_id", "original_text", "normalized_query", "type"])
        row = [
            entry.get("timestamp", ""),
            entry.get("user_id", ""),
            (entry.get("original_text") or "")[:1000],
            (entry.get("normalized_query") or "")[:500],
            entry.get("type", ""),
        ]
        ws.append_row(row, value_input_option="USER_ENTERED")
    except Exception as e:
        logger.warning("Sheets append Normalization: %s", e)


# Фиксированный порядок колонок Judge: заголовки и данные в одном порядке
JUDGE_HEADERS = [
    "timestamp", "request_id", "user_id", "question", "answer",
    "rel", "grnd", "safe", "compl",
    "verdict", "score", "type_ok", "refusal_ok", "explanation",
]


def _append_judge_sync(entry: Dict[str, Any]) -> None:
    gc, sh = _get_client()
    if not sh:
        return
    try:
        ws = sh.worksheet("Judge") if "Judge" in [s.title for s in sh.worksheets()] else sh.add_worksheet("Judge", rows=1000, cols=16)
        _ensure_headers(ws, JUDGE_HEADERS, force_if_mismatch=True)
        j = entry.get("judge_verdict") or {}
        row = [
            entry.get("timestamp", ""),
            entry.get("request_id", ""),
            entry.get("user_id", ""),
            (entry.get("question") or "")[:500],
            (entry.get("answer") or "")[:500],
            j.get("relevance", ""),
            j.get("groundedness", ""),
            j.get("safety", ""),
            j.get("completeness", ""),
            j.get("verdict", ""),
            j.get("overall_score", ""),
            j.get("question_type_correct", ""),
            j.get("correct_refusal", ""),
            (j.get("explanation") or "")[:300],
        ]
        ws.append_row(row, value_input_option="USER_ENTERED")
    except Exception as e:
        logger.warning("Sheets append Judge: %s", e)


def _append_feedback_sync(entry: Dict[str, Any]) -> None:
    gc, sh = _get_client()
    if not sh:
        return
    try:
        ws = sh.worksheet("Feedback") if "Feedback" in [s.title for s in sh.worksheets()] else sh.add_worksheet("Feedback", rows=1000, cols=10)
        _ensure_headers(ws, ["timestamp", "request_id", "user_id", "query_type", "rating", "feedback_at", "question", "answer"])
        row = [
            entry.get("timestamp", ""),
            entry.get("request_id", ""),
            entry.get("user_id", ""),
            entry.get("query_type", ""),
            entry.get("rating") or "",
            entry.get("feedback_at", ""),
            (entry.get("question") or "")[:500],
            (entry.get("answer") or "")[:500],
        ]
        ws.append_row(row, value_input_option="USER_ENTERED")
    except Exception as e:
        logger.warning("Sheets append Feedback: %s", e)


def _update_feedback_rating_sync(request_id: str, rating: str, feedback_at: str) -> None:
    """Ищем строку по request_id в листе Feedback и обновляем колонки rating и feedback_at."""
    gc, sh = _get_client()
    if not sh:
        return
    try:
        ws = sh.worksheet("Feedback")
        cell = ws.find(request_id, in_column=2)
        row = cell.row
        col_rating = 5
        col_feedback_at = 6
        ws.update_cell(row, col_rating, rating)
        ws.update_cell(row, col_feedback_at, feedback_at)
    except Exception as e:
        logger.warning("Sheets update Feedback rating: %s", e)


def _append_escalation_sync(entry: Dict[str, Any]) -> None:
    gc, sh = _get_client()
    if not sh:
        return
    try:
        ws = sh.worksheet("Escalation") if "Escalation" in [s.title for s in sh.worksheets()] else sh.add_worksheet("Escalation", rows=500, cols=8)
        _ensure_headers(ws, ["timestamp", "user_id", "question", "answer", "escalated"])
        row = [
            entry.get("timestamp", ""),
            entry.get("user_id", ""),
            (entry.get("question") or "")[:500],
            (entry.get("answer") or "")[:500],
            "1",
        ]
        ws.append_row(row, value_input_option="USER_ENTERED")
    except Exception as e:
        logger.warning("Sheets append Escalation: %s", e)


def duplicate_normalization_to_sheets(entry: Dict[str, Any]) -> None:
    """Дублирует результат нормализации (Блок 1) в лист Normalization — для оценки классификации."""
    threading.Thread(target=_append_normalization_sync, args=(entry,), daemon=True).start()


def duplicate_judge_to_sheets(entry: Dict[str, Any]) -> None:
    """Дублирует запись Judge в Google Таблицу (в фоне)."""
    threading.Thread(target=_append_judge_sync, args=(entry,), daemon=True).start()


def duplicate_feedback_to_sheets(entry: Dict[str, Any]) -> None:
    """Дублирует запись Feedback в Google Таблицу (в фоне)."""
    threading.Thread(target=_append_feedback_sync, args=(entry,), daemon=True).start()


def duplicate_feedback_rating_update_to_sheets(request_id: str, rating: str, feedback_at: str) -> None:
    """Обновляет в таблице строку Feedback по request_id (в фоне)."""
    threading.Thread(target=_update_feedback_rating_sync, args=(request_id, rating, feedback_at), daemon=True).start()


def duplicate_escalation_to_sheets(entry: Dict[str, Any]) -> None:
    """Дублирует эскалацию в Google Таблицу (в фоне)."""
    threading.Thread(target=_append_escalation_sync, args=(entry,), daemon=True).start()
