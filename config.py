"""Конфигурация бота"""
import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CURATOR_CHAT_ID = os.getenv("CURATOR_CHAT_ID")

# GigaChat
GIGACHAT_AUTH_KEY = os.getenv("GIGACHAT_AUTH_KEY")  # Authorization key от Сбера

# Course
COURSE_NAME = os.getenv("COURSE_NAME", "ОбучAI")

# Paths
KNOWLEDGE_BASE_PATH = os.getenv("KNOWLEDGE_BASE_PATH", "./knowledge_base")
LOGS_PATH = os.getenv("LOGS_PATH", "./logs")
VECTOR_DB_PATH = "./vector_db"

# RAG Settings (при изменении удалите папку vector_db/ и перезапустите бота)
# Можно переопределить в .env: CHUNK_SIZE, CHUNK_OVERLAP, RAG_TOP_K, RAG_TOP_K_CANDIDATES
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))   # размер чанка в символах; больше — больше контекста, реже режем термины
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))  # перекрытие чанков, чтобы не резать фразу по границе
TOP_K = int(os.getenv("RAG_TOP_K", "6"))   # сколько чанков отдаём в промпт; больше — больше контекста, дороже по токенам
TOP_K_CANDIDATES = int(os.getenv("RAG_TOP_K_CANDIDATES", "24"))  # кандидатов по вектору до переранжирования; больше — выше шанс найти нужный фрагмент

# LLM Settings
TEMPERATURE_GENERATION = 0.3
MAX_TOKENS = 700

# Embeddings
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# Дублирование логов в Google Таблицу (реальное время). Если не задано — только файлы.
_raw_sheet_id = os.getenv("GOOGLE_SHEET_ID", "").strip() or "1UhkErAjyPc2MlT1KqnWa_WWuIwi95rcNWO2fYrJd0D8"
if "/spreadsheets/d/" in _raw_sheet_id or "docs.google.com" in _raw_sheet_id:
    import re
    _m = re.search(r"/d/([a-zA-Z0-9_-]+)", _raw_sheet_id)
    GOOGLE_SHEET_ID = _m.group(1) if _m else _raw_sheet_id
else:
    GOOGLE_SHEET_ID = _raw_sheet_id
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "").strip() or os.path.join(os.path.dirname(os.path.abspath(__file__)), "google_credentials.json")
