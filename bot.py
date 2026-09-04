import json
import logging
import re
import sys
import time
from pathlib import Path
from typing import Dict, Optional
import requests

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

# Persistent interactive menu buttons
MAIN_KEYBOARD = {
    "keyboard": [
        [{"text": "🔍 Fetch Deals Now"}],
        [{"text": "📍 Set / Change Pincode"}, {"text": "⏰ Schedule & Status"}]
    ],
    "resize_keyboard": True,
    "is_persistent": True
}

SCHEDULE_INFO_TEXT = (
    "⏰ <b>BigBasket Scheduled Deal Drops (IST):</b>\n\n"
    "🌙 <b>Midnight Drop: 12:05 AM IST</b>\n"
    "   <i>Main daily campaign rollover & price updates</i>\n\n"
    "☀️ <b>Morning Refresh: 7:35 AM IST</b>\n"
    "   <i>Morning grocery slots & fresh stock updates</i>\n\n"
    "🌆 <b>Evening Clearance: 6:05 PM IST</b>\n"
    "   <i>Evening flash drops & clearance items</i>\n\n"
    "✨ <i>New deals will automatically be checked and pushed to this chat at these set intervals!</i>"
)

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
        self.sync_bot_commands()

    def sync_bot_commands(self):
        """Registers the / menu button commands on Telegram."""
        url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/setMyCommands"
        cmds = [
            {"command": "deals", "description": "🔍 Fetch 70%+ OFF deals now"},
            {"command": "pincode", "description": "📍 Set or change your delivery pincode"},
            {"command": "status", "description": "⏰ Show schedule intervals & status"},
            {"command": "start", "description": "👋 Start bot & setup"}
        ]
        try:
            requests.post(url, json={"commands": cmds}, timeout=10)
        except Exception as e:
            logger.warning(f"Could not sync bot commands: {e}")

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

        # 1. /start or /help
        if user_text in ("/start", "/help"):
            user_info = self.user_settings.get(chat_id, {})
            current_pin = user_info.get("pincode")

            if current_pin:
                welcome_text = (
                    f"👋 <b>Welcome back {first_name}!</b>\n\n"
                    f"📍 Current Pincode: <b>{current_pin}</b>\n"
                    f"🔥 Monitoring deals with <b>≥ {config.MIN_DISCOUNT:.0f}% OFF</b>\n\n"
                    f"{SCHEDULE_INFO_TEXT}\n\n"
                    f"Tap an option below to get started:"
                )
            else:
                welcome_text = (
                    f"👋 <b>Hello {first_name}! Welcome to BigBasket Deal Finder!</b>\n\n"
                    f"I monitor BigBasket for flash deals with <b>≥ {config.MIN_DISCOUNT:.0f}% OFF</b>.\n\n"
                    f"📍 <b>Please enter your 6-digit Pincode</b> (e.g. <code>560001</code>) to begin:"
                )
            self.tg.send_message(chat_id, welcome_text, reply_markup=MAIN_KEYBOARD)
            return

        # 2. Check for 6-digit pincode (e.g. "560001" or "/pincode 560001")
        pin_match = re.search(r'\b(\d{6})\b', user_text)
        if pin_match:
            pincode = pin_match.group(1)
            self.user_settings[chat_id] = {"pincode": pincode, "updated_at": time.time()}
            save_user_settings(self.user_settings)

            confirmation = (
                f"✅ <b>Pincode set to {pincode}!</b>\n\n"
                f"{SCHEDULE_INFO_TEXT}\n\n"
                f"You can also tap <b>🔍 Fetch Deals Now</b> below anytime to check live deals right away!"
            )
            self.tg.send_message(chat_id, confirmation, reply_markup=MAIN_KEYBOARD)
            return

        # 3. Schedule & Status
        if user_text.lower() in ("/status", "⏰ schedule & status", "schedule", "status"):
            user_info = self.user_settings.get(chat_id, {})
            current_pin = user_info.get("pincode", config.DEFAULT_PINCODE)

            status_msg = (
                f"{SCHEDULE_INFO_TEXT}\n\n"
                f"📋 <b>Your Active Configuration:</b>\n"
                f"📍 Delivery Pincode: <b>{current_pin}</b>\n"
                f"🔥 Discount Filter: <b>≥ {config.MIN_DISCOUNT:.0f}% OFF</b>\n"
                f"📦 Format: <b>Pure Text List with Direct Links</b> (no attachments)"
            )
            self.tg.send_message(chat_id, status_msg, reply_markup=MAIN_KEYBOARD)
            return

        # 4. Set / Change Pincode request
        if user_text.lower() in ("/pincode", "📍 set / change pincode", "pincode", "change pincode"):
            self.tg.send_message(
                chat_id,
                "📍 <b>Please send your 6-digit Pincode:</b>\n"
                "Example: <code>560001</code>",
                reply_markup=MAIN_KEYBOARD
            )
            return

        # 5. Fetch Deals Now / /deals
        if user_text.lower() in ("/deals", "🔍 fetch deals now", "deals", "fetch"):
            user_info = self.user_settings.get(chat_id, {})
            pincode = user_info.get("pincode", config.DEFAULT_PINCODE)

            if not pincode:
                self.tg.send_message(
                    chat_id,
                    "📍 <b>Please provide your 6-digit Pincode first:</b>\n"
                    "Example: <code>560001</code>",
                    reply_markup=MAIN_KEYBOARD
                )
                return

            self.tg.send_message(
                chat_id,
                f"🔎 <b>Scanning BigBasket for deals with ≥ {config.MIN_DISCOUNT:.0f}% OFF in {pincode}...</b>\n"
                f"<i>Checking 20 categories. Please hold on for ~20-30 seconds!</i>",
                reply_markup=MAIN_KEYBOARD
            )
            self.execute_fetch(chat_id, pincode)
            return

        # 6. Fallback prompt
        self.tg.send_message(
            chat_id,
            "❓ Please choose an option below, or send a <b>6-digit Pincode</b> (e.g. <code>560001</code>):",
            reply_markup=MAIN_KEYBOARD
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

        except Exception as e:
            logger.error(f"Error fetching deals for pincode {pincode}: {e}")
            self.tg.send_message(
                chat_id,
                "⚠️ <b>Oops!</b> An error occurred while fetching deals from BigBasket. Please try again in a few moments.",
                reply_markup=MAIN_KEYBOARD
            )

if __name__ == "__main__":
    bot = InteractiveDealBot()
    bot.run()
