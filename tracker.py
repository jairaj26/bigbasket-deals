import sqlite3
import time
from pathlib import Path
from typing import List, Dict, Optional, Any

DB_PATH = Path(__file__).resolve().parent / "seen_deals.db"

def get_db_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Creates a connection with Row factory."""
    path = db_path if db_path is not None else DB_PATH
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path: Optional[Path] = None):
    """Initializes and migrates the database schema."""
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS product_history (
                product_uid TEXT,
                pincode TEXT,
                name TEXT,
                brand TEXT,
                category_bucket TEXT,
                effective_price REAL,
                mrp REAL,
                discount_pct REAL,
                savings REAL,
                in_stock BOOLEAN,
                url TEXT,
                unit_price TEXT,
                last_alert_date TEXT,
                last_alert_price REAL,
                first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (product_uid, pincode)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS seen_deals (
                id TEXT,
                pincode TEXT,
                name TEXT,
                sp REAL,
                disc REAL,
                posted_at REAL,
                PRIMARY KEY (id, pincode)
            )
        """)
        conn.commit()
    finally:
        conn.close()

# Run init on module load
init_db()

def get_product_history(product_uid: str, pincode: str, db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Fetches historical price and alert data for a product in a specific pincode."""
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM product_history
            WHERE product_uid = ? AND pincode = ?
        """, (str(product_uid), str(pincode).strip()))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def upsert_product_history(
    product: Dict[str, Any],
    pincode: str,
    last_alert_date: Optional[str] = None,
    last_alert_price: Optional[float] = None,
    db_path: Optional[Path] = None
) -> None:
    """Inserts or updates product price history and alert timestamps."""
    pincode = str(pincode).strip()
    uid = str(product.get("id") or product.get("url") or product.get("name"))
    name = str(product.get("name") or "Product")
    brand = str(product.get("brand") or "BigBasket")
    bucket = str(product.get("category_bucket") or "")
    sp = float(product.get("sp") or 0.0)
    mrp = float(product.get("mrp") or sp)
    disc = float(product.get("disc") or 0.0)
    savings = float(product.get("savings") or max(0, mrp - sp))
    in_stock = not bool(product.get("is_out_of_stock", False))
    url = str(product.get("url") or "")
    unit_price = str(product.get("unit_price") or "")

    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        existing = get_product_history(uid, pincode, db_path)

        if not existing:
            cursor.execute("""
                INSERT INTO product_history (
                    product_uid, pincode, name, brand, category_bucket,
                    effective_price, mrp, discount_pct, savings, in_stock,
                    url, unit_price, last_alert_date, last_alert_price
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                uid, pincode, name, brand, bucket,
                sp, mrp, disc, savings, in_stock,
                url, unit_price, last_alert_date, last_alert_price
            ))
        else:
            new_alert_date = last_alert_date if last_alert_date is not None else existing.get("last_alert_date")
            new_alert_price = last_alert_price if last_alert_price is not None else existing.get("last_alert_price")

            cursor.execute("""
                UPDATE product_history SET
                    name = ?, brand = ?, category_bucket = ?,
                    effective_price = ?, mrp = ?, discount_pct = ?, savings = ?,
                    in_stock = ?, url = ?, unit_price = ?,
                    last_alert_date = ?, last_alert_price = ?,
                    last_seen_at = CURRENT_TIMESTAMP
                WHERE product_uid = ? AND pincode = ?
            """, (
                name, brand, bucket,
                sp, mrp, disc, savings,
                in_stock, url, unit_price,
                new_alert_date, new_alert_price,
                uid, pincode
            ))
        conn.commit()
    finally:
        conn.close()


class DealTracker:
    """Wrapper class providing backwards compatibility for existing CLI runs."""
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        init_db(self.db_path)

    def filter_unseen_deals(self, deals: List[Dict], pincode: str, cooldown_hours: int = 168) -> List[Dict]:
        """
        Filters deals using the 7-day (168 hour) hybrid differ.
        Imports deal_differ dynamically to avoid circular imports.
        """
        if not deals:
            return []
        from deal_differ import analyze_and_update_deals
        alert_deals, _, _, _ = analyze_and_update_deals(deals, pincode)
        return alert_deals

    def mark_deals_as_seen(self, deals: List[Dict], pincode: str):
        """Backwards compatible deal recorder."""
        if not deals:
            return
        from deal_differ import get_current_ist_date
        today = get_current_ist_date()
        for d in deals:
            upsert_product_history(d, pincode, last_alert_date=today, last_alert_price=float(d.get('sp', 0.0)), db_path=self.db_path)

    def get_stats(self) -> dict:
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM product_history")
            total = cursor.fetchone()[0]
            return {"total_tracked": total}
