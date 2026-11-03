"""
BigBasket Deal Sniper - Headless Telegram Bot Automation
=========================================================
Runs completely in the background without opening any visible browser window.
Scans BigBasket for steep discounts (>=50% or >=70% OFF) and alerts via Telegram Bot.

Features:
- Completely Invisible Execution (off-screen Edge instance with masked screen coordinates)
- Pincode & Dark-Store Lock: Automatically enforces delivery pincode (e.g. 560045) in browser session
- Strict Out-of-Stock (OOS) Filtering: Rejects products with avail_status != '001', 'Notify Me', not_for_sale, etc.
- Upgraded Akamai WAF Evasion:
    * Aborts heavy media/fonts while preserving JS sensors
    * Spoofs dynamic Referer via window.history.pushState for every category
    * Extracts session tracker UUID from sessionStorage
    * Generates human mouse movement and wheel telemetry to keep _abck valid
    * Micro-batching and adaptive jitter between categories
    * Graceful 429/503 backoff and 403 recovery
- Variant Product Parsing: Scans both top-level products and nested variant children
- HTML Telegram Formatting: 100% immune to entity parse errors
- Deduplication & 15-Day Cooloff Rule:
    * Sends new deals on Day 1.
    * If an item remains at the same discount on Day 2, suppresses it for 15 days.
    * If the discount changes, alerts immediately.
    * Commits history only after successful Telegram delivery.
- File Logging: Auto-rotating log (bb_sniper.log) for background diagnostics
- Windows Task Scheduler integration (4x daily: 12:00 AM, 4:00 PM, 7:00 PM, 11:30 PM)

Usage:
    python bb_telegram_sniper.py --now             # Run scan for assigned categories & alert
    python bb_telegram_sniper.py --now --all-cats  # Run scan for all 20 categories
    python bb_telegram_sniper.py --test-telegram   # Send a test message to Telegram bot
    python bb_telegram_sniper.py --install-task    # Register 4x daily schedule in Windows
    python bb_telegram_sniper.py --status-task     # Check Windows Task Scheduler status
    python bb_telegram_sniper.py --remove-task     # Remove scheduled task
    python bb_telegram_sniper.py --reset-history   # Reset deals history tracking database
"""

import sys
import os
import re
import time
import json
import html
import random
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
LOG_FILE = os.path.join(SCRIPT_DIR, "bb_sniper.log")
TASK_NAME = "BigBasketTelegramSniper"


def log(msg: str):
    """Print to console and append to rotating log file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    print(msg)
    try:
        # Rotate log if larger than 1 MB
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 1024 * 1024:
            old_log = LOG_FILE + ".1"
            if os.path.exists(old_log):
                try:
                    os.remove(old_log)
                except Exception:
                    pass
            try:
                os.rename(LOG_FILE, old_log)
            except Exception:
                pass
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except Exception:
        pass


def load_env():
    """Load settings from .env file without external dependencies."""
    config = {
        "TELEGRAM_BOT_TOKEN": "",
        "TELEGRAM_CHAT_ID": "",
        "MIN_DISCOUNT": 50,
        "PINCODE": "560045",
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
            log(f"[!] Warning reading .env: {e}")
    return config


CFG = load_env()

# Master list of all 20 categories
ALL_CATEGORIES = [
    {"name": "Foodgrains, Oil & Masala", "slug": "foodgrains-oil-masala"},
    {"name": "Edible Oils & Ghee", "slug": "edible-oils-ghee"},
    {"name": "Dairy", "slug": "dairy"},
    {"name": "Beverages", "slug": "beverages"},
    {"name": "Biscuits & Cookies", "slug": "biscuits-cookies"},
    {"name": "Chocolates & Candies", "slug": "chocolates-candies"},
    {"name": "Snacks & Branded Foods", "slug": "snacks-branded-foods"},
    {"name": "Bakery, Cakes & Dairy", "slug": "bakery-cakes-dairy"},
    {"name": "Dry Fruits", "slug": "dry-fruits"},
    {"name": "Skin Care", "slug": "skin-care"},
    {"name": "Hair Care", "slug": "hair-care"},
    {"name": "Bath & Hand Wash", "slug": "bath-hand-wash"},
    {"name": "Baby Care", "slug": "baby-care"},
    {"name": "Detergents & Dishwash", "slug": "detergents-dishwash"},
    {"name": "Gourmet & World Food", "slug": "gourmet-world-food"},
    {"name": "Diapers & Wipes", "slug": "diapers-wipes"},
    {"name": "Beauty & Hygiene", "slug": "beauty-hygiene"},
    {"name": "Cleaning & Household", "slug": "cleaning-household"},
    {"name": "Kitchen & Home Needs", "slug": "kitchen-garden-pets"},
    {"name": "Fruits & Vegetables", "slug": "fruits-vegetables"}
]

# Currently assigned categories for daily scheduled scanning
# (Kept to 4 categories for WAF validation as instructed; switchable via --all-cats)
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
# Telegram Bot Delivery (HTML Parse Mode)
# ==============================================================================

def send_telegram_message(text: str, bot_token: str = None, chat_id: str = None) -> bool:
    """Send a formatted message to Telegram Bot via HTTP API using HTML parse mode."""
    token = bot_token or CFG["TELEGRAM_BOT_TOKEN"]
    cid = chat_id or CFG["TELEGRAM_CHAT_ID"]

    if not token or not cid or token == "your_telegram_bot_token_here":
        log("[!] Telegram credentials missing! Please configure TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": cid,
        "text": text,
        "parse_mode": "HTML",
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
        log(f"[!] Telegram API error ({e.code}): {err_msg}")
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
        log(f"[!] Network error sending to Telegram: {e}")
        return False


def chunk_and_send_deals(deal_items: list, bot_token: str = None, chat_id: str = None) -> int:
    """
    Format deals into exact 3-line blocks separated by \\n\\n,
    chunk them safely within Telegram's 4096 char limit, and send using HTML.
    """
    if not deal_items:
        return 0

    deal_blocks = []
    for d in deal_items:
        title = html.escape(d["title"])
        sp_str = str(int(d["sp"])) if float(d["sp"]).is_integer() else f"{d['sp']:.2f}"
        mrp_str = str(int(d["mrp"])) if float(d["mrp"]).is_integer() else f"{d['mrp']:.2f}"
        disc_str = str(int(d["disc"]))
        escaped_url = html.escape(d["url"], quote=True)

        block = (
            f"🛒 {title}\n"
            f"💰 ₹{sp_str}  (MRP: ₹{mrp_str}) || {disc_str}% OFF\n"
            f'🔗 <a href="{escaped_url}">Open on BigBasket</a>'
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
            log(f"[OK] Sent Telegram message batch [{idx + 1}/{len(messages)}]")
        else:
            log(f"[!] Failed to send Telegram message batch [{idx + 1}/{len(messages)}]")
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
        log(f"[!] Failed to save history: {e}")


def filter_deals_with_cooloff(scanned_deals: list, today_str: str = None) -> tuple:
    """
    Applies the user's specific cooloff rules:
    1. Send deals when first seen.
    2. If an item stays at the same discount for the second day, hide it from sending for 15 days.
    3. If the discount changes, send immediately.
    4. Do not repeat identical sends on the same calendar day.

    Returns (deals_to_send, updated_history).
    History is NOT committed to disk here; caller commits only after successful send.
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

        # CASE 1: Discount changed! (e.g. 50% -> 70% or vice versa) -> Alert immediately
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
            continue

        # Check suppression window FIRST before counting consecutive days
        if suppressed_until:
            try:
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
            except Exception:
                record["suppressed_until"] = None

        # CASE 3: It's a new calendar day! Verify consecutive day progression
        try:
            last_seen_dt = date.fromisoformat(last_seen)
        except Exception:
            last_seen_dt = today_dt

        if last_seen != today_str:
            is_consecutive_day = (last_seen_dt == today_dt - timedelta(days=1))
            if is_consecutive_day:
                consec_days += 1
            else:
                consec_days = 1
            record["consecutive_days_at_same_disc"] = consec_days

        # CASE 4: Second day at the SAME discount -> Suppress for 15 days!
        if consec_days >= 2:
            supp_target = (today_dt + timedelta(days=15)).isoformat()
            record["suppressed_until"] = supp_target
            continue

        # Otherwise send (first day or refreshed send)
        record["last_sent"] = today_str
        deals_to_send.append(item)

    return deals_to_send, history


# ==============================================================================
# Location & Pincode Enforcement
# ==============================================================================

def ensure_pincode_set(page, target_pincode: str) -> bool:
    """
    Verifies that the BigBasket browser session is locked to the configured pincode (e.g. 560045).
    If mismatched or missing, uses the location autocomplete search to lock into the authentic darkstore.
    """
    target_pin = str(target_pincode or "").strip()
    if not target_pin:
        return True

    cookies = page.context.cookies()
    curr_pin = next((c["value"] for c in cookies if c["name"] == "_bb_pin_code"), "")
    if curr_pin == target_pin:
        log(f"[OK] Delivery location verified: Pincode {target_pin} is active.")
        return True

    log(f"[*] Delivery pincode currently '{curr_pin or 'default'}'. Switching to '{target_pin}'...")
    try:
        # Click header location button
        page.evaluate("""() => {
            let btns = Array.from(document.querySelectorAll('header button, [data-headlessui-state]'));
            let btn = btns.find(b => {
                let t = (b.innerText || '');
                return t.includes('Location') || t.includes('Bengaluru') || t.includes('Bangalore') || t.includes('Delivery in') || t.includes('5600');
            });
            if (btn) btn.click();
        }""")
        time.sleep(1.5)

        # Check for "Click here to change" inside location popup
        page.evaluate("""() => {
            let changeLink = Array.from(document.querySelectorAll('button, a, span')).find(el => {
                let t = (el.innerText || '').toLowerCase();
                return t.includes('click here to change') || (t.includes('change') && t.includes('location'));
            });
            if (changeLink) changeLink.click();
        }""")
        time.sleep(1.0)

        # Wait for input
        inp = page.locator('input[placeholder*="area or street"]').first
        if not inp.is_visible():
            page.evaluate("""() => {
                let all = Array.from(document.querySelectorAll('button, div[role="button"]'));
                for (let el of all) {
                    if ((el.innerText || '').includes('Location')) { el.click(); break; }
                }
            }""")
            time.sleep(1.5)

        if inp.is_visible():
            inp.fill(target_pin)
            log(f"[*] Entered {target_pin} into location search...")
            time.sleep(2.5)

            # Click matching suggestion
            clicked_sugg = page.evaluate("""(pin) => {
                let items = Array.from(document.querySelectorAll('li, div, p, span')).filter(el => {
                    let t = el.innerText || '';
                    return t.includes(pin) && (t.includes('Bengaluru') || t.includes('Bangalore') || t.includes('India'));
                });
                let target = items[items.length - 1];
                if (target) {
                    target.click();
                    return target.innerText.slice(0, 70);
                }
                return null;
            }""", target_pin)
            log(f"[OK] Selected location suggestion: {clicked_sugg}")
            time.sleep(3.5)

        # Verify new cookie
        new_cookies = page.context.cookies()
        new_pin = next((c["value"] for c in new_cookies if c["name"] == "_bb_pin_code"), "")
        if new_pin == target_pin:
            log(f"[OK] Successfully locked delivery session to pincode: {new_pin}")
            return True
        else:
            log(f"[!] Warning: Active pincode is '{new_pin}', expected '{target_pin}'.")
            return False
    except Exception as e:
        log(f"[!] Error setting delivery pincode: {e}")
        return False


# ==============================================================================
# Product Parsing & Strict Out-Of-Stock Filtering
# ==============================================================================

def parse_product_node(p: dict, cname: str, min_discount: int):
    """
    Parses a single BigBasket product dict (top-level or child variant)
    and applies strict price, discount, and out-of-stock validation.
    """
    if not p or not isinstance(p, dict):
        return None

    # Filter out-of-stock items with strict checks
    avail = p.get("availability") or {}
    avail_status = str(avail.get("avail_status", "")).strip()
    btn = str(avail.get("button") or avail.get("button_state") or "").strip().lower()
    not_for_sale = avail.get("not_for_sale") is True
    is_available = avail.get("is_available")

    # In BigBasket: "001" is Available / In Stock.
    # Anything other than "001" (such as "000", "002") or "Notify Me" is OUT OF STOCK.
    if (
        avail_status != "001"
        or is_available is False
        or not_for_sale
        or btn in ("notify me", "out_of_stock", "not_available", "coming_soon", "sold out")
    ):
        return None

    # Check inventory node if present
    inv = p.get("inv_info") or p.get("inventory") or {}
    if inv.get("is_out_of_stock") is True or str(inv.get("stock_status", "")).strip() in ("000", "002"):
        return None

    pricing = p.get("pricing") or {}
    disc_info = pricing.get("discount") or {}
    mrp = float(disc_info.get("mrp") or pricing.get("mrp") or p.get("mrp") or 0)
    sp = float(disc_info.get("prim_price", {}).get("sp") or pricing.get("sp") or p.get("sp") or 0)

    if sp <= 0 and mrp > 0:
        sp = mrp
    disc = round(((mrp - sp) / mrp) * 100) if mrp > 0 and sp > 0 else 0

    if disc < min_discount:
        return None

    brand = (p.get("brand") or {}).get("name", "").strip() or p.get("p_brand", "").strip()
    desc = (p.get("desc") or p.get("p_desc") or p.get("name") or "").strip()
    w = (p.get("w") or p.get("pack_desc") or "").strip()

    title_parts = []
    if brand and brand.lower() not in desc.lower():
        title_parts.append(brand)
    if desc:
        title_parts.append(desc)
    if w and w.lower() not in desc.lower():
        title_parts.append(f"({w})")
    full_title = " ".join(title_parts).strip() or "Product"

    abs_url = p.get("absolute_url", "")
    if abs_url.startswith("http"):
        url = abs_url
    elif abs_url:
        url = f"https://www.bigbasket.com{abs_url}"
    else:
        url = f"https://www.bigbasket.com/pd/{p.get('id', '')}"

    return {
        "id": str(p.get("id")),
        "title": full_title,
        "brand": brand,
        "desc": desc,
        "mrp": mrp,
        "sp": sp,
        "disc": disc,
        "url": url,
        "category": cname
    }


# ==============================================================================
# Headless Background Scanner (Off-screen Playwright Engine with WAF Defense)
# ==============================================================================

def scan_deals_headless(categories: list = None) -> list:
    """
    Launches Microsoft Edge off-screen via Playwright,
    locks into the authentic delivery pincode, evades Akamai Bot Manager,
    and returns live, in-stock deals.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log("[!] Playwright is required. Run: python -m pip install playwright")
        return []

    if categories is None:
        categories = ASSIGNED_CATEGORIES

    min_discount = CFG.get("MIN_DISCOUNT", 50)
    target_pin = str(CFG.get("PINCODE", "560045")).strip()
    profile_dir = CFG.get("EDGE_PROFILE_DIR", os.path.expandvars(r"%LOCALAPPDATA%\bb_bot_profile"))
    os.makedirs(profile_dir, exist_ok=True)

    log(f"[*] Starting silent background scan for {len(categories)} categories...")
    log(f"[*] Target delivery pincode: {target_pin}")
    log(f"[*] Discount filter threshold: >= {min_discount}% OFF")

    all_deals = []
    seen_ids = set()

    with sync_playwright() as playwright_engine:
        # Launch persistent context off-screen (-32000, -32000) so NO window is visible,
        # while masking screen coordinates via add_init_script so bmak never sees off-screen coords.
        context = playwright_engine.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            channel="msedge",
            headless=False,
            args=[
                "--window-position=-32000,-32000",
                "--window-size=1920,1080",
                "--disable-blink-features=AutomationControlled"
            ],
            viewport={"width": 1920, "height": 1080}
        )

        # Mask off-screen coordinates in JavaScript
        context.add_init_script("""
            Object.defineProperty(window, 'screenX', { get: () => 0 });
            Object.defineProperty(window, 'screenY', { get: () => 0 });
            Object.defineProperty(window, 'screenLeft', { get: () => 0 });
            Object.defineProperty(window, 'screenTop', { get: () => 0 });
        """)

        page = context.pages[0] if context.pages else context.new_page()

        # Block heavy static media assets to keep scan fast and bandwidth-minimal
        page.route(
            re.compile(r"\.(png|jpg|jpeg|webp|gif|svg|woff|woff2|ttf|mp4)(\?.*)?$", re.IGNORECASE),
            lambda route: route.abort()
        )

        try:
            log("[*] Establishing BigBasket session in background...")
            page.goto("https://www.bigbasket.com/", wait_until="domcontentloaded", timeout=40000)
            time.sleep(3)

            # Enforce pincode and darkstore alignment
            ensure_pincode_set(page, target_pin)

            # Reusable JS function executed inside the authenticated browser context
            js_fetch_category = """
            async (slug) => {
                try {
                    // Update location so browser sends authentic matching Referer header
                    window.history.pushState({}, '', '/cl/' + slug + '/?nc=nb');

                    // Extract session tracker UUID
                    let tracker = '';
                    try {
                        for (let i = 0; i < sessionStorage.length; i++) {
                            const k = sessionStorage.key(i);
                            if (k && k.toLowerCase().includes('tracker')) {
                                const v = sessionStorage.getItem(k);
                                if (v && v.length > 10) { tracker = v; break; }
                            }
                        }
                    } catch(_) {}
                    if (!tracker) {
                        tracker = (typeof crypto !== 'undefined' && crypto.randomUUID) ? crypto.randomUUID() : ('bb-' + Date.now());
                    }

                    const res = await fetch(`https://www.bigbasket.com/listing-svc/v2/products?type=pc&slug=${slug}&page=1&sort=dphtl`, {
                        headers: {
                            "accept": "application/json",
                            "x-channel": "BB-WEB",
                            "x-entry-context": "bb-b2c",
                            "x-entry-context-id": "100",
                            "x-tracker": tracker
                        }
                    });

                    if (!res.ok) return { status: res.status, products: [] };
                    const data = await res.json();
                    let prods = [];
                    for (const t of (data.tabs || [])) {
                        const p_list = t?.product_info?.products || [];
                        if (p_list.length) prods.push(...p_list);
                    }
                    return { status: 200, products: prods };
                } catch(e) {
                    return { status: 0, error: e.message, products: [] };
                }
            }
            """

            for idx, cat in enumerate(categories):
                slug = cat["slug"]
                cname = cat["name"]
                log(f"[*] Scanning [{idx + 1}/{len(categories)}]: {cname}...")

                # Micro-batching pause every 5 categories
                if idx > 0 and idx % 5 == 0:
                    pause_sec = random.uniform(12.0, 18.0)
                    log(f"[*] Batch milestone ({idx} categories scanned). Taking a human pause ({pause_sec:.1f}s)...")
                    for _ in range(2):
                        page.mouse.move(random.randint(100, 1200), random.randint(100, 700), steps=6)
                        time.sleep(0.5)
                    time.sleep(pause_sec - 1.0)

                # Human behavioral telemetry before each category fetch
                for _ in range(random.randint(2, 3)):
                    page.mouse.move(random.randint(100, 1200), random.randint(100, 700), steps=5)
                page.mouse.wheel(0, random.choice([-120, 120]))
                time.sleep(random.uniform(0.3, 0.7))

                # Fetch category with retries for 429 / 503
                data = None
                max_retries = 2
                status = 0
                for attempt in range(max_retries + 1):
                    res = page.evaluate(js_fetch_category, slug)
                    status = res.get("status", 0)

                    if status == 200:
                        data = res.get("products", [])
                        break
                    elif status in (429, 503):
                        wait_sec = 30 + random.uniform(5, 15)
                        log(f"[!] Rate limited (HTTP {status}) on {cname}. Pausing {wait_sec:.1f}s (attempt {attempt + 1}/{max_retries + 1})...")
                        time.sleep(wait_sec)
                    elif status == 403:
                        log(f"[!] Akamai WAF 403 Access Denied on {cname}!")
                        log("[*] Attempting page reload to refresh Akamai session...")
                        try:
                            page.goto("https://www.bigbasket.com/", wait_until="domcontentloaded", timeout=40000)
                            time.sleep(15)
                            for _ in range(3):
                                page.mouse.move(random.randint(100, 1200), random.randint(100, 700), steps=6)
                            res_retry = page.evaluate(js_fetch_category, slug)
                            if res_retry.get("status") == 200:
                                log(f"[OK] Recovery successful for {cname}!")
                                data = res_retry.get("products", [])
                                break
                        except Exception as e:
                            log(f"[!] Recovery failed: {e}")
                        log("[!] Akamai 403 block persists. Gracefully halting scan to protect IP.")
                        break
                    else:
                        log(f"[!] HTTP {status} on {cname}: {res.get('error', 'Unknown')}")
                        break

                if status == 403 and data is None:
                    break

                # Parse top-level products & variant children
                if data:
                    cat_deals = 0
                    for prod in data:
                        # Top-level product
                        item = parse_product_node(prod, cname, min_discount)
                        if item and item["id"] not in seen_ids:
                            seen_ids.add(item["id"])
                            all_deals.append(item)
                            cat_deals += 1

                        # Variant children
                        for child in (prod.get("children") or []):
                            c_item = parse_product_node(child, cname, min_discount)
                            if c_item and c_item["id"] not in seen_ids:
                                seen_ids.add(c_item["id"])
                                all_deals.append(c_item)
                                cat_deals += 1

                    log(f"[OK] Found {cat_deals} in-stock deals (>= {min_discount}% OFF) in {cname}")

                # Jitter delay between categories
                if idx < len(categories) - 1:
                    delay = random.uniform(3.2, 5.8)
                    time.sleep(delay)

        finally:
            context.close()
            log("[*] Background browser closed cleanly.")

    all_deals.sort(key=lambda x: x["disc"], reverse=True)
    return all_deals


# ==============================================================================
# Core Execution Workflow
# ==============================================================================

def execute_scan_and_alert(categories: list = None):
    """Perform full background scan, apply 15-day cooloff, and send to Telegram."""
    log("=" * 65)
    log("  BigBasket Telegram Sniper - Headless Background Execution")
    log("=" * 65)
    log(f"[*] Execution time: {datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')}")

    scanned_deals = scan_deals_headless(categories)
    log(f"\n[*] Total live in-stock deals found: {len(scanned_deals)}")

    if not scanned_deals:
        log("[*] No deals found matching filter threshold today.")
        return

    deals_to_send, updated_history = filter_deals_with_cooloff(scanned_deals)
    log(f"[*] Deals eligible to alert (after cooloff/dedup): {len(deals_to_send)}")

    if not deals_to_send:
        save_deals_history(updated_history)
        log("[*] All deals are either already sent today or suppressed by the 15-day rule.")
        return

    log("\n[*] Sending deals to Telegram...")
    batches = chunk_and_send_deals(deals_to_send)
    if batches > 0:
        save_deals_history(updated_history)
        log(f"[OK] Done! Delivered {len(deals_to_send)} deals across {batches} Telegram message(s).")
    else:
        log("[!] Warning: Telegram send failed or 0 batches delivered. History not committed to allow retry.")


def test_telegram_alert():
    """Send a test deal to verify Telegram bot setup."""
    log("[*] Testing Telegram bot credentials...")
    sample_deal = [{
        "id": "test_99999",
        "title": "Fortune Sunlite Refined Sunflower Oil (1L)",
        "sp": 85,
        "mrp": 175,
        "disc": 51,
        "url": "https://www.bigbasket.com"
    }]
    count = chunk_and_send_deals(sample_deal)
    if count > 0:
        log("[OK] Test message delivered successfully to your Telegram chat!")
    else:
        log("[!] Test failed. Please check your BOT_TOKEN and CHAT_ID in .env")


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

    log(f"[*] Registering background scheduled task: {TASK_NAME}")
    log("[*] Schedule: 4 Times Daily (12:00 AM, 4:00 PM, 7:00 PM, 11:30 PM)")
    log(f"[*] Executable: {pythonw_path}")
    log(f"[*] Working Directory: {SCRIPT_DIR}")

    ps_script = f"""
    $ErrorActionPreference = 'Stop'
    $action = New-ScheduledTaskAction -Execute '{pythonw_path}' -Argument '"{script_path}" --run-now' -WorkingDirectory '{SCRIPT_DIR}'
    $triggers = @(
        $(New-ScheduledTaskTrigger -Daily -At "00:00"),
        $(New-ScheduledTaskTrigger -Daily -At "16:00"),
        $(New-ScheduledTaskTrigger -Daily -At "19:00"),
        $(New-ScheduledTaskTrigger -Daily -At "23:30")
    )
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -WakeToRun
    Register-ScheduledTask -TaskName '{TASK_NAME}' -Action $action -Trigger $triggers -Settings $settings -Force
    """

    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            capture_output=True, text=True, check=False
        )
        if res.returncode == 0:
            log(f"\n[OK] SUCCESS: Background task '{TASK_NAME}' registered successfully!")
            log("    Runs completely hidden in the background without popping up any browser window at:")
            log("      • 12:00 AM  (Midnight Deals)")
            log("      •  4:00 PM  (Afternoon Restock)")
            log("      •  7:00 PM  (Evening Flash Sales)")
            log("      • 11:30 PM  (Pre-Midnight Clearance)")
            log("\n    - Test immediately with : python bb_telegram_sniper.py --now")
            log("    - Test Telegram alert   : python bb_telegram_sniper.py --test-telegram")
            log("    - Check status with     : python bb_telegram_sniper.py --status-task")
            log("    - View execution log at : bb_sniper.log")
            log("    - Remove anytime with   : python bb_telegram_sniper.py --remove-task\n")
        else:
            log(f"[X] Error creating task:\n{res.stderr.strip() or res.stdout.strip()}")
    except Exception as e:
        log(f"[!] Execution failed: {e}")


def remove_task():
    """Remove background scheduled task from Windows Task Scheduler."""
    cmd = ["schtasks", "/delete", "/tn", TASK_NAME, "/f"]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode == 0:
        log(f"[OK] Scheduled task '{TASK_NAME}' removed.")
    else:
        log(f"[!] Task '{TASK_NAME}' was not found or could not be removed.")


def status_task():
    """Query scheduled task status."""
    cmd = ["schtasks", "/query", "/tn", TASK_NAME, "/fo", "LIST", "/v"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode == 0:
            log(f"[OK] Task '{TASK_NAME}' is currently ACTIVE.\n")
            log("  Configured Schedule: 4 Times Daily (12:00 AM, 4:00 PM, 7:00 PM, 11:30 PM)\n")
            for line in res.stdout.splitlines():
                line_str = line.strip()
                if any(line_str.startswith(k) for k in [
                    "TaskName:", "Status:", "Next Run Time:", "Last Run Time:", "Last Result:", "Schedule Type:", "Start Time:"
                ]):
                    log(f"  {line_str}")
        else:
            log(f"[!] Task '{TASK_NAME}' is NOT registered.")
            log("    Run 'python bb_telegram_sniper.py --install-task' to enable scheduled alerts.")
    except Exception as e:
        log(f"[!] Error querying task: {e}")


# ==============================================================================
# Main CLI Interface
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="BigBasket Telegram Sniper - Headless Background Deal Tracker"
    )
    parser.add_argument("--now", "--run-now", action="store_true", help="Execute background scan and alert Telegram now")
    parser.add_argument("--all-cats", action="store_true", help="Scan all 20 categories instead of default assigned categories")
    parser.add_argument("--test-telegram", action="store_true", help="Send a test message to Telegram bot")
    parser.add_argument("--install-task", action="store_true", help="Register 4x daily schedule in Windows Task Scheduler")
    parser.add_argument("--remove-task", action="store_true", help="Remove scheduled task")
    parser.add_argument("--status-task", action="store_true", help="View scheduled task status")
    parser.add_argument("--reset-history", action="store_true", help="Clear deals history tracking database")

    args = parser.parse_args()

    selected_categories = ALL_CATEGORIES if args.all_cats else ASSIGNED_CATEGORIES

    if args.now:
        execute_scan_and_alert(selected_categories)
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
            log("[OK] Deals history cleared. Next scan will treat all deals as fresh.")
        else:
            log("[*] No deals history found to clear.")
    else:
        print("=" * 65)
        print("  BigBasket Telegram Sniper (Headless Background Automation)")
        print("=" * 65)
        print("Available options:")
        print("  1) python bb_telegram_sniper.py --now            -> Run background scan for assigned categories")
        print("  2) python bb_telegram_sniper.py --now --all-cats -> Run background scan for all 20 categories")
        print("  3) python bb_telegram_sniper.py --test-telegram  -> Send test deal card to Telegram")
        print("  4) python bb_telegram_sniper.py --install-task   -> Register 4x daily schedule in Windows")
        print("  5) python bb_telegram_sniper.py --status-task    -> Check task status & next run times")
        print("  6) python bb_telegram_sniper.py --reset-history  -> Reset deals history database")
        print("  7) python bb_telegram_sniper.py --remove-task    -> Remove scheduled task")
        print("-" * 65)
        parser.print_help()


if __name__ == "__main__":
    main()
