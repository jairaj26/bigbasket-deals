import json
import logging
import re
import sys
import time
from pathlib import Path
from typing import Dict

# Ensure UTF-8 output in Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
import config
from bb_scraper import BigBasketScraper
from telegram_service import TelegramService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("interactive_bot")

USER_DATA_FILE = Path(__file__).resolve().parent / "user_settings.json"

def load_user_settings() -> Dict[str, dict]:
    if USER_DATA_FILE.exists():
        try:
            with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading user settings: {e}")
    return {}

def save_user_settings(data: Dict[str, dict]):
    try:
        with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving user settings: {e}")

class InteractiveDealBot:
    def __init__(self):
        if not config.TELEGRAM_BOT_TOKEN or config.TELEGRAM_BOT_TOKEN == "your_telegram_bot_token_here":
            raise ValueError("TELEGRAM_BOT_TOKEN is not set in .env or environment!")

        self.tg = TelegramService(config.TELEGRAM_BOT_TOKEN)
        self.user_settings = load_user_settings()
        self.scraper = BigBasketScraper()

    def run(self):
        test_info = self.tg.test_connection()
        if not test_info.get("ok"):
            logger.error(f"Failed to connect to Telegram Bot: {test_info.get('error')}")
            print(f"\n❌ Error: Cannot connect to Telegram Bot with provided token.")
            print(f"Details: {test_info.get('error')}\n")
            return

        bot_username = test_info.get("username", "BB Deals Bot")
        logger.info(f"🤖 Interactive Telegram Bot started as @{bot_username}")
        print(f"\n✅ Interactive Telegram Bot is now RUNNING as @{bot_username}!")
        print("Open Telegram, find your bot, and send /start or your pincode.\n")

        offset = None
        while True:
            try:
                updates = self.tg.get_updates(offset=offset, timeout=20)
                for update in updates:
                    offset = update["update_id"] + 1
                    self.handle_update(update)
            except KeyboardInterrupt:
                print("\n🛑 Bot stopped by user.")
                break
            except Exception as e:
                logger.error(f"Error in bot polling loop: {e}")
                time.sleep(3)

    def handle_update(self, update: dict):
        message = update.get("message")
        if not message or "text" not in message:
            return

        chat_id = str(message["chat"]["id"])
        user_text = message["text"].strip()
        first_name = message.get("from", {}).get("first_name", "there")

        # 1. Check for /start or /help
        if user_text in ("/start", "/help"):
            welcome_text = (
                f"👋 <b>Hello {first_name}! Welcome to BigBasket Deal Finder!</b>\n\n"
                f"I scan BigBasket to find flash deals with <b>≥ {config.MIN_DISCOUNT:.0f}% OFF</b> in your area.\n\n"
                f"📍 <b>Please enter your 6-digit Pincode</b> (e.g. <code>560001</code>) to start:"
            )
            self.tg.send_message(chat_id, welcome_text)
            return

        # 2. Check for 6-digit pincode (e.g. "560001" or "/pincode 560001")
        pin_match = re.search(r'\b(\d{6})\b', user_text)
        if pin_match:
            pincode = pin_match.group(1)
            self.user_settings[chat_id] = {"pincode": pincode, "updated_at": time.time()}
            save_user_settings(self.user_settings)

            self.tg.send_message(
                chat_id,
                f"📍 Pincode set to <b>{pincode}</b>!\n\n"
                f"🔎 <b>Scanning BigBasket for deals with ≥ {config.MIN_DISCOUNT:.0f}% OFF...</b>\n"
                f"<i>This takes about 20-30 seconds. Please hold on!</i>"
            )

            # Perform the fetch
            self.execute_fetch(chat_id, pincode)
            return

        # 3. Check for /deals command
        if user_text.lower() == "/deals":
            user_info = self.user_settings.get(chat_id)
            if user_info and user_info.get("pincode"):
                pincode = user_info["pincode"]
                self.tg.send_message(
                    chat_id,
                    f"🔎 <b>Scanning BigBasket for deals with ≥ {config.MIN_DISCOUNT:.0f}% OFF in {pincode}...</b>"
                )
                self.execute_fetch(chat_id, pincode)
            else:
                self.tg.send_message(
                    chat_id,
                    "📍 <b>Please provide your 6-digit Pincode first:</b>\n"
                    "Example: <code>560001</code>"
                )
            return

        # 4. Fallback prompt
        self.tg.send_message(
            chat_id,
            "❓ I didn't recognize that command.\n\n"
            "Please send a <b>6-digit Pincode</b> (e.g. <code>560001</code>) to scan for 70%+ OFF deals,\n"
            "or type /deals to refresh deals for your saved location."
        )

    def execute_fetch(self, chat_id: str, pincode: str):
        try:
            deals = self.scraper.fetch_deals(
                pincode=pincode,
                min_discount=config.MIN_DISCOUNT,
                exclude_out_of_stock=config.EXCLUDE_OUT_OF_STOCK,
                max_pages=config.MAX_PAGES_PER_CATEGORY
            )

            location_name = self.scraper.location_name or ""
            sent_count = self.tg.send_deal_list(
                chat_id=chat_id,
                deals=deals,
                pincode=pincode,
                location_name=location_name,
                min_discount=config.MIN_DISCOUNT,
                max_items=30
            )

            if not deals:
                logger.info(f"No >= {config.MIN_DISCOUNT}% deals found for pincode {pincode}.")
            else:
                logger.info(f"Sent {len(deals)} deals across {sent_count} messages to chat {chat_id}.")

            # Follow up tip
            self.tg.send_message(
                chat_id,
                f"💡 <i>Tip: Send a new pincode anytime to change location, or type /deals to scan again.</i>"
            )

        except Exception as e:
            logger.error(f"Error fetching deals for pincode {pincode}: {e}")
            self.tg.send_message(
                chat_id,
                "⚠️ <b>Oops!</b> An error occurred while fetching deals from BigBasket. Please try again in a few moments."
            )

if __name__ == "__main__":
    bot = InteractiveDealBot()
    bot.run()
