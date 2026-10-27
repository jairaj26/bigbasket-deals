"""
BigBasket Deal Sniper - Headless Telegram Bot Automation
=========================================================
Runs completely in the background without opening any visible browser window.
Scans BigBasket for steep discounts (>=50% OFF) and alerts via Telegram Bot.

Features:
- Completely Invisible / Off-screen Execution (zero desktop disruption)
- Akamai Bot-Proof (uses real Edge engine off-screen via Playwright)
- Deduplication & 15-Day Cooloff Rule:
    * Sends new deals on Day 1.
    * If an item remains at the same discount on Day 2, suppresses it for 15 days.
    * If the discount changes, alerts immediately.
- Compact 3-line format per deal, combined in single messages separated by \\n\\n
- Windows Task Scheduler registration for 4 daily scans (12:00 AM, 4:00 PM, 7:00 PM, 11:30 PM)

Usage:
    python bb_telegram_sniper.py --now             # Run background scan & send deals to Telegram now
    python bb_telegram_sniper.py --test-telegram   # Send a test message to your Telegram bot
    python bb_telegram_sniper.py --install-task    # Register 4x daily background schedule in Windows
    python bb_telegram_sniper.py --status-task     # Check Windows Task Scheduler status
    python bb_telegram_sniper.py --remove-task     # Remove scheduled task
    python bb_telegram_sniper.py --reset-history   # Reset deals history tracking database
"""

import sys
import os
import time
import json
import argparse
import subprocess
import urllib.request
import urllib.parse
from datetime import datetime, date, timedelta

# Safely handle Windows console encoding
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# ==============================================================================
# Configuration & Environment
# ==============================================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(SCRIPT_DIR, ".env")
HISTORY_FILE = os.path.join(SCRIPT_DIR, "bb_deals_history.json")
TASK_NAME = "BigBasketTelegramSniper"

def load_env():
    """Load settings from .env file without external dependencies."""
    config = {
        "TELEGRAM_BOT_TOKEN": "",
        "TELEGRAM_CHAT_ID": "",
        "MIN_DISCOUNT": 50,
        "PINCODE": "560001",
        "EDGE_PROFILE_DIR": os.path.expandvars(r"%LOCALAPPDATA%\bb_bot_profile")
    }
    if os.path.exists(ENV_FILE):
        try:
            with open(ENV_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k in config:
                        if k == "MIN_DISCOUNT":
                            try:
                                config[k] = int(v)
                            except ValueError:
                                pass
                        else:
                            config[k] = v
        except Exception as e:
            print(f"[!] Warning reading .env: {e}")
    return config

CFG = load_env()

# Assigned Essential Categories for automated scan
ASSIGNED_CATEGORIES = [
    {"name": "Foodgrains, Oil & Masala", "slug": "foodgrains-oil-masala"},
    {"name": "Edible Oils & Ghee", "slug": "edible-oils-ghee"},
    {"name": "Dairy", "slug": "dairy"},
    {"name": "Beverages", "slug": "beverages"}
]

# 4 Daily scan times: (hour, minute, label)
DAILY_SCHEDULE = [
    (0, 0, "12:00 AM (Midnight Deals)"),
    (16, 0, "4:00 PM (Afternoon Restock)"),
    (19, 0, "7:00 PM (Evening Flash Sales)"),
    (23, 30, "11:30 PM (Pre-Midnight Clearance)")
]


# ==============================================================================
# Telegram Bot Delivery
# ==============================================================================

def send_telegram_message(text: str, bot_token: str = None, chat_id: str = None) -> bool:
    """Send a formatted message to Telegram Bot via HTTP API."""
    token = bot_token or CFG["TELEGRAM_BOT_TOKEN"]
    cid = chat_id or CFG["TELEGRAM_CHAT_ID"]

    if not token or not cid or token == "your_telegram_bot_token_here":
        print("[!] Telegram credentials missing! Please configure TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": cid,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            res_json = json.loads(resp.read().decode())
            return res_json.get("ok", False)
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode()
        print(f"[!] Telegram API error ({e.code}): {err_msg}")
        # If Markdown parsing failed, attempt sending as plain text
        if "can't parse entities" in err_msg.lower():
            try:
                payload.pop("parse_mode", None)
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    return json.loads(resp.read().decode()).get("ok", False)
            except Exception:
                pass
        return False
    except Exception as e:
        print(f"[!] Network error sending to Telegram: {e}")
        return False


def chunk_and_send_deals(deal_items: list, bot_token: str = None, chat_id: str = None) -> int:
    """
    Format deals into exact 3-line blocks separated by \\n\\n,
    chunk them safely within Telegram's 4096 char limit, and send.
    """
    if not deal_items:
        return 0

    deal_blocks = []
    for d in deal_items:
        title = d["title"]
        sp_str = str(int(d["sp"])) if float(d["sp"]).is_integer() else f"{d['sp']:.2f}"
        mrp_str = str(int(d["mrp"])) if float(d["mrp"]).is_integer() else f"{d['mrp']:.2f}"
        disc_str = str(int(d["disc"]))

        block = (
            f"🛒 {title}\n"
            f"💰 ₹{sp_str}  (MRP: ₹{mrp_str}) || {disc_str}% OFF\n"
            f"🔗 [Open on BigBasket]({d['url']})"
        )
        deal_blocks.append(block)

    # Chunk into combined messages <= 3800 chars
    messages = []
    curr_chunk = []
    curr_len = 0
    for block in deal_blocks:
        add_len = len(block) + (2 if curr_chunk else 0)
        if curr_len + add_len > 3800 and curr_chunk:
            messages.append("\n\n".join(curr_chunk))
            curr_chunk = [block]
            curr_len = len(block)
        else:
            curr_chunk.append(block)
            curr_len += add_len
    if curr_chunk:
        messages.append("\n\n".join(curr_chunk))

    sent_count = 0
    for idx, msg in enumerate(messages):
        ok = send_telegram_message(msg, bot_token, chat_id)
        if ok:
            sent_count += 1
            print(f"[OK] Sent Telegram message batch [{idx + 1}/{len(messages)}]")
        else:
            print(f"[!] Failed to send Telegram message batch [{idx + 1}/{len(messages)}]")
        time.sleep(1)

    return sent_count


# ==============================================================================
# Deals History & 15-Day Cooloff State Management
# ==============================================================================

def load_deals_history() -> dict:
    """Load tracking history database."""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_deals_history(history: dict):
    """Save tracking history database atomically."""
    temp_file = HISTORY_FILE + ".tmp"
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
        if os.path.exists(HISTORY_FILE):
            os.remove(HISTORY_FILE)
        os.rename(temp_file, HISTORY_FILE)
    except Exception as e:
        print(f"[!] Failed to save history: {e}")


def filter_deals_with_cooloff(scanned_deals: list, today_str: str = None) -> tuple:
    """
    Applies the user's specific cooloff rules:
    1. Send deals when first seen.
    2. If an item stays at the same discount for the second day, hide it from sending for 15 days.
    3. If the discount changes, send immediately.
    4. Do not repeat identical sends on the same calendar day.
    """
    if today_str is None:
        today_str = date.today().isoformat()
    today_dt = date.fromisoformat(today_str)

    history = load_deals_history()
    deals_to_send = []

    for item in scanned_deals:
        pid = str(item["id"])
        curr_disc = round(float(item["disc"]))

        record = history.get(pid)

        if not record:
            # Day 1: Brand new deal discovered
            history[pid] = {
                "title": item["title"],
                "disc": curr_disc,
                "sp": item["sp"],
                "mrp": item["mrp"],
                "url": item["url"],
                "first_seen": today_str,
                "last_seen": today_str,
                "last_sent": today_str,
                "consecutive_days_at_same_disc": 1,
                "suppressed_until": None
            }
            deals_to_send.append(item)
            continue

        prev_disc = round(float(record.get("disc", 0)))
        last_seen = record.get("last_seen", today_str)
        last_sent = record.get("last_sent", "")
        suppressed_until = record.get("suppressed_until")
        consec_days = record.get("consecutive_days_at_same_disc", 1)

        # Update metadata
        record["title"] = item["title"]
        record["sp"] = item["sp"]
        record["mrp"] = item["mrp"]
        record["url"] = item["url"]
        record["last_seen"] = today_str

        # CASE 1: Discount changed! (e.g. 50% -> 60% or vice versa)
        if curr_disc != prev_disc:
            record["disc"] = curr_disc
            record["first_seen"] = today_str
            record["last_sent"] = today_str
            record["consecutive_days_at_same_disc"] = 1
            record["suppressed_until"] = None
            deals_to_send.append(item)
            continue

        # Discount is unchanged from here on
        # CASE 2: Checked multiple times within the SAME day
        if last_sent == today_str:
            # Already sent today; don't re-send during afternoon/evening scans
            continue

        # CASE 3: It's a new day! Check consecutive days
        is_next_day = (last_seen != today_str)
        if is_next_day:
            consec_days += 1
            record["consecutive_days_at_same_disc"] = consec_days

        # Check suppression window
        if suppressed_until:
            supp_date = date.fromisoformat(suppressed_until)
            if today_dt < supp_date:
                # Still within 15-day cooloff period
                continue
            else:
                # 15-day cooloff expired! Re-send deal
                record["suppressed_until"] = None
                record["consecutive_days_at_same_disc"] = 1
                record["last_sent"] = today_str
                deals_to_send.append(item)
                continue

        # CASE 4: Second day at the SAME discount -> Suppress for 15 days!
        if consec_days >= 2:
            supp_target = (today_dt + timedelta(days=15)).isoformat()
            record["suppressed_until"] = supp_target
            # Suppress from sending today
            continue

        # Otherwise send (e.g. single day send)
        record["last_sent"] = today_str
        deals_to_send.append(item)

    save_deals_history(history)
    return deals_to_send, history


# ==============================================================================
# Headless Background Scanner (Off-screen Playwright Engine)
# ==============================================================================

def scan_deals_headless() -> list:
    """
    Launches Microsoft Edge completely off-screen via Playwright,
    fetches the assigned categories safely through page context, and returns deals.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[!] Playwright is required. Run: python -m pip install playwright")
        return []

    min_discount = CFG.get("MIN_DISCOUNT", 50)
    profile_dir = CFG.get("EDGE_PROFILE_DIR", os.path.expandvars(r"%LOCALAPPDATA%\bb_bot_profile"))
    os.makedirs(profile_dir, exist_ok=True)

    print(f"[*] Starting silent background scan for {len(ASSIGNED_CATEGORIES)} categories...")
    print(f"[*] Discount filter: >= {min_discount}% OFF")

    all_deals = []

    with sync_playwright() as p:
        # Launch persistent context off-screen (-32000, -32000) so NO window is visible
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            channel="msedge",
            headless=False,
            args=[
                "--window-position=-32000,-32000",
                "--window-size=1280,800",
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox"
            ]
        )
        page = context.pages[0] if context.pages else context.new_page()

        try:
            print("[*] Loading BigBasket session in background...")
            page.goto("https://www.bigbasket.com/cl/dairy/?nc=nb", wait_until="networkidle", timeout=40000)
            time.sleep(2)

            for idx, cat in enumerate(ASSIGNED_CATEGORIES):
                slug = cat["slug"]
                cname = cat["name"]
                print(f"[*] Scanning [{idx + 1}/{len(ASSIGNED_CATEGORIES)}]: {cname}...")

                js_fetch = f"""
                async () => {{
                    try {{
                        const res = await fetch("https://www.bigbasket.com/listing-svc/v2/products?type=pc&slug={slug}&page=1&sort=dphtl", {{
                            headers: {{
                                "accept": "application/json",
                                "x-channel": "BB-WEB",
                                "x-entry-context": "bb-b2c",
                                "x-entry-context-id": "100"
                            }}
                        }});
                        if (!res.ok) return {{ status: res.status, products: [] }};
                        const data = await res.json();
                        let prods = [];
                        for (const t of (data.tabs || [])) {{
                            const p_list = t?.product_info?.products || [];
                            if (p_list.length) prods.push(...p_list);
                        }}
                        return {{ status: 200, products: prods }};
                    }} catch(e) {{
                        return {{ status: 0, error: e.message, products: [] }};
                    }}
                }}
                """

                res = page.evaluate(js_fetch)
                prods_raw = res.get("products", [])

                cat_deals = 0
                for p in prods_raw:
                    pricing = p.get("pricing", {})
                    disc_info = pricing.get("discount", {})
                    mrp = float(disc_info.get("mrp") or pricing.get("mrp") or 0)
                    sp = float(disc_info.get("prim_price", {}).get("sp") or pricing.get("sp") or 0)

                    if sp <= 0 and mrp > 0:
                        sp = mrp
                    disc = round(((mrp - sp) / mrp) * 100) if mrp > 0 and sp > 0 else 0

                    if disc < min_discount:
                        continue

                    # Filter out-of-stock items
                    avail = p.get("availability", {})
                    if avail.get("avail_status") == "002" or avail.get("is_available") is False:
                        continue

                    brand = (p.get("brand") or {}).get("name", "").strip()
                    desc = p.get("desc", "").strip()
                    w = p.get("w", "").strip()

                    title_parts = []
                    if brand and brand.lower() not in desc.lower():
                        title_parts.append(brand)
                    title_parts.append(desc)
                    if w and w.lower() not in desc.lower():
                        title_parts.append(f"({w})")
                    full_title = " ".join(title_parts).strip()

                    abs_url = p.get("absolute_url", "")
                    if abs_url.startswith("http"):
                        url = abs_url
                    elif abs_url:
                        url = f"https://www.bigbasket.com{abs_url}"
                    else:
                        url = f"https://www.bigbasket.com/pd/{p.get('id', '')}"

                    all_deals.append({
                        "id": p.get("id"),
                        "title": full_title,
                        "brand": brand,
                        "desc": desc,
                        "mrp": mrp,
                        "sp": sp,
                        "disc": disc,
                        "url": url,
                        "category": cname
                    })
                    cat_deals += 1

                print(f"[OK] Found {cat_deals} deals (>= {min_discount}% OFF) in {cname}")
                time.sleep(2.0 + (idx * 0.5))

        finally:
            context.close()
            print("[*] Background browser closed cleanly.")

    # Deduplicate deals by ID
    seen_ids = set()
    unique_deals = []
    for d in all_deals:
        if d["id"] not in seen_ids:
            seen_ids.add(d["id"])
            unique_deals.append(d)

    unique_deals.sort(key=lambda x: x["disc"], reverse=True)
    return unique_deals


# ==============================================================================
# Core Execution Workflow
# ==============================================================================

def execute_scan_and_alert():
    """Perform full background scan, apply 15-day cooloff, and send to Telegram."""
    print("=" * 65)
    print("  BigBasket Telegram Sniper - Headless Background Execution")
    print("=" * 65)
    print(f"[*] Execution time: {datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')}")

    scanned_deals = scan_deals_headless()
    print(f"\n[*] Total live deals found: {len(scanned_deals)}")

    if not scanned_deals:
        print("[*] No deals found matching filter threshold today.")
        return

    deals_to_send, _ = filter_deals_with_cooloff(scanned_deals)
    print(f"[*] Deals eligible to alert (after cooloff/dedup): {len(deals_to_send)}")

    if not deals_to_send:
        print("[*] All deals are either already sent today or suppressed by the 15-day rule.")
        return

    print("\n[*] Sending deals to Telegram...")
    batches = chunk_and_send_deals(deals_to_send)
    print(f"[OK] Done! Delivered {len(deals_to_send)} deals across {batches} Telegram message(s).")


def test_telegram_alert():
    """Send a test deal to verify Telegram bot setup."""
    print("[*] Testing Telegram bot credentials...")
    sample_deal = [{
        "title": "Fortune Sunlite Refined Sunflower Oil (1L)",
        "sp": 85,
        "mrp": 175,
        "disc": 51,
        "url": "https://www.bigbasket.com"
    }]
    count = chunk_and_send_deals(sample_deal)
    if count > 0:
        print("[OK] Test message delivered successfully to your Telegram chat!")
    else:
        print("[!] Test failed. Please check your BOT_TOKEN and CHAT_ID in .env")


# ==============================================================================
# Windows Task Scheduler Management
# ==============================================================================

def install_task():
    """Register the 4-times daily background schedule in Windows Task Scheduler."""
    script_path = os.path.abspath(__file__)
    python_dir = os.path.dirname(sys.executable)
    pythonw_path = os.path.join(python_dir, "pythonw.exe")
    if not os.path.exists(pythonw_path):
        pythonw_path = sys.executable

    print(f"[*] Registering background scheduled task: {TASK_NAME}")
    print("[*] Schedule: 4 Times Daily (12:00 AM, 4:00 PM, 7:00 PM, 11:30 PM)")
    print(f"[*] Executable: {pythonw_path}")

    ps_script = f"""
    $ErrorActionPreference = 'Stop'
    $action = New-ScheduledTaskAction -Execute '{pythonw_path}' -Argument '"{script_path}" --run-now'
    $triggers = @(
        $(New-ScheduledTaskTrigger -Daily -At "00:00"),
        $(New-ScheduledTaskTrigger -Daily -At "16:00"),
        $(New-ScheduledTaskTrigger -Daily -At "19:00"),
        $(New-ScheduledTaskTrigger -Daily -At "23:30")
    )
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
    Register-ScheduledTask -TaskName '{TASK_NAME}' -Action $action -Trigger $triggers -Settings $settings -Force
    """

    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            capture_output=True, text=True, check=False
        )
        if res.returncode == 0:
            print(f"\n[OK] SUCCESS: Background task '{TASK_NAME}' registered successfully!")
            print("    Runs completely hidden in the background without popping up any browser window at:")
            print("      • 12:00 AM  (Midnight Deals)")
            print("      •  4:00 PM  (Afternoon Restock)")
            print("      •  7:00 PM  (Evening Flash Sales)")
            print("      • 11:30 PM  (Pre-Midnight Clearance)")
            print("\n    - Test immediately with : python bb_telegram_sniper.py --now")
            print("    - Test Telegram alert   : python bb_telegram_sniper.py --test-telegram")
            print("    - Check status with     : python bb_telegram_sniper.py --status-task")
            print("    - Remove anytime with   : python bb_telegram_sniper.py --remove-task\n")
        else:
            print(f"[X] Error creating task:\n{res.stderr.strip() or res.stdout.strip()}")
    except Exception as e:
        print(f"[!] Execution failed: {e}")


def remove_task():
    """Remove background scheduled task from Windows Task Scheduler."""
    cmd = ["schtasks", "/delete", "/tn", TASK_NAME, "/f"]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode == 0:
        print(f"[OK] Scheduled task '{TASK_NAME}' removed.")
    else:
        print(f"[!] Task '{TASK_NAME}' was not found or could not be removed.")


def status_task():
    """Query scheduled task status."""
    cmd = ["schtasks", "/query", "/tn", TASK_NAME, "/fo", "LIST", "/v"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode == 0:
            print(f"[OK] Task '{TASK_NAME}' is currently ACTIVE.\n")
            print("  Configured Schedule: 4 Times Daily (12:00 AM, 4:00 PM, 7:00 PM, 11:30 PM)\n")
            for line in res.stdout.splitlines():
                line_str = line.strip()
                if any(line_str.startswith(k) for k in [
                    "TaskName:", "Status:", "Next Run Time:", "Last Run Time:", "Last Result:", "Schedule Type:", "Start Time:"
                ]):
                    print(f"  {line_str}")
        else:
            print(f"[!] Task '{TASK_NAME}' is NOT registered.")
            print("    Run 'python bb_telegram_sniper.py --install-task' to enable scheduled alerts.")
    except Exception as e:
        print(f"[!] Error querying task: {e}")


# ==============================================================================
# Main CLI Interface
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="BigBasket Telegram Sniper - Headless Background Deal Tracker"
    )
    parser.add_argument("--now", "--run-now", action="store_true", help="Execute background scan and alert Telegram now")
    parser.add_argument("--test-telegram", action="store_true", help="Send a test message to Telegram bot")
    parser.add_argument("--install-task", action="store_true", help="Register 4x daily schedule in Windows Task Scheduler")
    parser.add_argument("--remove-task", action="store_true", help="Remove scheduled task")
    parser.add_argument("--status-task", action="store_true", help="View scheduled task status")
    parser.add_argument("--reset-history", action="store_true", help="Clear deals history tracking database")

    args = parser.parse_args()

    if args.now:
        execute_scan_and_alert()
    elif args.test_telegram:
        test_telegram_alert()
    elif args.install_task:
        install_task()
    elif args.remove_task:
        remove_task()
    elif args.status_task:
        status_task()
    elif args.reset_history:
        if os.path.exists(HISTORY_FILE):
            os.remove(HISTORY_FILE)
            print("[OK] Deals history cleared. Next scan will treat all deals as fresh.")
        else:
            print("[*] No deals history found to clear.")
    else:
        print("=" * 65)
        print("  BigBasket Telegram Sniper (Headless Background Automation)")
        print("=" * 65)
        print("Available options:")
        print("  1) python bb_telegram_sniper.py --now            -> Run background scan and alert now")
        print("  2) python bb_telegram_sniper.py --test-telegram  -> Send test deal card to Telegram")
        print("  3) python bb_telegram_sniper.py --install-task   -> Register 4x daily schedule in Windows")
        print("  4) python bb_telegram_sniper.py --status-task    -> Check task status & next run times")
        print("  5) python bb_telegram_sniper.py --reset-history  -> Reset deals history database")
        print("  6) python bb_telegram_sniper.py --remove-task    -> Remove scheduled task")
        print("-" * 65)
        parser.print_help()


if __name__ == "__main__":
    main()
