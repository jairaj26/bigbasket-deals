import json
import logging
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
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
from deal_differ import (
    analyze_and_update_deals,
    filter_by_category_code,
    CATEGORY_MAP,
    DiffType
)
from formatter import format_deals_message, format_deal_item

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("interactive_bot")

USER_DATA_FILE = Path(__file__).resolve().parent / "user_settings.json"

# In-memory cache for fast category browsing without re-scraping
USER_DEAL_POOLS: Dict[str, Dict[str, Any]] = {}

SCHEDULE_INFO_TEXT = (
    "⏰ <b>BigBasket Scheduled Deal Drops (IST):</b>\n\n"
    "🌙 <b>Midnight Drop: 12:01 AM IST</b>\n"
    "   <i>Main daily campaign rollover & price updates</i>\n\n"
    "☀️ <b>Morning Refresh: 7:01 AM IST</b>\n"
    "   <i>Morning grocery slots & fresh stock updates</i>\n\n"
    "🌆 <b>Evening Clearance: 6:01 PM IST</b>\n"
    "   <i>Evening flash drops & clearance items</i>\n\n"
    "✨ <i>Deals are checked automatically at these intervals with 7-day cooldown on unchanged items!</i>"
)

def get_main_inline_keyboard() -> Dict[str, Any]:
    """
    Inline keyboard attached directly to messages.
    Does NOT block or intercept the Android/mobile system back button!
    """
    return {
        "inline_keyboard": [
            [
                {"text": "🔥 All Top Deals", "callback_data": "cat_all"}
            ],
            [
                {"text": "🏠 Home & Kitchen", "callback_data": "cat_home"},
                {"text": "🪔 Pooja & Festive", "callback_data": "cat_pooja"}
            ],
            [
                {"text": "🌾 Staples & Oil", "callback_data": "cat_staples"},
                {"text": "🥨 Snacks & Dairy", "callback_data": "cat_snacks"}
            ],
            [
                {"text": "📍 Change Pincode", "callback_data": "cmd_pincode"},
                {"text": "⏰ Schedule & Status", "callback_data": "cmd_status"}
            ]
        ]
    }

def get_category_back_keyboard() -> Dict[str, Any]:
    """Inline keyboard for subcategory views."""
    return {
        "inline_keyboard": [
            [
                {"text": "🏠 Home & Kitchen", "callback_data": "cat_home"},
                {"text": "🪔 Pooja & Festive", "callback_data": "cat_pooja"}
            ],
            [
                {"text": "🔥 Back to All Top Deals", "callback_data": "cat_all"}
            ]
        ]
    }

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
            {"command": "home", "description": "🏠 Browse Home & Kitchen deals"},
            {"command": "pooja", "description": "🪔 Browse Pooja & Festive deals"},
            {"command": "categories", "description": "📑 Browse deals by category"},
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
                    # 1. Handle Callback Query (Inline button clicks)
                    if "callback_query" in update:
                        self.handle_callback_query(update["callback_query"])
                    # 2. Handle standard message
                    elif "message" in update:
                        self.handle_message(update["message"])
            except KeyboardInterrupt:
                print("\n🛑 Bot stopped by user.")
                break
            except Exception as e:
                logger.error(f"Error in bot polling loop: {e}")
                time.sleep(3)

    def handle_callback_query(self, query: dict):
        query_id = query.get("id")
        data = query.get("data", "")
        message = query.get("message", {})
        chat_id = str(message.get("chat", {}).get("id") or "")

        if not chat_id:
            return

        self.tg.answer_callback_query(query_id)
        user_info = self.user_settings.get(chat_id, {})
        pincode = user_info.get("pincode", config.DEFAULT_PINCODE)

        if data == "cmd_status":
            self.send_status_message(chat_id, pincode)
        elif data == "cmd_pincode":
            self.tg.send_message(
                chat_id,
                "📍 <b>Please send your 6-digit Pincode:</b>\n"
                "Example: <code>560001</code>",
                reply_markup=get_main_inline_keyboard()
            )
        elif data in ("cat_all", "cat_home", "cat_pooja", "cat_staples", "cat_snacks", "cat_beauty", "cat_baby"):
            self.handle_category_request(chat_id, pincode, data)

    def handle_message(self, message: dict):
        chat_id = str(message["chat"]["id"])

        # Reject attachments / media and guide user
        if "text" not in message:
            self.tg.send_message(
                chat_id,
                "⚠️ <b>Attachments are disabled.</b>\n\n"
                "Please enter a <b>6-digit Pincode</b> (e.g. <code>560001</code>) or choose an option below:",
                reply_markup=get_main_inline_keyboard()
            )
            return

        user_text = message["text"].strip()
        first_name = message.get("from", {}).get("first_name", "there")

        # 1. /start or /help
        if user_text in ("/start", "/help"):
            user_info = self.user_settings.get(chat_id, {})
            current_pin = user_info.get("pincode")

            # Crucial: Send remove_keyboard to dismiss any legacy sticky dock on mobile!
            self.tg.send_message(
                chat_id,
                "🔄 <i>System keyboard refreshed. Mobile back button navigation restored!</i>",
                reply_markup={"remove_keyboard": True}
            )

            if current_pin:
                welcome_text = (
                    f"👋 <b>Welcome back {first_name}!</b>\n\n"
                    f"📍 Current Pincode: <b>{current_pin}</b>\n"
                    f"🔥 Monitoring deals with <b>≥ {config.MIN_DISCOUNT:.0f}% OFF</b>\n\n"
                    f"{SCHEDULE_INFO_TEXT}\n\n"
                    f"Tap an option below to browse deals:"
                )
            else:
                welcome_text = (
                    f"👋 <b>Hello {first_name}! Welcome to BigBasket Deal Finder!</b>\n\n"
                    f"I monitor BigBasket for flash deals with <b>≥ {config.MIN_DISCOUNT:.0f}% OFF</b>.\n\n"
                    f"📍 <b>Please enter your 6-digit Pincode</b> (e.g. <code>560001</code>) to begin:"
                )
            self.tg.send_message(chat_id, welcome_text, reply_markup=get_main_inline_keyboard())
            return

        # 2. Check for 6-digit pincode (e.g. "560001" or "/pincode 560001")
        pin_match = re.search(r'\b(\d{6})\b', user_text)
        if pin_match:
            pincode = pin_match.group(1)
            self.user_settings[chat_id] = {"pincode": pincode, "updated_at": time.time()}
            save_user_settings(self.user_settings)

            # Invalidate pool cache for new pincode
            USER_DEAL_POOLS.pop(chat_id, None)

            confirmation = (
                f"✅ <b>Pincode set to {pincode}!</b>\n\n"
                f"{SCHEDULE_INFO_TEXT}\n\n"
                f"Tap an option below to fetch live deals:"
            )
            self.tg.send_message(chat_id, confirmation, reply_markup=get_main_inline_keyboard())
            return

        # 3. Schedule & Status
        if user_text.lower() in ("/status", "schedule", "status"):
            user_info = self.user_settings.get(chat_id, {})
            current_pin = user_info.get("pincode", config.DEFAULT_PINCODE)
            self.send_status_message(chat_id, current_pin)
            return

        # 4. Set / Change Pincode request
        if user_text.lower() in ("/pincode", "pincode", "change pincode"):
            self.tg.send_message(
                chat_id,
                "📍 <b>Please send your 6-digit Pincode:</b>\n"
                "Example: <code>560001</code>",
                reply_markup=get_main_inline_keyboard()
            )
            return

        # 5. Direct Category Commands: /home, /pooja, /categories
        if user_text.lower() in ("/home", "home"):
            user_info = self.user_settings.get(chat_id, {})
            pincode = user_info.get("pincode", config.DEFAULT_PINCODE)
            self.handle_category_request(chat_id, pincode, "cat_home")
            return

        if user_text.lower() in ("/pooja", "pooja"):
            user_info = self.user_settings.get(chat_id, {})
            pincode = user_info.get("pincode", config.DEFAULT_PINCODE)
            self.handle_category_request(chat_id, pincode, "cat_pooja")
            return

        if user_text.lower() in ("/categories", "categories"):
            user_info = self.user_settings.get(chat_id, {})
            pincode = user_info.get("pincode", config.DEFAULT_PINCODE)
            self.tg.send_message(
                chat_id,
                f"📑 <b>Browse BigBasket Deals by Category</b>\n📍 Pincode: <code>{pincode}</code>\n\n"
                f"Select a category below:",
                reply_markup=get_main_inline_keyboard()
            )
            return

        # 6. Fetch Deals Now / /deals
        if user_text.lower() in ("/deals", "deals", "fetch"):
            user_info = self.user_settings.get(chat_id, {})
            pincode = user_info.get("pincode", config.DEFAULT_PINCODE)
            self.handle_category_request(chat_id, pincode, "cat_all")
            return

        # 7. Fallback prompt
        self.tg.send_message(
            chat_id,
            "❓ Please choose an option below, or send a <b>6-digit Pincode</b> (e.g. <code>560001</code>):",
            reply_markup=get_main_inline_keyboard()
        )

    def send_status_message(self, chat_id: str, pincode: str):
        status_msg = (
            f"{SCHEDULE_INFO_TEXT}\n\n"
            f"📋 <b>Your Active Configuration:</b>\n"
            f"📍 Delivery Pincode: <b>{pincode}</b>\n"
            f"🔥 Discount Filter: <b>≥ {config.MIN_DISCOUNT:.0f}% OFF</b>\n"
            f"📦 Format: <b>Pure Text List with Direct Links</b> (no attachments)\n"
            f"⏱️ Cooldown: <b>7-Day Reset for Unchanged Items</b> (immediate on price drops)"
        )
        self.tg.send_message(chat_id, status_msg, reply_markup=get_main_inline_keyboard())

    def handle_category_request(self, chat_id: str, pincode: str, cat_code: str):
        pool = USER_DEAL_POOLS.get(chat_id)
        # Re-fetch if cache is missing or older than 30 minutes
        if not pool or (time.time() - pool.get("cached_at", 0) > 1800) or pool.get("pincode") != pincode:
            self.tg.send_message(
                chat_id,
                f"🔎 <b>Scanning BigBasket for deals with ≥ {config.MIN_DISCOUNT:.0f}% OFF in {pincode}...</b>\n"
                f"<i>Analyzing price drops & 7-day cooldown. Please hold on ~20s...</i>"
            )
            self.execute_fetch(chat_id, pincode)
            pool = USER_DEAL_POOLS.get(chat_id, {})

        cat_title = CATEGORY_MAP.get(cat_code, "Top Deals")
        all_raw_deals = pool.get("all_deals", [])

        if cat_code == "cat_all":
            # For all deals, prioritize alert-eligible deals (new, price drops, weekly picks)
            display_deals = pool.get("alert_deals", [])
            # Fallback to all deals if alert deals pool is small
            if len(display_deals) < 10:
                display_deals = all_raw_deals
        else:
            display_deals = filter_by_category_code(all_raw_deals, cat_code)

        location_name = pool.get("location_name", "")
        if not display_deals:
            self.tg.send_message(
                chat_id,
                f"ℹ️ No deals currently available in <b>{cat_title}</b> for <code>{pincode}</code>.",
                reply_markup=get_main_inline_keyboard()
            )
            return

        header_title = f"🛒 <b>BigBasket Deals — {cat_title}</b>"
        messages = format_deals_message(
            deals=display_deals,
            pincode=pincode,
            location_name=location_name,
            min_discount=config.MIN_DISCOUNT,
            max_items=25,
            header_title=header_title
        )

        for i, msg in enumerate(messages):
            # Attach inline keyboard to the final chunk
            kb = get_main_inline_keyboard() if i == len(messages) - 1 else None
            self.tg.send_message(chat_id=chat_id, text=msg, reply_markup=kb)
            time.sleep(1.0)

    def execute_fetch(self, chat_id: str, pincode: str):
        try:
            raw_deals = self.scraper.fetch_deals(
                pincode=pincode,
                min_discount=config.MIN_DISCOUNT,
                exclude_out_of_stock=config.EXCLUDE_OUT_OF_STOCK,
                max_pages=config.MAX_PAGES_PER_CATEGORY
            )

            location_name = self.scraper.location_name or ""

            # Run through smart differ with 7-day cooldown
            alert_deals, home_pool, pooja_pool, stale_deals = analyze_and_update_deals(
                raw_deals, pincode
            )

            # Store in cache
            USER_DEAL_POOLS[chat_id] = {
                "pincode": pincode,
                "location_name": location_name,
                "cached_at": time.time(),
                "all_deals": raw_deals,
                "alert_deals": alert_deals,
                "home_pool": home_pool,
                "pooja_pool": pooja_pool,
                "stale_count": len(stale_deals)
            }

            logger.info(
                f"Scanned {len(raw_deals)} deals for {pincode}: "
                f"{len(alert_deals)} alert-eligible, {len(stale_deals)} suppressed under 7-day cooldown."
            )

        except Exception as e:
            logger.error(f"Error fetching deals for pincode {pincode}: {e}")
            self.tg.send_message(
                chat_id,
                "⚠️ <b>Oops!</b> An error occurred while fetching deals from BigBasket. Please try again in a few moments.",
                reply_markup=get_main_inline_keyboard()
            )

if __name__ == "__main__":
    bot = InteractiveDealBot()
    bot.run()
