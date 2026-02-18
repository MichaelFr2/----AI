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

# RAG Settings
CHUNK_SIZE = 600
CHUNK_OVERLAP = 100
TOP_K = 4

# LLM Settings
TEMPERATURE_GENERATION = 0.3
MAX_TOKENS = 700

# Embeddings
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

