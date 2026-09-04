import html
from typing import List, Dict

def format_deal_item(index: int, deal: Dict) -> str:
    """
    Formats a single deal item into Telegram HTML:
    - Product name
    - Brand
    - Selling price & MRP
    - Discount percentage
    - Click here link
    """
    name = html.escape(deal.get('name', 'Product'))
    brand = html.escape(deal.get('brand', 'BigBasket'))
    sp = deal.get('sp', 0.0)
    mrp = deal.get('mrp', 0.0)
    disc = deal.get('disc', 0.0)
    unit_price = deal.get('unit_price', '')
    url = deal.get('url', 'https://www.bigbasket.com')

    unit_price_str = f" ({html.escape(unit_price)})" if unit_price else ""

    item_html = (
        f"<b>{index}. {name}</b>\n"
        f"🏷️ Brand: <i>{brand}</i>\n"
        f"💰 Selling Price: <b>₹{sp:.2f}</b>  <s>₹{mrp:.2f}</s>{unit_price_str}\n"
        f"🔥 Discount: <b>{disc:.1f}% OFF</b>\n"
        f"🔗 <a href=\"{url}\">Click here to view</a>\n"
    )
    return item_html

def format_deals_message(
    deals: List[Dict],
    pincode: str = "560001",
    location_name: str = "",
    min_discount: float = 70.0,
    max_items: int = 50
) -> List[str]:
    """
    Builds one or more chunked Telegram messages (each <= 4000 characters)
    containing the requested formatted deal list.
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

    header = (
        f"🛒 <b>BigBasket {min_discount:.0f}%+ OFF Deals</b>\n"
        f"{loc_header}\n"
        f"✨ Found <b>{total_deals}</b> deals (showing top {len(display_deals)}):\n\n"
    )

    messages: List[str] = []
    current_msg = header

    for idx, deal in enumerate(display_deals, 1):
        item_text = format_deal_item(idx, deal) + "\n"
        if len(current_msg) + len(item_text) > 3900:
            messages.append(current_msg)
            current_msg = f"🛒 <b>BigBasket {min_discount:.0f}%+ Deals (Cont.)</b>\n\n" + item_text
        else:
            current_msg += item_text

    if current_msg:
        messages.append(current_msg)

    return messages
