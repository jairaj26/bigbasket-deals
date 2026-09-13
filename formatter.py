import html
from typing import List, Dict, Optional

def format_deal_item(index: int, deal: Dict) -> str:
    """
    Formats a single deal item into clean Telegram HTML:
    - Product name
    - Brand
    - Selling price & MRP (with price drop indication if applicable)
    - Discount percentage
    - Click here link
    """
    name = html.escape(deal.get('name', 'Product'))
    brand = html.escape(deal.get('brand', 'BigBasket'))
    sp = float(deal.get('sp', 0.0))
    mrp = float(deal.get('mrp', 0.0))
    disc = float(deal.get('disc', 0.0))
    unit_price = deal.get('unit_price', '')
    url = deal.get('url', 'https://www.bigbasket.com')
    diff_tag = deal.get('diff_tag', '')
    diff_reason = deal.get('diff_reason', '')

    unit_price_str = f" ({html.escape(unit_price)})" if unit_price else ""
    tag_str = f" <i>[{html.escape(diff_tag)}]</i>" if diff_tag else ""

    item_html = (
        f"<b>{index}. {name}</b>{tag_str}\n"
        f"🏷️ Brand: <i>{brand}</i>\n"
        f"💰 Selling Price: <b>₹{sp:.2f}</b>  <s>₹{mrp:.2f}</s>{unit_price_str}\n"
    )

    if diff_reason and "dropped from" in diff_reason.lower():
        item_html += f"   <i>↳ {html.escape(diff_reason)}</i>\n"

    item_html += (
        f"🔥 Discount: <b>{disc:.1f}% OFF</b>\n"
        f"🔗 <a href=\"{url}\">Click here to view</a>\n"
    )
    return item_html

def format_deals_message(
    deals: List[Dict],
    pincode: str = "560001",
    location_name: str = "",
    min_discount: float = 70.0,
    max_items: int = 50,
    header_title: Optional[str] = None
) -> List[str]:
    """
    Builds one or more chunked Telegram messages (each <= 3900 characters)
    containing the formatted deal list.
    """
    if not deals:
        loc_str = f" for <b>{pincode}</b>" if pincode else ""
        return [
            f"🛒 <b>BigBasket Deal Finder</b>\n\n"
            f"No deals found with ≥ {min_discount:.0f}% OFF{loc_str} right now.\n"
            f"Check back later or try another pincode!"
        ]

    loc_header = f"📍 Pincode: <b>{pincode}</b>"
    if location_name:
        clean_loc = html.escape(location_name)
        loc_header += f" (<i>{clean_loc}</i>)"

    total_deals = len(deals)
    display_deals = deals[:max_items]

    title = header_title or f"🛒 <b>BigBasket {min_discount:.0f}%+ OFF Deals</b>"
    header = (
        f"{title}\n"
        f"{loc_header}\n"
        f"✨ Found <b>{total_deals}</b> deals (showing top {len(display_deals)}):\n\n"
    )

    messages: List[str] = []
    current_msg = header

    for idx, deal in enumerate(display_deals, 1):
        item_text = format_deal_item(idx, deal) + "\n"
        if len(current_msg) + len(item_text) > 3900:
            messages.append(current_msg)
            current_msg = f"🛒 <b>BigBasket Deals (Cont.)</b>\n\n" + item_text
        else:
            current_msg += item_text

    if current_msg:
        messages.append(current_msg)

    return messages

def format_grouped_deals_message(
    grouped_deals: Dict[str, List[Dict]],
    pincode: str = "560001",
    location_name: str = "",
    min_discount: float = 70.0,
    max_items_per_category: int = 15
) -> List[str]:
    """
    Formats deals grouped cleanly by category buckets:
    - 🪔 Pooja, Festive & Seasonal
    - 🏠 Home, Kitchen & Cleaning
    - 🌾 Staples, Oil & Masala
    - etc.
    """
    total_deals = sum(len(items) for items in grouped_deals.values())
    if total_deals == 0:
        return format_deals_message([], pincode=pincode, location_name=location_name, min_discount=min_discount)

    loc_header = f"📍 Pincode: <b>{pincode}</b>"
    if location_name:
        clean_loc = html.escape(location_name)
        loc_header += f" (<i>{clean_loc}</i>)"

    header = (
        f"🛒 <b>BigBasket {min_discount:.0f}%+ OFF Deals by Category</b>\n"
        f"{loc_header}\n"
        f"✨ Found <b>{total_deals}</b> active deals:\n\n"
    )

    messages: List[str] = []
    current_msg = header

    for bucket_name, items in grouped_deals.items():
        if not items:
            continue

        section_header = f"\n━━━━━━━━━━━━━━━━━━━━\n<b>{html.escape(bucket_name)}</b> ({len(items)} deals)\n━━━━━━━━━━━━━━━━━━━━\n\n"
        if len(current_msg) + len(section_header) > 3900:
            messages.append(current_msg)
            current_msg = section_header
        else:
            current_msg += section_header

        for idx, deal in enumerate(items[:max_items_per_category], 1):
            item_text = format_deal_item(idx, deal) + "\n"
            if len(current_msg) + len(item_text) > 3900:
                messages.append(current_msg)
                current_msg = f"<b>{html.escape(bucket_name)} (Cont.)</b>\n\n" + item_text
            else:
                current_msg += item_text

    if current_msg:
        messages.append(current_msg)

    return messages
