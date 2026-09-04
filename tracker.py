import sqlite3
import time
from pathlib import Path
from typing import List, Dict

DB_PATH = Path(__file__).resolve().parent / "seen_deals.db"

class DealTracker:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
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

    def filter_unseen_deals(self, deals: List[Dict], pincode: str, cooldown_hours: int = 48) -> List[Dict]:
        """
        Returns only deals that:
        1. Have never been posted for this pincode, OR
        2. Had their price drop even lower, OR
        3. Were posted longer than `cooldown_hours` ago.
        """
        if not deals:
            return []

        pincode = str(pincode).strip()
        cutoff_time = time.time() - (cooldown_hours * 3600)
        unseen = []

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            for d in deals:
                prod_id = str(d['id'])
                cursor.execute(
                    "SELECT sp, posted_at FROM seen_deals WHERE id = ? AND pincode = ?",
                    (prod_id, pincode)
                )
                row = cursor.fetchone()
                if row is None:
                    # Brand new deal
                    unseen.append(d)
                else:
                    prev_sp, posted_at = row
                    current_sp = float(d['sp'])
                    # If price dropped further, or cooldown elapsed
                    if current_sp < prev_sp or posted_at < cutoff_time:
                        unseen.append(d)

        return unseen

    def mark_deals_as_seen(self, deals: List[Dict], pincode: str):
        """Records deals in database with current timestamp."""
        if not deals:
            return

        pincode = str(pincode).strip()
        now = time.time()
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO seen_deals (id, pincode, name, sp, disc, posted_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (str(d['id']), pincode, d['name'], float(d['sp']), float(d['disc']), now)
                    for d in deals
                ]
            )
            conn.commit()

    def get_stats(self) -> dict:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM seen_deals")
            total = cursor.fetchone()[0]
            return {"total_seen": total}
