"""
=============================================================================
BigBasket Smart Deal Diffing & Categorization Engine
=============================================================================
1. Groups deals into clean visual category buckets:
   - 🏠 Home, Kitchen & Cleaning
   - 🪔 Pooja, Festive & Seasonal
   - 🌾 Staples, Oil & Masala
   - 🥨 Snacks, Bakery & Dairy
   - 🧴 Personal Care & Beauty
   - 👶 Baby Care
   - 🎁 General & Other
2. Manages 7-Day Hybrid Cooldown:
   - New deals: Alerted immediately (🆕 NEW DEAL).
   - Price drops: Alerted immediately with price drop amount (📉 PRICE DROP (-₹X)).
   - Discount increases: Alerted immediately (💥 DISCOUNT UP (+X%)).
   - Back in stock: Alerted immediately (🔄 BACK IN STOCK).
   - Static/unchanged deals: Suppressed if alerted < 7 days ago.
   - Weekly refresh: Surfaced once a week if 7+ days elapsed (🗓️ WEEKLY TOP PICK).
=============================================================================
"""

import datetime
import re
from typing import Dict, List, Any, Tuple, Optional
from tracker import get_product_history, upsert_product_history

class DiffType:
    NEW = "NEW"
    PRICE_DROP = "PRICE_DROP"
    DISCOUNT_UP = "DISCOUNT_UP"
    RESTOCKED = "RESTOCKED"
    WEEKLY_PICK = "WEEKLY_PICK"
    STALE = "STALE"

# Category Maps & Display Names
CATEGORY_MAP = {
    "cat_home": "🏠 Home, Kitchen & Cleaning",
    "cat_pooja": "🪔 Pooja, Festive & Seasonal",
    "cat_staples": "🌾 Staples, Oil & Masala",
    "cat_snacks": "🥨 Snacks, Bakery & Dairy",
    "cat_beauty": "🧴 Personal Care & Beauty",
    "cat_baby": "👶 Baby Care",
    "cat_all": "🔥 All Top Deals"
}

# Categorization Keywords (checked in order of specificity)
CATEGORY_BUCKETS = [
    ("🪔 Pooja, Festive & Seasonal", [
        "pooja", "puja", "diya", "diyas", "rakhi", "rakhis", "agarbatti", "incense",
        "dhoop", "camphor", "havan", "sambrani", "tasbih", "prayer", "christmas",
        "xmas", "bauble", "ganesha", "ganesh", "swastik", "rangoli", "festival",
        "festive", "idol", "murtis", "mandir", "chawal", "roli", "haldi kumkum",
        "bells", "windchimes", "hanging bells"
    ]),
    ("👶 Baby Care", [
        "diaper", "diapers", "baby diaper", "baby wipes", "baby care", "baby",
        "pram", "stroller", "feeding bottle", "pacifier", "baby lotion", "baby soap",
        "baby wash", "baby shampoo", "crib", "play gym", "crawling crab"
    ]),
    ("🌾 Staples, Oil & Masala", [
        "atta", "flour", "rice", "dal", "pulse", "edible oil", "refined oil",
        "mustard oil", "sunflower oil", "ghee", "masala", "spice", "spices",
        "sugar", "salt", "besan", "sooji", "rava", "maida", "poha", "toor",
        "moong", "urad", "chana", "rajma", "foodgrains", "organic staples"
    ]),
    ("🥨 Snacks, Bakery & Dairy", [
        "snack", "snacks", "biscuit", "biscuits", "cookie", "cookies", "chocolate",
        "chocolates", "candy", "candies", "dry fruit", "dry fruits", "nut", "nuts",
        "almond", "cashew", "kaju", "badam", "raisin", "kishmish", "pista", "walnut",
        "dates", "makhana", "namkeen", "chips", "dairy", "milk", "cheese", "butter",
        "paneer", "bakery", "bread", "cake", "beverage", "tea", "coffee", "juice"
    ]),
    ("🧴 Personal Care & Beauty", [
        "beauty", "skin care", "skincare", "hair care", "haircare",
        "bath", "hand wash", "handwash", "soap", "body wash", "shampoo",
        "conditioner", "face wash", "facewash", "lotion", "cream", "sunscreen",
        "serum", "deodorant", "perfume", "deo", "toothpaste", "toothbrush",
        "shaving", "razor", "sanitary", "pad", "pads", "underpads", "adult wipes"
    ]),
    ("🏠 Home, Kitchen & Cleaning", [
        "cookware", "kitchen", "cleaning", "detergent", "dishwash", "chopper",
        "bottle", "flask", "mug", "kadhai", "pan", "gas stove", "stove", "mat",
        "mats", "table mat", "drying stand", "stand", "cloth liner", "storage",
        "organizer", "organiser", "bin", "container", "hooks", "hook", "spatula",
        "tiffin", "lunch box", "mop", "broom", "wiper", "scrubber", "sponge",
        "wallpaper", "sticker", "curtain", "towel", "drain cover", "pourer",
        "dispenser", "peeler", "knife", "scissors", "bedsheet", "pillow", "cushion",
        "clock", "mirror", "planter", "pot", "plastic", "stainless steel"
    ])
]

def classify_category_bucket(product: Dict[str, Any]) -> str:
    """Classifies a product into one of the intuitive category buckets."""
    name = str(product.get("name") or "").lower()
    brand = str(product.get("brand") or "").lower()
    category = str(product.get("category") or "").lower()
    url = str(product.get("url") or "").lower()

    name_text = f"{name} {brand}"

    # Pass 1: Whole-word match in product name & brand
    for bucket_name, keywords in CATEGORY_BUCKETS:
        for kw in keywords:
            if re.search(r'\b' + re.escape(kw) + r'\b', name_text, re.I):
                return bucket_name

    # Pass 2: Whole-word match in category field or URL
    cat_text = f"{category} {url}"
    for bucket_name, keywords in CATEGORY_BUCKETS:
        for kw in keywords:
            if re.search(r'\b' + re.escape(kw) + r'\b', cat_text, re.I):
                return bucket_name

    return "🎁 General & Other"

def group_products_by_category(products: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Groups a list of products by their category bucket."""
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for p in products:
        bucket = p.get("category_bucket") or classify_category_bucket(p)
        p["category_bucket"] = bucket
        if bucket not in grouped:
            grouped[bucket] = []
        grouped[bucket].append(p)
    return grouped

def filter_by_category_code(products: List[Dict[str, Any]], cat_code: str) -> List[Dict[str, Any]]:
    """Filters products to match a specific category code (e.g. cat_home, cat_pooja)."""
    if not cat_code or cat_code == "cat_all":
        return products
    target_bucket_name = CATEGORY_MAP.get(cat_code)
    if not target_bucket_name:
        return products

    return [
        p for p in products
        if (p.get("category_bucket") or classify_category_bucket(p)) == target_bucket_name
    ]

def get_current_ist_date() -> str:
    """Returns today's date string in IST (YYYY-MM-DD)."""
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    ist_now = utc_now + datetime.timedelta(hours=5, minutes=30)
    return ist_now.strftime("%Y-%m-%d")

def analyze_and_update_deals(
    current_products: List[Dict[str, Any]],
    pincode: str,
    is_master_digest: bool = False
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Compares current scraped deals against historical SQLite database records.
    
    Implements a 7-day cooldown on unchanged static items:
    - NEW: First time seen in database at >= 70% OFF.
    - PRICE_DROP: Price dropped lower than last alerted price.
    - DISCOUNT_UP: Discount increased by >= 2%.
    - RESTOCKED: Item was previously out of stock and is now available.
    - WEEKLY_PICK: Unchanged price, but 7+ days elapsed since last alert.
    - STALE: Unchanged price and alerted < 7 days ago (suppressed from alerts).

    Returns:
        (alert_deals, home_deals_pool, pooja_deals_pool, stale_deals)
    """
    today_date = get_current_ist_date()
    today_dt = datetime.datetime.strptime(today_date, "%Y-%m-%d").date()

    alert_deals = []
    home_deals_pool = []
    pooja_deals_pool = []
    stale_deals = []

    for p in current_products:
        uid = str(p.get("id") or p.get("url") or p.get("name"))
        curr_price = float(p.get("sp", 0.0))
        curr_disc = float(p.get("disc", 0.0))
        curr_stock = not bool(p.get("is_out_of_stock", False))
        bucket = classify_category_bucket(p)
        p["category_bucket"] = bucket

        is_home = (bucket == "🏠 Home, Kitchen & Cleaning")
        is_pooja = (bucket == "🪔 Pooja, Festive & Seasonal")

        history = get_product_history(uid, pincode)

        if not history:
            # 1. Brand New Deal detected
            p_copy = dict(p)
            p_copy["diff_type"] = DiffType.NEW
            p_copy["diff_tag"] = "🆕 NEW DEAL"
            p_copy["diff_reason"] = "First time detected at 70%+ OFF"
            alert_deals.append(p_copy)
            if is_home:
                home_deals_pool.append(p_copy)
            elif is_pooja:
                pooja_deals_pool.append(p_copy)
            upsert_product_history(p, pincode, last_alert_date=today_date, last_alert_price=curr_price)

        else:
            prev_price = float(history.get("effective_price") or curr_price)
            prev_disc = float(history.get("discount_pct") or curr_disc)
            prev_stock = bool(history.get("in_stock", True))
            last_alert_date_str = history.get("last_alert_date")
            last_alert_price = float(history.get("last_alert_price") or prev_price)

            days_since_alert = 999
            if last_alert_date_str:
                try:
                    last_alert_dt = datetime.datetime.strptime(last_alert_date_str, "%Y-%m-%d").date()
                    days_since_alert = (today_dt - last_alert_dt).days
                except Exception:
                    pass

            has_price_drop = curr_price < (prev_price - 1.0) or curr_price < (last_alert_price - 1.0)
            has_disc_increase = curr_disc >= (prev_disc + 2.0)
            was_restocked = (not prev_stock) and curr_stock

            # 2. Price Drop Detected
            if has_price_drop:
                drop_amt = min(prev_price, last_alert_price) - curr_price
                p_copy = dict(p)
                p_copy["diff_type"] = DiffType.PRICE_DROP
                p_copy["diff_tag"] = f"📉 PRICE DROP (-₹{drop_amt:,.0f})"
                p_copy["diff_reason"] = f"Price dropped from ₹{last_alert_price:,.0f} to ₹{curr_price:,.0f}"
                alert_deals.append(p_copy)
                if is_home:
                    home_deals_pool.append(p_copy)
                elif is_pooja:
                    pooja_deals_pool.append(p_copy)
                upsert_product_history(p, pincode, last_alert_date=today_date, last_alert_price=curr_price)

            # 3. Restocked Item
            elif was_restocked:
                p_copy = dict(p)
                p_copy["diff_type"] = DiffType.RESTOCKED
                p_copy["diff_tag"] = "🔄 BACK IN STOCK"
                p_copy["diff_reason"] = "Previously out of stock"
                alert_deals.append(p_copy)
                if is_home:
                    home_deals_pool.append(p_copy)
                elif is_pooja:
                    pooja_deals_pool.append(p_copy)
                upsert_product_history(p, pincode, last_alert_date=today_date, last_alert_price=curr_price)

            # 4. Significant Discount Increase (+2% or more)
            elif has_disc_increase:
                disc_diff = curr_disc - prev_disc
                p_copy = dict(p)
                p_copy["diff_type"] = DiffType.DISCOUNT_UP
                p_copy["diff_tag"] = f"💥 DISCOUNT UP (+{disc_diff:.0f}%)"
                p_copy["diff_reason"] = f"Discount increased from {prev_disc:.0f}% to {curr_disc:.0f}%"
                alert_deals.append(p_copy)
                if is_home:
                    home_deals_pool.append(p_copy)
                elif is_pooja:
                    pooja_deals_pool.append(p_copy)
                upsert_product_history(p, pincode, last_alert_date=today_date, last_alert_price=curr_price)

            # 5. 7-Day Hybrid Cooldown for Unchanged Static Items
            elif days_since_alert >= 7:
                # 7 days have elapsed -> show once a week
                p_copy = dict(p)
                p_copy["diff_type"] = DiffType.WEEKLY_PICK
                p_copy["diff_tag"] = "🗓️ WEEKLY TOP PICK"
                p_copy["diff_reason"] = "Weekly deal highlight (stable price)"
                alert_deals.append(p_copy)
                if is_home:
                    home_deals_pool.append(p_copy)
                elif is_pooja:
                    pooja_deals_pool.append(p_copy)
                upsert_product_history(p, pincode, last_alert_date=today_date, last_alert_price=curr_price)

            else:
                # Stale item (alerted < 7 days ago with no price change) -> Suppress from alert feed
                p_copy = dict(p)
                p_copy["diff_type"] = DiffType.STALE
                if is_home:
                    home_deals_pool.append(p_copy)
                elif is_pooja:
                    pooja_deals_pool.append(p_copy)
                stale_deals.append(p_copy)
                upsert_product_history(p, pincode)

    return alert_deals, home_deals_pool, pooja_deals_pool, stale_deals
