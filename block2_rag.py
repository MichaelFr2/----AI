"""Блок 2: RAG - поиск по базе знаний"""
import os
from typing import List, Dict, Any
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
)
from langchain.schema import Document
import config

# Инициализация эмбеддингов
embeddings = HuggingFaceEmbeddings(
    model_name=config.EMBEDDING_MODEL,
    model_kwargs={'device': 'cpu'}
)

# Инициализация сплиттера
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=config.CHUNK_SIZE,
    chunk_overlap=config.CHUNK_OVERLAP,
    length_function=len,
)

vector_store = None


def load_knowledge_base():
    """Загружает материалы курса в векторную базу"""
    global vector_store
    
    if not os.path.exists(config.KNOWLEDGE_BASE_PATH):
        os.makedirs(config.KNOWLEDGE_BASE_PATH)
        print(f"Создана папка {config.KNOWLEDGE_BASE_PATH}. Добавьте туда материалы курса (PDF, TXT, MD, DOCX)")
        return None
    
    documents = []
    
    # Загрузка файлов
    for filename in os.listdir(config.KNOWLEDGE_BASE_PATH):
        filepath = os.path.join(config.KNOWLEDGE_BASE_PATH, filename)
        
        try:
            if filename.endswith('.pdf'):
                loader = PyPDFLoader(filepath)
                docs = loader.load()
                documents.extend(docs)
            elif filename.endswith('.txt'):
                loader = TextLoader(filepath, encoding='utf-8')
                docs = loader.load()
                documents.extend(docs)
            elif filename.endswith('.md'):
                # Для MD файлов читаем как текст
                with open(filepath, 'r', encoding='utf-8') as f:
                    text = f.read()
                documents.append(Document(page_content=text, metadata={"source": filename}))
            elif filename.endswith('.docx'):
                # Для DOCX используем python-docx
                from docx import Document as DocxDocument
                doc = DocxDocument(filepath)
                text = '\n'.join([p.text for p in doc.paragraphs])
                documents.append(Document(page_content=text, metadata={"source": filename}))
        except Exception as e:
            print(f"Ошибка при загрузке {filename}: {e}")
            continue
    
    if not documents:
        print(f"Не найдено документов в {config.KNOWLEDGE_BASE_PATH}")
        return None
    
    # Разбивка на чанки
    chunks = text_splitter.split_documents(documents)
    print(f"Загружено {len(documents)} документов, создано {len(chunks)} чанков")
    
    # Создание векторной базы
    os.makedirs(config.VECTOR_DB_PATH, exist_ok=True)
    vector_store = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=config.VECTOR_DB_PATH
    )
    # В Chroma 0.4.x автоматическое сохранение, persist() больше не нужен
    # vector_store.persist()  # Удалено - вызывает предупреждение
    
    print("Векторная база создана и сохранена")
    return vector_store


def search_relevant_chunks(query: str, top_k: int = None) -> List[Dict[str, Any]]:
    """
    Ищет релевантные чанки по запросу.
    
    Returns:
        List of dicts with keys: content, score, metadata
    """
    global vector_store
    
    if vector_store is None:
        # Попытка загрузить существующую БД
        if os.path.exists(config.VECTOR_DB_PATH):
            try:
                vector_store = Chroma(
                    persist_directory=config.VECTOR_DB_PATH,
                    embedding_function=embeddings
                )
            except:
                vector_store = load_knowledge_base()
        else:
            vector_store = load_knowledge_base()
    
    if vector_store is None:
        return []
    
    top_k = top_k or config.TOP_K
    
    # Поиск с возвратом метаданных и скоров
    results = vector_store.similarity_search_with_score(query, k=top_k)
    
    chunks = []
    for doc, score in results:
        chunks.append({
            "content": doc.page_content,
            "score": float(score),
            "metadata": doc.metadata
        })
    
    return chunks


def get_context_from_chunks(chunks: List[Dict[str, Any]]) -> str:
    """Формирует контекст из чанков для промпта"""
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        source = chunk.get("metadata", {}).get("source", "неизвестный источник")
        context_parts.append(f"[Фрагмент {i} из {source}]\n{chunk['content']}\n")
    
    return "\n".join(context_parts)

