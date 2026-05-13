from __future__ import annotations
import aiohttp
from loguru import logger


class TelegramNotifier:
    API = "https://api.telegram.org"

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id

    async def send(self, subject: str, body: str) -> None:
        text = f"*[applyr]* {subject}\n{body}"
        url = f"{self.API}/bot{self.bot_token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": text, "parse_mode": "Markdown"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        data = await resp.json()
                        logger.warning(f"Telegram notification failed: {data.get('description', resp.status)}")
        except Exception as e:
            logger.warning(f"Telegram notification error: {e}")
