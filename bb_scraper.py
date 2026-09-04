import requests
import re
import uuid
import time
import random
import logging
import base64
from typing import List, Dict, Optional, Callable
from config import DEFAULT_CATEGORIES

logger = logging.getLogger("bb_scraper")

class BigBasketScraper:
    BASE_URL = "https://www.bigbasket.com"
    LISTING_API = f"{BASE_URL}/listing-svc/v2/products"
    VISITOR_API = f"{BASE_URL}/mapi/v3.5.2/create-visitor/?integratedglobalsa=true"
    AUTOCOMPLETE_API = f"{BASE_URL}/places/v1/places/autocomplete/"
    PLACE_DETAILS_API = f"{BASE_URL}/places/v1/places/details/"
    HEADER_API = f"{BASE_URL}/ui-svc/v2/header"

    def __init__(self, user_agent: Optional[str] = None):
        self.session = requests.Session()
        self.session_tracker = f"bb-py-{uuid.uuid4()}"
        self.ua = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
        self.session.headers.update({
            "User-Agent": self.ua,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "x-channel": "BB-WEB",
            "x-entry-context": "bb-b2c",
            "x-entry-context-id": "100",
            "x-tracker": self.session_tracker,
            "referer": "https://www.bigbasket.com/",
            "origin": "https://www.bigbasket.com"
        })
        self.current_pincode: Optional[str] = None
        self.location_name: Optional[str] = None
        self.is_initialized = False

    def bootstrap_session(self) -> bool:
        """Visits homepage to initialize base session and Akamai cookies."""
        try:
            r = self.session.get(self.BASE_URL, timeout=12)
            self.is_initialized = r.ok
            return r.ok
        except Exception as e:
            logger.error(f"Error bootstrapping BigBasket session: {e}")
            return False

    def set_pincode(self, pincode: str) -> bool:
        """
        Configures the session for a specific delivery pincode.
        Resolves geolocation, establishes local dark store / service area (SA) context,
        and sets essential cookies (_bb_sa_ids, _bb_cda_sa_info, is_global=0) so that
        listing APIs return genuine in-stock deals for the user's exact area instead of
        central warehouse clearance remnants.
        """
        pincode = str(pincode).strip()
        if not re.match(r'^\d{6}$', pincode):
            logger.warning(f"Invalid 6-digit Indian pincode format: {pincode}")
            return False

        if not self.is_initialized:
            self.bootstrap_session()

        token = str(uuid.uuid4())
        try:
            # 1. Autocomplete / place lookup
            auto_url = f"{self.AUTOCOMPLETE_API}?inputText={pincode}&token={token}"
            auto_res = self.session.get(auto_url, timeout=10)
            place_id = None
            if auto_res.ok:
                predictions = auto_res.json().get('predictions', [])
                if predictions:
                    place_id = predictions[0].get('placeId') or predictions[0].get('place_id')
                    self.location_name = predictions[0].get('description')

            # 2. Query place details for exact lat/long and city
            lat, lng = None, None
            city = "Bengaluru"
            if place_id:
                det_url = f"{self.PLACE_DETAILS_API}?placeId={place_id}&token={token}"
                det_res = self.session.get(det_url, timeout=10)
                if det_res.ok:
                    det_data = det_res.json()
                    loc = det_data.get('geometry', {}).get('location', {})
                    lat = loc.get('lat')
                    lng = loc.get('lng')
                    fmt_addr = det_data.get('formattedAddress')
                    if fmt_addr:
                        self.location_name = fmt_addr

                    for comp in det_data.get('addressComponents', []):
                        types = comp.get('types', [])
                        if 'locality' in types:
                            city = comp.get('longName')
                            break

            # 3. Fallback coordinates if autocomplete is unavailable
            if lat is None or lng is None:
                lat, lng = 12.9716, 77.5946  # Default fallback

            # 4. Construct BigBasket address and lat/long cookies
            lat_long_str = f"{lat}|{lng}"
            b64_lat_long = base64.b64encode(lat_long_str.encode()).decode()
            addr_str = f"{lat}|{lng}|{pincode}|{pincode}|{city}|1|false|true|true|Bigbasketeer"
            b64_addr = base64.b64encode(addr_str.encode()).decode()

            self.session.cookies.set('_bb_lat_long', b64_lat_long, domain='.bigbasket.com')
            self.session.cookies.set('_bb_addressinfo', b64_addr, domain='.bigbasket.com')
            self.session.cookies.set('_bb_pin_code', pincode, domain='.bigbasket.com')
            self.session.cookies.set('_bb_cid', '1', domain='.bigbasket.com')

            # 5. Resolve Local Dark Store & Service Area IDs via Header API
            ts = int(time.time() * 1000)
            header_url = f"{self.HEADER_API}/?send_door_info=true&send_address_set_by_user=true&i={ts}"
            h_res = self.session.get(header_url, timeout=10)
            if h_res.ok:
                h_data = h_res.json()
                add_cookies = h_data.get('additional_cookies', {})
                for k, v in add_cookies.items():
                    if v is not None:
                        self.session.cookies.set(k, str(v), domain='.bigbasket.com')

                self.current_pincode = pincode
                sa_id = add_cookies.get('_bb_sa_ids', self.session.cookies.get('_bb_sa_ids', 'Unknown'))
                logger.info(
                    f"Successfully bound BigBasket session to pincode {pincode} "
                    f"(Dark Store SA ID: {sa_id}, Area: {self.location_name or 'Resolved'})"
                )
                return True
            else:
                logger.warning(f"Header API returned status {h_res.status_code} for pincode {pincode}")
                # Fallback to visitor API registration
                vis_payload = {'z': pincode, 'is_bot': 'false', 'send_global_address': '0'}
                vis_res = self.session.post(
                    self.VISITOR_API,
                    data=vis_payload,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=10
                )
                if vis_res.ok:
                    cookie_dict = vis_res.json().get('response', {})
                    for k, v in cookie_dict.items():
                        if v:
                            self.session.cookies.set(k, str(v), domain='.bigbasket.com')
                    self.session.cookies.set('_bb_pin_code', pincode, domain='.bigbasket.com')
                    self.current_pincode = pincode
                    return True
                return False

        except Exception as e:
            logger.error(f"Exception setting pincode {pincode}: {e}")
            return False

    @staticmethod
    def calc_unit_price(sp: float, weight_str: str, name: str) -> str:
        """Calculates normalized unit price (per 100g, per kg, per L, per pc) matching bookmarklet logic."""
        if not sp or sp <= 0:
            return ""
        text = f"{weight_str} {name}".lower()

        g_match = re.search(r'([\d.]+)\s*(?:g|gm|gms|gram|grams)\b', text, re.I)
        if g_match:
            try:
                g = float(g_match.group(1))
                if g > 0:
                    p100 = (sp / g) * 100
                    return f"₹{round(p100)}/100g" if p100 >= 10 else f"₹{p100:.1f}/100g"
            except ValueError:
                pass

        kg_match = re.search(r'([\d.]+)\s*(?:kg|kgs|kilo|kilogram)\b', text, re.I)
        if kg_match:
            try:
                kg = float(kg_match.group(1))
                if kg > 0:
                    pkg = sp / kg
                    return f"₹{round(pkg)}/kg" if pkg >= 10 else f"₹{pkg:.1f}/kg"
            except ValueError:
                pass

        ml_match = re.search(r'([\d.]+)\s*(?:ml|mls|millilitre|milliliter)\b', text, re.I)
        if ml_match:
            try:
                ml = float(ml_match.group(1))
                if ml > 0:
                    p100 = (sp / ml) * 100
                    return f"₹{round(p100)}/100ml" if p100 >= 10 else f"₹{p100:.1f}/100ml"
            except ValueError:
                pass

        l_match = re.search(r'([\d.]+)\s*(?:l|ltr|litre|liter|litres)\b', text, re.I)
        if l_match:
            try:
                lit = float(l_match.group(1))
                if lit > 0:
                    pl = sp / lit
                    return f"₹{round(pl)}/L" if pl >= 10 else f"₹{pl:.1f}/L"
            except ValueError:
                pass

        pc_match = re.search(r'([\d.]+)\s*(?:pcs|pc|units|unit|count|sheets|wipes|diapers|tablets|capsules|caps)\b', text, re.I)
        if pc_match:
            try:
                pc = float(pc_match.group(1))
                if pc > 1:
                    ppc = sp / pc
                    return f"₹{round(ppc)}/pc" if ppc >= 10 else f"₹{ppc:.1f}/pc"
            except ValueError:
                pass

        return ""

    def parse_product(self, p: dict, cat_name: str) -> Optional[Dict]:
        """Parses a product JSON dictionary into a standardized deal dictionary."""
        if not p:
            return None

        mrp = float(
            p.get('pricing', {}).get('discount', {}).get('mrp')
            or p.get('pricing', {}).get('mrp')
            or p.get('mrp')
            or 0
        )
        sp = float(
            p.get('pricing', {}).get('discount', {}).get('prim_price', {}).get('sp')
            or p.get('pricing', {}).get('offer_price')
            or p.get('pricing', {}).get('sp')
            or p.get('sp')
            or 0
        )

        if sp <= 0 and mrp > 0:
            sp = mrp

        if mrp <= 0 or sp <= 0:
            return None

        disc = round(((mrp - sp) / mrp) * 100, 1)
        savings = round(max(0, mrp - sp), 2)

        avail = p.get('availability', {})
        button_val = str(avail.get('button') or '').strip().lower()
        button_state = str(avail.get('button_state') or '').strip().upper()
        avail_status = str(avail.get('avail_status') or '').strip()
        not_for_sale = bool(avail.get('not_for_sale'))
        is_available = avail.get('is_available')

        # Strict Out of Stock detection:
        # Item is only purchasable if avail_status is '001', button is 'Add', and not marked not_for_sale
        is_oos = bool(
            is_available is False
            or p.get('is_available') is False
            or p.get('all_stores_oos') is True
            or not_for_sale is True
            or (avail_status and avail_status != '001')
            or (button_val and button_val not in ('add', 'in basket'))
            or button_state in ('OUT_OF_STOCK', 'NOT_AVAILABLE', 'COMING_SOON', 'NOTIFY_ME', 'DISABLED')
        )

        prod_id = str(p.get('id') or '')
        name = p.get('desc') or p.get('p_desc') or p.get('name') or 'Product'
        weight_str = p.get('w') or p.get('pack_desc') or ''
        if weight_str and weight_str not in name:
            full_name = f"{name} ({weight_str})"
        else:
            full_name = name

        brand = p.get('brand', {}).get('name') or p.get('p_brand') or 'BigBasket'
        unit_price = self.calc_unit_price(sp, weight_str, name)

        abs_url = p.get('absolute_url', '')
        if abs_url:
            prod_url = abs_url if abs_url.startswith('http') else f"https://www.bigbasket.com{abs_url}"
        else:
            prod_url = f"https://www.bigbasket.com/pd/{prod_id}"

        images = p.get('images', [])
        img_url = images[0].get('s') or images[0].get('m') if images else 'https://www.bigbasket.com/static/images/default.jpg'

        return {
            "id": prod_id,
            "name": full_name,
            "brand": brand,
            "mrp": round(mrp, 2),
            "sp": round(sp, 2),
            "savings": savings,
            "disc": disc,
            "unit_price": unit_price,
            "is_out_of_stock": is_oos,
            "url": prod_url,
            "img": img_url,
            "category": cat_name
        }

    def fetch_category_page(self, slug: str, page: int = 1, retries: int = 2) -> Optional[dict]:
        """Fetches a single page of deals for a category, sorted by discount percentage high-to-low."""
        url = f"{self.LISTING_API}?type=pc&slug={slug}&page={page}&sort=dphtl"
        for attempt in range(retries + 1):
            try:
                self.session.headers["x-tracker"] = f"bb-py-{uuid.uuid4()}"
                res = self.session.get(url, timeout=12)
                if res.ok:
                    return res.json()
                elif res.status_code == 429:
                    wait_time = (attempt + 1) * 5.0
                    logger.warning(f"Rate limited (429) on {slug} P{page}. Backing off {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.warning(f"Failed to fetch {slug} P{page}: Status {res.status_code}")
            except Exception as e:
                logger.error(f"Network error fetching {slug} P{page}: {e}")
                time.sleep(2.0)
        return None

    def fetch_deals(
        self,
        pincode: Optional[str] = None,
        min_discount: float = 70.0,
        exclude_out_of_stock: bool = True,
        max_pages: int = 2,
        categories: Optional[List[tuple]] = None,
        on_progress: Optional[Callable[[str, int, int], None]] = None
    ) -> List[Dict]:
        """
        Scans BigBasket categories for deals meeting or exceeding `min_discount`.
        Returns deduplicated product deals sorted by discount % descending.
        """
        if pincode:
            self.set_pincode(pincode)
        elif not self.is_initialized:
            self.bootstrap_session()

        cats = categories or DEFAULT_CATEGORIES
        total_cats = len(cats)
        all_deals: List[Dict] = []
        seen_ids = set()

        for idx, (cat_name, slug) in enumerate(cats, 1):
            if on_progress:
                on_progress(cat_name, idx, total_cats)
            logger.info(f"[{idx}/{total_cats}] Scanning {cat_name}...")

            for page in range(1, max_pages + 1):
                data = self.fetch_category_page(slug, page=page)
                if not data:
                    continue

                tabs = data.get('tabs', [])
                products = []
                if tabs and isinstance(tabs, list):
                    for t in tabs:
                        tab_prods = t.get('product_info', {}).get('products', [])
                        if tab_prods:
                            products = tab_prods
                            break
                if not products:
                    products = data.get('product_info', {}).get('products') or data.get('products') or []

                page_deal_count = 0
                for p in products:
                    deal = self.parse_product(p, cat_name)
                    if deal and deal['id'] not in seen_ids:
                        if deal['disc'] >= min_discount:
                            if not (exclude_out_of_stock and deal['is_out_of_stock']):
                                seen_ids.add(deal['id'])
                                all_deals.append(deal)
                                page_deal_count += 1

                    # Check children / variant products
                    children = p.get('children', [])
                    if isinstance(children, list):
                        for c in children:
                            c_deal = self.parse_product(c, cat_name)
                            if c_deal and c_deal['id'] not in seen_ids:
                                if c_deal['disc'] >= min_discount:
                                    if not (exclude_out_of_stock and c_deal['is_out_of_stock']):
                                        seen_ids.add(c_deal['id'])
                                        all_deals.append(c_deal)
                                        page_deal_count += 1

                # Polite delay between pages
                time.sleep(random.uniform(1.2, 1.8))

            # Polite delay between categories
            time.sleep(random.uniform(2.2, 3.2))

        # Sort all deals from highest discount % to lowest
        all_deals.sort(key=lambda x: x['disc'], reverse=True)
        return all_deals
