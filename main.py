import argparse
import logging
import sys
import json
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple

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

def run_dry_run(pincode: str, min_discount: float, max_pages: int, chunk: Optional[int] = None):
    chunk_str = f" [Chunk #{chunk}]" if chunk else ""
    print(f"\n==================================================")
    print(f"🛒 BigBasket Deal Finder (Dry Run){chunk_str}")
    print(f"📍 Target Pincode: {pincode}")
    print(f"🔥 Minimum Discount: {min_discount}% OFF")
    print(f"📄 Pages per category: {max_pages}")
    print(f"==================================================\n")

    scraper = BigBasketScraper()
    cats = config.get_categories_for_chunk(chunk) if chunk else config.DEFAULT_CATEGORIES
    deals = scraper.fetch_deals(
        pincode=pincode,
        min_discount=min_discount,
        exclude_out_of_stock=config.EXCLUDE_OUT_OF_STOCK,
        max_pages=max_pages,
        categories=cats,
        on_progress=lambda cat, curr, tot: print(f"[{curr}/{tot}] Scanning {cat}...")
    )

    from deal_differ import analyze_and_update_deals, group_products_by_category
    alert_deals, home_pool, pooja_pool, stale_deals = analyze_and_update_deals(deals, pincode)
    grouped = group_products_by_category(deals)

    print(f"\n✨ Scan complete! Found {len(deals)} total deals with ≥ {min_discount}% OFF:")
    print(f"   • Alert-eligible (New / Price Drop / Weekly Pick): {len(alert_deals)}")
    print(f"   • Suppressed (Unchanged under 7-day cooldown): {len(stale_deals)}")
    print(f"\n📊 Category Breakdown:")
    for cat_name, items in grouped.items():
        print(f"   • {cat_name}: {len(items)} deals")

    if not deals:
        print("\nNo deals matched your criteria at this time.")
        return

    print(f"\n🔥 Top Alert-Eligible Deals (showing up to 25):\n")
    sample_deals = alert_deals[:25] if alert_deals else deals[:25]
    for idx, d in enumerate(sample_deals, 1):
        tag_str = f" [{d.get('diff_tag')}]" if d.get('diff_tag') else ""
        print(f"{idx}. {d['name']}{tag_str}")
        print(f"   Brand: {d['brand']} | Bucket: {d.get('category_bucket', d['category'])}")
        print(f"   Selling Price: Rs.{d['sp']:.2f} (MRP: Rs.{d['mrp']:.2f})")
        print(f"   Discount: {d['disc']}% OFF | Savings: Rs.{d['savings']:.2f}")
        if d.get('unit_price'):
            print(f"   Unit Price: {d['unit_price']}")
        print(f"   Link: {d['url']}\n")

def run_notify(pincode: str, min_discount: float, max_pages: int, chat_id: str):
    if not config.TELEGRAM_BOT_TOKEN or config.TELEGRAM_BOT_TOKEN == "your_telegram_bot_token_here":
        print("\n❌ Error: TELEGRAM_BOT_TOKEN is not configured in .env or environment!")
        sys.exit(1)

    target_chat = chat_id or config.TELEGRAM_CHAT_ID
    if not target_chat or target_chat == "your_telegram_chat_id_here":
        print("\n❌ Error: TELEGRAM_CHAT_ID is not configured in .env or arguments!")
        sys.exit(1)

    tg = TelegramService(config.TELEGRAM_BOT_TOKEN, default_chat_id=target_chat)
    scraper = BigBasketScraper()

    logger.info(f"Starting scheduled deal scan for Pincode: {pincode}, Min Discount: {min_discount}%...")
    deals = scraper.fetch_deals(
        pincode=pincode,
        min_discount=min_discount,
        exclude_out_of_stock=config.EXCLUDE_OUT_OF_STOCK,
        max_pages=max_pages
    )

    logger.info(f"Fetched {len(deals)} total deals meeting threshold.")

    # Apply 7-day hybrid cooldown and price-drop tracking (identical to JioMart)
    from deal_differ import analyze_and_update_deals
    from bot import get_main_inline_keyboard
    alert_deals, home_pool, pooja_pool, stale_deals = analyze_and_update_deals(
        current_products=deals,
        pincode=pincode
    )

    logger.info(
        f"Differ Results: {len(alert_deals)} alert deals (new/drops/weekly), "
        f"{len(stale_deals)} unchanged deals suppressed under 7-day cooldown."
    )

    if alert_deals:
        location_name = scraper.location_name or ""
        # Format messages with diff tags
        from formatter import format_deals_message
        messages = format_deals_message(
            deals=alert_deals,
            pincode=pincode,
            location_name=location_name,
            min_discount=min_discount,
            max_items=35
        )
        for i, msg in enumerate(messages):
            # Attach inline navigation keyboard to final chunk
            kb = get_main_inline_keyboard() if i == len(messages) - 1 else None
            tg.send_message(chat_id=target_chat, text=msg, reply_markup=kb)
            import time
            time.sleep(1.2)

        logger.info(f"Successfully posted {len(alert_deals)} deals across {len(messages)} messages to Telegram.")
        print(f"\n✅ Posted {len(alert_deals)} deals to Telegram chat ({target_chat})!\n")
    else:
        logger.info("No new deals or price drops to alert (all current deals suppressed under 7-day cooldown).")
        print("\nℹ️ No new deals to post (all active deals notified within the last 7 days without price change).\n")

def run_scrape_only(
    pincode: str,
    min_discount: float,
    max_pages: int,
    chunk: Optional[int] = None,
    output_path: Optional[str] = None
):
    cats = config.get_categories_for_chunk(chunk) if chunk else config.DEFAULT_CATEGORIES
    logger.info(
        f"Scrape-only started: Pincode={pincode}, MinDisc={min_discount}%, "
        f"Chunk={chunk or 'ALL'} ({len(cats)} categories)"
    )

    scraper = BigBasketScraper()
    deals = scraper.fetch_deals(
        pincode=pincode,
        min_discount=min_discount,
        exclude_out_of_stock=config.EXCLUDE_OUT_OF_STOCK,
        max_pages=max_pages,
        categories=cats,
        on_progress=lambda cat, curr, tot: print(f"[{curr}/{tot}] Scanning {cat}...")
    )

    out_file = output_path or (f"deals_chunk_{chunk}.json" if chunk else "deals_scraped.json")
    out_p = Path(out_file)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "pincode": pincode,
        "location_name": scraper.location_name or "",
        "chunk": chunk,
        "count": len(deals),
        "deals": deals
    }

    with open(out_p, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    logger.info(f"Scraped {len(deals)} deals across {len(cats)} categories. Saved to {out_p.resolve()}")
    print(f"\n✅ Successfully scraped {len(deals)} deals. Saved to: {out_p.resolve()}\n")

def load_chunk_files(input_dir: str, pattern: str = "deals_chunk_*.json") -> Tuple[List[Dict], str]:
    """Scans directory for chunk JSON files and merges deals, returning (all_deals, resolved_location_name)."""
    p = Path(input_dir)
    json_files = []
    if p.is_file():
        json_files = [p]
    elif p.is_dir():
        # Look for pattern matches first
        json_files = list(p.glob(pattern))
        if not json_files:
            # Check recursively in case artifacts were unpacked into subfolders
            json_files = list(p.rglob("*.json"))
            ignored_names = {"package.json", "user_settings.json", "tsconfig.json"}
            json_files = [
                f for f in json_files
                if f.name not in ignored_names and (f.name.startswith("deals_") or "chunk" in f.name.lower())
            ]

    logger.info(f"Discovered {len(json_files)} chunk artifact files in '{input_dir}'")

    seen_ids = set()
    merged_deals: List[Dict] = []
    location_name = ""

    for jf in sorted(json_files):
        try:
            with open(jf, "r", encoding="utf-8") as f:
                data = json.load(f)

            file_deals = []
            if isinstance(data, list):
                file_deals = data
            elif isinstance(data, dict):
                file_deals = data.get("deals", [])
                if not location_name and data.get("location_name"):
                    location_name = data.get("location_name")

            added_from_file = 0
            for d in file_deals:
                pid = str(d.get("id"))
                if pid and pid not in seen_ids:
                    seen_ids.add(pid)
                    merged_deals.append(d)
                    added_from_file += 1

            logger.info(f"Loaded {added_from_file} new deals from {jf.name}")
        except Exception as e:
            logger.error(f"Error loading chunk file {jf}: {e}")

    merged_deals.sort(key=lambda x: x.get("disc", 0), reverse=True)
    return merged_deals, location_name

def run_aggregate_and_notify(
    pincode: str,
    min_discount: float,
    input_dir: str,
    chat_id: Optional[str] = None,
    dry_run: bool = False
):
    merged_deals, loc_name = load_chunk_files(input_dir)
    logger.info(f"Total merged unique deals across all chunks: {len(merged_deals)}")

    if not merged_deals:
        print("\n⚠️ No deals found across the chunk artifacts.")
        return

    from deal_differ import analyze_and_update_deals, group_products_by_category
    alert_deals, home_pool, pooja_pool, stale_deals = analyze_and_update_deals(
        current_products=merged_deals,
        pincode=pincode
    )

    logger.info(
        f"Differ Results: {len(alert_deals)} alert-eligible (new/drops/weekly), "
        f"{len(stale_deals)} unchanged deals suppressed under 7-day cooldown."
    )

    if dry_run:
        grouped = group_products_by_category(merged_deals)
        print(f"\n✨ Aggregation Complete! {len(merged_deals)} total deals with ≥ {min_discount}% OFF:")
        print(f"   • Alert-eligible (New / Price Drop / Weekly Pick): {len(alert_deals)}")
        print(f"   • Suppressed (Unchanged under 7-day cooldown): {len(stale_deals)}")
        print(f"\n📊 Category Breakdown:")
        for cat_name, items in grouped.items():
            print(f"   • {cat_name}: {len(items)} deals")

        print(f"\n🔥 Top Alert-Eligible Deals (showing up to 25):\n")
        sample_deals = alert_deals[:25] if alert_deals else merged_deals[:25]
        for idx, d in enumerate(sample_deals, 1):
            tag_str = f" [{d.get('diff_tag')}]" if d.get('diff_tag') else ""
            print(f"{idx}. {d['name']}{tag_str}")
            print(f"   Brand: {d['brand']} | Bucket: {d.get('category_bucket', d['category'])}")
            print(f"   Selling Price: Rs.{d['sp']:.2f} (MRP: Rs.{d['mrp']:.2f})")
            print(f"   Discount: {d['disc']}% OFF | Savings: Rs.{d['savings']:.2f}\n")
        return

    if not config.TELEGRAM_BOT_TOKEN or config.TELEGRAM_BOT_TOKEN == "your_telegram_bot_token_here":
        print("\n❌ Error: TELEGRAM_BOT_TOKEN is not configured in .env or environment!")
        sys.exit(1)

    target_chat = chat_id or config.TELEGRAM_CHAT_ID
    if not target_chat or target_chat == "your_telegram_chat_id_here":
        print("\n❌ Error: TELEGRAM_CHAT_ID is not configured in .env or arguments!")
        sys.exit(1)

    tg = TelegramService(config.TELEGRAM_BOT_TOKEN, default_chat_id=target_chat)

    if alert_deals:
        from formatter import format_deals_message
        from bot import get_main_inline_keyboard

        messages = format_deals_message(
            deals=alert_deals,
            pincode=pincode,
            location_name=loc_name,
            min_discount=min_discount,
            max_items=35
        )
        for i, msg in enumerate(messages):
            kb = get_main_inline_keyboard() if i == len(messages) - 1 else None
            tg.send_message(chat_id=target_chat, text=msg, reply_markup=kb)
            time.sleep(1.2)

        logger.info(f"Successfully posted {len(alert_deals)} deals across {len(messages)} messages to Telegram.")
        print(f"\n✅ Posted {len(alert_deals)} deals to Telegram chat ({target_chat})!\n")
    else:
        logger.info("No new deals or price drops to alert (all current deals suppressed under 7-day cooldown).")
        print("\nℹ️ No new deals to post (all active deals notified within the last 7 days without price change).\n")

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
    parser.add_argument("--scrape-only", action="store_true", help="Scrape deals and save to a JSON file without sending alerts")
    parser.add_argument("--aggregate-and-notify", action="store_true", help="Merge chunk artifacts, run differ, and send Telegram alert")
    parser.add_argument("--chunk", type=int, default=None, choices=[1, 2, 3, 4], help="Chunk ID (1-4) to scrape only a subset of categories")
    parser.add_argument("--output", type=str, default=None, help="Output JSON file path for --scrape-only")
    parser.add_argument("--input-dir", type=str, default=".", help="Directory containing deals_chunk_*.json for aggregation")
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
    elif args.scrape_only:
        run_scrape_only(
            pincode=args.pincode,
            min_discount=args.min_discount,
            max_pages=args.pages,
            chunk=args.chunk,
            output_path=args.output
        )
    elif args.aggregate_and_notify:
        run_aggregate_and_notify(
            pincode=args.pincode,
            min_discount=args.min_discount,
            input_dir=args.input_dir,
            chat_id=args.chat_id,
            dry_run=args.dry_run
        )
    elif args.notify:
        run_notify(
            pincode=args.pincode,
            min_discount=args.min_discount,
            max_pages=args.pages,
            chat_id=args.chat_id
        )
    elif args.dry_run or len(sys.argv) == 1:
        run_dry_run(
            pincode=args.pincode,
            min_discount=args.min_discount,
            max_pages=args.pages,
            chunk=args.chunk
        )
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
