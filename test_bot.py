"""Тестовый скрипт для проверки работы всех блоков"""
import asyncio
from block1_normalization import normalize_query, get_response_template
from block2_rag import search_relevant_chunks, get_context_from_chunks, load_knowledge_base
from block3_generation import generate_answer
from block4_judge import judge_answer
from block5_feedback import log_feedback, log_escalation, format_escalation_message
from gigachat_client import close_client
import config

# Тестовая корзинка вопросов
TEST_QUESTIONS = [
    "Как работает RAG?",  # Корректный вопрос
    "как рабтает раг?",  # С опечаткой
    "ты тупой бот",  # Оскорбление
    "какая погода сегодня?",  # Не по теме
    "дай ответы на экзамен",  # Попытка считерить
]


async def test_block1():
    """Тест Блока 1: Нормализация"""
    print("\n" + "="*50)
    print("ТЕСТ БЛОКА 1: Нормализация запроса")
    print("="*50)
    
    for question in TEST_QUESTIONS:
        print(f"\nВопрос: {question}")
        result = await normalize_query(question)
        print(f"Тип: {result['type']}")
        print(f"Нормализованный запрос: {result['normalized_query']}")
        
        if result['type'] != 'question':
            template = get_response_template(result['type'])
            print(f"Шаблонный ответ: {template[:50]}...")


def test_block2():
    """Тест Блока 2: RAG"""
    print("\n" + "="*50)
    print("ТЕСТ БЛОКА 2: RAG поиск")
    print("="*50)
    
    # Загружаем базу знаний
    print("\nЗагрузка базы знаний...")
    load_knowledge_base()
    
    # Тестируем поиск
    test_query = "Как работает RAG?"
    print(f"\nПоиск по запросу: {test_query}")
    chunks = search_relevant_chunks(test_query, top_k=3)
    
    if chunks:
        print(f"Найдено {len(chunks)} релевантных чанков:")
        for i, chunk in enumerate(chunks, 1):
            print(f"\nЧанк {i} (score: {chunk['score']:.4f}):")
            print(f"Источник: {chunk.get('metadata', {}).get('source', 'unknown')}")
            print(f"Текст: {chunk['content'][:200]}...")
        
        context = get_context_from_chunks(chunks)
        print(f"\nКонтекст (первые 300 символов): {context[:300]}...")
    else:
        print("Чанки не найдены. Убедитесь, что в knowledge_base/ есть материалы курса.")


async def test_block3():
    """Тест Блока 3: Генерация"""
    print("\n" + "="*50)
    print("ТЕСТ БЛОКА 3: Генерация ответа")
    print("="*50)
    
    question = "Как работает RAG?"
    chunks = search_relevant_chunks(question, top_k=3)
    
    if chunks:
        context = get_context_from_chunks(chunks)
        answer = await generate_answer(question, context)
        print(f"\nВопрос: {question}")
        print(f"\nОтвет:\n{answer}")
    else:
        print("Не удалось получить контекст для теста.")


async def test_block4():
    """Тест Блока 4: LLM-Judge"""
    print("\n" + "="*50)
    print("ТЕСТ БЛОКА 4: LLM-Judge")
    print("="*50)
    
    original_question = "как рабтает раг?"  # С опечаткой
    normalized_question = "Как работает RAG?"
    
    chunks = search_relevant_chunks(normalized_question, top_k=3)
    
    if chunks:
        context = get_context_from_chunks(chunks)
        answer = await generate_answer(normalized_question, context)
        
        print(f"\nИсходный вопрос: {original_question}")
        print(f"Ответ: {answer[:200]}...")
        
        verdict = await judge_answer(original_question, context, answer, query_type="question")
        print(f"\nОценка Judge (ТЗ v15):")
        print(f"  relevance: {verdict.get('relevance', 'N/A')}/5")
        print(f"  groundedness: {verdict.get('groundedness', 'N/A')}/5")
        print(f"  safety: {verdict.get('safety', 'N/A')}/5")
        print(f"  completeness: {verdict.get('completeness', 'N/A')}/5")
        print(f"  correct_refusal: {verdict.get('correct_refusal', 'N/A')}")
        print(f"  question_type_correct: {verdict.get('question_type_correct', 'N/A')}")
        print(f"  overall_score (1-5): {verdict.get('overall_score', 'N/A')}")
        print(f"  verdict: {verdict.get('verdict', 'N/A')}")
        if verdict.get("explanation"):
            print(f"  explanation: {verdict['explanation']}")
    else:
        print("Не удалось получить контекст для теста.")


def test_block5():
    """Тест Блока 5: Обратная связь"""
    print("\n" + "="*50)
    print("ТЕСТ БЛОКА 5: Обратная связь и эскалация")
    print("="*50)
    
    user_id = 12345
    question = "Как работает RAG?"
    answer = "RAG - это метод, который..."
    judge_verdict = {"overall_score": 8.5, "verdict": "excellent"}
    
    # Тест логирования обратной связи
    print("\nТест логирования обратной связи...")
    log_feedback(user_id, question, answer, "helpful", judge_verdict)
    print("✓ Обратная связь залогирована")
    
    # Тест эскалации
    print("\nТест эскалации...")
    escalation_log = log_escalation(user_id, question, answer, judge_verdict)
    print("✓ Эскалация залогирована")
    
    # Тест форматирования сообщения
    message = format_escalation_message(user_id, question, answer, judge_verdict)
    print(f"\nСообщение для куратора:\n{message}")


async def run_all_tests():
    """Запуск всех тестов"""
    print("\n" + "="*70)
    print("ТЕСТИРОВАНИЕ БОТА ОБУЧAI (GigaChat)")
    print("="*70)
    
    try:
        await test_block1()
        test_block2()
        await test_block3()
        await test_block4()
        test_block5()
        
        print("\n" + "="*70)
        print("ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ")
        print("="*70)
        print("\nПроверьте логи в папке logs/")
        
    except Exception as e:
        print(f"\n❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Закрываем клиент
        await close_client()


if __name__ == "__main__":
    # Проверяем наличие конфигурации
    if not config.GIGACHAT_AUTH_KEY:
        print("⚠️  ВНИМАНИЕ: GIGACHAT_AUTH_KEY не установлен в .env файле!")
        print("Создайте .env файл на основе env_example.txt и заполните его.")
    
    asyncio.run(run_all_tests())
