import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env if present
env_path = Path(__file__).resolve().parent / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '').strip()
DEFAULT_PINCODE = os.getenv('PINCODE', '560001').strip()
MIN_DISCOUNT = float(os.getenv('MIN_DISCOUNT', '70'))
MAX_PAGES_PER_CATEGORY = int(os.getenv('MAX_PAGES_PER_CATEGORY', '2'))
EXCLUDE_OUT_OF_STOCK = os.getenv('EXCLUDE_OUT_OF_STOCK', 'true').lower() in ('true', '1', 'yes')
COOLDOWN_HOURS = int(os.getenv('COOLDOWN_HOURS', '48'))

# BigBasket Canonical Categories (matching the bookmarklet)
DEFAULT_CATEGORIES = [
    ("Baby Care", "baby-care"),
    ("Diapers & Wipes", "diapers-wipes"),
    ("Snacks & Branded Foods", "snacks-branded-foods"),
    ("Biscuits & Cookies", "biscuits-cookies"),
    ("Chocolates & Candies", "chocolates-candies"),
    ("Foodgrains, Oil & Masala", "foodgrains-oil-masala"),
    ("Edible Oils & Ghee", "edible-oils-ghee"),
    ("Dry Fruits", "dry-fruits"),
    ("Bakery, Cakes & Dairy", "bakery-cakes-dairy"),
    ("Dairy", "dairy"),
    ("Beverages (Tea/Coffee)", "beverages"),
    ("Beauty & Hygiene", "beauty-hygiene"),
    ("Skin Care", "skin-care"),
    ("Hair Care", "hair-care"),
    ("Bath & Hand Wash", "bath-hand-wash"),
    ("Cleaning & Household", "cleaning-household"),
    ("Detergents & Dishwash", "detergents-dishwash"),
    ("Gourmet & World Food", "gourmet-world-food"),
    ("Kitchen & Home Needs", "kitchen-garden-pets"),
    ("Fruits & Vegetables", "fruits-vegetables"),
]
