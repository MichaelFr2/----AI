"""Главный файл Telegram бота - интеграция всех блоков"""
import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
import config
from block1_normalization import normalize_query, get_response_template
from block2_rag import search_relevant_chunks, get_context_from_chunks, load_knowledge_base
from block3_generation import generate_answer
from block4_judge import judge_answer
from block5_feedback import (
    log_feedback,
    log_escalation,
    format_escalation_message,
    log_judge_only,
    get_feedback_log_path,
    create_feedback_entry,
    update_feedback_rating,
    generate_request_id,
)
from gigachat_client import close_client

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Глобальное хранилище для контекста диалога
user_contexts = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user_id = update.effective_user.id
    
    # Если это куратор - сохраняем его chat_id
    if config.CURATOR_CHAT_ID and str(user_id) == str(config.CURATOR_CHAT_ID):
        await update.message.reply_text(
            "Вы зарегистрированы как куратор. Вы будете получать уведомления об эскалациях."
        )
    else:
        await update.message.reply_text(
            f"Привет! Я AI-куратор курса {config.COURSE_NAME}.\n\n"
            "Задайте мне вопрос по материалам курса, и я постараюсь помочь!"
        )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений - главная цепочка"""
    user_id = update.effective_user.id
    original_question = update.message.text
    logger.info("User %s исходный текст (до нормализации): %s", user_id, original_question)

    # Показываем, что бот думает
    thinking_msg = await update.message.reply_text("🤔 Думаю...")
    
    try:
        # БЛОК 1: Нормализация запроса
        normalization_result = await normalize_query(original_question)
        query_type = normalization_result["type"]
        normalized_query = normalization_result["normalized_query"]

        logger.info(f"User {user_id}: type={query_type}, normalized={normalized_query}")

        try:
            from logs_to_sheets import duplicate_normalization_to_sheets
            from datetime import datetime
            duplicate_normalization_to_sheets({
                "timestamp": datetime.now().isoformat(),
                "user_id": user_id,
                "original_text": original_question,
                "normalized_query": normalized_query,
                "type": query_type,
            })
        except Exception:
            pass
        
        # abuse / off_topic / cheat — шаблонный ответ, Блок 4 (Judge) проверяет корректность типа, Блок 5 не показываем.
        if query_type != "question":
            template_response = get_response_template(query_type)
            judge_result = await judge_answer(
                original_question,
                context="",
                answer=template_response,
                query_type=query_type,
            )
            logger.info(f"Judge (шаблон) user {user_id}: question_type_correct={judge_result.get('question_type_correct')}")
            log_judge_only(user_id, original_question, template_response, judge_result, request_id=None)
            await thinking_msg.edit_text(template_response)
            return

        # БЛОК 2: RAG - поиск релевантных чанков
        chunks = search_relevant_chunks(normalized_query)
        
        if not chunks:
            response = "Извините, в базе знаний не найдено информации по вашему вопросу. Попробуйте переформулировать вопрос или обратитесь к куратору."
            judge_result = await judge_answer(original_question, "", response, query_type="question")
            log_judge_only(user_id, original_question, response, judge_result, request_id=None)
            await thinking_msg.edit_text(response)
            return
        
        context_text = get_context_from_chunks(chunks)
        
        # БЛОК 3: Генерация ответа
        answer = await generate_answer(normalized_query, context_text)
        
        # БЛОК 4: Judge для вопроса по курсу (полная оценка)
        judge_result = await judge_answer(original_question, context_text, answer, query_type=query_type)
        logger.info(f"Judge verdict for user {user_id}: {judge_result.get('overall_score', 'N/A')}")

        request_id = generate_request_id()
        user_contexts[user_id] = {
            "request_id": request_id,
            "question": original_question,
            "answer": answer,
            "judge_verdict": judge_result,
        }
        log_judge_only(user_id, original_question, answer, judge_result, request_id=request_id)
        create_feedback_entry(request_id, user_id, original_question, answer, "question", judge_result)

        # БЛОК 5: кнопки только для type=question
        keyboard = [
            [
                InlineKeyboardButton("✅ Полезно", callback_data=f"feedback_helpful_{request_id}"),
                InlineKeyboardButton("❌ Не помогло", callback_data=f"feedback_not_helpful_{request_id}"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await thinking_msg.edit_text(answer, reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Error processing message from user {user_id}: {e}", exc_info=True)
        await thinking_msg.edit_text(
            "Произошла ошибка при обработке вашего вопроса. Попробуйте позже или обратитесь к куратору."
        )


async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик обратной связи (кнопки)"""
    query = update.callback_query
    data = query.data or ""
    user_id = update.effective_user.id
    logger.info("Callback feedback: data=%s user_id=%s", data, user_id)

    await query.answer()

    context_data = user_contexts.get(user_id, {})
    if not context_data:
        logger.warning("Нет контекста для user_id=%s (бот перезапускали или другой инстанс). Фидбэк всё равно запишем.", user_id)

    if data.startswith("feedback_helpful_"):
        request_id = data[len("feedback_helpful_"):]
        updated = update_feedback_rating(request_id, "helpful")
        if not updated:
            log_feedback(
                user_id,
                context_data.get("question", "unknown"),
                context_data.get("answer", "unknown"),
                "helpful",
                context_data.get("judge_verdict"),
            )
        logger.info("Feedback: user %s нажал «Полезно» request_id=%s", user_id, request_id)

        await query.edit_message_text(
            query.message.text + "\n\n✅ Рад, что помогло!"
        )

    elif data.startswith("feedback_not_helpful_"):
        request_id = data[len("feedback_not_helpful_"):]
        updated = update_feedback_rating(request_id, "not_helpful")
        if not updated:
            log_feedback(
                user_id,
                context_data.get("question", "unknown"),
                context_data.get("answer", "unknown"),
                "not_helpful",
                context_data.get("judge_verdict"),
            )
        logger.info("Feedback: user %s нажал «Не помогло» request_id=%s", user_id, request_id)

        keyboard = [
            [
                InlineKeyboardButton("🔔 Вызвать куратора", callback_data=f"escalate_{user_id}"),
                InlineKeyboardButton("❌ Закрыть", callback_data=f"close_{user_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            query.message.text + "\n\n❌ Извините, что не помогло. Хотите обратиться к куратору?",
            reply_markup=reply_markup
        )


async def handle_escalation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик эскалации: «Вызвать куратора» → отправка сообщения куратору (CURATOR_CHAT_ID)."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    if data.startswith("escalate_"):
        context_data = user_contexts.get(user_id, {})
        
        # Логируем эскалацию
        escalation_log = log_escalation(
            user_id,
            context_data.get("question", "unknown"),
            context_data.get("answer", "unknown"),
            context_data.get("judge_verdict")
        )
        
        # Отправляем сообщение куратору
        if config.CURATOR_CHAT_ID:
            try:
                escalation_message = format_escalation_message(
                    user_id,
                    context_data.get("question", "unknown"),
                    context_data.get("answer", "unknown"),
                    context_data.get("judge_verdict")
                )
                
                await context.bot.send_message(
                    chat_id=config.CURATOR_CHAT_ID,
                    text=escalation_message
                )
                
                await query.edit_message_text(
                    query.message.text + "\n\n✅ Передал куратору, он свяжется с вами."
                )
            except Exception as e:
                logger.error(f"Error sending escalation to curator: {e}")
                await query.edit_message_text(
                    query.message.text + "\n\n⚠️ Не удалось связаться с куратором. Попробуйте позже."
                )
        else:
            await query.edit_message_text(
                query.message.text + "\n\n⚠️ Куратор не настроен. Ваш запрос залогирован."
            )
    
    elif data.startswith("close_"):
        # Закрыть модалку
        await query.edit_message_text(query.message.text)


def main():
    """Запуск бота"""
    if not config.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN не установлен в .env файле!")
        return
    
    # Загружаем базу знаний при старте
    logger.info("Загрузка базы знаний...")
    load_knowledge_base()
    
    # Создаем приложение
    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(handle_feedback, pattern="^feedback_"))
    application.add_handler(CallbackQueryHandler(handle_escalation, pattern="^(escalate_|close_)"))
    
    # Запускаем бота
    logger.info("Бот запущен. Лог фидбэка: %s", get_feedback_log_path())
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt:
        logger.info("Остановка бота...")
    finally:
        # Закрываем клиент GigaChat при завершении
        import asyncio
        try:
            asyncio.run(close_client())
        except:
            pass


if __name__ == "__main__":
    main()

