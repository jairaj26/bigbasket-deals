import argparse
import logging
import sys
from typing import List, Dict

# Ensure UTF-8 output in Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import config
from bb_scraper import BigBasketScraper
from formatter import format_deal_item
from tracker import DealTracker
from telegram_service import TelegramService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("bb_main")

def run_dry_run(pincode: str, min_discount: float, max_pages: int):
    print(f"\n==================================================")
    print(f"🛒 BigBasket Deal Finder (Dry Run)")
    print(f"📍 Target Pincode: {pincode}")
    print(f"🔥 Minimum Discount: {min_discount}% OFF")
    print(f"📄 Pages per category: {max_pages}")
    print(f"==================================================\n")

    scraper = BigBasketScraper()
    deals = scraper.fetch_deals(
        pincode=pincode,
        min_discount=min_discount,
        exclude_out_of_stock=config.EXCLUDE_OUT_OF_STOCK,
        max_pages=max_pages,
        on_progress=lambda cat, curr, tot: print(f"[{curr}/{tot}] Scanning {cat}...")
    )

    print(f"\n✨ Scan complete! Found {len(deals)} deals with ≥ {min_discount}% OFF:\n")

    if not deals:
        print("No deals matched your criteria at this time.")
        return

    for idx, d in enumerate(deals[:30], 1):
        print(f"{idx}. {d['name']}")
        print(f"   Brand: {d['brand']} | Category: {d['category']}")
        print(f"   Selling Price: Rs.{d['sp']:.2f} (MRP: Rs.{d['mrp']:.2f})")
        print(f"   Discount: {d['disc']}% OFF | Savings: Rs.{d['savings']:.2f}")
        if d.get('unit_price'):
            print(f"   Unit Price: {d['unit_price']}")
        print(f"   Link: {d['url']}\n")

    if len(deals) > 30:
        print(f"... and {len(deals) - 30} more deals found!\n")

def run_notify(pincode: str, min_discount: float, max_pages: int, chat_id: str):
    if not config.TELEGRAM_BOT_TOKEN or config.TELEGRAM_BOT_TOKEN == "your_telegram_bot_token_here":
        print("\n❌ Error: TELEGRAM_BOT_TOKEN is not configured in .env or environment!")
        sys.exit(1)

    target_chat = chat_id or config.TELEGRAM_CHAT_ID
    if not target_chat or target_chat == "your_telegram_chat_id_here":
        print("\n❌ Error: TELEGRAM_CHAT_ID is not configured in .env or arguments!")
        sys.exit(1)

    tg = TelegramService(config.TELEGRAM_BOT_TOKEN, default_chat_id=target_chat)
    tracker = DealTracker()
    scraper = BigBasketScraper()

    logger.info(f"Starting deal scan for Pincode: {pincode}, Min Discount: {min_discount}%...")
    deals = scraper.fetch_deals(
        pincode=pincode,
        min_discount=min_discount,
        exclude_out_of_stock=config.EXCLUDE_OUT_OF_STOCK,
        max_pages=max_pages
    )

    logger.info(f"Fetched {len(deals)} total deals meeting threshold.")

    # Deduplicate: only get unseen deals or deals whose prices dropped further
    unseen_deals = tracker.filter_unseen_deals(
        deals=deals,
        pincode=pincode,
        cooldown_hours=config.COOLDOWN_HOURS
    )

    logger.info(f"Identified {len(unseen_deals)} new unseen deals.")

    if unseen_deals:
        location_name = scraper.location_name or ""
        sent_chunks = tg.send_deal_list(
            chat_id=target_chat,
            deals=unseen_deals,
            pincode=pincode,
            location_name=location_name,
            min_discount=min_discount,
            max_items=40
        )
        tracker.mark_deals_as_seen(unseen_deals, pincode=pincode)
        logger.info(f"Successfully posted {len(unseen_deals)} deals across {sent_chunks} messages to Telegram.")
        print(f"\n✅ Posted {len(unseen_deals)} fresh deals to Telegram chat ({target_chat})!\n")
    else:
        logger.info("No new deals to post (all currently active deals have already been notified).")
        print("\nℹ️ No new deals to post (already notified recently).\n")

def test_telegram(chat_id: str):
    if not config.TELEGRAM_BOT_TOKEN or config.TELEGRAM_BOT_TOKEN == "your_telegram_bot_token_here":
        print("\n❌ Error: TELEGRAM_BOT_TOKEN is not configured!")
        return

    tg = TelegramService(config.TELEGRAM_BOT_TOKEN)
    info = tg.test_connection()
    if not info.get("ok"):
        print(f"\n❌ Bot connection failed: {info.get('error')}\n")
        return

    print(f"\n✅ Bot connection successful! Bot username: @{info.get('username')}")

    target_chat = chat_id or config.TELEGRAM_CHAT_ID
    if target_chat and target_chat != "your_telegram_chat_id_here":
        msg = "👋 <b>BigBasket Deal Finder Test</b>\n\nYour Telegram Bot is configured properly and ready to push deals!"
        if tg.send_message(target_chat, msg):
            print(f"✅ Test message delivered to chat: {target_chat}!\n")
        else:
            print(f"❌ Failed to send test message to chat: {target_chat}\n")
    else:
        print("ℹ️ Provide --chat-id or set TELEGRAM_CHAT_ID in .env to test sending messages.\n")

def main():
    parser = argparse.ArgumentParser(description="BigBasket Automated Deal Finder & Telegram Bot")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and display deals in terminal without sending to Telegram")
    parser.add_argument("--notify", action="store_true", help="Fetch deals, deduplicate, and push new deals to Telegram")
    parser.add_argument("--bot", "--interactive", action="store_true", help="Run interactive Telegram bot (asks user for pincode)")
    parser.add_argument("--test-telegram", action="store_true", help="Verify Telegram bot connection and send test message")
    parser.add_argument("--pincode", type=str, default=config.DEFAULT_PINCODE, help=f"Delivery pincode (default: {config.DEFAULT_PINCODE})")
    parser.add_argument("--min-discount", type=float, default=config.MIN_DISCOUNT, help=f"Minimum discount percentage (default: {config.MIN_DISCOUNT})")
    parser.add_argument("--pages", type=int, default=config.MAX_PAGES_PER_CATEGORY, help=f"Pages to scan per category (default: {config.MAX_PAGES_PER_CATEGORY})")
    parser.add_argument("--chat-id", type=str, default=None, help="Telegram chat/channel ID override")

    args = parser.parse_args()

    if args.test_telegram:
        test_telegram(args.chat_id)
    elif args.bot:
        from bot import InteractiveDealBot
        bot = InteractiveDealBot()
        bot.run()
    elif args.notify:
        run_notify(
            pincode=args.pincode,
            min_discount=args.min_discount,
            max_pages=args.pages,
            chat_id=args.chat_id
        )
    elif args.dry_run or len(sys.argv) == 1:
        # Default to dry-run if no action specified
        run_dry_run(
            pincode=args.pincode,
            min_discount=args.min_discount,
            max_pages=args.pages
        )
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
