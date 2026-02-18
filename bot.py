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
from block5_feedback import log_feedback, log_escalation, format_escalation_message, log_judge_only
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
    
    # Показываем, что бот думает
    thinking_msg = await update.message.reply_text("🤔 Думаю...")
    
    try:
        # БЛОК 1: Нормализация запроса
        normalization_result = await normalize_query(original_question)
        query_type = normalization_result["type"]
        normalized_query = normalization_result["normalized_query"]
        
        logger.info(f"User {user_id}: type={query_type}, normalized={normalized_query}")
        
        # Если не вопрос по курсу (abuse / off_topic / cheat) — шаблонный ответ, кнопки не показываем, Judge не вызываем.
        # Верное определение типа вопроса считается успехом; шаблонный ответ не оценивается Judge.
        if query_type != "question":
            template_response = get_response_template(query_type)
            await thinking_msg.edit_text(template_response)
            log_feedback(user_id, original_question, template_response, "not_rated")
            return
        
        # БЛОК 2: RAG - поиск релевантных чанков
        chunks = search_relevant_chunks(normalized_query)
        
        if not chunks:
            response = "Извините, в базе знаний не найдено информации по вашему вопросу. Попробуйте переформулировать вопрос или обратитесь к куратору."
            await thinking_msg.edit_text(response)
            log_feedback(user_id, original_question, response, "not_rated")
            return
        
        context_text = get_context_from_chunks(chunks)
        
        # БЛОК 3: Генерация ответа
        answer = await generate_answer(normalized_query, context_text)
        
        # БЛОК 4: LLM-Judge (скрыто). Только для type=question; для abuse/off_topic/cheat Judge не вызывается — верное определение типа = успех.
        judge_result = await judge_answer(original_question, context_text, answer, query_type=query_type)
        logger.info(f"Judge verdict for user {user_id}: {judge_result.get('overall_score', 'N/A')}")
        
        # Сохраняем контекст для обратной связи
        user_contexts[user_id] = {
            "question": original_question,
            "answer": answer,
            "judge_verdict": judge_result
        }
        
        # Логируем оценку Judge сразу (даже если пользователь не нажмет кнопку)
        log_judge_only(user_id, original_question, answer, judge_result)
        
        # БЛОК 5: Отправляем ответ с кнопками обратной связи
        keyboard = [
            [
                InlineKeyboardButton("✅ Полезно", callback_data=f"feedback_helpful_{user_id}"),
                InlineKeyboardButton("❌ Не помогло", callback_data=f"feedback_not_helpful_{user_id}")
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
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    if data.startswith("feedback_helpful_"):
        # Полезно
        context_data = user_contexts.get(user_id, {})
        log_feedback(
            user_id,
            context_data.get("question", "unknown"),
            context_data.get("answer", "unknown"),
            "helpful",
            context_data.get("judge_verdict")
        )
        
        await query.edit_message_text(
            query.message.text + "\n\n✅ Рад, что помогло!"
        )
        
    elif data.startswith("feedback_not_helpful_"):
        # Не помогло — лог + модалка «Вызвать куратора» / «Закрыть». Эскалация в препода — только по кнопке «Вызвать куратора».
        context_data = user_contexts.get(user_id, {})
        log_feedback(
            user_id,
            context_data.get("question", "unknown"),
            context_data.get("answer", "unknown"),
            "not_helpful",
            context_data.get("judge_verdict")
        )
        
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
    logger.info("Бот запущен...")
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

