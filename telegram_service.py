import requests
import time
import logging
from typing import List, Dict, Optional
from formatter import format_deals_message

logger = logging.getLogger("telegram_service")

class TelegramService:
    def __init__(self, bot_token: str, default_chat_id: Optional[str] = None):
        self.bot_token = bot_token.strip()
        self.default_chat_id = default_chat_id.strip() if default_chat_id else None
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    def is_configured(self) -> bool:
        return bool(self.bot_token and self.bot_token != "your_telegram_bot_token_here")

    def test_connection(self) -> Dict:
        """Verifies bot token validity with getMe."""
        if not self.is_configured():
            return {"ok": False, "error": "Bot token not configured"}
        try:
            r = requests.get(f"{self.base_url}/getMe", timeout=10)
            data = r.json()
            if data.get('ok'):
                bot_user = data.get('result', {}).get('username')
                return {"ok": True, "username": bot_user}
            else:
                return {"ok": False, "error": data.get('description', 'Unknown error')}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def send_message(
        self,
        chat_id: Optional[str],
        text: str,
        parse_mode: str = "HTML",
        disable_web_page_preview: bool = True
    ) -> bool:
        """Sends a single message to a chat ID."""
        target_chat = chat_id or self.default_chat_id
        if not target_chat:
            logger.error("No chat_id provided and no default_chat_id configured.")
            return False

        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": target_chat,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview
        }

        try:
            r = requests.post(url, json=payload, timeout=12)
            data = r.json()
            if data.get('ok'):
                return True
            else:
                logger.error(f"Telegram API error: {data.get('description')}")
                return False
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False

    def send_deal_list(
        self,
        chat_id: Optional[str],
        deals: List[Dict],
        pincode: str = "560001",
        location_name: str = "",
        min_discount: float = 70.0,
        max_items: int = 50
    ) -> int:
        """
        Formats deals into HTML chunks and sends them sequentially
        with polite delays to avoid Telegram flood limits.
        Returns the number of message chunks successfully delivered.
        """
        messages = format_deals_message(
            deals=deals,
            pincode=pincode,
            location_name=location_name,
            min_discount=min_discount,
            max_items=max_items
        )

        sent_count = 0
        for msg in messages:
            success = self.send_message(chat_id=chat_id, text=msg)
            if success:
                sent_count += 1
            # Delay between messages to adhere to Telegram rate limits
            time.sleep(1.2)

        return sent_count

    def get_updates(self, offset: Optional[int] = None, timeout: int = 25) -> List[Dict]:
        """Polls for incoming messages (used by the interactive bot)."""
        url = f"{self.base_url}/getUpdates"
        params = {"timeout": timeout}
        if offset is not None:
            params["offset"] = offset

        try:
            r = requests.get(url, params=params, timeout=timeout + 5)
            data = r.json()
            if data.get('ok'):
                return data.get('result', [])
        except Exception as e:
            logger.error(f"Error getting Telegram updates: {e}")
        return []
