"""Универсальный клиент для работы с GigaChat API"""
import aiohttp
import json
import logging
import uuid
from typing import Optional, List, Dict, Any
from config import GIGACHAT_AUTH_KEY

logger = logging.getLogger(__name__)


class GigaChatClient:
    """Клиент для работы с GigaChat API"""
    
    def __init__(self):
        self.auth_key = GIGACHAT_AUTH_KEY
        self.access_token = None
        self.session = None
    
    async def _ensure_session(self):
        """Создает сессию если её нет"""
        if self.session is None:
            self.session = aiohttp.ClientSession()
    
    async def close(self):
        """Закрывает сессию"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def _get_access_token(self):
        """Получение Access token для GigaChat"""
        if not self.auth_key:
            raise Exception("GigaChat Authorization key не настроен")
        
        await self._ensure_session()
        
        try:
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json',
                'RqUID': str(uuid.uuid4()),
                'Authorization': f'Basic {self.auth_key}'
            }
            
            data = {'scope': 'GIGACHAT_API_PERS'}
            
            async with self.session.post(
                'https://ngw.devices.sberbank.ru:9443/api/v2/oauth',
                headers=headers,
                data=data,
                ssl=False
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    self.access_token = result.get('access_token')
                    logger.info("Access token получен успешно")
                    return self.access_token
                else:
                    error_text = await response.text()
                    logger.error(f"Ошибка получения токена: {response.status} - {error_text}")
                    raise Exception(f"Не удалось получить Access token: {response.status}")
                    
        except Exception as e:
            logger.error(f"Ошибка при получении Access token: {e}")
            raise
    
    async def _make_request(
        self, 
        messages: List[Dict[str, str]], 
        max_tokens: int = 500, 
        temperature: float = 0.7,
        response_format: Optional[str] = None
    ) -> str:
        """Выполнение запроса к GigaChat API"""
        await self._ensure_session()
        
        if not self.access_token:
            await self._get_access_token()
        
        try:
            headers = {
                'Accept': 'application/json',
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            data = {
                "model": "GigaChat:latest",
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature
            }
            
            # GigaChat поддерживает JSON mode через параметр
            if response_format == "json_object":
                data["response_format"] = {"type": "json_object"}
            
            async with self.session.post(
                'https://gigachat.devices.sberbank.ru/api/v1/chat/completions',
                headers=headers,
                json=data,
                ssl=False
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result["choices"][0]["message"]["content"]
                elif response.status == 401:
                    # Токен истек, получаем новый
                    logger.info("Токен истек, получаем новый")
                    await self._get_access_token()
                    # Повторяем запрос с новым токеном
                    return await self._make_request(messages, max_tokens, temperature, response_format)
                else:
                    error_text = await response.text()
                    logger.error(f"GigaChat API error: {response.status} - {error_text}")
                    raise Exception(f"GigaChat API error: {response.status}")
                    
        except Exception as e:
            logger.error(f"Error in GigaChat API: {e}")
            raise
    
    async def chat_completion(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 500,
        temperature: float = 0.7,
        response_format: Optional[str] = None
    ) -> str:
        """
        Универсальный метод для запросов к GigaChat
        
        Args:
            system_prompt: Системный промпт
            user_message: Сообщение пользователя
            max_tokens: Максимальное количество токенов
            temperature: Температура (0.0-1.0)
            response_format: Формат ответа ("json_object" для JSON)
            
        Returns:
            Ответ от GigaChat
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        return await self._make_request(messages, max_tokens, temperature, response_format)


# Глобальный экземпляр клиента
_client_instance: Optional[GigaChatClient] = None


async def get_client() -> GigaChatClient:
    """Получить или создать глобальный экземпляр клиента"""
    global _client_instance
    if _client_instance is None:
        _client_instance = GigaChatClient()
    return _client_instance


async def close_client():
    """Закрыть глобальный клиент"""
    global _client_instance
    if _client_instance:
        await _client_instance.close()
        _client_instance = None

