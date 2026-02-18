# Миграция с OpenAI на GigaChat

- **Конфиг:** `OPENAI_API_KEY` заменён на `GIGACHAT_AUTH_KEY`
- **Клиент:** `gigachat_client.py` (aiohttp, OAuth, авто-обновление токена)
- **Блоки 1, 3, 4:** асинхронные вызовы (`async`/`await`)
- **Зависимости:** убраны openai, langchain-openai; добавлены aiohttp, langchain-community

Подробнее: обновите `.env`, переустановите `pip install -r requirements.txt`, перезапустите бота.
